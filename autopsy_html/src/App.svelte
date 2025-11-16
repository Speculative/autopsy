<script lang="ts">
  import type { AutopsyData, CallSite } from './types'

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

  function formatValue(value: unknown): string {
    if (value === null) return 'null'
    if (value === undefined) return 'undefined'
    if (typeof value === 'string') return `"${value}"`
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value, null, 2)
      } catch {
        return String(value)
      }
    }
    return String(value)
  }

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
          <div class="file-path">{callSite.filename}</div>
          <div class="values">
            {#each callSite.values as value, index}
              <div class="value">
                <span class="value-index">[{index}]</span>
                <pre class="value-content">{formatValue(value)}</pre>
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

  .file-path {
    color: #888;
    font-size: 0.85rem;
    margin-bottom: 1rem;
    font-family: monospace;
  }

  .values {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .value {
    display: flex;
    gap: 0.5rem;
    align-items: flex-start;
  }

  .value-index {
    color: #666;
    font-weight: 500;
    min-width: 3ch;
  }

  .value-content {
    flex: 1;
    margin: 0;
    padding: 0.5rem;
    background: white;
    border: 1px solid #e5e5e5;
    border-radius: 4px;
    font-size: 0.9rem;
    overflow-x: auto;
  }

  pre.value-content {
    white-space: pre-wrap;
    word-wrap: break-word;
  }
</style>
