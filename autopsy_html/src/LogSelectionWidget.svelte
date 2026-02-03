<script lang="ts">
  import type { AutopsyData, ValueGroup, CallSite, LogMark } from "./types";
  import { X, Search } from "lucide-svelte";

  // Props
  let {
    data,
    logMarks = {},
    selectedLogIndex = $bindable<number | null>(null),
    placeholder = "Select a log...",
  }: {
    data: AutopsyData;
    logMarks?: Record<number, LogMark>;
    selectedLogIndex?: number | null;
    placeholder?: string;
  } = $props();

  // Local state
  let isOpen = $state(false);
  let searchTerm = $state("");
  let isDragOver = $state(false);

  // Get all logs with their context
  type LogInfo = {
    logIndex: number;
    functionName: string;
    className?: string;
    callSiteKey: string;
    mark?: LogMark;
  };

  let allLogs = $derived.by(() => {
    const logs: LogInfo[] = [];
    for (const callSite of data.call_sites) {
      const key = `${callSite.filename}:${callSite.line}`;
      for (const valueGroup of callSite.value_groups) {
        logs.push({
          logIndex: valueGroup.log_index,
          functionName: valueGroup.function_name,
          className: valueGroup.class_name,
          callSiteKey: key,
          mark: logMarks[valueGroup.log_index],
        });
      }
    }
    return logs.sort((a, b) => a.logIndex - b.logIndex);
  });

  // Filter logs based on search term - only show marked logs
  let filteredLogs = $derived.by(() => {
    if (!searchTerm && !isOpen) return [];

    const term = searchTerm.toLowerCase();
    // Only include marked logs
    let results = allLogs.filter((log) => log.mark);

    // Filter by search term if provided
    if (term) {
      results = results.filter((log) => {
        const indexMatch = log.logIndex.toString().includes(term);
        const funcMatch = log.functionName.toLowerCase().includes(term);
        const classMatch = log.className?.toLowerCase().includes(term);
        const noteMatch = log.mark?.note.toLowerCase().includes(term);
        return indexMatch || funcMatch || classMatch || noteMatch;
      });
    }

    // Return marked logs only, limited to 50 results
    return results.slice(0, 50);
  });

  // Get selected log info
  let selectedLog = $derived.by(() => {
    if (selectedLogIndex === null) return null;
    return allLogs.find((log) => log.logIndex === selectedLogIndex);
  });

  function handleSelect(logIndex: number) {
    selectedLogIndex = logIndex;
    isOpen = false;
    searchTerm = "";
  }

  function handleClear() {
    selectedLogIndex = null;
    searchTerm = "";
    isOpen = false;
  }

  function handleInputFocus() {
    isOpen = true;
  }

  function handleInputBlur() {
    // Delay to allow click on dropdown items
    setTimeout(() => {
      isOpen = false;
    }, 200);
  }

  function handleInputChange(e: Event) {
    const target = e.target as HTMLInputElement;
    searchTerm = target.value;
    isOpen = true;
  }

  // Drag and drop handlers
  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    isDragOver = true;
  }

  function handleDragLeave(e: DragEvent) {
    e.preventDefault();
    isDragOver = false;
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    isDragOver = false;

    const logIndexStr = e.dataTransfer?.getData("text/log-index");
    if (logIndexStr) {
      const logIndex = parseInt(logIndexStr);
      if (!isNaN(logIndex)) {
        selectedLogIndex = logIndex;
      }
    }
  }

  // Display text for input
  let displayText = $derived.by(() => {
    if (selectedLog) {
      const className = selectedLog.className ? `${selectedLog.className}.` : "";
      return `#${selectedLog.logIndex}: ${className}${selectedLog.functionName}`;
    }
    return "";
  });
</script>

<div class="log-selection-widget">
  <div
    class="input-wrapper"
    class:drag-over={isDragOver}
    ondragover={handleDragOver}
    ondragleave={handleDragLeave}
    ondrop={handleDrop}
  >
    <Search size={16} class="search-icon" />
    <input
      type="text"
      class="log-input"
      value={selectedLog ? displayText : searchTerm}
      placeholder={placeholder}
      onfocus={handleInputFocus}
      onblur={handleInputBlur}
      oninput={handleInputChange}
    />
    {#if selectedLogIndex !== null}
      <button class="clear-button" onclick={handleClear} title="Clear selection">
        <X size={16} />
      </button>
    {/if}
  </div>

  {#if isOpen && filteredLogs.length > 0}
    <div class="dropdown">
      {#each filteredLogs as log (log.logIndex)}
        <button class="dropdown-item" onclick={() => handleSelect(log.logIndex)}>
          <div class="log-item" style={log.mark ? `background-color: ${log.mark.color};` : ""}>
            <div class="log-index">#{log.logIndex}</div>
            <div class="log-details">
              <div class="log-function">
                {log.className ? `${log.className}.` : ""}{log.functionName}
              </div>
              {#if log.mark?.note}
                <div class="log-note">{log.mark.note}</div>
              {/if}
            </div>
          </div>
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .log-selection-widget {
    position: relative;
    width: 100%;
  }

  .input-wrapper {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
    transition: all 0.2s;
  }

  .input-wrapper:focus-within {
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
  }

  .input-wrapper.drag-over {
    border-color: #2563eb;
    background: #eff6ff;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
  }

  .input-wrapper :global(.search-icon) {
    color: #9ca3af;
    flex-shrink: 0;
  }

  .log-input {
    flex: 1;
    border: none;
    outline: none;
    font-size: 0.875rem;
    background: transparent;
    min-width: 0;
  }

  .clear-button {
    background: none;
    border: none;
    color: #9ca3af;
    cursor: pointer;
    padding: 0.25rem;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .clear-button:hover {
    background: #fee2e2;
    color: #dc2626;
  }

  .dropdown {
    position: absolute;
    top: calc(100% + 0.25rem);
    left: 0;
    right: 0;
    max-height: 300px;
    overflow-y: auto;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 1000;
  }

  .dropdown-item {
    width: 100%;
    border: none;
    background: none;
    padding: 0;
    cursor: pointer;
    text-align: left;
  }

  .dropdown-item:hover .log-item {
    background: #f8fafc;
  }

  .log-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem;
    border-bottom: 1px solid #f3f4f6;
    transition: background-color 0.2s;
  }

  .log-index {
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    font-size: 0.75rem;
    color: #6b7280;
    font-weight: 600;
    flex-shrink: 0;
  }

  .log-details {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    min-width: 0;
    flex: 1;
  }

  .log-function {
    font-size: 0.85rem;
    color: #1f2937;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .log-note {
    font-size: 0.75rem;
    color: #6b7280;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
