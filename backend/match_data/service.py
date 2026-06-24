"""Match data service - Fetch matches and results from football API"""
import requests
from datetime import datetime, timedelta, timezone
from backend import config
from backend.models import Match, get_db, SessionLocal


class FootballAPIClient:
    """Client for football-data.org API"""

    def __init__(self):
        self.base_url = config.FOOTBALL_API_URL
        self.api_key = config.FOOTBALL_API_KEY
        self.headers = {
            'X-Auth-Token': self.api_key
        }

    def get_competition_matches(self, competition_id):
        """
        Get all matches for a specific competition
        competition_id: e.g., 2000 for World Cup
        """
        url = f'{self.base_url}/competitions/{competition_id}/matches'

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
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


KNOCKOUT_STAGES = {'LAST_32', 'LAST_16', 'QUARTER_FINALS', 'SEMI_FINALS', 'THIRD_PLACE', 'FINAL'}

def map_stage_to_round(stage_name, matchday=None):
    """Map API stage name (+ matchday) to our round names"""
    if stage_name == 'GROUP_STAGE' and matchday:
        return f'group_md{matchday}'
    mapping = {
        'LAST_32': 'round_of_32',
        'LAST_16': 'round_of_16',
        'QUARTER_FINALS': 'quarter_final',
        'SEMI_FINALS': 'semi_final',
        'THIRD_PLACE': 'third_place',
        'FINAL': 'final',
    }
    return mapping.get(stage_name)


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
    skipped = 0
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=2)

    try:
        for match_data in data['matches']:
            stage = match_data.get('stage', '')
            matchday = match_data.get('matchday')

            round_name = map_stage_to_round(stage, matchday)
            if not round_name:
                continue

            external_id = match_data['id']
            home_team = match_data['homeTeam']['name'] or 'TBD'
            away_team = match_data['awayTeam']['name'] or 'TBD'
            group = match_data.get('group') or ''
            match_date = datetime.fromisoformat(match_data['utcDate'].replace('Z', '+00:00'))

            status = match_data['status']
            finished = status in ['FINISHED', 'AWARDED']

            existing = db.query(Match).filter_by(external_id=external_id).first()

            # Skip matches that don't need updating:
            # - Future matches (not started yet, no results to collect)
            # - Matches older than 2 days that are already finished in our DB
            if existing:
                if match_date > now and not finished:
                    skipped += 1
                    continue
                if existing.finished and match_date < cutoff:
                    skipped += 1
                    continue

            if finished:
                score = match_data['score']
                # Knockout matches: use regularTime (90 min) so extra time
                # and penalties don't affect 1X2 outcome
                if stage in KNOCKOUT_STAGES and score.get('regularTime', {}).get('home') is not None:
                    home_goals = score['regularTime']['home']
                    away_goals = score['regularTime']['away']
                else:
                    home_goals = score['fullTime']['home']
                    away_goals = score['fullTime']['away']
            else:
                home_goals = None
                away_goals = None

            if existing:
                existing.home_team = home_team
                existing.away_team = away_team
                existing.group = group
                existing.match_date = match_date
                existing.home_goals = home_goals
                existing.away_goals = away_goals
                existing.finished = finished
                existing.updated_at = datetime.utcnow()
                updated += 1
            else:
                db.add(Match(
                    external_id=external_id,
                    round=round_name,
                    group=group,
                    home_team=home_team,
                    away_team=away_team,
                    match_date=match_date,
                    home_goals=home_goals,
                    away_goals=away_goals,
                    finished=finished,
                ))
                synced += 1

        db.commit()
        return {
            'status': 'success',
            'synced': synced,
            'updated': updated,
            'skipped': skipped,
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
                    score = match_info['score']
                    stage = match_info.get('stage', '')
                    # Knockout: use regularTime (90 min) so extra time/penalties
                    # don't affect 1X2 outcome
                    if stage in KNOCKOUT_STAGES and score.get('regularTime', {}).get('home') is not None:
                        match.home_goals = score['regularTime']['home']
                        match.away_goals = score['regularTime']['away']
                    else:
                        match.home_goals = score['fullTime']['home']
                        match.away_goals = score['fullTime']['away']
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
