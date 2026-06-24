import { Page } from '@playwright/test';

export async function loginAs(page: Page, email: string, password: string) {
  await page.goto('/auth/login');
  await page.getByRole('button', { name: 'Password' }).click();
  await page.locator('#pw-email').fill(email);
  await page.locator('#pw-password').fill(password);
  await page.locator('#tab-password button[type=submit]').click();
  // Wait for redirect away from login page
  await page.waitForURL(url => !url.pathname.includes('/auth/login'));
}
