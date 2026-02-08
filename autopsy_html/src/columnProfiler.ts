import type { CallSite, ValueGroup, AutopsyData } from './types';
import type { EvaluationResult } from './computedColumns';

/**
 * Column data type based on profiling
 */
export type ColumnDataType =
  | 'numeric'        // Numbers or dates (use range slider)
  | 'enum'           // Low cardinality strings (< 10 unique values, use checkboxes)
  | 'high_cardinality_string'  // High cardinality strings (use regex)
  | 'array'          // Arrays (show length distribution)
  | 'object'         // Objects (show field profiling)
  | 'mixed'          // Mixed types
  | 'unknown';       // Empty or all undefined

/**
 * Profile for numeric columns
 */
export interface NumericProfile {
  type: 'numeric';
  min: number;
  max: number;
  count: number;
  nullCount: number;
  // Histogram bins for visualization
  bins: Array<{ min: number; max: number; count: number }>;
}

/**
 * Profile for enum columns (low cardinality)
 */
export interface EnumProfile {
  type: 'enum';
  values: Array<{ value: string; count: number; percentage: number }>;
  nullCount: number;
  totalCount: number;
}

/**
 * Profile for high cardinality string columns
 */
export interface HighCardinalityStringProfile {
  type: 'high_cardinality_string';
  uniqueCount: number;
  totalCount: number;
  nullCount: number;
  sampleValues: string[];  // Top 5-10 values
}

/**
 * Profile for array columns
 */
export interface ArrayProfile {
  type: 'array';
  lengthDistribution: Array<{ length: number; count: number; percentage: number }>;
  totalCount: number;
  nullCount: number;
}

/**
 * Profile for object columns
 */
export interface ObjectProfile {
  type: 'object';
  fieldProfiles: Record<string, {
    type: string;
    count: number;
    sampleValues: unknown[];
  }>;
  totalCount: number;
  nullCount: number;
}

/**
 * Profile for columns with mixed types
 */
export interface MixedProfile {
  type: 'mixed';
  typeCounts: Record<string, number>;
  totalCount: number;
  nullCount: number;
}

/**
 * Profile for unknown columns
 */
export interface UnknownProfile {
  type: 'unknown';
  totalCount: number;
}

export type ColumnProfile =
  | NumericProfile
  | EnumProfile
  | HighCardinalityStringProfile
  | ArrayProfile
  | ObjectProfile
  | MixedProfile
  | UnknownProfile;

/**
 * Profiling options
 */
export interface ProfileOptions {
  enumThreshold?: number;      // Max unique values to consider as enum (default: 10)
  numHistogramBins?: number;    // Number of bins for numeric histogram (default: 20)
  sampleSize?: number;          // Number of sample values to keep (default: 10)
}

/**
 * Get all values for a column
 */
function getColumnValues(
  callSite: CallSite,
  columnName: string,
  computedColumnCache?: Map<string, Map<number, EvaluationResult>>,
  callSiteKey?: string
): unknown[] {
  const values: unknown[] = [];

  for (const valueGroup of callSite.value_groups) {
    // Check if this is a computed column
    if (columnName.startsWith('computed:') && computedColumnCache && callSiteKey) {
      const columnId = columnName.substring('computed:'.length);
      const cacheKey = `${callSiteKey}:${columnId}`;
      const cachedResults = computedColumnCache.get(cacheKey);

      if (cachedResults) {
        const result = cachedResults.get(valueGroup.log_index);
        if (result && !result.error) {
          values.push(result.value);
        } else {
          values.push(undefined);
        }
      } else {
        values.push(undefined);
      }
    } else {
      // Regular column
      if (!valueGroup.values) {
        values.push(undefined);
        continue;
      }
      const value = valueGroup.values.find((v) => v.name === columnName);
      values.push(value?.value);
    }
  }

  return values;
}

/**
 * Detect the data type of a column based on its values
 */
function detectDataType(values: unknown[], options: ProfileOptions): ColumnDataType {
  const enumThreshold = options.enumThreshold ?? 10;

  // Filter out null/undefined
  const definedValues = values.filter(v => v !== null && v !== undefined);

  if (definedValues.length === 0) {
    return 'unknown';
  }

  // Count types
  const typeCounts: Record<string, number> = {};
  for (const value of definedValues) {
    const type = Array.isArray(value) ? 'array' : typeof value;
    typeCounts[type] = (typeCounts[type] || 0) + 1;
  }

  const types = Object.keys(typeCounts);

  // If more than one type, it's mixed
  if (types.length > 1) {
    // Exception: if all numeric types (number), treat as numeric
    if (types.length === 1 && types[0] === 'number') {
      return 'numeric';
    }
    return 'mixed';
  }

  const primaryType = types[0];

  if (primaryType === 'number') {
    return 'numeric';
  }

  if (primaryType === 'boolean') {
    // Treat booleans as enums (true/false)
    return 'enum';
  }

  if (primaryType === 'string') {
    // Check cardinality
    const uniqueValues = new Set(definedValues as string[]);
    if (uniqueValues.size <= enumThreshold) {
      return 'enum';
    } else {
      return 'high_cardinality_string';
    }
  }

  if (primaryType === 'array') {
    return 'array';
  }

  if (primaryType === 'object') {
    return 'object';
  }

  return 'mixed';
}

/**
 * Profile a numeric column
 */
function profileNumeric(values: unknown[], options: ProfileOptions): NumericProfile {
  const numBins = options.numHistogramBins ?? 20;

  // Separate finite numbers from special values
  const allNumbers = values.filter(v => typeof v === 'number') as number[];
  const finiteNumbers = allNumbers.filter(v => isFinite(v));
  const negInfCount = allNumbers.filter(v => v === -Infinity).length;
  const posInfCount = allNumbers.filter(v => v === Infinity).length;
  const nanCount = allNumbers.filter(v => Number.isNaN(v)).length;
  const nullCount = values.length - allNumbers.length;

  // Create histogram bins
  const bins: Array<{ min: number; max: number; count: number }> = [];

  // Add -Infinity bin if present
  if (negInfCount > 0) {
    bins.push({ min: -Infinity, max: -Infinity, count: negInfCount });
  }

  // Add regular numeric bins if we have finite numbers
  if (finiteNumbers.length > 0) {
    const min = Math.min(...finiteNumbers);
    const max = Math.max(...finiteNumbers);
    const range = max - min;

    if (range === 0) {
      // All same value - this bin goes after the -Inf bin if it exists
      bins.push({ min, max, count: finiteNumbers.length });
    } else {
      const binSize = range / numBins;
      for (let i = 0; i < numBins; i++) {
        const binMin = min + i * binSize;
        const binMax = min + (i + 1) * binSize;
        bins.push({ min: binMin, max: binMax, count: 0 });
      }

      // Count values in each bin
      // Note: bins array already has the -Inf bin if it exists, so offset by that
      const binOffset = negInfCount > 0 ? 1 : 0;
      for (const num of finiteNumbers) {
        const binIndex = Math.min(Math.floor((num - min) / binSize), numBins - 1);
        bins[binOffset + binIndex].count++;
      }
    }
  }

  // Add Infinity bin if present
  if (posInfCount > 0) {
    bins.push({ min: Infinity, max: Infinity, count: posInfCount });
  }

  // Add NaN bin if present (rightmost)
  if (nanCount > 0) {
    bins.push({ min: NaN, max: NaN, count: nanCount });
  }

  // Calculate overall min/max for the profile (excluding special values)
  const profileMin = finiteNumbers.length > 0 ? Math.min(...finiteNumbers) : 0;
  const profileMax = finiteNumbers.length > 0 ? Math.max(...finiteNumbers) : 0;

  return {
    type: 'numeric',
    min: profileMin,
    max: profileMax,
    count: allNumbers.length,
    nullCount,
    bins
  };
}

/**
 * Profile an enum column
 */
function profileEnum(values: unknown[]): EnumProfile {
  // Handle both strings and booleans
  const enumValues = values.filter(v => typeof v === 'string' || typeof v === 'boolean');
  const nullCount = values.length - enumValues.length;

  // Count occurrences (convert to string for consistency)
  const counts = new Map<string, number>();
  for (const val of enumValues) {
    const strVal = String(val);
    counts.set(strVal, (counts.get(strVal) || 0) + 1);
  }

  // Sort by count descending
  const sorted = Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([value, count]) => ({
      value,
      count,
      percentage: (count / enumValues.length) * 100
    }));

  return {
    type: 'enum',
    values: sorted,
    nullCount,
    totalCount: values.length
  };
}

/**
 * Profile a high cardinality string column
 */
function profileHighCardinalityString(values: unknown[], options: ProfileOptions): HighCardinalityStringProfile {
  const sampleSize = options.sampleSize ?? 10;
  const strings = values.filter(v => typeof v === 'string') as string[];
  const nullCount = values.length - strings.length;

  // Get unique values
  const unique = new Set(strings);

  // Count occurrences for top values
  const counts = new Map<string, number>();
  for (const str of strings) {
    counts.set(str, (counts.get(str) || 0) + 1);
  }

  // Get top N by count
  const topValues = Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, sampleSize)
    .map(([value]) => value);

  return {
    type: 'high_cardinality_string',
    uniqueCount: unique.size,
    totalCount: values.length,
    nullCount,
    sampleValues: topValues
  };
}

/**
 * Profile an array column
 */
function profileArray(values: unknown[]): ArrayProfile {
  const arrays = values.filter(v => Array.isArray(v)) as unknown[][];
  const nullCount = values.length - arrays.length;

  // Count length distribution
  const lengthCounts = new Map<number, number>();
  for (const arr of arrays) {
    const len = arr.length;
    lengthCounts.set(len, (lengthCounts.get(len) || 0) + 1);
  }

  // Sort by length and create distribution
  const distribution = Array.from(lengthCounts.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([length, count]) => ({
      length,
      count,
      percentage: (count / arrays.length) * 100
    }));

  return {
    type: 'array',
    lengthDistribution: distribution,
    totalCount: values.length,
    nullCount
  };
}

/**
 * Profile an object column
 */
function profileObject(values: unknown[], options: ProfileOptions): ObjectProfile {
  const sampleSize = options.sampleSize ?? 5;
  const objects = values.filter(v => v !== null && typeof v === 'object' && !Array.isArray(v)) as Record<string, unknown>[];
  const nullCount = values.length - objects.length;

  // Collect all fields and their types
  const fieldProfiles: Record<string, {
    type: string;
    count: number;
    sampleValues: unknown[];
  }> = {};

  for (const obj of objects) {
    for (const [key, value] of Object.entries(obj)) {
      if (!fieldProfiles[key]) {
        fieldProfiles[key] = {
          type: Array.isArray(value) ? 'array' : typeof value,
          count: 0,
          sampleValues: []
        };
      }
      fieldProfiles[key].count++;

      // Add to sample values if we don't have enough yet
      if (fieldProfiles[key].sampleValues.length < sampleSize) {
        fieldProfiles[key].sampleValues.push(value);
      }
    }
  }

  return {
    type: 'object',
    fieldProfiles,
    totalCount: values.length,
    nullCount
  };
}

/**
 * Profile a mixed type column
 */
function profileMixed(values: unknown[]): MixedProfile {
  const definedValues = values.filter(v => v !== null && v !== undefined);
  const nullCount = values.length - definedValues.length;

  const typeCounts: Record<string, number> = {};
  for (const value of definedValues) {
    const type = Array.isArray(value) ? 'array' : typeof value;
    typeCounts[type] = (typeCounts[type] || 0) + 1;
  }

  return {
    type: 'mixed',
    typeCounts,
    totalCount: values.length,
    nullCount
  };
}

/**
 * Profile a column to determine its type and statistics
 */
export function profileColumn(
  callSite: CallSite,
  columnName: string,
  options: ProfileOptions = {},
  computedColumnCache?: Map<string, Map<number, EvaluationResult>>,
  callSiteKey?: string
): ColumnProfile {
  // Get all values for this column
  const values = getColumnValues(callSite, columnName, computedColumnCache, callSiteKey);

  // Detect data type
  const dataType = detectDataType(values, options);

  // Profile based on detected type
  switch (dataType) {
    case 'numeric':
      return profileNumeric(values, options);

    case 'enum':
      return profileEnum(values);

    case 'high_cardinality_string':
      return profileHighCardinalityString(values, options);

    case 'array':
      return profileArray(values);

    case 'object':
      return profileObject(values, options);

    case 'mixed':
      return profileMixed(values);

    case 'unknown':
    default:
      return {
        type: 'unknown',
        totalCount: values.length
      };
  }
}
