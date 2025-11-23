<script lang="ts">
  import type { AutopsyData, CallSite, ValueGroup } from "./types";
  import TreeView from "./TreeView.svelte";
  import { tick } from "svelte";

  interface Props {
    data: AutopsyData;
    highlightedLogIndex?: number | null;
    selectedLogIndex?: number | null;
    onShowInHistory?: (logIndex: number) => void;
    onEntryClick?: (logIndex: number, stackTraceId?: string) => void;
  }

  let {
    data,
    highlightedLogIndex = null,
    selectedLogIndex = null,
    onShowInHistory,
    onEntryClick,
  }: Props = $props();

  const collapsedCallSites = $state<Record<string, boolean>>({});

  function getCallSiteKey(callSite: CallSite): string {
    return callSite.filename + callSite.line;
  }

  function toggleCollapse(callSite: CallSite) {
    const key = getCallSiteKey(callSite);
    collapsedCallSites[key] = !collapsedCallSites[key];
  }

  function isCollapsed(callSite: CallSite): boolean {
    return collapsedCallSites[getCallSiteKey(callSite)] ?? false;
  }

  function getFilename(callSite: CallSite): string {
    const parts = callSite.filename.split("/");
    return parts[parts.length - 1];
  }

  // Get all unique column names (argument names) for a call site
  function getColumnNames(callSite: CallSite): string[] {
    const columnNames = new Set<string>();
    for (const valueGroup of callSite.value_groups) {
      for (const value of valueGroup.values) {
        if (value.name) {
          columnNames.add(value.name);
        }
      }
    }
    return Array.from(columnNames).sort();
  }

  // Get value for a specific column in a value group
  function getValueForColumn(
    valueGroup: ValueGroup,
    columnName: string
  ): unknown | undefined {
    const value = valueGroup.values.find((v) => v.name === columnName);
    return value?.value;
  }

  function handleRowClick(valueGroup: ValueGroup) {
    onEntryClick?.(valueGroup.log_index, valueGroup.stack_trace_id);
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
        {#if getColumnNames(callSite).length > 0}
          <table class="value-table">
            <thead class="table-header">
              <tr
                class="call-site-info-row"
                class:collapsible-header={true}
                onclick={() => toggleCollapse(callSite)}
                role="button"
                tabindex="0"
                onkeydown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    toggleCollapse(callSite);
                  }
                }}
              >
                <th
                  colspan={getColumnNames(callSite).length + 1}
                  class="call-site-info"
                >
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
                    {#if callSite.value_groups.length > 0 && callSite.value_groups[0].name}
                      <span class="log-name-header"
                        >{callSite.value_groups[0].name}</span
                      >
                    {/if}
                  </div>
                </th>
              </tr>
              <tr>
                <th class="log-number-header">#</th>
                {#each getColumnNames(callSite) as columnName}
                  <th class="column-header">{columnName}</th>
                {/each}
              </tr>
            </thead>
            {#if isCollapsed(callSite)}
              <tbody>
                <tr
                  class="collapsed-summary-row"
                  onclick={() => toggleCollapse(callSite)}
                  role="button"
                  tabindex="0"
                  onkeydown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      toggleCollapse(callSite);
                    }
                  }}
                >
                  <td
                    colspan={getColumnNames(callSite).length + 1}
                    class="collapsed-summary"
                  >
                    ...{callSite.value_groups.length}
                    {callSite.value_groups.length === 1 ? "log" : "logs"}
                  </td>
                </tr>
              </tbody>
            {:else}
              <tbody>
                {#each callSite.value_groups as valueGroup, groupIndex}
                  <tr
                    class="table-row"
                    class:highlighted={highlightedLogIndex ===
                      valueGroup.log_index}
                    class:selected={selectedLogIndex === valueGroup.log_index}
                    class:clickable={valueGroup.stack_trace_id !== undefined}
                    data-log-index={valueGroup.log_index}
                    onclick={() => handleRowClick(valueGroup)}
                    role={valueGroup.stack_trace_id !== undefined
                      ? "button"
                      : undefined}
                    tabindex={valueGroup.stack_trace_id !== undefined
                      ? 0
                      : undefined}
                    onkeydown={(e) => {
                      if (
                        valueGroup.stack_trace_id !== undefined &&
                        (e.key === "Enter" || e.key === " ")
                      ) {
                        e.preventDefault();
                        handleRowClick(valueGroup);
                      }
                    }}
                  >
                    <td class="log-number-cell">
                      <span
                        class="log-number clickable"
                        role="button"
                        tabindex="0"
                        onclick={(e) => {
                          e.stopPropagation();
                          onShowInHistory?.(valueGroup.log_index);
                        }}
                        onkeydown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            e.stopPropagation();
                            onShowInHistory?.(valueGroup.log_index);
                          }
                        }}
                        title="Show this log in the History view"
                      >
                        <span class="log-number-text"
                          >#{valueGroup.log_index}</span
                        >
                        <span class="log-number-arrow">➡️</span>
                      </span>
                    </td>
                    {#each getColumnNames(callSite) as columnName}
                      <td class="value-cell">
                        {#if getValueForColumn(valueGroup, columnName) !== undefined}
                          <TreeView
                            value={getValueForColumn(valueGroup, columnName)}
                          />
                        {:else}
                          <span class="empty-cell">—</span>
                        {/if}
                      </td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            {/if}
          </table>
        {:else}
          <div
            class="call-site-header"
            class:collapsible-header={true}
            onclick={() => toggleCollapse(callSite)}
            role="button"
            tabindex="0"
            onkeydown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                toggleCollapse(callSite);
              }
            }}
          >
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
              {#if callSite.value_groups.length > 0 && callSite.value_groups[0].name}
                <span class="log-name-header"
                  >{callSite.value_groups[0].name}</span
                >
              {/if}
            </div>
          </div>
          {#if isCollapsed(callSite)}
            <div
              class="collapsed-summary"
              onclick={() => toggleCollapse(callSite)}
              role="button"
              tabindex="0"
              onkeydown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  toggleCollapse(callSite);
                }
              }}
            >
              {callSite.value_groups.length}
              {callSite.value_groups.length === 1 ? "log" : "logs"}
            </div>
          {:else}
            <div class="value-groups">
              {#each callSite.value_groups as valueGroup, groupIndex}
                <div
                  class="value-group"
                  class:highlighted={highlightedLogIndex ===
                    valueGroup.log_index}
                  class:selected={selectedLogIndex === valueGroup.log_index}
                  class:clickable={valueGroup.stack_trace_id !== undefined}
                  data-log-index={valueGroup.log_index}
                  onclick={() => handleRowClick(valueGroup)}
                  role={valueGroup.stack_trace_id !== undefined
                    ? "button"
                    : undefined}
                  tabindex={valueGroup.stack_trace_id !== undefined
                    ? 0
                    : undefined}
                  onkeydown={(e) => {
                    if (
                      valueGroup.stack_trace_id !== undefined &&
                      (e.key === "Enter" || e.key === " ")
                    ) {
                      e.preventDefault();
                      handleRowClick(valueGroup);
                    }
                  }}
                >
                  <div class="value-group-row">
                    <span
                      class="log-number clickable"
                      role="button"
                      tabindex="0"
                      onclick={(e) => {
                        e.stopPropagation();
                        onShowInHistory?.(valueGroup.log_index);
                      }}
                      onkeydown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          e.stopPropagation();
                          onShowInHistory?.(valueGroup.log_index);
                        }
                      }}
                      title="Show this log in the History view"
                    >
                      <span class="log-number-text"
                        >#{valueGroup.log_index}</span
                      >
                      <span class="log-number-arrow">➡️</span>
                    </span>
                    {#if valueGroup.values.length === 0 && valueGroup.name}
                      <span class="log-name-only">{valueGroup.name}</span>
                    {:else}
                      <div class="values">
                        {#if valueGroup.function_name !== callSite.function_name || valueGroup.class_name !== callSite.class_name}
                          <span class="function-name-inline">
                            in {#if valueGroup.class_name}{valueGroup.class_name}.{/if}{valueGroup.function_name}
                          </span>
                        {/if}
                        {#each valueGroup.values as valueWithName, valueIndex}
                          <div class="value-item">
                            {#if valueWithName.name}
                              <div class="value-label">
                                {valueWithName.name}:
                              </div>
                            {/if}
                            <TreeView value={valueWithName.value} />
                          </div>
                        {/each}
                      </div>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          {/if}
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

  .header-left {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.4rem;
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

  .log-name-header {
    margin-left: 0.4rem;
    color: #881391;
    font-size: 0.9rem;
    font-weight: 600;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
  }

  .log-name-only {
    color: #881391;
    font-size: 1rem;
    font-weight: 500;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
  }

  .value-table {
    width: 100%;
    border-collapse: collapse;
    background: white;
    border-radius: 4px;
    overflow: hidden;
  }

  .table-header {
    position: sticky;
    top: 0;
    z-index: 10;
    background: #f9f9f9;
  }

  .call-site-info-row {
    border-bottom: 1px solid #e5e5e5;
  }

  .call-site-info {
    padding: 0.75rem;
    text-align: left;
    border-bottom: 1px solid #e5e5e5;
    font-weight: normal;
    color: inherit;
    font-size: inherit;
    font-family: inherit;
  }

  .collapsible-header {
    cursor: pointer;
    transition: background-color 0.2s;
  }

  .collapsible-header:hover {
    background-color: #f0f0f0;
  }

  .call-site-header {
    padding: 0.75rem;
    border-bottom: 1px solid #e5e5e5;
    margin-bottom: 0.5rem;
  }

  .collapsed-summary-row {
    border-bottom: 1px solid #e5e5e5;
    cursor: pointer;
    transition: background-color 0.2s;
  }

  .collapsed-summary-row:hover {
    background-color: #f8fafc;
  }

  .collapsed-summary {
    padding: 0.75rem;
    text-align: center;
    color: #666;
    font-style: italic;
    cursor: pointer;
    transition: background-color 0.2s;
  }

  .collapsed-summary:hover {
    background-color: #f8fafc;
  }

  .table-header th:not(.call-site-info) {
    padding: 0.75rem;
    text-align: left;
    font-weight: 600;
    /* color: #2563eb; */
    color: #881391;
    font-size: 0.85rem;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    border-bottom: 2px solid #e5e5e5;
    white-space: nowrap;
  }

  .log-number-header {
    width: 4rem;
    min-width: 4rem;
  }

  .table-row {
    border-bottom: 1px solid #e5e5e5;
    transition: background-color 0.2s;
  }

  .table-row.clickable {
    cursor: pointer;
  }

  .table-row:hover {
    background-color: #f8fafc;
  }

  .table-row.highlighted {
    animation: highlight-pulse-table 2s ease-in-out;
  }

  .table-row.highlighted.selected {
    animation: highlight-pulse-table-selected 2s ease-in-out;
  }

  .table-row.selected {
    background-color: #eff6ff;
  }

  .table-row.selected:hover {
    background-color: #dbeafe;
  }

  .log-number-cell {
    padding: 0.5rem 0.75rem;
    vertical-align: top;
  }

  .value-cell {
    padding: 0.75rem;
    vertical-align: top;
    min-width: 200px;
  }

  .empty-cell {
    color: #cbd5e1;
    font-style: italic;
  }

  .value-groups {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .value-group {
    border-left: 3px solid #2563eb;
    padding: 0.5rem 0 0.5rem 0.75rem;
    transition:
      border-color 0.2s,
      background-color 0.2s;
    border-radius: 4px;
    position: relative;
  }

  .value-group > * {
    position: relative;
    z-index: 2;
  }

  .value-group.clickable {
    cursor: pointer;
  }

  .value-group.highlighted {
    position: relative;
    border-left-color: #2563eb;
  }

  .value-group.highlighted::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    border-radius: 4px;
    pointer-events: none;
    animation: highlight-pulse 2s ease-in-out;
    z-index: 1;
  }

  .value-group.selected {
    background: #eff6ff;
    border-left-color: #2563eb;
  }

  .value-group.selected:hover {
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

  @keyframes highlight-pulse-table {
    0% {
      background-color: transparent;
      box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.4);
    }
    10% {
      background-color: #dbeafe;
      box-shadow: 0 0 0 8px rgba(37, 99, 235, 0);
    }
    30% {
      background-color: #bfdbfe;
    }
    100% {
      background-color: transparent;
      box-shadow: 0 0 0 0 rgba(37, 99, 235, 0);
    }
  }

  @keyframes highlight-pulse-table-selected {
    0% {
      background-color: #eff6ff;
      box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.4);
    }
    10% {
      background-color: #dbeafe;
      box-shadow: 0 0 0 8px rgba(37, 99, 235, 0);
    }
    30% {
      background-color: #bfdbfe;
    }
    100% {
      background-color: #eff6ff;
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
