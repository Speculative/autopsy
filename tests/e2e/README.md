# Autopsy E2E Tests

End-to-end browser tests for the Autopsy HTML reporting interface using Playwright.

## Setup

1. **Install dependencies** (one-time setup):
   ```bash
   cd tests/e2e
   npm install
   npm run install:browsers
   ```

   **Note for Arch Linux**: If you get missing library errors, install system dependencies:
   ```bash
   sudo pacman -S nss nspr at-spi2-core cups libdrm libxcb libxkbcommon
   ```
   See [ARCH_SETUP.md](./ARCH_SETUP.md) for the complete list.

2. **Generate test fixtures** (run Python scenarios):
   ```bash
   npm run test:scenarios
   ```

3. **Run tests**:
   ```bash
   npm run test:e2e
   ```

## Test Suites

### Basic UI Tests (`specs/basic-ui.spec.ts`)
- Verifies HTML report loads correctly
- Tests tab switching (History, Streams, Dashboard)
- Confirms log data is displayed

### History View Tests (`specs/history-view.spec.ts`)
- Tests that rows render within 1 second
- Verifies table format and data display
- Tests row selection and navigation

### Stream View Tests (`specs/stream-view.spec.ts`)
- Tests that rows render within 1 second
- Verifies call sites are grouped correctly
- Tests table headers and structure
- Tests expanding/collapsing call sites

### Call Stack Panel Tests (`specs/call-stack-panel.spec.ts`)
- Tests opening the call stack sidebar
- Verifies stack frame information display
- Tests closing the sidebar

### Live Mode Tests (`specs/live-mode.spec.ts`)
- Tests connecting to live mode server and displaying logs
- Verifies real-time log updates via WebSocket

## Available Scripts

```bash
# Generate Python test scenarios (creates HTML fixtures)
npm run test:scenarios

# Run all E2E tests headless (14 tests)
npm run test:e2e

# Run tests with UI (interactive mode)
npm run test:e2e:ui

# Run tests in headed mode (see browser)
npm run test:e2e:headed

# Run tests in debug mode (step through)
npm run test:e2e:debug
```

## Test Scenarios

Python scenarios in `scenarios/` generate HTML reports for testing:

- **`basic_logging.py`**: Simple logging scenario with various data types
- **`history_stream.py`**: Comprehensive scenario with nested calls and multiple log sites
- **`live_mode.py`**: Live mode scenario that streams logs in real-time

## Writing New Tests

1. **Create a Python scenario** in `scenarios/`:
   ```python
   from autopsy import report
   from autopsy.report import generate_html

   def my_scenario():
       report.init(clear=True, warn=False)
       # Your test code here
       report.log("test data")

       output_path = Path(__file__).parent.parent / "fixtures" / "my_scenario.html"
       generate_html(report, output_path=str(output_path))
   ```

2. **Create a Playwright test** in `specs/`:
   ```typescript
   import { test, expect } from '@playwright/test';
   import path from 'path';

   test.describe('My Feature', () => {
     test('should do something', async ({ page }) => {
       const reportPath = path.resolve(__dirname, '../fixtures/my_scenario.html');
       await page.goto(`file://${reportPath}`);

       // Your test assertions
       await expect(page.locator('.some-element')).toBeVisible();
     });
   });
   ```

3. **Update test:scenarios script** in `package.json` to include your new scenario.

## Selectors Reference

Common selectors used in tests:

- **Tabs**: `.tab` (with text: "History", "Streams", "Dashboard", "Tests")
- **Log rows**: `[data-log-index]` or `.table-row`
- **Call site headers**: `.call-site-info` or `.call-site-info-row`
- **Stack frames**: `.stack-frame`
- **Sidebar**: `.sidebar-body`

## CI Integration

To run tests in CI:

```yaml
- name: Install Playwright
  run: |
    cd tests/e2e
    npm ci
    npx playwright install --with-deps chromium

- name: Generate test fixtures
  run: |
    cd tests/e2e
    npm run test:scenarios

- name: Run E2E tests
  run: |
    cd tests/e2e
    npm run test:e2e
```

## Debugging

### View test reports
After running tests, open the HTML report:
```bash
npx playwright show-report
```

### Use UI mode for debugging
```bash
npm run test:e2e:ui
```

### Run a single test file
```bash
npx playwright test specs/history-view.spec.ts
```

### Run tests in headed mode (see the browser)
```bash
npm run test:e2e:headed
```
