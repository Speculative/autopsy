import jmespath from 'jmespath';
import type { AutopsyData, ValueGroup, ComputedColumn } from './types';

export interface EvaluationResult {
  value: unknown;
  error?: string;
}

/**
 * Evaluate a JMESPath expression for a specific row (ValueGroup)
 * The expression operates on the StackTrace.frames array
 */
export function evaluateComputedColumn(
  expression: string,
  valueGroup: ValueGroup,
  data: AutopsyData
): EvaluationResult {
  try {
    // Get stack trace frames array
    const stackTraceId = valueGroup.stack_trace_id;
    if (!stackTraceId) {
      return { value: undefined };
    }

    const stackTrace = data.stack_traces[stackTraceId];
    if (!stackTrace) {
      return { value: undefined };
    }

    // Evaluate JMESPath on frames array
    const result = jmespath.search(stackTrace.frames, expression);
    return { value: result };
  } catch (error) {
    // Return error type name (e.g., "SyntaxError", "TypeError")
    return {
      value: undefined,
      error: error instanceof Error ? error.name : 'Error'
    };
  }
}

/**
 * Check if all values in an array are primitive (sortable)
 */
export function isComputedColumnSortable(results: EvaluationResult[]): boolean {
  for (const result of results) {
    if (result.error) return false;  // Errors are not sortable
    if (result.value === null || result.value === undefined) continue;
    const type = typeof result.value;
    if (type !== 'string' && type !== 'number' && type !== 'boolean') {
      return false;
    }
  }
  return true;
}

/**
 * Get display name for a computed column
 */
export function getComputedColumnDisplayName(column: ComputedColumn): string {
  return column.title || column.expression;
}

/**
 * Generate unique ID for new computed column
 */
export function generateColumnId(): string {
  return `computed_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}
