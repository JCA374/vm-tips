"""Tests for leaderboard scoring — points are calculated from actual match results."""
import pytest
from datetime import datetime, timedelta
from conftest import BASE_URL, create_test_match


def _create_prediction(user_id, match_id, outcome=None, home_goals=None, away_goals=None):
    """Insert a prediction directly into the DB."""
    from backend.models import Prediction, SessionLocal
    db = SessionLocal()
    try:
        pred = Prediction(
            user_id=user_id,
            match_id=match_id,
            predicted_outcome=outcome,
            predicted_home_goals=home_goals,
            predicted_away_goals=away_goals,
        )
        db.add(pred)
        db.commit()
        return pred.id
    finally:
        db.close()


def _finish_match(match_id, home_goals, away_goals):
    """Mark a match as finished with a final score."""
    from backend.models import Match, SessionLocal
    db = SessionLocal()
    try:
        match = db.query(Match).filter_by(id=match_id).first()
        match.finished = True
        match.home_goals = home_goals
        match.away_goals = away_goals
        db.commit()
    finally:
        db.close()


def _create_user(email, name):
    """Create a user directly in the DB, return user id."""
    from backend.models import User, SessionLocal
    db = SessionLocal()
    try:
        user = User(email=email, name=name)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


# ── Unit tests: calculate_all_scores recalculates from results ───────────────

def test_calculate_all_scores_updates_points():
    """calculate_all_scores should compute points from finished match results."""
    from backend.prediction.service import calculate_all_scores

    user_id = _create_user('scorer@test.com', 'Scorer')
    match_id = create_test_match('Italy', 'Spain', round_name='group_md1')

    # Predict home win (1)
    _create_prediction(user_id, match_id, outcome='1')

    # Finish match with home win 2-0 → correct outcome → 1 pt
    _finish_match(match_id, home_goals=2, away_goals=0)

    result = calculate_all_scores()
    assert result['status'] == 'success'
    assert result['updated'] >= 1

    from backend.models import Prediction, SessionLocal
    db = SessionLocal()
    pred = db.query(Prediction).filter_by(user_id=user_id, match_id=match_id).first()
    assert pred.points == 1
    db.close()


def test_calculate_all_scores_wrong_prediction():
    """Wrong prediction gets 0 points after calculation."""
    from backend.prediction.service import calculate_all_scores

    user_id = _create_user('wrong@test.com', 'Wrong')
    match_id = create_test_match('Japan', 'Korea', round_name='group_md2')

    _create_prediction(user_id, match_id, outcome='1')  # predicted home win
    _finish_match(match_id, home_goals=0, away_goals=1)  # away win

    calculate_all_scores()

    from backend.models import Prediction, SessionLocal
    db = SessionLocal()
    pred = db.query(Prediction).filter_by(user_id=user_id, match_id=match_id).first()
    assert pred.points == 0
    db.close()


def test_calculate_scores_knockout_round():
    """Knockout round uses same 1X2 scoring: 1pt correct, 0pt wrong."""
    from backend.prediction.service import calculate_all_scores

    user_correct = _create_user('perfect@test.com', 'Perfect')
    user_wrong = _create_user('outcome@test.com', 'Wrong')
    match_id = create_test_match('England', 'France', round_name='quarter_final')

    _create_prediction(user_correct, match_id, outcome='1')  # picks home win
    _create_prediction(user_wrong, match_id, outcome='2')    # picks away win

    _finish_match(match_id, home_goals=2, away_goals=1)
    calculate_all_scores()

    from backend.models import Prediction, SessionLocal
    db = SessionLocal()
    pred_correct = db.query(Prediction).filter_by(user_id=user_correct, match_id=match_id).first()
    pred_wrong = db.query(Prediction).filter_by(user_id=user_wrong, match_id=match_id).first()
    assert pred_correct.points == 1
    assert pred_wrong.points == 0
    db.close()


# ── Leaderboard reflects actual scores ───────────────────────────────────────

def test_leaderboard_shows_correct_totals():
    """Leaderboard should sum points from finished matches."""
    from backend.prediction.service import get_leaderboard, calculate_all_scores

    user_id = _create_user('leader@test.com', 'Leader')
    m1 = create_test_match('USA', 'Mexico', round_name='group_md3')
    m2 = create_test_match('Canada', 'Panama', round_name='group_md3')

    _create_prediction(user_id, m1, outcome='1')
    _create_prediction(user_id, m2, outcome='X')

    _finish_match(m1, home_goals=3, away_goals=0)  # home win → correct
    _finish_match(m2, home_goals=1, away_goals=1)  # draw → correct

    calculate_all_scores()
    lb = get_leaderboard()

    entry = next(e for e in lb if e['user_id'] == user_id)
    assert entry['total_points'] == 2  # 1 + 1


def test_leaderboard_page_recalculates_scores(page):
    """Visiting /leaderboard should trigger score recalculation."""
    user_id = _create_user('autorecalc@test.com', 'AutoRecalc')
    match_id = create_test_match('Belgium', 'Netherlands', round_name='group_md1')

    _create_prediction(user_id, match_id, outcome='2')
    _finish_match(match_id, home_goals=0, away_goals=2)  # away win → correct

    # Don't call calculate_all_scores — the page should do it
    response = page.goto(f'{BASE_URL}/leaderboard')
    assert response.status == 200

    html = page.content()
    assert 'AutoRecalc' in html

    # Verify points were calculated by the page load
    from backend.models import Prediction, SessionLocal
    db = SessionLocal()
    pred = db.query(Prediction).filter_by(user_id=user_id, match_id=match_id).first()
    assert pred.points == 1
    db.close()


def test_leaderboard_ordering(page):
    """Higher-scoring users should appear first on the leaderboard."""
    user_top = _create_user('top@test.com', 'TopPlayer')
    user_low = _create_user('low@test.com', 'LowPlayer')

    m1 = create_test_match('Sweden', 'Norway', round_name='group_md1')
    m2 = create_test_match('Denmark', 'Finland', round_name='group_md1')

    # TopPlayer gets both right
    _create_prediction(user_top, m1, outcome='1')
    _create_prediction(user_top, m2, outcome='2')
    # LowPlayer gets one right, one wrong
    _create_prediction(user_low, m1, outcome='1')
    _create_prediction(user_low, m2, outcome='1')  # wrong

    _finish_match(m1, home_goals=2, away_goals=0)  # home win
    _finish_match(m2, home_goals=0, away_goals=1)  # away win

    response = page.goto(f'{BASE_URL}/leaderboard')
    assert response.status == 200

    html = page.content()
    top_pos = html.index('TopPlayer')
    low_pos = html.index('LowPlayer')
    assert top_pos < low_pos, 'TopPlayer should appear before LowPlayer'


# ── End-to-end: sync + score pipeline (what cron does overnight) ────────────

def test_sync_recalculates_scores_end_to_end():
    """Simulates the morning cron: API returns finished matches → scores must update.

    This is the exact flow that runs overnight via cron_sync.py.
    The bug: sync_matches fetches results but doesn't recalculate scores,
    so the leaderboard stays stale until someone manually triggers it.
    """
    from unittest.mock import patch
    from backend.prediction.service import get_leaderboard
    from backend.models import Prediction, SessionLocal

    user_id = _create_user('cronuser@test.com', 'CronUser')
    match_id = create_test_match('Colombia', 'Uruguay', round_name='group_md1')
    _create_prediction(user_id, match_id, outcome='1')  # predict home win

    # Simulate API returning this match as finished (home win 2-0)
    from backend.models import Match
    db = SessionLocal()
    match = db.query(Match).filter_by(id=match_id).first()
    external_id = match.external_id
    match_date = match.match_date.strftime('%Y-%m-%dT%H:%M:%SZ')
    db.close()

    fake_api_response = {
        'matches': [{
            'id': external_id,
            'stage': 'GROUP_STAGE',
            'matchday': 1,
            'homeTeam': {'name': 'Colombia'},
            'awayTeam': {'name': 'Uruguay'},
            'group': 'GROUP_A',
            'utcDate': match_date,
            'status': 'FINISHED',
            'score': {
                'fullTime': {'home': 2, 'away': 0},
                'regularTime': None,
            },
        }]
    }

    # Run the same sequence as cron_sync.py: sync_matches → calculate_all_scores
    from backend.match_data.service import sync_matches
    from backend.prediction.service import calculate_all_scores

    with patch('backend.match_data.service.FootballAPIClient') as MockClient:
        instance = MockClient.return_value
        instance.get_competition_matches.return_value = fake_api_response
        result = sync_matches()

    assert result['status'] == 'success'

    # This is the critical step that was missing from the admin route
    scores = calculate_all_scores()
    assert scores['status'] == 'success'

    # Verify: prediction has points AND leaderboard reflects them
    db = SessionLocal()
    pred = db.query(Prediction).filter_by(user_id=user_id, match_id=match_id).first()
    assert pred.points == 1, 'Points should be calculated after sync'
    db.close()

    lb = get_leaderboard()
    entry = next(e for e in lb if e['user_id'] == user_id)
    assert entry['total_points'] >= 1


def test_admin_sync_recalculates_scores(page, register_and_login):
    """Admin sync-matches button must also recalculate scores (not just fetch results).

    This was the actual bug: clicking sync in backstage fetched results
    but the leaderboard stayed stale because calculate_all_scores wasn't called.
    """
    from unittest.mock import patch
    from backend.models import Prediction, Match, SessionLocal

    user_id = _create_user('adminsync@test.com', 'AdminSync')
    match_id = create_test_match('Chile', 'Ecuador', round_name='group_md2')
    _create_prediction(user_id, match_id, outcome='2')  # predict away win

    db = SessionLocal()
    match = db.query(Match).filter_by(id=match_id).first()
    external_id = match.external_id
    match_date = match.match_date.strftime('%Y-%m-%dT%H:%M:%SZ')
    db.close()

    fake_api_response = {
        'matches': [{
            'id': external_id,
            'stage': 'GROUP_STAGE',
            'matchday': 2,
            'homeTeam': {'name': 'Chile'},
            'awayTeam': {'name': 'Ecuador'},
            'group': 'GROUP_B',
            'utcDate': match_date,
            'status': 'FINISHED',
            'score': {
                'fullTime': {'home': 0, 'away': 1},
                'regularTime': None,
            },
        }]
    }

    register_and_login('testadmin@test.com', 'Admin User', admin=True)

    with patch('backend.admin.routes.sync_matches') as mock_sync:
        mock_sync.return_value = {
            'status': 'success', 'synced': 0, 'updated': 1, 'skipped': 0, 'total': 1
        }

        # First, apply the API result to DB manually (mock only intercepts the route)
        db = SessionLocal()
        m = db.query(Match).filter_by(id=match_id).first()
        m.finished = True
        m.home_goals = 0
        m.away_goals = 1
        db.commit()
        db.close()

        # Hit the admin sync button
        page.goto(f'{BASE_URL}/backstage/status')
        with page.expect_navigation():
            page.click('form[action*="sync-matches"] button[type=submit]')

    # The sync route should have called calculate_all_scores automatically
    db = SessionLocal()
    pred = db.query(Prediction).filter_by(user_id=user_id, match_id=match_id).first()
    assert pred.points == 1, 'Scores must be recalculated after admin sync'
    db.close()
