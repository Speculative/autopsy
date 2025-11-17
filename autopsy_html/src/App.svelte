<script lang="ts">
  import type { AutopsyData } from "./types";
  import StreamsView from "./StreamsView.svelte";
  import HistoryView from "./HistoryView.svelte";

  let data: AutopsyData = $state({ generated_at: "", call_sites: [] });
  let activeTab = $state<"streams" | "history">("streams");
  let highlightedLogIndex = $state<number | null>(null);

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
        };
      } catch (e) {
        console.error("Failed to parse autopsy data:", e);
        data = { generated_at: "", call_sites: [] };
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

  // Clear highlight when switching tabs manually
  $effect(() => {
    if (activeTab === "streams") {
      highlightedLogIndex = null;
    }
  });
</script>

<main>
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
      <StreamsView {data} onShowInHistory={handleShowInHistory} />
    {:else if activeTab === "history"}
      <HistoryView {data} {highlightedLogIndex} />
    {/if}
  </div>
</main>

<style>
  main {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
    font-family:
      system-ui,
      -apple-system,
      sans-serif;
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

  .content {
    min-height: 200px;
  }
</style>
