<script lang="ts">
  import type { AutopsyData, CallSite, ComputedColumn } from "./types";
  import { evaluateComputedColumnBatch, generateColumnId } from "./computedColumns";
  import { pythonExecutor } from "./pythonExecutor";
  import TreeView from "./TreeView.svelte";

  interface Props {
    data: AutopsyData;
    callSite: CallSite;
    callSiteKey: string;
    existingColumn?: ComputedColumn;
    onSave: (column: ComputedColumn) => void;
    onDelete?: () => void;
    onClose: () => void;
  }

  let { data, callSite, callSiteKey, existingColumn, onSave, onDelete, onClose }: Props = $props();

  // Form state
  let title = $state(existingColumn?.title || '');
  let expression = $state(existingColumn?.expression || '');
  let previewResults = $state<Map<number, {value: unknown, error?: string}>>(new Map());
  let isEvaluating = $state(false);
  let loadingPyodide = $state(false);
  let showAllPreview = $state(false);

  const isEditMode = existingColumn !== undefined;

  // Real-time preview evaluation (debounced, async for Python)
  let evaluationTimeout: number | null = null;
  $effect(() => {
    if (evaluationTimeout) clearTimeout(evaluationTimeout);

    if (!expression.trim()) {
      previewResults = new Map();
      return;
    }

    isEvaluating = true;
    evaluationTimeout = setTimeout(async () => {
      // Check if Pyodide needs loading
      if (!pythonExecutor.isReady() && pythonExecutor.getStatus() === 'uninitialized') {
        loadingPyodide = true;
      }

      try {
        const results = await evaluateComputedColumnBatch(
          expression,
          callSite.value_groups,
          data
        );

        const resultsMap = new Map();
        callSite.value_groups.forEach((vg, i) => {
          resultsMap.set(vg.log_index, results[i]);
        });
        previewResults = resultsMap;
      } catch (error) {
        console.error('Python evaluation error:', error);
      } finally {
        loadingPyodide = false;
        isEvaluating = false;
      }
    }, 300) as unknown as number;
  });

  function handleSave() {
    const column: ComputedColumn = {
      id: existingColumn?.id || generateColumnId(),
      title: title.trim() || undefined,
      expression: expression.trim(),
      callSiteKey,
    };
    onSave(column);
  }

  function handleDelete() {
    if (onDelete) onDelete();
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }

  const previewEntries = $derived(
    showAllPreview
      ? Array.from(previewResults.entries())
      : Array.from(previewResults.entries()).slice(0, 10)
  );
</script>

<div class="modal-backdrop" onclick={handleBackdropClick}>
  <div class="modal-content" onclick={(e) => e.stopPropagation()}>
    <div class="modal-header">
      <h2>{isEditMode ? 'Edit' : 'Add'} Computed Column</h2>
      <button class="close-button" onclick={onClose}>×</button>
    </div>

    <div class="modal-body">
      <div class="form-group">
        <label for="title">Title (optional)</label>
        <input
          id="title"
          type="text"
          bind:value={title}
          placeholder="Leave blank to use expression"
          class="form-input"
        />
      </div>

      <div class="form-group">
        <label for="expression">Python Code</label>
        <textarea
          id="expression"
          bind:value={expression}
          placeholder="e.g., trace['frames'][0]['filename']"
          rows="8"
          class="form-textarea python-code"
        />
        <div class="expression-help">
          Python code with access to <code>trace</code> variable (StackTrace object).
          You can write multiple statements. The last expression is returned.
        </div>
      </div>

      <div class="preview-section">
        <h3>Preview ({callSite.value_groups.length} rows)</h3>
        {#if loadingPyodide}
          <div class="pyodide-loading">
            <div class="loading-spinner"></div>
            <div>Loading Python interpreter (first time only, ~10s)...</div>
          </div>
        {:else if isEvaluating}
          <div class="preview-loading">Evaluating...</div>
        {:else if previewResults.size === 0}
          <div class="preview-empty">Enter an expression to see preview</div>
        {:else}
          <div class="preview-table-container">
            <table class="preview-table">
              <thead>
                <tr>
                  <th>Log #</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {#each previewEntries as [logIndex, result]}
                  <tr>
                    <td class="log-index">#{logIndex}</td>
                    <td class="result-cell">
                      {#if result.error}
                        <span class="error-badge">{result.error}</span>
                      {:else if result.value === undefined}
                        <span class="undefined-value">undefined</span>
                      {:else}
                        <TreeView value={result.value} />
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
          {#if callSite.value_groups.length > 10 && !showAllPreview}
            <button class="show-all-button" onclick={() => showAllPreview = true}>
              Show all {callSite.value_groups.length} rows
            </button>
          {/if}
        {/if}
      </div>
    </div>

    <div class="modal-footer">
      <div class="footer-left">
        {#if isEditMode && onDelete}
          <button class="delete-button" onclick={handleDelete}>Delete</button>
        {/if}
      </div>
      <div class="footer-right">
        <button class="cancel-button" onclick={onClose}>Cancel</button>
        <button
          class="save-button"
          onclick={handleSave}
          disabled={!expression.trim()}
        >
          {isEditMode ? 'Save' : 'Add'}
        </button>
      </div>
    </div>
  </div>
</div>

<style>
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 1rem;
  }

  .modal-content {
    background: white;
    border-radius: 8px;
    max-width: 800px;
    width: 100%;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid #e5e5e5;
  }

  .modal-header h2 {
    margin: 0;
    font-size: 1.5rem;
    color: #333;
  }

  .close-button {
    background: none;
    border: none;
    font-size: 2rem;
    color: #666;
    cursor: pointer;
    padding: 0;
    width: 2rem;
    height: 2rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: background-color 0.2s;
  }

  .close-button:hover {
    background-color: #f0f0f0;
  }

  .modal-body {
    padding: 1.5rem;
    overflow-y: auto;
    flex: 1;
  }

  .form-group {
    margin-bottom: 1.5rem;
  }

  .form-group label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 600;
    color: #333;
    font-size: 0.9rem;
  }

  .form-input, .form-textarea {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.9rem;
    font-family: inherit;
    transition: border-color 0.2s;
  }

  .form-textarea {
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    resize: vertical;
  }

  .form-textarea.python-code {
    line-height: 1.5;
  }

  .expression-help code {
    background: #f3f4f6;
    padding: 0.125rem 0.375rem;
    border-radius: 3px;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    font-size: 0.85em;
  }

  .form-input:focus, .form-textarea:focus {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
  }

  .expression-help {
    margin-top: 0.5rem;
    font-size: 0.85rem;
    color: #666;
  }


  .preview-section {
    margin-top: 2rem;
  }

  .preview-section h3 {
    margin: 0 0 1rem 0;
    font-size: 1.1rem;
    color: #333;
  }

  .preview-loading, .preview-empty {
    text-align: center;
    padding: 2rem;
    color: #666;
    font-style: italic;
  }

  .pyodide-loading {
    text-align: center;
    padding: 2rem;
    color: #2563eb;
  }

  .loading-spinner {
    border: 3px solid #f3f4f6;
    border-top: 3px solid #2563eb;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    animation: spin 1s linear infinite;
    margin: 0 auto 1rem;
  }

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  .preview-table-container {
    border: 1px solid #e5e5e5;
    border-radius: 4px;
    overflow: auto;
    max-height: 300px;
  }

  .preview-table {
    width: 100%;
    border-collapse: collapse;
  }

  .preview-table th {
    background: #f9fafb;
    padding: 0.75rem;
    text-align: left;
    font-weight: 600;
    font-size: 0.85rem;
    color: #666;
    border-bottom: 2px solid #e5e5e5;
    position: sticky;
    top: 0;
  }

  .preview-table td {
    padding: 0.75rem;
    border-bottom: 1px solid #e5e5e5;
    font-size: 0.85rem;
  }

  .log-index {
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    color: #2563eb;
    font-weight: 600;
    width: 80px;
  }

  .result-cell {
    max-width: 500px;
    overflow: auto;
  }

  .error-badge {
    background: #fee2e2;
    color: #dc2626;
    padding: 0.25rem 0.5rem;
    border-radius: 3px;
    font-size: 0.8rem;
    font-weight: 600;
  }

  .undefined-value {
    color: #9ca3af;
    font-style: italic;
  }

  .show-all-button {
    margin-top: 0.75rem;
    padding: 0.5rem 1rem;
    background: #f3f4f6;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
    color: #374151;
    transition: background-color 0.2s;
  }

  .show-all-button:hover {
    background: #e5e7eb;
  }

  .modal-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    border-top: 1px solid #e5e5e5;
  }

  .footer-left, .footer-right {
    display: flex;
    gap: 0.75rem;
  }

  .delete-button {
    padding: 0.75rem 1.5rem;
    background: #fee2e2;
    color: #dc2626;
    border: 1px solid #dc2626;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.9rem;
    transition: background-color 0.2s;
  }

  .delete-button:hover {
    background: #fecaca;
  }

  .cancel-button {
    padding: 0.75rem 1.5rem;
    background: white;
    color: #374151;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.9rem;
    transition: background-color 0.2s;
  }

  .cancel-button:hover {
    background: #f9fafb;
  }

  .save-button {
    padding: 0.75rem 1.5rem;
    background: #2563eb;
    color: white;
    border: 1px solid #2563eb;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.9rem;
    transition: background-color 0.2s;
  }

  .save-button:hover:not(:disabled) {
    background: #1d4ed8;
  }

  .save-button:disabled {
    background: #9ca3af;
    border-color: #9ca3af;
    cursor: not-allowed;
    opacity: 0.6;
  }
</style>
