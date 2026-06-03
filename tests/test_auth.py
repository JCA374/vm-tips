"""Tests for authentication flows: register, magic link login, logout."""
import pytest
from conftest import BASE_URL, get_magic_link_token


def test_login_page_renders(page):
    page.goto(f'{BASE_URL}/login')
    assert 'Login' in page.title() or 'login' in page.title().lower()
    assert page.locator('#pw-email').is_visible()


def test_register_tab_renders(page):
    page.goto(f'{BASE_URL}/login')
    page.click('button.tab-btn[data-tab="register"]')
    assert page.locator('#reg-name').is_visible()
    assert page.locator('#reg-email').is_visible()


def test_register_new_user(page):
    page.goto(f'{BASE_URL}/login')
    page.click('button.tab-btn[data-tab="register"]')
    page.fill('#reg-name', 'Test User')
    page.fill('#reg-email', 'newuser@test.com')
    page.click('#tab-register button[type=submit]')

    # Should show "sent" confirmation
    assert 'sent' in page.content().lower() or 'magic' in page.content().lower() or 'link' in page.content().lower()


def test_magic_link_login(page):
    """Register, get token from DB, navigate to verify URL — no email needed."""
    email = 'magiclink@test.com'

    page.goto(f'{BASE_URL}/login')
    page.click('button.tab-btn[data-tab="register"]')
    page.fill('#reg-name', 'Magic Link User')
    page.fill('#reg-email', email)
    page.click('#tab-register button[type=submit]')

    token = get_magic_link_token(email)
    assert token, 'Token not created in DB'

    # GET shows confirm page, POST consumes the token
    page.goto(f'{BASE_URL}/auth/verify?token={token}')
    page.click('button[type=submit]')

    # Should be logged in and redirected away from login
    assert '/login' not in page.url


def test_invalid_token_rejected(page):
    page.goto(f'{BASE_URL}/auth/verify?token=this-is-not-a-real-token')
    assert '/login' in page.url
    assert 'invalid' in page.content().lower() or 'expired' in page.content().lower()


def test_used_token_rejected(page):
    """A token that has already been used should be rejected."""
    email = 'usedtoken@test.com'

    page.goto(f'{BASE_URL}/login')
    page.click('button.tab-btn[data-tab="register"]')
    page.fill('#reg-name', 'Used Token User')
    page.fill('#reg-email', email)
    page.click('#tab-register button[type=submit]')

    token = get_magic_link_token(email)
    # Consume the token
    page.goto(f'{BASE_URL}/auth/verify?token={token}')
    page.click('button[type=submit]')
    # Log out and try the same token again
    page.goto(f'{BASE_URL}/logout')
    page.goto(f'{BASE_URL}/auth/verify?token={token}')

    assert '/login' in page.url


def test_logout(page, register_and_login):
    register_and_login('logout@test.com', 'Logout User')

    page.goto(f'{BASE_URL}/logout')
    assert '/login' in page.url

    # Trying to access protected page redirects to login
    page.goto(f'{BASE_URL}/predict')
    assert '/login' in page.url
