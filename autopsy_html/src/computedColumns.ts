import { pythonExecutor } from './pythonExecutor';
import type { AutopsyData, ValueGroup, ComputedColumn } from './types';

export interface EvaluationResult {
  value: unknown;
  error?: string;
}

/**
 * Evaluate Python code for a single ValueGroup
 * This is a wrapper around the batch function for convenience
 */
export async function evaluateComputedColumn(
  pythonCode: string,
  valueGroup: ValueGroup,
  data: AutopsyData
): Promise<EvaluationResult> {
  const results = await evaluateComputedColumnBatch(
    pythonCode,
    [valueGroup],
    data
  );
  return results[0];
}

/**
 * Evaluate Python code for multiple ValueGroups in batch (efficient)
 * The Python code has access to a 'trace' variable containing the StackTrace object
 */
export async function evaluateComputedColumnBatch(
  pythonCode: string,
  valueGroups: ValueGroup[],
  data: AutopsyData
): Promise<EvaluationResult[]> {
  try {
    // Ensure Pyodide is initialized
    if (!pythonExecutor.isReady()) {
      await pythonExecutor.initialize();
    }

    // Prepare StackTrace objects for each ValueGroup
    const traces = valueGroups.map(vg => {
      const stackTraceId = vg.stack_trace_id;
      if (!stackTraceId) {
        return null;
      }
      const stackTrace = data.stack_traces[stackTraceId];
      if (!stackTrace) {
        return null;
      }
      return {
        frames: stackTrace.frames,
        timestamp: stackTrace.timestamp
      };
    });

    // Execute Python code in batch
    const results = await pythonExecutor.executeBatch(
      pythonCode,
      traces,
      'trace'
    );

    return results;
  } catch (error) {
    // Global error (e.g., syntax error)
    const errorName = error instanceof Error ? error.name : 'Error';
    return valueGroups.map(() => ({ value: undefined, error: errorName }));
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
