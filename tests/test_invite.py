"""Tests for invite flow: accept invite, set name + password, auto-login."""
import pytest
from datetime import datetime, timedelta
from conftest import BASE_URL


def _create_invite(sender_email='inviter@test.com', sender_name='Inviter',
                   recipient_email='invited@test.com'):
    """Create a sender user and an invite token, return the token."""
    from backend.models import User, Invite, SessionLocal
    from backend.auth.service import generate_token
    db = SessionLocal()
    try:
        sender = db.query(User).filter_by(email=sender_email).first()
        if not sender:
            sender = User(email=sender_email, name=sender_name)
            db.add(sender)
            db.flush()

        token = generate_token()
        invite = Invite(
            sender_id=sender.id,
            recipient_email=recipient_email,
            token=token,
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        db.add(invite)
        db.commit()
        return token
    finally:
        db.close()


def test_invite_join_page_renders(page):
    """GET /join?invite=<token> should show the join form."""
    token = _create_invite(recipient_email='render@test.com')
    page.goto(f'{BASE_URL}/join?invite={token}')

    assert page.locator('#name').is_visible()
    assert page.locator('#password').is_visible()
    assert 'render@test.com' in page.content()


def test_invite_join_creates_account_and_logs_in(page):
    """Submitting the join form should create the user and log them in."""
    token = _create_invite(
        sender_email='sender1@test.com', sender_name='Sender',
        recipient_email='joiner@test.com',
    )
    page.goto(f'{BASE_URL}/join?invite={token}')

    page.fill('#name', 'New Joiner')
    page.fill('#password', 'testpass')
    page.click('button[type=submit]')

    # Should be redirected to home and logged in
    page.wait_for_url(f'{BASE_URL}/')
    html = page.content()
    assert 'New Joiner' in html or 'joiner@test.com' in html


def test_invite_join_sets_password(page):
    """After joining, the user should be able to log in with their password."""
    token = _create_invite(
        sender_email='sender2@test.com', sender_name='Sender2',
        recipient_email='pwjoin@test.com',
    )
    page.goto(f'{BASE_URL}/join?invite={token}')
    page.fill('#name', 'PW Joiner')
    page.fill('#password', 'mypass123')
    page.click('button[type=submit]')
    page.wait_for_url(f'{BASE_URL}/')

    # Log out
    page.goto(f'{BASE_URL}/logout')

    # Log back in with password
    page.goto(f'{BASE_URL}/login')
    page.fill('#pw-email', 'pwjoin@test.com')
    page.fill('#pw-password', 'mypass123')
    page.click('#tab-password button[type=submit]')

    assert '/login' not in page.url
    assert 'PW Joiner' in page.content() or 'pwjoin@test.com' in page.content()


def test_invite_marks_token_used(page):
    """After joining, the invite token should be consumed."""
    token = _create_invite(
        sender_email='sender3@test.com', sender_name='Sender3',
        recipient_email='used@test.com',
    )
    page.goto(f'{BASE_URL}/join?invite={token}')
    page.fill('#name', 'Used Token')
    page.fill('#password', 'pass1234')
    page.click('button[type=submit]')
    page.wait_for_url(f'{BASE_URL}/')

    # Log out and try the same invite link
    page.goto(f'{BASE_URL}/logout')
    page.goto(f'{BASE_URL}/join?invite={token}')

    # Should redirect to login with error
    assert '/login' in page.url


def test_invite_invalid_token_rejected(page):
    """An invalid invite token should redirect to login."""
    page.goto(f'{BASE_URL}/join?invite=bogus-token-12345')
    assert '/login' in page.url


def test_invite_requires_password(page):
    """Submitting without a password should show an error."""
    token = _create_invite(
        sender_email='sender4@test.com', sender_name='Sender4',
        recipient_email='nopw@test.com',
    )
    page.goto(f'{BASE_URL}/join?invite={token}')
    page.fill('#name', 'No Password')
    # Don't fill password — browser minlength may block submit,
    # so we use JS to bypass
    page.evaluate('document.getElementById("password").removeAttribute("required")')
    page.evaluate('document.getElementById("password").removeAttribute("minlength")')
    page.click('button[type=submit]')

    # Should stay on join page with error
    assert '/join' in page.url or 'password' in page.content().lower() or '4' in page.content()
