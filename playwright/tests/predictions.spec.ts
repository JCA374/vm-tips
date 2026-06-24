/**
 * Prediction tests (runs with saved auth state)
 * - Page loads and shows round tabs
 * - Score inputs are present for open rounds
 * - Saving predictions shows success flash
 * - Saving partial round warns about missing matches (≤3 named, >3 count only)
 * - Locked rounds show locked state
 */
import { test, expect } from '@playwright/test';

test.describe('predict page structure', () => {
  test('loads and shows round tabs', async ({ page }) => {
    await page.goto('/predict');
    await expect(page.locator('.tabs')).toBeVisible();
    // At least one tab should exist
    const tabs = page.locator('.tab-btn');
    await expect(tabs).not.toHaveCount(0);
  });

  test('shows score inputs for open rounds', async ({ page }) => {
    await page.goto('/predict');
    // Find the first unlocked tab panel
    const activePanel = page.locator('.tab-panel.active');
    await expect(activePanel).toBeVisible();
    // Score inputs or 1X2 buttons should be present
    const hasScoreInputs = await activePanel.locator('.score-input').count() > 0;
    const hasOutcomeInputs = await activePanel.locator('.ox2-group').count() > 0;
    expect(hasScoreInputs || hasOutcomeInputs).toBeTruthy();
  });

  test('locked rounds show locked badge', async ({ page }) => {
    await page.goto('/predict');
    const lockedBadges = page.locator('.deadline-badge.locked');
    // May be 0 if no deadlines have passed — that is fine
    const count = await lockedBadges.count();
    if (count > 0) {
      await expect(lockedBadges.first()).toBeVisible();
    }
  });
});

test.describe('saving predictions', () => {
  test('save with no changes shows success flash', async ({ page }) => {
    await page.goto('/predict');
    // Submit the form for the active tab without changing anything
    await page.locator('.tab-panel.active button[type=submit]').click();
    await expect(page.locator('.flash')).toBeVisible();
  });

  test('partial save on open round warns about missing matches', async ({ page }) => {
    await page.goto('/predict');

    // Clear all score inputs in the active panel, then save
    const activePanel = page.locator('.tab-panel.active');
    const inputs = activePanel.locator('.score-input');
    const inputCount = await inputs.count();

    if (inputCount > 0) {
      // Clear first input only so there are definitely missing predictions
      await inputs.first().fill('');
      await activePanel.locator('button[type=submit]').click();

      // Should see a warning flash
      const warnings = page.locator('.flash.warning');
      await expect(warnings).not.toHaveCount(0);
    } else {
      test.skip(); // No score inputs on this round
    }
  });

  test('warning names matches when 3 or fewer are missing', async ({ page }) => {
    await page.goto('/predict');
    const activePanel = page.locator('.tab-panel.active');
    const inputs = activePanel.locator('.score-input');
    const inputCount = await inputs.count();

    // Only run if the round has 3 or fewer score inputs
    if (inputCount > 0 && inputCount <= 6) { // 6 = 3 matches × 2 inputs
      for (let i = 0; i < inputCount; i++) {
        await inputs.nth(i).fill('');
      }
      await activePanel.locator('button[type=submit]').click();

      const warning = page.locator('.flash.warning').first();
      await expect(warning).toBeVisible();
      // Warning should contain "vs" (team name format), not just a number
      const text = await warning.textContent();
      expect(text).toContain('vs');
    }
  });

  test('warning shows count when more than 3 matches missing', async ({ page }) => {
    await page.goto('/predict');
    const activePanel = page.locator('.tab-panel.active');
    const inputs = activePanel.locator('.score-input');
    const inputCount = await inputs.count();

    // Only run if round has more than 3 matches (>6 score inputs)
    if (inputCount > 6) {
      for (let i = 0; i < inputCount; i++) {
        await inputs.nth(i).fill('');
      }
      await activePanel.locator('button[type=submit]').click();

      const warning = page.locator('.flash.warning').first();
      await expect(warning).toBeVisible();
      // Warning should contain a number and "matches", not a list of names
      const text = await warning.textContent();
      expect(text).toMatch(/\d+ matches/);
    }
  });
});
