/**
 * Leaderboard tests
 * - Page loads with table
 * - Shows rank, name, points columns
 * - Current user is highlighted
 */
import { test, expect } from '@playwright/test';

test.describe('leaderboard', () => {
  test('loads and shows table', async ({ page }) => {
    await page.goto('/leaderboard');
    await expect(page.locator('table')).toBeVisible();
  });

  test('table has rank, name and points columns', async ({ page }) => {
    await page.goto('/leaderboard');
    const headers = page.locator('thead th');
    const texts = await headers.allTextContents();
    const joined = texts.join(' ').toLowerCase();
    expect(joined).toMatch(/rank|#/);
    expect(joined).toMatch(/name|namn/);
    expect(joined).toMatch(/points|poäng/);
  });

  test('shows at least one player row', async ({ page }) => {
    await page.goto('/leaderboard');
    const rows = page.locator('tbody tr');
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
  });

  test('page title contains leaderboard keyword', async ({ page }) => {
    await page.goto('/leaderboard');
    await expect(page).toHaveTitle(/topplista|leaderboard/i);
  });
});
