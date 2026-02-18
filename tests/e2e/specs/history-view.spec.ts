import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('History View', () => {
  test.beforeEach(async ({ page }) => {
    const reportPath = path.resolve(__dirname, '../fixtures/history_stream.html');
    await page.goto(`file://${reportPath}`);

    // Switch to History view
    await page.locator('.tab', { hasText: 'History' }).click();
    await expect(page.locator('.tab', { hasText: 'History' })).toHaveClass(/active/);
  });

  test('should render rows within 1 second', async ({ page }) => {
    // Wait for at least one row to appear within 1 second
    const firstRow = page.locator('[data-log-index]').first();
    await expect(firstRow).toBeVisible({ timeout: 1000 });

    // Verify we have multiple rows
    const rows = page.locator('[data-log-index]');
    const count = await rows.count();
    expect(count).toBeGreaterThan(10);
  });

  test('should display log data in table format', async ({ page }) => {
    // Wait for rows to appear
    await expect(page.locator('[data-log-index]').first()).toBeVisible({ timeout: 1000 });

    // Check for table structure
    const rows = page.locator('[data-log-index]');
    const firstRow = rows.first();

    // Row should have content
    await expect(firstRow).not.toBeEmpty();
  });

  test('should navigate to specific log when clicked', async ({ page }) => {
    // Wait for rows to appear
    await expect(page.locator('[data-log-index]').first()).toBeVisible({ timeout: 1000 });

    // Find a clickable row (one with a stack trace)
    const clickableRow = page.locator('[data-log-index].clickable').first();

    // If there's a clickable row, click it
    if (await clickableRow.count() > 0) {
      await clickableRow.click();

      // The row should be selected
      await expect(clickableRow).toHaveClass(/selected/);
    }
  });
});
