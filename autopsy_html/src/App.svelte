<script lang="ts">
  import type { AutopsyData, StackTrace, CallSite, ComputedColumn, LogMark } from "./types";
  import StreamsView from "./StreamsView.svelte";
  import HistoryView from "./HistoryView.svelte";
  import DashboardView from "./DashboardView.svelte";
  import TestsView from "./TestsView.svelte";
  import TreeView from "./TreeView.svelte";
  import ComputedColumnModal from "./ComputedColumnModal.svelte";
  import ViewFilterMenu from "./ViewFilterMenu.svelte";
  import * as pako from "pako";
  import { isVSCodeWebview, openFileInVSCode, sendLogDataUpdate } from "./vscodeApi";
  import { Table, Logs } from "lucide-svelte";
  import {
    saveTestFilter,
    restoreTestFilter,
    saveLogMarks,
    restoreLogMarks,
    saveRangeFilter,
    restoreRangeFilter,
    saveComputedColumns,
    restoreComputedColumns,
    saveColumnOrders,
    restoreColumnOrders,
    saveHiddenColumns,
    restoreHiddenColumns,
  } from "./persistence";

  // Conditional imports for live mode
  let createWebSocketConnection: any;
  let mergeIncrementalUpdate: any;

  // Dynamic import for live mode (only if enabled at build time)
  let liveModeCodeLoaded: Promise<void>;
  if (typeof __LIVE_MODE_ENABLED__ !== 'undefined' && __LIVE_MODE_ENABLED__) {
    liveModeCodeLoaded = import('./websocket').then(module => {
      console.log("Loaded websocket code")
      createWebSocketConnection = module.createWebSocketConnection;
      mergeIncrementalUpdate = module.mergeIncrementalUpdate;
    });
  }

  // Get initial tab from hash or default to history
  function getInitialTab(): "streams" | "history" | "dashboard" | "tests" {
    const hash = window.location.hash.slice(1); // Remove the '#'
    if (hash === "streams" || hash === "history" || hash === "dashboard" || hash === "tests") {
      return hash;
    }
    return "history";
  }

  let data: AutopsyData = $state({
    generated_at: "",
    call_sites: [],
    stack_traces: {},
  });
  let activeTab = $state<"streams" | "history" | "dashboard" | "tests">(getInitialTab());
  let highlightedLogIndex = $state<number | null>(null);
  let selectedLogIndex = $state<number | null>(null);
  let selectedStackTrace = $state<StackTrace | null>(null);
  let selectedStackTraceIds = $state<string[]>([]);
  let selectedLogIndices = $state<(number | null)[]>([]);
  let selectedStackTraceIndex = $state<number>(0);
  let selectedDashboardElementKey = $state<string | null>(null);
  let sidebarWidth = $state(500);
  let isResizing = $state(false);
  let hiddenCallSites = $state<Set<string>>(new Set());
  let showDashboardCalls = $state(false);
  let frameFilter = $state<string | null>(null);
  let frameFilterEnabled = $state(true);
  let testFilter = $state<string | null>(null);
  let testFilterEnabled = $state(true);
  let rangeStartLogIndex = $state<number | null>(null);
  let rangeEndLogIndex = $state<number | null>(null);
  let rangeFilterEnabled = $state(true);
  let menuOpenForFrame = $state<string | null>(null);

  // Effective frame filter (null when disabled)
  let effectiveFrameFilter = $derived(frameFilter !== null && frameFilterEnabled ? frameFilter : null);
  let effectiveTestFilter = $derived(testFilter !== null && testFilterEnabled ? testFilter : null);
  let effectiveRangeFilter = $derived.by(() => {
    if (rangeStartLogIndex !== null && rangeEndLogIndex !== null && rangeFilterEnabled) {
      // Ensure start is before end
      const start = Math.min(rangeStartLogIndex, rangeEndLogIndex);
      const end = Math.max(rangeStartLogIndex, rangeEndLogIndex);
      return { start, end };
    }
    return null;
  });

  // Frame context highlighting state
  let hoveredFrameKey = $state<string | null>(null);
  let selectedFrameKeys = $state<Set<string>>(new Set()); // Support multiple selections for future
  let expandedCodeFrames = $state<Set<string>>(new Set()); // Track which frames have expanded code context

  // Column order state: maps callSiteKey -> array of column names in order
  let columnOrders = $state<Record<string, string[]>>({});

  // View state that persists across tab changes
  let hideSkippedLogs = $state(false);
  let collapsedCallSites = $state<Record<string, boolean>>({});

  // Sort state for Streams view: maps callSiteKey -> array of {columnName, direction}
  type SortDirection = 'asc' | 'desc';
  type ColumnSort = { columnName: string; direction: SortDirection };
  let columnSorts = $state<Record<string, ColumnSort[]>>({});

  // Hidden columns state: maps callSiteKey -> Set of hidden column names
  let hiddenColumns = $state<Record<string, Set<string>>>({});

  // Column filters state: maps callSiteKey -> { columnName -> filter }
  let columnFilters = $state<Record<string, import('./types').ColumnFilters>>({});

  // Computed columns state: maps callSiteKey -> array of computed columns
  let computedColumns = $state<Record<string, ComputedColumn[]>>({});
  let computedColumnModalOpen = $state<{
    callSite: CallSite;
    callSiteKey: string;
    existingColumn?: ComputedColumn;
  } | null>(null);

  // Mark state: maps logIndex -> {color, note}
  let logMarks = $state<Record<number, LogMark>>({});

  // Live mode state
  let liveMode = $state(false);
  let wsConnection = $state<WebSocket | null>(null);
  let connectionStatus = $state<'connected' | 'disconnected' | 'connecting'>('disconnected');
  let lastUpdateTime = $state<string>("");

  // Track if we've restored persisted state
  let hasRestoredState = $state(false);

  // Load data from the injection point or dev data
  async function loadData(): Promise<void> {
    // Check for live mode (only if this is a live build)
    if (typeof __LIVE_MODE_ENABLED__ !== 'undefined' && __LIVE_MODE_ENABLED__) {
      console.log("Loading live mode data...")
      const params = new URLSearchParams(window.location.search);
      const liveModeParam = params.get('live');
      const wsUrl = params.get('ws') || "ws://localhost:8765/ws";

      await liveModeCodeLoaded;

      // In VS Code mode, auto-enable live mode without requiring URL param
      const shouldEnableLiveMode = (typeof __VSCODE_MODE__ !== 'undefined' && __VSCODE_MODE__) || liveModeParam === 'true';

      if (shouldEnableLiveMode && wsUrl && createWebSocketConnection) {
        liveMode = true;
        connectionStatus = 'connecting';
        console.log("Trying to initialize live mode ws")

        wsConnection = createWebSocketConnection({
          url: wsUrl,
          onSnapshot: (snapshotData: AutopsyData) => {
            data = snapshotData;
            connectionStatus = 'connected';
            lastUpdateTime = new Date().toLocaleString();
          },
          onUpdate: (update: any) => {
            if (mergeIncrementalUpdate) {
              data = mergeIncrementalUpdate(data, update);
              lastUpdateTime = new Date().toLocaleString();
            }
          },
          onError: (error: Event) => {
            console.error('WebSocket error:', error);
            connectionStatus = 'disconnected';
          },
          onClose: () => {
            console.log('WebSocket closed');
            connectionStatus = 'disconnected';
            // Attempt reconnect after 2s
            setTimeout(() => loadData(), 2000);
          }
        });

        return;
      }
    }

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
            dashboard: parsed.dashboard,
            tests: parsed.tests,
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
        let jsonString: string;

        // Check if data is compressed
        const isCompressed = dataElement.getAttribute("data-compressed") === "gzip";

        if (isCompressed) {
          // Decompress base64-encoded gzipped data
          const base64Data = dataElement.textContent.trim();
          const binaryString = atob(base64Data);
          const bytes = new Uint8Array(binaryString.length);
          for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
          }
          const decompressed = pako.inflate(bytes, { to: "string" });
          jsonString = decompressed;
        } else {
          // Use uncompressed data directly
          jsonString = dataElement.textContent;
        }

        const parsed = JSON.parse(jsonString) as Partial<AutopsyData>;
        data = {
          generated_at: parsed.generated_at ?? "",
          call_sites: parsed.call_sites ?? [],
          stack_traces: parsed.stack_traces ?? {},
          dashboard: parsed.dashboard,
          tests: parsed.tests,
        };
      } catch (e) {
        console.error("Failed to parse autopsy data:", e);
        data = { generated_at: "", call_sites: [], stack_traces: {} };
      }
    }
  }

  // Load data on mount
  loadData();

  // Restore persisted state after data loads (only once)
  $effect(() => {
    // Only restore if we haven't restored yet
    if (hasRestoredState) return;

    // Wait for data to load
    if (data.call_sites.length === 0) return;

    // Restore test filter
    const { testFilter: restoredTestFilter, testFilterEnabled: restoredTestFilterEnabled } = restoreTestFilter(data);
    if (restoredTestFilter !== null) {
      testFilter = restoredTestFilter;
      testFilterEnabled = restoredTestFilterEnabled;
    }

    // Restore log marks
    const restoredMarks = restoreLogMarks(data);
    if (Object.keys(restoredMarks).length > 0) {
      logMarks = restoredMarks;
    }

    // Restore range filter (depends on marks being restored)
    const { rangeStartLogIndex: restoredStart, rangeEndLogIndex: restoredEnd } = restoreRangeFilter(data);
    if (restoredStart !== null && restoredEnd !== null) {
      rangeStartLogIndex = restoredStart;
      rangeEndLogIndex = restoredEnd;
    }

    // Restore computed columns
    const restoredColumns = restoreComputedColumns(data);
    if (Object.keys(restoredColumns).length > 0) {
      // Use spread operator to ensure proper reactivity in Svelte 5
      computedColumns = { ...restoredColumns };
    }

    // Restore column orders
    const restoredOrders = restoreColumnOrders(data);
    if (Object.keys(restoredOrders).length > 0) {
      columnOrders = { ...restoredOrders };
    }

    // Restore hidden columns
    const restoredHidden = restoreHiddenColumns(data);
    if (Object.keys(restoredHidden).length > 0) {
      hiddenColumns = { ...restoredHidden };
    }

    // Mark that we've restored state (MUST be last so save effects don't run during restoration)
    hasRestoredState = true;
  });

  // Sync hash with active tab
  $effect(() => {
    const currentHash = window.location.hash.slice(1);
    if (currentHash !== activeTab) {
      window.location.hash = activeTab;
    }
  });

  // Listen for hash changes (browser back/forward)
  $effect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.slice(1);
      if (hash === "streams" || hash === "history" || hash === "dashboard" || hash === "tests") {
        activeTab = hash;
      }
    };

    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  });

  // Send data updates to VS Code extension when data changes
  $effect(() => {
    if (isVSCodeWebview() && data.call_sites.length > 0) {
      console.log("Sending log data update to VS Code extension");
      sendLogDataUpdate(data);
    }
  });

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
    selectedDashboardElementKey = null;
    if (stackTraceId !== undefined && data.stack_traces) {
      const traceId = String(stackTraceId);
      const trace = data.stack_traces[traceId];
      selectedStackTrace = trace || null;
      selectedStackTraceIds = stackTraceId ? [stackTraceId] : [];
      selectedStackTraceIndex = 0;
    } else {
      selectedStackTrace = null;
      selectedStackTraceIds = [];
      selectedStackTraceIndex = 0;
    }
  }

  // Find log index for a stack trace ID
  function findLogIndexForStackTrace(stackTraceId: string): number | null {
    for (const callSite of data.call_sites) {
      for (const valueGroup of callSite.value_groups) {
        if (valueGroup.stack_trace_id === stackTraceId) {
          return valueGroup.log_index;
        }
      }
    }
    return null;
  }

  function handleDashboardEntryClick(
    stackTraceIds: string[],
    elementKey: string
  ) {
    selectedDashboardElementKey = elementKey;
    selectedStackTraceIds = stackTraceIds;
    selectedStackTraceIndex = 0;
    
    // Extract log_indices from dashboard data based on elementKey
    // elementKey format: "count-{entryIndex}-{valueKey}" or "histogram-{entryIndex}-{binIndex}" etc.
    const logIndices: (number | null)[] = [];
    
    if (elementKey.startsWith("count-")) {
      const parts = elementKey.split("-");
      const entryIndex = parseInt(parts[1]);
      const valueKey = parts.slice(2).join("-");
      
      if (data.dashboard?.counts[entryIndex]) {
        const entry = data.dashboard.counts[entryIndex];
        const valueData = entry.value_counts[valueKey];
        if (valueData?.log_indices) {
          // Match stack_trace_ids to log_indices in order
          for (const stackTraceId of stackTraceIds) {
            const idx = valueData.stack_trace_ids.indexOf(stackTraceId);
            logIndices.push(idx >= 0 ? valueData.log_indices[idx] : null);
          }
        }
      }
    } else if (elementKey.startsWith("histogram-")) {
      const parts = elementKey.split("-");
      const entryIndex = parseInt(parts[1]);
      const binIndex = parseInt(parts[2]);
      
      if (data.dashboard?.histograms[entryIndex]) {
        const entry = data.dashboard.histograms[entryIndex];
        // For histograms, match stack_trace_ids to values that have matching stack_trace_id
        for (const stackTraceId of stackTraceIds) {
          const value = entry.values.find(v => v.stack_trace_id === stackTraceId);
          logIndices.push(value?.log_index ?? null);
        }
      }
    } else if (elementKey.startsWith("timeline-")) {
      const entryIndex = parseInt(elementKey.split("-")[1]);
      if (data.dashboard?.timeline[entryIndex]) {
        const entry = data.dashboard.timeline[entryIndex];
        logIndices.push(entry.log_index ?? null);
      }
    } else if (elementKey.startsWith("happened-")) {
      const entryIndex = parseInt(elementKey.split("-")[1]);
      if (data.dashboard?.happened[entryIndex]) {
        const entry = data.dashboard.happened[entryIndex];
        // Match stack_trace_ids to log_indices in order
        for (const stackTraceId of stackTraceIds) {
          const idx = entry.stack_trace_ids.indexOf(stackTraceId);
          logIndices.push(idx >= 0 ? entry.log_indices[idx] : null);
        }
      }
    }
    
    // Fallback: if we couldn't extract log_indices, search for them
    if (logIndices.length === 0 || logIndices.every(idx => idx === null)) {
      logIndices.push(...stackTraceIds.map(id => findLogIndexForStackTrace(id)));
    }
    
    selectedLogIndices = logIndices;
    
    // Find log index from the first stack trace ID
    if (stackTraceIds.length > 0) {
      const logIndex = logIndices[0] ?? findLogIndexForStackTrace(stackTraceIds[0]);
      selectedLogIndex = logIndex;
      
      if (data.stack_traces) {
        const trace = data.stack_traces[stackTraceIds[0]];
        selectedStackTrace = trace || null;
      } else {
        selectedStackTrace = null;
      }
    } else {
      selectedLogIndex = null;
      selectedStackTrace = null;
    }
  }

  function handleStackTraceIndexChange(index: number) {
    selectedStackTraceIndex = index;
    if (selectedStackTraceIds[index]) {
      // Use stored log index if available, otherwise search for it
      const logIndex = selectedLogIndices[index] ?? findLogIndexForStackTrace(selectedStackTraceIds[index]);
      selectedLogIndex = logIndex;
      
      if (data.stack_traces) {
        const trace = data.stack_traces[selectedStackTraceIds[index]];
        selectedStackTrace = trace || null;
      } else {
        selectedStackTrace = null;
      }
    }
  }

  function closeSidebar() {
    selectedLogIndex = null;
    selectedStackTrace = null;
    selectedStackTraceIds = [];
    selectedLogIndices = [];
    selectedStackTraceIndex = 0;
    selectedDashboardElementKey = null;
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

  // Close frame menu when clicking outside
  $effect(() => {
    if (menuOpenForFrame !== null) {
      const handler = (e: MouseEvent) => {
        if (!(e.target as Element)?.closest(".frame-menu-container")) {
          closeFrameMenu();
        }
      };
      document.addEventListener("click", handler);
      return () => document.removeEventListener("click", handler);
    }
  });

  function handleHideCallSite(callSiteKey: string) {
    hiddenCallSites.add(callSiteKey);
    hiddenCallSites = new Set(hiddenCallSites);
  }

  function handleShowCallSite(callSiteKey: string) {
    hiddenCallSites.delete(callSiteKey);
    hiddenCallSites = new Set(hiddenCallSites);
  }

  function handleNavigateToLog(logIndex: number) {
    highlightedLogIndex = logIndex;
    // Switch to history view to show the log
    activeTab = "history";
    // Clear highlight after animation completes (2s)
    setTimeout(() => {
      highlightedLogIndex = null;
    }, 2000);
  }

  function handleToggleShowDashboard(show: boolean) {
    showDashboardCalls = show;
  }

  function createFrameKey(filename: string, lineNumber: number, functionName: string): string {
    return `${filename}:${lineNumber}:${functionName}`;
  }

  function handleShowFrameOnly(filename: string, lineNumber: number, functionName: string) {
    frameFilter = createFrameKey(filename, lineNumber, functionName);
    frameFilterEnabled = true;
    menuOpenForFrame = null;
  }

  function handleClearFrameFilter() {
    frameFilter = null;
    frameFilterEnabled = true;
  }

  function handleSetTestFilter(testNodeid: string) {
    testFilter = testNodeid;
    testFilterEnabled = true;
  }

  function toggleFrameMenu(frameKey: string, e: MouseEvent | KeyboardEvent) {
    e.stopPropagation();
    menuOpenForFrame = menuOpenForFrame === frameKey ? null : frameKey;
  }

  function closeFrameMenu() {
    menuOpenForFrame = null;
  }

  function stackTraceContainsFrame(stackTraceId: string, frameKey: string): boolean {
    const trace = data.stack_traces[stackTraceId];
    if (!trace) return false;
    return trace.frames.some(frame =>
      createFrameKey(frame.filename, frame.line_number, frame.function_name) === frameKey
    );
  }

  function handleFrameHover(frameKey: string | null) {
    hoveredFrameKey = frameKey;
  }

  function handleFrameClick(frameKey: string) {
    // Toggle selection for the frame
    if (selectedFrameKeys.has(frameKey)) {
      selectedFrameKeys.delete(frameKey);
    } else {
      // For now, only allow one selected frame (but using Set for future multi-select)
      selectedFrameKeys.clear();
      selectedFrameKeys.add(frameKey);
    }
    selectedFrameKeys = new Set(selectedFrameKeys); // Trigger reactivity
  }

  function toggleCodeExpansion(frameKey: string) {
    if (expandedCodeFrames.has(frameKey)) {
      expandedCodeFrames.delete(frameKey);
    } else {
      expandedCodeFrames.add(frameKey);
    }
    expandedCodeFrames = new Set(expandedCodeFrames); // Trigger reactivity
  }

  function handleColumnOrderChange(callSiteKey: string, newOrder: string[]) {
    columnOrders[callSiteKey] = newOrder;
    columnOrders = { ...columnOrders };
  }

  function handleOpenComputedColumnModal(callSite: CallSite, existingColumn?: ComputedColumn) {
    const callSiteKey = getCallSiteKey(callSite);
    computedColumnModalOpen = { callSite, callSiteKey, existingColumn };
  }

  function handleSaveComputedColumn(column: ComputedColumn) {
    const { callSiteKey } = column;
    const existing = computedColumns[callSiteKey] || [];
    const index = existing.findIndex(c => c.id === column.id);

    if (index >= 0) {
      existing[index] = column;
    } else {
      existing.push(column);
    }

    computedColumns[callSiteKey] = existing;
    computedColumns = { ...computedColumns };
    computedColumnModalOpen = null;
  }

  function handleDeleteComputedColumn() {
    if (!computedColumnModalOpen?.existingColumn) return;
    const { callSiteKey, existingColumn } = computedColumnModalOpen;

    computedColumns[callSiteKey] = (computedColumns[callSiteKey] || [])
      .filter(c => c.id !== existingColumn.id);
    computedColumns = { ...computedColumns };

    const order = columnOrders[callSiteKey];
    if (order) {
      columnOrders[callSiteKey] = order.filter(name => name !== `computed:${existingColumn.id}`);
      columnOrders = { ...columnOrders };
    }

    computedColumnModalOpen = null;
  }

  function handleMarkLog(logIndex: number, color: string, note: string) {
    if (color || note) {
      logMarks[logIndex] = { color, note };
      logMarks = { ...logMarks };
    } else {
      delete logMarks[logIndex];
      logMarks = { ...logMarks };
    }
  }

  function getCallSiteKey(callSite: CallSite): string {
    return `${callSite.filename}:${callSite.line}`;
  }

  // Persist state changes to localStorage (only after initial restoration)
  $effect(() => {
    // Don't save until we've restored state, to avoid overwriting on initial load
    if (!hasRestoredState) return;
    // Save test filter when it changes
    saveTestFilter(testFilter, testFilterEnabled);
  });

  $effect(() => {
    // Don't save until we've restored state
    if (!hasRestoredState) return;
    // Save log marks when they change (only if we have data)
    if (data.call_sites.length > 0) {
      saveLogMarks(data, logMarks);
    }
  });

  $effect(() => {
    // Don't save until we've restored state
    if (!hasRestoredState) return;
    // Save range filter when it changes (only if we have data)
    if (data.call_sites.length > 0) {
      saveRangeFilter(data, rangeStartLogIndex, rangeEndLogIndex);
    }
  });

  $effect(() => {
    // Don't save until we've restored state
    if (!hasRestoredState) return;
    // Save computed columns when they change
    saveComputedColumns(computedColumns);
  });

  $effect(() => {
    // Don't save until we've restored state
    if (!hasRestoredState) return;
    // Save column orders when they change
    saveColumnOrders(columnOrders);
  });

  $effect(() => {
    // Don't save until we've restored state
    if (!hasRestoredState) return;
    // Save hidden columns when they change
    saveHiddenColumns(hiddenColumns);
  });
</script>

<div class="app-container">
  <main class="main-panel">
    <div class="header">
      <div class="header-top">
        {#if typeof __LIVE_MODE_ENABLED__ !== 'undefined' && __LIVE_MODE_ENABLED__ && liveMode}
          <div class="timestamp">
            <span class="live-indicator {connectionStatus}">●</span>
            <span>Live - Last updated: {lastUpdateTime || 'Connecting...'}</span>
          </div>
        {:else if data.generated_at}
          <div class="timestamp">
            Generated: {new Date(data.generated_at).toLocaleString()}
          </div>
        {/if}
      </div>
    </div>

    <div class="tabs">
      <button
        class="tab"
        class:active={activeTab === "history"}
        onclick={() => (activeTab = "history")}
      >
        History
      </button>
      <button
        class="tab"
        class:active={activeTab === "streams"}
        onclick={() => (activeTab = "streams")}
      >
        Streams
      </button>
      <button
        class="tab"
        class:active={activeTab === "dashboard"}
        onclick={() => (activeTab = "dashboard")}
      >
        Dashboard
      </button>
      <button
        class="tab"
        class:active={activeTab === "tests"}
        onclick={() => (activeTab = "tests")}
      >
        Tests
      </button>
    </div>

    <div class="content">
      {#if activeTab === "history"}
        <HistoryView
          {data}
          {highlightedLogIndex}
          {selectedLogIndex}
          hiddenCallSites={hiddenCallSites}
          {showDashboardCalls}
          {activeTab}
          frameFilter={effectiveFrameFilter}
          testFilter={effectiveTestFilter}
          rangeFilter={effectiveRangeFilter}
          {hoveredFrameKey}
          {selectedFrameKeys}
          {columnOrders}
          {computedColumns}
          {logMarks}
          bind:hideSkippedLogs
          onShowInStream={handleShowInStream}
          onEntryClick={handleEntryClick}
          onHideCallSite={handleHideCallSite}
          onToggleShowDashboard={handleToggleShowDashboard}
          onMarkLog={handleMarkLog}
        />
      {:else if activeTab === "streams"}
        <StreamsView
          {data}
          {highlightedLogIndex}
          {selectedLogIndex}
          hiddenCallSites={hiddenCallSites}
          frameFilter={effectiveFrameFilter}
          testFilter={effectiveTestFilter}
          rangeFilter={effectiveRangeFilter}
          {hoveredFrameKey}
          {selectedFrameKeys}
          {columnOrders}
          {computedColumns}
          {logMarks}
          bind:collapsedCallSites
          bind:columnSorts
          bind:hiddenColumns
          bind:columnFilters
          onShowInHistory={handleShowInHistory}
          onEntryClick={handleEntryClick}
          onHideCallSite={handleHideCallSite}
          onShowCallSite={handleShowCallSite}
          onColumnOrderChange={handleColumnOrderChange}
          onOpenComputedColumnModal={handleOpenComputedColumnModal}
          onSaveComputedColumn={handleSaveComputedColumn}
        />
      {:else if activeTab === "dashboard"}
        <DashboardView
          {data}
          {selectedLogIndex}
          selectedElementKey={selectedDashboardElementKey}
          onEntryClick={handleDashboardEntryClick}
        />
      {:else if activeTab === "tests"}
        <TestsView
          {data}
          testFilter={effectiveTestFilter}
          onShowInHistory={handleShowInHistory}
          onSetTestFilter={handleSetTestFilter}
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
        <div class="sidebar-actions">
          <button
            class="nav-button"
            onclick={() =>
              selectedLogIndex !== null && handleShowInStream(selectedLogIndex)}
            disabled={selectedLogIndex === null}
            title="Jump to Stream"
          >
            <Table size={18} />
          </button>
          <button
            class="nav-button"
            onclick={() =>
              selectedLogIndex !== null &&
              handleShowInHistory(selectedLogIndex)}
            disabled={selectedLogIndex === null}
            title="Jump to History"
          >
            <Logs size={18} />
          </button>
          <button class="close-button" onclick={closeSidebar}>×</button>
        </div>
      </div>
      {#if selectedStackTraceIds.length > 1}
        {@const sortedEntries = selectedStackTraceIds.map((id, i) => ({ id, logIndex: selectedLogIndices[i] ?? null, originalIndex: i })).sort((a, b) => {
          if (a.logIndex === null && b.logIndex === null) return 0;
          if (a.logIndex === null) return 1;
          if (b.logIndex === null) return -1;
          return a.logIndex - b.logIndex;
        })}
        {@const sortedIndex = sortedEntries.findIndex(entry => entry.originalIndex === selectedStackTraceIndex)}
        <div class="stack-trace-selector">
          <span class="selector-label"
            >{selectedStackTraceIds.length} matching call stacks</span
          >
          <select
            class="stack-trace-dropdown"
            value={sortedIndex >= 0 ? sortedIndex : 0}
            onchange={(e) => {
              const newSortedIndex = parseInt((e.target as HTMLSelectElement).value);
              const originalIndex = sortedEntries[newSortedIndex]?.originalIndex ?? 0;
              handleStackTraceIndexChange(originalIndex);
            }}
          >
            {#each sortedEntries as entry, i}
              <option value={i}>
                {#if entry.logIndex !== null}
                  #{entry.logIndex}
                {:else}
                  Invocation #{entry.originalIndex + 1}
                {/if}
              </option>
            {/each}
          </select>
        </div>
      {/if}
      <div class="sidebar-body">
        <div class="stack-trace">
          {#each selectedStackTrace.frames as frame, index}
            {@const frameKey = createFrameKey(frame.filename, frame.line_number, frame.function_name)}
            <div class="stack-frame">
              <div
                class="frame-header"
                class:frame-selected={selectedFrameKeys.has(frameKey)}
              >
                <span
                  class="frame-number"
                  class:clickable={true}
                  onclick={() => handleFrameClick(frameKey)}
                  onmouseenter={() => handleFrameHover(frameKey)}
                  onmouseleave={() => handleFrameHover(null)}
                  role="button"
                  tabindex="0"
                  onkeydown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      handleFrameClick(frameKey);
                    }
                  }}
                  title="Click to highlight all logs with this frame"
                >#{index + 1}</span>
                <div class="frame-info">
                  <span class="frame-function">{frame.function_name}</span>
                  {#if isVSCodeWebview()}
                    <button
                      class="frame-location clickable"
                      onclick={(e) => {
                        e.stopPropagation();
                        openFileInVSCode(frame.filename, frame.line_number);
                      }}
                      title="Open in editor: {frame.filename}:{frame.line_number}"
                    >
                      {frame.filename}:{frame.line_number}
                    </button>
                  {:else}
                    <span class="frame-location">
                      {frame.filename}:{frame.line_number}
                    </span>
                  {/if}
                </div>
                <div class="frame-menu-container">
                  <button
                    class="frame-menu-button"
                    onclick={(e) => toggleFrameMenu(frameKey, e)}
                    onkeydown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        toggleFrameMenu(frameKey, e);
                      }
                    }}
                    title="Menu"
                  >
                    ⋯
                  </button>
                  {#if menuOpenForFrame === frameKey}
                    <div class="frame-menu-dropdown" onclick={(e) => e.stopPropagation()} role="menu">
                      <button
                        class="frame-menu-item"
                        role="menuitem"
                        onclick={(e) => {
                          e.stopPropagation();
                          handleShowFrameOnly(frame.filename, frame.line_number, frame.function_name);
                        }}
                      >
                        Show this frame only
                      </button>
                    </div>
                  {/if}
                </div>
              </div>
              <div
                class="frame-code"
                class:expanded={expandedCodeFrames.has(frameKey)}
                onclick={() => toggleCodeExpansion(frameKey)}
                role="button"
                tabindex="0"
                onkeydown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    toggleCodeExpansion(frameKey);
                  }
                }}
                title={expandedCodeFrames.has(frameKey) ? "Click to collapse" : "Click to expand"}
              >
                <code>{frame.code_context || "(no code context)"}</code>
              </div>
              {#if Object.keys(frame.local_variables).length > 0}
                <div class="frame-variables">
                  <div class="variables-header">Local Variables:</div>
                  <div class="variables-list">
                    {#each Object.entries(frame.local_variables) as [name, value]}
                      <TreeView
                        {value}
                        key={name}
                        enableDrag={true}
                        frameIndex={index}
                        sourceLogIndex={selectedLogIndex ?? undefined}
                        frameFunctionName={frame.function_name}
                        frameFilename={frame.filename}
                        frameLineNumber={frame.line_number}
                      />
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

  {#if computedColumnModalOpen}
    <ComputedColumnModal
      {data}
      callSite={computedColumnModalOpen.callSite}
      callSiteKey={computedColumnModalOpen.callSiteKey}
      existingColumn={computedColumnModalOpen.existingColumn}
      onSave={handleSaveComputedColumn}
      onDelete={handleDeleteComputedColumn}
      onClose={() => computedColumnModalOpen = null}
    />
  {/if}

  <ViewFilterMenu
    {data}
    {logMarks}
    bind:frameFilter
    bind:frameFilterEnabled
    bind:testFilter
    bind:testFilterEnabled
    bind:rangeStartLogIndex
    bind:rangeEndLogIndex
    bind:rangeFilterEnabled
  />
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

  .live-indicator {
    font-size: 14px;
    line-height: 1;
    margin-right: 4px;
  }

  .live-indicator.connected {
    color: #4ade80;
  }

  .live-indicator.disconnected {
    color: #f87171;
  }

  .live-indicator.connecting {
    color: #fbbf24;
    animation: pulse 1s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  .main-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    min-width: 0;
  }

  .main-panel > .header {
    width: 100%;
    padding: 0.5rem 2rem 0 2rem;
  }

  .main-panel > .tabs {
    width: 100%;
    padding: 0 2rem;
  }

  .main-panel > .content {
    width: 100%;
    padding: 0 0 2rem 0;
    flex: 1;
    min-height: 200px;
  }

  /* Only limit width for Dashboard view */
  .main-panel > .content:has(> :nth-child(3)) {
    max-width: 1200px;
    margin: 0 auto;
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
    z-index: 200;
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
    z-index: 200;
  }

  .sidebar-header {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    padding: 0.5rem;
    border-bottom: 1px solid #e5e5e5;
    flex-shrink: 0;
  }

  .sidebar-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .nav-button {
    background: none;
    border: none;
    font-size: 1.5rem;
    color: #666;
    cursor: pointer;
    padding: 0.25rem 0.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition:
      background-color 0.2s,
      color 0.2s;
    min-width: 2rem;
    height: 2rem;
  }

  .nav-button:hover:not(:disabled) {
    background-color: #f0f0f0;
    color: #2563eb;
  }

  .nav-button:disabled {
    opacity: 0.3;
    cursor: not-allowed;
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

  .stack-trace-selector {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.5rem;
    background: #f8fafc;
    border-bottom: 1px solid #e5e5e5;
    flex-shrink: 0;
  }

  .selector-label {
    font-size: 0.85rem;
    color: #64748b;
    font-weight: 500;
  }

  .stack-trace-dropdown {
    padding: 0.4rem 0.75rem;
    font-size: 0.85rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    background: white;
    color: #333;
    cursor: pointer;
    min-width: 140px;
  }

  .stack-trace-dropdown:hover {
    border-color: #2563eb;
  }

  .stack-trace-dropdown:focus {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2);
  }

  .sidebar-body {
    padding: 0.5rem;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .stack-trace {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .stack-frame {
    border: 1px solid #e5e5e5;
    border-radius: 6px;
    padding: 0.5rem;
    background: #f9fafb;
    width: 100%;
  }

  .frame-header {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
    position: relative;
    border-left: 3px solid transparent;
  }

  .frame-number {
    font-weight: 600;
    color: #2563eb;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    background: #eff6ff;
    padding: 2px 6px;
    border-radius: 3px;
    flex-shrink: 0;
    transition: background-color 0.2s, color 0.2s;
  }

  .frame-number.clickable {
    cursor: pointer;
  }

  .frame-number.clickable:hover {
    background: #dbeafe;
    color: #1e40af;
  }

  .frame-header.frame-selected {
    border-left: 3px solid #f59e0b;
    padding-left: 0.5rem;
    margin-left: -0.5rem;
  }

  .frame-header.frame-selected .frame-number {
    background: #fef3c7;
    color: #d97706;
  }

  .frame-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    flex: 1;
  }

  .frame-menu-container {
    margin-left: auto;
    position: relative;
  }

  .frame-menu-button {
    background: none;
    border: none;
    font-size: 1.2rem;
    color: #666;
    cursor: pointer;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    transition: background-color 0.2s;
    line-height: 1;
  }

  .frame-menu-button:hover {
    background-color: #f0f0f0;
  }

  .frame-menu-dropdown {
    position: absolute;
    right: 0;
    top: 100%;
    margin-top: 0.25rem;
    background: white;
    border: 1px solid #e5e5e5;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    z-index: 10;
    min-width: 180px;
  }

  .frame-menu-item {
    display: block;
    width: 100%;
    padding: 0.5rem 0.75rem;
    background: none;
    border: none;
    text-align: left;
    cursor: pointer;
    font-size: 0.85rem;
    color: #333;
    transition: background-color 0.2s;
  }

  .frame-menu-item:hover {
    background-color: #f8fafc;
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

  .frame-location.clickable {
    background: none;
    border: none;
    padding: 0;
    font: inherit;
    cursor: pointer;
    text-align: left;
  }

  .frame-location.clickable:hover {
    color: #2563eb;
    text-decoration: underline;
  }

  .frame-code {
    background: white;
    padding: 0.5rem;
    border-radius: 4px;
    margin-bottom: 0.5rem;
    border: 1px solid #e5e5e5;
    cursor: pointer;
    transition: background-color 0.2s;
    overflow: hidden;
  }

  .frame-code:hover {
    background-color: #f8fafc;
  }

  .frame-code code {
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    font-size: 0.85rem;
    color: #333;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    display: block;
  }

  .frame-code.expanded code {
    white-space: pre-wrap;
    overflow: visible;
    text-overflow: clip;
  }

  .frame-variables {
    background: white;
    padding: 0.5rem;
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
