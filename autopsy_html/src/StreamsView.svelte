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
          <div class="header-left">
            <span class="filename"
              >{getFilename(callSite)}<span class="line-number"
                >:{callSite.line}</span
              ></span
            >
            <span class="function-name">
              in <code>
                {#if callSite.class_name}
                  {callSite.class_name}.{callSite.function_name}
                {:else}
                  {callSite.function_name}
                {/if}
              </code>
            </span>
          </div>
        </div>
        <div class="value-groups">
          {#each callSite.value_groups as valueGroup, groupIndex}
            <div
              class="value-group"
              class:highlighted={highlightedLogIndex === valueGroup.log_index}
              data-log-index={valueGroup.log_index}
            >
              <div class="value-group-row">
                <span
                  class="log-number clickable"
                  role="button"
                  tabindex="0"
                  onclick={() => onShowInHistory?.(valueGroup.log_index)}
                  onkeydown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onShowInHistory?.(valueGroup.log_index);
                    }
                  }}
                  title="Show this log in the History view"
                >
                  <span class="log-number-text">#{valueGroup.log_index}</span>
                  <span class="log-number-arrow">➡️</span>
                </span>
                <div class="values">
                  {#if valueGroup.function_name !== callSite.function_name || valueGroup.class_name !== callSite.class_name}
                    <span class="function-name-inline">
                      in {#if valueGroup.class_name}{valueGroup.class_name}.{/if}{valueGroup.function_name}
                    </span>
                  {/if}
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
    position: sticky;
    top: 0;
    background: #f9f9f9;
    z-index: 10;
    padding: 0.75rem 0;
    margin: -1rem -1rem 0.5rem -1rem;
    padding-left: 1rem;
    padding-right: 1rem;
    border-bottom: 1px solid #e5e5e5;
  }

  .header-left {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
  }

  .filename {
    font-weight: 600;
    color: #2563eb;
    font-size: 1.1rem;
  }

  .line-number {
    margin-left: 0.25rem;
    font-weight: 400;
    font-size: 0.9rem;
    color: #666;
  }

  .function-name {
    margin-left: 0.4rem;
    color: #666;
    font-size: 0.9rem;
    font-weight: 500;
  }

  .function-name code {
    background: #f0f0f0;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    color: #2563eb;
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

  .value-group-row {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
  }

  .log-number {
    font-weight: 600;
    color: #2563eb;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    background: #eff6ff;
    border-radius: 3px;
    text-transform: none;
    letter-spacing: normal;
    flex-shrink: 0;
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
    transform: translateX(0);
  }

  .log-number-arrow {
    transform: translateX(0);
  }

  .log-number.clickable:hover .log-number-text,
  .log-number.clickable:focus .log-number-text {
    transform: translateX(-100%);
  }

  .log-number.clickable:hover .log-number-arrow,
  .log-number.clickable:focus .log-number-arrow {
    transform: translateX(-100%);
  }

  .function-name-inline {
    font-size: 0.75rem;
    text-transform: none;
    font-weight: 400;
    color: #666;
    align-self: center;
    flex-shrink: 0;
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
