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
