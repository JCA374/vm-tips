"""Match data service - Fetch matches and results from football API"""
import requests
from datetime import datetime, timedelta, timezone
from sqlalchemy import or_, and_
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


def after_90_total(score, stage):
    """Return the (home, away) total after extra time + penalties for a knockout
    match decided beyond 90 minutes, else (None, None).

    The API's fullTime score already includes extra time and the shootout; we
    only surface it when it differs from the 90-minute (regularTime) result, so
    matches won in normal time get no parenthetical score.
    """
    if stage not in KNOCKOUT_STAGES:
        return None, None
    reg = score.get('regularTime') or {}
    full = score.get('fullTime') or {}
    if reg.get('home') is None or full.get('home') is None:
        return None, None
    if (full['home'], full['away']) == (reg['home'], reg['away']):
        return None, None
    return full['home'], full['away']


# Our internal round names for the knockout phase (map_stage_to_round values).
KNOCKOUT_ROUNDS = {
    'round_of_32', 'round_of_16', 'quarter_final',
    'semi_final', 'third_place', 'final',
}


def knockout_aware_score(score, stage):
    """Return (home, away, home_ft, away_ft) for a finished match.

    For knockout matches the 1X2 score uses the 90-minute (regularTime) result
    so extra time and penalties don't change the outcome; home_ft/away_ft carry
    the after-90 total for display. Falls back to fullTime when the API hasn't
    populated the regularTime breakdown yet.
    """
    if stage in KNOCKOUT_STAGES and score.get('regularTime', {}).get('home') is not None:
        home = score['regularTime']['home']
        away = score['regularTime']['away']
    else:
        home = score['fullTime']['home']
        away = score['fullTime']['away']
    home_ft, away_ft = after_90_total(score, stage)
    return home, away, home_ft, away_ft


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
            # - Matches older than 2 days that are already finished in our DB
            # - Future unfinished matches where team names haven't changed
            if existing:
                if existing.finished and match_date < cutoff:
                    skipped += 1
                    continue
                if match_date > now and not finished:
                    # Still update if team names changed (TBD → real team)
                    teams_changed = (existing.home_team != home_team or existing.away_team != away_team)
                    if not teams_changed:
                        skipped += 1
                        continue

            if finished:
                home_goals, away_goals, home_goals_ft, away_goals_ft = \
                    knockout_aware_score(match_data['score'], stage)
            else:
                home_goals = None
                away_goals = None
                home_goals_ft = None
                away_goals_ft = None

            if existing:
                existing.home_team = home_team
                existing.away_team = away_team
                existing.group = group
                existing.match_date = match_date
                existing.home_goals = home_goals
                existing.away_goals = away_goals
                existing.home_goals_ft = home_goals_ft
                existing.away_goals_ft = away_goals_ft
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
                    home_goals_ft=home_goals_ft,
                    away_goals_ft=away_goals_ft,
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


def sync_tbd_teams(competition_id=2000):
    """Fetch team names for upcoming matches that still have TBD teams"""
    client = FootballAPIClient()
    data = client.get_competition_matches(competition_id)

    if not data or 'matches' not in data:
        return {'status': 'error', 'message': 'Failed to fetch matches'}

    db = SessionLocal()
    updated = 0

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

            existing = db.query(Match).filter_by(external_id=external_id).first()
            if not existing:
                continue

            # Only update matches that still have TBD and API now has real names
            if (existing.home_team == 'TBD' and home_team != 'TBD') or \
               (existing.away_team == 'TBD' and away_team != 'TBD'):
                existing.home_team = home_team
                existing.away_team = away_team
                existing.updated_at = datetime.utcnow()
                updated += 1

        db.commit()
        return {'status': 'success', 'updated': updated}

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
    """Fetch results for unfinished matches, and re-check recently-played
    knockout matches so a result stored before the API populated its
    regular-time breakdown (extra-time games) self-corrects to the 90-minute
    score.
    """
    db = SessionLocal()
    try:
        # Re-check finished knockout matches for a short window after kickoff:
        # the bulk feed can mark a match FINISHED with only the fullTime score,
        # then backfill regularTime, which would otherwise be missed once the
        # match is frozen.
        recheck_cutoff = datetime.utcnow() - timedelta(days=3)
        to_check = db.query(Match).filter(
            or_(
                Match.finished == False,
                and_(
                    Match.finished == True,
                    Match.round.in_(KNOCKOUT_ROUNDS),
                    Match.match_date >= recheck_cutoff,
                ),
            )
        ).all()
        client = FootballAPIClient()
        updated = 0

        for match in to_check:
            # The /matches/{id} endpoint returns the match object at the top
            # level (no 'match' wrapper), and carries the regularTime breakdown
            # the bulk competition feed sometimes omits.
            data = client.get_match_by_id(match.external_id)
            if not data or data.get('status') not in ('FINISHED', 'AWARDED'):
                continue

            stage = data.get('stage', '')
            home_goals, away_goals, home_goals_ft, away_goals_ft = \
                knockout_aware_score(data['score'], stage)

            if (match.home_goals, match.away_goals,
                    match.home_goals_ft, match.away_goals_ft, match.finished) == \
                    (home_goals, away_goals, home_goals_ft, away_goals_ft, True):
                continue

            match.home_goals = home_goals
            match.away_goals = away_goals
            match.home_goals_ft = home_goals_ft
            match.away_goals_ft = away_goals_ft
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
