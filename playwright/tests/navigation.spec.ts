/**
 * Navigation and layout tests
 * - Header and nav are present on all main pages
 * - Ocean theme colours applied (dark header)
 * - Nav links work
 * - Flash messages render correctly
 */
import { test, expect } from '@playwright/test';

const MAIN_PAGES = ['/', '/predict', '/leaderboard', '/results'];

for (const path of MAIN_PAGES) {
  test(`${path} — header and nav are visible`, async ({ page }) => {
    await page.goto(path);
    await expect(page.locator('header')).toBeVisible();
    await expect(page.locator('nav')).toBeVisible();
  });
}

test.describe('header', () => {
  test('shows football emoji logo', async ({ page }) => {
    await page.goto('/');
    const logo = page.locator('header .logo');
    await expect(logo).toContainText('⚽');
  });

  test('shows app name', async ({ page }) => {
    await page.goto('/');
    const h1 = page.locator('header h1');
    await expect(h1).toBeVisible();
    const text = await h1.textContent();
    expect(text!.trim().length).toBeGreaterThan(0);
  });

  test('header has dark background (ocean theme)', async ({ page }) => {
    await page.goto('/');
    const header = page.locator('header');
    const bg = await header.evaluate(el =>
      window.getComputedStyle(el).backgroundColor
    );
    // #0A1C2E = rgb(10, 28, 46) — dark navy
    expect(bg).toBe('rgb(10, 28, 46)');
  });
});

test.describe('nav links', () => {
  test('home link navigates to /', async ({ page }) => {
    await page.goto('/leaderboard');
    await page.locator('nav a', { hasText: /Hem|Home/i }).click();
    await expect(page).toHaveURL('/');
  });

  test('leaderboard link works', async ({ page }) => {
    await page.goto('/');
    await page.locator('nav a', { hasText: /Topplista|Leaderboard/i }).click();
    await expect(page).toHaveURL('/leaderboard');
  });

  test('predict link works', async ({ page }) => {
    await page.goto('/');
    await page.locator('nav a', { hasText: /Tippa|Predict/i }).click();
    await expect(page).toHaveURL('/predict');
  });
});
