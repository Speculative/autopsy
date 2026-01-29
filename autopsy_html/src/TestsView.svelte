<script lang="ts">
  import type { TestResult, AutopsyData } from "./types";
  import CodeLocation from "./CodeLocation.svelte";

  interface Props {
    data: AutopsyData;
    onShowInHistory?: (logIndex: number) => void;
  }

  let { data, onShowInHistory }: Props = $props();

  // Get tests from data, defaulting to empty array
  let tests: TestResult[] = $derived(data.tests || []);

  // Group tests by outcome
  let testsByOutcome = $derived(() => {
    const grouped: Record<string, TestResult[]> = {
      failed: [],
      passed: [],
      skipped: [],
      error: [],
    };

    for (const test of tests) {
      if (test.outcome in grouped) {
        grouped[test.outcome].push(test);
      }
    }

    return grouped;
  });

  // Summary stats
  let summary = $derived(() => {
    return {
      total: tests.length,
      passed: testsByOutcome().passed.length,
      failed: testsByOutcome().failed.length,
      skipped: testsByOutcome().skipped.length,
      error: testsByOutcome().error.length,
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
</script>

<div class="tests-view">
  {#if tests.length === 0}
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
      {#each ["failed", "error", "passed", "skipped"] as outcome}
        {#if testsByOutcome()[outcome].length > 0}
          <div class="test-group">
            <h4 class="group-header" style="color: {getOutcomeColor(outcome)}">
              {outcome.charAt(0).toUpperCase() + outcome.slice(1)} ({testsByOutcome()[outcome].length})
            </h4>
            <div class="test-list">
              {#each testsByOutcome()[outcome] as test}
                <div class="test-item">
                  <div class="test-header">
                    <span class="test-icon" style="color: {getOutcomeColor(test.outcome)}">
                      {getOutcomeIcon(test.outcome)}
                    </span>
                    <span class="test-name">{test.test_name || test.nodeid}</span>
                    <span class="test-logs">
                      {test.log_count} log{test.log_count === 1 ? "" : "s"}
                    </span>
                  </div>

                  {#if test.filename}
                    <div class="test-location">
                      <CodeLocation
                        filename={test.filename}
                        line={test.line || 0}
                      />
                    </div>
                  {/if}

                  {#if test.failure_message}
                    <div class="test-failure">
                      <pre>{test.failure_message}</pre>
                    </div>
                  {/if}

                  {#if test.log_count > 0 && onShowInHistory}
                    <div class="test-actions">
                      <button
                        class="btn-show-logs"
                        onclick={() => {
                          if (test.start_log_index !== undefined && onShowInHistory) {
                            onShowInHistory(test.start_log_index);
                          }
                        }}
                      >
                        View Logs in History
                      </button>
                    </div>
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

  .test-group {
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    overflow: hidden;
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

  .test-icon {
    font-size: 18px;
    font-weight: bold;
  }

  .test-name {
    flex: 1;
    font-family: "SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas,
      "Courier New", monospace;
    font-size: 14px;
    font-weight: 500;
  }

  .test-logs {
    font-size: 12px;
    color: #6b7280;
    background: #f3f4f6;
    padding: 2px 8px;
    border-radius: 4px;
  }

  .test-location {
    margin-bottom: 8px;
    font-size: 13px;
    color: #6b7280;
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

  .test-actions {
    margin-top: 12px;
    display: flex;
    gap: 8px;
  }

  .btn-show-logs {
    padding: 6px 12px;
    background: #3b82f6;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    cursor: pointer;
    transition: background-color 0.2s;
  }

  .btn-show-logs:hover {
    background: #2563eb;
  }
</style>
