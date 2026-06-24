/**
 * Admin tests
 * - Regular user cannot access /backstage (403 or redirect)
 * - Admin user can access dashboard, users, deadlines, status pages
 * - Stat boxes are visible on the dashboard
 * - Deadlines table shows all rounds
 */
import { test, expect } from '@playwright/test';
import { loginAs } from '../fixtures/login';

test.describe('admin access control', () => {
  test('regular user cannot access /backstage', async ({ page }) => {
    // Already logged in as regular test user via saved state
    await page.goto('/backstage');
    // Should either redirect or show 403
    const status = page.url();
    const bodyText = await page.locator('body').textContent();
    const isBlocked =
      status.includes('/auth/login') ||
      bodyText?.includes('403') ||
      bodyText?.toLowerCase().includes('not authorized') ||
      bodyText?.toLowerCase().includes('admin');
    expect(isBlocked).toBeTruthy();
  });
});

test.describe('admin dashboard (admin user)', () => {
  // These tests log in as admin separately — ignoring saved regular-user state
  test.use({ storageState: { cookies: [], origins: [] } });

  test.beforeEach(async ({ page }) => {
    const email = process.env.ADMIN_EMAIL;
    const password = process.env.ADMIN_PASSWORD;
    if (!email || !password) {
      test.skip();
      return;
    }
    await loginAs(page, email, password);
  });

  test('admin can reach /backstage', async ({ page }) => {
    await page.goto('/backstage');
    await expect(page).not.toHaveURL(/\/auth\/login/);
    await expect(page.locator('body')).not.toContainText('403');
  });

  test('dashboard shows stat boxes', async ({ page }) => {
    await page.goto('/backstage');
    const statBoxes = page.locator('.stat-box');
    await expect(statBoxes).not.toHaveCount(0);
  });

  test('admin nav links are present', async ({ page }) => {
    await page.goto('/backstage');
    await expect(page.locator('.admin-nav')).toBeVisible();
    await expect(page.locator('.admin-nav a', { hasText: /Users|Deadlines|Matches/i }).first()).toBeVisible();
  });

  test('users page lists registered users', async ({ page }) => {
    await page.goto('/backstage/users');
    await expect(page.locator('table')).toBeVisible();
    const rows = page.locator('tbody tr');
    await expect(rows).not.toHaveCount(0);
  });

  test('deadlines page shows all 8 rounds', async ({ page }) => {
    await page.goto('/backstage/deadlines');
    await expect(page.locator('table')).toBeVisible();
    const rows = page.locator('tbody tr');
    // 8 rounds: group_md1-3, round_of_32, round_of_16, quarter, semi, final
    await expect(rows).toHaveCount(8);
  });

  test('status page loads without error', async ({ page }) => {
    await page.goto('/backstage/status');
    await expect(page.locator('body')).not.toContainText('Internal Server Error');
    await expect(page.locator('.stat-row')).toBeVisible();
  });
});
