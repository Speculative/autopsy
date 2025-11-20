<script lang="ts">
  import TreeView from "./TreeView.svelte";

  interface Props {
    value: unknown;
    key?: string | number;
    depth?: number;
  }

  export let value: unknown;
  export let key: string | number | undefined = undefined;
  export let depth: number = 0;

  let expanded = false; // Collapsed by default

  function isObject(value: unknown): value is Record<string, unknown> {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function isArray(value: unknown): value is unknown[] {
    return Array.isArray(value);
  }

  function getType(value: unknown): string {
    if (value === null) return "null";
    if (value === undefined) return "undefined";
    if (isArray(value)) return "array";
    if (isObject(value)) return "object";
    return typeof value;
  }

  function getValuePreview(value: unknown): string {
    const type = getType(value);
    if (type === "string") {
      const str = value as string;
      // Truncate long strings
      if (str.length > 50) {
        return `"${str.substring(0, 47)}..."`;
      }
      return `"${str}"`;
    }
    if (type === "null" || type === "undefined") return type;
    if (type === "number" || type === "boolean") return String(value);
    if (isArray(value)) {
      return `Array(${value.length})`;
    }
    if (isObject(value)) {
      const keys = Object.keys(value);
      return keys.length === 0
        ? "{}"
        : `{${keys.length} ${keys.length === 1 ? "key" : "keys"}}`;
    }
    return String(value);
  }

  function toggle(event: MouseEvent | KeyboardEvent) {
    event.stopPropagation();
    if (isObject(value) || isArray(value)) {
      expanded = !expanded;
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggle(event);
    }
  }

  function getTypeColor(type: string): string {
    switch (type) {
      case "string":
        return "#0a0";
      case "number":
        return "#00a";
      case "boolean":
        return "#a0a";
      case "null":
      case "undefined":
        return "#888";
      case "object":
        return "#a50";
      case "array":
        return "#05a";
      default:
        return "#333";
    }
  }
</script>

<div class="tree-node">
  {#if key !== undefined}
    <span
      class="key"
      on:click={(e) => toggle(e)}
      on:keydown={handleKeydown}
      role="button"
      tabindex="0"
    >
      {#if isObject(value) || isArray(value)}
        <span class="expand-icon">{expanded ? "▼" : "▶"}</span>
      {:else}
        <span class="expand-icon-placeholder"></span>
      {/if}
      <span class="key-name">{key}:</span>
    </span>
  {/if}
  <span
    class="value-wrapper"
    class:expandable={isObject(value) || isArray(value)}
  >
    {#if isObject(value)}
      <span class="type-badge" style="color: {getTypeColor('object')}"
        >Object</span
      >
      <span
        class="value-preview"
        on:click={(e) => toggle(e)}
        on:keydown={handleKeydown}
        role="button"
        tabindex="0"
      >
        {getValuePreview(value)}
      </span>
      {#if expanded}
        <div class="children">
          {#each Object.entries(value) as [k, v]}
            <TreeView value={v} key={k} depth={depth + 1} />
          {/each}
        </div>
      {/if}
    {:else if isArray(value)}
      <span class="type-badge" style="color: {getTypeColor('array')}"
        >Array</span
      >
      <span
        class="value-preview"
        on:click={(e) => toggle(e)}
        on:keydown={handleKeydown}
        role="button"
        tabindex="0"
      >
        {getValuePreview(value)}
      </span>
      {#if expanded}
        <div class="children">
          {#each value as item, index}
            <TreeView value={item} key={index} depth={depth + 1} />
          {/each}
        </div>
      {/if}
    {:else}
      <span
        class="value-preview literal"
        style="color: {getTypeColor(getType(value))}"
      >
        {getValuePreview(value)}
      </span>
    {/if}
  </span>
</div>

<style>
  .tree-node {
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", "source-code-pro",
      monospace;
    font-size: 13px;
    line-height: 1.5;
    display: flex;
    flex-direction: row;
    align-items: flex-start;
  }

  .key {
    color: #881391;
    cursor: pointer;
    user-select: none;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    margin-right: 4px;
    padding: 1px 2px;
    border-radius: 2px;
  }

  .key:hover {
    background-color: #f0f0f0;
  }

  .key:focus {
    outline: 1px solid #2563eb;
    outline-offset: 1px;
  }

  .expand-icon,
  .expand-icon-placeholder {
    display: inline-block;
    width: 12px;
    font-size: 10px;
    color: #666;
    text-align: center;
  }

  .expand-icon-placeholder {
    visibility: hidden;
  }

  .key-name {
    font-weight: 500;
  }

  .value-wrapper {
    display: inline-block;
  }

  .value-wrapper.expandable {
    cursor: pointer;
  }

  .type-badge {
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    margin-right: 6px;
    opacity: 0.7;
    text-transform: uppercase;
  }

  .value-preview {
    color: #333;
  }

  .value-preview.literal {
    color: #333;
  }

  .value-preview:not(.literal) {
    cursor: pointer;
    user-select: none;
    padding: 1px 2px;
    border-radius: 2px;
  }

  .value-preview:not(.literal):hover {
    background-color: #f0f0f0;
  }

  .value-preview:not(.literal):focus {
    outline: 1px solid #2563eb;
    outline-offset: 1px;
  }

  /* Color coding for different types */
  .value-preview.literal {
    color: #333;
  }

  .children {
    margin-left: 20px;
    margin-top: 2px;
    border-left: 1px solid #e0e0e0;
    padding-left: 12px;
  }
</style>
