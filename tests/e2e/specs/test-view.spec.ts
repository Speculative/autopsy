import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('Test View', () => {
  test.beforeEach(async ({ page }) => {
    const reportPath = path.resolve(__dirname, '../fixtures/test_view.html');
    await page.goto(`file://${reportPath}`);

    // Switch to Tests tab
    await page.locator('.tab', { hasText: 'Tests' }).click();
    await expect(page.locator('.tab', { hasText: 'Tests' })).toHaveClass(/active/);
  });

  test('should display test summary with counts', async ({ page }) => {
    // Wait for tests view to load
    await expect(page.locator('.tests-view')).toBeVisible({ timeout: 5000 });

    // Verify summary section exists
    await expect(page.locator('.summary')).toBeVisible();

    // Check that total count is displayed
    const totalStat = page.locator('.stat', { hasText: 'Total:' });
    await expect(totalStat).toBeVisible();
  });

  test('should display tests grouped by outcome', async ({ page }) => {
    await expect(page.locator('.tests-view')).toBeVisible({ timeout: 5000 });

    // Should have test groups
    const groups = page.locator('.test-group');
    const count = await groups.count();
    expect(count).toBeGreaterThan(0);

    // Should have passed and failed groups
    await expect(page.locator('.group-header', { hasText: 'Passed' })).toBeVisible();
    await expect(page.locator('.group-header', { hasText: 'Failed' })).toBeVisible();
  });

  test('should display individual test items with names', async ({ page }) => {
    await expect(page.locator('.tests-view')).toBeVisible({ timeout: 5000 });

    // Should have test items
    const testItems = page.locator('.test-item');
    const count = await testItems.count();
    expect(count).toBeGreaterThan(0);

    // Test names should be visible
    const testNames = page.locator('.test-name');
    await expect(testNames.first()).toBeVisible();
  });

  test('should show dropdown menu when clicking ... button', async ({ page }) => {
    await expect(page.locator('.tests-view')).toBeVisible({ timeout: 5000 });

    // Find the first menu button and click it
    const menuButton = page.locator('.test-menu-button').first();
    await expect(menuButton).toBeVisible();
    await menuButton.click();

    // Dropdown should appear
    const dropdown = page.locator('.test-menu-dropdown');
    await expect(dropdown).toBeVisible();

    // Should have menu items
    await expect(dropdown.locator('.test-menu-item', { hasText: 'Show first log in history' })).toBeVisible();
    await expect(dropdown.locator('.test-menu-item', { hasText: 'Show this test only' })).toBeVisible();
  });

  test('should not occlude dropdown menu for non-first tests', async ({ page }) => {
    await expect(page.locator('.tests-view')).toBeVisible({ timeout: 5000 });

    // Find a menu button that is NOT the first one (to test overflow behavior)
    const menuButtons = page.locator('.test-menu-button');
    const buttonCount = await menuButtons.count();
    expect(buttonCount).toBeGreaterThan(1);

    // Click the last test's menu button
    const lastMenuButton = menuButtons.last();
    await lastMenuButton.click();

    // The dropdown should be visible
    const dropdown = page.locator('.test-menu-dropdown');
    await expect(dropdown).toBeVisible();

    // Verify the dropdown is not clipped - check that its bounding box is within the viewport
    const dropdownBox = await dropdown.boundingBox();
    expect(dropdownBox).not.toBeNull();

    const viewportSize = page.viewportSize();
    expect(viewportSize).not.toBeNull();

    // The dropdown should be fully visible within the viewport
    expect(dropdownBox!.x).toBeGreaterThanOrEqual(0);
    expect(dropdownBox!.y).toBeGreaterThanOrEqual(0);
    expect(dropdownBox!.x + dropdownBox!.width).toBeLessThanOrEqual(viewportSize!.width);
    expect(dropdownBox!.y + dropdownBox!.height).toBeLessThanOrEqual(viewportSize!.height);
  });

  test('should close dropdown when clicking outside', async ({ page }) => {
    await expect(page.locator('.tests-view')).toBeVisible({ timeout: 5000 });

    // Open a dropdown
    const menuButton = page.locator('.test-menu-button').first();
    await menuButton.click();
    await expect(page.locator('.test-menu-dropdown')).toBeVisible();

    // Click outside the menu
    await page.locator('.summary').click();

    // Dropdown should close
    await expect(page.locator('.test-menu-dropdown')).not.toBeVisible();
  });

  test('should show failure details for failed tests', async ({ page }) => {
    await expect(page.locator('.tests-view')).toBeVisible({ timeout: 5000 });

    // Failed tests should show error summary
    const errorSummary = page.locator('.test-error-summary');
    await expect(errorSummary.first()).toBeVisible();
  });
});
