<script lang="ts">
  import type { AutopsyData, CallSite, ValueGroup, ComputedColumn, LogMark } from "./types";
  import TreeView from "./TreeView.svelte";

  interface Props {
    data: AutopsyData;
    logMarks?: Record<number, LogMark>;
    computedColumns?: Record<string, ComputedColumn[]>;
    columnOrders?: Record<string, string[]>;
    frameFilter?: string | null;
    testFilter?: string | null;
    rangeFilter?: { start: number; end: number } | null;
    isExpanded?: boolean;
    onMarkLog?: (logIndex: number, color: string, note: string) => void;
    onEntryClick?: (logIndex: number, stackTraceId?: string) => void;
  }

  let {
    data,
    logMarks = {},
    computedColumns = {},
    columnOrders = {},
    frameFilter = $bindable(null),
    testFilter = $bindable(null),
    rangeFilter = $bindable(null),
    isExpanded = $bindable(false),
    onMarkLog,
    onEntryClick,
  }: Props = $props();

  const COLLAPSED_LIMIT = 30;

  interface HistoryEntry {
    log_index: number;
    callSite: CallSite;
    valueGroup: ValueGroup;
  }

  // Filter and flatten all log entries
  let filteredEntries = $derived.by(() => {
    const entries: HistoryEntry[] = [];

    for (const callSite of data.call_sites) {
      for (const valueGroup of callSite.value_groups) {
        // Apply frame filter if active
        if (frameFilter) {
          if (!stackTraceContainsFrame(valueGroup.stack_trace_id, frameFilter)) continue;
        }

        // Apply test filter if active
        if (testFilter) {
          if (!logBelongsToTest(valueGroup.log_index, testFilter)) continue;
        }

        // Apply range filter if active
        if (rangeFilter) {
          if (valueGroup.log_index < rangeFilter.start || valueGroup.log_index > rangeFilter.end) continue;
        }

        entries.push({ log_index: valueGroup.log_index, callSite, valueGroup });
      }
    }

    entries.sort((a, b) => a.log_index - b.log_index);
    return entries;
  });

  let displayedEntries = $derived(
    isExpanded ? filteredEntries : filteredEntries.slice(0, COLLAPSED_LIMIT)
  );

  let hasMore = $derived(filteredEntries.length > COLLAPSED_LIMIT);

  function getCallSiteKey(callSite: CallSite): string {
    return `${callSite.filename}:${callSite.line}`;
  }

  function createFrameKey(filename: string, lineNumber: number, functionName: string): string {
    return `${filename}:${lineNumber}:${functionName}`;
  }

  function stackTraceContainsFrame(stackTraceId: string | undefined, frameKey: string): boolean {
    if (!stackTraceId) return false;
    const trace = data.stack_traces[stackTraceId];
    if (!trace) return false;
    return trace.frames.some(frame =>
      createFrameKey(frame.filename, frame.line_number, frame.function_name) === frameKey
    );
  }

  function logBelongsToTest(logIndex: number, testNodeid: string): boolean {
    if (!data.tests) return false;
    const test = data.tests.find(t => t.nodeid === testNodeid);
    if (!test) return false;
    if (test.start_log_index === undefined || test.end_log_index === undefined) return false;
    return logIndex >= test.start_log_index && logIndex <= test.end_log_index;
  }

  function getOrderedValues(valueGroup: ValueGroup, callSite: CallSite) {
    const callSiteKey = getCallSiteKey(callSite);
    const storedOrder = columnOrders[callSiteKey];
    const regularValues = valueGroup.values || [];

    if (!storedOrder) return regularValues;

    const valueMap = new Map(regularValues.map(v => [v.name, v]));
    const ordered = [];
    for (const name of storedOrder) {
      if (name.startsWith('computed:')) continue;
      const value = valueMap.get(name);
      if (value) {
        ordered.push(value);
        valueMap.delete(name);
      }
    }
    for (const value of valueMap.values()) {
      ordered.push(value);
    }
    return ordered;
  }

  // Mark handling
  const MARK_COLORS = [
    { name: "Red", value: "#fee2e2" },
    { name: "Orange", value: "#fed7aa" },
    { name: "Yellow", value: "#fef3c7" },
    { name: "Green", value: "#d1fae5" },
    { name: "Blue", value: "#dbeafe" },
    { name: "Purple", value: "#e9d5ff" },
    { name: "Pink", value: "#fce7f3" },
  ];

  let markNotes = $state<Record<number, string>>({});
  let menuOpenFor: number | null = $state(null);

  $effect(() => {
    const _ = logMarks;
    for (const logIndex in logMarks) {
      if (logMarks[logIndex].note && !markNotes[logIndex]) {
        markNotes[parseInt(logIndex)] = logMarks[logIndex].note;
      }
    }
  });

  function toggleMenu(logIndex: number, e: MouseEvent | KeyboardEvent) {
    e.stopPropagation();
    menuOpenFor = menuOpenFor === logIndex ? null : logIndex;
  }

  function handleMarkColor(logIndex: number, color: string) {
    const note = markNotes[logIndex] || logMarks[logIndex]?.note || "";
    onMarkLog?.(logIndex, color, note);
  }

  function handleMarkNote(logIndex: number, note: string) {
    markNotes[logIndex] = note;
  }

  function handleMarkNoteBlur(logIndex: number) {
    const color = logMarks[logIndex]?.color || "";
    const note = markNotes[logIndex] || "";
    onMarkLog?.(logIndex, color, note);
  }

  function handleClearMark(logIndex: number) {
    onMarkLog?.(logIndex, "", "");
    delete markNotes[logIndex];
    markNotes = { ...markNotes };
  }

  // Filter bar state
  let showFilterBar = $state(false);
  let rangeStartInput = $state("");
  let rangeEndInput = $state("");

  function applyRangeFilter() {
    const start = parseInt(rangeStartInput);
    const end = parseInt(rangeEndInput);
    if (!isNaN(start) && !isNaN(end) && start <= end) {
      rangeFilter = { start, end };
    }
  }

  function clearRangeFilter() {
    rangeFilter = null;
    rangeStartInput = "";
    rangeEndInput = "";
  }
</script>

<div class="history-cell">
  <div class="cell-header">
    <span class="entry-count">{filteredEntries.length} logs</span>
    <button class="filter-toggle" class:active={showFilterBar} onclick={() => showFilterBar = !showFilterBar}>
      Filters
      {#if testFilter || frameFilter || rangeFilter}
        <span class="filter-badge">
          {(testFilter ? 1 : 0) + (frameFilter ? 1 : 0) + (rangeFilter ? 1 : 0)}
        </span>
      {/if}
    </button>
  </div>

  {#if showFilterBar}
    <div class="filter-bar">
      <div class="filter-row">
        <label class="filter-label">Test:</label>
        <select
          class="filter-select"
          value={testFilter ?? ""}
          onchange={(e) => { testFilter = e.currentTarget.value || null; }}
        >
          <option value="">All tests</option>
          {#if data.tests}
            {#each data.tests as test}
              <option value={test.nodeid}>{test.nodeid}</option>
            {/each}
          {/if}
        </select>
        {#if testFilter}
          <button class="filter-clear" onclick={() => { testFilter = null; }}>&#10005;</button>
        {/if}
      </div>

      <div class="filter-row">
        <label class="filter-label">Range:</label>
        <input
          type="number"
          class="filter-input"
          placeholder="Start"
          bind:value={rangeStartInput}
          onchange={applyRangeFilter}
        />
        <span class="filter-separator">to</span>
        <input
          type="number"
          class="filter-input"
          placeholder="End"
          bind:value={rangeEndInput}
          onchange={applyRangeFilter}
        />
        {#if rangeFilter}
          <button class="filter-clear" onclick={clearRangeFilter}>&#10005;</button>
        {/if}
      </div>
    </div>
  {/if}

  <div class="log-list" class:expanded={isExpanded}>
    {#each displayedEntries as entry (entry.log_index)}
      {@const mark = logMarks[entry.log_index]}
      <div
        class="history-entry"
        class:clickable={entry.valueGroup.stack_trace_id !== undefined}
        class:menu-open={menuOpenFor === entry.log_index}
        style={mark?.color ? `background-color: ${mark.color};` : ""}
        onclick={() => onEntryClick?.(entry.log_index, entry.valueGroup.stack_trace_id)}
      >
        <span class="log-number">#{entry.log_index}</span>

        <div class="entry-content">
          {#if entry.valueGroup.dashboard_type}
            <div class="dashboard-entry">
              <span class="dashboard-label">{entry.valueGroup.dashboard_type}:</span>
              {#if entry.valueGroup.value !== undefined}
                <TreeView value={entry.valueGroup.value} />
              {:else if entry.valueGroup.event_name}
                <span class="dashboard-text">{entry.valueGroup.event_name}</span>
              {:else if entry.valueGroup.message}
                <span class="dashboard-text">{entry.valueGroup.message}</span>
              {/if}
            </div>
          {:else if entry.valueGroup.values && entry.valueGroup.values.length === 0 && entry.valueGroup.name}
            <span class="log-name-inline">{entry.valueGroup.name}</span>
          {:else if entry.valueGroup.values}
            {#if entry.valueGroup.name}
              <span class="log-name-inline">{entry.valueGroup.name}</span>
            {/if}
            {#each getOrderedValues(entry.valueGroup, entry.callSite) as valueWithName}
              <span class="value-item" title={valueWithName.name || ''}>
                {#if valueWithName.name}
                  <span class="value-label">{valueWithName.name}:</span>
                {/if}
                <TreeView value={valueWithName.value} />
              </span>
            {/each}
          {/if}
        </div>

        {#if mark?.note}
          <div class="mark-note-display" title={mark.note}>
            {mark.note}
          </div>
        {/if}

        <div class="entry-menu-container">
          <button
            class="menu-button"
            onclick={(e) => toggleMenu(entry.log_index, e)}
            title="Menu"
          >
            &#8943;
          </button>
          {#if menuOpenFor === entry.log_index}
            <div class="menu-dropdown" onclick={(e) => e.stopPropagation()}>
              <div class="menu-section">
                <div class="menu-section-title">Mark</div>
                <div class="mark-colors">
                  {#each MARK_COLORS as markColor}
                    <button
                      class="mark-color-button"
                      style="background-color: {markColor.value};"
                      title={markColor.name}
                      class:selected={logMarks[entry.log_index]?.color === markColor.value}
                      onclick={(e) => {
                        e.stopPropagation();
                        handleMarkColor(entry.log_index, markColor.value);
                      }}
                    >
                      {#if logMarks[entry.log_index]?.color === markColor.value}
                        &#10003;
                      {/if}
                    </button>
                  {/each}
                  {#if logMarks[entry.log_index]?.color}
                    <button
                      class="mark-clear-button"
                      title="Clear mark"
                      onclick={(e) => {
                        e.stopPropagation();
                        handleClearMark(entry.log_index);
                      }}
                    >
                      &#10005;
                    </button>
                  {/if}
                </div>
                <input
                  type="text"
                  class="mark-note-input"
                  placeholder="Add note..."
                  value={markNotes[entry.log_index] || ""}
                  oninput={(e) => handleMarkNote(entry.log_index, e.currentTarget.value)}
                  onblur={() => handleMarkNoteBlur(entry.log_index)}
                  onclick={(e) => e.stopPropagation()}
                />
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/each}
  </div>

  {#if hasMore}
    <div class="expand-bar">
      <button class="expand-button" onclick={() => isExpanded = !isExpanded}>
        {#if isExpanded}
          Collapse ({filteredEntries.length} total)
        {:else}
          Show all ({filteredEntries.length - COLLAPSED_LIMIT} more)
        {/if}
      </button>
    </div>
  {/if}
</div>

<style>
  .history-cell {
    display: flex;
    flex-direction: column;
  }

  .cell-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.35rem 0.75rem;
    border-bottom: 1px solid #e5e7eb;
  }

  .entry-count {
    font-size: 0.8rem;
    color: #64748b;
  }

  .filter-toggle {
    background: none;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    padding: 0.2rem 0.6rem;
    font-size: 0.8rem;
    color: #64748b;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.3rem;
  }

  .filter-toggle:hover, .filter-toggle.active {
    border-color: #2563eb;
    color: #2563eb;
  }

  .filter-badge {
    background: #2563eb;
    color: #fff;
    border-radius: 999px;
    font-size: 0.65rem;
    padding: 0 0.35rem;
    line-height: 1.3;
    font-weight: 600;
  }

  .filter-bar {
    padding: 0.5rem 0.75rem;
    background: #f9fafb;
    border-bottom: 1px solid #e5e7eb;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .filter-row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .filter-label {
    font-size: 0.8rem;
    color: #64748b;
    min-width: 3rem;
    font-weight: 500;
  }

  .filter-select {
    flex: 1;
    padding: 0.2rem 0.4rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.8rem;
    min-width: 0;
  }

  .filter-input {
    width: 5rem;
    padding: 0.2rem 0.4rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.8rem;
  }

  .filter-separator {
    font-size: 0.8rem;
    color: #94a3b8;
  }

  .filter-clear {
    background: none;
    border: none;
    color: #94a3b8;
    cursor: pointer;
    padding: 0.1rem 0.3rem;
    font-size: 0.8rem;
  }

  .filter-clear:hover {
    color: #dc2626;
  }

  .log-list {
    max-height: 300px;
    overflow-y: auto;
    padding: 0.25rem;
    display: flex;
    flex-direction: column;
    gap: 1px;
    scrollbar-width: thin;
  }

  .log-list.expanded {
    max-height: none;
  }

  .history-entry {
    border: 1px solid #e5e5e5;
    border-radius: 6px;
    padding: 0.4rem 0.6rem;
    background: #ffffff;
    transition: border-color 0.2s, background-color 0.2s;
    position: relative;
    display: flex;
    flex-direction: row;
    align-items: flex-start;
    gap: 0.5rem;
    flex-wrap: nowrap;
  }

  .history-entry.clickable {
    cursor: pointer;
  }

  .history-entry.menu-open {
    z-index: 100;
  }

  .history-entry:hover {
    border-color: #2563eb;
  }

  .history-entry > * {
    position: relative;
    z-index: 2;
  }

  .entry-content {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-direction: row;
    align-items: flex-start;
    gap: 0.5rem;
    flex-wrap: nowrap;
    overflow-x: auto;
  }

  .log-number {
    font-weight: 600;
    color: #2563eb;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    background: #eff6ff;
    border-radius: 3px;
    padding: 2px 6px;
    flex-shrink: 0;
    align-self: flex-start;
  }

  .log-name-inline {
    color: #881391;
    font-size: 0.9rem;
    font-weight: 600;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    align-self: center;
    margin-right: 0.25rem;
  }

  .value-item {
    flex: 0 0 auto;
    min-width: 0;
    padding: 2px;
    background: none;
    border: 1px solid transparent;
    border-radius: 3px;
    overflow-x: visible;
    white-space: nowrap;
    display: inline-flex;
    flex-direction: row;
    gap: 0;
    align-items: center;
    transition: border-color 0.15s ease;
  }

  .value-item:hover {
    border-color: #cbd5e1;
    background: #f8fafc;
  }

  .value-label {
    display: none;
  }

  .dashboard-entry {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.25rem 0.5rem;
    background: #f0f9ff;
    border: 1px solid #bae6fd;
    border-radius: 4px;
  }

  .dashboard-label {
    font-weight: 600;
    color: #0369a1;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    font-size: 0.85rem;
  }

  .dashboard-text {
    color: #0369a1;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    font-size: 0.85rem;
  }

  .mark-note-display {
    font-size: 0.85rem;
    color: #666;
    font-style: italic;
    padding: 0.25rem 0.5rem;
    background: rgba(255, 255, 255, 0.7);
    border-radius: 3px;
    margin-left: auto;
    flex-shrink: 0;
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .entry-menu-container {
    flex-shrink: 0;
    position: relative;
    align-self: flex-start;
    z-index: 20;
  }

  .menu-button {
    background: none;
    border: none;
    font-size: 1.2rem;
    color: #666;
    cursor: pointer;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    transition: background-color 0.2s;
    line-height: 1;
  }

  .menu-button:hover {
    background-color: #f0f0f0;
  }

  .menu-dropdown {
    position: absolute;
    right: 0;
    top: 100%;
    margin-top: 0.25rem;
    background: white;
    border: 1px solid #e5e5e5;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    z-index: 10;
    min-width: 200px;
  }

  .menu-section {
    padding: 0.5rem 0.75rem;
  }

  .menu-section-title {
    font-size: 0.75rem;
    font-weight: 600;
    color: #666;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
  }

  .mark-colors {
    display: flex;
    gap: 0.25rem;
    flex-wrap: wrap;
    margin-bottom: 0.5rem;
  }

  .mark-color-button {
    width: 2rem;
    height: 2rem;
    border: 2px solid #d1d5db;
    border-radius: 4px;
    cursor: pointer;
    transition: border-color 0.2s, transform 0.1s;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.9rem;
    padding: 0;
  }

  .mark-color-button:hover {
    border-color: #9ca3af;
    transform: scale(1.05);
  }

  .mark-color-button.selected {
    border-color: #2563eb;
    border-width: 2px;
  }

  .mark-clear-button {
    width: 2rem;
    height: 2rem;
    border: 2px solid #d1d5db;
    border-radius: 4px;
    background: white;
    cursor: pointer;
    transition: background-color 0.2s, border-color 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.9rem;
    color: #666;
    padding: 0;
  }

  .mark-clear-button:hover {
    background-color: #fee2e2;
    border-color: #dc2626;
    color: #dc2626;
  }

  .mark-note-input {
    width: 100%;
    padding: 0.4rem 0.5rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.85rem;
    font-family: inherit;
  }

  .mark-note-input:focus {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
  }

  .expand-bar {
    padding: 0.4rem;
    text-align: center;
    border-top: 1px solid #e5e7eb;
  }

  .expand-button {
    background: none;
    border: none;
    color: #2563eb;
    cursor: pointer;
    font-size: 0.8rem;
    padding: 0.2rem 0.6rem;
  }

  .expand-button:hover {
    text-decoration: underline;
  }
</style>
