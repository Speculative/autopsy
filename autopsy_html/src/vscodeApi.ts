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

export function sendLogDataUpdate(data: any): boolean {
  const api = getVSCodeApi();
  if (!api) {
    console.error('VS Code API not available');
    return false;
  }

  try {
    console.log('Attempting to send log data update, call_sites:', data.call_sites?.length);

    // Deep clone the data to avoid circular references and ensure it's serializable
    // postMessage uses structured clone algorithm which can't handle some objects
    const serializedData = JSON.parse(JSON.stringify(data));

    api.postMessage({
      type: 'logDataUpdate',
      data: serializedData
    });
    console.log('Log data update sent successfully');
    return true;
  } catch (error) {
    console.error('Failed to send log data update:', error);
    return false;
  }
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
