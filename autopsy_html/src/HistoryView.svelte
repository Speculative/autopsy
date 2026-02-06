<script lang="ts">
  import type { AutopsyData, CallSite, ValueGroup, ComputedColumn, LogMark } from "./types";
  import type { EvaluationResult } from "./computedColumns";
  import TreeView from "./TreeView.svelte";
  import CodeLocation from "./CodeLocation.svelte";
  import { tick } from "svelte";
  import { evaluateComputedColumnBatch, getComputedColumnDisplayName } from "./computedColumns";
  import { isVSCodeWebview, navigateToLogInVSCode } from "./vscodeApi";
  import { FileCodeCorner, Table } from "lucide-svelte";

  interface Props {
    data: AutopsyData;
    highlightedLogIndex?: number | null;
    selectedLogIndex?: number | null;
    hiddenCallSites?: Set<string>;
    showDashboardCalls?: boolean;
    activeTab?: "streams" | "history" | "dashboard";
    frameFilter?: string | null;
    testFilter?: string | null;
    rangeFilter?: { start: number; end: number } | null;
    hoveredFrameKey?: string | null;
    selectedFrameKeys?: Set<string>;
    columnOrders?: Record<string, string[]>;
    computedColumns?: Record<string, ComputedColumn[]>;
    logMarks?: Record<number, LogMark>;
    hideSkippedLogs?: boolean;
    onShowInStream?: (logIndex: number) => void;
    onEntryClick?: (logIndex: number, stackTraceId?: string) => void;
    onHideCallSite?: (callSiteKey: string) => void;
    onToggleShowDashboard?: (show: boolean) => void;
    onMarkLog?: (logIndex: number, color: string, note: string) => void;
  }

  let {
    data,
    highlightedLogIndex = null,
    selectedLogIndex = null,
    hiddenCallSites = new Set<string>(),
    showDashboardCalls = true,
    activeTab = "history",
    frameFilter = null,
    testFilter = null,
    rangeFilter = null,
    hoveredFrameKey = null,
    selectedFrameKeys = new Set<string>(),
    columnOrders = {},
    computedColumns = {},
    logMarks = {},
    hideSkippedLogs = $bindable(false),
    onShowInStream,
    onEntryClick,
    onHideCallSite,
    onToggleShowDashboard,
    onMarkLog,
  }: Props = $props();

  let showCodeLocations = $state(false);

  // Cache for computed column values (callSiteKey:columnId -> log_index -> value)
  let computedColumnCache = $state<Map<string, Map<number, EvaluationResult>>>(new Map());

  // Pre-compute all computed columns when data or columns change
  $effect(() => {
    // Trigger reactivity on data and computedColumns
    const _ = [data, computedColumns];

    // Async function to recompute all computed columns
    (async () => {
      const newCache = new Map<string, Map<number, EvaluationResult>>();

      for (const callSite of data.call_sites) {
        const callSiteKey = getCallSiteKey(callSite);
        const columns = computedColumns[callSiteKey] || [];

        for (const column of columns) {
          const cacheKey = `${callSiteKey}:${column.id}`;

          try {
            // Batch evaluate Python
            const results = await evaluateComputedColumnBatch(
              column.expression,
              callSite.value_groups,
              data
            );

            const resultMap = new Map<number, EvaluationResult>();
            callSite.value_groups.forEach((vg, i) => {
              resultMap.set(vg.log_index, results[i]);
            });
            newCache.set(cacheKey, resultMap);
          } catch (error) {
            console.error(`Error evaluating computed column ${column.id}:`, error);
          }
        }
      }

      computedColumnCache = newCache;
    })();
  });

  // Create a flattened list of all log entries with their context
  interface HistoryEntry {
    log_index: number;
    callSite: CallSite;
    valueGroup: ValueGroup;
  }

  let historyEntries = $derived.by(() => {
    // Collect all entries (both visible and hidden) with their metadata
    interface EntryWithMetadata {
      log_index: number;
      callSite: CallSite;
      valueGroup: ValueGroup;
      isHidden: boolean;
    }

    const allEntries: EntryWithMetadata[] = [];

    for (const callSite of data.call_sites) {
      const callSiteKey = getCallSiteKey(callSite);
      const isDashboard = callSite.is_dashboard ?? false;
      // Dashboard call sites are hidden if explicitly hidden OR if showDashboardCalls is false
      const isHidden = hiddenCallSites.has(callSiteKey) || (isDashboard && !showDashboardCalls);

      for (const valueGroup of callSite.value_groups) {
        // Apply frame filter if active
        let matchesFrameFilter = true;
        if (frameFilter) {
          matchesFrameFilter = stackTraceContainsFrame(valueGroup.stack_trace_id, frameFilter);
        }

        // Apply test filter if active
        let matchesTestFilter = true;
        if (testFilter) {
          matchesTestFilter = logBelongsToTest(valueGroup.log_index, testFilter);
        }

        // Apply range filter if active
        let matchesRangeFilter = true;
        if (rangeFilter) {
          matchesRangeFilter = valueGroup.log_index >= rangeFilter.start && valueGroup.log_index <= rangeFilter.end;
        }

        // Entry is hidden if it's explicitly hidden OR doesn't match frame filter OR doesn't match test filter OR doesn't match range filter
        const entryIsHidden = isHidden || !matchesFrameFilter || !matchesTestFilter || !matchesRangeFilter;

        allEntries.push({
          log_index: valueGroup.log_index,
          callSite,
          valueGroup,
          isHidden: entryIsHidden,
        });
      }
    }

    // Sort by log_index to get chronological order
    allEntries.sort((a, b) => a.log_index - b.log_index);

    // Build result with skip markers (combining consecutive hidden entries)
    const result: (HistoryEntry | { type: "skip"; count: number; entries: HistoryEntry[] })[] = [];
    let hiddenEntries: HistoryEntry[] = [];

    for (const entry of allEntries) {
      if (entry.isHidden) {
        // Accumulate hidden entries (from any call site)
        hiddenEntries.push({
          log_index: entry.log_index,
          callSite: entry.callSite,
          valueGroup: entry.valueGroup,
        });
      } else {
        // Visible entry - insert combined skip marker for any pending hidden entries
        if (hiddenEntries.length > 0) {
          result.push({
            type: "skip",
            count: hiddenEntries.length,
            entries: hiddenEntries,
          });
          hiddenEntries = [];
        }
        // Add visible entry
        result.push({
          log_index: entry.log_index,
          callSite: entry.callSite,
          valueGroup: entry.valueGroup,
        });
      }
    }

    // Add final skip marker if there are hidden entries at the end
    if (hiddenEntries.length > 0) {
      result.push({
        type: "skip",
        count: hiddenEntries.length,
        entries: hiddenEntries,
      });
    }

    return result;
  });

  function getFilename(callSite: CallSite): string {
    const parts = callSite.filename.split("/");
    return parts[parts.length - 1];
  }

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

  // Check if a log should be highlighted based on frame context
  function shouldHighlightForFrameContext(stackTraceId: string | undefined): boolean {
    if (hoveredFrameKey && stackTraceContainsFrame(stackTraceId, hoveredFrameKey)) {
      return true;
    }
    for (const selectedKey of selectedFrameKeys) {
      if (stackTraceContainsFrame(stackTraceId, selectedKey)) {
        return true;
      }
    }
    return false;
  }

  // Get ordered values for a value group based on column order
  function getOrderedValues(valueGroup: ValueGroup, callSite: CallSite) {
    const callSiteKey = getCallSiteKey(callSite);
    const storedOrder = columnOrders[callSiteKey];

    // Start with regular values
    const regularValues = valueGroup.values || [];

    if (!storedOrder) {
      // No stored order, return regular values plus computed columns
      const computed = computedColumns[callSiteKey] || [];
      const computedValues = computed.map(col => {
        const cacheKey = `${callSiteKey}:${col.id}`;
        const cachedResults = computedColumnCache.get(cacheKey);
        const result = cachedResults?.get(valueGroup.log_index) || { value: undefined };
        return {
          name: getComputedColumnDisplayName(col),
          value: result.error ? { __error: result.error } : result.value
        };
      });
      return [...regularValues, ...computedValues];
    }

    // Create a map for regular values
    const valueMap = new Map(regularValues.map(v => [v.name, v]));

    // Create a map for computed values
    const computed = computedColumns[callSiteKey] || [];
    const computedMap = new Map(
      computed.map(col => {
        const cacheKey = `${callSiteKey}:${col.id}`;
        const cachedResults = computedColumnCache.get(cacheKey);
        const result = cachedResults?.get(valueGroup.log_index) || { value: undefined };
        return [
          `computed:${col.id}`,
          {
            name: getComputedColumnDisplayName(col),
            value: result.error ? { __error: result.error } : result.value
          }
        ];
      })
    );

    // Order according to stored order (including computed columns)
    const ordered = [];
    for (const name of storedOrder) {
      if (name.startsWith('computed:')) {
        const computedValue = computedMap.get(name);
        if (computedValue) {
          ordered.push(computedValue);
          computedMap.delete(name);
        }
      } else {
        const value = valueMap.get(name);
        if (value) {
          ordered.push(value);
          valueMap.delete(name);
        }
      }
    }

    // Add remaining regular values (not in stored order)
    for (const value of valueMap.values()) {
      ordered.push(value);
    }

    // Add remaining computed values (not in stored order)
    for (const value of computedMap.values()) {
      ordered.push(value);
    }

    return ordered;
  }

  function handleEntryClick(entry: HistoryEntry) {
    onEntryClick?.(entry.log_index, entry.valueGroup.stack_trace_id);
  }

  function handleHideCallSite(callSite: CallSite) {
    const key = getCallSiteKey(callSite);
    onHideCallSite?.(key);
  }

  let menuOpenFor: number | null = $state(null);
  let expandedSkipMarkers = $state<Set<number>>(new Set());
  let lastProcessedLogIndex: number | null = $state(null);

  // Mark colors available for selection
  const MARK_COLORS = [
    { name: "Red", value: "#fee2e2" },
    { name: "Orange", value: "#fed7aa" },
    { name: "Yellow", value: "#fef3c7" },
    { name: "Green", value: "#d1fae5" },
    { name: "Blue", value: "#dbeafe" },
    { name: "Purple", value: "#e9d5ff" },
    { name: "Pink", value: "#fce7f3" },
  ];

  // Track note input for each log
  let markNotes = $state<Record<number, string>>({});

  function toggleMenu(logIndex: number, e: MouseEvent | KeyboardEvent) {
    e.stopPropagation();
    menuOpenFor = menuOpenFor === logIndex ? null : logIndex;
  }

  function closeMenu() {
    menuOpenFor = null;
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

  // Initialize markNotes from logMarks
  $effect(() => {
    const _ = logMarks;
    for (const logIndex in logMarks) {
      if (logMarks[logIndex].note && !markNotes[logIndex]) {
        markNotes[logIndex] = logMarks[logIndex].note;
      }
    }
  });

  function toggleSkipMarker(index: number) {
    if (expandedSkipMarkers.has(index)) {
      expandedSkipMarkers.delete(index);
      expandedSkipMarkers = new Set(expandedSkipMarkers);
    } else {
      expandedSkipMarkers.add(index);
      expandedSkipMarkers = new Set(expandedSkipMarkers);
    }
  }

  function isSkipMarkerExpanded(index: number): boolean {
    return expandedSkipMarkers.has(index);
  }

  // Effect to scroll to and highlight the entry when highlightedLogIndex changes
  $effect(() => {
    if (highlightedLogIndex !== null && highlightedLogIndex !== lastProcessedLogIndex) {
      lastProcessedLogIndex = highlightedLogIndex;
      
      // Capture the current historyEntries to avoid reactivity issues
      const entries = historyEntries;
      
      // Find which skip marker (if any) contains this log index
      let skipMarkerIndex: number | null = null;
      let entryIndex = 0;
      for (const item of entries) {
        if ("type" in item && item.type === "skip") {
          const containsLogIndex = item.entries.some(
            (e) => e.log_index === highlightedLogIndex
          );
          if (containsLogIndex) {
            skipMarkerIndex = entryIndex;
            break;
          }
        }
        entryIndex++;
      }

      // If the log index is in a skipped section, expand it
      // Only expand if not already expanded to avoid unnecessary state updates
      if (skipMarkerIndex !== null && !expandedSkipMarkers.has(skipMarkerIndex)) {
        const newSet = new Set(expandedSkipMarkers);
        newSet.add(skipMarkerIndex);
        expandedSkipMarkers = newSet;
      }

      // Wait for the DOM to update
      tick().then(() => {
        const element = document.querySelector(
          `[data-log-index="${highlightedLogIndex}"]`
        );
        if (element) {
          element.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      });
    } else if (highlightedLogIndex === null) {
      // Reset when highlight is cleared
      lastProcessedLogIndex = null;
    }
  });

  // Close menu when clicking outside
  $effect(() => {
    if (menuOpenFor !== null) {
      const handler = (e: MouseEvent) => {
        if (!(e.target as Element)?.closest(".entry-menu-container")) {
          closeMenu();
        }
      };
      document.addEventListener("click", handler);
      return () => document.removeEventListener("click", handler);
    }
  });

</script>

{#if historyEntries.length === 0}
  <p class="empty">No report data available.</p>
{:else}
  <div class="history-header">
    <label class="header-checkbox">
      <input
        type="checkbox"
        checked={showDashboardCalls}
        onchange={(e) => onToggleShowDashboard?.(e.currentTarget.checked)}
      />
      <span>Show dashboard calls</span>
    </label>
    <label class="header-checkbox">
      <input
        type="checkbox"
        checked={hideSkippedLogs}
        onchange={(e) => hideSkippedLogs = e.currentTarget.checked}
      />
      <span>Hide skipped logs</span>
    </label>
    <label class="header-checkbox">
      <input
        type="checkbox"
        checked={showCodeLocations}
        onchange={(e) => showCodeLocations = e.currentTarget.checked}
      />
      <span>Show code locations</span>
    </label>
  </div>
  <div class="history">
    {#each historyEntries as item, index}
      {#if "type" in item && item.type === "skip"}
        {#if !hideSkippedLogs}
          {@const isExpanded = isSkipMarkerExpanded(index)}
          <div class="skip-marker-wrapper">
            <div
              class="skip-marker"
              class:expanded={isExpanded}
              role="button"
              tabindex="0"
              onclick={() => toggleSkipMarker(index)}
              onkeydown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  toggleSkipMarker(index);
                }
              }}
              aria-label="{item.count} entries skipped, click to {isExpanded ? 'collapse' : 'expand'}"
              title="{item.count} {item.count === 1 ? 'log' : 'logs'} skipped"
            >
              +{item.count}
            </div>
            {#if isExpanded}
              <div class="skip-marker-container">
                {#each item.entries as skippedEntry}
                  {@const skippedCallSiteKey = getCallSiteKey(skippedEntry.callSite)}
                  {@const skippedMark = logMarks[skippedEntry.log_index]}
                  {@const skippedFrameContextHighlight = shouldHighlightForFrameContext(skippedEntry.valueGroup.stack_trace_id)}
                  <div
                    class="history-entry skipped-entry"
                    class:highlighted={highlightedLogIndex === skippedEntry.log_index}
                    class:selected={selectedLogIndex === skippedEntry.log_index}
                    class:frame-context-highlight={skippedFrameContextHighlight}
                    class:clickable={skippedEntry.valueGroup.stack_trace_id !== undefined}
                    class:menu-open={menuOpenFor === skippedEntry.log_index}
                    data-log-index={skippedEntry.log_index}
                    style={skippedMark?.color ? `background-color: ${skippedMark.color};` : ""}
                    onclick={() => handleEntryClick(skippedEntry)}
                  >
                    <span class="log-number">#{skippedEntry.log_index}</span>

                    <button
                      class="nav-button"
                      onclick={(e) => {
                        e.stopPropagation();
                        onShowInStream?.(skippedEntry.log_index);
                      }}
                      title="Jump to Stream"
                    >
                      <Table size={14} />
                    </button>

                    {#if isVSCodeWebview()}
                      <button
                        class="nav-button"
                        onclick={(e) => {
                          e.stopPropagation();
                          navigateToLogInVSCode(skippedEntry.log_index);
                        }}
                        title="Navigate to code location"
                      >
                        <FileCodeCorner size={14} />
                      </button>
                    {/if}

                    <div class="entry-content">
                      {#if showCodeLocations}
                        <CodeLocation
                          filename={skippedEntry.callSite.filename}
                          line={skippedEntry.callSite.line}
                          functionName={skippedEntry.valueGroup.function_name}
                          className={skippedEntry.valueGroup.class_name}
                          compact={true}
                        />
                      {/if}
                      {#if skippedEntry.valueGroup.dashboard_type}
                        <div class="dashboard-entry">
                          {#if skippedEntry.valueGroup.dashboard_type === "count"}
                            <span class="dashboard-label">count:</span>
                            <TreeView value={skippedEntry.valueGroup.value} />
                          {:else if skippedEntry.valueGroup.dashboard_type === "hist"}
                            <span class="dashboard-label">hist:</span>
                            <TreeView value={skippedEntry.valueGroup.value} />
                          {:else if skippedEntry.valueGroup.dashboard_type === "timeline"}
                            <span class="dashboard-label">timeline:</span>
                            <span class="dashboard-text">{skippedEntry.valueGroup.event_name}</span>
                          {:else if skippedEntry.valueGroup.dashboard_type === "happened"}
                            <span class="dashboard-label">happened</span>
                            {#if skippedEntry.valueGroup.message}
                              <span class="dashboard-text">: {skippedEntry.valueGroup.message}</span>
                            {/if}
                          {/if}
                        </div>
                      {:else if skippedEntry.valueGroup.values && skippedEntry.valueGroup.values.length === 0 && skippedEntry.valueGroup.name}
                        <span class="log-name-inline">{skippedEntry.valueGroup.name}</span>
                      {:else if skippedEntry.valueGroup.values}
                        {#if skippedEntry.valueGroup.name}
                          <span class="log-name-inline">{skippedEntry.valueGroup.name}</span>
                        {/if}
                        {#each getOrderedValues(skippedEntry.valueGroup, skippedEntry.callSite) as valueWithName}
                          <span class="value-item" title={valueWithName.name || ''}>
                            {#if valueWithName.name}
                              <span class="value-label">{valueWithName.name}:</span>
                            {/if}
                            {#if typeof valueWithName.value === 'object' && valueWithName.value !== null && '__error' in valueWithName.value}
                              <span class="computed-error">{valueWithName.value.__error}</span>
                            {:else}
                              <TreeView value={valueWithName.value} />
                            {/if}
                          </span>
                        {/each}
                      {/if}
                    </div>

                    {#if skippedMark?.note}
                      <div class="mark-note-display" title={skippedMark.note}>
                        {skippedMark.note}
                      </div>
                    {/if}

                    <div class="entry-menu-container">
                      <button
                        class="menu-button"
                        onclick={(e) => toggleMenu(skippedEntry.log_index, e)}
                        onkeydown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            toggleMenu(skippedEntry.log_index, e);
                          }
                        }}
                        title="Menu"
                      >
                        ⋯
                      </button>
                      {#if menuOpenFor === skippedEntry.log_index}
                        <div class="menu-dropdown" onclick={(e) => e.stopPropagation()}>
                          <div class="menu-section">
                            <div class="menu-section-title">Mark</div>
                            <div class="mark-colors">
                              {#each MARK_COLORS as markColor}
                                <button
                                  class="mark-color-button"
                                  style="background-color: {markColor.value};"
                                  title={markColor.name}
                                  class:selected={logMarks[skippedEntry.log_index]?.color === markColor.value}
                                  onclick={(e) => {
                                    e.stopPropagation();
                                    handleMarkColor(skippedEntry.log_index, markColor.value);
                                  }}
                                >
                                  {#if logMarks[skippedEntry.log_index]?.color === markColor.value}
                                    ✓
                                  {/if}
                                </button>
                              {/each}
                              {#if logMarks[skippedEntry.log_index]?.color}
                                <button
                                  class="mark-clear-button"
                                  title="Clear mark"
                                  onclick={(e) => {
                                    e.stopPropagation();
                                    handleClearMark(skippedEntry.log_index);
                                  }}
                                >
                                  ✕
                                </button>
                              {/if}
                            </div>
                            <input
                              type="text"
                              class="mark-note-input"
                              placeholder="Add note..."
                              value={markNotes[skippedEntry.log_index] || ""}
                              oninput={(e) => handleMarkNote(skippedEntry.log_index, e.currentTarget.value)}
                              onblur={() => handleMarkNoteBlur(skippedEntry.log_index)}
                              onclick={(e) => e.stopPropagation()}
                            />
                          </div>
                          <div class="menu-divider"></div>
                          <button
                            class="menu-item"
                            onclick={(e) => {
                              e.stopPropagation();
                              handleHideCallSite(skippedEntry.callSite);
                              closeMenu();
                            }}
                          >
                            Hide {skippedEntry.callSite.value_groups.length} {skippedEntry.callSite.value_groups.length === 1 ? "log" : "logs"} like this
                          </button>
                        </div>
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {/if}
      {:else}
        {@const entry = item as HistoryEntry}
        {@const callSiteKey = getCallSiteKey(entry.callSite)}
        {@const mark = logMarks[entry.log_index]}
        {@const frameContextHighlight = shouldHighlightForFrameContext(entry.valueGroup.stack_trace_id)}
        <div
          class="history-entry"
          class:highlighted={highlightedLogIndex === entry.log_index}
          class:selected={selectedLogIndex === entry.log_index}
          class:frame-context-highlight={frameContextHighlight}
          class:clickable={entry.valueGroup.stack_trace_id !== undefined}
          class:menu-open={menuOpenFor === entry.log_index}
          data-log-index={entry.log_index}
          style={mark?.color ? `background-color: ${mark.color};` : ""}
          draggable="true"
          ondragstart={(e) => {
            if (e.dataTransfer) {
              e.dataTransfer.setData("text/log-index", entry.log_index.toString());
              e.dataTransfer.effectAllowed = "copy";
            }
          }}
          onclick={() => handleEntryClick(entry)}
        >
          <span class="log-number">#{entry.log_index}</span>

          <button
            class="nav-button"
            onclick={(e) => {
              e.stopPropagation();
              onShowInStream?.(entry.log_index);
            }}
            title="Jump to Stream"
          >
            <Table size={14} />
          </button>

          {#if isVSCodeWebview()}
            <button
              class="nav-button"
              onclick={(e) => {
                e.stopPropagation();
                navigateToLogInVSCode(entry.log_index);
              }}
              title="Navigate to code location"
            >
              <FileCodeCorner size={14} />
            </button>
          {/if}

          <div class="entry-content">
            {#if showCodeLocations}
              <CodeLocation
                filename={entry.callSite.filename}
                line={entry.callSite.line}
                functionName={entry.valueGroup.function_name}
                className={entry.valueGroup.class_name}
                compact={true}
              />
            {/if}
            {#if entry.valueGroup.dashboard_type}
              <div class="dashboard-entry">
                {#if entry.valueGroup.dashboard_type === "count"}
                  <span class="dashboard-label">count:</span>
                  <TreeView value={entry.valueGroup.value} />
                {:else if entry.valueGroup.dashboard_type === "hist"}
                  <span class="dashboard-label">hist:</span>
                  <TreeView value={entry.valueGroup.value} />
                {:else if entry.valueGroup.dashboard_type === "timeline"}
                  <span class="dashboard-label">timeline:</span>
                  <span class="dashboard-text">{entry.valueGroup.event_name}</span>
                {:else if entry.valueGroup.dashboard_type === "happened"}
                  <span class="dashboard-label">happened</span>
                  {#if entry.valueGroup.message}
                    <span class="dashboard-text">: {entry.valueGroup.message}</span>
                  {/if}
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
                  {#if typeof valueWithName.value === 'object' && valueWithName.value !== null && '__error' in valueWithName.value}
                    <span class="computed-error">{valueWithName.value.__error}</span>
                  {:else}
                    <TreeView value={valueWithName.value} />
                  {/if}
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
              onkeydown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  toggleMenu(entry.log_index, e);
                }
              }}
              title="Menu"
            >
              ⋯
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
                          ✓
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
                        ✕
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
                <div class="menu-divider"></div>
                <button
                  class="menu-item"
                  onclick={(e) => {
                    e.stopPropagation();
                    handleHideCallSite(entry.callSite);
                    closeMenu();
                  }}
                >
                  Hide {entry.callSite.value_groups.length} {entry.callSite.value_groups.length === 1 ? "log" : "logs"} like this
                </button>
              </div>
            {/if}
          </div>
        </div>
      {/if}
    {/each}
  </div>
{/if}

<style>
  .empty {
    text-align: center;
    color: #666;
    padding: 3rem;
  }

  .history-header {
    margin-bottom: 0.5rem;
    padding: 0.4rem 0.6rem;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    display: flex;
    gap: 1.5rem;
    flex-wrap: wrap;
  }

  .header-checkbox {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    font-size: 0.9rem;
    color: #333;
  }

  .header-checkbox input[type="checkbox"] {
    cursor: pointer;
  }

  .history {
    display: flex;
    flex-direction: column;
    gap: 0;
    margin-left: 2rem;
    position: relative;
  }

  .history-entry {
    border: 1px solid #e5e5e5;
    border-radius: 6px;
    padding: 0.4rem 0.6rem;
    background: #ffffff;
    background-color: #ffffff;
    transition: border-color 0.2s, background-color 0.2s;
    position: relative;
    display: flex;
    flex-direction: row;
    align-items: flex-start;
    gap: 0.5rem;
    flex-wrap: wrap;
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

  .history-entry.highlighted {
    position: relative;
    border-color: #2563eb;
  }

  .history-entry.highlighted::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    border-radius: 6px;
    pointer-events: none;
    animation: highlight-pulse 2s ease-in-out;
    z-index: 1;
  }

  .history-entry.selected {
    background: #eff6ff;
    border-color: #2563eb;
  }

  .history-entry.selected:hover {
    background: #dbeafe;
  }

  .history-entry.frame-context-highlight {
    background: #fef3c7;
    border-color: #f59e0b;
  }

  .history-entry.frame-context-highlight:hover {
    background: #fde68a;
  }

  .history-entry.frame-context-highlight.selected {
    background: #fde68a;
    border-color: #f59e0b;
  }

  @keyframes highlight-pulse {
    0% {
      background-color: rgba(219, 234, 254, 0);
      box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.4);
    }
    10% {
      background-color: rgba(219, 234, 254, 1);
      box-shadow: 0 0 0 8px rgba(37, 99, 235, 0);
    }
    30% {
      background-color: rgba(191, 219, 254, 1);
    }
    100% {
      background-color: rgba(219, 234, 254, 0);
      box-shadow: 0 0 0 0 rgba(37, 99, 235, 0);
    }
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
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    align-items: flex-start;
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

  .menu-item {
    display: block;
    width: 100%;
    padding: 0.5rem 0.75rem;
    background: none;
    border: none;
    text-align: left;
    cursor: pointer;
    font-size: 0.85rem;
    color: #333;
    transition: background-color 0.2s;
  }

  .menu-item:hover {
    background-color: #f8fafc;
  }

  .skip-marker-wrapper {
    position: relative;
  }

  .skip-marker {
    position: absolute;
    left: -2rem;
    top: 0;
    padding: 0.1rem 0.3rem;
    color: #999;
    font-size: 0.65rem;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    cursor: pointer;
    transition: background-color 0.2s, color 0.2s;
    border-radius: 3px;
    background: #f9fafb;
    border: 1px solid #d1d5db;
    user-select: none;
    z-index: 5;
  }

  .skip-marker:hover {
    background-color: #e5e7eb;
    color: #666;
  }

  .skip-marker:focus {
    outline: 2px solid #2563eb;
    outline-offset: 2px;
  }

  .skip-marker-container {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .skip-marker-container .history-entry {
    border: 2px dashed #d1d5db !important;
    opacity: 0.8;
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
    flex: 0 1 auto;
    min-width: 0;
    padding: 2px;
    background: none;
    border: 1px solid transparent;
    border-radius: 3px;
    overflow-x: visible;
    max-width: 100%;
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

  .computed-error {
    color: #dc2626;
    font-style: italic;
    font-size: 0.85rem;
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

  .menu-divider {
    height: 1px;
    background: #e5e5e5;
    margin: 0.25rem 0;
  }

  .nav-button {
    background: none;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    padding: 2px 6px;
    cursor: pointer;
    opacity: 0.7;
    transition: opacity 0.2s, border-color 0.2s;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #6b7280;
    flex-shrink: 0;
  }

  .nav-button:hover {
    opacity: 1;
    border-color: #3b82f6;
    color: #3b82f6;
  }
</style>
