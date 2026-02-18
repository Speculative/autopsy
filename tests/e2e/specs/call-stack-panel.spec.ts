import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('Call Stack Panel', () => {
  test.beforeEach(async ({ page }) => {
    const reportPath = path.resolve(__dirname, '../fixtures/history_stream.html');
    await page.goto(`file://${reportPath}`);

    // Start in History view
    await page.locator('.tab', { hasText: 'History' }).click();
  });

  test('should open call stack panel when clicking on a row', async ({ page }) => {
    // Wait for rows to load
    await expect(page.locator('[data-log-index]').first()).toBeVisible({ timeout: 1000 });

    // Find a clickable row (has stack trace)
    const clickableRow = page.locator('[data-log-index].clickable').first();

    if (await clickableRow.count() > 0) {
      await clickableRow.click();

      // Sidebar should appear
      const sidebar = page.locator('.sidebar-body');
      await expect(sidebar).toBeVisible({ timeout: 500 });

      // Should display stack frames
      const stackFrames = page.locator('.stack-frame');
      const frameCount = await stackFrames.count();
      expect(frameCount).toBeGreaterThan(0);
    } else {
      test.skip();
    }
  });

  test('should display stack frame information', async ({ page }) => {
    // Wait for rows to load
    await expect(page.locator('[data-log-index]').first()).toBeVisible({ timeout: 1000 });

    // Click on a row with stack trace
    const clickableRow = page.locator('[data-log-index].clickable').first();

    if (await clickableRow.count() > 0) {
      await clickableRow.click();

      // Wait for sidebar
      await expect(page.locator('.sidebar-body')).toBeVisible({ timeout: 500 });

      // Check that stack frames have content
      const firstFrame = page.locator('.stack-frame').first();
      await expect(firstFrame).not.toBeEmpty();
    } else {
      test.skip();
    }
  });

  test('should close sidebar when close button is clicked', async ({ page }) => {
    // Wait for rows to load
    await expect(page.locator('[data-log-index]').first()).toBeVisible({ timeout: 1000 });

    // Click on a row to open sidebar
    const clickableRow = page.locator('[data-log-index].clickable').first();

    if (await clickableRow.count() > 0) {
      await clickableRow.click();

      // Wait for sidebar to appear
      const sidebar = page.locator('.sidebar-body');
      await expect(sidebar).toBeVisible({ timeout: 500 });

      // Find and click close button (the × button)
      const closeButton = page.locator('.close-button');
      await closeButton.click();

      // Sidebar should disappear
      await expect(sidebar).not.toBeVisible({ timeout: 1000 });
    } else {
      test.skip();
    }
  });
});
