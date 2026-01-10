<script lang="ts">
  import { isVSCodeWebview, openFileInVSCode } from './vscodeApi';

  interface Props {
    filename: string;
    line: number;
    functionName?: string;
    className?: string;
    showFunction?: boolean;
    compact?: boolean;
  }

  let {
    filename,
    line,
    functionName,
    className,
    showFunction = true,
    compact = false
  }: Props = $props();

  const inVSCode = isVSCodeWebview();

  function getShortFilename(path: string): string {
    const parts = path.split(/[\\/]/);
    return parts[parts.length - 1];
  }

  function handleClick(e: MouseEvent) {
    if (inVSCode) {
      e.preventDefault();
      e.stopPropagation();
      openFileInVSCode(filename, line);
    }
  }
</script>

{#if inVSCode}
  <button class="code-location clickable" class:compact onclick={handleClick} title="Open in editor: {filename}:{line}">
    {#if compact}
      <span class="compact-text">
        {getShortFilename(filename)}:{line}
        {#if showFunction && functionName}
          ({#if className}{className}.{/if}{functionName})
        {/if}
      </span>
    {:else}
      <span class="filename">{getShortFilename(filename)}</span><span class="line-number">:{line}</span>
      {#if showFunction && functionName}
        <span class="function-name">
          in <code>
            {#if className}
              {className}.{functionName}
            {:else}
              {functionName}
            {/if}
          </code>
        </span>
      {/if}
    {/if}
  </button>
{:else}
  <span class="code-location" class:compact>
    {#if compact}
      <span class="compact-text">
        {getShortFilename(filename)}:{line}
        {#if showFunction && functionName}
          ({#if className}{className}.{/if}{functionName})
        {/if}
      </span>
    {:else}
      <span class="filename">{getShortFilename(filename)}</span><span class="line-number">:{line}</span>
      {#if showFunction && functionName}
        <span class="function-name">
          in <code>
            {#if className}
              {className}.{functionName}
            {:else}
              {functionName}
            {/if}
          </code>
        </span>
      {/if}
    {/if}
  </span>
{/if}

<style>
  .code-location {
    display: inline;
  }

  .code-location.clickable {
    cursor: pointer;
    background: none;
    border: none;
    padding: 0;
    font: inherit;
    color: inherit;
    text-align: left;
  }

  .code-location.clickable:hover .filename {
    text-decoration: underline;
    color: #2563eb;
  }

  .code-location.clickable:hover .line-number {
    color: #2563eb;
  }

  .filename {
    font-weight: 600;
    color: #3b82f6;
    font-size: 1.1rem;
  }

  .line-number {
    color: #6b7280;
    font-size: 0.9rem;
    font-weight: 400;
  }

  .function-name {
    color: #6b7280;
    margin-left: 0.5rem;
  }

  .function-name code {
    background-color: #f3f4f6;
    padding: 0.125rem 0.375rem;
    border-radius: 0.25rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.875rem;
  }

  /* Compact mode styles */
  .compact-text {
    font-weight: 400;
    color: #9ca3af;
    font-size: 0.7rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }

  .code-location.clickable.compact:hover .compact-text {
    color: #6b7280;
  }
</style>
