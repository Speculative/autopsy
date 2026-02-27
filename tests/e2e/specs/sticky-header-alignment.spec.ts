import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('Sticky Header Alignment', () => {
  test.beforeEach(async ({ page }) => {
    const reportPath = path.resolve(__dirname, '../fixtures/sticky_header_alignment.html');
    await page.goto(`file://${reportPath}`);

    // Switch to Streams view
    await page.locator('.tab', { hasText: 'Streams' }).click();
    await expect(page.locator('.tab', { hasText: 'Streams' })).toHaveClass(/active/);

    // Wait for content to load
    await expect(page.locator('.table-row').first()).toBeVisible({ timeout: 2000 });
  });

  test('should align sticky header columns with table body columns when scrolling', async ({ page }) => {
    const mainPanel = page.locator('.main-panel');

    // Scroll down to trigger the sticky header
    await mainPanel.evaluate((el) => {
      el.scrollTop = 500;
    });

    // Wait for the floating header to appear
    await page.waitForTimeout(100);
    const floatingHeader = page.locator('.floating-header').first();
    await expect(floatingHeader).toBeVisible({ timeout: 1000 });

    // Get ALL th elements from the floating header (including log-number-header)
    const floatingHeaderRow = floatingHeader.locator('tr').nth(1); // Second row has column headers
    const allFloatingHeaders = floatingHeaderRow.locator('th');
    const allFloatingHeaderCount = await allFloatingHeaders.count();

    // Get the first data row from the table body
    const firstDataRow = page.locator('.table-row').first();
    const dataCells = firstDataRow.locator('td');
    const dataCellCount = await dataCells.count();

    // Column count should match (headers include an extra add-column button)
    expect(dataCellCount).toBe(allFloatingHeaderCount - 1);

    // Check alignment by comparing x-positions and widths of headers vs data cells
    const columnsToCheck = Math.min(dataCellCount, allFloatingHeaderCount - 1);

    for (let i = 0; i < columnsToCheck; i++) {
      const floatingHeaderCell = allFloatingHeaders.nth(i);
      const floatingHeaderBox = await floatingHeaderCell.boundingBox();
      expect(floatingHeaderBox).not.toBeNull();

      const dataCell = dataCells.nth(i);
      const dataCellBox = await dataCell.boundingBox();
      expect(dataCellBox).not.toBeNull();

      if (floatingHeaderBox && dataCellBox) {
        // Check horizontal alignment (x-position should match within a small tolerance)
        const xDiff = Math.abs(floatingHeaderBox.x - dataCellBox.x);
        expect(xDiff).toBeLessThan(2); // Allow 2px tolerance for rounding

        // Check width alignment (widths should match within a small tolerance)
        const widthDiff = Math.abs(floatingHeaderBox.width - dataCellBox.width);
        expect(widthDiff).toBeLessThan(2); // Allow 2px tolerance for rounding
      }
    }
  });

  test('should maintain alignment when horizontal scrolling with sticky header', async ({ page }) => {
    const tableContainer = page.locator('.table-container').first();
    const mainPanel = page.locator('.main-panel');

    // Scroll down to trigger sticky header
    await mainPanel.evaluate((el) => {
      el.scrollTop = 500;
    });

    // Wait for floating header
    await page.waitForTimeout(100);
    const floatingHeader = page.locator('.floating-header').first();
    await expect(floatingHeader).toBeVisible({ timeout: 1000 });

    // Scroll horizontally
    await tableContainer.evaluate((el) => {
      el.scrollLeft = 200;
    });

    // Wait for scroll sync
    await page.waitForTimeout(100);

    // Check alignment after horizontal scroll
    const floatingHeaderRow = floatingHeader.locator('tr').nth(1);
    const allFloatingHeaders = floatingHeaderRow.locator('th');
    const firstDataRow = page.locator('.table-row').first();
    const dataCells = firstDataRow.locator('td');
    const dataCellCount = await dataCells.count();

    // Check the first few visible columns after scroll
    const columnsToCheck = Math.min(dataCellCount, 5);
    for (let i = 0; i < columnsToCheck; i++) {
      const floatingHeaderCell = allFloatingHeaders.nth(i);
      const floatingHeaderBox = await floatingHeaderCell.boundingBox();

      const dataCell = dataCells.nth(i);
      const dataCellBox = await dataCell.boundingBox();

      if (floatingHeaderBox && dataCellBox) {
        const xDiff = Math.abs(floatingHeaderBox.x - dataCellBox.x);
        expect(xDiff).toBeLessThan(2);

        const widthDiff = Math.abs(floatingHeaderBox.width - dataCellBox.width);
        expect(widthDiff).toBeLessThan(2);
      }
    }
  });
});
