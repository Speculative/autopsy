<script lang="ts">
  import type { AutopsyData, CallSite, ValueGroup, ComputedColumn } from "./types";
  import TreeView from "./TreeView.svelte";
  import CodeLocation from "./CodeLocation.svelte";
  import { tick } from "svelte";
  import { evaluateComputedColumn, getComputedColumnDisplayName } from "./computedColumns";

  interface Props {
    data: AutopsyData;
    highlightedLogIndex?: number | null;
    selectedLogIndex?: number | null;
    hiddenCallSites?: Set<string>;
    showDashboardCalls?: boolean;
    activeTab?: "streams" | "history" | "dashboard";
    frameFilter?: string | null;
    columnOrders?: Record<string, string[]>;
    computedColumns?: Record<string, ComputedColumn[]>;
    hideSkippedLogs?: boolean;
    onShowInStream?: (logIndex: number) => void;
    onEntryClick?: (logIndex: number, stackTraceId?: string) => void;
    onHideCallSite?: (callSiteKey: string) => void;
    onToggleShowDashboard?: (show: boolean) => void;
  }

  let {
    data,
    highlightedLogIndex = null,
    selectedLogIndex = null,
    hiddenCallSites = new Set<string>(),
    showDashboardCalls = true,
    activeTab = "history",
    frameFilter = null,
    columnOrders = {},
    computedColumns = {},
    hideSkippedLogs = $bindable(false),
    onShowInStream,
    onEntryClick,
    onHideCallSite,
    onToggleShowDashboard,
  }: Props = $props();

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
        
        // Entry is hidden if it's explicitly hidden OR doesn't match frame filter
        const entryIsHidden = isHidden || !matchesFrameFilter;
        
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
        const result = evaluateComputedColumn(col.expression, valueGroup, data);
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
        const result = evaluateComputedColumn(col.expression, valueGroup, data);
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

  let menuOpenFor: string | null = $state(null);
  let expandedSkipMarkers = $state<Set<number>>(new Set());
  let lastProcessedLogIndex: number | null = $state(null);

  function toggleMenu(callSiteKey: string, e: MouseEvent | KeyboardEvent) {
    e.stopPropagation();
    menuOpenFor = menuOpenFor === callSiteKey ? null : callSiteKey;
  }

  function closeMenu() {
    menuOpenFor = null;
  }

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
  </div>
  <div class="history">
    {#each historyEntries as item, index}
      {#if "type" in item && item.type === "skip"}
        {#if !hideSkippedLogs}
          {@const isExpanded = isSkipMarkerExpanded(index)}
          <div class="skip-marker-container">
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
            >
              <span class="skip-text">
                {isExpanded ? "▼" : "▶"} ...{item.count}{" "}
                {item.count === 1 ? "log" : "logs"} skipped
              </span>
            </div>
            {#if isExpanded}
              <div class="skipped-entries">
                {#each item.entries as skippedEntry}
                  <div
                    class="history-entry skipped-entry"
                    class:highlighted={highlightedLogIndex === skippedEntry.log_index}
                    class:selected={selectedLogIndex === skippedEntry.log_index}
                    class:clickable={skippedEntry.valueGroup.stack_trace_id !== undefined}
                    data-log-index={skippedEntry.log_index}
                    onclick={() => handleEntryClick(skippedEntry)}
                  >
                    <div class="entry-header">
                      <span
                        class="log-number clickable"
                        role="button"
                        tabindex="0"
                        onclick={(e) => {
                          e.stopPropagation();
                          onShowInStream?.(skippedEntry.log_index);
                        }}
                        onkeydown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            e.stopPropagation();
                            onShowInStream?.(skippedEntry.log_index);
                          }
                        }}
                        title="Show this log in the Streams view"
                      >
                        <span class="log-number-arrow">⬅️</span>
                        <span class="log-number-text">#{skippedEntry.log_index}</span>
                      </span>
                      <span class="location">
                        <span class="filename">{getFilename(skippedEntry.callSite)}</span>
                        <span class="separator">:</span>
                        <span class="line">{skippedEntry.callSite.line}</span>
                      </span>
                      <span class="separator">in</span>
                      <span class="function">
                        {#if skippedEntry.valueGroup.class_name}
                          {skippedEntry.valueGroup.class_name}.{skippedEntry.valueGroup.function_name}
                        {:else}
                          {skippedEntry.valueGroup.function_name}
                        {/if}
                      </span>
                    </div>
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
                      <div class="log-name-only">{skippedEntry.valueGroup.name}</div>
                    {:else if skippedEntry.valueGroup.values}
                      <div class="values">
                        {#if skippedEntry.valueGroup.name}
                          <span class="log-name-inline">{skippedEntry.valueGroup.name}</span>
                        {/if}
                        {#each getOrderedValues(skippedEntry.valueGroup, skippedEntry.callSite) as valueWithName}
                          <div class="value-item">
                            {#if valueWithName.name}
                              <div class="value-label">{valueWithName.name}:</div>
                            {/if}
                            {#if typeof valueWithName.value === 'object' && valueWithName.value !== null && '__error' in valueWithName.value}
                              <span class="computed-error">{valueWithName.value.__error}</span>
                            {:else}
                              <TreeView value={valueWithName.value} />
                            {/if}
                          </div>
                        {/each}
                      </div>
                    {/if}
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {/if}
      {:else}
        {@const entry = item as HistoryEntry}
        {@const callSiteKey = getCallSiteKey(entry.callSite)}
        <div
          class="history-entry"
          class:highlighted={highlightedLogIndex === entry.log_index}
          class:selected={selectedLogIndex === entry.log_index}
          class:clickable={entry.valueGroup.stack_trace_id !== undefined}
          data-log-index={entry.log_index}
          onclick={() => handleEntryClick(entry)}
        >
          <div class="entry-header">
            <span
              class="log-number clickable"
              role="button"
              tabindex="0"
              onclick={(e) => {
                e.stopPropagation();
                onShowInStream?.(entry.log_index);
              }}
              onkeydown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  e.stopPropagation();
                  onShowInStream?.(entry.log_index);
                }
              }}
              title="Show this log in the Streams view"
            >
              <span class="log-number-arrow">⬅️</span>
              <span class="log-number-text">#{entry.log_index}</span>
            </span>
            <CodeLocation
              filename={entry.callSite.filename}
              line={entry.callSite.line}
              functionName={entry.valueGroup.function_name}
              className={entry.valueGroup.class_name}
            />
            <div class="entry-menu-container">
              <button
                class="menu-button"
                onclick={(e) => toggleMenu(callSiteKey, e)}
                onkeydown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    toggleMenu(callSiteKey, e);
                  }
                }}
                title="Menu"
              >
                ⋯
              </button>
              {#if menuOpenFor === callSiteKey}
                <div class="menu-dropdown" onclick={(e) => e.stopPropagation()}>
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
            <div class="log-name-only">{entry.valueGroup.name}</div>
          {:else if entry.valueGroup.values}
            <div class="values">
              {#if entry.valueGroup.name}
                <span class="log-name-inline">{entry.valueGroup.name}</span>
              {/if}
              {#each getOrderedValues(entry.valueGroup, entry.callSite) as valueWithName}
                <div class="value-item">
                  {#if valueWithName.name}
                    <div class="value-label">{valueWithName.name}:</div>
                  {/if}
                  {#if typeof valueWithName.value === 'object' && valueWithName.value !== null && '__error' in valueWithName.value}
                    <span class="computed-error">{valueWithName.value.__error}</span>
                  {:else}
                    <TreeView value={valueWithName.value} />
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
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
    margin-bottom: 1rem;
    padding: 0.75rem;
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
    gap: 0.75rem;
  }

  .history-entry {
    border: 1px solid #e5e5e5;
    border-radius: 6px;
    padding: 0.75rem;
    background: white;
    transition: border-color 0.2s, background-color 0.2s;
    position: relative;
  }

  .history-entry.clickable {
    cursor: pointer;
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

  .entry-header {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
    position: relative;
    z-index: 3;
  }

  .entry-menu-container {
    margin-left: auto;
    position: relative;
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

  .skip-marker-container {
    margin: 0.5rem 0;
  }

  .skip-marker {
    text-align: center;
    padding: 0.5rem;
    color: #999;
    font-style: italic;
    font-size: 0.85rem;
    cursor: pointer;
    transition: background-color 0.2s, color 0.2s;
    border-radius: 4px;
  }

  .skip-marker:hover {
    background-color: #f3f4f6;
    color: #666;
  }

  .skip-marker:focus {
    outline: 2px solid #2563eb;
    outline-offset: 2px;
  }

  .skip-text {
    background: #f9fafb;
    padding: 0.25rem 0.75rem;
    border-radius: 4px;
    border: 1px dashed #d1d5db;
    display: inline-block;
  }

  .skipped-entries {
    margin-top: 0.5rem;
    margin-left: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .skipped-entry {
    border: 2px dashed #d1d5db !important;
    opacity: 0.8;
  }

  .dashboard-entry {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.5rem;
    padding: 0.5rem;
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
    width: 4rem;
  }

  .log-number.clickable {
    cursor: pointer;
    position: relative;
    transition: background 0.2s;
    overflow: hidden;
    display: flex;
  }

  .log-number.clickable:hover,
  .log-number.clickable:focus {
    background: #dbeafe;
    outline: 2px solid #2563eb;
    outline-offset: 2px;
  }

  .log-number-text,
  .log-number-arrow {
    display: inline-block;
    width: 100%;
    flex-shrink: 0;
    padding: 2px 6px;
    transition: transform 0.2s ease;
  }

  .log-number-arrow {
    color: #2563eb;
    font-weight: 600;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    font-size: 1.2em;
    text-align: center;
  }

  .log-number-text {
    transform: translateX(-100%);
  }

  .log-number-arrow {
    transform: translateX(-100%);
  }

  .log-number.clickable:hover .log-number-text,
  .log-number.clickable:focus .log-number-text {
    transform: translateX(0);
  }

  .log-number.clickable:hover .log-number-arrow,
  .log-number.clickable:focus .log-number-arrow {
    transform: translateX(0);
  }

  .location {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    color: #666;
  }

  .filename {
    font-weight: 500;
    color: #475569;
  }

  .separator {
    color: #64748b;
  }

  .line {
    color: #64748b;
  }

  .function {
    color: #64748b;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
  }

  .values {
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: flex-start;
  }

  .log-name-only {
    color: #881391;
    font-size: 1rem;
    font-weight: 500;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    margin-top: 0.25rem;
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
    padding: 0.5rem;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
    overflow-x: auto;
    max-width: 100%;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .value-label {
    font-weight: 400;
    color: #881391;
    font-size: 0.7rem;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
  }

  @media (max-width: 768px) {
    .entry-header {
      flex-wrap: wrap;
    }

    .function {
      margin-left: 0;
      width: 100%;
    }

    .values {
      flex-direction: column;
    }

    .value-item {
      width: 100%;
    }
  }

  .computed-error {
    color: #dc2626;
    font-style: italic;
    font-size: 0.85rem;
  }
</style>
