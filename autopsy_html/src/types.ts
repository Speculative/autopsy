/**
 * Type definitions for autopsy report data structure
 */

export interface CallSite {
  filename: string
  line: number
  value_groups: unknown[][]  // Each group contains values from one log() call
}

export interface AutopsyData {
  generated_at: string
  call_sites: CallSite[]
}

