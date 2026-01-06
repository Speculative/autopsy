<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { EditorView, basicSetup } from 'codemirror';
  import { python } from '@codemirror/lang-python';
  import { EditorState } from '@codemirror/state';

  interface Props {
    value: string;
    onchange: (value: string) => void;
    placeholder?: string;
  }

  let { value = $bindable(), onchange, placeholder = '' }: Props = $props();
  let editorContainer: HTMLDivElement;
  let editorView: EditorView | null = null;

  onMount(() => {
    const updateListener = EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        const newValue = update.state.doc.toString();
        value = newValue;
        onchange(newValue);
      }
    });

    editorView = new EditorView({
      state: EditorState.create({
        doc: value,
        extensions: [
          basicSetup,
          python(),
          updateListener,
          EditorView.theme({
            "&": {
              fontSize: "0.9rem",
              fontFamily: '"Monaco", "Menlo", "Ubuntu Mono", "Consolas", monospace',
            },
            ".cm-content": {
              minHeight: "200px",
            },
            ".cm-scroller": {
              overflow: "auto",
            }
          })
        ],
      }),
      parent: editorContainer,
    });
  });

  onDestroy(() => {
    if (editorView) {
      editorView.destroy();
    }
  });

  // Update editor when value changes externally
  $effect(() => {
    if (editorView && editorView.state.doc.toString() !== value) {
      editorView.dispatch({
        changes: {
          from: 0,
          to: editorView.state.doc.length,
          insert: value
        }
      });
    }
  });
</script>

<div bind:this={editorContainer} class="code-editor"></div>

<style>
  .code-editor {
    border: 1px solid #d1d5db;
    border-radius: 4px;
    overflow: hidden;
  }

  .code-editor :global(.cm-editor) {
    height: 100%;
  }

  .code-editor :global(.cm-focused) {
    outline: none;
  }
</style>
