<script lang="ts">
  import type { AutopsyData, CallSite, ValueGroup, ComputedColumn, ColumnFilters, ColumnFilter, LogMark } from "./types";
  import type { EvaluationResult } from "./computedColumns";
  import type { ColumnProfile } from "./columnProfiler";
  import TreeView from "./TreeView.svelte";
  import CodeLocation from "./CodeLocation.svelte";
  import FilterWidgets from "./FilterWidgets.svelte";
  import { tick } from "svelte";
  import { evaluateComputedColumnBatch, isComputedColumnSortable, getComputedColumnDisplayName, generateColumnId, isFrameIndexStable } from "./computedColumns";
  import { profileColumn } from "./columnProfiler";
  import { ListFilter } from "lucide-svelte";

  // Drag-and-drop types for stack variables
  interface PathSegment {
    key: string | number;
    type: 'object' | 'array';
  }

  interface StackVariableDragPayload {
    type: 'stack-variable';
    frameIndex: number;
    path: PathSegment[];
    sourceLogIndex: number;
    frameFunctionName?: string;
    frameFilename?: string;
    frameLineNumber?: number;
    baseExpression?: string;
  }

  // Sort state types (must be defined before Props interface)
  type SortDirection = 'asc' | 'desc';
  type ColumnSort = { columnName: string; direction: SortDirection };

  // Extended CallSite type to track filtered logs
  interface FilteredCallSite extends CallSite {
    filtered_value_groups?: ValueGroup[]; // Logs that were filtered out
  }

  interface Props {
    data: AutopsyData;
    highlightedLogIndex?: number | null;
    selectedLogIndex?: number | null;
    hiddenCallSites?: Set<string>;
    frameFilter?: string | null;
    testFilter?: string | null;
    rangeFilter?: { start: number; end: number } | null;
    hoveredFrameKey?: string | null;
    selectedFrameKeys?: Set<string>;
    columnOrders?: Record<string, string[]>;
    computedColumns?: Record<string, ComputedColumn[]>;
    logMarks?: Record<number, LogMark>;
    collapsedCallSites?: Record<string, boolean>;
    columnSorts?: Record<string, ColumnSort[]>;
    hiddenColumns?: Record<string, Set<string>>;
    columnFilters?: Record<string, ColumnFilters>;
    onShowInHistory?: (logIndex: number) => void;
    onEntryClick?: (logIndex: number, stackTraceId?: string) => void;
    onHideCallSite?: (callSiteKey: string) => void;
    onShowCallSite?: (callSiteKey: string) => void;
    onColumnOrderChange?: (callSiteKey: string, newOrder: string[]) => void;
    onOpenComputedColumnModal?: (callSite: CallSite, existingColumn?: ComputedColumn) => void;
    onSaveComputedColumn?: (column: ComputedColumn) => void;
    onHideColumn?: (callSiteKey: string, columnName: string) => void;
    onShowColumn?: (callSiteKey: string, columnName: string) => void;
  }

  let {
    data,
    highlightedLogIndex = null,
    selectedLogIndex = null,
    hiddenCallSites = new Set<string>(),
    frameFilter = null,
    testFilter = null,
    rangeFilter = null,
    hoveredFrameKey = null,
    selectedFrameKeys = new Set<string>(),
    columnOrders = {},
    computedColumns = {},
    logMarks = {},
    collapsedCallSites = $bindable({}),
    columnSorts = $bindable({}),
    hiddenColumns = $bindable({}),
    columnFilters = $bindable({}),
    onShowInHistory,
    onEntryClick,
    onHideCallSite,
    onShowCallSite,
    onColumnOrderChange,
    onOpenComputedColumnModal,
    onSaveComputedColumn,
    onHideColumn,
    onShowColumn,
  }: Props = $props();

  // Drag-and-drop state
  let draggedColumn = $state<{ callSiteKey: string; columnName: string } | null>(null);
  let dropTarget = $state<{ callSiteKey: string; index: number } | null>(null);

  // Dropdown menu state - track which column's dropdown is open
  let openDropdown = $state<{ callSiteKey: string; columnName: string; top: number; left: number } | null>(null);

  // Column resize state
  let resizingColumn = $state<{ callSiteKey: string; columnName: string; startX: number; startWidth: number } | null>(null);
  let columnWidths = $state<Record<string, Record<string, number>>>({});

  // Track which call sites have expanded filtered logs
  let expandedFilteredLogs = $state<Set<string>>(new Set());

  // Track table container refs for initial width computation
  let tableContainers = $state<Record<string, HTMLDivElement | null>>({});

  // Track table header refs for sticky behavior
  let tableHeaders = $state<Record<string, HTMLTableSectionElement | null>>({});

  // Track floating header state: which headers should show their floating clones
  let floatingHeaders = $state<Record<string, {
    visible: boolean;
    top: number;
    left: number;
    width: number;
    scrollLeft: number;
    columnWidths: number[];
  }>>({});

  // Cache for computed column values (callSiteKey:columnId -> log_index -> value)
  let computedColumnCache = $state<Map<string, Map<number, EvaluationResult>>>(new Map());

  // Cache for column profiles (callSiteKey:columnName -> profile)
  let columnProfileCache = $state<Map<string, ColumnProfile>>(new Map());

  // Cache for Python expression filter results (callSiteKey:columnName -> log_index -> boolean)
  let pythonFilterCache = $state<Map<string, Map<number, boolean>>>(new Map());

  // Pre-compute all computed columns when data or columns change
  $effect(() => {
    // Trigger reactivity on data and computedColumns
    const _ = [data, computedColumns];

    // Async function to recompute all computed columns
    (async () => {
      const newCache = new Map<string, Map<number, EvaluationResult>>();

      for (const callSite of data.call_sites) {
        const callSiteKey = getCallSiteKey(callSite);
        const columns = computedColumns[callSiteKey] || [];

        for (const column of columns) {
          const cacheKey = `${callSiteKey}:${column.id}`;

          try {
            // Batch evaluate Python
            const results = await evaluateComputedColumnBatch(
              column.expression,
              callSite.value_groups,
              data
            );

            const resultMap = new Map<number, EvaluationResult>();
            callSite.value_groups.forEach((vg, i) => {
              resultMap.set(vg.log_index, results[i]);
            });
            newCache.set(cacheKey, resultMap);
          } catch (error) {
            console.error(`Error evaluating computed column ${column.id}:`, error);
          }
        }
      }

      computedColumnCache = newCache;
    })();
  });

  // Pre-compute Python expression filters when data or filters change
  $effect(() => {
    // Trigger reactivity on data and columnFilters
    const _ = [data, columnFilters];

    // Async function to evaluate all Python expression filters
    (async () => {
      const newFilterCache = new Map<string, Map<number, boolean>>();

      // Import pythonExecutor
      const { pythonExecutor } = await import('./pythonExecutor');

      for (const callSite of data.call_sites) {
        const callSiteKey = getCallSiteKey(callSite);
        const filters = columnFilters[callSiteKey];

        if (!filters) continue;

        for (const [columnName, filter] of Object.entries(filters)) {
          if (filter.type !== 'python_expression') continue;

          const cacheKey = `${callSiteKey}:${columnName}`;

          try {
            // Ensure Pyodide is initialized
            if (!pythonExecutor.isReady()) {
              await pythonExecutor.initialize();
            }

            // Get the actual values for this column
            const values = callSite.value_groups.map(vg =>
              getValueForColumn(vg, columnName, callSite)
            );

            // Use executeBatch to evaluate the Python expression with 'value' as the variable
            const results = await pythonExecutor.executeBatch(
              filter.expression,
              values,
              'value'
            );

            // Store boolean results in cache
            const resultMap = new Map<number, boolean>();
            callSite.value_groups.forEach((vg, i) => {
              const result = results[i];
              // Convert result to boolean (truthy/falsy)
              const passes = !result.error && !!result.value;
              resultMap.set(vg.log_index, passes);
            });
            newFilterCache.set(cacheKey, resultMap);
          } catch (error) {
            console.error(`Error evaluating Python filter for ${columnName}:`, error);
            // On error, create a cache that fails all values
            const resultMap = new Map<number, boolean>();
            callSite.value_groups.forEach(vg => {
              resultMap.set(vg.log_index, false);
            });
            newFilterCache.set(cacheKey, resultMap);
          }
        }
      }

      pythonFilterCache = newFilterCache;
    })();
  });

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

  function logBelongsToTest(logIndex: number, testNodeid: string): boolean {
    if (!data.tests) return false;
    const test = data.tests.find(t => t.nodeid === testNodeid);
    if (!test) return false;
    if (test.start_log_index === undefined || test.end_log_index === undefined) return false;
    return logIndex >= test.start_log_index && logIndex <= test.end_log_index;
  }

  // Check if a log should be highlighted based on frame context
  function shouldHighlightForFrameContext(stackTraceId: string | undefined): boolean {
    if (hoveredFrameKey && stackTraceContainsFrame(stackTraceId, hoveredFrameKey)) {
      return true;
    }
    for (const selectedKey of selectedFrameKeys) {
      if (stackTraceContainsFrame(stackTraceId, selectedKey)) {
        return true;
      }
    }
    return false;
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

  function toggleFilteredLogs(callSite: FilteredCallSite) {
    const key = getCallSiteKey(callSite);
    const newSet = new Set(expandedFilteredLogs);
    if (newSet.has(key)) {
      newSet.delete(key);
    } else {
      newSet.add(key);
    }
    expandedFilteredLogs = newSet;
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
  function getColumnNames(callSite: CallSite | FilteredCallSite): string[] {
    const callSiteKey = getCallSiteKey(callSite);

    // Get regular columns from both visible and filtered value groups
    const columnNames = new Set<string>();
    const allValueGroups = [
      ...callSite.value_groups,
      ...((callSite as FilteredCallSite).filtered_value_groups || [])
    ];

    for (const valueGroup of allValueGroups) {
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

    // Filter out hidden columns
    const hiddenCols = hiddenColumns[callSiteKey] || new Set<string>();
    const visibleColumns = allColumns.filter(col => !hiddenCols.has(col));

    // If we have a stored order, use it and append any new columns
    const storedOrder = columnOrders[callSiteKey];
    if (storedOrder) {
      // Filter stored order to only include columns that still exist and are visible
      const orderedCols = storedOrder.filter(col => visibleColumns.includes(col));
      // Add any new columns not in stored order (preserve original order)
      const newCols = visibleColumns.filter(col => !storedOrder.includes(col));
      return [...orderedCols, ...newCols];
    }

    // Return columns in their natural order from the data (matches call site order)
    return visibleColumns;
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
      const cacheKey = `${callSiteKey}:${columnId}`;

      // Use cached results for sortability check
      const cachedResults = computedColumnCache.get(cacheKey);
      if (!cachedResults) return false;

      const results = callSite.value_groups.map(vg =>
        cachedResults.get(vg.log_index) || { value: undefined }
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

  // Dropdown menu functions
  function toggleDropdown(callSite: CallSite, columnName: string, event: MouseEvent) {
    event.stopPropagation();
    const callSiteKey = getCallSiteKey(callSite);
    if (openDropdown?.callSiteKey === callSiteKey && openDropdown?.columnName === columnName) {
      openDropdown = null;
    } else {
      // Calculate position relative to the clicked button
      const button = event.currentTarget as HTMLElement;
      const rect = button.getBoundingClientRect();
      openDropdown = {
        callSiteKey,
        columnName,
        top: rect.bottom + 4,
        left: rect.right - 180  // Align right edge (dropdown min-width is 180px)
      };
    }
  }

  function closeDropdown() {
    openDropdown = null;
  }

  function isDropdownOpen(callSite: CallSite, columnName: string): boolean {
    const callSiteKey = getCallSiteKey(callSite);
    return openDropdown?.callSiteKey === callSiteKey && openDropdown?.columnName === columnName;
  }

  function handleSortAscending(callSite: CallSite, columnName: string) {
    const callSiteKey = getCallSiteKey(callSite);
    const sorts = columnSorts[callSiteKey] || [];
    const existingIndex = sorts.findIndex(s => s.columnName === columnName);

    if (existingIndex === -1) {
      columnSorts[callSiteKey] = [...sorts, { columnName, direction: 'asc' }];
    } else {
      const newSorts = [...sorts];
      newSorts[existingIndex] = { columnName, direction: 'asc' };
      columnSorts[callSiteKey] = newSorts;
    }
    closeDropdown();
  }

  function handleSortDescending(callSite: CallSite, columnName: string) {
    const callSiteKey = getCallSiteKey(callSite);
    const sorts = columnSorts[callSiteKey] || [];
    const existingIndex = sorts.findIndex(s => s.columnName === columnName);

    if (existingIndex === -1) {
      columnSorts[callSiteKey] = [...sorts, { columnName, direction: 'desc' }];
    } else {
      const newSorts = [...sorts];
      newSorts[existingIndex] = { columnName, direction: 'desc' };
      columnSorts[callSiteKey] = newSorts;
    }
    closeDropdown();
  }

  function handleResetSort(callSite: CallSite, columnName: string) {
    const callSiteKey = getCallSiteKey(callSite);
    const sorts = columnSorts[callSiteKey] || [];
    columnSorts[callSiteKey] = sorts.filter(s => s.columnName !== columnName);
    closeDropdown();
  }

  // Get or create column profile
  function getColumnProfile(callSite: CallSite, columnName: string): ColumnProfile {
    const callSiteKey = getCallSiteKey(callSite);
    const cacheKey = `${callSiteKey}:${columnName}`;

    // Check cache first
    const cached = columnProfileCache.get(cacheKey);
    if (cached) {
      return cached;
    }

    // Find the original unfiltered call site from data.call_sites
    // This ensures we profile the full dataset, not the filtered one
    const originalCallSite = data.call_sites.find(cs => getCallSiteKey(cs) === callSiteKey);
    if (!originalCallSite) {
      // Fallback to the passed callSite if we can't find the original
      // This shouldn't happen in normal operation
      const profile = profileColumn(callSite, columnName, {}, computedColumnCache, callSiteKey);
      columnProfileCache.set(cacheKey, profile);
      return profile;
    }

    // Profile the column using the original unfiltered data
    const profile = profileColumn(originalCallSite, columnName, {}, computedColumnCache, callSiteKey);

    // Cache it
    columnProfileCache.set(cacheKey, profile);

    return profile;
  }

  // Handle filter changes
  function handleFilterChange(callSite: CallSite, columnName: string, filter: ColumnFilter | null) {
    const callSiteKey = getCallSiteKey(callSite);

    if (!columnFilters[callSiteKey]) {
      columnFilters[callSiteKey] = {};
    }

    if (filter === null) {
      // Remove filter
      delete columnFilters[callSiteKey][columnName];

      // Clean up empty filter objects
      if (Object.keys(columnFilters[callSiteKey]).length === 0) {
        delete columnFilters[callSiteKey];
      }
    } else {
      // Set filter
      columnFilters[callSiteKey][columnName] = filter;
    }

    // Trigger reactivity
    columnFilters = { ...columnFilters };
  }

  function handleHideColumn(callSite: CallSite, columnName: string) {
    const callSiteKey = getCallSiteKey(callSite);
    const currentHidden = hiddenColumns[callSiteKey] || new Set<string>();
    const newHidden = new Set(currentHidden);
    newHidden.add(columnName);
    hiddenColumns[callSiteKey] = newHidden;
    onHideColumn?.(callSiteKey, columnName);
    closeDropdown();
  }

  // Check if a value passes a filter
  function valuePassesFilter(
    value: unknown,
    filter: ColumnFilter,
    callSiteKey: string,
    columnName: string,
    logIndex: number
  ): boolean {
    if (filter.type === 'numeric_range') {
      if (typeof value !== 'number') return false;
      return value >= filter.min && value <= filter.max;
    }

    if (filter.type === 'enum_values') {
      // Handle both strings and booleans
      if (typeof value !== 'string' && typeof value !== 'boolean') return false;
      return filter.selectedValues.has(String(value));
    }

    if (filter.type === 'regex') {
      if (typeof value !== 'string') return false;
      try {
        const regex = new RegExp(filter.pattern);
        return regex.test(value);
      } catch {
        return false;
      }
    }

    if (filter.type === 'python_expression') {
      // Look up cached result
      const cacheKey = `${callSiteKey}:${columnName}`;
      const cachedResults = pythonFilterCache.get(cacheKey);
      if (cachedResults) {
        return cachedResults.get(logIndex) ?? false;
      }
      // If not yet cached, fail by default (filter is still evaluating)
      return false;
    }

    return true;
  }

  // Check if a value group passes all column filters
  function valueGroupPassesFilters(
    valueGroup: ValueGroup,
    callSite: CallSite,
    callSiteKey: string,
    filters: ColumnFilters
  ): boolean {
    for (const [columnName, filter] of Object.entries(filters)) {
      const value = getValueForColumn(valueGroup, columnName, callSite);

      // Handle undefined values - they don't pass any filter
      if (value === undefined || value === null) {
        return false;
      }

      if (!valuePassesFilter(value, filter, callSiteKey, columnName, valueGroup.log_index)) {
        return false;
      }
    }

    return true;
  }

  // Get filtered and sorted call sites (dashboard at bottom)
  let filteredCallSites = $derived.by(() => {
    const regular: FilteredCallSite[] = [];
    const dashboard: FilteredCallSite[] = [];

    for (const callSite of data.call_sites) {
      const callSiteKey = getCallSiteKey(callSite);
      const isHidden = hiddenCallSites.has(callSiteKey);
      const isDashboard = callSite.is_dashboard ?? false;

      // Track original value groups before filtering
      const originalValueGroups = callSite.value_groups;

      // Filter value_groups based on frameFilter and testFilter if active
      let filteredValueGroups = callSite.value_groups;
      if (frameFilter) {
        filteredValueGroups = filteredValueGroups.filter(valueGroup =>
          stackTraceContainsFrame(valueGroup.stack_trace_id, frameFilter)
        );
      }
      if (testFilter) {
        filteredValueGroups = filteredValueGroups.filter(valueGroup =>
          logBelongsToTest(valueGroup.log_index, testFilter)
        );
      }
      if (rangeFilter) {
        filteredValueGroups = filteredValueGroups.filter(valueGroup =>
          valueGroup.log_index >= rangeFilter.start && valueGroup.log_index <= rangeFilter.end
        );
      }

      // Apply column filters if configured
      const filters = columnFilters[callSiteKey];
      if (filters && Object.keys(filters).length > 0) {
        filteredValueGroups = filteredValueGroups.filter(valueGroup =>
          valueGroupPassesFilters(valueGroup, callSite, callSiteKey, filters)
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

      // Calculate filtered-out logs
      const filteredOutLogs = originalValueGroups.filter(
        vg => !filteredValueGroups.includes(vg)
      );

      // Create filtered call site with both visible and filtered logs
      const filteredCallSite: FilteredCallSite = {
        ...callSite,
        value_groups: filteredValueGroups,
        filtered_value_groups: filteredOutLogs.length > 0 ? filteredOutLogs : undefined,
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
      const cacheKey = `${callSiteKey}:${columnId}`;

      // Use cached value
      const cachedResults = computedColumnCache.get(cacheKey);
      if (cachedResults) {
        const result = cachedResults.get(valueGroup.log_index);
        if (result) {
          return result.error ? { __error: result.error } : result.value;
        }
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

  // Column resize handlers
  function handleResizeStart(callSite: CallSite, columnName: string, e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();

    const callSiteKey = getCallSiteKey(callSite);
    const th = (e.target as HTMLElement).closest('th');
    if (!th) return;

    // Capture current widths of ALL columns in this table to prevent them from changing
    const headerRow = th.parentElement;
    if (headerRow) {
      const allHeaders = Array.from(headerRow.querySelectorAll('th.column-header'));
      const columns = getColumnNames(callSite);

      if (!columnWidths[callSiteKey]) {
        columnWidths[callSiteKey] = {};
      }

      // Lock ALL column widths at their current rendered widths
      allHeaders.forEach((header, index) => {
        const colName = columns[index];
        if (colName) {
          // Always capture the current width, even if already set
          columnWidths[callSiteKey][colName] = (header as HTMLElement).offsetWidth;
        }
      });
    }

    const startWidth = th.offsetWidth;
    resizingColumn = { callSiteKey, columnName, startX: e.clientX, startWidth };

    // Prevent text selection during resize
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
  }

  function handleResizeMove(e: MouseEvent) {
    if (!resizingColumn) return;

    const deltaX = e.clientX - resizingColumn.startX;
    const newWidth = Math.max(100, resizingColumn.startWidth + deltaX); // Min width 100px

    // Update the width in state
    if (!columnWidths[resizingColumn.callSiteKey]) {
      columnWidths[resizingColumn.callSiteKey] = {};
    }
    columnWidths[resizingColumn.callSiteKey][resizingColumn.columnName] = newWidth;
  }

  function handleResizeEnd() {
    if (resizingColumn) {
      resizingColumn = null;
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    }
  }

  function getColumnWidth(callSite: CallSite, columnName: string): string {
    const callSiteKey = getCallSiteKey(callSite);
    const width = columnWidths[callSiteKey]?.[columnName];
    if (width !== undefined) {
      return `width: ${width}px; min-width: ${width}px; max-width: ${width}px;`;
    }
    // Return default width to ensure all columns have explicit widths
    return 'width: 200px; min-width: 200px; max-width: 200px;';
  }

  // Estimate width needed to display a value (heuristic-based, no DOM measurement)
  function estimateValueWidth(value: unknown): number {
    if (value === null || value === undefined) return 60;
    if (typeof value === 'boolean') return 60;
    if (typeof value === 'number') return 80;
    if (typeof value === 'string') {
      const len = value.length;
      if (len <= 10) return 100;
      if (len <= 30) return 180;
      return 250;
    }
    // Objects and arrays show collapsed by default
    if (Array.isArray(value)) return 120;
    if (typeof value === 'object') return 120;
    return 100;
  }

  // Estimate width needed for column header
  function estimateHeaderWidth(displayName: string, isComputed: boolean): number {
    // Base: character width (~8px per char) + padding (24px) + gap (8px) + filter button (~42px) + resize handle (16px)
    const charWidth = displayName.length * 8;
    const fixedWidth = isComputed ? 105 : 90; // extra for computed icon (ƒ + spacing)
    return charWidth + fixedWidth;
  }

  // Compute initial column widths for a call site to fill available space
  function computeInitialColumnWidths(callSite: CallSite, availableWidth: number): Record<string, number> {
    const columns = getColumnNames(callSite);
    if (columns.length === 0) return {};

    const firstRow = callSite.value_groups[0];
    const MIN_WIDTH = 80;

    // Calculate data width and full width for each column
    const columnInfo = columns.map(columnName => {
      const isComputed = columnName.startsWith('computed:');
      const computedCol = isComputed ? getComputedColumn(callSite, columnName) : undefined;
      const displayName = isComputed && computedCol ? getComputedColumnDisplayName(computedCol) : columnName;

      const value = firstRow ? getValueForColumn(firstRow, columnName, callSite) : undefined;
      const dataWidth = Math.max(estimateValueWidth(value), MIN_WIDTH);
      const headerWidth = estimateHeaderWidth(displayName, isComputed);
      const fullWidth = Math.max(dataWidth, headerWidth);

      return { columnName, dataWidth, headerWidth, fullWidth };
    });

    const totalDataWidth = columnInfo.reduce((sum, c) => sum + c.dataWidth, 0);
    const totalFullWidth = columnInfo.reduce((sum, c) => sum + c.fullWidth, 0);

    const result: Record<string, number> = {};

    if (totalFullWidth <= availableWidth) {
      // Case A: Everything fits, distribute extra space proportionally
      const extra = availableWidth - totalFullWidth;
      const extraPerColumn = extra / columns.length;
      for (const c of columnInfo) {
        result[c.columnName] = Math.floor(c.fullWidth + extraPerColumn);
      }
    } else if (totalDataWidth <= availableWidth) {
      // Case B: Data fits but headers may be clipped
      // Start with data widths, distribute remaining to columns that need header space
      let remaining = availableWidth - totalDataWidth;

      // Sort by gap (fullWidth - dataWidth) ascending to prioritize small gaps
      const gaps = columnInfo
        .map(c => ({ columnName: c.columnName, gap: c.fullWidth - c.dataWidth }))
        .filter(g => g.gap > 0)
        .sort((a, b) => a.gap - b.gap);

      // Initialize with data widths
      for (const c of columnInfo) {
        result[c.columnName] = c.dataWidth;
      }

      // Distribute remaining space to close gaps
      for (const g of gaps) {
        if (remaining <= 0) break;
        const add = Math.min(g.gap, remaining);
        result[g.columnName] += add;
        remaining -= add;
      }

      // If still space left, distribute evenly
      if (remaining > 0) {
        const extraPerColumn = remaining / columns.length;
        for (const c of columnInfo) {
          result[c.columnName] = Math.floor(result[c.columnName] + extraPerColumn);
        }
      }
    } else {
      // Case C: Need to compress - scale proportionally
      const scale = availableWidth / totalDataWidth;
      for (const c of columnInfo) {
        result[c.columnName] = Math.max(MIN_WIDTH, Math.floor(c.dataWidth * scale));
      }
    }

    return result;
  }

  // Add global mouse event listeners for resize
  $effect(() => {
    if (resizingColumn) {
      const handleMove = (e: MouseEvent) => handleResizeMove(e);
      const handleUp = () => handleResizeEnd();

      document.addEventListener('mousemove', handleMove);
      document.addEventListener('mouseup', handleUp);

      return () => {
        document.removeEventListener('mousemove', handleMove);
        document.removeEventListener('mouseup', handleUp);
      };
    }
  });

  // Initialize column widths when table containers are mounted
  $effect(() => {
    // Trigger on tableContainers and filteredCallSites changes
    const containers = tableContainers;
    const callSites = filteredCallSites;

    for (const callSite of callSites) {
      const callSiteKey = getCallSiteKey(callSite);
      const container = containers[callSiteKey];

      // Only compute if container exists and no widths set yet
      if (container && !columnWidths[callSiteKey]) {
        // Subtract space for # column and + column
        const availableWidth = container.clientWidth - 96 - 56;
        if (availableWidth > 0) {
          columnWidths[callSiteKey] = computeInitialColumnWidths(callSite, availableWidth);
        }
      }
    }
  });

  // Drag-and-drop handlers
  function handleDragStart(callSite: CallSite, columnName: string, e: DragEvent) {
    // Prevent drag if we're currently resizing
    if (resizingColumn) {
      e.preventDefault();
      return;
    }

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

    console.log("handleDragOver", { types: e.dataTransfer?.types, callSiteKey, index });

    // Check for stack variable drag (external)
    if (e.dataTransfer?.types.includes('application/json')) {
      console.log("Detected stack variable drag");
      e.dataTransfer.dropEffect = 'copy';
      dropTarget = { callSiteKey, index };
      return;
    }

    // Existing column reorder logic
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

    console.log("handleDrop", { callSiteKey, targetIndex });

    // Check for stack variable drag (external)
    const jsonData = e.dataTransfer?.getData('application/json');
    console.log("Drop JSON data:", jsonData);
    if (jsonData) {
      try {
        const payload: StackVariableDragPayload = JSON.parse(jsonData);
        console.log("Parsed payload:", payload);
        if (payload.type === 'stack-variable') {
          console.log("Calling handleStackVariableDrop");
          handleStackVariableDrop(callSite, callSiteKey, targetIndex, payload);
          dropTarget = null;
          return;
        }
      } catch (err) {
        console.error('Failed to parse drag payload:', err);
      }
    }

    // Existing column reorder logic
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

  function handleStackVariableDrop(
    callSite: CallSite,
    callSiteKey: string,
    targetIndex: number,
    payload: StackVariableDragPayload
  ) {
    console.log("handleStackVariableDrop called", { callSiteKey, targetIndex, payload });

    // Validate: check that sourceLogIndex belongs to this call site
    const belongsToCallSite = callSite.value_groups.some(
      vg => vg.log_index === payload.sourceLogIndex
    );

    console.log("Validation result:", { belongsToCallSite, sourceLogIndex: payload.sourceLogIndex, valueGroups: callSite.value_groups.map(vg => vg.log_index) });

    if (!belongsToCallSite) {
      console.warn('Cannot drop: stack trace is from a different call site');
      return;
    }

    // Validate payload
    if (!payload.path || payload.path.length === 0) {
      console.warn('Invalid drag payload: empty path');
      return;
    }

    // Generate expression and title
    const expression = generatePythonExpression(payload, callSite);
    const title = generateColumnTitle(payload);

    console.log("Generated expression:", expression);
    console.log("Generated title:", title);

    // Create computed column
    const column: ComputedColumn = {
      id: generateColumnId(),
      title,
      expression,
      callSiteKey,
    };

    console.log("Created column:", column);

    // Get current column order BEFORE saving (so it doesn't include the new column yet)
    const columns = getColumnNames(callSite);
    const newColumnName = `computed:${column.id}`;
    const newOrder = [...columns];
    newOrder.splice(targetIndex, 0, newColumnName);
    console.log("Updating column order:", { newOrder, targetIndex });

    // Save the column (this makes it available in computedColumns)
    onSaveComputedColumn?.(column);
    console.log("Called onSaveComputedColumn");

    // Update column order to insert at target position
    onColumnOrderChange?.(callSiteKey, newOrder);
    console.log("Done with handleStackVariableDrop");
  }

  function generatePythonExpression(payload: StackVariableDragPayload, callSite: CallSite): string {
    const { frameIndex, path, frameFunctionName, frameFilename, frameLineNumber, baseExpression } = payload;

    let expr: string;

    if (baseExpression) {
      // Append to existing expression
      expr = baseExpression;

      // Append the dragged path
      for (const segment of path) {
        if (segment.type === 'array') {
          // Array access - check if key is numeric or string
          if (typeof segment.key === 'number') {
            expr += `[${segment.key}]`;
          } else {
            const escapedKey = escapeForPython(String(segment.key));
            expr += `["${escapedKey}"]`;
          }
        } else {
          const escapedKey = escapeForPython(String(segment.key));
          expr += `["${escapedKey}"]`;
        }
      }
    } else {
      // Check if this is the top frame (index 0) and we're accessing a direct variable
      if (frameIndex === 0 && path.length > 0) {
        // For top frame, the first segment can be a direct variable name
        const firstSegment = path[0];
        if (firstSegment.type === 'object') {
          // Use direct variable name
          expr = String(firstSegment.key);

          // Append remaining path segments (skipping the first one)
          for (let i = 1; i < path.length; i++) {
            const segment = path[i];
            if (segment.type === 'array') {
              // Array access - check if key is numeric or string
              if (typeof segment.key === 'number') {
                expr += `[${segment.key}]`;
              } else {
                const escapedKey = escapeForPython(String(segment.key));
                expr += `["${escapedKey}"]`;
              }
            } else {
              const escapedKey = escapeForPython(String(segment.key));
              expr += `["${escapedKey}"]`;
            }
          }
        } else {
          // First segment is an array access, so we still need full path from trace
          expr = buildFrameExpression(frameIndex, frameFunctionName, callSite, path);
        }
      } else {
        // For non-top frames, use frame access
        expr = buildFrameExpression(frameIndex, frameFunctionName, callSite, path);
      }
    }

    return expr;
  }

  function buildFrameExpression(
    frameIndex: number,
    frameFunctionName: string | undefined,
    callSite: CallSite,
    path: PathSegment[]
  ): string {
    // Generate frame access expression
    let frameAccessExpr: string;

    // Check if the frame at this index is stable across all logs
    const stability = isFrameIndexStable(callSite.value_groups, frameIndex, data);

    if (stability.stable) {
      // Frame is stable - use direct index access (more efficient)
      frameAccessExpr = `trace['frames'][${frameIndex}]`;
    } else if (frameFunctionName) {
      // Frame is not stable - use next() to search by function name
      const functionNameEscaped = escapeForPython(frameFunctionName);
      frameAccessExpr = `next((f for f in trace['frames'] if f['function_name'] == "${functionNameEscaped}"), trace['frames'][${frameIndex}])`;
    } else {
      // Fallback to direct index access
      frameAccessExpr = `trace['frames'][${frameIndex}]`;
    }

    // Access local_variables
    let expr = `(${frameAccessExpr})['local_variables']`;

    // Append the full path
    for (const segment of path) {
      if (segment.type === 'array') {
        // Array access - check if key is numeric or string
        if (typeof segment.key === 'number') {
          expr += `[${segment.key}]`;
        } else {
          const escapedKey = escapeForPython(String(segment.key));
          expr += `["${escapedKey}"]`;
        }
      } else {
        const escapedKey = escapeForPython(String(segment.key));
        expr += `["${escapedKey}"]`;
      }
    }

    return expr;
  }

  function escapeForPython(str: string): string {
    return str
      .replace(/\\/g, '\\\\')
      .replace(/"/g, '\\"')
      .replace(/\n/g, '\\n')
      .replace(/\r/g, '\\r')
      .replace(/\t/g, '\\t');
  }

  function generateColumnTitle(payload: StackVariableDragPayload): string {
    const { frameIndex, path, frameFunctionName, baseExpression } = payload;

    if (path.length === 0) {
      return frameFunctionName ? frameFunctionName : `frame[${frameIndex}]`;
    }

    const leafSegment = path[path.length - 1];
    const leafKey = String(leafSegment.key);

    if (baseExpression) {
      // When appending to an existing expression, just use the leaf key
      return leafKey;
    }

    // Use function name if available, otherwise fall back to frame index
    const frameLabel = frameFunctionName || `frame ${frameIndex}`;
    return `${leafKey} (${frameLabel})`;
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

  // Close dropdown when clicking outside
  $effect(() => {
    if (openDropdown) {
      const handleClickOutside = (event: MouseEvent) => {
        const target = event.target as HTMLElement;
        // Don't close if clicking inside the dropdown menu or the button that opened it
        if (!target.closest('.column-dropdown-menu') && !target.closest('.column-menu-container')) {
          closeDropdown();
        }
      };
      document.addEventListener('click', handleClickOutside);
      return () => {
        document.removeEventListener('click', handleClickOutside);
      };
    }
  });

  // Handle sticky headers with JavaScript
  $effect(() => {
    // Capture current refs - access them once to establish reactivity
    const currentHeaders = { ...tableHeaders };
    const currentContainers = { ...tableContainers };

    // Find the actual scrolling container (main-panel)
    const scrollContainer = document.querySelector('.main-panel');
    if (!scrollContainer) {
      console.log('[Sticky Headers] Could not find .main-panel scrolling container');
      return;
    }

    console.log('[Sticky Headers] Found scroll container:', scrollContainer);

    let rafId: number | null = null;

    const updateHeaders = () => {
      // Get the scroll container's position for reference
      const scrollContainerRect = scrollContainer.getBoundingClientRect();
      const scrollTop = scrollContainerRect.top;

      const newFloatingHeaders: typeof floatingHeaders = {};

      for (const callSiteKey in currentHeaders) {
        const thead = currentHeaders[callSiteKey];
        const container = currentContainers[callSiteKey];

        if (!thead || !container) continue;

        const containerRect = container.getBoundingClientRect();
        const theadRect = thead.getBoundingClientRect();

        // Calculate position relative to the scroll container's top edge
        const containerTopRelative = containerRect.top - scrollTop;

        // Check if table has scrolled past the top of the scroll container
        const tableHasScrolledPastTop = containerTopRelative < 0;
        const tableBottomBelowViewport = containerRect.bottom > scrollTop;

        if (tableHasScrolledPastTop && tableBottomBelowViewport) {
          // Calculate how much space is left at the bottom
          const spaceBelow = containerRect.bottom - scrollTop - theadRect.height;

          // If there's not enough space below, stick the header to the table bottom
          // by adjusting the top position
          let topPosition = scrollTop;
          if (spaceBelow < 0) {
            // Move the header up by the amount of space that's missing
            topPosition = scrollTop + spaceBelow;
          }

          // Measure column widths from the original header
          // The second row contains the actual column headers
          const headerRows = thead.querySelectorAll('tr');
          const columnRow = headerRows[1]; // Second row has the column headers
          const columnWidths: number[] = [];

          if (columnRow) {
            const ths = columnRow.querySelectorAll('th');
            ths.forEach((th) => {
              const width = th.getBoundingClientRect().width;
              columnWidths.push(width);
            });
          }

          // Update floating header state
          newFloatingHeaders[callSiteKey] = {
            visible: true,
            top: topPosition,
            left: containerRect.left,
            width: theadRect.width,
            scrollLeft: container.scrollLeft,
            columnWidths,
          };
        } else {
          // Header should not be floating
          newFloatingHeaders[callSiteKey] = {
            visible: false,
            top: 0,
            left: 0,
            width: 0,
            scrollLeft: 0,
            columnWidths: [],
          };
        }
      }

      // Update state
      floatingHeaders = newFloatingHeaders;
    };

    const handleScroll = () => {
      // Cancel any pending animation frame
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }

      // Schedule update on next animation frame for smooth rendering
      rafId = requestAnimationFrame(updateHeaders);
    };

    // Add scroll listener to the actual scrolling element
    console.log('[Sticky Headers] Setting up scroll listener on .main-panel', Object.keys(currentHeaders));
    scrollContainer.addEventListener('scroll', handleScroll, { passive: true });

    // Also add horizontal scroll listeners to each table container
    const containerScrollListeners: Array<() => void> = [];
    for (const callSiteKey in currentContainers) {
      const container = currentContainers[callSiteKey];
      if (container) {
        container.addEventListener('scroll', handleScroll, { passive: true });
        containerScrollListeners.push(() => container.removeEventListener('scroll', handleScroll));
      }
    }

    // Initial check
    updateHeaders();

    return () => {
      console.log('[Sticky Headers] Cleaning up scroll listener');
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }
      scrollContainer.removeEventListener('scroll', handleScroll);
      // Clean up horizontal scroll listeners
      containerScrollListeners.forEach(cleanup => cleanup());
    };
  });
</script>

{#snippet headerContent(callSite: CallSite, callSiteKey: string, isDashboard: boolean, columnWidths?: number[])}
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
        <CodeLocation
          filename={callSite.filename}
          line={callSite.line}
          functionName={callSite.function_name}
          className={callSite.class_name}
        />
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
    <th class="log-number-header" style={columnWidths && columnWidths[0] ? `width: ${columnWidths[0]}px` : ''}>#</th>
    {#each getColumnNames(callSite) as columnName, columnIndex}
    {@const sortable = isColumnSortable(callSite, columnName)}
    {@const sortState = getColumnSortState(callSite, columnName)}
    {@const sortPriority = getSortPriority(callSite, columnName)}
    {@const isDragging = draggedColumn?.callSiteKey === callSiteKey && draggedColumn?.columnName === columnName}
    {@const isDropTarget = dropTarget?.callSiteKey === callSiteKey && dropTarget?.index === columnIndex}
    {@const isComputed = columnName.startsWith('computed:')}
    {@const computedCol = isComputed ? getComputedColumn(callSite, columnName) : undefined}
    {@const displayName = isComputed && computedCol ? getComputedColumnDisplayName(computedCol) : columnName}
    {@const thIndex = columnIndex + 1}
    {@const measuredWidth = columnWidths && columnWidths[thIndex] ? `width: ${columnWidths[thIndex]}px;` : ''}
    {@const baseStyle = getColumnWidth(callSite, columnName)}
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
      title={isComputed && computedCol ? `${displayName}\n\nExpression: ${computedCol.expression}` : displayName}
      style={columnWidths ? measuredWidth : baseStyle}
    >
      <div class="column-header-content">
        {#if isComputed}
          <span class="computed-icon">ƒ</span>
        {/if}
        <span class="column-name">{displayName}</span>
        <div class="column-menu-container">
          <button
            class="filter-menu-button"
            class:menu-active={sortState !== null}
            onclick={(e) => toggleDropdown(callSite, columnName, e)}
            title="Column options"
          >
            <ListFilter size={14} />
            {#if sortPriority !== null && (columnSorts[callSiteKey]?.length ?? 0) > 1}
              <span class="sort-priority">{sortPriority}</span>
            {/if}
          </button>
        </div>
        <div
          class="resize-handle"
          class:resizing={resizingColumn?.callSiteKey === callSiteKey && resizingColumn?.columnName === columnName}
          onmousedown={(e) => handleResizeStart(callSite, columnName, e)}
          title="Drag to resize column"
        ></div>
      </div>
    </th>
  {/each}
  {#if dropTarget?.callSiteKey === callSiteKey && dropTarget?.index === getColumnNames(callSite).length}
    <th class="drop-target-after"></th>
  {/if}
  <th class="add-column-header" style={columnWidths && columnWidths[getColumnNames(callSite).length + 1] ? `width: ${columnWidths[getColumnNames(callSite).length + 1]}px` : ''}>
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
{/snippet}

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
              <CodeLocation
                filename={callSite.filename}
                line={callSite.line}
                functionName={callSite.function_name}
                className={callSite.class_name}
              />
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
                {@const mark = logMarks[valueGroup.log_index]}
                <div
                  class="value-group"
                  class:highlighted={highlightedLogIndex === valueGroup.log_index}
                  class:selected={selectedLogIndex === valueGroup.log_index}
                  class:clickable={valueGroup.stack_trace_id !== undefined}
                  data-log-index={valueGroup.log_index}
                  style={mark?.color ? `background-color: ${mark.color};` : ""}
                  draggable="true"
                  ondragstart={(e) => {
                    if (e.dataTransfer) {
                      e.dataTransfer.setData("text/log-index", valueGroup.log_index.toString());
                      e.dataTransfer.effectAllowed = "copy";
                    }
                  }}
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
          <div class="table-wrapper">
            <div class="table-container" bind:this={tableContainers[callSiteKey]}>
              <table class="value-table">
              <thead class="table-header" bind:this={tableHeaders[callSiteKey]}>
                {@render headerContent(callSite, callSiteKey, isDashboard)}
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
                    {#if callSite.value_groups.length === 0 && callSite.filtered_value_groups && callSite.filtered_value_groups.length > 0}
                      <span class="filtered-indicator">...{callSite.filtered_value_groups.length}
                      {callSite.filtered_value_groups.length === 1 ? "log" : "logs"} (filtered)</span>
                    {:else}
                      ...{callSite.value_groups.length}
                      {callSite.value_groups.length === 1 ? "log" : "logs"}
                      {#if callSite.filtered_value_groups && callSite.filtered_value_groups.length > 0}
                        <span class="filtered-count"> (+{callSite.filtered_value_groups.length} filtered)</span>
                      {/if}
                    {/if}
                  </td>
                </tr>
              </tbody>
            {:else}
              <tbody>
                {#each callSite.value_groups as valueGroup, groupIndex}
                  {@const mark = logMarks[valueGroup.log_index]}
                  {@const frameContextHighlight = shouldHighlightForFrameContext(valueGroup.stack_trace_id)}
                  <tr
                    class="table-row"
                    class:highlighted={highlightedLogIndex ===
                      valueGroup.log_index}
                    class:selected={selectedLogIndex === valueGroup.log_index}
                    class:frame-context-highlight={frameContextHighlight}
                    class:clickable={valueGroup.stack_trace_id !== undefined}
                    data-log-index={valueGroup.log_index}
                    style={mark?.color ? `background-color: ${mark.color};` : ""}
                    draggable="true"
                    ondragstart={(e) => {
                      if (e.dataTransfer) {
                        e.dataTransfer.setData("text/log-index", valueGroup.log_index.toString());
                        e.dataTransfer.effectAllowed = "copy";
                      }
                    }}
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
                      {@const stackTrace = valueGroup.stack_trace_id ? data.stack_traces[valueGroup.stack_trace_id] : undefined}
                      {@const firstFrame = stackTrace?.frames[0]}
                      {@const isComputedColumn = columnName.startsWith('computed:')}
                      {@const isSimpleVariable = !isComputedColumn && firstFrame && columnName in firstFrame.local_variables}
                      {@const canDrag = !!firstFrame && (isComputedColumn || isSimpleVariable)}
                      {@const baseExpr = isComputedColumn
                        ? getComputedColumn(callSite, columnName)?.expression
                        : isSimpleVariable
                          ? columnName
                          : undefined}
                      <td
                        class="value-cell"
                        style={getColumnWidth(callSite, columnName)}
                      >
                        {#if cellValue !== undefined}
                          {#if typeof cellValue === 'object' && cellValue !== null && '__error' in cellValue}
                            <span class="computed-error">{cellValue.__error}</span>
                          {:else}
                            <TreeView
                              value={cellValue}
                              enableDrag={canDrag}
                              frameIndex={0}
                              sourceLogIndex={valueGroup.log_index}
                              frameFunctionName={firstFrame?.function_name}
                              frameFilename={firstFrame?.filename}
                              frameLineNumber={firstFrame?.line_number}
                              baseExpression={baseExpr}
                            />
                          {/if}
                        {:else}
                          <span class="empty-cell">—</span>
                        {/if}
                      </td>
                    {/each}
                  </tr>
                {/each}
                {#if callSite.filtered_value_groups && callSite.filtered_value_groups.length > 0}
                  {@const isExpanded = expandedFilteredLogs.has(callSiteKey)}
                  <!-- Show filtered logs if expanded -->
                  {#if isExpanded}
                    {#each callSite.filtered_value_groups as valueGroup, groupIndex}
                      {@const mark = logMarks[valueGroup.log_index]}
                      {@const frameContextHighlight = shouldHighlightForFrameContext(valueGroup.stack_trace_id)}
                      <tr
                        class="table-row filtered-log-row"
                        class:highlighted={highlightedLogIndex ===
                          valueGroup.log_index}
                        class:selected={selectedLogIndex === valueGroup.log_index}
                        class:frame-context-highlight={frameContextHighlight}
                        class:clickable={valueGroup.stack_trace_id !== undefined}
                        data-log-index={valueGroup.log_index}
                        style={mark?.color ? `background-color: ${mark.color};` : ""}
                        draggable="true"
                        ondragstart={(e) => {
                          if (e.dataTransfer) {
                            e.dataTransfer.setData("text/log-index", valueGroup.log_index.toString());
                            e.dataTransfer.effectAllowed = "copy";
                          }
                        }}
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
                          {@const stackTrace = valueGroup.stack_trace_id ? data.stack_traces[valueGroup.stack_trace_id] : undefined}
                          {@const firstFrame = stackTrace?.frames[0]}
                          {@const isComputedColumn = columnName.startsWith('computed:')}
                          {@const isSimpleVariable = !isComputedColumn && firstFrame && columnName in firstFrame.local_variables}
                          {@const canDrag = !!firstFrame && (isComputedColumn || isSimpleVariable)}
                          {@const baseExpr = isComputedColumn
                            ? getComputedColumn(callSite, columnName)?.expression
                            : isSimpleVariable
                              ? columnName
                              : undefined}
                          <td
                            class="value-cell"
                            style={getColumnWidth(callSite, columnName)}
                          >
                            {#if cellValue !== undefined}
                              {#if typeof cellValue === 'object' && cellValue !== null && '__error' in cellValue}
                                <span class="computed-error">{cellValue.__error}</span>
                              {:else}
                                <TreeView
                                  value={cellValue}
                                  enableDrag={canDrag}
                                  frameIndex={0}
                                  sourceLogIndex={valueGroup.log_index}
                                  frameFunctionName={firstFrame?.function_name}
                                  frameFilename={firstFrame?.filename}
                                  frameLineNumber={firstFrame?.line_number}
                                  baseExpression={baseExpr}
                                />
                              {/if}
                            {:else}
                              <span class="empty-cell">—</span>
                            {/if}
                          </td>
                        {/each}
                      </tr>
                    {/each}
                  {/if}
                  <!-- "...n logs" row -->
                  <tr
                    class="filtered-logs-toggle-row"
                    onclick={() => toggleFilteredLogs(callSite)}
                    role="button"
                    tabindex="0"
                    onkeydown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        toggleFilteredLogs(callSite);
                      }
                    }}
                  >
                    <td
                      colspan={getColumnNames(callSite).length + 1}
                      class="filtered-logs-summary"
                    >
                      ...{callSite.filtered_value_groups.length}
                      {callSite.filtered_value_groups.length === 1 ? "log" : "logs"}
                    </td>
                  </tr>
                {/if}
              </tbody>
            {/if}
          </table>
          </div>
          </div>
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
              <CodeLocation
                filename={callSite.filename}
                line={callSite.line}
                functionName={callSite.function_name}
                className={callSite.class_name}
              />
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
                {@const mark = logMarks[valueGroup.log_index]}
                <div
                  class="value-group"
                  class:highlighted={highlightedLogIndex ===
                    valueGroup.log_index}
                  class:selected={selectedLogIndex === valueGroup.log_index}
                  class:clickable={valueGroup.stack_trace_id !== undefined}
                  data-log-index={valueGroup.log_index}
                  style={mark?.color ? `background-color: ${mark.color};` : ""}
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

<!-- Render dropdown outside the table structure to prevent event bubbling -->
{#if openDropdown}
  {@const dropdownState = openDropdown}
  {@const filteredCallSite = filteredCallSites.find(cs => getCallSiteKey(cs) === dropdownState.callSiteKey)}
  {@const callSite = data.call_sites.find(cs => getCallSiteKey(cs) === dropdownState.callSiteKey)}
  {#if callSite && filteredCallSite}
    {@const columnName = dropdownState.columnName}
    {@const sortable = isColumnSortable(filteredCallSite, columnName)}
    {@const sortState = getColumnSortState(filteredCallSite, columnName)}
    {@const columnProfile = getColumnProfile(callSite, columnName)}
    {@const callSiteKey = getCallSiteKey(callSite)}
    {@const currentFilter = columnFilters[callSiteKey]?.[columnName] || null}
    <div
      class="column-dropdown-menu"
      style="top: {dropdownState.top}px; left: {dropdownState.left}px;"
      role="menu"
      tabindex="-1"
      onmousedown={(e) => e.stopPropagation()}
      ondblclick={(e) => e.stopPropagation()}
      ondragstart={(e) => e.preventDefault()}
    >
      {#if sortable}
        <div class="dropdown-section">
          <button
            class="dropdown-item"
            class:active={sortState === 'asc'}
            onclick={() => handleSortAscending(callSite, columnName)}
          >
            <span class="dropdown-icon">▲</span>
            Sort ascending
          </button>
          <button
            class="dropdown-item"
            class:active={sortState === 'desc'}
            onclick={() => handleSortDescending(callSite, columnName)}
          >
            <span class="dropdown-icon">▼</span>
            Sort descending
          </button>
          <button
            class="dropdown-item"
            class:disabled={sortState === null}
            onclick={() => handleResetSort(callSite, columnName)}
            disabled={sortState === null}
          >
            <span class="dropdown-icon">─</span>
            Reset sort
          </button>
        </div>
        <div class="dropdown-divider"></div>
      {/if}
      <div class="dropdown-section filter-section">
        <FilterWidgets
          profile={columnProfile}
          filter={currentFilter}
          onFilterChange={(filter) => handleFilterChange(callSite, columnName, filter)}
        />
      </div>
      <div class="dropdown-divider"></div>
      <div class="dropdown-section">
        <button
          class="dropdown-item"
          onclick={() => handleHideColumn(callSite, columnName)}
        >
          <span class="dropdown-icon">✕</span>
          Hide column
        </button>
      </div>
    </div>
  {/if}
{/if}

<!-- Floating headers (clones that appear when scrolling) -->
{#each filteredCallSites as callSite (getCallSiteKey(callSite))}
  {@const callSiteKey = getCallSiteKey(callSite)}
  {@const isDashboard = callSite.is_dashboard ?? false}
  {@const floatingState = floatingHeaders[callSiteKey]}
  {#if floatingState?.visible && getColumnNames(callSite).length > 0}
    <div
      class="floating-header"
      style="
        position: fixed;
        top: {floatingState.top}px;
        left: {floatingState.left}px;
        width: {floatingState.width}px;
        z-index: 100;
        transform: translateX(-{floatingState.scrollLeft}px);
      "
    >
      <table class="value-table floating-header-table">
        <thead class="table-header">
          {@render headerContent(callSite, callSiteKey, isDashboard, floatingState.columnWidths)}
        </thead>
      </table>
    </div>
  {/if}
{/each}

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
    padding: 0;
    background: #f9f9f9;
    transition: opacity 0.2s, background-color 0.2s;
    /* No overflow here - we want sticky headers to work relative to viewport */
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

  .table-wrapper {
    position: relative;
  }

  .table-container {
    overflow-x: auto;
    overflow-y: visible;
  }

  .value-table {
    width: auto;
    border-collapse: collapse;
    background: white;
    border-radius: 4px;
    table-layout: fixed;
  }

  .table-header {
    background: #f9f9f9;
    /* Will be positioned via JavaScript - no transition for smoothness */
    display: table-header-group;
    width: 100%;
  }

  .floating-header {
    pointer-events: auto;
    overflow: visible;
  }

  .floating-header-table {
    table-layout: fixed;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .call-site-info-row {
    border-bottom: 1px solid #e5e5e5;
  }

  .call-site-info-row th {
    background: #f9f9f9;
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

  .filtered-indicator {
    color: #64748b;
    font-style: italic;
  }

  .filtered-count {
    color: #64748b;
    font-size: 0.85rem;
    margin-left: 0.5rem;
  }

  .table-header th:not(.call-site-info) {
    padding: 0.25rem 0.75rem;
    text-align: left;
    font-weight: 600;
    /* color: #2563eb; */
    color: #881391;
    font-size: 0.85rem;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    border-bottom: 2px solid #e5e5e5;
    white-space: nowrap;
    background: #f9f9f9;
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
    position: relative;
    overflow: hidden;
    padding-right: 10px; /* Space for resize handle */
  }

  .column-name {
    flex: 1 1 auto;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }

  .column-menu-container {
    position: relative;
    flex: 0 0 auto;
  }

  .resize-handle {
    position: absolute;
    right: 0;
    top: 0;
    bottom: 0;
    width: 16px;
    cursor: col-resize;
    user-select: none;
    z-index: 10;
    border-right: 1px solid #ddd;
  }

  .resize-handle:hover {
    border-right: none;
    background: linear-gradient(to right, transparent, rgba(37, 99, 235, 0.4));
  }

  .resize-handle.resizing {
    border-right: none;
    background: linear-gradient(to right, transparent 30%, rgba(37, 99, 235, 0.6));
  }

  .filter-menu-button {
    background: transparent;
    border: 1px solid #cbd5e1;
    border-radius: 3px;
    padding: 2px 6px;
    cursor: pointer;
    color: #64748b;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 2px;
    min-width: 1.9rem;
    justify-content: center;
    height: 22px;
  }

  .filter-menu-button:hover {
    background: #f1f5f9;
    border-color: #94a3b8;
    color: #475569;
  }

  .filter-menu-button.menu-active {
    background: #881391;
    border-color: #881391;
    color: white;
  }

  .filter-menu-button.menu-active:hover {
    background: #6b0f73;
    border-color: #6b0f73;
  }

  .sort-priority {
    font-size: 0.65rem;
    font-weight: 600;
    margin-left: 1px;
  }

  .column-dropdown-menu {
    position: fixed;
    background: white;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 10000;
    min-width: 320px;
    max-width: 400px;
    max-height: 600px;
    overflow-y: auto;
  }

  .dropdown-section {
    padding: 4px 0;
  }

  .dropdown-section.filter-section {
    padding: 0;
  }

  .dropdown-divider {
    height: 1px;
    background: #e5e7eb;
    margin: 0;
  }

  .dropdown-item {
    width: 100%;
    padding: 8px 12px;
    background: white;
    border: none;
    text-align: left;
    cursor: pointer;
    font-size: 0.85rem;
    color: #374151;
    transition: background-color 0.15s;
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: inherit;
  }

  .dropdown-item:hover:not(:disabled) {
    background: #f3f4f6;
  }

  .dropdown-item.active {
    background: #eff6ff;
    color: #2563eb;
    font-weight: 500;
  }

  .dropdown-item.active:hover {
    background: #dbeafe;
  }

  .dropdown-item:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .dropdown-icon {
    font-size: 0.75rem;
    width: 16px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-family: monospace;
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

  .table-row.frame-context-highlight {
    background-color: #fef3c7;
  }

  .table-row.frame-context-highlight:hover {
    background-color: #fde68a;
  }

  .table-row.frame-context-highlight.selected {
    background-color: #fde68a;
  }

  .filtered-log-row {
    opacity: 0.6;
    background-color: #f9fafb;
  }

  .filtered-log-row:hover {
    opacity: 0.8;
    background-color: #f3f4f6;
  }

  .filtered-log-row.highlighted {
    opacity: 1;
  }

  .filtered-log-row.selected {
    opacity: 1;
    background-color: #e0e7ff;
  }

  .filtered-log-row.selected:hover {
    background-color: #c7d2fe;
  }

  .filtered-logs-toggle-row {
    border-top: 1px dashed #cbd5e1;
    border-bottom: 1px solid #e5e5e5;
    cursor: pointer;
    transition: background-color 0.2s;
    background-color: #fafafa;
  }

  .filtered-logs-toggle-row:hover {
    background-color: #f0f0f0;
  }

  .filtered-logs-summary {
    padding: 0.5rem;
    text-align: center;
    color: #64748b;
    font-size: 0.875rem;
    font-style: italic;
    user-select: none;
  }

  .log-number-cell {
    padding: 0.4rem 0.6rem;
    vertical-align: top;
  }

  .value-cell {
    padding: 0.4rem 0.6rem;
    vertical-align: top;
    min-width: 200px;
    max-width: 0; /* Force the cell to respect the width constraint */
    overflow: hidden;
    text-overflow: ellipsis;
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
    flex-shrink: 0;
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
