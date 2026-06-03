"""Tests for admin access control, deadline management, and system status."""
import pytest
from conftest import BASE_URL

# Must match ADMIN_EMAIL in conftest.py env setup
ADMIN_EMAIL = 'testadmin@test.com'


def test_admin_hidden_from_anonymous(page):
    """Admin pages return 404 for anonymous users (not redirect to login)."""
    response = page.goto(f'{BASE_URL}/backstage/')
    assert response.status == 404


def test_admin_hidden_from_regular_user(page, register_and_login):
    register_and_login('regular@test.com', 'Regular User')
    response = page.goto(f'{BASE_URL}/backstage/')
    assert response.status == 404


def test_admin_accessible_for_admin_user(page, register_and_login):
    register_and_login(ADMIN_EMAIL, 'Admin User')
    response = page.goto(f'{BASE_URL}/backstage/')
    assert response.status == 200


def test_admin_users_page(page, register_and_login):
    register_and_login(ADMIN_EMAIL, 'Admin User')
    response = page.goto(f'{BASE_URL}/backstage/users')
    assert response.status == 200


def test_admin_deadlines_page_renders(page, register_and_login):
    register_and_login(ADMIN_EMAIL, 'Admin User')
    response = page.goto(f'{BASE_URL}/backstage/deadlines')
    assert response.status == 200


def test_admin_set_deadline(page, register_and_login):
    register_and_login(ADMIN_EMAIL, 'Admin User')
    page.goto(f'{BASE_URL}/backstage/deadlines')

    field = page.locator('input[name="quarter_final"]')
    if field.is_visible():
        field.fill('2026-07-01T12:00')
        page.click('button[type=submit]')


def test_admin_status_page(page, register_and_login):
    register_and_login(ADMIN_EMAIL, 'Admin User')
    response = page.goto(f'{BASE_URL}/backstage/status')
    assert response.status == 200
