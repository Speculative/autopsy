/**
 * studyEvents.ts — HCI study interaction event tracking for autopsy_html.
 *
 * Buffers events and flushes them periodically to the VS Code extension via
 * postMessage. Is a no-op when not running inside a VS Code webview.
 */

import { isVSCodeWebview, getVSCodeApi } from './vscodeApi';

interface StudyEvent {
  eventType: string;
  timestamp: string;
  data?: Record<string, unknown>;
}

const FLUSH_INTERVAL_MS = 500;
const MAX_BUFFER_SIZE = 50;

const eventBuffer: StudyEvent[] = [];
let flushTimer: ReturnType<typeof setInterval> | null = null;

function flush(): void {
  if (eventBuffer.length === 0) return;
  const api = getVSCodeApi();
  if (!api) return;

  const events = eventBuffer.splice(0, eventBuffer.length);
  try {
    api.postMessage({ type: 'studyEvent', events });
  } catch {
    // drop on error — best effort
  }
}

/**
 * Record a study interaction event. No-op outside VS Code webview.
 */
export function trackEvent(eventType: string, data?: Record<string, unknown>): void {
  if (!isVSCodeWebview()) return;

  eventBuffer.push({
    eventType,
    timestamp: new Date().toISOString(),
    data,
  });

  if (eventBuffer.length >= MAX_BUFFER_SIZE) {
    flush();
  }
}

/**
 * Start buffered event tracking. Call once on app init.
 */
export function initStudyTracking(): void {
  if (!isVSCodeWebview()) return;

  flushTimer = setInterval(flush, FLUSH_INTERVAL_MS);

  // Track when the webview iframe gains/loses keyboard focus.
  // This fires reliably when the user clicks into or out of the webview,
  // even when the panel was already the active tab in its column (in which
  // case the extension-side onDidChangeViewState does not fire).
  window.addEventListener('focus', () => trackEvent('ui.webviewFocus'));
  window.addEventListener('blur', () => trackEvent('ui.webviewBlur'));

  // Flush on visibility change (panel hidden/shown)
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) flush();
  });
}

/**
 * Flush remaining events and stop the timer. Call on app teardown.
 */
export function disposeStudyTracking(): void {
  if (flushTimer !== null) {
    clearInterval(flushTimer);
    flushTimer = null;
  }
  flush();
}
