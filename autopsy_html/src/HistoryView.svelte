<script lang="ts">
  import type { AutopsyData, CallSite, ValueGroup } from "./types";
  import TreeView from "./TreeView.svelte";
  import { tick } from "svelte";

  interface Props {
    data: AutopsyData;
    highlightedLogIndex?: number | null;
  }

  let { data, highlightedLogIndex = null }: Props = $props();

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
        data-log-index={entry.log_index}
      >
        <div class="entry-header">
          <span class="log-number">#{entry.log_index}</span>
          <span class="location">
            <span class="filename">{getFilename(entry.callSite)}</span>
            <span class="separator">:</span>
            <span class="line">{entry.callSite.line}</span>
          </span>
          <span class="function">
            {entry.valueGroup.function_name}
          </span>
        </div>
        <div class="values">
          {#each entry.valueGroup.values as valueWithName}
            <div class="value-item">
              {#if valueWithName.name}
                <div class="value-label">{valueWithName.name}:</div>
              {/if}
              <TreeView value={valueWithName.value} />
            </div>
          {/each}
        </div>
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
    transition: border-color 0.2s;
  }

  .history-entry:hover {
    border-color: #2563eb;
  }

  .history-entry.highlighted {
    animation: highlight-pulse 2s ease-in-out;
    border-color: #2563eb;
  }

  @keyframes highlight-pulse {
    0% {
      background: white;
      box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.4);
    }
    10% {
      background: #dbeafe;
      box-shadow: 0 0 0 8px rgba(37, 99, 235, 0);
    }
    30% {
      background: #bfdbfe;
    }
    100% {
      background: white;
      box-shadow: 0 0 0 0 rgba(37, 99, 235, 0);
    }
  }

  .entry-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
  }

  .log-number {
    font-weight: 600;
    color: #2563eb;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    background: #eff6ff;
    padding: 2px 6px;
    border-radius: 3px;
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
    color: #cbd5e1;
  }

  .line {
    color: #64748b;
  }

  .function {
    color: #64748b;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    margin-left: auto;
  }

  .values {
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: flex-start;
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
    font-weight: 600;
    color: #881391;
    font-size: 0.85rem;
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
