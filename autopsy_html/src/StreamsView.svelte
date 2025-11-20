<script lang="ts">
  import type { AutopsyData, CallSite } from "./types";
  import TreeView from "./TreeView.svelte";
  import { tick } from "svelte";

  interface Props {
    data: AutopsyData;
    highlightedLogIndex?: number | null;
    onShowInHistory?: (logIndex: number) => void;
  }

  let { data, highlightedLogIndex = null, onShowInHistory }: Props = $props();

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

{#if data.call_sites.length === 0}
  <p class="empty">No report data available.</p>
{:else}
  <div class="call-sites">
    {#each data.call_sites as callSite (callSite.filename + callSite.line)}
      <div class="call-site">
        <div class="call-site-header">
          <span class="filename">{getFilename(callSite)}</span>
          <span class="line">Line {callSite.line}</span>
        </div>
        <div class="function-name">
          Function: <code>{callSite.function_name}</code>
        </div>
        <div class="file-path">{callSite.filename}</div>
        <div class="value-groups">
          {#each callSite.value_groups as valueGroup, groupIndex}
            <div
              class="value-group"
              class:highlighted={highlightedLogIndex === valueGroup.log_index}
              data-log-index={valueGroup.log_index}
            >
              <div class="value-group-header">
                <span class="call-label">
                  Call {groupIndex + 1}
                  {#if valueGroup.function_name !== callSite.function_name}
                    <span class="function-name-inline"
                      >in {valueGroup.function_name}</span
                    >
                  {/if}
                </span>
                <button
                  class="show-in-history-btn"
                  onclick={() => onShowInHistory?.(valueGroup.log_index)}
                  title="Show this log in the History view"
                >
                  Show in History →
                </button>
              </div>
              <div class="values">
                {#each valueGroup.values as valueWithName, valueIndex}
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

  .call-sites {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .call-site {
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 1rem;
    background: #f9f9f9;
  }

  .call-site-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .filename {
    font-weight: 600;
    color: #2563eb;
    font-size: 1.1rem;
  }

  .line {
    color: #666;
    font-size: 0.9rem;
  }

  .function-name {
    color: #666;
    font-size: 0.9rem;
    margin-bottom: 0.5rem;
    font-weight: 500;
  }

  .function-name code {
    background: #f0f0f0;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    color: #2563eb;
  }

  .file-path {
    color: #888;
    font-size: 0.85rem;
    margin-bottom: 1rem;
    font-family: monospace;
  }

  .value-groups {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .value-group {
    border-left: 3px solid #2563eb;
    padding: 0.5rem 0 0.5rem 0.75rem;
    transition: border-color 0.2s;
    border-radius: 4px;
  }

  .value-group.highlighted {
    animation: highlight-pulse 2s ease-in-out;
    border-left-color: #2563eb;
  }

  @keyframes highlight-pulse {
    0% {
      background: transparent;
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
      background: transparent;
      box-shadow: 0 0 0 0 rgba(37, 99, 235, 0);
    }
  }

  .value-group-header {
    font-weight: 600;
    color: #2563eb;
    font-size: 0.85rem;
    margin-bottom: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .call-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .function-name-inline {
    font-size: 0.75rem;
    text-transform: none;
    font-weight: 400;
    color: #666;
  }

  .show-in-history-btn {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    color: #2563eb;
    padding: 0.25rem 0.5rem;
    font-size: 0.7rem;
    font-weight: 500;
    border-radius: 4px;
    cursor: pointer;
    text-transform: none;
    letter-spacing: normal;
    transition: all 0.2s;
    white-space: nowrap;
  }

  .show-in-history-btn:hover {
    background: #dbeafe;
    border-color: #93c5fd;
  }

  .show-in-history-btn:active {
    background: #bfdbfe;
  }

  .values {
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 1rem;
    align-items: flex-start;
  }

  .value-item {
    flex: 0 1 auto;
    min-width: 0;
    padding: 0.75rem;
    background: white;
    border: 1px solid #e5e5e5;
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
    .values {
      flex-direction: column;
    }

    .value-item {
      width: 100%;
    }
  }
</style>
