<script lang="ts">
  import TreeView from "./TreeView.svelte";

  interface PathSegment {
    key: string | number;
    type: 'object' | 'array';
  }

  interface Props {
    value: unknown;
    key?: string | number;
    depth?: number;
    enableDrag?: boolean;
    frameIndex?: number;
    pathPrefix?: PathSegment[];
    sourceLogIndex?: number;
    frameFunctionName?: string;
    frameFilename?: string;
    frameLineNumber?: number;
    baseExpression?: string; // The base expression to prepend to the dragged path
  }

  let {
    value,
    key = undefined,
    depth = 0,
    enableDrag = false,
    frameIndex = undefined,
    pathPrefix = [],
    sourceLogIndex = undefined,
    frameFunctionName = undefined,
    frameFilename = undefined,
    frameLineNumber = undefined,
    baseExpression = undefined,
  }: Props = $props();

  let expanded = $state(false); // Collapsed by default

  // Compute current path by appending current key to pathPrefix
  const currentPath = $derived.by(() => {
    if (!enableDrag || key === undefined) return [];

    const segment: PathSegment = {
      key,
      type: isArray(value) ? 'array' : 'object'
    };

    return [...pathPrefix, segment];
  });

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
    console.log("toggle called", { isExpandable: isObject(value) || isArray(value), expanded, value });
    event.stopPropagation();
    if (isObject(value) || isArray(value)) {
      expanded = !expanded;
      console.log("toggled to", expanded);
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggle(event);
    }
  }

  function handleDragStart(event: DragEvent) {
    console.log("Drag started", { enableDrag, frameIndex, sourceLogIndex, path: currentPath });

    if (!enableDrag || !event.dataTransfer || frameIndex === undefined || sourceLogIndex === undefined) {
      return;
    }

    const payload = {
      type: 'stack-variable',
      frameIndex,
      path: currentPath,
      sourceLogIndex,
      frameFunctionName,
      frameFilename,
      frameLineNumber,
      baseExpression,
    };

    // Set drag data
    event.dataTransfer.effectAllowed = 'copy';
    event.dataTransfer.setData('application/json', JSON.stringify(payload));

    // Create visual ghost showing the path
    const ghostText = generatePathPreview(currentPath);
    const ghost = document.createElement('div');
    ghost.textContent = ghostText;
    ghost.style.cssText = 'position: absolute; top: -1000px; background: #f3f4f6; padding: 6px 12px; border-radius: 4px; font-family: monospace; font-size: 12px; border: 1px solid #d1d5db; box-shadow: 0 1px 3px rgba(0,0,0,0.1);';
    document.body.appendChild(ghost);
    event.dataTransfer.setDragImage(ghost, 0, 0);
    setTimeout(() => document.body.removeChild(ghost), 0);
  }

  function generatePathPreview(path: PathSegment[]): string {
    if (path.length === 0) return '';
    return path.map(seg => {
      if (typeof seg.key === 'number') return `[${seg.key}]`;
      return seg.key;
    }).join('.');
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

<div class="tree-node" class:nested={key !== undefined}>
  <div class="tree-line">
    {#if key !== undefined}
      <span
        class="key"
        class:draggable={enableDrag && key !== undefined}
        draggable={enableDrag && key !== undefined}
        ondragstart={(e) => {
          console.log("Drag start event")
          handleDragStart(e)
        }}
        onclick={(e) => {
          console.log("Clicked")
          toggle(e);
        }}
        onkeydown={handleKeydown}
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
      onclick={(e) => (isObject(value) || isArray(value)) && toggle(e)}
      onkeydown={(e) =>
        (isObject(value) || isArray(value)) && handleKeydown(e)}
      {...isObject(value) || isArray(value)
        ? { role: "button", tabindex: 0 }
        : {}}
    >
      {#if isObject(value)}
        <span class="type-badge" style="color: {getTypeColor('object')}"
          >Object</span
        >
        <span class="value-preview">
          {getValuePreview(value)}
        </span>
      {:else if isArray(value)}
        <span class="type-badge" style="color: {getTypeColor('array')}"
          >Array</span
        >
        <span class="value-preview">
          {getValuePreview(value)}
        </span>
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
  {#if expanded && (isObject(value) || isArray(value))}
    <div class="children">
      {#if isObject(value)}
        {#each Object.entries(value) as [k, v]}
          <TreeView
            value={v}
            key={k}
            depth={depth + 1}
            enableDrag={enableDrag}
            frameIndex={frameIndex}
            pathPrefix={currentPath}
            sourceLogIndex={sourceLogIndex}
            frameFunctionName={frameFunctionName}
            frameFilename={frameFilename}
            frameLineNumber={frameLineNumber}
            baseExpression={baseExpression}
          />
        {/each}
      {:else if isArray(value)}
        {#each value as item, index}
          <TreeView
            value={item}
            key={index}
            depth={depth + 1}
            enableDrag={enableDrag}
            frameIndex={frameIndex}
            pathPrefix={currentPath}
            sourceLogIndex={sourceLogIndex}
            frameFunctionName={frameFunctionName}
            frameFilename={frameFilename}
            frameLineNumber={frameLineNumber}
            baseExpression={baseExpression}
          />
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .tree-node {
    font-family: "Monaco", "Menlo", "Ubuntu Mono", "Consolas", "source-code-pro",
      monospace;
    font-size: 0.9rem;
    line-height: 1.5;
  }

  .tree-node.nested {
    margin-left: 20px;
  }

  .tree-line {
    display: flex;
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

  .key.draggable {
    cursor: grab;
    transition: background-color 0.2s;
  }

  .key.draggable:hover {
    background-color: #e0f2fe;
    box-shadow: 0 0 0 1px #bae6fd;
  }

  .key.draggable:active {
    cursor: grabbing;
    background-color: #bae6fd;
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
    user-select: none;
    padding: 1px 2px;
    border-radius: 2px;
  }

  .value-wrapper.expandable:hover {
    background-color: #f0f0f0;
  }

  .value-wrapper.expandable:focus {
    outline: 1px solid #2563eb;
    outline-offset: 1px;
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

  /* Color coding for different types */
  .value-preview.literal {
    color: #333;
  }

  .children {
    margin-top: 2px;
    border-left: 1px solid #e0e0e0;
    padding-left: 0;
    margin-left: 0;
  }
</style>
