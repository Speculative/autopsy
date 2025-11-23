<script lang="ts">
  import type { AutopsyData, StackTrace } from "./types";
  import StreamsView from "./StreamsView.svelte";
  import HistoryView from "./HistoryView.svelte";
  import TreeView from "./TreeView.svelte";

  let data: AutopsyData = $state({
    generated_at: "",
    call_sites: [],
    stack_traces: {},
  });
  let activeTab = $state<"streams" | "history">("streams");
  let highlightedLogIndex = $state<number | null>(null);
  let selectedLogIndex = $state<number | null>(null);
  let selectedStackTrace = $state<StackTrace | null>(null);
  let sidebarWidth = $state(500);
  let isResizing = $state(false);

  // Load data from the injection point or dev data
  async function loadData(): Promise<void> {
    // In development mode, try to load dev-data.json if it exists
    if (import.meta.env.DEV) {
      try {
        const response = await fetch("/dev-data.json");
        if (response.ok) {
          const parsed = (await response.json()) as Partial<AutopsyData>;
          data = {
            generated_at: parsed.generated_at ?? "",
            call_sites: parsed.call_sites ?? [],
            stack_traces: parsed.stack_traces ?? {},
          };
          console.log("Loaded development data from dev-data.json");
          return;
        }
      } catch (e) {
        console.log("No dev-data.json found, using empty data");
      }
    }

    // Load from the injected data element (production mode or no dev data)
    const dataElement = document.getElementById("autopsy-data");
    if (dataElement && dataElement.textContent) {
      try {
        const parsed = JSON.parse(
          dataElement.textContent
        ) as Partial<AutopsyData>;
        data = {
          generated_at: parsed.generated_at ?? "",
          call_sites: parsed.call_sites ?? [],
          stack_traces: parsed.stack_traces ?? {},
        };
      } catch (e) {
        console.error("Failed to parse autopsy data:", e);
        data = { generated_at: "", call_sites: [], stack_traces: {} };
      }
    }
  }

  // Load data on mount
  loadData();

  function handleShowInHistory(logIndex: number) {
    highlightedLogIndex = logIndex;
    activeTab = "history";
    // Clear highlight after animation completes (2s)
    setTimeout(() => {
      highlightedLogIndex = null;
    }, 2000);
  }

  function handleShowInStream(logIndex: number) {
    highlightedLogIndex = logIndex;
    activeTab = "streams";
    // Clear highlight after animation completes (2s)
    setTimeout(() => {
      highlightedLogIndex = null;
    }, 2000);
  }

  function handleEntryClick(logIndex: number, stackTraceId?: string) {
    selectedLogIndex = logIndex;
    if (stackTraceId !== undefined && data.stack_traces) {
      const traceId = String(stackTraceId);
      const trace = data.stack_traces[traceId];
      selectedStackTrace = trace || null;
    } else {
      selectedStackTrace = null;
    }
  }

  function closeSidebar() {
    selectedLogIndex = null;
    selectedStackTrace = null;
  }

  function handleResizeStart(e: MouseEvent) {
    isResizing = true;
    e.preventDefault();
  }

  function handleResizeMove(e: MouseEvent) {
    if (!isResizing) return;
    const newWidth = window.innerWidth - e.clientX;
    const minWidth = 300;
    const maxWidth = Math.min(800, window.innerWidth * 0.7);
    sidebarWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
  }

  function handleResizeEnd() {
    isResizing = false;
  }

  // Set up global mouse event listeners for resizing
  $effect(() => {
    if (isResizing) {
      document.addEventListener("mousemove", handleResizeMove);
      document.addEventListener("mouseup", handleResizeEnd);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      return () => {
        document.removeEventListener("mousemove", handleResizeMove);
        document.removeEventListener("mouseup", handleResizeEnd);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      };
    }
  });

  // Clear highlight when switching tabs manually
  $effect(() => {
    if (activeTab === "history") {
      // Only clear highlight when switching to history, not streams
      // (streams might be showing a highlight from handleShowInStream)
    }
  });
</script>

<div class="app-container">
  <main class="main-panel">
    <div class="header">
      <h1>Autopsy Report</h1>
      {#if data.generated_at}
        <div class="timestamp">
          Generated: {new Date(data.generated_at).toLocaleString()}
        </div>
      {/if}
    </div>

    <div class="tabs">
      <button
        class="tab"
        class:active={activeTab === "streams"}
        onclick={() => (activeTab = "streams")}
      >
        Streams
      </button>
      <button
        class="tab"
        class:active={activeTab === "history"}
        onclick={() => (activeTab = "history")}
      >
        History
      </button>
    </div>

    <div class="content">
      {#if activeTab === "streams"}
        <StreamsView
          {data}
          {highlightedLogIndex}
          {selectedLogIndex}
          onShowInHistory={handleShowInHistory}
          onEntryClick={handleEntryClick}
        />
      {:else if activeTab === "history"}
        <HistoryView
          {data}
          {highlightedLogIndex}
          {selectedLogIndex}
          onShowInStream={handleShowInStream}
          onEntryClick={handleEntryClick}
        />
      {/if}
    </div>
  </main>

  {#if selectedStackTrace !== null}
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      class="resize-handle"
      class:resizing={isResizing}
      onmousedown={handleResizeStart}
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize sidebar"
    ></div>
    <aside class="sidebar" style="width: {sidebarWidth}px">
      <div class="sidebar-header">
        <h2>Stack Trace</h2>
        <button class="close-button" onclick={closeSidebar}>×</button>
      </div>
      <div class="sidebar-body">
        <div class="stack-trace">
          {#each selectedStackTrace.frames as frame, index}
            <div class="stack-frame">
              <div class="frame-header">
                <span class="frame-number">#{index + 1}</span>
                <div class="frame-info">
                  <span class="frame-function">{frame.function_name}</span>
                  <span class="frame-location">
                    {frame.filename}:{frame.line_number}
                  </span>
                </div>
              </div>
              <div class="frame-code">
                <code>{frame.code_context || "(no code context)"}</code>
              </div>
              {#if Object.keys(frame.local_variables).length > 0}
                <div class="frame-variables">
                  <div class="variables-header">Local Variables:</div>
                  <div class="variables-list">
                    {#each Object.entries(frame.local_variables) as [name, value]}
                      <TreeView {value} key={name} />
                    {/each}
                  </div>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    </aside>
  {/if}
</div>

<style>
  .app-container {
    display: flex;
    height: 100vh;
    overflow: hidden;
    font-family:
      system-ui,
      -apple-system,
      sans-serif;
  }

  .main-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    min-width: 0;
  }

  .main-panel > .header {
    max-width: 1200px;
    width: 100%;
    margin: 0 auto;
    padding: 2rem 2rem 0 2rem;
  }

  .main-panel > .tabs {
    max-width: 1200px;
    width: 100%;
    margin: 0 auto;
    padding: 0 2rem;
  }

  .main-panel > .content {
    max-width: 1200px;
    width: 100%;
    margin: 0 auto;
    padding: 0 2rem 2rem 2rem;
    flex: 1;
    min-height: 200px;
  }

  .header {
    margin-bottom: 1.5rem;
  }

  h1 {
    margin: 0 0 0.5rem 0;
    color: #333;
  }

  .timestamp {
    color: #666;
    font-size: 0.9rem;
  }

  .tabs {
    display: flex;
    gap: 0.5rem;
    border-bottom: 2px solid #e5e7eb;
    margin-bottom: 1.5rem;
  }

  .tab {
    padding: 0.75rem 1.5rem;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    font-size: 0.95rem;
    font-weight: 500;
    color: #64748b;
    cursor: pointer;
    transition: all 0.2s;
  }

  .tab:hover {
    color: #2563eb;
    background: #f8fafc;
  }

  .tab.active {
    color: #2563eb;
    border-bottom-color: #2563eb;
  }

  .resize-handle {
    width: 4px;
    flex-shrink: 0;
    background: #e5e5e5;
    cursor: col-resize;
    transition: background-color 0.2s;
    position: relative;
  }

  .resize-handle:hover,
  .resize-handle.resizing {
    background: #2563eb;
  }

  .resize-handle::before {
    content: "";
    position: absolute;
    left: -2px;
    right: -2px;
    top: 0;
    bottom: 0;
  }

  .sidebar {
    flex-shrink: 0;
    background: white;
    border-left: 1px solid #e5e5e5;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .sidebar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid #e5e5e5;
    flex-shrink: 0;
  }

  .sidebar-header h2 {
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

  .sidebar-body {
    padding: 1.5rem;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .stack-trace {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .stack-frame {
    border: 1px solid #e5e5e5;
    border-radius: 6px;
    padding: 1rem;
    background: #f9fafb;
  }

  .frame-header {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
    font-size: 0.9rem;
  }

  .frame-number {
    font-weight: 600;
    color: #2563eb;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    background: #eff6ff;
    padding: 2px 6px;
    border-radius: 3px;
    flex-shrink: 0;
  }

  .frame-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    flex: 1;
  }

  .frame-function {
    font-weight: 500;
    color: #475569;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
  }

  .frame-location {
    color: #64748b;
    font-size: 0.85rem;
  }

  .frame-code {
    background: white;
    padding: 0.75rem;
    border-radius: 4px;
    margin-bottom: 0.75rem;
    border: 1px solid #e5e5e5;
  }

  .frame-code code {
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    font-size: 0.85rem;
    color: #333;
  }

  .frame-variables {
    background: white;
    padding: 0.75rem;
    border-radius: 4px;
    border: 1px solid #e5e5e5;
    max-width: 100%;
    min-width: 0;
    overflow-x: auto;
  }

  .variables-header {
    font-weight: 600;
    color: #475569;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
  }

  .variables-list {
    display: flex;
    flex-direction: column;
    max-width: 100%;
    overflow-x: auto;
    min-width: 0;
  }

  @media (max-width: 1200px) {
    .sidebar {
      width: 100% !important;
      max-width: 500px;
    }
    .resize-handle {
      display: none;
    }
  }
</style>
