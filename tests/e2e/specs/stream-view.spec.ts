import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('Stream View', () => {
  test.beforeEach(async ({ page }) => {
    const reportPath = path.resolve(__dirname, '../fixtures/history_stream.html');
    await page.goto(`file://${reportPath}`);

    // Switch to Streams view
    await page.locator('.tab', { hasText: 'Streams' }).click();
    await expect(page.locator('.tab', { hasText: 'Streams' })).toHaveClass(/active/);
  });

  test('should render rows within 1 second', async ({ page }) => {
    // Wait for at least one row to appear within 1 second
    const firstRow = page.locator('.table-row').first();
    await expect(firstRow).toBeVisible({ timeout: 1000 });

    // Verify we have multiple rows
    const rows = page.locator('.table-row');
    const count = await rows.count();
    expect(count).toBeGreaterThan(5);
  });

  test('should display call sites grouped together', async ({ page }) => {
    // Wait for content to load
    await expect(page.locator('.call-sites').first()).toBeVisible({ timeout: 1000 });

    // Check that we have call site groups
    const callSiteHeaders = page.locator('.call-site-info');
    const headerCount = await callSiteHeaders.count();
    expect(headerCount).toBeGreaterThan(0);
  });

  test('should display table headers for each call site', async ({ page }) => {
    // Wait for content
    await expect(page.locator('.table-row').first()).toBeVisible({ timeout: 1000 });

    // Check for table structure with headers
    const tables = page.locator('table');
    const tableCount = await tables.count();
    expect(tableCount).toBeGreaterThan(0);

    // Each table should have headers
    const firstTable = tables.first();
    const headers = firstTable.locator('th');
    const headerCount = await headers.count();
    expect(headerCount).toBeGreaterThan(0);
  });

  test('should allow expanding collapsed call sites', async ({ page }) => {
    // Wait for content
    await expect(page.locator('.call-site-info').first()).toBeVisible({ timeout: 1000 });

    // Find the first call site header
    const firstCallSiteHeader = page.locator('.call-site-info-row').first();

    // Click to toggle expansion
    await firstCallSiteHeader.click();

    // Wait a bit for animation
    await page.waitForTimeout(100);

    // The associated table should be visible or hidden based on state
    // (This test just verifies the interaction works without errors)
  });
});
