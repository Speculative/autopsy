import type { AutopsyData, LogMark, ComputedColumn, StackFrame, ValueGroup } from "./types";

// Keys for localStorage
const STORAGE_KEYS = {
  TEST_FILTER: 'autopsy:testFilter',
  TEST_FILTER_ENABLED: 'autopsy:testFilterEnabled',
  LOG_MARKS: 'autopsy:logMarks',
  RANGE_FILTER: 'autopsy:rangeFilter',
  COMPUTED_COLUMNS: 'autopsy:computedColumns',
  COLUMN_ORDERS: 'autopsy:columnOrders',
  HIDDEN_COLUMNS: 'autopsy:hiddenColumns',
} as const;

// Persisted state structure
export interface PersistedState {
  testFilter: string | null;
  testFilterEnabled: boolean;
  logMarks: Record<string, { // keyed by log signature, not index
    color: string;
    note: string;
    logSignature: string; // To identify this log
  }>;
  rangeFilter: {
    startSignature: string;
    endSignature: string;
  } | null;
  computedColumns: Record<string, ComputedColumn[]>;
}

/**
 * Create a signature for a log entry based on its explicit logged values and call stack structure.
 * This allows matching logs across sessions even if log indices change.
 */
export function createLogSignature(
  data: AutopsyData,
  logIndex: number
): string | null {
  // Find the value group for this log index
  let valueGroup: ValueGroup | null = null;
  let callSiteKey = '';

  for (const callSite of data.call_sites) {
    const vg = callSite.value_groups.find(g => g.log_index === logIndex);
    if (vg) {
      valueGroup = vg;
      callSiteKey = `${callSite.filename}:${callSite.line}`;
      break;
    }
  }

  if (!valueGroup) return null;

  // Serialize the explicit logged values (not the full call stack, but we'll include stack structure)
  const explicitValues = valueGroup.values || [];
  const valuesJson = JSON.stringify(explicitValues.map(v => ({
    name: v.name,
    value: v.value,
  })));

  // Include function name, class name, dashboard type, etc.
  const metadataJson = JSON.stringify({
    function_name: valueGroup.function_name,
    class_name: valueGroup.class_name,
    dashboard_type: valueGroup.dashboard_type,
    name: valueGroup.name,
  });

  // Get stack trace structure (just function names at each level)
  let stackStructure = '';
  if (valueGroup.stack_trace_id && data.stack_traces) {
    const trace = data.stack_traces[valueGroup.stack_trace_id];
    if (trace) {
      stackStructure = trace.frames.map(f =>
        `${f.function_name}@${f.filename}:${f.line_number}`
      ).join('|');
    }
  }

  // Combine into signature
  return `${callSiteKey}::${metadataJson}::${valuesJson}::${stackStructure}`;
}

/**
 * Check if a log matches a given signature.
 * Uses the same logic as createLogSignature.
 */
export function logMatchesSignature(
  data: AutopsyData,
  logIndex: number,
  signature: string
): boolean {
  const currentSignature = createLogSignature(data, logIndex);
  return currentSignature === signature;
}

/**
 * Find a log index that matches the given signature.
 * Returns null if no match found.
 */
export function findLogBySignature(
  data: AutopsyData,
  signature: string
): number | null {
  // Extract call site key from signature to narrow search
  const callSiteKeyEnd = signature.indexOf('::');
  if (callSiteKeyEnd === -1) return null;

  const callSiteKey = signature.substring(0, callSiteKeyEnd);

  // Search through all logs
  for (const callSite of data.call_sites) {
    const currentCallSiteKey = `${callSite.filename}:${callSite.line}`;
    if (currentCallSiteKey !== callSiteKey) continue;

    for (const vg of callSite.value_groups) {
      if (logMatchesSignature(data, vg.log_index, signature)) {
        return vg.log_index;
      }
    }
  }

  return null;
}

/**
 * Save test filter to localStorage
 */
export function saveTestFilter(testFilter: string | null, enabled: boolean): void {
  try {
    if (testFilter !== null) {
      localStorage.setItem(STORAGE_KEYS.TEST_FILTER, testFilter);
    } else {
      localStorage.removeItem(STORAGE_KEYS.TEST_FILTER);
    }
    localStorage.setItem(STORAGE_KEYS.TEST_FILTER_ENABLED, String(enabled));
  } catch (e) {
    console.warn('Failed to save test filter:', e);
  }
}

/**
 * Restore test filter from localStorage
 */
export function restoreTestFilter(data: AutopsyData): {
  testFilter: string | null;
  testFilterEnabled: boolean;
} {
  try {
    const testFilter = localStorage.getItem(STORAGE_KEYS.TEST_FILTER);
    const enabled = localStorage.getItem(STORAGE_KEYS.TEST_FILTER_ENABLED) === 'true';

    // Verify the test still exists
    if (testFilter && data.tests) {
      const testExists = data.tests.some(t => t.nodeid === testFilter);
      if (testExists) {
        return { testFilter, testFilterEnabled: enabled };
      }
    }
  } catch (e) {
    console.warn('Failed to restore test filter:', e);
  }

  return { testFilter: null, testFilterEnabled: true };
}

/**
 * Save log marks to localStorage
 */
export function saveLogMarks(data: AutopsyData, logMarks: Record<number, LogMark>): void {
  try {
    const persistedMarks: Record<string, { color: string; note: string; logSignature: string }> = {};

    for (const [logIndexStr, mark] of Object.entries(logMarks)) {
      const logIndex = parseInt(logIndexStr);
      const signature = createLogSignature(data, logIndex);
      if (signature) {
        persistedMarks[logIndexStr] = {
          color: mark.color,
          note: mark.note,
          logSignature: signature,
        };
      }
    }

    localStorage.setItem(STORAGE_KEYS.LOG_MARKS, JSON.stringify(persistedMarks));
  } catch (e) {
    console.warn('Failed to save log marks:', e);
  }
}

/**
 * Restore log marks from localStorage
 */
export function restoreLogMarks(data: AutopsyData): Record<number, LogMark> {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.LOG_MARKS);
    if (!stored) return {};

    const persistedMarks = JSON.parse(stored) as Record<string, {
      color: string;
      note: string;
      logSignature: string;
    }>;

    const restoredMarks: Record<number, LogMark> = {};

    // Try to match each persisted mark to a current log
    for (const persistedMark of Object.values(persistedMarks)) {
      const logIndex = findLogBySignature(data, persistedMark.logSignature);
      if (logIndex !== null) {
        restoredMarks[logIndex] = {
          color: persistedMark.color,
          note: persistedMark.note,
        };
      }
    }

    return restoredMarks;
  } catch (e) {
    console.warn('Failed to restore log marks:', e);
    return {};
  }
}

/**
 * Save range filter to localStorage
 */
export function saveRangeFilter(
  data: AutopsyData,
  rangeStartLogIndex: number | null,
  rangeEndLogIndex: number | null
): void {
  try {
    if (rangeStartLogIndex !== null && rangeEndLogIndex !== null) {
      const startSignature = createLogSignature(data, rangeStartLogIndex);
      const endSignature = createLogSignature(data, rangeEndLogIndex);

      if (startSignature && endSignature) {
        localStorage.setItem(STORAGE_KEYS.RANGE_FILTER, JSON.stringify({
          startSignature,
          endSignature,
        }));
        return;
      }
    }

    localStorage.removeItem(STORAGE_KEYS.RANGE_FILTER);
  } catch (e) {
    console.warn('Failed to save range filter:', e);
  }
}

/**
 * Restore range filter from localStorage
 */
export function restoreRangeFilter(data: AutopsyData): {
  rangeStartLogIndex: number | null;
  rangeEndLogIndex: number | null;
} {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.RANGE_FILTER);
    if (!stored) return { rangeStartLogIndex: null, rangeEndLogIndex: null };

    const rangeFilter = JSON.parse(stored) as {
      startSignature: string;
      endSignature: string;
    };

    const startIndex = findLogBySignature(data, rangeFilter.startSignature);
    const endIndex = findLogBySignature(data, rangeFilter.endSignature);

    // Only restore if both marks still exist
    if (startIndex !== null && endIndex !== null) {
      return {
        rangeStartLogIndex: startIndex,
        rangeEndLogIndex: endIndex,
      };
    }
  } catch (e) {
    console.warn('Failed to restore range filter:', e);
  }

  return { rangeStartLogIndex: null, rangeEndLogIndex: null };
}

/**
 * Save computed columns to localStorage
 */
export function saveComputedColumns(computedColumns: Record<string, ComputedColumn[]>): void {
  try {
    // Convert Svelte Proxy to plain object for serialization
    const plainObject: Record<string, ComputedColumn[]> = {};
    for (const [key, value] of Object.entries(computedColumns)) {
      plainObject[key] = [...value]; // Shallow copy the array
    }
    localStorage.setItem(STORAGE_KEYS.COMPUTED_COLUMNS, JSON.stringify(plainObject));
  } catch (e) {
    console.warn('Failed to save computed columns:', e);
  }
}

/**
 * Restore computed columns from localStorage
 * Only restores columns where the call site still exists
 */
export function restoreComputedColumns(data: AutopsyData): Record<string, ComputedColumn[]> {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.COMPUTED_COLUMNS);
    if (!stored) return {};

    const persistedColumns = JSON.parse(stored) as Record<string, ComputedColumn[]>;
    const restoredColumns: Record<string, ComputedColumn[]> = {};

    // Build set of existing call site keys
    const existingCallSiteKeys = new Set(
      data.call_sites.map(cs => `${cs.filename}:${cs.line}`)
    );

    // Only restore columns for call sites that still exist
    for (const [callSiteKey, columns] of Object.entries(persistedColumns)) {
      if (existingCallSiteKeys.has(callSiteKey)) {
        restoredColumns[callSiteKey] = columns;
      }
    }

    return restoredColumns;
  } catch (e) {
    console.warn('Failed to restore computed columns:', e);
    return {};
  }
}

/**
 * Save column orders to localStorage
 */
export function saveColumnOrders(columnOrders: Record<string, string[]>): void {
  try {
    // Convert Svelte Proxy to plain object for serialization
    const plainObject: Record<string, string[]> = {};
    for (const [key, value] of Object.entries(columnOrders)) {
      plainObject[key] = [...value];
    }
    localStorage.setItem(STORAGE_KEYS.COLUMN_ORDERS, JSON.stringify(plainObject));
  } catch (e) {
    console.warn('Failed to save column orders:', e);
  }
}

/**
 * Restore column orders from localStorage
 * Only restores orders for call sites that still exist
 */
export function restoreColumnOrders(data: AutopsyData): Record<string, string[]> {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.COLUMN_ORDERS);
    if (!stored) return {};

    const persistedOrders = JSON.parse(stored) as Record<string, string[]>;
    const restoredOrders: Record<string, string[]> = {};

    // Build set of existing call site keys
    const existingCallSiteKeys = new Set(
      data.call_sites.map(cs => `${cs.filename}:${cs.line}`)
    );

    // Only restore orders for call sites that still exist
    for (const [callSiteKey, order] of Object.entries(persistedOrders)) {
      if (existingCallSiteKeys.has(callSiteKey)) {
        restoredOrders[callSiteKey] = order;
      }
    }

    return restoredOrders;
  } catch (e) {
    console.warn('Failed to restore column orders:', e);
    return {};
  }
}

/**
 * Save hidden columns to localStorage
 */
export function saveHiddenColumns(hiddenColumns: Record<string, Set<string>>): void {
  try {
    // Convert Sets to arrays for JSON serialization
    const plainObject: Record<string, string[]> = {};
    for (const [key, value] of Object.entries(hiddenColumns)) {
      plainObject[key] = Array.from(value);
    }
    localStorage.setItem(STORAGE_KEYS.HIDDEN_COLUMNS, JSON.stringify(plainObject));
  } catch (e) {
    console.warn('Failed to save hidden columns:', e);
  }
}

/**
 * Restore hidden columns from localStorage
 * Only restores for call sites that still exist
 */
export function restoreHiddenColumns(data: AutopsyData): Record<string, Set<string>> {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.HIDDEN_COLUMNS);
    if (!stored) return {};

    const persistedHidden = JSON.parse(stored) as Record<string, string[]>;
    const restoredHidden: Record<string, Set<string>> = {};

    // Build set of existing call site keys
    const existingCallSiteKeys = new Set(
      data.call_sites.map(cs => `${cs.filename}:${cs.line}`)
    );

    // Only restore for call sites that still exist
    for (const [callSiteKey, hiddenArray] of Object.entries(persistedHidden)) {
      if (existingCallSiteKeys.has(callSiteKey)) {
        restoredHidden[callSiteKey] = new Set(hiddenArray);
      }
    }

    return restoredHidden;
  } catch (e) {
    console.warn('Failed to restore hidden columns:', e);
    return {};
  }
}

/**
 * Clear all persisted state
 */
export function clearPersistedState(): void {
  try {
    for (const key of Object.values(STORAGE_KEYS)) {
      localStorage.removeItem(key);
    }
  } catch (e) {
    console.warn('Failed to clear persisted state:', e);
  }
}
