/**
 * Type definitions for autopsy report data structure
 */

export interface ValueWithName {
  name?: string  // Variable name if available
  value: unknown
}

export interface StackFrame {
  filename: string
  function_name: string
  line_number: number
  code_context: string
  local_variables: Record<string, unknown>
}

export interface StackTrace {
  frames: StackFrame[]
  timestamp: number
}

export interface ValueGroup {
  values?: ValueWithName[]  // Values with their variable names (for regular log() calls)
  function_name: string  // Name of the function containing this log call
  class_name?: string  // Name of the class if this is a method
  log_index: number  // Global index for ordering all logs chronologically
  stack_trace_id?: string  // ID of associated stack trace (as string to match JSON keys)
  name?: string  // Optional name for this log entry (inferred or explicit)
  dashboard_type?: "count" | "hist" | "timeline" | "happened"  // Type of dashboard call if this is a dashboard invocation
  value?: unknown  // Dashboard value (for count/hist types)
  event_name?: string  // For timeline type
  timestamp?: number  // For timeline type
  message?: string  // For happened type
}

export interface CallSite {
  filename: string
  line: number
  function_name: string  // Name of the enclosing function
  class_name?: string  // Name of the class if this is a method
  value_groups: ValueGroup[]  // Each group contains values from one log() call or dashboard invocation
  is_dashboard?: boolean  // True if this is a dashboard call site (count/hist/timeline/happened)
}

export interface DashboardCallSite {
  filename: string
  line: number
  function_name: string
  class_name?: string
}

export interface CountValue {
  count: number
  stack_trace_ids: string[]
  log_indices: number[]
}

export interface HistogramValue {
  value: number
  stack_trace_id?: string
  log_index: number
}

export interface CountEntry {
  call_site: DashboardCallSite
  value_counts: Record<string, CountValue>  // Key is JSON-serialized value
}

export interface HistogramEntry {
  call_site: DashboardCallSite
  values: HistogramValue[]
}

export interface TimelineEntry {
  timestamp: number
  event_name: string
  call_site: DashboardCallSite
  stack_trace_id?: string
  log_index?: number
}

export interface HappenedEntry {
  call_site: DashboardCallSite
  count: number
  stack_trace_ids: string[]
  log_indices: number[]
  message?: string
}

export interface DashboardData {
  counts: CountEntry[]
  histograms: HistogramEntry[]
  timeline: TimelineEntry[]
  happened: HappenedEntry[]
}

export interface AutopsyData {
  generated_at: string
  call_sites: CallSite[]
  stack_traces: Record<string, StackTrace>  // Keyed by stack_trace_id as string
  dashboard?: DashboardData
}

// Computed column definition
export interface ComputedColumn {
  id: string;              // Unique identifier
  title?: string;          // Optional display name
  expression: string;      // JMESPath expression
  callSiteKey: string;     // Which call site this belongs to
}

// Column filter types
export type ColumnFilter =
  | { type: 'numeric_range'; min: number; max: number }
  | { type: 'enum_values'; selectedValues: Set<string> }  // Set of selected enum values
  | { type: 'regex'; pattern: string }
  | { type: 'python_expression'; expression: string };

// Filters for a call site (columnName -> filter)
export type ColumnFilters = Record<string, ColumnFilter>;

