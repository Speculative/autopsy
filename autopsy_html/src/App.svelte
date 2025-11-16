<script lang="ts">
  import type { AutopsyData, CallSite } from './types'
  import TreeView from './TreeView.svelte'

  let data: AutopsyData = { generated_at: '', call_sites: [] }

  // Load data from the injection point
  function loadData(): void {
    const dataElement = document.getElementById('autopsy-data')
    if (dataElement && dataElement.textContent) {
      try {
        const parsed = JSON.parse(dataElement.textContent) as Partial<AutopsyData>
        data = {
          generated_at: parsed.generated_at ?? '',
          call_sites: parsed.call_sites ?? []
        }
      } catch (e) {
        console.error('Failed to parse autopsy data:', e)
        data = { generated_at: '', call_sites: [] }
      }
    }
  }

  // Load data on mount
  loadData()

  function getFilename(callSite: CallSite): string {
    const parts = callSite.filename.split('/')
    return parts[parts.length - 1]
  }
</script>

<main>
  <div class="header">
    <h1>Autopsy Report</h1>
    {#if data.generated_at}
      <div class="timestamp">Generated: {new Date(data.generated_at).toLocaleString()}</div>
    {/if}
  </div>

  {#if data.call_sites.length === 0}
    <p class="empty">No report data available.</p>
  {:else}
    <div class="call-sites">
      {#each data.call_sites as callSite (callSite.filename + callSite.line)}
        <div class="call-site">
          <div class="call-site-header">
            <span class="filename">{getFilename(callSite)}</span>
            <span class="line">Line {callSite.line}</span>
          </div>
          <div class="function-name">Function: <code>{callSite.function_name}</code></div>
          <div class="file-path">{callSite.filename}</div>
          <div class="value-groups">
            {#each callSite.value_groups as valueGroup, groupIndex}
              <div class="value-group">
                <div class="value-group-header">
                  Call {groupIndex + 1}
                  {#if valueGroup.function_name !== callSite.function_name}
                    <span class="function-name-inline">in {valueGroup.function_name}</span>
                  {/if}
                </div>
                <div class="values">
                  {#each valueGroup.values as valueWithName, valueIndex}
                    <div class="value-item">
                      {#if valueWithName.name}
                        <div class="value-label">{valueWithName.name}:</div>
                      {/if}
                      <TreeView value={valueWithName.value} />
                    </div>
                  {/each}
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</main>

<style>
  main {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
    font-family: system-ui, -apple-system, sans-serif;
  }

  .header {
    margin-bottom: 2rem;
  }

  h1 {
    margin: 0 0 0.5rem 0;
    color: #333;
  }

  .timestamp {
    color: #666;
    font-size: 0.9rem;
  }

  .empty {
    text-align: center;
    color: #666;
    padding: 3rem;
  }

  .call-sites {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .call-site {
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 1rem;
    background: #f9f9f9;
  }

  .call-site-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .filename {
    font-weight: 600;
    color: #2563eb;
    font-size: 1.1rem;
  }

  .line {
    color: #666;
    font-size: 0.9rem;
  }

  .function-name {
    color: #666;
    font-size: 0.9rem;
    margin-bottom: 0.5rem;
    font-weight: 500;
  }

  .function-name code {
    background: #f0f0f0;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
    color: #2563eb;
  }

  .file-path {
    color: #888;
    font-size: 0.85rem;
    margin-bottom: 1rem;
    font-family: monospace;
  }

  .value-groups {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .value-group {
    border-left: 3px solid #2563eb;
    padding-left: 0.75rem;
  }

  .value-group-header {
    font-weight: 600;
    color: #2563eb;
    font-size: 0.85rem;
    margin-bottom: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .function-name-inline {
    font-size: 0.75rem;
    text-transform: none;
    font-weight: 400;
    color: #666;
  }

  .values {
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 1rem;
    align-items: flex-start;
  }

  .value-item {
    flex: 0 1 auto;
    min-width: 0;
    padding: 0.75rem;
    background: white;
    border: 1px solid #e5e5e5;
    border-radius: 4px;
    overflow-x: auto;
    max-width: 100%;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .value-label {
    font-weight: 600;
    color: #881391;
    font-size: 0.85rem;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  }

  @media (max-width: 768px) {
    .values {
      flex-direction: column;
    }

    .value-item {
      width: 100%;
    }
  }
</style>
