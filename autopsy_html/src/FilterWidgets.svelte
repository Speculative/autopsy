<script lang="ts">
  import type { ColumnProfile, NumericProfile, EnumProfile } from './columnProfiler';
  import type { ColumnFilter } from './types';

  interface Props {
    profile: ColumnProfile;
    filter: ColumnFilter | null;
    onFilterChange: (filter: ColumnFilter | null) => void;
  }

  let {
    profile,
    filter = null,
    onFilterChange
  }: Props = $props();

  // State for different filter types
  let minValue = $state(0);
  let maxValue = $state(100);
  let selectedEnumValues = $state<Set<string>>(new Set());
  let regexPattern = $state('');
  let regexValid = $state(true);
  let pythonExpression = $state('');

  // Initialize state based on profile and filter
  $effect(() => {
    if (profile.type === 'numeric') {
      minValue = filter?.type === 'numeric_range' ? filter.min : profile.min;
      maxValue = filter?.type === 'numeric_range' ? filter.max : profile.max;
    } else if (profile.type === 'enum') {
      if (filter?.type === 'enum_values') {
        selectedEnumValues = new Set(filter.selectedValues);
      } else {
        selectedEnumValues = new Set(profile.values.map(v => v.value));
      }
    } else if (profile.type === 'high_cardinality_string') {
      regexPattern = filter?.type === 'regex' ? filter.pattern : '';
    }

    if (filter?.type === 'python_expression') {
      pythonExpression = filter.expression;
    }
  });

  // Range slider drag state
  let draggingHandle = $state<'min' | 'max' | null>(null);
  let sliderContainer = $state<HTMLDivElement | null>(null);

  // Numeric filter handlers
  function handleMinDragStart(e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    draggingHandle = 'min';
    document.body.style.userSelect = 'none';
  }

  function handleMaxDragStart(e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    draggingHandle = 'max';
    document.body.style.userSelect = 'none';
  }

  function handleTrackMouseDown(e: MouseEvent) {
    if (!sliderContainer || profile.type !== 'numeric') return;

    e.preventDefault();

    // Calculate click position
    const rect = sliderContainer.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const percentage = x / rect.width;
    const clickValue = profile.min + percentage * (profile.max - profile.min);

    // Determine which handle is closer
    const minDistance = Math.abs(clickValue - minValue);
    const maxDistance = Math.abs(clickValue - maxValue);

    // Start dragging the closer handle
    draggingHandle = minDistance <= maxDistance ? 'min' : 'max';
    document.body.style.userSelect = 'none';

    // Immediately update the value
    if (draggingHandle === 'min') {
      minValue = Math.min(clickValue, maxValue);
    } else {
      maxValue = Math.max(minValue, clickValue);
    }
    updateNumericFilter();
  }

  function handleDragMove(e: MouseEvent) {
    if (!draggingHandle || !sliderContainer || profile.type !== 'numeric') return;

    const rect = sliderContainer.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const percentage = x / rect.width;
    const range = profile.max - profile.min;
    const newValue = profile.min + percentage * range;

    if (draggingHandle === 'min') {
      minValue = Math.min(newValue, maxValue);
    } else {
      maxValue = Math.max(minValue, newValue);
    }

    updateNumericFilter();
  }

  function handleDragEnd() {
    draggingHandle = null;
    document.body.style.userSelect = '';
  }

  // Add global mouse event listeners for dragging
  $effect(() => {
    if (draggingHandle) {
      const handleMove = (e: MouseEvent) => handleDragMove(e);
      const handleUp = () => handleDragEnd();

      document.addEventListener('mousemove', handleMove);
      document.addEventListener('mouseup', handleUp);

      return () => {
        document.removeEventListener('mousemove', handleMove);
        document.removeEventListener('mouseup', handleUp);
      };
    }
  });

  function updateNumericFilter() {
    if (profile.type !== 'numeric') return;
    const isDirty = minValue !== profile.min || maxValue !== profile.max;
    if (isDirty) {
      onFilterChange({ type: 'numeric_range', min: minValue, max: maxValue });
    } else {
      onFilterChange(null);
    }
  }

  function resetNumericFilter() {
    if (profile.type !== 'numeric') return;
    minValue = profile.min;
    maxValue = profile.max;
    onFilterChange(null);
  }

  // Enum filter handlers
  function toggleEnumValue(value: string) {
    const newSelected = new Set(selectedEnumValues);
    if (newSelected.has(value)) {
      newSelected.delete(value);
    } else {
      newSelected.add(value);
    }
    selectedEnumValues = newSelected;
    updateEnumFilter();
  }

  function updateEnumFilter() {
    if (profile.type !== 'enum') return;
    if (selectedEnumValues.size === profile.values.length) {
      onFilterChange(null);
    } else {
      onFilterChange({ type: 'enum_values', selectedValues: selectedEnumValues });
    }
  }

  function selectAllEnum() {
    if (profile.type !== 'enum') return;
    selectedEnumValues = new Set(profile.values.map(v => v.value));
    onFilterChange(null);
  }

  function selectNoneEnum() {
    selectedEnumValues = new Set();
    updateEnumFilter();
  }

  // Regex filter handlers
  function handleRegexChange(e: Event) {
    const target = e.target as HTMLInputElement;
    regexPattern = target.value;

    try {
      new RegExp(regexPattern);
      regexValid = true;
      if (regexPattern === '') {
        onFilterChange(null);
      } else {
        onFilterChange({ type: 'regex', pattern: regexPattern });
      }
    } catch {
      regexValid = false;
    }
  }

  // Python expression filter handlers
  function handlePythonChange(e: Event) {
    const target = e.target as HTMLInputElement;
    pythonExpression = target.value;

    if (pythonExpression === '') {
      onFilterChange(null);
    } else {
      onFilterChange({ type: 'python_expression', expression: pythonExpression });
    }
  }

  // Helper to format bin labels
  function formatBinLabel(min: number, max: number): string {
    // Handle special values
    if (Number.isNaN(min)) return 'NaN';
    if (min === -Infinity) return '-∞';
    if (min === Infinity) return '∞';

    // Handle regular numeric ranges
    if (min === max) return min.toFixed(2);
    return `${min.toFixed(2)} - ${max.toFixed(2)}`;
  }

  // Derived values
  const maxBinCount = $derived(
    profile.type === 'numeric' ? Math.max(...profile.bins.map(b => b.count), 1) : 1
  );

  const isNumericDirty = $derived(
    profile.type === 'numeric' && (minValue !== profile.min || maxValue !== profile.max)
  );

  // Calculate slider handle positions
  const minPercent = $derived(
    profile.type === 'numeric'
      ? ((minValue - profile.min) / (profile.max - profile.min)) * 100
      : 0
  );

  const maxPercent = $derived(
    profile.type === 'numeric'
      ? ((maxValue - profile.min) / (profile.max - profile.min)) * 100
      : 100
  );
</script>

<div class="filter-widgets">
  {#if profile.type === 'numeric'}
    <!-- Numeric Range Filter -->
    <div class="numeric-range-filter">
      <div class="histogram">
        {#each profile.bins as bin}
          {@const height = (bin.count / maxBinCount) * 100}
          {@const label = formatBinLabel(bin.min, bin.max)}
          {@const isSpecial = !isFinite(bin.min) || Number.isNaN(bin.min)}
          <div
            class="histogram-bar"
            class:special-value={isSpecial}
            style="height: {height}%"
            title="{label}: {bin.count} values"
          ></div>
        {/each}
      </div>

      <div
        class="range-slider-container"
        bind:this={sliderContainer}
        onmousedown={handleTrackMouseDown}
      >
        <div class="range-track"></div>
        <div
          class="range-handle range-handle-min"
          class:dragging={draggingHandle === 'min'}
          style="left: {minPercent}%"
          onmousedown={handleMinDragStart}
          role="slider"
          tabindex="0"
          aria-label="Minimum value"
          aria-valuenow={minValue}
          aria-valuemin={profile.min}
          aria-valuemax={profile.max}
        ></div>
        <div
          class="range-handle range-handle-max"
          class:dragging={draggingHandle === 'max'}
          style="left: {maxPercent}%"
          onmousedown={handleMaxDragStart}
          role="slider"
          tabindex="0"
          aria-label="Maximum value"
          aria-valuenow={maxValue}
          aria-valuemin={profile.min}
          aria-valuemax={profile.max}
        ></div>
      </div>

      <div class="range-labels">
        <span class="range-label">{minValue.toFixed(2)}</span>
        <span class="range-label">{maxValue.toFixed(2)}</span>
      </div>

      {#if isNumericDirty}
        <button class="reset-button" onclick={resetNumericFilter}>Reset</button>
      {/if}
    </div>

  {:else if profile.type === 'enum'}
    <!-- Enum Checkbox Filter -->
    <div class="enum-checkbox-filter">
      <div class="enum-controls">
        <button class="enum-control-button" onclick={selectAllEnum}>All</button>
        <button class="enum-control-button" onclick={selectNoneEnum}>None</button>
      </div>

      <div class="enum-values">
        {#each profile.values as { value, count, percentage }}
          {@const isSelected = selectedEnumValues.has(value)}
          <label class="enum-value-item">
            <input
              type="checkbox"
              checked={isSelected}
              onchange={() => toggleEnumValue(value)}
            />
            <div class="enum-value-content">
              <div class="enum-value-bar" style="width: {percentage}%"></div>
              <span class="enum-value-text">{value}</span>
              <span class="enum-value-count">({count})</span>
            </div>
          </label>
        {/each}
      </div>
    </div>

  {:else if profile.type === 'high_cardinality_string'}
    <!-- Regex Filter -->
    <div class="regex-filter">
      <input
        type="text"
        class="regex-input"
        class:invalid={!regexValid}
        placeholder="Enter regex pattern (e.g., ^[A-Z].*)"
        value={regexPattern}
        oninput={handleRegexChange}
      />
      {#if !regexValid}
        <span class="regex-error">Invalid regex pattern</span>
      {/if}
    </div>

  {:else if profile.type === 'array'}
    <!-- Array Length Distribution Histogram -->
    {@const createHistogramBins = () => {
      const numBins = 10;
      const lengths = profile.lengthDistribution.map(d => d.length);
      const minLength = Math.min(...lengths);
      const maxLength = Math.max(...lengths);
      const range = maxLength - minLength;

      if (range === 0) {
        // All same length
        const totalCount = profile.lengthDistribution.reduce((sum, d) => sum + d.count, 0);
        return [{ minLength, maxLength, count: totalCount, label: String(minLength) }];
      }

      const binSize = Math.ceil(range / numBins);
      const bins = [];

      for (let i = 0; i < numBins; i++) {
        const binMin = minLength + i * binSize;
        const binMax = minLength + (i + 1) * binSize;
        let binCount = 0;

        // Sum up counts for lengths that fall in this bin
        for (const { length, count } of profile.lengthDistribution) {
          if (length >= binMin && (i === numBins - 1 ? length <= binMax : length < binMax)) {
            binCount += count;
          }
        }

        if (binCount > 0) {
          const label = binSize === 1 ? String(binMin) : `${binMin}-${binMax - 1}`;
          bins.push({ minLength: binMin, maxLength: binMax, count: binCount, label });
        }
      }

      return bins;
    }}
    {@const histogramBins = createHistogramBins()}
    {@const maxCount = Math.max(...histogramBins.map(d => d.count), 1)}
    <div class="array-profile">
      <div class="array-histogram">
        {#each histogramBins as bin}
          {@const height = (bin.count / maxCount) * 100}
          {@const totalArrays = profile.lengthDistribution.reduce((sum, d) => sum + d.count, 0)}
          {@const percentage = (bin.count / totalArrays) * 100}
          <div
            class="array-histogram-bar"
            style="height: {height}%"
            title="Length {bin.label}: {bin.count} arrays ({percentage.toFixed(1)}%)"
          ></div>
        {/each}
      </div>
    </div>

  {:else if profile.type === 'object'}
    <!-- Object Profile Display (read-only for now) -->
    <div class="object-profile">
      <div class="profile-title">Object Fields:</div>
      {#each Object.entries(profile.fieldProfiles).slice(0, 5) as [fieldName, fieldInfo]}
        <div class="profile-item">
          <span class="profile-label">{fieldName}:</span>
          <span class="profile-type">{fieldInfo.type}</span>
          <span class="profile-count">({fieldInfo.count} values)</span>
        </div>
      {/each}
    </div>

  {:else}
    <div class="unknown-profile">
      <span class="profile-message">No specific filter available for this column type</span>
    </div>
  {/if}

  <!-- Python Expression Filter (always shown) -->
  <div class="python-expression-filter">
    <label class="python-filter-label">
      Python filter expression:
    </label>
    <input
      type="text"
      class="python-filter-input"
      placeholder="e.g., value > 10 and value < 100"
      value={pythonExpression}
      oninput={handlePythonChange}
    />
    <div class="python-filter-hint">
      Use 'value' to reference the column value
    </div>
  </div>
</div>

<style>
  .filter-widgets {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  /* Numeric Range Filter */
  .numeric-range-filter {
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .histogram {
    display: flex;
    align-items: flex-end;
    height: 60px;
    gap: 1px;
    background: #f3f4f6;
    padding: 4px;
    border-radius: 4px;
  }

  .histogram-bar {
    flex: 1;
    background: linear-gradient(to top, #3b82f6, #60a5fa);
    min-height: 2px;
    transition: opacity 0.2s;
  }

  .histogram-bar.special-value {
    background: linear-gradient(to top, #f59e0b, #fbbf24);
    border-left: 1px solid #d97706;
  }

  .histogram-bar:hover {
    opacity: 0.8;
  }

  .range-slider-container {
    position: relative;
    height: 24px;
    margin: 8px 0;
    cursor: pointer;
  }

  .range-track {
    position: absolute;
    top: 50%;
    left: 0;
    right: 0;
    height: 4px;
    background: #cbd5e1;
    border-radius: 2px;
    transform: translateY(-50%);
    z-index: 1;
  }

  .range-handle {
    position: absolute;
    top: 50%;
    width: 16px;
    height: 16px;
    background: #2563eb;
    cursor: pointer;
    border-radius: 50%;
    border: 2px solid white;
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    transform: translate(-50%, -50%);
    z-index: 4;
    transition: box-shadow 0.2s, transform 0.1s;
  }

  .range-handle:hover {
    box-shadow: 0 2px 6px rgba(0,0,0,0.3);
  }

  .range-handle.dragging {
    z-index: 5;
    box-shadow: 0 4px 8px rgba(0,0,0,0.4);
    transform: translate(-50%, -50%) scale(1.1);
  }

  .range-handle-min {
    /* Additional styles for min handle if needed */
  }

  .range-handle-max {
    /* Additional styles for max handle if needed */
  }

  .range-labels {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: #64748b;
    font-family: monospace;
  }

  .reset-button {
    padding: 4px 12px;
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.8rem;
    transition: all 0.2s;
  }

  .reset-button:hover {
    background: #e2e8f0;
  }

  /* Enum Checkbox Filter */
  .enum-checkbox-filter {
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .enum-controls {
    display: flex;
    gap: 8px;
  }

  .enum-control-button {
    padding: 4px 12px;
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.75rem;
    transition: all 0.2s;
  }

  .enum-control-button:hover {
    background: #e2e8f0;
  }

  .enum-values {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 200px;
    overflow-y: auto;
  }

  .enum-value-item {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: background 0.2s;
  }

  .enum-value-item:hover {
    background: #f8fafc;
  }

  .enum-value-content {
    flex: 1;
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 24px;
    padding: 0 8px;
  }

  .enum-value-bar {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    background: #dbeafe;
    border-radius: 2px;
    z-index: 0;
  }

  .enum-value-text {
    position: relative;
    z-index: 1;
    font-size: 0.85rem;
    font-family: monospace;
    color: #1e293b;
  }

  .enum-value-count {
    position: relative;
    z-index: 1;
    font-size: 0.75rem;
    color: #64748b;
    margin-left: auto;
  }

  /* Regex Filter */
  .regex-filter {
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .regex-input {
    width: 100%;
    padding: 6px 10px;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    font-size: 0.85rem;
    font-family: monospace;
  }

  .regex-input:focus {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
  }

  .regex-input.invalid {
    border-color: #dc2626;
  }

  .regex-error {
    font-size: 0.75rem;
    color: #dc2626;
  }

  /* Profile Display Styles */
  .array-profile,
  .object-profile {
    padding: 12px;
    font-size: 0.85rem;
  }

  .profile-title {
    font-weight: 600;
    margin-bottom: 8px;
    color: #475569;
  }

  .profile-item {
    display: flex;
    gap: 8px;
    padding: 4px 0;
    align-items: baseline;
  }

  .profile-label {
    color: #64748b;
    font-family: monospace;
  }

  .profile-type {
    color: #3b82f6;
    font-family: monospace;
    font-size: 0.8rem;
  }

  .profile-count {
    color: #64748b;
    font-size: 0.8rem;
  }

  /* Array Histogram */
  .array-histogram {
    display: flex;
    align-items: flex-end;
    height: 60px;
    gap: 1px;
    background: #f3f4f6;
    padding: 4px;
    border-radius: 4px;
  }

  .array-histogram-bar {
    flex: 1;
    background: linear-gradient(to top, #3b82f6, #60a5fa);
    min-height: 2px;
    transition: opacity 0.2s;
  }

  .array-histogram-bar:hover {
    opacity: 0.8;
  }

  .unknown-profile {
    padding: 12px;
    text-align: center;
  }

  .profile-message {
    color: #64748b;
    font-size: 0.85rem;
    font-style: italic;
  }

  /* Python Expression Filter */
  .python-expression-filter {
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    border-top: 1px solid #e5e7eb;
  }

  .python-filter-label {
    font-size: 0.8rem;
    font-weight: 500;
    color: #475569;
  }

  .python-filter-input {
    width: 100%;
    padding: 6px 10px;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    font-size: 0.85rem;
    font-family: monospace;
  }

  .python-filter-input:focus {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
  }

  .python-filter-hint {
    font-size: 0.7rem;
    color: #64748b;
    font-style: italic;
  }
</style>
