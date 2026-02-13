<script lang="ts">
  interface Props {
    content?: string;
  }

  let { content = $bindable("") }: Props = $props();

  let isEditing = $state(false);
  let textareaEl: HTMLTextAreaElement | undefined = $state();

  function startEditing() {
    isEditing = true;
    // Focus the textarea after Svelte updates the DOM
    requestAnimationFrame(() => textareaEl?.focus());
  }

  function stopEditing() {
    isEditing = false;
  }
</script>

<div class="markdown-cell">
  {#if isEditing}
    <textarea
      bind:this={textareaEl}
      bind:value={content}
      onblur={stopEditing}
      class="markdown-editor"
      placeholder="Write your notes here..."
      rows="4"
    ></textarea>
  {:else}
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="markdown-display" onclick={startEditing}>
      {#if content}
        {content}
      {:else}
        <span class="placeholder">Click to add notes...</span>
      {/if}
    </div>
  {/if}
</div>

<style>
  .markdown-cell {
    min-height: 2.5rem;
  }

  .markdown-editor {
    width: 100%;
    min-height: 80px;
    padding: 0.75rem;
    border: none;
    border-radius: 0 0 8px 8px;
    font-family: inherit;
    font-size: 0.9rem;
    line-height: 1.5;
    resize: vertical;
    outline: none;
    background: #fff;
    box-sizing: border-box;
  }

  .markdown-display {
    padding: 0.75rem;
    white-space: pre-wrap;
    font-size: 0.9rem;
    line-height: 1.5;
    cursor: text;
    min-height: 2.5rem;
    border-radius: 0 0 8px 8px;
  }

  .markdown-display:hover {
    background: #f8fafc;
  }

  .placeholder {
    color: #94a3b8;
    font-style: italic;
  }
</style>
