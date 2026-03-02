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

  test('virtual scroll: expanding objects and scrolling should not create gaps', async ({ page }) => {
    // Wait for history view to render
    await expect(page.locator('[data-log-index]').first()).toBeVisible({ timeout: 2000 });

    // Helper: find gaps between consecutive visible virtual items
    // tolerance: minimum gap size in pixels to report
    async function findGaps(tolerance: number = 1) {
      return page.evaluate((tol) => {
        const items = Array.from(document.querySelectorAll('.virtual-item'))
          .map(el => {
            const rect = (el as HTMLElement).getBoundingClientRect();
            return {
              index: parseInt((el as HTMLElement).dataset.virtualIndex || '0'),
              top: rect.top,
              bottom: rect.bottom,
              height: rect.height,
            };
          })
          .sort((a, b) => a.index - b.index);

        const gaps: { between: string; gap: number }[] = [];
        for (let i = 0; i < items.length - 1; i++) {
          const current = items[i];
          const next = items[i + 1];
          if (next.index === current.index + 1) {
            const gap = next.top - current.bottom;
            if (Math.abs(gap) > tol) {
              gaps.push({ between: `${current.index}-${next.index}`, gap });
            }
          }
        }
        return gaps;
      }, tolerance);
    }

    // Expand visible expandable objects to change item heights
    const expandableCount = await page.locator('.value-wrapper.expandable').count();
    expect(expandableCount).toBeGreaterThan(0);

    for (let i = 0; i < Math.min(expandableCount, 5); i++) {
      await page.locator('.value-wrapper.expandable').nth(i).click();
      await page.waitForTimeout(50);
    }
    await page.waitForTimeout(200);

    // After expanding and settling, no gaps should exist
    expect(await findGaps()).toEqual([]);

    // Scroll down past expanded items so they leave the viewport and unmount.
    const container = page.locator('.virtual-list-container');
    await container.evaluate(el => { el.scrollTop = 2000; });
    await page.waitForTimeout(200);
    expect(await findGaps()).toEqual([]);

    // Scroll back to top — items re-enter the viewport. With keyed {#each},
    // components are recreated; with durable expansion state, TreeViews
    // restore their expanded state. No gaps should appear.
    await container.evaluate(el => { el.scrollTop = 0; });
    await page.waitForTimeout(300);
    expect(await findGaps()).toEqual([]);

    // Scroll through the entire list in steps.
    // During scrolling, small transient overlaps (<5px) are acceptable as newly-
    // rendered items are positioned with estimated heights and corrected within
    // one frame by ResizeObserver. But large gaps (>10px) should never occur —
    // those would indicate stale measured heights from expanded objects.
    const scrollHeight = await container.evaluate(el => el.scrollHeight);
    for (let pos = 0; pos <= scrollHeight; pos += 400) {
      await container.evaluate((el, scrollPos) => { el.scrollTop = scrollPos; }, pos);
      const bigGaps = await findGaps(10);
      expect(bigGaps, `Large gaps found at scroll position ${pos}`).toEqual([]);
    }

    // After settling at the end, all gaps (even small ones) should be corrected
    await page.waitForTimeout(300);
    expect(await findGaps()).toEqual([]);
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
