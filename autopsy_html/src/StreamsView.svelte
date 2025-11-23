<script lang="ts">
  import type { AutopsyData, CallSite, ValueGroup, StackTrace } from "./types";
  import TreeView from "./TreeView.svelte";
  import { tick } from "svelte";

  interface Props {
    data: AutopsyData;
    highlightedLogIndex?: number | null;
    onShowInHistory?: (logIndex: number) => void;
  }

  let { data, highlightedLogIndex = null, onShowInHistory }: Props = $props();

  let selectedStackTrace = $state<StackTrace | null>(null);

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
    if (valueGroup.stack_trace_id !== undefined && data.stack_traces) {
      const traceId = valueGroup.stack_trace_id;
      const trace = data.stack_traces[traceId];
      selectedStackTrace = trace || null;
    }
  }

  function closeModal() {
    selectedStackTrace = null;
  }

  function handleBackdropClick(event: MouseEvent) {
    if (event.target === event.currentTarget) {
      closeModal();
    }
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
              <tr class="call-site-info-row">
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
                      <span class="log-name-header">{callSite.value_groups[0].name}</span>
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
            <tbody>
              {#each callSite.value_groups as valueGroup, groupIndex}
                <tr
                  class="table-row"
                  class:highlighted={highlightedLogIndex ===
                    valueGroup.log_index}
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
          </table>
        {:else}
          <div class="value-groups">
            {#each callSite.value_groups as valueGroup, groupIndex}
              <div
                class="value-group"
                class:highlighted={highlightedLogIndex === valueGroup.log_index}
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
                    <span class="log-number-text">#{valueGroup.log_index}</span>
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
                            <div class="value-label">{valueWithName.name}:</div>
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
      </div>
    {/each}
  </div>
{/if}

{#if selectedStackTrace !== null}
  <div class="modal-backdrop" onclick={handleBackdropClick}>
    <div class="modal-content" onclick={(e) => e.stopPropagation()}>
      <div class="modal-header">
        <h2>Stack Trace</h2>
        <button class="close-button" onclick={closeModal}>×</button>
      </div>
      <div class="modal-body">
        <div class="stack-trace">
          {#each selectedStackTrace.frames as frame, index}
            <div class="stack-frame">
              <div class="frame-header">
                <span class="frame-number">#{index + 1}</span>
                <span class="frame-function">{frame.function_name}</span>
                <span class="frame-location">
                  {frame.filename}:{frame.line_number}
                </span>
              </div>
              <div class="frame-code">
                <code>{frame.code_context || "(no code context)"}</code>
              </div>
              {#if Object.keys(frame.local_variables).length > 0}
                <div class="frame-variables">
                  <div class="variables-header">Local Variables:</div>
                  <div class="variables-list">
                    {#each Object.entries(frame.local_variables) as [name, value]}
                      <div class="variable-item">
                        <TreeView {value} key={name} />
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    </div>
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
    animation: highlight-pulse 2s ease-in-out;
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
    transition: border-color 0.2s;
    border-radius: 4px;
  }

  .value-group.clickable {
    cursor: pointer;
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

  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 2rem;
  }

  .modal-content {
    background: white;
    border-radius: 8px;
    max-width: 900px;
    width: 100%;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow:
      0 20px 25px -5px rgba(0, 0, 0, 0.1),
      0 10px 10px -5px rgba(0, 0, 0, 0.04);
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid #e5e5e5;
  }

  .modal-header h2 {
    margin: 0;
    font-size: 1.5rem;
    color: #333;
  }

  .close-button {
    background: none;
    border: none;
    font-size: 2rem;
    color: #666;
    cursor: pointer;
    padding: 0;
    width: 2rem;
    height: 2rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: background-color 0.2s;
  }

  .close-button:hover {
    background-color: #f0f0f0;
  }

  .modal-body {
    padding: 1.5rem;
    overflow-y: auto;
    flex: 1;
  }

  .stack-trace {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .stack-frame {
    border: 1px solid #e5e5e5;
    border-radius: 6px;
    padding: 1rem;
    background: #f9fafb;
  }

  .frame-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
    font-size: 0.9rem;
  }

  .frame-number {
    font-weight: 600;
    color: #2563eb;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    background: #eff6ff;
    padding: 2px 6px;
    border-radius: 3px;
  }

  .frame-function {
    font-weight: 500;
    color: #475569;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
  }

  .frame-location {
    color: #64748b;
    font-size: 0.85rem;
    margin-left: auto;
  }

  .frame-code {
    background: white;
    padding: 0.75rem;
    border-radius: 4px;
    margin-bottom: 0.75rem;
    border: 1px solid #e5e5e5;
  }

  .frame-code code {
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    font-size: 0.85rem;
    color: #333;
  }

  .frame-variables {
    background: white;
    padding: 0.75rem;
    border-radius: 4px;
    border: 1px solid #e5e5e5;
  }

  .variables-header {
    font-weight: 600;
    color: #475569;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
  }

  .variables-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .variable-item {
    margin-bottom: 0.5rem;
  }
</style>
