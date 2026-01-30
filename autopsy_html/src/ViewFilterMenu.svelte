<script lang="ts">
  import { Filter, X } from "lucide-svelte";

  // Props
  let {
    frameFilter = $bindable<string | null>(null),
    frameFilterEnabled = $bindable(true),
  }: {
    frameFilter?: string | null;
    frameFilterEnabled?: boolean;
  } = $props();

  // Local state
  let isOpen = $state(false);

  // Computed values
  let activeFilterCount = $derived(() => {
    let count = 0;
    if (frameFilter !== null && frameFilterEnabled) count++;
    return count;
  });

  function toggleMenu() {
    isOpen = !isOpen;
  }

  function handleFrameFilterToggle() {
    frameFilterEnabled = !frameFilterEnabled;
  }

  function handleFrameFilterRemove() {
    frameFilter = null;
    frameFilterEnabled = true;
  }

  // Close menu when clicking outside
  function handleClickOutside(e: MouseEvent) {
    if (!(e.target as Element)?.closest(".view-filter-menu")) {
      isOpen = false;
    }
  }

  $effect(() => {
    if (isOpen) {
      document.addEventListener("click", handleClickOutside);
      return () => document.removeEventListener("click", handleClickOutside);
    }
  });

  // Parse frame filter for display
  function parseFrameFilter(filter: string): { filename: string; lineNumber: number; functionName: string } {
    const parts = filter.split(":");
    return {
      filename: parts[0] || "",
      lineNumber: parseInt(parts[1]) || 0,
      functionName: parts.slice(2).join(":") || "",
    };
  }
</script>

<div class="view-filter-menu">
  {#if isOpen && frameFilter !== null}
    <div class="filter-menu-panel">
      <div class="menu-header">View Filters</div>

      {#if frameFilter !== null}
        {@const parsed = parseFrameFilter(frameFilter)}
        <div class="filter-section">
          <div class="section-title">Frame Filters</div>
          <div class="filter-item">
            <label class="filter-checkbox-label">
              <input
                type="checkbox"
                checked={frameFilterEnabled}
                onchange={handleFrameFilterToggle}
                class="filter-checkbox"
              />
              <span class="filter-label-text">
                <span class="filter-label-main">{parsed.functionName}</span>
                <span class="filter-label-sub">{parsed.filename}:{parsed.lineNumber}</span>
              </span>
            </label>
            <button
              class="filter-remove-button"
              onclick={handleFrameFilterRemove}
              title="Remove filter"
            >
              <X size={16} />
            </button>
          </div>
        </div>
      {/if}
    </div>
  {/if}

  <button
    class="filter-menu-button"
    class:has-filters={activeFilterCount() > 0}
    onclick={toggleMenu}
    title="View Filters"
  >
    <Filter size={20} />
    {#if activeFilterCount() > 0}
      <span class="filter-badge">{activeFilterCount()}</span>
    {/if}
  </button>
</div>

<style>
  .view-filter-menu {
    position: fixed;
    bottom: 1rem;
    left: 1rem;
    z-index: 1000;
  }

  .filter-menu-button {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: white;
    border: 2px solid #e5e7eb;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    transition: all 0.2s;
    position: relative;
  }

  .filter-menu-button:hover {
    background: #f8fafc;
    border-color: #2563eb;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  .filter-menu-button.has-filters {
    border-color: #2563eb;
    background: #eff6ff;
  }

  .filter-badge {
    position: absolute;
    top: -4px;
    right: -4px;
    background: #2563eb;
    color: white;
    font-size: 0.7rem;
    font-weight: 600;
    min-width: 20px;
    height: 20px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 4px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  }

  .filter-menu-panel {
    position: absolute;
    bottom: calc(100% + 0.5rem);
    left: 0;
    min-width: 320px;
    max-width: 400px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
    padding: 0;
    overflow: hidden;
  }

  .menu-header {
    padding: 0.75rem 1rem;
    font-weight: 600;
    font-size: 0.9rem;
    color: #1f2937;
    border-bottom: 1px solid #e5e7eb;
    background: #f8fafc;
  }

  .filter-section {
    padding: 0.75rem 0;
  }

  .section-title {
    padding: 0 1rem 0.5rem 1rem;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    color: #6b7280;
    letter-spacing: 0.05em;
  }

  .filter-item {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    transition: background-color 0.2s;
  }

  .filter-item:hover {
    background: #f8fafc;
  }

  .filter-checkbox-label {
    flex: 1;
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    cursor: pointer;
    min-width: 0;
  }

  .filter-checkbox {
    margin-top: 0.15rem;
    cursor: pointer;
    flex-shrink: 0;
  }

  .filter-label-text {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    min-width: 0;
  }

  .filter-label-main {
    font-size: 0.85rem;
    color: #1f2937;
    font-weight: 500;
    word-break: break-word;
  }

  .filter-label-sub {
    font-size: 0.75rem;
    color: #6b7280;
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace;
    word-break: break-word;
  }

  .filter-remove-button {
    background: none;
    border: none;
    color: #9ca3af;
    cursor: pointer;
    padding: 0.25rem;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
    flex-shrink: 0;
  }

  .filter-remove-button:hover {
    background: #fee2e2;
    color: #dc2626;
  }
</style>
