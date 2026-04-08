"""Match data service - Fetch matches and results from football API"""
import requests
from datetime import datetime
from config import settings
from database.models import Match, get_db, SessionLocal


class FootballAPIClient:
    """Client for football-data.org API"""

    def __init__(self):
        self.base_url = settings.FOOTBALL_API_URL
        self.api_key = settings.FOOTBALL_API_KEY
        self.headers = {
            'X-Auth-Token': self.api_key
        }

    def get_competition_matches(self, competition_id, stage='KNOCKOUT'):
        """
        Get matches for a specific competition
        competition_id: e.g., 2000 for World Cup
        stage: KNOCKOUT for knockout rounds
        """
        url = f'{self.base_url}/competitions/{competition_id}/matches'
        params = {'stage': stage}

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f'Error fetching matches: {e}')
            return None

    def get_match_by_id(self, match_id):
        """Get specific match by ID"""
        url = f'{self.base_url}/matches/{match_id}'

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f'Error fetching match {match_id}: {e}')
            return None


def map_stage_to_round(stage_name):
    """Map API stage name to our round names"""
    mapping = {
        'ROUND_OF_16': 'round_of_16',
        'QUARTER_FINALS': 'quarter_final',
        'SEMI_FINALS': 'semi_final',
        'FINAL': 'final'
    }
    return mapping.get(stage_name, stage_name.lower())


def sync_matches(competition_id=2000):
    """
    Sync matches from football API to database
    competition_id: 2000 is FIFA World Cup
    """
    client = FootballAPIClient()
    data = client.get_competition_matches(competition_id)

    if not data or 'matches' not in data:
        return {'status': 'error', 'message': 'Failed to fetch matches'}

    db = SessionLocal()
    synced = 0
    updated = 0

    try:
        for match_data in data['matches']:
            # Extract match info
            external_id = match_data['id']
            stage = match_data.get('stage', '')
            round_name = map_stage_to_round(stage)

            home_team = match_data['homeTeam']['name']
            away_team = match_data['awayTeam']['name']
            match_date = datetime.fromisoformat(match_data['utcDate'].replace('Z', '+00:00'))

            # Check if match finished
            status = match_data['status']
            finished = status in ['FINISHED', 'AWARDED']

            home_goals = match_data['score']['fullTime']['home'] if finished else None
            away_goals = match_data['score']['fullTime']['away'] if finished else None

            # Check if match exists
            existing = db.query(Match).filter_by(external_id=external_id).first()

            if existing:
                # Update existing match
                existing.home_team = home_team
                existing.away_team = away_team
                existing.match_date = match_date
                existing.home_goals = home_goals
                existing.away_goals = away_goals
                existing.finished = finished
                existing.updated_at = datetime.utcnow()
                updated += 1
            else:
                # Create new match
                new_match = Match(
                    external_id=external_id,
                    round=round_name,
                    home_team=home_team,
                    away_team=away_team,
                    match_date=match_date,
                    home_goals=home_goals,
                    away_goals=away_goals,
                    finished=finished
                )
                db.add(new_match)
                synced += 1

        db.commit()
        return {
            'status': 'success',
            'synced': synced,
            'updated': updated,
            'total': synced + updated
        }

    except Exception as e:
        db.rollback()
        return {'status': 'error', 'message': str(e)}
    finally:
        db.close()


def get_upcoming_matches(round_name=None):
    """Get upcoming (unfinished) matches, optionally filtered by round"""
    db = SessionLocal()
    try:
        query = db.query(Match).filter_by(finished=False)
        if round_name:
            query = query.filter_by(round=round_name)

        return query.order_by(Match.match_date).all()
    finally:
        db.close()


def get_finished_matches(round_name=None):
    """Get finished matches, optionally filtered by round"""
    db = SessionLocal()
    try:
        query = db.query(Match).filter_by(finished=True)
        if round_name:
            query = query.filter_by(round=round_name)

        return query.order_by(Match.match_date.desc()).all()
    finally:
        db.close()


def update_match_results():
    """Update results for all unfinished matches"""
    db = SessionLocal()
    try:
        unfinished = db.query(Match).filter_by(finished=False).all()
        client = FootballAPIClient()
        updated = 0

        for match in unfinished:
            data = client.get_match_by_id(match.external_id)
            if data and 'match' in data:
                match_info = data['match']
                status = match_info['status']

                if status in ['FINISHED', 'AWARDED']:
                    match.home_goals = match_info['score']['fullTime']['home']
                    match.away_goals = match_info['score']['fullTime']['away']
                    match.finished = True
                    match.updated_at = datetime.utcnow()
                    updated += 1

        db.commit()
        return {'status': 'success', 'updated': updated}

    except Exception as e:
        db.rollback()
        return {'status': 'error', 'message': str(e)}
    finally:
        db.close()
