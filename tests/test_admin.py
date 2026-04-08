"""Tests for admin access control, deadline management, and system status."""
import pytest
from conftest import BASE_URL


def test_admin_redirects_anonymous(page):
    page.goto(f'{BASE_URL}/admin/')
    assert '/login' in page.url


def test_admin_denied_for_regular_user(page, register_and_login):
    register_and_login('regular@test.com', 'Regular User', admin=False)
    page.goto(f'{BASE_URL}/admin/')
    # Should redirect away — not show dashboard
    assert 'admin' not in page.title().lower() or '/login' in page.url


def test_admin_accessible_for_admin_user(page, register_and_login):
    register_and_login('admin@test.com', 'Admin User', admin=True)
    response = page.goto(f'{BASE_URL}/admin/')
    assert response.status == 200
    assert 'admin' in page.content().lower()


def test_admin_users_page(page, register_and_login):
    register_and_login('admin2@test.com', 'Admin Two', admin=True)
    response = page.goto(f'{BASE_URL}/admin/users')
    assert response.status == 200
    assert 'admin2@test.com' in page.content()


def test_admin_deadlines_page_renders(page, register_and_login):
    register_and_login('admin3@test.com', 'Admin Three', admin=True)
    response = page.goto(f'{BASE_URL}/admin/deadlines')
    assert response.status == 200
    assert 'deadline' in page.content().lower()


def test_admin_set_deadline(page, register_and_login):
    register_and_login('admin4@test.com', 'Admin Four', admin=True)
    page.goto(f'{BASE_URL}/admin/deadlines')

    # Fill in the quarter_final deadline
    field = page.locator('input[name="quarter_final"]')
    if field.is_visible():
        field.fill('2026-07-01T12:00')
        page.click('button[type=submit]')
        assert 'updated' in page.content().lower()


def test_admin_status_page(page, register_and_login):
    register_and_login('admin5@test.com', 'Admin Five', admin=True)
    response = page.goto(f'{BASE_URL}/admin/status')
    assert response.status == 200
    assert 'sync' in page.content().lower()
