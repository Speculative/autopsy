<script lang="ts">
  import type { TestResult, AutopsyData } from "./types";
  import CodeLocation from "./CodeLocation.svelte";
  import { MoreVertical } from "lucide-svelte";

  interface Props {
    data: AutopsyData;
    testFilter?: string | null;
    onShowInHistory?: (logIndex: number) => void;
    onSetTestFilter?: (testNodeid: string) => void;
  }

  let { data, testFilter, onShowInHistory, onSetTestFilter }: Props = $props();

  // Get tests from data, defaulting to empty array
  let allTests: TestResult[] = $derived(data.tests || []);

  // Track which test menu is open
  let openMenuTestId: string | null = $state(null);

  // Track which test failures are expanded
  let expandedFailures: Set<string> = $state(new Set());

  // Separate filtered and non-filtered tests
  let filteredTest: TestResult | null = $derived(
    testFilter ? allTests.find(test => test.nodeid === testFilter) ?? null : null
  );

  let otherTests: TestResult[] = $derived(
    testFilter ? allTests.filter(test => test.nodeid !== testFilter) : allTests
  );

  // Group other tests by outcome
  let otherTestsByOutcome = $derived(() => {
    const grouped: Record<string, TestResult[]> = {
      failed: [],
      passed: [],
      skipped: [],
      error: [],
    };

    for (const test of otherTests) {
      if (test.outcome in grouped) {
        grouped[test.outcome].push(test);
      }
    }

    return grouped;
  });

  // Summary stats (always show stats for all tests)
  let summary = $derived(() => {
    const counts = { passed: 0, failed: 0, skipped: 0, error: 0 };
    for (const test of allTests) {
      if (test.outcome in counts) {
        counts[test.outcome as keyof typeof counts]++;
      }
    }
    return {
      total: allTests.length,
      ...counts,
    };
  });

  function getOutcomeColor(outcome: string): string {
    switch (outcome) {
      case "passed":
        return "#22c55e";
      case "failed":
        return "#ef4444";
      case "skipped":
        return "#f59e0b";
      case "error":
        return "#dc2626";
      default:
        return "#6b7280";
    }
  }

  function getOutcomeIcon(outcome: string): string {
    switch (outcome) {
      case "passed":
        return "✓";
      case "failed":
        return "✗";
      case "skipped":
        return "⊘";
      case "error":
        return "⚠";
      default:
        return "?";
    }
  }

  function toggleTestMenu(testId: string) {
    openMenuTestId = openMenuTestId === testId ? null : testId;
  }

  function handleShowFirstLog(test: TestResult) {
    if (test.start_log_index !== undefined && onShowInHistory) {
      onShowInHistory(test.start_log_index);
    }
    openMenuTestId = null;
  }

  function handleShowTestOnly(test: TestResult) {
    if (onSetTestFilter) {
      onSetTestFilter(test.nodeid);
    }
    openMenuTestId = null;
  }

  function toggleFailureExpansion(testId: string) {
    const newExpanded = new Set(expandedFailures);
    if (newExpanded.has(testId)) {
      newExpanded.delete(testId);
    } else {
      newExpanded.add(testId);
    }
    expandedFailures = newExpanded;
  }

  function getErrorSummary(test: TestResult): string {
    // Use the error_summary if available (captured directly from pytest)
    if (test.error_summary) {
      return test.error_summary;
    }

    // Fallback: parse from failure_message if error_summary wasn't captured
    if (!test.failure_message) {
      return 'Test failed';
    }

    // Extract just the assertion error line from the full traceback
    // Pytest formats errors with lines starting with "E       "
    const lines = test.failure_message.split('\n');

    // Look for lines starting with "E       " which contain the actual error
    const errorLines = lines.filter(line => line.trim().startsWith('E       '));

    if (errorLines.length > 0) {
      // Get the last error line, which typically has the key message
      const lastErrorLine = errorLines[errorLines.length - 1];
      return lastErrorLine.replace(/^E\s+/, '').trim();
    }

    // Fallback: look for common exception patterns in the last few lines
    for (let i = lines.length - 1; i >= Math.max(0, lines.length - 5); i--) {
      const line = lines[i].trim();
      if (line.match(/^(AssertionError|ValueError|TypeError|KeyError|AttributeError|IndexError|RuntimeError|Exception):/)) {
        return line;
      }
    }

    // Last resort: return first non-empty line
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed) {
        return trimmed;
      }
    }

    return 'Test failed';
  }

  // Close menu when clicking outside
  function handleClickOutside(e: MouseEvent) {
    if (!(e.target as Element)?.closest(".test-menu")) {
      openMenuTestId = null;
    }
  }

  $effect(() => {
    if (openMenuTestId !== null) {
      document.addEventListener("click", handleClickOutside);
      return () => document.removeEventListener("click", handleClickOutside);
    }
  });
</script>

<div class="tests-view">
  {#if allTests.length === 0}
    <div class="empty-state">
      <p>No test results captured.</p>
      <p class="hint">
        Run tests with pytest to capture test results and associate them with logs.
      </p>
    </div>
  {:else}
    <div class="summary">
      <h3>Test Summary</h3>
      <div class="summary-stats">
        <div class="stat">
          <span class="stat-label">Total:</span>
          <span class="stat-value">{summary().total}</span>
        </div>
        <div class="stat" style="color: {getOutcomeColor('passed')}">
          <span class="stat-label">Passed:</span>
          <span class="stat-value">{summary().passed}</span>
        </div>
        <div class="stat" style="color: {getOutcomeColor('failed')}">
          <span class="stat-label">Failed:</span>
          <span class="stat-value">{summary().failed}</span>
        </div>
        <div class="stat" style="color: {getOutcomeColor('skipped')}">
          <span class="stat-label">Skipped:</span>
          <span class="stat-value">{summary().skipped}</span>
        </div>
        {#if summary().error > 0}
          <div class="stat" style="color: {getOutcomeColor('error')}">
            <span class="stat-label">Error:</span>
            <span class="stat-value">{summary().error}</span>
          </div>
        {/if}
      </div>
    </div>

    <div class="test-groups">
      {#if filteredTest}
        <div class="test-group filtered-group">
          <h4 class="group-header" style="color: {getOutcomeColor(filteredTest.outcome)}">
            Filtered: {filteredTest.outcome.charAt(0).toUpperCase() + filteredTest.outcome.slice(1)}
          </h4>
          <div class="test-list">
            <div class="test-item" class:has-failure={filteredTest.failure_message}>
              <div
                class="test-header"
                class:clickable={filteredTest.failure_message}
                onclick={() => filteredTest.failure_message && toggleFailureExpansion(filteredTest.nodeid)}
              >
                <span class="test-icon" style="color: {getOutcomeColor(filteredTest.outcome)}">
                  {getOutcomeIcon(filteredTest.outcome)}
                </span>
                <span class="test-name-with-location">
                  <span class="test-name">{filteredTest.test_name || filteredTest.nodeid}</span>
                  {#if filteredTest.filename}
                    <span class="inline-location">
                      <CodeLocation
                        filename={filteredTest.filename}
                        line={filteredTest.line || 0}
                        showFunction={false}
                        compact={true}
                      />
                    </span>
                  {/if}
                </span>
                {#if filteredTest.failure_message}
                  <span class="expand-indicator">
                    {expandedFailures.has(filteredTest.nodeid) ? "▼" : "▶"}
                  </span>
                {/if}
                <span class="test-logs">
                  {filteredTest.log_count} log{filteredTest.log_count === 1 ? "" : "s"}
                </span>
                <div class="test-menu">
                  <button
                    class="test-menu-button"
                    onclick={(e) => { e.stopPropagation(); toggleTestMenu(filteredTest.nodeid); }}
                    title="Test actions"
                  >
                    <MoreVertical size={16} />
                  </button>
                  {#if openMenuTestId === filteredTest.nodeid}
                    <div class="test-menu-dropdown">
                      <button
                        class="test-menu-item"
                        onclick={() => handleShowFirstLog(filteredTest)}
                        disabled={filteredTest.start_log_index === undefined}
                      >
                        Show first log in history
                      </button>
                      <button
                        class="test-menu-item"
                        onclick={() => handleShowTestOnly(filteredTest)}
                      >
                        Show this test only
                      </button>
                    </div>
                  {/if}
                </div>
              </div>

              {#if filteredTest.failure_message}
                {#if !expandedFailures.has(filteredTest.nodeid)}
                  <div class="test-error-summary">
                    {getErrorSummary(filteredTest)}
                  </div>
                {:else}
                  <div class="test-failure">
                    <pre>{filteredTest.failure_message}</pre>
                  </div>
                {/if}
              {/if}
            </div>
          </div>
        </div>

        <div class="filter-separator">
          <div class="separator-line"></div>
          <span class="separator-text">Other Tests</span>
          <div class="separator-line"></div>
        </div>
      {/if}

      {#each ["failed", "error", "passed", "skipped"] as outcome}
        {#if otherTestsByOutcome()[outcome].length > 0}
          <div class="test-group" class:dimmed={filteredTest !== null}>
            <h4 class="group-header" style="color: {getOutcomeColor(outcome)}">
              {outcome.charAt(0).toUpperCase() + outcome.slice(1)} ({otherTestsByOutcome()[outcome].length})
            </h4>
            <div class="test-list">
              {#each otherTestsByOutcome()[outcome] as test}
                <div class="test-item" class:has-failure={test.failure_message}>
                  <div
                    class="test-header"
                    class:clickable={test.failure_message}
                    onclick={() => test.failure_message && toggleFailureExpansion(test.nodeid)}
                  >
                    <span class="test-icon" style="color: {getOutcomeColor(test.outcome)}">
                      {getOutcomeIcon(test.outcome)}
                    </span>
                    <span class="test-name-with-location">
                      <span class="test-name">{test.test_name || test.nodeid}</span>
                      {#if test.filename}
                        <span class="inline-location">
                          <CodeLocation
                            filename={test.filename}
                            line={test.line || 0}
                            showFunction={false}
                            compact={true}
                          />
                        </span>
                      {/if}
                    </span>
                    {#if test.failure_message}
                      <span class="expand-indicator">
                        {expandedFailures.has(test.nodeid) ? "▼" : "▶"}
                      </span>
                    {/if}
                    <span class="test-logs">
                      {test.log_count} log{test.log_count === 1 ? "" : "s"}
                    </span>
                    <div class="test-menu">
                      <button
                        class="test-menu-button"
                        onclick={(e) => { e.stopPropagation(); toggleTestMenu(test.nodeid); }}
                        title="Test actions"
                      >
                        <MoreVertical size={16} />
                      </button>
                      {#if openMenuTestId === test.nodeid}
                        <div class="test-menu-dropdown">
                          <button
                            class="test-menu-item"
                            onclick={() => handleShowFirstLog(test)}
                            disabled={test.start_log_index === undefined}
                          >
                            Show first log in history
                          </button>
                          <button
                            class="test-menu-item"
                            onclick={() => handleShowTestOnly(test)}
                          >
                            Show this test only
                          </button>
                        </div>
                      {/if}
                    </div>
                  </div>

                  {#if test.failure_message}
                    {#if !expandedFailures.has(test.nodeid)}
                      <div class="test-error-summary">
                        {getErrorSummary(test)}
                      </div>
                    {:else}
                      <div class="test-failure">
                        <pre>{test.failure_message}</pre>
                      </div>
                    {/if}
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}
      {/each}
    </div>
  {/if}
</div>

<style>
  .tests-view {
    padding: 20px;
    height: 100%;
    overflow-y: auto;
  }

  .empty-state {
    text-align: center;
    padding: 40px;
    color: #6b7280;
  }

  .empty-state .hint {
    margin-top: 10px;
    font-size: 14px;
  }

  .summary {
    margin-bottom: 30px;
    padding: 20px;
    background: #f9fafb;
    border-radius: 8px;
  }

  .summary h3 {
    margin: 0 0 15px 0;
    font-size: 18px;
    font-weight: 600;
  }

  .summary-stats {
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
  }

  .stat {
    display: flex;
    gap: 8px;
    font-size: 16px;
  }

  .stat-label {
    font-weight: 500;
  }

  .stat-value {
    font-weight: 700;
  }

  .test-groups {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .filter-separator {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 12px 0;
  }

  .separator-line {
    flex: 1;
    height: 1px;
    background: #e5e7eb;
  }

  .separator-text {
    font-size: 0.85rem;
    color: #6b7280;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .test-group {
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    overflow: hidden;
  }

  .test-group.filtered-group {
    border: 2px solid #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
  }

  .test-group.dimmed {
    opacity: 0.6;
    border-style: dashed;
  }

  .group-header {
    margin: 0;
    padding: 12px 16px;
    background: #f9fafb;
    border-bottom: 1px solid #e5e7eb;
    font-size: 16px;
    font-weight: 600;
  }

  .test-list {
    display: flex;
    flex-direction: column;
  }

  .test-item {
    padding: 16px;
    border-bottom: 1px solid #e5e7eb;
  }

  .test-item:last-child {
    border-bottom: none;
  }

  .test-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
  }

  .test-header.clickable {
    cursor: pointer;
    user-select: none;
    transition: background-color 0.15s;
    padding: 8px;
    margin: -8px;
    border-radius: 4px;
  }

  .test-header.clickable:hover {
    background-color: #f9fafb;
  }

  .test-icon {
    font-size: 18px;
    font-weight: bold;
  }

  .test-name-with-location {
    flex: 1;
    display: flex;
    align-items: baseline;
    gap: 8px;
    min-height: 0;
  }

  .test-name {
    font-family: "SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas,
      "Courier New", monospace;
    font-size: 14px;
    font-weight: 500;
    line-height: 1.4;
    display: flex;
    align-items: center;
  }

  .inline-location {
    flex-shrink: 0;
    display: flex;
    align-items: center;
  }

  .expand-indicator {
    font-size: 10px;
    color: #6b7280;
    margin-left: 4px;
    transition: transform 0.15s;
  }

  .test-logs {
    font-size: 12px;
    color: #6b7280;
    background: #f3f4f6;
    padding: 2px 8px;
    border-radius: 4px;
  }

  .test-error-summary {
    margin-top: 8px;
    padding: 8px 12px;
    background: #fef2f2;
    border-left: 3px solid #ef4444;
    border-radius: 4px;
    font-family: "SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas,
      "Courier New", monospace;
    font-size: 13px;
    color: #991b1b;
    overflow-x: auto;
    white-space: nowrap;
  }

  .test-failure {
    margin-top: 12px;
    padding: 12px;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 6px;
    overflow-x: auto;
  }

  .test-failure pre {
    margin: 0;
    font-family: "SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas,
      "Courier New", monospace;
    font-size: 12px;
    color: #991b1b;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .test-menu {
    position: relative;
    margin-left: auto;
  }

  .test-menu-button {
    background: none;
    border: none;
    color: #9ca3af;
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
  }

  .test-menu-button:hover {
    background: #f3f4f6;
    color: #4b5563;
  }

  .test-menu-dropdown {
    position: absolute;
    top: calc(100% + 4px);
    right: 0;
    min-width: 200px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    overflow: hidden;
    z-index: 100;
  }

  .test-menu-item {
    width: 100%;
    padding: 10px 14px;
    background: none;
    border: none;
    text-align: left;
    font-size: 13px;
    color: #374151;
    cursor: pointer;
    transition: background-color 0.2s;
    border-bottom: 1px solid #f3f4f6;
  }

  .test-menu-item:last-child {
    border-bottom: none;
  }

  .test-menu-item:hover:not(:disabled) {
    background: #f9fafb;
  }

  .test-menu-item:disabled {
    color: #9ca3af;
    cursor: not-allowed;
  }
</style>
