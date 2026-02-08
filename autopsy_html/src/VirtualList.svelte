<script lang="ts" generics="T">
  import { onMount, tick } from "svelte";

  interface Props {
    items: T[];
    itemHeight: number | ((item: T, index: number) => number);
    overscan?: number;
    useWindowScroll?: boolean;
    containerHeight?: string;
    children: (item: T, index: number) => any;
  }

  let {
    items,
    itemHeight,
    overscan = 5,
    useWindowScroll = false,
    containerHeight = "600px",
    children,
  }: Props = $props();

  function getItemHeight(item: T, index: number): number {
    return typeof itemHeight === "function" ? itemHeight(item, index) : itemHeight;
  }

  let containerElement: HTMLDivElement | undefined = $state();
  let scrollTop = $state(0);
  let containerClientHeight = $state(0);

  // Pre-calculate cumulative heights for all items
  let itemOffsets = $derived.by(() => {
    const offsets: number[] = [0];
    let cumulative = 0;
    for (let i = 0; i < items.length; i++) {
      cumulative += getItemHeight(items[i], i);
      offsets.push(cumulative);
    }
    return offsets;
  });

  let totalHeight = $derived(itemOffsets[itemOffsets.length - 1] || 0);

  // Binary search to find the first visible item
  function findStartIndex(scrollTop: number): number {
    let left = 0;
    let right = items.length - 1;
    while (left < right) {
      const mid = Math.floor((left + right) / 2);
      if (itemOffsets[mid] < scrollTop) {
        left = mid + 1;
      } else {
        right = mid;
      }
    }
    return Math.max(0, left - overscan);
  }

  // Calculate visible range
  let visibleRange = $derived.by(() => {
    const start = findStartIndex(scrollTop);
    // Ensure we have a minimum viewport height for initial render
    const effectiveHeight = Math.max(containerClientHeight, 800);
    const viewportEnd = scrollTop + effectiveHeight;
    let end = start;
    while (end < items.length && itemOffsets[end] < viewportEnd) {
      end++;
    }
    end = Math.min(items.length, end + overscan);
    return { start, end };
  });

  let visibleItems = $derived.by(() => {
    return items.slice(visibleRange.start, visibleRange.end).map((item, i) => ({
      item,
      index: visibleRange.start + i,
      offset: itemOffsets[visibleRange.start + i],
    }));
  });

  function handleScroll(e: Event) {
    if (useWindowScroll) {
      const rect = containerElement?.getBoundingClientRect();
      scrollTop = Math.max(0, -(rect?.top ?? 0));
      containerClientHeight = window.innerHeight;
    } else {
      const target = e.target as HTMLDivElement;
      scrollTop = target.scrollTop;
      containerClientHeight = target.clientHeight;
    }
  }

  onMount(() => {
    if (useWindowScroll) {
      // Set initial viewport height
      containerClientHeight = window.innerHeight;

      window.addEventListener("scroll", handleScroll, { passive: true });
      window.addEventListener("resize", handleScroll);

      // Initial calculation after mount
      requestAnimationFrame(() => {
        handleScroll(new Event("scroll"));
      });

      return () => {
        window.removeEventListener("scroll", handleScroll);
        window.removeEventListener("resize", handleScroll);
      };
    } else if (containerElement) {
      containerClientHeight = containerElement.clientHeight;
      scrollTop = containerElement.scrollTop;
    }
  });

  export function scrollToIndex(index: number, behavior: ScrollBehavior = "smooth") {
    if (index < 0 || index >= itemOffsets.length - 1) return;

    const targetScrollTop = itemOffsets[index] || 0;

    if (useWindowScroll && containerElement) {
      const rect = containerElement.getBoundingClientRect();
      const currentWindowScroll = window.scrollY;
      const containerTop = rect.top + currentWindowScroll;

      window.scrollTo({
        top: containerTop + targetScrollTop - window.innerHeight / 2,
        behavior,
      });
    } else if (containerElement) {
      // For container scroll, center the item in the viewport
      const itemHeight = getItemHeight(items[index], index);
      const centerOffset = (containerClientHeight - itemHeight) / 2;
      containerElement.scrollTo({
        top: Math.max(0, targetScrollTop - centerOffset),
        behavior,
      });
    }
  }
</script>

{#if useWindowScroll}
  <div bind:this={containerElement} class="virtual-list-window" style="height: {totalHeight}px;">
    {#each visibleItems as { item, index, offset }}
      <div class="virtual-item" style="position: absolute; top: {offset}px; left: 0; right: 0;">
        {@render children(item, index)}
      </div>
    {/each}
  </div>
{:else}
  <div
    bind:this={containerElement}
    class="virtual-list-container"
    style="height: {containerHeight}; overflow-y: auto; overflow-x: clip; padding-left: 2rem; box-sizing: border-box;"
    onscroll={handleScroll}
  >
    <div class="virtual-list-inner" style="height: {totalHeight}px; position: relative;">
      {#each visibleItems as { item, index, offset }}
        <div class="virtual-item" style="position: absolute; top: {offset}px; left: 0; right: 0;">
          {@render children(item, index)}
        </div>
      {/each}
    </div>
  </div>
{/if}

<style>
  .virtual-list-window {
    position: relative;
    width: 100%;
  }

  .virtual-list-container {
    width: 100%;
  }

  .virtual-list-inner {
    position: relative;
    width: 100%;
  }

  .virtual-item {
    will-change: transform;
    width: 100%;
  }
</style>
