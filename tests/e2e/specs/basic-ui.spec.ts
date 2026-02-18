import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('Basic UI Loading', () => {
  test('should load the HTML report and display content', async ({ page }) => {
    const reportPath = path.resolve(__dirname, '../fixtures/basic_logging.html');
    await page.goto(`file://${reportPath}`);

    // Wait for the app to be ready (check for main container)
    await expect(page.locator('main')).toBeVisible({ timeout: 5000 });

    // Verify tabs are present
    await expect(page.locator('.tab', { hasText: 'History' })).toBeVisible();
    await expect(page.locator('.tab', { hasText: 'Streams' })).toBeVisible();
  });

  test('should switch between tabs', async ({ page }) => {
    const reportPath = path.resolve(__dirname, '../fixtures/basic_logging.html');
    await page.goto(`file://${reportPath}`);

    // Click on Streams tab
    await page.locator('.tab', { hasText: 'Streams' }).click();
    await expect(page.locator('.tab', { hasText: 'Streams' })).toHaveClass(/active/);

    // Click on History tab
    await page.locator('.tab', { hasText: 'History' }).click();
    await expect(page.locator('.tab', { hasText: 'History' })).toHaveClass(/active/);
  });

  test('should display log data', async ({ page }) => {
    const reportPath = path.resolve(__dirname, '../fixtures/basic_logging.html');
    await page.goto(`file://${reportPath}`);

    // Switch to History view
    await page.locator('.tab', { hasText: 'History' }).click();

    // Wait for data to load and check that we have log entries
    const logRows = page.locator('[data-log-index]');
    await expect(logRows.first()).toBeVisible({ timeout: 5000 });

    // We should have multiple log entries
    const count = await logRows.count();
    expect(count).toBeGreaterThan(0);
  });
});
