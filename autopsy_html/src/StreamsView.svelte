<script lang="ts">
  import type { AutopsyData, CallSite, ValueGroup, ComputedColumn } from "./types";
  import TreeView from "./TreeView.svelte";
  import { tick } from "svelte";
  import { evaluateComputedColumn, isComputedColumnSortable, getComputedColumnDisplayName } from "./computedColumns";

  // Sort state types (must be defined before Props interface)
  type SortDirection = 'asc' | 'desc';
  type ColumnSort = { columnName: string; direction: SortDirection };

  interface Props {
    data: AutopsyData;
    highlightedLogIndex?: number | null;
    selectedLogIndex?: number | null;
    hiddenCallSites?: Set<string>;
    frameFilter?: string | null;
    columnOrders?: Record<string, string[]>;
    computedColumns?: Record<string, ComputedColumn[]>;
    collapsedCallSites?: Record<string, boolean>;
    columnSorts?: Record<string, ColumnSort[]>;
    onShowInHistory?: (logIndex: number) => void;
    onEntryClick?: (logIndex: number, stackTraceId?: string) => void;
    onHideCallSite?: (callSiteKey: string) => void;
    onShowCallSite?: (callSiteKey: string) => void;
    onColumnOrderChange?: (callSiteKey: string, newOrder: string[]) => void;
    onOpenComputedColumnModal?: (callSite: CallSite, existingColumn?: ComputedColumn) => void;
  }

  let {
    data,
    highlightedLogIndex = null,
    selectedLogIndex = null,
    hiddenCallSites = new Set<string>(),
    frameFilter = null,
    columnOrders = {},
    computedColumns = {},
    collapsedCallSites = $bindable({}),
    columnSorts = $bindable({}),
    onShowInHistory,
    onEntryClick,
    onHideCallSite,
    onShowCallSite,
    onColumnOrderChange,
    onOpenComputedColumnModal,
  }: Props = $props();

  // Drag-and-drop state
  let draggedColumn = $state<{ callSiteKey: string; columnName: string } | null>(null);
  let dropTarget = $state<{ callSiteKey: string; index: number } | null>(null);

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

  function toggleCollapse(callSite: CallSite) {
    const key = getCallSiteKey(callSite);
    // If the key is undefined, initialize it to the opposite of the default
    if (collapsedCallSites[key] === undefined) {
      const isDashboard = callSite.is_dashboard ?? false;
      collapsedCallSites[key] = !isDashboard;
    } else {
      collapsedCallSites[key] = !collapsedCallSites[key];
    }
  }

  function isCollapsed(callSite: CallSite): boolean {
    const key = getCallSiteKey(callSite);
    // Dashboard call sites are collapsed by default
    const isDashboard = callSite.is_dashboard ?? false;
    return collapsedCallSites[key] ?? isDashboard;
  }

  function handleHideCallSite(callSiteKey: string) {
    // Auto-collapse when hiding
    collapsedCallSites[callSiteKey] = true;
    onHideCallSite?.(callSiteKey);
  }

  function handleShowCallSite(callSiteKey: string) {
    // Ensure expanded when showing
    collapsedCallSites[callSiteKey] = false;
    onShowCallSite?.(callSiteKey);
  }

  function getFilename(callSite: CallSite): string {
    const parts = callSite.filename.split("/");
    return parts[parts.length - 1];
  }

  // Get all unique column names (argument names) for a call site
  function getColumnNames(callSite: CallSite): string[] {
    const callSiteKey = getCallSiteKey(callSite);

    // Get regular columns
    const columnNames = new Set<string>();
    for (const valueGroup of callSite.value_groups) {
      if (valueGroup.values) {
        for (const value of valueGroup.values) {
          if (value.name) {
            columnNames.add(value.name);
          }
        }
      }
    }

    const regularColumns = Array.from(columnNames);

    // Get computed columns for this call site
    const computed = computedColumns[callSiteKey] || [];
    const computedColumnNames = computed.map(col => `computed:${col.id}`);

    const allColumns = [...regularColumns, ...computedColumnNames];

    // If we have a stored order, use it and append any new columns
    const storedOrder = columnOrders[callSiteKey];
    if (storedOrder) {
      // Filter stored order to only include columns that still exist
      const orderedCols = storedOrder.filter(col => allColumns.includes(col));
      // Add any new columns not in stored order (preserve original order)
      const newCols = allColumns.filter(col => !storedOrder.includes(col));
      return [...orderedCols, ...newCols];
    }

    // Return columns in their natural order from the data (matches call site order)
    return allColumns;
  }

  // Check if a value is a primitive type that can be sorted
  function isSortable(value: unknown): boolean {
    if (value === null || value === undefined) return true;
    const type = typeof value;
    return type === 'string' || type === 'number' || type === 'boolean';
  }

  // Check if a column is sortable (all non-undefined values are primitives)
  function isColumnSortable(callSite: CallSite, columnName: string): boolean {
    // Check if computed column
    if (columnName.startsWith('computed:')) {
      const columnId = columnName.substring('computed:'.length);
      const callSiteKey = getCallSiteKey(callSite);
      const computedCol = computedColumns[callSiteKey]?.find(c => c.id === columnId);
      if (!computedCol) return false;

      // Evaluate for all rows and check sortability
      const results = callSite.value_groups.map(vg =>
        evaluateComputedColumn(computedCol.expression, vg, data)
      );
      return isComputedColumnSortable(results);
    }

    // Regular column check
    for (const valueGroup of callSite.value_groups) {
      const value = getValueForColumn(valueGroup, columnName, callSite);
      if (value !== undefined && !isSortable(value)) {
        return false;
      }
    }
    return true;
  }

  // Get the current sort state for a column
  function getColumnSortState(callSite: CallSite, columnName: string): SortDirection | null {
    const callSiteKey = getCallSiteKey(callSite);
    const sorts = columnSorts[callSiteKey] || [];
    const sort = sorts.find(s => s.columnName === columnName);
    return sort?.direction || null;
  }

  // Toggle sort for a column: null -> desc -> asc -> null
  function toggleSort(callSite: CallSite, columnName: string) {
    const callSiteKey = getCallSiteKey(callSite);
    const sorts = columnSorts[callSiteKey] || [];
    const existingIndex = sorts.findIndex(s => s.columnName === columnName);

    if (existingIndex === -1) {
      // Not sorted, add as descending
      columnSorts[callSiteKey] = [...sorts, { columnName, direction: 'desc' }];
    } else {
      const currentDirection = sorts[existingIndex].direction;
      if (currentDirection === 'desc') {
        // Change to ascending
        const newSorts = [...sorts];
        newSorts[existingIndex] = { columnName, direction: 'asc' };
        columnSorts[callSiteKey] = newSorts;
      } else {
        // Remove sort
        columnSorts[callSiteKey] = sorts.filter((_, i) => i !== existingIndex);
      }
    }
  }

  // Get the icon for a column's sort state
  function getSortIcon(direction: SortDirection | null): string {
    if (direction === 'desc') return '▼';
    if (direction === 'asc') return '▲';
    return '─';
  }

  // Get the sort priority number (1-indexed) for display
  function getSortPriority(callSite: CallSite, columnName: string): number | null {
    const callSiteKey = getCallSiteKey(callSite);
    const sorts = columnSorts[callSiteKey] || [];
    const index = sorts.findIndex(s => s.columnName === columnName);
    return index === -1 ? null : index + 1;
  }

  // Get filtered and sorted call sites (dashboard at bottom)
  let filteredCallSites = $derived.by(() => {
    const regular: CallSite[] = [];
    const dashboard: CallSite[] = [];

    for (const callSite of data.call_sites) {
      const callSiteKey = getCallSiteKey(callSite);
      const isHidden = hiddenCallSites.has(callSiteKey);
      const isDashboard = callSite.is_dashboard ?? false;

      // Filter value_groups based on frameFilter if active
      let filteredValueGroups = callSite.value_groups;
      if (frameFilter) {
        filteredValueGroups = callSite.value_groups.filter(valueGroup =>
          stackTraceContainsFrame(valueGroup.stack_trace_id, frameFilter)
        );
      }

      // Apply sorting if configured
      const sorts = columnSorts[callSiteKey] || [];
      if (sorts.length > 0) {
        filteredValueGroups = [...filteredValueGroups].sort((a, b) => {
          // Compare by each sort column in priority order
          for (const sort of sorts) {
            const aVal = getValueForColumn(a, sort.columnName, callSite);
            const bVal = getValueForColumn(b, sort.columnName, callSite);

            // Handle undefined values (always sort to end)
            if (aVal === undefined && bVal === undefined) continue;
            if (aVal === undefined) return 1;
            if (bVal === undefined) return -1;

            // Handle null values (sort after defined values but before undefined)
            if (aVal === null && bVal === null) continue;
            if (aVal === null) return 1;
            if (bVal === null) return -1;

            // Compare primitive values
            let comparison = 0;
            if (typeof aVal === 'string' && typeof bVal === 'string') {
              comparison = aVal.localeCompare(bVal);
            } else if (typeof aVal === 'number' && typeof bVal === 'number') {
              comparison = aVal - bVal;
            } else if (typeof aVal === 'boolean' && typeof bVal === 'boolean') {
              comparison = (aVal === bVal) ? 0 : (aVal ? 1 : -1);
            } else {
              // Mixed types - convert to string for comparison
              comparison = String(aVal).localeCompare(String(bVal));
            }

            if (comparison !== 0) {
              return sort.direction === 'asc' ? comparison : -comparison;
            }
          }

          // If all sort columns are equal, fall back to log_index
          return a.log_index - b.log_index;
        });
      }

      // Create filtered call site
      const filteredCallSite: CallSite = {
        ...callSite,
        value_groups: filteredValueGroups,
      };

      // Include all call sites (even hidden ones) - they'll be collapsed/lowlighted
      if (isDashboard) {
        dashboard.push(filteredCallSite);
      } else {
        regular.push(filteredCallSite);
      }
    }

    return [...regular, ...dashboard];
  });

  // Get value for a specific column in a value group
  function getValueForColumn(
    valueGroup: ValueGroup,
    columnName: string,
    callSite: CallSite
  ): unknown | undefined {
    // Check if this is a computed column
    if (columnName.startsWith('computed:')) {
      const columnId = columnName.substring('computed:'.length);
      const callSiteKey = getCallSiteKey(callSite);
      const computedCol = computedColumns[callSiteKey]?.find(c => c.id === columnId);
      if (computedCol) {
        const result = evaluateComputedColumn(computedCol.expression, valueGroup, data);
        return result.error ? { __error: result.error } : result.value;
      }
      return undefined;
    }

    // Regular column
    if (!valueGroup.values) return undefined;
    const value = valueGroup.values.find((v) => v.name === columnName);
    return value?.value;
  }

  function handleRowClick(valueGroup: ValueGroup) {
    onEntryClick?.(valueGroup.log_index, valueGroup.stack_trace_id);
  }

  function getComputedColumn(callSite: CallSite, columnName: string): ComputedColumn | undefined {
    if (!columnName.startsWith('computed:')) return undefined;
    const columnId = columnName.substring('computed:'.length);
    const callSiteKey = getCallSiteKey(callSite);
    return computedColumns[callSiteKey]?.find(c => c.id === columnId);
  }

  function handleColumnDoubleClick(callSite: CallSite, columnName: string) {
    if (columnName.startsWith('computed:')) {
      const column = getComputedColumn(callSite, columnName);
      if (column && onOpenComputedColumnModal) {
        onOpenComputedColumnModal(callSite, column);
      }
    }
  }

  // Drag-and-drop handlers
  function handleDragStart(callSite: CallSite, columnName: string, e: DragEvent) {
    const callSiteKey = getCallSiteKey(callSite);
    draggedColumn = { callSiteKey, columnName };
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', columnName);
    }
  }

  function handleDragOver(callSite: CallSite, index: number, e: DragEvent) {
    e.preventDefault();
    const callSiteKey = getCallSiteKey(callSite);
    if (draggedColumn && draggedColumn.callSiteKey === callSiteKey) {
      if (e.dataTransfer) {
        e.dataTransfer.dropEffect = 'move';
      }

      // Adjust the drop target index to account for the dragged column's removal
      const columns = getColumnNames(callSite);
      const draggedIndex = columns.indexOf(draggedColumn.columnName);

      // If dragging from left to right, the visual indicator should be one position ahead
      // because the dragged column will be removed first
      const adjustedIndex = draggedIndex < index ? index + 1 : index;

      dropTarget = { callSiteKey, index: adjustedIndex };
    }
  }

  function handleDragLeave() {
    dropTarget = null;
  }

  function handleDrop(callSite: CallSite, targetIndex: number, e: DragEvent) {
    e.preventDefault();
    const callSiteKey = getCallSiteKey(callSite);

    if (!draggedColumn || draggedColumn.callSiteKey !== callSiteKey) {
      draggedColumn = null;
      dropTarget = null;
      return;
    }

    const columns = getColumnNames(callSite);
    const draggedIndex = columns.indexOf(draggedColumn.columnName);

    if (draggedIndex === -1) {
      draggedColumn = null;
      dropTarget = null;
      return;
    }

    // Create new order
    const newOrder = [...columns];
    newOrder.splice(draggedIndex, 1);
    newOrder.splice(targetIndex, 0, draggedColumn.columnName);

    onColumnOrderChange?.(callSiteKey, newOrder);

    draggedColumn = null;
    dropTarget = null;
  }

  function handleDragEnd() {
    draggedColumn = null;
    dropTarget = null;
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
    {#each filteredCallSites as callSite (getCallSiteKey(callSite))}
      {@const callSiteKey = getCallSiteKey(callSite)}
      {@const isHidden = hiddenCallSites.has(callSiteKey)}
      {@const isDashboard = callSite.is_dashboard ?? false}
      <div class="call-site" class:hidden={isHidden}>
        {#if isDashboard}
          <!-- Dashboard call site display -->
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
              <label class="call-site-checkbox" onclick={(e) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  checked={!hiddenCallSites.has(callSiteKey)}
                  onclick={(e) => e.stopPropagation()}
                  onchange={(e) => {
                    e.stopPropagation();
                    if (e.currentTarget.checked) {
                      handleShowCallSite(callSiteKey);
                    } else {
                      handleHideCallSite(callSiteKey);
                    }
                  }}
                />
              </label>
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
              <span class="dashboard-badge">dashboard</span>
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
              ...{callSite.value_groups.length} {callSite.value_groups.length === 1 ? "invocation" : "invocations"}
            </div>
          {:else}
            <div class="value-groups">
              {#each callSite.value_groups as valueGroup}
                <div
                  class="value-group"
                  class:highlighted={highlightedLogIndex === valueGroup.log_index}
                  class:selected={selectedLogIndex === valueGroup.log_index}
                  class:clickable={valueGroup.stack_trace_id !== undefined}
                  data-log-index={valueGroup.log_index}
                  onclick={() => handleRowClick(valueGroup)}
                >
                  <div class="value-group-row">
                    <span class="log-number">#{valueGroup.log_index}</span>
                    {#if valueGroup.dashboard_type === "count"}
                      <span class="dashboard-label">count:</span>
                      <TreeView value={valueGroup.value} />
                    {:else if valueGroup.dashboard_type === "hist"}
                      <span class="dashboard-label">hist:</span>
                      <TreeView value={valueGroup.value} />
                    {:else if valueGroup.dashboard_type === "timeline"}
                      <span class="dashboard-label">timeline:</span>
                      <span class="dashboard-text">{valueGroup.event_name}</span>
                    {:else if valueGroup.dashboard_type === "happened"}
                      <span class="dashboard-label">happened</span>
                      {#if valueGroup.message}
                        <span class="dashboard-text">: {valueGroup.message}</span>
                      {/if}
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        {:else if getColumnNames(callSite).length > 0}
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
                  colspan={getColumnNames(callSite).length + 2}
                  class="call-site-info"
                >
                  <div class="header-left">
                    <label class="call-site-checkbox" onclick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={!hiddenCallSites.has(callSiteKey)}
                        onclick={(e) => e.stopPropagation()}
                        onchange={(e) => {
                          e.stopPropagation();
                          if (e.currentTarget.checked) {
                            handleShowCallSite(callSiteKey);
                          } else {
                            handleHideCallSite(callSiteKey);
                          }
                        }}
                      />
                    </label>
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
                    {#if isDashboard}
                      <span class="dashboard-badge">dashboard</span>
                    {/if}
                  </div>
                </th>
              </tr>
              <tr>
                <th class="log-number-header">#</th>
                {#each getColumnNames(callSite) as columnName, columnIndex}
                  {@const sortable = isColumnSortable(callSite, columnName)}
                  {@const sortState = getColumnSortState(callSite, columnName)}
                  {@const sortPriority = getSortPriority(callSite, columnName)}
                  {@const isDragging = draggedColumn?.callSiteKey === getCallSiteKey(callSite) && draggedColumn?.columnName === columnName}
                  {@const isDropTarget = dropTarget?.callSiteKey === getCallSiteKey(callSite) && dropTarget?.index === columnIndex}
                  {@const isComputed = columnName.startsWith('computed:')}
                  {@const computedCol = isComputed ? getComputedColumn(callSite, columnName) : undefined}
                  {@const displayName = isComputed && computedCol ? getComputedColumnDisplayName(computedCol) : columnName}
                  <th
                    class="column-header"
                    class:computed-column={isComputed}
                    class:dragging={isDragging}
                    class:drop-target-before={isDropTarget}
                    draggable="true"
                    ondragstart={(e) => handleDragStart(callSite, columnName, e)}
                    ondragover={(e) => handleDragOver(callSite, columnIndex, e)}
                    ondragleave={handleDragLeave}
                    ondrop={(e) => handleDrop(callSite, columnIndex, e)}
                    ondragend={handleDragEnd}
                    ondblclick={() => handleColumnDoubleClick(callSite, columnName)}
                    title={isComputed && computedCol ? `Expression: ${computedCol.expression}` : ''}
                  >
                    <div class="column-header-content">
                      {#if isComputed}
                        <span class="computed-icon">ƒ</span>
                      {/if}
                      <span class="column-name">{displayName}</span>
                      {#if sortable}
                        <button
                          class="sort-button"
                          class:sorted={sortState !== null}
                          onclick={(e) => {
                            e.stopPropagation();
                            toggleSort(callSite, columnName);
                          }}
                          title={sortState === null
                            ? 'Click to sort descending'
                            : sortState === 'desc'
                              ? 'Click to sort ascending'
                              : 'Click to remove sort'}
                        >
                          {getSortIcon(sortState)}
                          {#if sortPriority !== null && (columnSorts[getCallSiteKey(callSite)]?.length ?? 0) > 1}
                            <span class="sort-priority">{sortPriority}</span>
                          {/if}
                        </button>
                      {/if}
                    </div>
                  </th>
                {/each}
                {#if dropTarget?.callSiteKey === getCallSiteKey(callSite) && dropTarget?.index === getColumnNames(callSite).length}
                  <th class="drop-target-after"></th>
                {/if}
                <th class="add-column-header">
                  <button
                    class="add-column-button"
                    onclick={(e) => {
                      e.stopPropagation();
                      onOpenComputedColumnModal?.(callSite);
                    }}
                    title="Add computed column"
                  >
                    +
                  </button>
                </th>
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
                    colspan={getColumnNames(callSite).length + 2}
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
                      {@const cellValue = getValueForColumn(valueGroup, columnName, callSite)}
                      <td class="value-cell">
                        {#if cellValue !== undefined}
                          {#if typeof cellValue === 'object' && cellValue !== null && '__error' in cellValue}
                            <span class="computed-error">{cellValue.__error}</span>
                          {:else}
                            <TreeView value={cellValue} />
                          {/if}
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
              <label class="call-site-checkbox" onclick={(e) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  checked={!hiddenCallSites.has(callSiteKey)}
                  onclick={(e) => e.stopPropagation()}
                  onchange={(e) => {
                    e.stopPropagation();
                    if (e.currentTarget.checked) {
                      handleShowCallSite(callSiteKey);
                    } else {
                      handleHideCallSite(callSiteKey);
                    }
                  }}
                />
              </label>
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
                    {#if valueGroup.values && valueGroup.values.length === 0 && valueGroup.name}
                      <span class="log-name-only">{valueGroup.name}</span>
                    {:else if valueGroup.values}
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
    transition: opacity 0.2s, background-color 0.2s;
  }

  .call-site.hidden {
    opacity: 0.5;
    background: #f3f4f6;
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
    position: relative;
  }

  .column-header {
    cursor: grab;
    transition: background-color 0.2s, opacity 0.2s;
  }

  .column-header:active {
    cursor: grabbing;
  }

  .column-header.dragging {
    opacity: 0.5;
    background-color: #f0f0f0;
  }

  .column-header.drop-target-before::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    background-color: #2563eb;
    z-index: 100;
  }

  .drop-target-after {
    padding: 0 !important;
    width: 3px !important;
    background-color: #2563eb;
    position: relative;
  }

  .column-header-content {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .column-name {
    flex: 0 0 auto;
  }

  .sort-button {
    flex: 0 0 auto;
    background: transparent;
    border: 1px solid #cbd5e1;
    border-radius: 3px;
    padding: 2px 6px;
    cursor: pointer;
    font-size: 0.75rem;
    color: #64748b;
    transition: all 0.2s;
    font-family: monospace;
    display: flex;
    align-items: center;
    gap: 2px;
    min-width: 1.9rem;
    justify-content: center;
  }

  .sort-button:hover {
    background: #f1f5f9;
    border-color: #94a3b8;
    color: #475569;
  }

  .sort-button.sorted {
    background: #881391;
    border-color: #881391;
    color: white;
  }

  .sort-button.sorted:hover {
    background: #6b0f73;
    border-color: #6b0f73;
  }

  .sort-priority {
    font-size: 0.65rem;
    font-weight: 600;
    margin-left: 1px;
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

  @media (max-width: 768px) {
    .values {
      flex-direction: column;
    }

    .value-item {
      width: 100%;
    }
  }

  /* Computed column styles */
  .computed-column {
    background: #faf5ff !important;
    cursor: pointer;
  }

  .computed-column:hover {
    background: #f3e8ff !important;
  }

  .computed-icon {
    color: #9333ea;
    font-weight: bold;
    font-size: 0.9rem;
    margin-right: 0.25rem;
  }

  .add-column-header {
    padding: 0.5rem;
    border-bottom: 2px solid #e5e5e5;
    width: 3rem;
    background: #f9f9f9;
  }

  .add-column-button {
    background: #f3f4f6;
    border: 1px dashed #9ca3af;
    border-radius: 4px;
    width: 2rem;
    height: 2rem;
    font-size: 1.2rem;
    color: #6b7280;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .add-column-button:hover {
    background: #e5e7eb;
    border-color: #6b7280;
    color: #374151;
  }

  .computed-error {
    color: #dc2626;
    font-style: italic;
    font-size: 0.85rem;
  }
</style>
