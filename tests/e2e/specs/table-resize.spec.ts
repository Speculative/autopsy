import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Helper to get the sum of all visible column widths (including # and + columns)
 * by measuring the actual table width.
 */
async function getTableWidth(page: import('@playwright/test').Page) {
  const table = page.locator('.value-table').first();
  const box = await table.boundingBox();
  return box?.width ?? 0;
}

async function getContainerWidth(page: import('@playwright/test').Page) {
  const container = page.locator('.table-container').first();
  const box = await container.boundingBox();
  return box?.width ?? 0;
}

test.describe('Table Resize', () => {
  test.beforeEach(async ({ page }) => {
    const reportPath = path.resolve(__dirname, '../fixtures/table_resize.html');
    await page.goto(`file://${reportPath}`);

    // Switch to Streams view
    await page.locator('.tab', { hasText: 'Streams' }).click();
    await expect(page.locator('.tab', { hasText: 'Streams' })).toHaveClass(/active/);

    // Wait for content to load
    await expect(page.locator('.table-row').first()).toBeVisible({ timeout: 2000 });
  });

  test('table should fill the available width initially', async ({ page }) => {
    const tableWidth = await getTableWidth(page);
    const containerWidth = await getContainerWidth(page);

    // Table should fill close to 100% of the container
    // Allow some tolerance for scrollbar/padding
    expect(tableWidth).toBeGreaterThan(containerWidth - 20);
  });

  test('table should fill the available width after hiding a column', async ({ page }) => {
    const containerWidth = await getContainerWidth(page);

    // Click the filter menu button on the first column header to open the dropdown
    const firstColumnHeader = page.locator('.column-header').first();
    const filterButton = firstColumnHeader.locator('.filter-menu-button');
    await filterButton.click();

    // Wait for dropdown to appear
    const dropdown = page.locator('.column-dropdown-menu');
    await expect(dropdown).toBeVisible({ timeout: 1000 });

    // Click "Hide column"
    const hideButton = dropdown.locator('.dropdown-item', { hasText: 'Hide column' });
    await hideButton.click();

    // Wait for the column to be hidden and widths to recalculate
    await page.waitForTimeout(200);

    const tableWidthAfter = await getTableWidth(page);

    // After hiding a column, the table should still fill the container width
    expect(tableWidthAfter).toBeGreaterThan(containerWidth - 20);
  });

  test('table should fill the available width after hiding multiple columns', async ({ page }) => {
    const containerWidth = await getContainerWidth(page);

    // Hide two columns
    for (let i = 0; i < 2; i++) {
      const firstColumnHeader = page.locator('.column-header').first();
      const filterButton = firstColumnHeader.locator('.filter-menu-button');
      await filterButton.click();

      const dropdown = page.locator('.column-dropdown-menu');
      await expect(dropdown).toBeVisible({ timeout: 1000 });

      const hideButton = dropdown.locator('.dropdown-item', { hasText: 'Hide column' });
      await hideButton.click();

      await page.waitForTimeout(200);
    }

    const tableWidthAfter = await getTableWidth(page);

    // After hiding columns, the table should still fill the container width
    expect(tableWidthAfter).toBeGreaterThan(containerWidth - 20);
  });

  test('table should fill the available width after resizing the viewport wider', async ({ page }) => {
    // Set a smaller viewport first
    await page.setViewportSize({ width: 800, height: 600 });
    await page.waitForTimeout(200);

    // Now make it wider
    await page.setViewportSize({ width: 1400, height: 600 });
    await page.waitForTimeout(200);

    const tableWidth = await getTableWidth(page);
    const containerWidth = await getContainerWidth(page);

    expect(tableWidth).toBeGreaterThan(containerWidth - 20);
  });

  test('table should fill the available width after resizing the viewport smaller', async ({ page }) => {
    // Start with a large viewport
    await page.setViewportSize({ width: 1400, height: 600 });
    await page.waitForTimeout(200);

    // Shrink it
    await page.setViewportSize({ width: 800, height: 600 });
    await page.waitForTimeout(200);

    const tableWidth = await getTableWidth(page);
    const containerWidth = await getContainerWidth(page);

    expect(tableWidth).toBeGreaterThan(containerWidth - 20);
  });
});
