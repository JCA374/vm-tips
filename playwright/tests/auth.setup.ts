/**
 * Auth setup — runs once before all other tests.
 * Logs in as the test user and saves browser storage state
 * so all other tests start already authenticated.
 */
import { test as setup, expect } from '@playwright/test';
import { loginAs } from '../fixtures/login';
import * as fs from 'fs';
import * as path from 'path';

const authDir = path.join(__dirname, '..', '.auth');
const userStateFile = path.join(authDir, 'user.json');

setup('authenticate as test user', async ({ page }) => {
  const email = process.env.TEST_EMAIL;
  const password = process.env.TEST_PASSWORD;

  if (!email || !password) {
    throw new Error(
      'TEST_EMAIL and TEST_PASSWORD must be set in playwright/.env\n' +
      'Copy playwright/.env.example to playwright/.env and fill in your credentials.'
    );
  }

  await loginAs(page, email, password);

  // Confirm we're actually logged in
  await expect(page.locator('nav')).toContainText('Tippa');

  // Save auth state for reuse
  if (!fs.existsSync(authDir)) fs.mkdirSync(authDir, { recursive: true });
  await page.context().storageState({ path: userStateFile });
});
