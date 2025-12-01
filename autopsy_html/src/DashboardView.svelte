<script lang="ts">
  import type {
    AutopsyData,
    DashboardCallSite,
    CountEntry,
    HistogramEntry,
    TimelineEntry,
    HappenedEntry,
  } from "./types";

  interface Props {
    data: AutopsyData;
    selectedLogIndex?: number | null;
    selectedElementKey?: string | null;
    onEntryClick?: (stackTraceIds: string[], elementKey: string) => void;
  }

  let {
    data,
    selectedLogIndex = null,
    selectedElementKey = null,
    onEntryClick,
  }: Props = $props();

  function getFilename(callSite: DashboardCallSite): string {
    const parts = callSite.filename.split("/");
    return parts[parts.length - 1];
  }

  function handleCountClick(
    entryIndex: number,
    valueKey: string,
    stackTraceIds: string[]
  ) {
    if (stackTraceIds.length > 0 && onEntryClick) {
      const key = `count-${entryIndex}-${valueKey}`;
      onEntryClick(stackTraceIds, key);
    }
  }

  function handleHistogramClick(
    entryIndex: number,
    binIndex: number,
    stackTraceIds: string[]
  ) {
    if (stackTraceIds.length > 0 && onEntryClick) {
      const key = `histogram-${entryIndex}-${binIndex}`;
      onEntryClick(stackTraceIds, key);
    }
  }

  function handleTimelineClick(entryIndex: number, entry: TimelineEntry) {
    if (entry.stack_trace_id && onEntryClick) {
      const key = `timeline-${entryIndex}`;
      onEntryClick([entry.stack_trace_id], key);
    }
  }

  function handleHappenedClick(entryIndex: number, entry: HappenedEntry) {
    if (entry.stack_trace_ids.length > 0 && onEntryClick) {
      const key = `happened-${entryIndex}`;
      onEntryClick(entry.stack_trace_ids, key);
    }
  }

  // Helper to compute histogram bins
  function computeHistogramBins(
    values: number[],
    numBins: number = 10
  ): {
    bins: number[];
    counts: number[];
  } {
    if (values.length === 0) {
      return { bins: [], counts: [] };
    }
    const min = Math.min(...values);
    const max = Math.max(...values);
    const binWidth = (max - min) / numBins || 1;
    const bins: number[] = [];
    const counts: number[] = new Array(numBins).fill(0);

    for (let i = 0; i < numBins; i++) {
      bins.push(min + i * binWidth);
    }

    for (const value of values) {
      let binIndex = Math.floor((value - min) / binWidth);
      if (binIndex >= numBins) binIndex = numBins - 1;
      counts[binIndex]++;
    }

    return { bins, counts };
  }

  function getMaxCount(
    counts: Record<string, { count: number; stack_trace_ids: string[] }>
  ): number {
    return Math.max(...Object.values(counts).map((v) => v.count), 0);
  }

</script>

{#if !data.dashboard || (!data.dashboard.counts.length && !data.dashboard.histograms.length && !data.dashboard.timeline.length && !data.dashboard.happened.length)}
  <p class="empty">No dashboard data available.</p>
{:else}
  <div class="dashboard">
    {#if data.dashboard.counts.length > 0}
      <section class="dashboard-section">
        <h2>Value Counts</h2>
        {#each data.dashboard.counts as entry, entryIndex}
          <div class="dashboard-entry">
            <div class="call-site-header">
              <span class="filename"
                >{getFilename(entry.call_site)}<span class="line-number"
                  >:{entry.call_site.line}</span
                ></span
              >
              <span class="function-name">
                in <code>
                  {#if entry.call_site.class_name}
                    {entry.call_site.class_name}.{entry.call_site.function_name}
                  {:else}
                    {entry.call_site.function_name}
                  {/if}
                </code>
              </span>
            </div>
            <div class="counts-chart">
              {#each Object.entries(entry.value_counts) as [valueKey, valueData]}
                {@const maxCount = getMaxCount(entry.value_counts)}
                {@const barWidth =
                  maxCount > 0 ? (valueData.count / maxCount) * 100 : 0}
                {@const elementKey = `count-${entryIndex}-${valueKey}`}
                <div
                  class="count-bar"
                  class:clickable={valueData.stack_trace_ids.length > 0}
                  class:selected={selectedElementKey === elementKey}
                  onclick={() =>
                    onEntryClick?.(valueData.stack_trace_ids, elementKey)}
                  role={valueData.stack_trace_ids.length > 0
                    ? "button"
                    : undefined}
                  tabindex={valueData.stack_trace_ids.length > 0
                    ? 0
                    : undefined}
                  onkeydown={(e) => {
                    if (
                      valueData.stack_trace_ids.length > 0 &&
                      (e.key === "Enter" || e.key === " ")
                    ) {
                      e.preventDefault();
                    onEntryClick?.(valueData.stack_trace_ids, elementKey);
                    }
                  }}
                >
                  <div class="bar-label">
                    <span class="value-key">{valueKey}</span>
                    <span class="value-count">{valueData.count}</span>
                  </div>
                  <div class="bar-container">
                    <div class="bar-fill" style="width: {barWidth}%"></div>
                  </div>
                </div>
              {/each}
            </div>
          </div>
        {/each}
      </section>
    {/if}

    {#if data.dashboard.histograms.length > 0}
      <section class="dashboard-section">
        <h2>Histograms</h2>
        {#each data.dashboard.histograms as entry, entryIndex}
          {@const values = entry.values.map((v) => v.value)}
          {@const { bins, counts } = computeHistogramBins(values)}
          {@const maxCount = Math.max(...counts, 0)}
          <div class="dashboard-entry">
            <div class="call-site-header">
              <span class="filename"
                >{getFilename(entry.call_site)}<span class="line-number"
                  >:{entry.call_site.line}</span
                ></span
              >
              <span class="function-name">
                in <code>
                  {#if entry.call_site.class_name}
                    {entry.call_site.class_name}.{entry.call_site.function_name}
                  {:else}
                    {entry.call_site.function_name}
                  {/if}
                </code>
              </span>
            </div>
            <div class="histogram-chart">
              {#each counts as count, i}
                {@const barHeight = maxCount > 0 ? (count / maxCount) * 100 : 0}
                {@const binStart = bins[i]}
                {@const binEnd =
                  i < bins.length - 1 ? bins[i + 1] : Math.max(...values)}
                {@const valuesInBin = entry.values.filter(
                  (v) =>
                    v.value >= binStart &&
                    (i === counts.length - 1 || v.value < binEnd)
                )}
                {@const stackTraceIds = valuesInBin
                  .map((v) => v.stack_trace_id)
                  .filter((id): id is string => id !== undefined)}
                {@const elementKey = `histogram-${entryIndex}-${i}`}
                <div
                  class="histogram-bar"
                  class:clickable={stackTraceIds.length > 0}
                  class:selected={selectedElementKey === elementKey}
                  onclick={() => {
                    if (stackTraceIds.length > 0) {
                      onEntryClick?.(stackTraceIds, elementKey);
                    }
                  }}
                  role={stackTraceIds.length > 0 ? "button" : undefined}
                  tabindex={stackTraceIds.length > 0 ? 0 : undefined}
                  onkeydown={(e) => {
                    if (
                      stackTraceIds.length > 0 &&
                      (e.key === "Enter" || e.key === " ")
                    ) {
                      e.preventDefault();
                      onEntryClick?.(stackTraceIds, elementKey);
                    }
                  }}
                  title="{binStart.toFixed(2)} - {binEnd.toFixed(
                    2
                  )}: {count} values"
                >
                  <div class="bar-value">{count}</div>
                  <div
                    class="bar-fill-vertical"
                    style="height: {barHeight}%"
                  ></div>
                </div>
              {/each}
            </div>
          </div>
        {/each}
      </section>
    {/if}

    {#if data.dashboard.timeline.length > 0}
      <section class="dashboard-section">
        <h2>Timeline</h2>
        <div class="timeline-container">
          {#each data.dashboard.timeline as entry, index}
            {@const isLast = index === data.dashboard.timeline.length - 1}
            {@const prevTimestamp =
              index > 0
                ? data.dashboard.timeline[index - 1].timestamp
                : entry.timestamp}
            {@const timeDiff = entry.timestamp - prevTimestamp}
            {@const elementKey = `timeline-${index}`}
            <div
              class="timeline-entry"
              class:clickable={entry.stack_trace_id !== undefined}
              class:selected={selectedElementKey === elementKey}
              onclick={() => {
                onEntryClick?.(
                  entry.stack_trace_id ? [entry.stack_trace_id] : [],
                  elementKey
                );
              }}
              role={entry.stack_trace_id !== undefined ? "button" : undefined}
              tabindex={entry.stack_trace_id !== undefined ? 0 : undefined}
              onkeydown={(e) => {
                if (
                  entry.stack_trace_id !== undefined &&
                  (e.key === "Enter" || e.key === " ")
                ) {
                  e.preventDefault();
                    onEntryClick?.(
                      entry.stack_trace_id ? [entry.stack_trace_id] : [],
                      elementKey
                    );
                }
              }}
            >
              <div class="timeline-marker-container">
                <div
                  class="timeline-marker"
                  class:selected={selectedElementKey === elementKey}
                ></div>
                {#if !isLast}
                  <div class="timeline-line"></div>
                {/if}
              </div>
              <div class="timeline-content">
                <div class="timeline-event-name">{entry.event_name}</div>
                <div class="timeline-call-site">
                  <span class="filename"
                    >{getFilename(entry.call_site)}<span class="line-number"
                      >:{entry.call_site.line}</span
                    ></span
                  >
                  <span class="function-name">
                    in <code>
                      {#if entry.call_site.class_name}
                        {entry.call_site.class_name}.{entry.call_site
                          .function_name}
                      {:else}
                        {entry.call_site.function_name}
                      {/if}
                    </code>
                  </span>
                </div>
                <div class="timeline-time">
                  {new Date(entry.timestamp * 1000).toLocaleString()}
                  {#if index > 0}
                    <span class="time-diff"> (+{timeDiff.toFixed(3)}s)</span>
                  {/if}
                </div>
              </div>
            </div>
          {/each}
        </div>
      </section>
    {/if}

    {#if data.dashboard.happened.length > 0}
      <section class="dashboard-section">
        <h2>Invocation Counts</h2>
        {#each data.dashboard.happened as entry, entryIndex}
          {@const elementKey = `happened-${entryIndex}`}
          <div
            class="happened-entry"
            class:clickable={entry.stack_trace_ids.length > 0}
            class:selected={selectedElementKey === elementKey}
            onclick={() => {
              onEntryClick?.(entry.stack_trace_ids, elementKey);
            }}
            role={entry.stack_trace_ids.length > 0 ? "button" : undefined}
            tabindex={entry.stack_trace_ids.length > 0 ? 0 : undefined}
            onkeydown={(e) => {
              if (
                entry.stack_trace_ids.length > 0 &&
                (e.key === "Enter" || e.key === " ")
              ) {
                e.preventDefault();
                    onEntryClick?.(entry.stack_trace_ids, elementKey);
              }
            }}
          >
            <div class="happened-count">{entry.count}</div>
            <div class="happened-info">
              <div class="call-site-header">
                <span class="filename"
                  >{getFilename(entry.call_site)}<span class="line-number"
                    >:{entry.call_site.line}</span
                  ></span
                >
                <span class="function-name">
                  in <code>
                    {#if entry.call_site.class_name}
                      {entry.call_site.class_name}.{entry.call_site
                        .function_name}
                    {:else}
                      {entry.call_site.function_name}
                    {/if}
                  </code>
                </span>
              </div>
              {#if entry.message}
                <div class="happened-message">{entry.message}</div>
              {/if}
            </div>
          </div>
        {/each}
      </section>
    {/if}
  </div>
{/if}

<style>
  .empty {
    text-align: center;
    color: #666;
    padding: 3rem;
  }

  .dashboard {
    display: flex;
    flex-direction: column;
    gap: 2rem;
  }

  .dashboard-section {
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 1.5rem;
    background: #f9f9f9;
  }

  .dashboard-section h2 {
    margin: 0 0 1rem 0;
    color: #333;
    font-size: 1.3rem;
  }

  .dashboard-entry {
    margin-bottom: 1.5rem;
  }

  .dashboard-entry:last-child {
    margin-bottom: 0;
  }

  .call-site-header {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-bottom: 1rem;
  }

  .filename {
    font-weight: 600;
    color: #2563eb;
    font-size: 1rem;
  }

  .line-number {
    margin-left: 0.25rem;
    font-weight: 400;
    font-size: 0.9rem;
    color: #666;
  }

  .function-name {
    margin-left: 0.4rem;
    color: #666;
    font-size: 0.9rem;
    font-weight: 500;
  }

  .function-name code {
    background: #f0f0f0;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    color: #2563eb;
  }

  /* Counts chart */
  .counts-chart {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .count-bar {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .count-bar.clickable {
    cursor: pointer;
  }

  .count-bar.clickable:hover {
    opacity: 0.8;
  }

  .count-bar.selected .bar-fill {
    background: #1d4ed8;
    box-shadow: 0 0 0 2px #93c5fd;
  }

  .count-bar.selected .bar-container {
    box-shadow: 0 0 0 2px #93c5fd;
  }

  .bar-label {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.85rem;
  }

  .value-key {
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    color: #333;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .value-count {
    font-weight: 600;
    color: #2563eb;
    margin-left: 0.5rem;
  }

  .bar-container {
    height: 24px;
    background: #e5e7eb;
    border-radius: 4px;
    overflow: hidden;
  }

  .bar-fill {
    height: 100%;
    background: #2563eb;
    transition: width 0.3s ease;
  }

  /* Histogram chart */
  .histogram-chart {
    display: flex;
    align-items: flex-end;
    gap: 4px;
    height: 200px;
    padding: 0.5rem;
    background: white;
    border: 1px solid #e5e5e5;
    border-radius: 4px;
  }

  .histogram-bar {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-end;
    position: relative;
    min-width: 20px;
    height: 100%;
  }

  .histogram-bar.clickable {
    cursor: pointer;
  }

  .histogram-bar.clickable:hover {
    opacity: 0.8;
  }

  .histogram-bar.selected .bar-fill-vertical {
    background: #1d4ed8;
    box-shadow: 0 0 0 2px #93c5fd;
  }

  .bar-value {
    font-size: 0.75rem;
    color: #666;
    margin-bottom: 2px;
  }

  .bar-fill-vertical {
    width: 100%;
    background: #2563eb;
    border-radius: 2px 2px 0 0;
    transition: height 0.3s ease;
    min-height: 2px;
  }

  /* Timeline */
  .timeline-container {
    position: relative;
    padding-left: 2rem;
  }

  .timeline-entry {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
    position: relative;
    padding: 0.5rem;
    margin-left: -0.5rem;
    border-radius: 6px;
    transition: background-color 0.2s;
  }

  .timeline-entry:last-child {
    margin-bottom: 0;
  }

  .timeline-entry.clickable {
    cursor: pointer;
  }

  .timeline-entry.clickable:hover {
    background: rgba(37, 99, 235, 0.05);
  }

  .timeline-entry.selected {
    background: rgba(37, 99, 235, 0.1);
  }

  .timeline-marker-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    position: absolute;
    left: 0;
  }

  .timeline-marker {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #2563eb;
    border: 2px solid white;
    box-shadow: 0 0 0 2px #2563eb;
    flex-shrink: 0;
    z-index: 1;
    transition: transform 0.2s, background-color 0.2s;
  }

  .timeline-marker.selected {
    background: #1d4ed8;
    transform: scale(1.3);
    box-shadow: 0 0 0 3px #1d4ed8;
  }

  .timeline-line {
    width: 2px;
    background: #e5e7eb;
    flex: 1;
    min-height: 20px;
    margin-top: 6px;
  }

  .timeline-content {
    flex: 1;
    padding-left: 1rem;
  }

  .timeline-event-name {
    font-weight: 600;
    color: #333;
    font-size: 1rem;
    margin-bottom: 0.25rem;
  }

  .timeline-call-site {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-bottom: 0.25rem;
    font-size: 0.85rem;
  }

  .timeline-time {
    color: #666;
    font-size: 0.8rem;
  }

  .time-diff {
    color: #999;
  }

  /* Happened entries */
  .happened-entry {
    display: flex;
    gap: 1rem;
    padding: 1rem;
    background: white;
    border: 1px solid #e5e5e5;
    border-radius: 6px;
    margin-bottom: 0.75rem;
    transition: all 0.2s;
  }

  .happened-entry:last-child {
    margin-bottom: 0;
  }

  .happened-entry.clickable {
    cursor: pointer;
  }

  .happened-entry.clickable:hover {
    border-color: #2563eb;
    background: #f8fafc;
  }

  .happened-entry.selected {
    border-color: #1d4ed8;
    background: #eff6ff;
    box-shadow: 0 0 0 2px #93c5fd;
  }

  .happened-count {
    font-size: 2rem;
    font-weight: 600;
    color: #2563eb;
    flex-shrink: 0;
    min-width: 3rem;
    text-align: center;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .happened-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .happened-message {
    color: #881391;
    font-size: 0.9rem;
    font-weight: 500;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
  }
</style>
