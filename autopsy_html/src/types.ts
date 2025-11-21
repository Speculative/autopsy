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
  values: ValueWithName[]  // Values with their variable names
  function_name: string  // Name of the function containing this log call
  class_name?: string  // Name of the class if this is a method
  log_index: number  // Global index for ordering all logs chronologically
  stack_trace_id?: string  // ID of associated stack trace (as string to match JSON keys)
}

export interface CallSite {
  filename: string
  line: number
  function_name: string  // Name of the enclosing function
  class_name?: string  // Name of the class if this is a method
  value_groups: ValueGroup[]  // Each group contains values from one log() call
}

export interface AutopsyData {
  generated_at: string
  call_sites: CallSite[]
  stack_traces: Record<string, StackTrace>  // Keyed by stack_trace_id as string
}

