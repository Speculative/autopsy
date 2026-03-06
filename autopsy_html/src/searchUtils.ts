import type { ValueGroup, CallSite } from "./types";

/**
 * Extract searchable text from a log entry's value group.
 * Only includes strings and numbers — objects and arrays are skipped.
 */
export function getSearchableText(valueGroup: ValueGroup, callSite: CallSite): string {
  const parts: string[] = [];

  if (valueGroup.name) {
    parts.push(valueGroup.name);
  }

  if (valueGroup.dashboard_type) {
    parts.push(valueGroup.dashboard_type);
    if (valueGroup.dashboard_type === "timeline" && valueGroup.event_name) {
      parts.push(valueGroup.event_name);
    }
    if (valueGroup.dashboard_type === "happened" && valueGroup.message) {
      parts.push(valueGroup.message);
    }
    if ((valueGroup.dashboard_type === "count" || valueGroup.dashboard_type === "hist") && valueGroup.value != null) {
      if (typeof valueGroup.value === "string" || typeof valueGroup.value === "number") {
        parts.push(String(valueGroup.value));
      }
    }
  } else if (valueGroup.values) {
    for (const v of valueGroup.values) {
      if (typeof v.value === "string") {
        parts.push(v.value);
      } else if (typeof v.value === "number") {
        parts.push(String(v.value));
      }
      // Skip objects, arrays, booleans, null, etc.
    }
  }

  return parts.join(" ");
}
