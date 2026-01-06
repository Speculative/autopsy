<script lang="ts">
  import type { AutopsyData, CallSite, ComputedColumn } from "./types";
  import { evaluateComputedColumnBatch, generateColumnId } from "./computedColumns";
  import { pythonExecutor } from "./pythonExecutor";
  import TreeView from "./TreeView.svelte";
  import CodeEditor from "./CodeEditor.svelte";

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
  let lastValidResults = $state<Map<number, {value: unknown, error?: string}>>(new Map());
  let lastValidExpression = $state(existingColumn?.expression || '');
  let currentError = $state<string | null>(null);
  let isEvaluating = $state(false);
  let loadingPyodide = $state(false);
  let showAllPreview = $state(false);

  const isEditMode = existingColumn !== undefined;

  // Check if all results are errors
  const allResultsAreErrors = $derived(
    previewResults.size > 0 &&
    Array.from(previewResults.values()).every(r => r.error !== undefined)
  );

  // Determine which results to display
  const displayResults = $derived(
    allResultsAreErrors ? lastValidResults : previewResults
  );

  // Determine if we're showing fallback results
  const showingFallback = $derived(
    allResultsAreErrors && lastValidResults.size > 0
  );

  // Real-time preview evaluation (debounced, async for Python)
  let evaluationTimeout: number | null = null;
  $effect(() => {
    if (evaluationTimeout) clearTimeout(evaluationTimeout);

    if (!expression.trim()) {
      previewResults = new Map();
      currentError = null;
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

        // Check if all results are errors
        const hasAnySuccess = results.some(r => !r.error);
        if (hasAnySuccess) {
          // Store as last valid results
          lastValidResults = new Map(resultsMap);
          lastValidExpression = expression;
          currentError = null;
        } else {
          // All errors - capture the first error message
          const firstError = results.find(r => r.error)?.error;
          currentError = firstError || 'All rows returned errors';
        }
      } catch (error) {
        console.error('Python evaluation error:', error);
        currentError = error instanceof Error ? error.message : String(error);
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

  function handleReset() {
    expression = lastValidExpression;
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }

  const previewEntries = $derived(
    showAllPreview
      ? Array.from(displayResults.entries())
      : Array.from(displayResults.entries()).slice(0, 10)
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
        <CodeEditor
          bind:value={expression}
          onchange={(newValue) => expression = newValue}
          placeholder="e.g., trace['frames'][0]['filename']"
        />
        <div class="expression-help">
          Python code with access to <code>trace</code> variable (StackTrace object).
          You can write multiple statements. The last expression is returned.
        </div>
      </div>

      <div class="preview-section">
        <div class="preview-header">
          <h3>Preview ({callSite.value_groups.length} rows)</h3>
          {#if showingFallback}
            <button class="reset-button" onclick={handleReset}>Reset to last valid</button>
          {/if}
        </div>
        {#if loadingPyodide}
          <div class="pyodide-loading">
            <div class="loading-spinner"></div>
            <div>Loading Python interpreter (first time only, ~10s)...</div>
          </div>
        {:else if isEvaluating}
          <div class="preview-loading">Evaluating...</div>
        {:else if displayResults.size === 0}
          <div class="preview-empty">Enter an expression to see preview</div>
        {:else}
          <div class="preview-table-container" class:error-state={showingFallback}>
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
          {#if showingFallback && currentError}
            <div class="error-message">
              <strong>Error:</strong> {currentError}
            </div>
          {/if}
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

  .form-input {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.9rem;
    font-family: inherit;
    transition: border-color 0.2s;
  }

  .expression-help code {
    background: #f3f4f6;
    padding: 0.125rem 0.375rem;
    border-radius: 3px;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    font-size: 0.85em;
  }

  .form-input:focus {
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
    height: 400px;
    display: flex;
    flex-direction: column;
  }

  .preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }

  .preview-header h3 {
    margin: 0;
    font-size: 1.1rem;
    color: #333;
  }

  .reset-button {
    padding: 0.5rem 1rem;
    background: #fef3c7;
    color: #92400e;
    border: 1px solid #f59e0b;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 600;
    transition: background-color 0.2s;
  }

  .reset-button:hover {
    background: #fde68a;
  }

  .preview-loading, .preview-empty {
    text-align: center;
    padding: 2rem;
    color: #666;
    font-style: italic;
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .pyodide-loading {
    text-align: center;
    padding: 2rem;
    color: #2563eb;
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
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
    flex: 1;
    transition: border-color 0.2s;
  }

  .preview-table-container.error-state {
    border: 2px solid #dc2626;
    border-radius: 4px;
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

  .error-message {
    margin-top: 0.75rem;
    padding: 0.75rem;
    background: #fee2e2;
    border: 1px solid #dc2626;
    border-radius: 4px;
    color: #991b1b;
    font-size: 0.85rem;
  }

  .error-message strong {
    font-weight: 700;
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
