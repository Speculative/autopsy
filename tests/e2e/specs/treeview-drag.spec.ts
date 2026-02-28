import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('TreeView Drag to Create Computed Columns', () => {
  test.beforeEach(async ({ page }) => {
    const reportPath = path.resolve(__dirname, '../fixtures/treeview_drag.html');
    await page.goto(`file://${reportPath}`);
  });

  test('should create computed column by dragging TreeView key to column header', async ({ page }) => {
    // Start in Streams view
    await page.locator('.tab', { hasText: 'Streams' }).click();
    await expect(page.locator('.tab', { hasText: 'Streams' })).toHaveClass(/active/);

    // Wait for stream view to load
    await expect(page.locator('.call-site-info').first()).toBeVisible({ timeout: 1000 });

    // Get initial column count
    const initialHeaders = page.locator('.column-header');
    const initialColumnCount = await initialHeaders.count();

    // Click on a table row to open the sidebar with call stack
    const tableRow = page.locator('.table-row.clickable').first();
    await expect(tableRow).toBeVisible({ timeout: 1000 });
    await tableRow.click();

    // Wait for sidebar to appear
    const sidebar = page.locator('.sidebar-body');
    await expect(sidebar).toBeVisible({ timeout: 1000 });

    // Expand user_data in the call stack TreeView
    const userDataKey = page.locator('.sidebar .key .key-name', { hasText: 'user_data:' }).locator('..');
    await expect(userDataKey).toBeVisible({ timeout: 1000 });
    await userDataKey.click();
    await page.waitForTimeout(100);

    // Expand user
    const userKey = page.locator('.sidebar .key .key-name', { hasText: 'user:' }).locator('..');
    await userKey.click();
    await page.waitForTimeout(100);

    // Verify user is expanded
    const expandIcon = userKey.locator('.expand-icon');
    await expect(expandIcon).toHaveText('▼');

    // Find and verify city key is visible
    const cityKey = page.locator('.sidebar .key .key-name', { hasText: 'city:' }).locator('..');
    await expect(cityKey).toBeVisible();

    // Get bounding boxes for drag and drop
    const cityKeyBox = await cityKey.boundingBox();
    expect(cityKeyBox).not.toBeNull();

    // Find the first column header in the table to use as drop target
    const firstColumnHeader = page.locator('.column-header').first();
    await expect(firstColumnHeader).toBeVisible();
    const headerBox = await firstColumnHeader.boundingBox();
    expect(headerBox).not.toBeNull();

    // Perform drag and drop using Playwright's dragTo
    // Note: We'll use manual mouse movements for more control
    await page.mouse.move(cityKeyBox!.x + 10, cityKeyBox!.y + 10);
    await page.mouse.down();

    // Verify TreeView stays expanded during drag
    let iconText = await expandIcon.textContent();
    expect(iconText).toBe('▼');

    // Move to the drop target (to the right of the first column)
    await page.mouse.move(
      headerBox!.x + headerBox!.width - 10,
      headerBox!.y + 10,
      { steps: 10 }
    );

    // Verify still expanded
    iconText = await expandIcon.textContent();
    expect(iconText).toBe('▼');

    // Drop
    await page.mouse.up();
    await page.waitForTimeout(500);

    // Verify TreeView is still expanded after drop
    await expect(expandIcon).toHaveText('▼');

    // Verify a new computed column was created
    const updatedHeaders = page.locator('.column-header');
    const newColumnCount = await updatedHeaders.count();
    expect(newColumnCount).toBeGreaterThan(initialColumnCount);

    // Find and verify the computed column
    const computedColumns = page.locator('.column-header.computed-column');
    await expect(computedColumns.first()).toBeVisible();

    // Verify it has the computed icon (ƒ)
    const computedIcon = computedColumns.first().locator('.computed-icon');
    await expect(computedIcon).toHaveText('ƒ');

    // Verify the computed column has values (may be nested objects or direct values)
    // The new column should have been added and contain data from the dragged expression
    const computedColumnCells = page.locator('tbody tr:first-child .value-cell').nth(newColumnCount - 1);
    await expect(computedColumnCells).toBeVisible();

    // Log what we got for debugging
    const cellText = await computedColumnCells.textContent();
    console.log('Computed column cell text:', cellText);

    // The cell should not be empty
    expect(cellText?.trim()).not.toBe('');
    expect(cellText?.trim()).not.toBe('—'); // Not the empty cell indicator
  });

  test('should keep TreeView in table cell expanded when dragging to create column', async ({ page }) => {
    // This tests the specific scenario: dragging from a TreeView INSIDE a Streams table cell
    // Start in Streams view
    await page.locator('.tab', { hasText: 'Streams' }).click();
    await expect(page.locator('.tab', { hasText: 'Streams' })).toHaveClass(/active/);

    // Wait for stream view to load
    await expect(page.locator('.call-site-info').first()).toBeVisible({ timeout: 1000 });

    // Get initial column count
    const initialHeaders = page.locator('.column-header');
    const initialColumnCount = await initialHeaders.count();

    // Step 1: Expand the root object in the user_data column (first row)
    // The root TreeView has no key, so there's no expand-icon - just a value-wrapper.expandable
    const rootExpandable = page.locator('.value-cell .value-wrapper.expandable').first();
    await expect(rootExpandable).toBeVisible({ timeout: 1000 });
    await rootExpandable.click();
    await page.waitForTimeout(200);

    // Step 2: Verify child keys appeared (user: and status:)
    const userKeyInCell = page.locator('.value-cell .key .key-name', { hasText: 'user:' }).locator('..');
    await expect(userKeyInCell).toBeVisible({ timeout: 1000 });

    // Step 3: Expand the "user:" child to reveal name, age, city
    await userKeyInCell.click();
    await page.waitForTimeout(200);

    // Verify "user:" is expanded (shows ▼)
    const userExpandIcon = userKeyInCell.locator('.expand-icon');
    await expect(userExpandIcon).toHaveText('▼');

    // Verify children are visible
    const cityKeyInCell = page.locator('.value-cell .key .key-name', { hasText: 'city:' }).locator('..');
    await expect(cityKeyInCell).toBeVisible({ timeout: 1000 });

    // Step 4: Drag the "city:" key to the column header area
    expect(await cityKeyInCell.getAttribute('draggable')).toBe('true');

    const cityKeyBox = await cityKeyInCell.boundingBox();
    expect(cityKeyBox).not.toBeNull();

    const lastColumnHeader = page.locator('.column-header').last();
    await expect(lastColumnHeader).toBeVisible();
    const headerBox = await lastColumnHeader.boundingBox();
    expect(headerBox).not.toBeNull();

    // Perform drag using mouse events (triggers HTML5 DnD on draggable elements)
    await page.mouse.move(cityKeyBox!.x + 10, cityKeyBox!.y + 5);
    await page.mouse.down();
    await page.waitForTimeout(100);

    // Verify still expanded during drag
    await expect(userExpandIcon).toHaveText('▼');

    // Move to the drop target (center of the last column header)
    await page.mouse.move(
      headerBox!.x + headerBox!.width / 2,
      headerBox!.y + headerBox!.height / 2,
      { steps: 10 }
    );
    await page.waitForTimeout(100);

    // Drop
    await page.mouse.up();
    await page.waitForTimeout(500);

    // Step 5: Verify a new computed column was created (confirming drag actually worked)
    const newColumnCount = await page.locator('.column-header').count();
    expect(newColumnCount).toBeGreaterThan(initialColumnCount);

    // Step 6: Verify the TreeView is STILL expanded after the computed column was created
    // This is the actual bug: the TreeView collapses when a computed column is added
    // because the {#each} re-render destroys and recreates TreeView components
    await expect(userExpandIcon).toHaveText('▼');

    // Verify children are still visible
    await expect(page.locator('.value-cell .key-name', { hasText: 'city:' }).first()).toBeVisible();
    await expect(page.locator('.value-cell .key-name', { hasText: 'name:' }).first()).toBeVisible();
  });

  test('should keep TreeView expanded when dragging a key', async ({ page }) => {
    // Switch to History view
    await page.locator('.tab', { hasText: 'History' }).click();
    await expect(page.locator('.tab', { hasText: 'History' })).toHaveClass(/active/);

    // Wait for rows to load
    await expect(page.locator('[data-log-index]').first()).toBeVisible({ timeout: 1000 });

    // Click on the first clickable row
    const clickableRow = page.locator('[data-log-index].clickable').first();
    await clickableRow.click();

    // Wait for sidebar
    const sidebar = page.locator('.sidebar-body');
    await expect(sidebar).toBeVisible({ timeout: 1000 });

    // Find and expand user_data
    const userDataKey = page.locator('.key .key-name', { hasText: 'user_data:' }).locator('..');
    await userDataKey.click();
    await page.waitForTimeout(100);

    // Expand user
    const userKey = page.locator('.key .key-name', { hasText: 'user:' }).locator('..');
    await userKey.click();
    await page.waitForTimeout(100);

    // Verify expanded
    const expandIcon = userKey.locator('.expand-icon');
    await expect(expandIcon).toHaveText('▼');

    // Verify children visible
    const nameKey = page.locator('.key-name', { hasText: 'name:' });
    await expect(nameKey).toBeVisible();

    // Start dragging the user key
    const userKeyBox = await userKey.boundingBox();
    expect(userKeyBox).not.toBeNull();

    await page.mouse.move(userKeyBox!.x + 10, userKeyBox!.y + 10);
    await page.mouse.down();
    await page.mouse.move(userKeyBox!.x + 100, userKeyBox!.y + 10, { steps: 10 });

    // Check it's still expanded during drag
    const iconTextDuringDrag = await expandIcon.textContent();
    expect(iconTextDuringDrag).toBe('▼');

    // Release
    await page.mouse.up();

    // Should still be expanded after drag
    await expect(expandIcon).toHaveText('▼');
    await expect(nameKey).toBeVisible();
  });
});
