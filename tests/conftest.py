"""
Pytest + Playwright test configuration for VM Tips.

Magic link flow: rather than reading emails, tests register a user via the UI,
then fetch the token directly from the database and navigate to the verify URL.
"""
import os
import sys
import tempfile
import threading

# Set env vars BEFORE any project modules are imported.
# SQLAlchemy creates the engine at import time using these values.
_db_fd, _db_path = tempfile.mkstemp(suffix='.db')
os.close(_db_fd)

os.environ.update({
    'SECRET_KEY': 'test-secret-key-for-pytest-do-not-use-in-prod',
    'DATABASE_PATH': _db_path,
    'APP_URL': 'http://localhost:5001',
    'MAIL_SERVER': 'localhost',
    'MAIL_PORT': '25',
    'MAIL_USERNAME': '',
    'MAIL_PASSWORD': '',
    'MAIL_DEFAULT_SENDER': 'test@vmtips.test',
    'FOOTBALL_API_KEY': 'dummy-test-key',
})

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import importlib.util
import pytest
from werkzeug.serving import make_server

BASE_URL = 'http://localhost:5001'

# Load app.py directly (avoid collision with the app/ package directory)
_project_root = os.path.dirname(os.path.dirname(__file__))
_spec = importlib.util.spec_from_file_location('flask_app_module', os.path.join(_project_root, 'app.py'))
_flask_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_flask_module)
_flask_app = _flask_module.app  # the Flask instance


@pytest.fixture(scope='session', autouse=True)
def flask_server():
    """Start Flask app once for the entire test session."""
    from database.models import init_db

    # Suppress actual email sending
    _flask_app.config['TESTING'] = True
    _flask_app.config['MAIL_SUPPRESS_SEND'] = True

    init_db()

    server = make_server('localhost', 5001, _flask_app)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    yield BASE_URL

    server.shutdown()
    os.unlink(_db_path)


@pytest.fixture(scope='session')
def base_url():
    return BASE_URL


def get_magic_link_token(email):
    """Fetch the most recent unused magic link token for a user from the DB."""
    from database.models import MagicLink, User, SessionLocal
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email=email).first()
        if not user:
            return None
        link = (
            db.query(MagicLink)
            .filter_by(user_id=user.id, used=False)
            .order_by(MagicLink.created_at.desc())
            .first()
        )
        return link.token if link else None
    finally:
        db.close()


def set_admin(email):
    """Promote a user to admin directly in the DB."""
    from database.models import User, SessionLocal
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email=email).first()
        if user:
            user.is_admin = True
            db.commit()
    finally:
        db.close()


def create_test_match(home_team='Brazil', away_team='Argentina',
                      round_name='quarter_final', finished=False,
                      home_goals=None, away_goals=None):
    """Insert a match directly into the DB for testing."""
    from database.models import Match, SessionLocal
    from datetime import datetime, timedelta
    import random
    db = SessionLocal()
    try:
        match = Match(
            external_id=random.randint(100000, 999999),
            round=round_name,
            home_team=home_team,
            away_team=away_team,
            match_date=datetime.utcnow() + timedelta(days=1),
            finished=finished,
            home_goals=home_goals,
            away_goals=away_goals,
        )
        db.add(match)
        db.commit()
        db.refresh(match)
        return match.id
    finally:
        db.close()


@pytest.fixture
def register_and_login(page):
    """
    Factory fixture: register a user and log them in by bypassing email.
    Usage: user_page = register_and_login('test@example.com', 'Test User')
    """
    def _login(email, name, admin=False):
        page.goto(f'{BASE_URL}/register')
        page.fill('#name', name)
        page.fill('#email', email)
        page.click('button[type=submit]')

        if admin:
            set_admin(email)

        token = get_magic_link_token(email)
        assert token, f'No magic link token found for {email}'
        page.goto(f'{BASE_URL}/auth/verify?token={token}')
        return page

    return _login
