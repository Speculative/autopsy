import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

export class AutopsyPanel {
  public static currentPanel: AutopsyPanel | undefined;
  private readonly _panel: vscode.WebviewPanel;
  private readonly _extensionUri: vscode.Uri;
  private readonly _outputChannel: vscode.OutputChannel;
  private _disposables: vscode.Disposable[] = [];

  public static createOrShow(extensionUri: vscode.Uri, outputChannel: vscode.OutputChannel) {
    const column = vscode.window.activeTextEditor
      ? vscode.window.activeTextEditor.viewColumn
      : undefined;

    // If panel exists, reveal it
    if (AutopsyPanel.currentPanel) {
      outputChannel.appendLine('Panel already exists, revealing it');
      AutopsyPanel.currentPanel._panel.reveal(column);
      return;
    }

    outputChannel.appendLine('Creating new webview panel');

    // Create new panel
    const panel = vscode.window.createWebviewPanel(
      'autopsyViewer',
      'Autopsy Viewer',
      column || vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')]
      }
    );

    outputChannel.appendLine('Webview panel created, initializing AutopsyPanel');
    AutopsyPanel.currentPanel = new AutopsyPanel(panel, extensionUri, outputChannel);
  }

  public reveal() {
    this._panel.reveal();
  }

  private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, outputChannel: vscode.OutputChannel) {
    this._panel = panel;
    this._extensionUri = extensionUri;
    this._outputChannel = outputChannel;

    this._outputChannel.appendLine('AutopsyPanel constructor called');

    // Set HTML content
    this._update();

    // Handle messages from webview
    this._panel.webview.onDidReceiveMessage(
      this._handleMessage.bind(this),
      null,
      this._disposables
    );

    // Handle panel disposal
    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
  }

  private _update() {
    this._outputChannel.appendLine('Updating webview HTML content');
    const webview = this._panel.webview;
    this._panel.webview.html = this._getHtmlForWebview(webview);
    this._outputChannel.appendLine('Webview HTML content set');
  }

  private _getHtmlForWebview(webview: vscode.Webview): string {
    // Read the built HTML file
    const htmlPath = vscode.Uri.joinPath(this._extensionUri, 'media', 'webview.html');
    this._outputChannel.appendLine(`Loading webview HTML from: ${htmlPath.fsPath}`);
    let html: string;

    try {
      html = fs.readFileSync(htmlPath.fsPath, 'utf8');
      this._outputChannel.appendLine(`Successfully loaded HTML file (${html.length} bytes)`);
    } catch (error) {
      this._outputChannel.appendLine(`ERROR: Failed to read HTML file: ${error}`);
      return `
        <!DOCTYPE html>
        <html>
          <head>
            <meta charset="UTF-8">
            <title>Autopsy Viewer - Error</title>
          </head>
          <body>
            <h1>Error Loading Autopsy Viewer</h1>
            <p>Could not find webview.html at: ${htmlPath.fsPath}</p>
            <p>Please run: <code>cd autopsy_html && npm run build:vscode</code></p>
          </body>
        </html>
      `;
    }

    // Generate nonce for CSP
    const nonce = getNonce();

    // Inject VS Code webview API acquisition script and console interceptor
    const vscodeApiScript = `
      <script nonce="${nonce}">
        (function() {
          window.vscode = acquireVsCodeApi();
          window.__VSCODE_WEBVIEW__ = true;

          // Intercept console methods to forward to extension
          const originalConsole = {
            log: console.log,
            warn: console.warn,
            error: console.error,
            info: console.info
          };

          ['log', 'warn', 'error', 'info'].forEach(level => {
            console[level] = function(...args) {
              // Call original console method
              originalConsole[level].apply(console, args);

              // Forward to extension
              try {
                window.vscode.postMessage({
                  type: 'console',
                  level: level,
                  message: args.map(arg =>
                    typeof arg === 'object' ? JSON.stringify(arg) : String(arg)
                  ).join(' ')
                });
              } catch (e) {
                originalConsole.error('Failed to forward console message:', e);
              }
            };
          });

          console.log('Autopsy Viewer webview initialized');
        })();
      </script>
    `;

    // Insert before the closing </head> or at start of <body>
    if (html.includes('</head>')) {
      html = html.replace('</head>', `${vscodeApiScript}</head>`);
    } else if (html.includes('<body')) {
      html = html.replace('<body', `${vscodeApiScript}<body`);
    } else {
      // Fallback: prepend to content
      html = vscodeApiScript + html;
    }

    // Add nonce to all inline script tags
    this._outputChannel.appendLine('Adding nonce attributes to script tags');
    html = html.replace(/<script(?!\s+src=)([^>]*)>/g, `<script nonce="${nonce}"$1>`);

    // Set CSP - allow inline scripts with nonce, allow WebSocket connections
    // Note: Svelte requires unsafe-inline and unsafe-eval for the bundled app
    const csp = `
      <meta http-equiv="Content-Security-Policy" content="
        default-src 'none';
        style-src ${webview.cspSource} 'unsafe-inline';
        script-src 'nonce-${nonce}' 'unsafe-inline' 'unsafe-eval';
        connect-src ws://localhost:* wss://localhost:* http://localhost:* https://localhost:*;
        img-src ${webview.cspSource} data: blob:;
        font-src ${webview.cspSource} data:;
      ">
    `;

    if (html.includes('<head>')) {
      html = html.replace('<head>', `<head>${csp}`);
    } else {
      // Add a head section if it doesn't exist
      html = `<!DOCTYPE html><html><head>${csp}</head><body>` + html + `</body></html>`;
    }

    this._outputChannel.appendLine('HTML processing complete, returning modified HTML');
    return html;
  }

  private async _handleMessage(message: any) {
    switch (message.type) {
      case 'openFile':
        this._outputChannel.appendLine(`Opening file: ${message.filename}:${message.line}`);
        await this._openFileAtLocation(
          message.filename,
          message.line,
          message.column || 0
        );
        break;
      case 'console':
        // Forward console messages from webview to output channel
        const level = message.level || 'log';
        const msg = message.message || '';
        this._outputChannel.appendLine(`[Webview ${level.toUpperCase()}] ${msg}`);
        break;
    }
  }

  private async _openFileAtLocation(
    filename: string,
    line: number,
    column: number = 0
  ) {
    try {
      // Use absolute path directly (as per user preference)
      const uri = vscode.Uri.file(filename);

      // Check if file exists
      try {
        await vscode.workspace.fs.stat(uri);
      } catch {
        vscode.window.showWarningMessage(`File not found: ${filename}`);
        return;
      }

      // Open the file
      const document = await vscode.workspace.openTextDocument(uri);
      const editor = await vscode.window.showTextDocument(document);

      // Move cursor to line (VS Code uses 0-indexed lines)
      const position = new vscode.Position(Math.max(0, line - 1), column);
      editor.selection = new vscode.Selection(position, position);
      editor.revealRange(
        new vscode.Range(position, position),
        vscode.TextEditorRevealType.InCenter
      );
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to open file: ${error}`);
    }
  }

  public dispose() {
    AutopsyPanel.currentPanel = undefined;
    this._panel.dispose();
    while (this._disposables.length) {
      const d = this._disposables.pop();
      if (d) d.dispose();
    }
  }
}

function getNonce() {
  let text = '';
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    text += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return text;
}
