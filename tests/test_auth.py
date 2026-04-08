"""Tests for authentication flows: register, magic link login, logout."""
import pytest
from conftest import BASE_URL, get_magic_link_token


def test_login_page_renders(page):
    page.goto(f'{BASE_URL}/login')
    assert 'Login' in page.title()
    assert page.locator('input[name=email]').is_visible()


def test_register_page_renders(page):
    page.goto(f'{BASE_URL}/register')
    assert page.locator('input[name=name]').is_visible()
    assert page.locator('input[name=email]').is_visible()


def test_register_new_user(page):
    page.goto(f'{BASE_URL}/register')
    page.fill('#name', 'Test User')
    page.fill('#email', 'newuser@test.com')
    page.click('button[type=submit]')

    # Should redirect to login with flash message
    assert page.url == f'{BASE_URL}/login'
    assert 'magic link' in page.content().lower() or 'registration' in page.content().lower()


def test_magic_link_login(page):
    """Register, get token from DB, navigate to verify URL — no email needed."""
    email = 'magiclink@test.com'

    page.goto(f'{BASE_URL}/register')
    page.fill('#name', 'Magic Link User')
    page.fill('#email', email)
    page.click('button[type=submit]')

    token = get_magic_link_token(email)
    assert token, 'Token not created in DB'

    page.goto(f'{BASE_URL}/auth/verify?token={token}')

    # Should be logged in and redirected away from login
    assert page.url != f'{BASE_URL}/login'


def test_invalid_token_rejected(page):
    page.goto(f'{BASE_URL}/auth/verify?token=this-is-not-a-real-token')
    assert page.url == f'{BASE_URL}/login'
    assert 'invalid' in page.content().lower() or 'expired' in page.content().lower()


def test_used_token_rejected(page):
    """A token that has already been used should be rejected."""
    email = 'usedtoken@test.com'

    page.goto(f'{BASE_URL}/register')
    page.fill('#name', 'Used Token User')
    page.fill('#email', email)
    page.click('button[type=submit]')

    token = get_magic_link_token(email)
    page.goto(f'{BASE_URL}/auth/verify?token={token}')  # use it once
    page.goto(f'{BASE_URL}/logout')
    page.goto(f'{BASE_URL}/auth/verify?token={token}')  # try again

    assert page.url == f'{BASE_URL}/login'


def test_logout(page, register_and_login):
    register_and_login('logout@test.com', 'Logout User')

    page.goto(f'{BASE_URL}/logout')
    assert page.url == f'{BASE_URL}/login'

    # Trying to access protected page redirects to login
    page.goto(f'{BASE_URL}/predict')
    assert '/login' in page.url
