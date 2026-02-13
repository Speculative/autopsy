<script lang="ts">
  import type { AutopsyData, CallSite, ValueGroup, LogMark } from "./types";
  import TreeView from "./TreeView.svelte";
  import CodeLocation from "./CodeLocation.svelte";

  interface Props {
    data: AutopsyData;
    logMarks?: Record<number, LogMark>;
    columnOrders?: Record<string, string[]>;
    callSiteKey?: string | null;
    isExpanded?: boolean;
    onMarkLog?: (logIndex: number, color: string, note: string) => void;
    onEntryClick?: (logIndex: number, stackTraceId?: string) => void;
  }

  let {
    data,
    logMarks = {},
    columnOrders = {},
    callSiteKey = $bindable(null),
    isExpanded = $bindable(false),
    onMarkLog,
    onEntryClick,
  }: Props = $props();

  const COLLAPSED_ROW_LIMIT = 10;

  function getCallSiteKey(cs: CallSite): string {
    return `${cs.filename}:${cs.line}`;
  }

  function getShortFilename(filename: string): string {
    const parts = filename.split("/");
    return parts[parts.length - 1];
  }

  // Available call sites (non-dashboard)
  let availableCallSites = $derived(
    data.call_sites.filter(cs => !cs.is_dashboard)
  );

  // Selected call site
  let selectedCallSite = $derived(
    callSiteKey ? data.call_sites.find(cs => getCallSiteKey(cs) === callSiteKey) ?? null : null
  );

  // Column names for selected call site
  let columnNames = $derived.by(() => {
    if (!selectedCallSite) return [];
    const key = getCallSiteKey(selectedCallSite);
    const names = new Set<string>();
    for (const vg of selectedCallSite.value_groups) {
      if (vg.values) {
        for (const v of vg.values) {
          if (v.name) names.add(v.name);
        }
      }
    }

    const storedOrder = columnOrders[key];
    if (!storedOrder) return Array.from(names);

    // Respect stored order
    const ordered: string[] = [];
    const remaining = new Set(names);
    for (const name of storedOrder) {
      if (name.startsWith('computed:')) continue;
      if (remaining.has(name)) {
        ordered.push(name);
        remaining.delete(name);
      }
    }
    for (const name of remaining) {
      ordered.push(name);
    }
    return ordered;
  });

  // Rows to display
  let allRows = $derived(selectedCallSite?.value_groups ?? []);
  let displayedRows = $derived(
    isExpanded ? allRows : allRows.slice(0, COLLAPSED_ROW_LIMIT)
  );
  let hasMore = $derived(allRows.length > COLLAPSED_ROW_LIMIT);

  function getValueForColumn(vg: ValueGroup, columnName: string): unknown | undefined {
    if (!vg.values) return undefined;
    const match = vg.values.find(v => v.name === columnName);
    return match?.value;
  }
</script>

<div class="stream-cell">
  {#if !callSiteKey}
    <div class="stream-picker">
      <label class="picker-label">Choose a stream:</label>
      <select
        class="picker-select"
        value=""
        onchange={(e) => { callSiteKey = e.currentTarget.value || null; }}
      >
        <option value="">Select...</option>
        {#each availableCallSites as cs}
          {@const key = getCallSiteKey(cs)}
          <option value={key}>
            {getShortFilename(cs.filename)}:{cs.line} ({cs.function_name}) - {cs.value_groups.length} logs
          </option>
        {/each}
      </select>
    </div>
  {:else if selectedCallSite}
    <div class="stream-header">
      <CodeLocation
        filename={selectedCallSite.filename}
        line={selectedCallSite.line}
        functionName={selectedCallSite.function_name}
        className={selectedCallSite.class_name}
      />
      <span class="row-count">{allRows.length} rows</span>
      <button class="change-stream" onclick={() => { callSiteKey = null; }} title="Change stream">
        Change
      </button>
    </div>

    <div class="table-container" class:expanded={isExpanded}>
      <table class="stream-table">
        <thead>
          <tr>
            <th class="log-number-header">#</th>
            {#each columnNames as colName}
              <th>{colName}</th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each displayedRows as vg (vg.log_index)}
            {@const mark = logMarks[vg.log_index]}
            <tr
              class="stream-row"
              class:clickable={vg.stack_trace_id !== undefined}
              style={mark?.color ? `background-color: ${mark.color};` : ""}
              onclick={() => onEntryClick?.(vg.log_index, vg.stack_trace_id)}
            >
              <td class="log-number-cell">
                <span class="log-number">#{vg.log_index}</span>
              </td>
              {#each columnNames as colName}
                {@const cellValue = getValueForColumn(vg, colName)}
                <td class="value-cell">
                  {#if cellValue !== undefined}
                    <TreeView value={cellValue} />
                  {:else}
                    <span class="empty-cell">&mdash;</span>
                  {/if}
                </td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if hasMore}
      <div class="expand-bar">
        <button class="expand-button" onclick={() => isExpanded = !isExpanded}>
          {#if isExpanded}
            Collapse ({allRows.length} total)
          {:else}
            Show all ({allRows.length - COLLAPSED_ROW_LIMIT} more)
          {/if}
        </button>
      </div>
    {/if}
  {:else}
    <div class="stream-not-found">
      <p>Stream not found. It may have been removed.</p>
      <button class="change-stream" onclick={() => { callSiteKey = null; }}>Select another</button>
    </div>
  {/if}
</div>

<style>
  .stream-cell {
    display: flex;
    flex-direction: column;
  }

  .stream-picker {
    padding: 1.5rem;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
  }

  .picker-label {
    font-size: 0.9rem;
    color: #64748b;
  }

  .picker-select {
    padding: 0.4rem 0.6rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.85rem;
    max-width: 100%;
    min-width: 300px;
  }

  .stream-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.35rem 0.75rem;
    border-bottom: 1px solid #e5e7eb;
  }

  .row-count {
    font-size: 0.8rem;
    color: #64748b;
    margin-left: auto;
  }

  .change-stream {
    background: none;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    padding: 0.15rem 0.5rem;
    font-size: 0.75rem;
    color: #64748b;
    cursor: pointer;
  }

  .change-stream:hover {
    border-color: #2563eb;
    color: #2563eb;
  }

  .table-container {
    max-height: 300px;
    overflow: auto;
    scrollbar-width: thin;
  }

  .table-container.expanded {
    max-height: none;
  }

  .stream-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }

  .stream-table th {
    position: sticky;
    top: 0;
    background: #f9fafb;
    padding: 0.35rem 0.6rem;
    text-align: left;
    font-weight: 600;
    color: #374151;
    border-bottom: 2px solid #e5e7eb;
    white-space: nowrap;
    font-size: 0.8rem;
  }

  .log-number-header {
    width: 3rem;
  }

  .stream-row {
    transition: background-color 0.15s;
  }

  .stream-row:hover {
    background-color: #f8fafc !important;
  }

  .stream-row.clickable {
    cursor: pointer;
  }

  .stream-table td {
    padding: 0.3rem 0.6rem;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: top;
  }

  .log-number-cell {
    white-space: nowrap;
  }

  .log-number {
    font-weight: 600;
    color: #2563eb;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    background: #eff6ff;
    border-radius: 3px;
    padding: 1px 4px;
    font-size: 0.8rem;
  }

  .value-cell {
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .empty-cell {
    color: #d1d5db;
  }

  .stream-not-found {
    padding: 1.5rem;
    text-align: center;
    color: #64748b;
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
