// VS Code webview API wrapper

interface VSCodeApi {
  postMessage(message: any): void;
  getState(): any;
  setState(state: any): void;
}

declare global {
  interface Window {
    vscode?: VSCodeApi;
    __VSCODE_WEBVIEW__?: boolean;
  }
}

let vscodeApi: VSCodeApi | null = null;

export function isVSCodeWebview(): boolean {
  return typeof window !== 'undefined' && window.__VSCODE_WEBVIEW__ === true;
}

export function getVSCodeApi(): VSCodeApi | null {
  if (!isVSCodeWebview()) return null;

  if (!vscodeApi && window.vscode) {
    vscodeApi = window.vscode;
  }
  return vscodeApi;
}

export function openFileInVSCode(filename: string, line: number, column: number = 0): boolean {
  const api = getVSCodeApi();
  if (!api) return false;

  api.postMessage({
    type: 'openFile',
    filename,
    line,
    column
  });
  return true;
}

/**
 * Extract only the minimal data the extension needs for CodeLens and navigation.
 * Avoids serializing the full data object (values, stack traces, etc.).
 */
function extractMinimalData(data: any): any {
  const call_sites = data.call_sites?.map((cs: any) => ({
    filename: cs.filename,
    line: cs.line,
    function_name: cs.function_name,
    class_name: cs.class_name,
    is_dashboard: cs.is_dashboard || false,
    value_groups: cs.value_groups?.map((vg: any) => ({
      log_index: vg.log_index,
      stack_trace_id: vg.stack_trace_id,
      dashboard_type: vg.dashboard_type,
    })) ?? [],
  })) ?? [];

  // Only include dashboard summary data (no full values)
  let dashboard: any = undefined;
  if (data.dashboard) {
    dashboard = {
      counts: data.dashboard.counts?.map((c: any) => ({
        call_site: { filename: c.call_site.filename, line: c.call_site.line },
        value_counts: Object.fromEntries(
          Object.entries(c.value_counts).map(([k, v]: [string, any]) => [k, { count: v.count }])
        ),
      })),
      histograms: data.dashboard.histograms?.map((h: any) => ({
        call_site: { filename: h.call_site.filename, line: h.call_site.line },
        values: h.values?.map((v: any) => ({ value: v.value })),
      })),
      timeline: data.dashboard.timeline?.map((t: any) => ({
        call_site: { filename: t.call_site.filename, line: t.call_site.line },
      })),
      happened: data.dashboard.happened?.map((h: any) => ({
        call_site: { filename: h.call_site.filename, line: h.call_site.line },
        count: h.count,
      })),
    };
  }

  return { call_sites, dashboard };
}

let _pendingData: any = null;
let _debounceTimer: ReturnType<typeof setTimeout> | null = null;
const DEBOUNCE_MS = 200;

function _flushLogDataUpdate() {
  _debounceTimer = null;
  if (!_pendingData) return;

  const api = getVSCodeApi();
  if (!api) return;

  try {
    api.postMessage({
      type: 'logDataUpdate',
      data: _pendingData,
    });
  } catch (error) {
    console.error('Failed to send log data update:', error);
  }
  _pendingData = null;
}

export function sendLogDataUpdate(data: any): boolean {
  if (!getVSCodeApi()) return false;

  // Extract minimal payload (avoids serializing full log values / stack traces)
  _pendingData = extractMinimalData(data);

  // Debounce: coalesce rapid updates into a single message
  if (_debounceTimer === null) {
    _debounceTimer = setTimeout(_flushLogDataUpdate, DEBOUNCE_MS);
  }
  return true;
}

export function navigateToLogInVSCode(logIndex: number): boolean {
  const api = getVSCodeApi();
  if (!api) return false;

  api.postMessage({
    type: 'navigateToLog',
    logIndex
  });
  return true;
}

// Message handler system for incoming messages from extension
export type MessageHandler = (message: any) => void;
let messageHandlers: MessageHandler[] = [];

export function addMessageHandler(handler: MessageHandler) {
  messageHandlers.push(handler);
}

export function removeMessageHandler(handler: MessageHandler) {
  messageHandlers = messageHandlers.filter(h => h !== handler);
}

// Initialize listener once
if (typeof window !== 'undefined' && window.vscode) {
  window.addEventListener('message', (event) => {
    const message = event.data;
    messageHandlers.forEach(handler => handler(message));
  });
}
