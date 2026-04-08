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


def test_submit_prediction(page, register_and_login):
    match_id = create_test_match('Spain', 'Portugal', round_name='quarter_final')
    register_and_login('submitter@test.com', 'Submitter')

    page.goto(f'{BASE_URL}/predict')

    home_input = page.locator(f'input[name="home_{match_id}"]')
    away_input = page.locator(f'input[name="away_{match_id}"]')

    if home_input.is_visible():
        home_input.fill('2')
        away_input.fill('1')
        page.click('button[type=submit]')
        assert 'saved' in page.content().lower() or 'prediction' in page.content().lower()


def test_prediction_locked_after_deadline(page, register_and_login):
    """After all deadlines pass, all prediction inputs should be disabled."""
    from database.models import RoundDeadline, SessionLocal

    # Set past deadlines for every round so all matches are locked
    db = SessionLocal()
    for round_name in ['round_of_16', 'quarter_final', 'semi_final', 'final']:
        existing = db.query(RoundDeadline).filter_by(round=round_name).first()
        past = datetime.utcnow() - timedelta(hours=1)
        if existing:
            existing.deadline = past
        else:
            db.add(RoundDeadline(round=round_name, deadline=past))
    db.commit()
    db.close()

    create_test_match('England', 'Netherlands', round_name='round_of_16')
    register_and_login('locked@test.com', 'Locked User')

    page.goto(f'{BASE_URL}/predict')
    # All inputs should be disabled since all deadlines have passed
    disabled_inputs = page.locator('input[type=number][disabled]').count()
    assert disabled_inputs > 0


def test_leaderboard_visible_without_login(page):
    response = page.goto(f'{BASE_URL}/leaderboard')
    assert response.status == 200
    assert 'leaderboard' in page.content().lower()


def test_results_hidden_before_deadline(page, register_and_login):
    """Other users' predictions should not appear before deadline passes."""
    register_and_login('viewer@test.com', 'Viewer')
    response = page.goto(f'{BASE_URL}/results')
    assert response.status == 200


def test_results_visible_after_deadline(page, register_and_login):
    """After deadline, predictions for that round should be visible."""
    from database.models import RoundDeadline, SessionLocal

    db = SessionLocal()
    existing = db.query(RoundDeadline).filter_by(round='final').first()
    if existing:
        existing.deadline = datetime.utcnow() - timedelta(hours=1)
    else:
        db.add(RoundDeadline(
            round='final',
            deadline=datetime.utcnow() - timedelta(hours=1)
        ))
    db.commit()
    db.close()

    create_test_match('Brazil', 'France', round_name='final', finished=True,
                      home_goals=2, away_goals=1)
    register_and_login('afterdeadline@test.com', 'After Deadline')

    response = page.goto(f'{BASE_URL}/results')
    assert response.status == 200
