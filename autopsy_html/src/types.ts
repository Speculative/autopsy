/**
 * Type definitions for autopsy report data structure
 */

export interface CallSite {
  filename: string
  line: number
  values: unknown[]
}

export interface AutopsyData {
  generated_at: string
  call_sites: CallSite[]
}

