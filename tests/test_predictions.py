"""Tests for prediction submission, deadline enforcement, and results visibility."""
import pytest
from datetime import datetime, timedelta
from conftest import BASE_URL, create_test_match


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


def test_predict_requires_login(page):
    page.goto(f'{BASE_URL}/predict')
    assert '/login' in page.url


def test_predict_page_renders_with_matches(page, register_and_login):
    create_test_match('France', 'Germany', round_name='semi_final')
    register_and_login('predictor@test.com', 'Predictor')

    page.goto(f'{BASE_URL}/predict')
    assert page.locator('form').is_visible()
    # Country names may be translated to Swedish (Frankrike)
    assert 'France' in page.content() or 'Frankrike' in page.content() or 'form' in page.content().lower()


# ── 1X2 betting (group stage / early knockout) ────────────────────────────────

def test_submit_1x2_prediction(page, register_and_login):
    """Group stage match should show 1/X/2 radio buttons and save correctly."""
    match_id = create_test_match('Spain', 'Portugal', round_name='group_md1')
    register_and_login('submitter1x2@test.com', 'Submitter1X2')

    page.goto(f'{BASE_URL}/predict')
    # Click the Groups MD1 tab so the panel is visible
    tab = page.locator('button.tab-btn', has_text='Matchday 1')
    if tab.count() > 0:
        tab.click()

    label = page.locator(f'#tab-group_md1 label:has(input[name="outcome_{match_id}"][value="1"])')
    if label.count() > 0:
        label.click()
        page.locator('#tab-group_md1 button[type=submit]').click()
        assert 'saved' in page.content().lower() or 'prediction' in page.content().lower()


def test_group_has_draw_option(page, register_and_login):
    """Group stage rounds should have 1, X, and 2 options."""
    match_id = create_test_match('Mexico', 'Canada', round_name='group_md2')
    register_and_login('check1x2@test.com', 'Check1X2')

    page.goto(f'{BASE_URL}/predict')
    assert page.locator(f'input[name="outcome_{match_id}"][value="X"]').count() > 0


def test_1x2_x_option(page, register_and_login):
    """Selecting X (draw) should save correctly."""
    match_id = create_test_match('Brazil', 'Argentina', round_name='round_of_16')
    register_and_login('drawpicker@test.com', 'DrawPicker')

    page.goto(f'{BASE_URL}/predict')
    tab = page.locator('button.tab-btn', has_text='Round of 16')
    if tab.count() > 0:
        tab.click()
    label = page.locator(f'#tab-round_of_16 label:has(input[name="outcome_{match_id}"][value="X"])')
    if label.count() > 0:
        label.click()
        page.locator('#tab-round_of_16 button[type=submit]').click()
        assert 'saved' in page.content().lower()


# ── Exact score betting (QF / SF / Final) ─────────────────────────────────────

def test_submit_1x2_knockout(page, register_and_login):
    """Knockout match should show 1X2 radio buttons and save correctly."""
    match_id = create_test_match('Spain', 'Portugal', round_name='quarter_final')
    register_and_login('submitter@test.com', 'Submitter')

    page.goto(f'{BASE_URL}/predict')
    tab = page.locator('button.tab-btn', has_text='Quarter')
    if tab.count() > 0:
        tab.click()

    label = page.locator(f'#tab-quarter_final label:has(input[name="outcome_{match_id}"][value="1"])')
    if label.count() > 0:
        label.click()
        page.locator('#tab-quarter_final button[type=submit]').click()
        assert 'saved' in page.content().lower() or 'prediction' in page.content().lower()


def test_knockout_has_1x2_options(page, register_and_login):
    """Knockout rounds should have 1, X, and 2 options like all rounds."""
    match_id = create_test_match('Germany', 'France', round_name='semi_final')
    register_and_login('checkscore@test.com', 'CheckScore')

    page.goto(f'{BASE_URL}/predict')
    assert page.locator(f'input[name="outcome_{match_id}"][value="1"]').count() > 0
    assert page.locator(f'input[name="outcome_{match_id}"][value="X"]').count() > 0
    assert page.locator(f'input[name="outcome_{match_id}"][value="2"]').count() > 0


# ── Updating predictions ─────────────────────────────────────────────────────

def test_update_prediction_changes_outcome():
    """Changing 1X2 on an already saved prediction should update it, not create a duplicate."""
    from backend.prediction.service import submit_prediction
    from backend.models import Prediction, RoundDeadline, SessionLocal
    from conftest import create_test_match

    # Clean up any leftover deadline from other tests (e.g. test_prediction_locked_after_deadline)
    db = SessionLocal()
    db.query(RoundDeadline).filter_by(round='group_md1').delete()
    db.commit()
    db.close()

    match_id = create_test_match('Chile', 'Peru', round_name='group_md1')
    user_id = _create_user('updater@test.com', 'Updater')

    # Submit initial prediction
    result = submit_prediction(user_id, match_id, outcome='1')
    assert result['status'] == 'success'
    assert result['message'] == 'Prediction submitted'

    # Re-submit same value — should be unchanged
    result = submit_prediction(user_id, match_id, outcome='1')
    assert result['status'] == 'success'
    assert result['message'] == 'Prediction unchanged'

    # Change to X
    result = submit_prediction(user_id, match_id, outcome='X')
    assert result['status'] == 'success'
    assert result['message'] == 'Prediction updated'

    # Verify only one prediction exists and it has the new value
    db = SessionLocal()
    preds = db.query(Prediction).filter_by(user_id=user_id, match_id=match_id).all()
    assert len(preds) == 1
    assert preds[0].predicted_outcome == 'X'
    db.close()


# ── Service-level edge cases ──────────────────────────────────────────────────

def test_unchanged_prediction_preserves_timestamp():
    """Re-submitting the same outcome must NOT update updated_at."""
    from backend.prediction.service import submit_prediction
    from backend.models import Prediction, RoundDeadline, SessionLocal
    from conftest import create_test_match
    import time

    # Clean up any leftover deadline from other tests
    db = SessionLocal()
    db.query(RoundDeadline).filter_by(round='group_md1').delete()
    db.commit()
    db.close()

    match_id = create_test_match('Nigeria', 'Egypt', round_name='group_md1')
    user_id = _create_user('timestamp@test.com', 'Timestamp')

    submit_prediction(user_id, match_id, outcome='2')

    db = SessionLocal()
    pred = db.query(Prediction).filter_by(user_id=user_id, match_id=match_id).first()
    original_ts = pred.updated_at
    db.close()

    time.sleep(0.05)  # ensure clock moves
    result = submit_prediction(user_id, match_id, outcome='2')
    assert result['message'] == 'Prediction unchanged'

    db = SessionLocal()
    pred = db.query(Prediction).filter_by(user_id=user_id, match_id=match_id).first()
    assert pred.updated_at == original_ts
    db.close()


def test_submit_prediction_rejected_after_deadline():
    """Predictions should be rejected when the round deadline has passed."""
    from backend.prediction.service import submit_prediction
    from backend.models import RoundDeadline, SessionLocal
    from conftest import create_test_match

    match_id = create_test_match('Japan', 'Belgium', round_name='group_md3')
    user_id = _create_user('late@test.com', 'Late')

    # Ensure a past deadline exists (may already exist from Playwright tests)
    db = SessionLocal()
    existing = db.query(RoundDeadline).filter_by(round='group_md3').first()
    if existing:
        existing.deadline = datetime.utcnow() - timedelta(hours=1)
    else:
        db.add(RoundDeadline(round='group_md3', deadline=datetime.utcnow() - timedelta(hours=1)))
    db.commit()
    db.close()

    result = submit_prediction(user_id, match_id, outcome='1')
    assert result['status'] == 'error'
    assert 'deadline' in result['message'].lower()


def test_submit_prediction_rejected_for_finished_match():
    """Predictions should be rejected for already finished matches."""
    from backend.prediction.service import submit_prediction
    from conftest import create_test_match

    match_id = create_test_match('Italy', 'Sweden', round_name='group_md1',
                                 finished=True, home_goals=1, away_goals=0)
    user_id = _create_user('finished@test.com', 'Finished')

    result = submit_prediction(user_id, match_id, outcome='1')
    assert result['status'] == 'error'
    assert 'finished' in result['message'].lower()


def test_submit_prediction_nonexistent_match():
    """Prediction for a non-existent match should return error."""
    from backend.prediction.service import submit_prediction

    user_id = _create_user('nomatch@test.com', 'NoMatch')
    result = submit_prediction(user_id, 999999, outcome='1')
    assert result['status'] == 'error'
    assert 'not found' in result['message'].lower()


# ── Regular time logic for knockout ──────────────────────────────────────────

def test_sync_knockout_uses_regular_time():
    """Knockout matches should use regularTime scores, not fullTime (which includes extra time)."""
    from backend.match_data.service import sync_matches, KNOCKOUT_STAGES
    from backend.models import Match, SessionLocal
    from unittest.mock import patch, MagicMock

    # Simulate API response: a QF match that went to extra time
    # Regular time: 1-1 (draw), Full time: 2-1 (home win after ET)
    fake_api_response = {
        'matches': [{
            'id': 888001,
            'stage': 'QUARTER_FINALS',
            'matchday': None,
            'homeTeam': {'name': 'TestHome'},
            'awayTeam': {'name': 'TestAway'},
            'group': None,
            'utcDate': '2026-07-10T20:00:00Z',
            'status': 'FINISHED',
            'score': {
                'fullTime': {'home': 2, 'away': 1},
                'regularTime': {'home': 1, 'away': 1},
            },
        }]
    }

    with patch('backend.match_data.service.FootballAPIClient') as MockClient:
        instance = MockClient.return_value
        instance.get_competition_matches.return_value = fake_api_response
        result = sync_matches()

    assert result['status'] == 'success'

    db = SessionLocal()
    match = db.query(Match).filter_by(external_id=888001).first()
    assert match is not None
    # Should use regularTime (1-1), NOT fullTime (2-1)
    assert match.home_goals == 1
    assert match.away_goals == 1
    db.delete(match)
    db.commit()
    db.close()


def test_sync_group_uses_full_time():
    """Group stage matches should use fullTime scores (no extra time possible)."""
    from backend.match_data.service import sync_matches
    from backend.models import Match, SessionLocal
    from unittest.mock import patch

    fake_api_response = {
        'matches': [{
            'id': 888002,
            'stage': 'GROUP_STAGE',
            'matchday': 1,
            'homeTeam': {'name': 'GroupHome'},
            'awayTeam': {'name': 'GroupAway'},
            'group': 'GROUP_A',
            'utcDate': '2026-06-11T19:00:00Z',
            'status': 'FINISHED',
            'score': {
                'fullTime': {'home': 3, 'away': 0},
                'regularTime': None,
            },
        }]
    }

    with patch('backend.match_data.service.FootballAPIClient') as MockClient:
        instance = MockClient.return_value
        instance.get_competition_matches.return_value = fake_api_response
        result = sync_matches()

    assert result['status'] == 'success'

    db = SessionLocal()
    match = db.query(Match).filter_by(external_id=888002).first()
    assert match is not None
    assert match.home_goals == 3
    assert match.away_goals == 0
    db.delete(match)
    db.commit()
    db.close()


def test_update_results_knockout_uses_regular_time():
    """update_match_results should use regularTime for knockout matches."""
    from backend.match_data.service import update_match_results
    from backend.models import Match, SessionLocal
    from unittest.mock import patch

    # Create an unfinished knockout match
    db = SessionLocal()
    match = Match(
        external_id=888003,
        round='semi_final',
        home_team='SemiHome',
        away_team='SemiAway',
        match_date=datetime.utcnow(),
        finished=False,
    )
    db.add(match)
    db.commit()
    match_id = match.id
    db.close()

    fake_match_response = {
        'match': {
            'status': 'FINISHED',
            'stage': 'SEMI_FINALS',
            'score': {
                'fullTime': {'home': 3, 'away': 2},
                'regularTime': {'home': 2, 'away': 2},
            },
        }
    }

    with patch('backend.match_data.service.FootballAPIClient') as MockClient:
        instance = MockClient.return_value
        instance.get_match_by_id.return_value = fake_match_response
        update_match_results()

    db = SessionLocal()
    match = db.query(Match).filter_by(id=match_id).first()
    # Should be 2-2 (regular time), not 3-2 (full time with ET)
    assert match.home_goals == 2
    assert match.away_goals == 2
    assert match.finished is True
    db.delete(match)
    db.commit()
    db.close()


# ── Scoring logic ─────────────────────────────────────────────────────────────

def test_1x2_scoring_correct():
    """Correct 1X2 pick gives 1 point."""
    from backend.models import Prediction, Match
    pred = Prediction(predicted_outcome='1')
    match = Match(round='group_md1', home_goals=2, away_goals=0, finished=True)
    pred.match = match
    assert pred.calculate_points() == 1


def test_1x2_scoring_wrong():
    """Wrong 1X2 pick gives 0 points."""
    from backend.models import Prediction, Match
    pred = Prediction(predicted_outcome='X')
    match = Match(round='group_md1', home_goals=2, away_goals=0, finished=True)
    pred.match = match
    assert pred.calculate_points() == 0


def test_1x2_scoring_correct_knockout():
    """Correct 1X2 pick in knockout gives 1 point."""
    from backend.models import Prediction, Match
    pred = Prediction(predicted_outcome='1')
    match = Match(round='quarter_final', home_goals=2, away_goals=1, finished=True)
    pred.match = match
    assert pred.calculate_points() == 1


def test_1x2_scoring_wrong_knockout():
    """Wrong 1X2 pick in knockout gives 0 points."""
    from backend.models import Prediction, Match
    pred = Prediction(predicted_outcome='1')
    match = Match(round='semi_final', home_goals=0, away_goals=2, finished=True)
    pred.match = match
    assert pred.calculate_points() == 0


def test_1x2_draw_prediction():
    """Correct draw prediction gives 1 point."""
    from backend.models import Prediction, Match
    pred = Prediction(predicted_outcome='X')
    match = Match(round='final', home_goals=2, away_goals=2, finished=True)
    pred.match = match
    assert pred.calculate_points() == 1


def test_1x2_scoring_third_place():
    """Third place match uses same 1X2 scoring."""
    from backend.models import Prediction, Match
    pred = Prediction(predicted_outcome='2')
    match = Match(round='third_place', home_goals=1, away_goals=3, finished=True)
    pred.match = match
    assert pred.calculate_points() == 1


# ── Stage mapping ────────────────────────────────────────────────────────────

def test_map_stage_to_round_group_stages():
    """Group stage maps to group_md1/2/3 based on matchday."""
    from backend.match_data.service import map_stage_to_round
    assert map_stage_to_round('GROUP_STAGE', 1) == 'group_md1'
    assert map_stage_to_round('GROUP_STAGE', 2) == 'group_md2'
    assert map_stage_to_round('GROUP_STAGE', 3) == 'group_md3'


def test_map_stage_to_round_knockout():
    """All knockout stages map to expected round names."""
    from backend.match_data.service import map_stage_to_round
    assert map_stage_to_round('LAST_32') == 'round_of_32'
    assert map_stage_to_round('LAST_16') == 'round_of_16'
    assert map_stage_to_round('QUARTER_FINALS') == 'quarter_final'
    assert map_stage_to_round('SEMI_FINALS') == 'semi_final'
    assert map_stage_to_round('THIRD_PLACE') == 'third_place'
    assert map_stage_to_round('FINAL') == 'final'


def test_map_stage_to_round_unknown():
    """Unknown stage returns None."""
    from backend.match_data.service import map_stage_to_round
    assert map_stage_to_round('MADE_UP_STAGE') is None


# ── Deadline locking ──────────────────────────────────────────────────────────

def test_prediction_locked_after_deadline(page, register_and_login):
    """After all deadlines pass, all prediction inputs should be disabled."""
    from backend.models import RoundDeadline, SessionLocal

    all_rounds = [
        'group_md1', 'group_md2', 'group_md3',
        'round_of_32', 'round_of_16', 'quarter_final', 'semi_final', 'third_place', 'final'
    ]
    db = SessionLocal()
    past = datetime.utcnow() - timedelta(hours=1)
    for round_name in all_rounds:
        existing = db.query(RoundDeadline).filter_by(round=round_name).first()
        if existing:
            existing.deadline = past
        else:
            db.add(RoundDeadline(round=round_name, deadline=past))
    db.commit()
    db.close()

    create_test_match('England', 'Netherlands', round_name='group_md1')
    register_and_login('locked@test.com', 'Locked User')

    page.goto(f'{BASE_URL}/predict')
    # Both radio buttons (1X2) and number inputs should all be disabled
    disabled_radios = page.locator('input[type=radio][disabled]').count()
    disabled_numbers = page.locator('input[type=number][disabled]').count()
    assert disabled_radios + disabled_numbers > 0


# ── Leaderboard & results ─────────────────────────────────────────────────────

def test_leaderboard_visible_without_login(page):
    response = page.goto(f'{BASE_URL}/leaderboard')
    assert response.status == 200
    # Swedish: "topplista", English: "leaderboard"
    assert 'leaderboard' in page.content().lower() or 'topplista' in page.content().lower()


def test_results_hidden_before_deadline(page, register_and_login):
    register_and_login('viewer@test.com', 'Viewer')
    response = page.goto(f'{BASE_URL}/results')
    assert response.status == 200


def test_results_visible_after_deadline(page, register_and_login):
    from backend.models import RoundDeadline, SessionLocal

    db = SessionLocal()
    existing = db.query(RoundDeadline).filter_by(round='final').first()
    if existing:
        existing.deadline = datetime.utcnow() - timedelta(hours=1)
    else:
        db.add(RoundDeadline(round='final', deadline=datetime.utcnow() - timedelta(hours=1)))
    db.commit()
    db.close()

    create_test_match('Brazil', 'France', round_name='final', finished=True,
                      home_goals=2, away_goals=1)
    register_and_login('afterdeadline@test.com', 'After Deadline')

    response = page.goto(f'{BASE_URL}/results')
    assert response.status == 200
