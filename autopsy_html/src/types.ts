/**
 * Type definitions for autopsy report data structure
 */

export interface ValueWithName {
  name?: string  // Variable name if available
  value: unknown
}

export interface ValueGroup {
  values: ValueWithName[]  // Values with their variable names
  function_name: string  // Name of the function containing this log call
  log_index: number  // Global index for ordering all logs chronologically
}

export interface CallSite {
  filename: string
  line: number
  function_name: string  // Name of the enclosing function
  value_groups: ValueGroup[]  // Each group contains values from one log() call
}

export interface AutopsyData {
  generated_at: string
  call_sites: CallSite[]
}

