<script lang="ts">
  import type { AutopsyData, ComputedColumn, LogMark } from "./types";
  import NotebookMarkdownCell from "./NotebookMarkdownCell.svelte";
  import NotebookHistoryCell from "./NotebookHistoryCell.svelte";
  import NotebookStreamCell from "./NotebookStreamCell.svelte";
  import NotebookVisualizationCell from "./NotebookVisualizationCell.svelte";
  import { saveNotebookCells, restoreNotebookCells, type PersistedNotebookCell } from "./persistence";
  import { isVSCodeWebview } from "./vscodeApi";

  interface NotebookCell {
    id: string;
    type: "markdown" | "history" | "stream" | "visualization";
    markdownContent?: string;
    historyTestFilter?: string | null;
    historyFrameFilter?: string | null;
    historyRangeFilter?: { start: number; end: number } | null;
    streamCallSiteKey?: string | null;
    isExpanded?: boolean;
  }

  interface Props {
    data: AutopsyData;
    logMarks?: Record<number, LogMark>;
    computedColumns?: Record<string, ComputedColumn[]>;
    columnOrders?: Record<string, string[]>;
    onMarkLog?: (logIndex: number, color: string, note: string) => void;
    onEntryClick?: (logIndex: number, stackTraceId?: string) => void;
  }

  let {
    data,
    logMarks = {},
    computedColumns = {},
    columnOrders = {},
    onMarkLog,
    onEntryClick,
  }: Props = $props();

  // Initialize cells - skip localStorage restore in VS Code webview
  let cells = $state<NotebookCell[]>(
    isVSCodeWebview() ? [] : restoreNotebookCells().map(c => ({
      id: c.id,
      type: c.type,
      markdownContent: c.markdownContent,
      historyTestFilter: c.historyTestFilter ?? null,
      historyFrameFilter: c.historyFrameFilter ?? null,
      historyRangeFilter: c.historyRangeFilter ?? null,
      streamCallSiteKey: c.streamCallSiteKey ?? null,
      isExpanded: c.isExpanded ?? false,
    }))
  );

  // Persist cells to localStorage when they change (skip in VS Code webview)
  $effect(() => {
    // Skip persistence in VS Code webview
    if (isVSCodeWebview()) return;

    const toSave: PersistedNotebookCell[] = cells.map(c => ({
      id: c.id,
      type: c.type,
      markdownContent: c.markdownContent,
      historyTestFilter: c.historyTestFilter,
      historyFrameFilter: c.historyFrameFilter,
      historyRangeFilter: c.historyRangeFilter,
      streamCallSiteKey: c.streamCallSiteKey,
      isExpanded: c.isExpanded,
    }));
    saveNotebookCells(toSave);
  });

  function addCell(index: number, type: NotebookCell["type"]) {
    const newCell: NotebookCell = {
      id: crypto.randomUUID(),
      type,
      isExpanded: false,
      markdownContent: type === "markdown" ? "" : undefined,
      historyTestFilter: null,
      historyFrameFilter: null,
      historyRangeFilter: null,
      streamCallSiteKey: null,
    };
    cells = [...cells.slice(0, index), newCell, ...cells.slice(index)];
  }

  function removeCell(index: number) {
    cells = [...cells.slice(0, index), ...cells.slice(index + 1)];
  }

  function moveCell(index: number, direction: -1 | 1) {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= cells.length) return;
    const newCells = [...cells];
    [newCells[index], newCells[newIndex]] = [newCells[newIndex], newCells[index]];
    cells = newCells;
  }
</script>

<div class="notebook">
  {#if cells.length === 0}
    <div class="empty-notebook">
      <p>Start your analysis notebook</p>
      <div class="add-cell-bar">
        <button class="add-cell-button" onclick={() => addCell(0, "markdown")}>+ Markdown</button>
        <button class="add-cell-button" onclick={() => addCell(0, "history")}>+ History</button>
        <button class="add-cell-button" onclick={() => addCell(0, "stream")}>+ Stream</button>
        <button class="add-cell-button" onclick={() => addCell(0, "visualization")}>+ Visualization</button>
      </div>
    </div>
  {/if}

  {#each cells as cell, index (cell.id)}
    <div class="notebook-cell-wrapper">
      <div class="cell-toolbar">
        <span class="cell-type-label">{cell.type}</span>
        <div class="cell-toolbar-actions">
          <button class="cell-action" onclick={() => moveCell(index, -1)} disabled={index === 0} title="Move up">&#9650;</button>
          <button class="cell-action" onclick={() => moveCell(index, 1)} disabled={index === cells.length - 1} title="Move down">&#9660;</button>
          <button class="cell-action cell-delete" onclick={() => removeCell(index)} title="Delete cell">&#10005;</button>
        </div>
      </div>

      {#if cell.type === "markdown"}
        <NotebookMarkdownCell bind:content={cell.markdownContent} />
      {:else if cell.type === "history"}
        <NotebookHistoryCell
          {data}
          {logMarks}
          {computedColumns}
          {columnOrders}
          bind:testFilter={cell.historyTestFilter}
          bind:frameFilter={cell.historyFrameFilter}
          bind:rangeFilter={cell.historyRangeFilter}
          bind:isExpanded={cell.isExpanded}
          {onMarkLog}
          {onEntryClick}
        />
      {:else if cell.type === "stream"}
        <NotebookStreamCell
          {data}
          {logMarks}
          {columnOrders}
          bind:callSiteKey={cell.streamCallSiteKey}
          bind:isExpanded={cell.isExpanded}
          {onMarkLog}
          {onEntryClick}
        />
      {:else if cell.type === "visualization"}
        <NotebookVisualizationCell />
      {/if}
    </div>

    <div class="add-cell-bar">
      <button class="add-cell-button" onclick={() => addCell(index + 1, "markdown")}>+ Markdown</button>
      <button class="add-cell-button" onclick={() => addCell(index + 1, "history")}>+ History</button>
      <button class="add-cell-button" onclick={() => addCell(index + 1, "stream")}>+ Stream</button>
      <button class="add-cell-button" onclick={() => addCell(index + 1, "visualization")}>+ Visualization</button>
    </div>
  {/each}
</div>

<style>
  .notebook {
    padding: 1rem;
    max-width: 1200px;
    margin: 0 auto;
  }

  .empty-notebook {
    text-align: center;
    color: #666;
    padding: 3rem;
  }

  .empty-notebook p {
    font-size: 1.1rem;
    margin-bottom: 1rem;
  }

  .notebook-cell-wrapper {
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #fff;
    margin-bottom: 0;
  }

  .cell-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.25rem 0.5rem;
    background: #f9fafb;
    border-bottom: 1px solid #e5e7eb;
    border-radius: 8px 8px 0 0;
  }

  .cell-type-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .cell-toolbar-actions {
    display: flex;
    gap: 0.25rem;
  }

  .cell-action {
    background: none;
    border: none;
    color: #94a3b8;
    cursor: pointer;
    padding: 0.15rem 0.4rem;
    border-radius: 3px;
    font-size: 0.75rem;
    transition: color 0.2s, background-color 0.2s;
  }

  .cell-action:hover {
    color: #475569;
    background: #e2e8f0;
  }

  .cell-action:disabled {
    opacity: 0.3;
    cursor: default;
  }

  .cell-delete:hover {
    color: #dc2626;
    background: #fee2e2;
  }

  .add-cell-bar {
    display: flex;
    gap: 0.5rem;
    justify-content: center;
    padding: 0.5rem;
    opacity: 0;
    transition: opacity 0.2s;
  }

  .add-cell-bar:hover,
  .empty-notebook .add-cell-bar {
    opacity: 1;
  }

  .add-cell-button {
    background: none;
    border: 1px dashed #d1d5db;
    color: #64748b;
    padding: 0.25rem 0.75rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.8rem;
    transition: all 0.2s;
  }

  .add-cell-button:hover {
    border-color: #2563eb;
    color: #2563eb;
    background: #eff6ff;
  }
</style>
