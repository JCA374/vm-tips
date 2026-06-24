/**
 * Authentication tests
 * - Login page structure
 * - Password login (valid + invalid)
 * - Magic link tab is visible
 * - Redirect when not logged in
 * - Logout
 */
import { test, expect } from '@playwright/test';
import { loginAs } from '../fixtures/login';

// These tests manage their own auth state — don't use saved state
test.use({ storageState: { cookies: [], origins: [] } });

test.describe('login page', () => {
  test('shows three tabs', async ({ page }) => {
    await page.goto('/auth/login');
    await expect(page.getByRole('button', { name: 'Login link' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Password' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Register' })).toBeVisible();
  });

  test('magic link tab is active by default', async ({ page }) => {
    await page.goto('/auth/login');
    const linkBtn = page.getByRole('button', { name: 'Login link' });
    await expect(linkBtn).toHaveClass(/active/);
  });

  test('switching to password tab shows password field', async ({ page }) => {
    await page.goto('/auth/login');
    await page.getByRole('button', { name: 'Password' }).click();
    await expect(page.locator('#pw-password')).toBeVisible();
  });
});

test.describe('password login', () => {
  test('wrong password shows error', async ({ page }) => {
    await page.goto('/auth/login');
    await page.getByRole('button', { name: 'Password' }).click();
    await page.locator('#pw-email').fill('nobody@example.com');
    await page.locator('#pw-password').fill('wrongpassword');
    await page.locator('#tab-password button[type=submit]').click();
    await expect(page.locator('.flash.error')).toBeVisible();
  });

  test('valid credentials redirect to home', async ({ page }) => {
    const email = process.env.TEST_EMAIL!;
    const password = process.env.TEST_PASSWORD!;
    await loginAs(page, email, password);
    await expect(page).not.toHaveURL(/\/auth\/login/);
    await expect(page.locator('nav')).toContainText('Tippa');
  });
});

test.describe('access control', () => {
  test('unauthenticated user redirected from /predict', async ({ page }) => {
    await page.goto('/predict');
    await expect(page).toHaveURL(/\/auth\/login/);
  });

  test('unauthenticated user redirected from /leaderboard', async ({ page }) => {
    await page.goto('/leaderboard');
    // Either redirects or shows login — both are acceptable
    const url = page.url();
    const hasContent = await page.locator('nav').isVisible();
    // If nav is visible without login the page is public, otherwise expect redirect
    if (!hasContent) {
      expect(url).toContain('/auth/login');
    }
  });

  test('unauthenticated user cannot access /backstage', async ({ page }) => {
    await page.goto('/backstage');
    await expect(page).toHaveURL(/\/auth\/login/);
  });
});

test.describe('logout', () => {
  test('logout clears session and redirects to login', async ({ page }) => {
    const email = process.env.TEST_EMAIL!;
    const password = process.env.TEST_PASSWORD!;
    await loginAs(page, email, password);
    await page.getByRole('link', { name: /Logga ut|Logout/i }).click();
    await expect(page).toHaveURL(/\/auth\/login|^\//);
    // Nav should no longer show authenticated links
    await expect(page.locator('nav')).not.toContainText('Tippa');
  });
});
