<script lang="ts">
  import type { AutopsyData, CallSite, ValueGroup } from "./types";
  import TreeView from "./TreeView.svelte";
  import { tick } from "svelte";

  interface Props {
    data: AutopsyData;
    highlightedLogIndex?: number | null;
    selectedLogIndex?: number | null;
    onShowInStream?: (logIndex: number) => void;
    onEntryClick?: (logIndex: number, stackTraceId?: string) => void;
  }

  let { data, highlightedLogIndex = null, selectedLogIndex = null, onShowInStream, onEntryClick }: Props = $props();

  // Create a flattened list of all log entries with their context
  interface HistoryEntry {
    log_index: number;
    callSite: CallSite;
    valueGroup: ValueGroup;
  }

  let historyEntries = $derived.by(() => {
    const entries: HistoryEntry[] = [];

    for (const callSite of data.call_sites) {
      for (const valueGroup of callSite.value_groups) {
        entries.push({
          log_index: valueGroup.log_index,
          callSite,
          valueGroup,
        });
      }
    }

    // Sort by log_index to get chronological order
    return entries.sort((a, b) => a.log_index - b.log_index);
  });

  function getFilename(callSite: CallSite): string {
    const parts = callSite.filename.split("/");
    return parts[parts.length - 1];
  }

  function handleEntryClick(entry: HistoryEntry) {
    onEntryClick?.(entry.log_index, entry.valueGroup.stack_trace_id);
  }

  // Effect to scroll to and highlight the entry when highlightedLogIndex changes
  $effect(() => {
    if (highlightedLogIndex !== null) {
      // Wait for the DOM to update
      tick().then(() => {
        const element = document.querySelector(
          `[data-log-index="${highlightedLogIndex}"]`
        );
        if (element) {
          element.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      });
    }
  });
</script>

{#if historyEntries.length === 0}
  <p class="empty">No report data available.</p>
{:else}
  <div class="history">
    {#each historyEntries as entry (entry.log_index)}
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
          <span class="location">
            <span class="filename">{getFilename(entry.callSite)}</span>
            <span class="separator">:</span>
            <span class="line">{entry.callSite.line}</span>
          </span>
          <span class="separator">in</span>
          <span class="function">
            {#if entry.valueGroup.class_name}
              {entry.valueGroup.class_name}.{entry.valueGroup.function_name}
            {:else}
              {entry.valueGroup.function_name}
            {/if}
          </span>
        </div>
        {#if entry.valueGroup.values.length === 0 && entry.valueGroup.name}
          <div class="log-name-only">{entry.valueGroup.name}</div>
        {:else}
          <div class="values">
            {#if entry.valueGroup.name}
              <span class="log-name-inline">{entry.valueGroup.name}</span>
            {/if}
            {#each entry.valueGroup.values as valueWithName}
              <div class="value-item">
                {#if valueWithName.name}
                  <div class="value-label">{valueWithName.name}:</div>
                {/if}
                <TreeView value={valueWithName.value} />
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/each}
  </div>
{/if}

<style>
  .empty {
    text-align: center;
    color: #666;
    padding: 3rem;
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
</style>
