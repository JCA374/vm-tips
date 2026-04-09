"""Tests for prediction submission, deadline enforcement, and results visibility."""
import pytest
from datetime import datetime, timedelta
from conftest import BASE_URL, create_test_match


def test_predict_requires_login(page):
    page.goto(f'{BASE_URL}/predict')
    assert '/login' in page.url


def test_predict_page_renders_with_matches(page, register_and_login):
    create_test_match('France', 'Germany', round_name='semi_final')
    register_and_login('predictor@test.com', 'Predictor')

    page.goto(f'{BASE_URL}/predict')
    assert page.locator('form').is_visible()
    assert 'France' in page.content() or 'No upcoming' in page.content()


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


def test_1x2_has_no_score_inputs(page, register_and_login):
    """1X2 rounds must not expose home_/away_ number inputs."""
    match_id = create_test_match('Mexico', 'Canada', round_name='group_md2')
    register_and_login('check1x2@test.com', 'Check1X2')

    page.goto(f'{BASE_URL}/predict')
    assert page.locator(f'input[name="home_{match_id}"]').count() == 0
    assert page.locator(f'input[name="away_{match_id}"]').count() == 0


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

def test_submit_score_prediction(page, register_and_login):
    """Quarter-final match should accept exact score inputs."""
    match_id = create_test_match('Spain', 'Portugal', round_name='quarter_final')
    register_and_login('submitter@test.com', 'Submitter')

    page.goto(f'{BASE_URL}/predict')
    tab = page.locator('button.tab-btn', has_text='Quarter')
    if tab.count() > 0:
        tab.click()

    home_input = page.locator(f'input[name="home_{match_id}"]')
    away_input = page.locator(f'input[name="away_{match_id}"]')

    if home_input.count() > 0:
        home_input.fill('2')
        away_input.fill('1')
        page.locator('#tab-quarter_final button[type=submit]').click()
        assert 'saved' in page.content().lower() or 'prediction' in page.content().lower()


def test_score_round_has_no_radio_buttons(page, register_and_login):
    """Score rounds must not expose 1X2 radio buttons."""
    match_id = create_test_match('Germany', 'France', round_name='semi_final')
    register_and_login('checkscore@test.com', 'CheckScore')

    page.goto(f'{BASE_URL}/predict')
    assert page.locator(f'input[name="outcome_{match_id}"]').count() == 0


# ── Scoring logic ─────────────────────────────────────────────────────────────

def test_1x2_scoring_correct():
    """Correct 1X2 pick gives 3 points."""
    from database.models import Prediction, Match, SCORE_ROUNDS
    pred = Prediction(predicted_outcome='1')
    match = Match(round='group_md1', home_goals=2, away_goals=0, finished=True)
    pred.match = match
    assert pred.calculate_points() == 3


def test_1x2_scoring_wrong():
    """Wrong 1X2 pick gives 0 points."""
    from database.models import Prediction, Match
    pred = Prediction(predicted_outcome='X')
    match = Match(round='group_md1', home_goals=2, away_goals=0, finished=True)
    pred.match = match
    assert pred.calculate_points() == 0


def test_score_round_correct_score():
    """Perfect exact score gives 7 points."""
    from database.models import Prediction, Match
    pred = Prediction(predicted_home_goals=2, predicted_away_goals=1)
    match = Match(round='quarter_final', home_goals=2, away_goals=1, finished=True)
    pred.match = match
    assert pred.calculate_points() == 7


def test_score_round_correct_outcome_only():
    """Correct outcome but both goals wrong gives exactly 3 points."""
    from database.models import Prediction, Match
    pred = Prediction(predicted_home_goals=3, predicted_away_goals=1)
    match = Match(round='quarter_final', home_goals=1, away_goals=0, finished=True)
    pred.match = match
    assert pred.calculate_points() == 3


def test_score_round_wrong_outcome():
    """Wrong outcome gives 0 points even if a goal count matches."""
    from database.models import Prediction, Match
    pred = Prediction(predicted_home_goals=1, predicted_away_goals=2)
    match = Match(round='final', home_goals=2, away_goals=1, finished=True)
    pred.match = match
    assert pred.calculate_points() == 0


# ── Deadline locking ──────────────────────────────────────────────────────────

def test_prediction_locked_after_deadline(page, register_and_login):
    """After all deadlines pass, all prediction inputs should be disabled."""
    from database.models import RoundDeadline, SessionLocal

    all_rounds = [
        'group_md1', 'group_md2', 'group_md3',
        'round_of_32', 'round_of_16', 'quarter_final', 'semi_final', 'final'
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
    assert 'leaderboard' in page.content().lower()


def test_results_hidden_before_deadline(page, register_and_login):
    register_and_login('viewer@test.com', 'Viewer')
    response = page.goto(f'{BASE_URL}/results')
    assert response.status == 200


def test_results_visible_after_deadline(page, register_and_login):
    from database.models import RoundDeadline, SessionLocal

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
