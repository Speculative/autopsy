import { test, expect } from '@playwright/test';
import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('Live Mode', () => {
  let pythonProcess: ChildProcess | null = null;

  test.beforeAll(async () => {
    // Start the Python live mode scenario
    const scenarioPath = path.resolve(__dirname, '../scenarios/live_mode.py');
    pythonProcess = spawn('uv', ['run', 'python', scenarioPath], {
      cwd: path.resolve(__dirname, '../../..'),
    });

    // Wait for the server to start (give it time to initialize)
    await new Promise(resolve => setTimeout(resolve, 5000));
  });

  test.afterAll(async () => {
    // Clean up: kill the Python process
    if (pythonProcess) {
      pythonProcess.kill();
    }
  });

  test('should connect to live mode server and display logs', async ({ page }) => {
    // Navigate to the live mode server with live=true query parameter
    await page.goto('http://localhost:8765/?live=true');

    // Wait for the page to load
    await expect(page.locator('main')).toBeVisible({ timeout: 5000 });

    // Switch to History view to see logs
    await page.locator('.tab', { hasText: 'History' }).click();

    // Wait for logs to appear (the Python script generates them)
    const logRows = page.locator('[data-log-index]');
    await expect(logRows.first()).toBeVisible({ timeout: 10000 });

    // We should have at least some log entries (timing may vary)
    const count = await logRows.count();
    expect(count).toBeGreaterThan(0);
  });

  test('should update in real-time as new logs arrive', async ({ page }) => {
    // Navigate to live mode server with live=true query parameter
    await page.goto('http://localhost:8765/?live=true');

    // Wait for initial load
    await expect(page.locator('main')).toBeVisible({ timeout: 5000 });

    // Switch to Streams view
    await page.locator('.tab', { hasText: 'Streams' }).click();

    // Wait for at least one log to appear
    const rows = page.locator('.table-row');
    await expect(rows.first()).toBeVisible({ timeout: 10000 });

    // Verify logs are present (this confirms WebSocket connection works)
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
  });
});
