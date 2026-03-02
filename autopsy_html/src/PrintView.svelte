<script lang="ts">
  import type { AutopsyData, CallSite, ValueGroup } from "./types";
  import TreeView from "./TreeView.svelte";
  import CodeLocation from "./CodeLocation.svelte";
  import { trackEvent } from "./studyEvents";
  import VirtualList from "./VirtualList.svelte";
  import { isVSCodeWebview, navigateToLogInVSCode } from "./vscodeApi";
  import { FileCodeCorner } from "lucide-svelte";

  /**
   * PrintView — Simplified chronological log view for the print ablation study condition.
   * Shows only: log numbers, code locations, argument values with TreeView expansion.
   * No: call stacks, tab bar, filters, skip markers, marks, menus, computed columns.
   *
   * This component is designed to be removed after the study is complete.
   */

  interface Props {
    data: AutopsyData;
  }

  let { data }: Props = $props();

  interface HistoryEntry {
    log_index: number;
    callSite: CallSite;
    valueGroup: ValueGroup;
  }

  // Durable TreeView expansion state that survives virtual scroll recycling.
  let treeExpansionState = $state<Map<string, Set<string>>>(new Map());

  function getExpansionSet(logIndex: number, valueName: string): Set<string> {
    const key = `${logIndex}:${valueName}`;
    return treeExpansionState.get(key) || new Set();
  }

  function makeToggleExpand(logIndex: number, valueName: string) {
    return (jsonPath: string) => {
      const key = `${logIndex}:${valueName}`;
      const oldPaths = treeExpansionState.get(key) || new Set<string>();
      const newPaths = new Set(oldPaths);
      if (newPaths.has(jsonPath)) {
        newPaths.delete(jsonPath);
      } else {
        newPaths.add(jsonPath);
      }
      const newMap = new Map(treeExpansionState);
      newMap.set(key, newPaths);
      treeExpansionState = newMap;
    };
  }

  // Flatten all log entries chronologically — no filtering, no skip markers
  let historyEntries = $derived.by(() => {
    const entries: HistoryEntry[] = [];

    for (const callSite of data.call_sites) {
      // Skip dashboard call sites entirely
      if (callSite.is_dashboard) continue;

      for (const valueGroup of callSite.value_groups) {
        if (valueGroup.dashboard_type) continue;
        entries.push({
          log_index: valueGroup.log_index,
          callSite,
          valueGroup,
        });
      }
    }

    entries.sort((a, b) => a.log_index - b.log_index);
    return entries;
  });

  let showCodeLocations = $state(false);

  const ENTRY_HEIGHT = 42;

  function estimateItemHeight(): number {
    return ENTRY_HEIGHT;
  }
</script>

{#if historyEntries.length === 0}
  <p class="empty">No log data available.</p>
{:else}
  <div class="history-header">
    <label class="header-checkbox">
      <input
        type="checkbox"
        checked={showCodeLocations}
        onchange={(e) => {
          showCodeLocations = e.currentTarget.checked;
          trackEvent('ui.printViewOptions', { option: 'showCodeLocations', enabled: e.currentTarget.checked });
        }}
      />
      <span>Show code locations</span>
    </label>
  </div>
  <div class="history">
    <VirtualList
      items={historyEntries}
      itemHeight={estimateItemHeight}
      overscan={10}
      useWindowScroll={false}
      containerHeight="calc(100vh - 40px)"
    >
      {#snippet children(item, index)}
        {@const entry = item as HistoryEntry}
        <div class="history-entry" data-log-index={entry.log_index}>
          <span class="log-number">#{entry.log_index}</span>

          {#if isVSCodeWebview()}
            <button
              class="nav-button"
              onclick={(e) => {
                e.stopPropagation();
                navigateToLogInVSCode(entry.log_index);
                trackEvent('ui.printViewNavigateToCode', { logIndex: entry.log_index });
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
                showFunction={false}
              />
            {/if}
            {#if entry.valueGroup.values && entry.valueGroup.values.length === 0 && entry.valueGroup.name}
              <span class="log-name-inline">{entry.valueGroup.name}</span>
            {:else if entry.valueGroup.values}
              {#if entry.valueGroup.name}
                <span class="log-name-inline">{entry.valueGroup.name}</span>
              {/if}
              {#each entry.valueGroup.values as valueWithName}
                <span class="value-item" title={valueWithName.name || ''}>
                  {#if valueWithName.name}
                    <span class="value-label">{valueWithName.name}:</span>
                  {/if}
                  <TreeView value={valueWithName.value} expansionState={getExpansionSet(entry.log_index, valueWithName.name || '')} onToggleExpand={makeToggleExpand(entry.log_index, valueWithName.name || '')} />
                </span>
              {/each}
            {/if}
          </div>
        </div>
      {/snippet}
    </VirtualList>
  </div>
{/if}

<style>
  .empty {
    text-align: center;
    color: #666;
    padding: 3rem;
  }

  .history-header {
    padding: 0.4rem 0.6rem;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    display: flex;
    gap: 1.5rem;
    flex-wrap: wrap;
    margin-bottom: 0.25rem;
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
    position: relative;
    height: calc(100vh - 40px);
  }

  .history :global(.virtual-list-container) {
    scrollbar-width: thin;
  }

  .history :global(.virtual-list-container)::-webkit-scrollbar {
    width: 8px;
  }

  .history :global(.virtual-list-container)::-webkit-scrollbar-track {
    background: #f1f1f1;
  }

  .history :global(.virtual-list-container)::-webkit-scrollbar-thumb {
    background: #888;
    border-radius: 4px;
  }

  .history :global(.virtual-list-container)::-webkit-scrollbar-thumb:hover {
    background: #555;
  }

  .history-entry {
    border: 1px solid #e5e5e5;
    border-radius: 6px;
    padding: 0.4rem 0.6rem;
    background: #ffffff;
    transition: border-color 0.2s;
    position: relative;
    display: flex;
    flex-direction: row;
    align-items: flex-start;
    gap: 0.5rem;
    flex-wrap: nowrap;
  }

  .history-entry:hover {
    border-color: #2563eb;
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
    align-self: flex-start;
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
    align-items: flex-start;
    align-self: flex-start;
    transition: border-color 0.15s ease;
  }

  .value-item:hover {
    border-color: #cbd5e1;
    background: #f8fafc;
  }

  .value-label {
    display: none;
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
