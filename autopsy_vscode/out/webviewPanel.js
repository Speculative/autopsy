"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.AutopsyPanel = void 0;
const vscode = __importStar(require("vscode"));
const fs = __importStar(require("fs"));
class AutopsyPanel {
    static createOrShow(extensionUri, outputChannel) {
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
        const panel = vscode.window.createWebviewPanel('autopsyViewer', 'Autopsy Viewer', column || vscode.ViewColumn.One, {
            enableScripts: true,
            retainContextWhenHidden: true,
            localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')]
        });
        outputChannel.appendLine('Webview panel created, initializing AutopsyPanel');
        AutopsyPanel.currentPanel = new AutopsyPanel(panel, extensionUri, outputChannel);
    }
    reveal() {
        this._panel.reveal();
    }
    constructor(panel, extensionUri, outputChannel) {
        this._disposables = [];
        this._panel = panel;
        this._extensionUri = extensionUri;
        this._outputChannel = outputChannel;
        this._outputChannel.appendLine('AutopsyPanel constructor called');
        // Set HTML content
        this._update();
        // Handle messages from webview
        this._panel.webview.onDidReceiveMessage(this._handleMessage.bind(this), null, this._disposables);
        // Handle panel disposal
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
    }
    _update() {
        this._outputChannel.appendLine('Updating webview HTML content');
        const webview = this._panel.webview;
        this._panel.webview.html = this._getHtmlForWebview(webview);
        this._outputChannel.appendLine('Webview HTML content set');
    }
    _getHtmlForWebview(webview) {
        // Read the built HTML file
        const htmlPath = vscode.Uri.joinPath(this._extensionUri, 'media', 'webview.html');
        this._outputChannel.appendLine(`Loading webview HTML from: ${htmlPath.fsPath}`);
        let html;
        try {
            html = fs.readFileSync(htmlPath.fsPath, 'utf8');
            this._outputChannel.appendLine(`Successfully loaded HTML file (${html.length} bytes)`);
        }
        catch (error) {
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
        }
        else if (html.includes('<body')) {
            html = html.replace('<body', `${vscodeApiScript}<body`);
        }
        else {
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
        }
        else {
            // Add a head section if it doesn't exist
            html = `<!DOCTYPE html><html><head>${csp}</head><body>` + html + `</body></html>`;
        }
        this._outputChannel.appendLine('HTML processing complete, returning modified HTML');
        return html;
    }
    async _handleMessage(message) {
        switch (message.type) {
            case 'openFile':
                this._outputChannel.appendLine(`Opening file: ${message.filename}:${message.line}`);
                await this._openFileAtLocation(message.filename, message.line, message.column || 0);
                break;
            case 'console':
                // Forward console messages from webview to output channel
                const level = message.level || 'log';
                const msg = message.message || '';
                this._outputChannel.appendLine(`[Webview ${level.toUpperCase()}] ${msg}`);
                break;
        }
    }
    async _openFileAtLocation(filename, line, column = 0) {
        try {
            // Use absolute path directly (as per user preference)
            const uri = vscode.Uri.file(filename);
            // Check if file exists
            try {
                await vscode.workspace.fs.stat(uri);
            }
            catch {
                vscode.window.showWarningMessage(`File not found: ${filename}`);
                return;
            }
            // Open the file
            const document = await vscode.workspace.openTextDocument(uri);
            const editor = await vscode.window.showTextDocument(document);
            // Move cursor to line (VS Code uses 0-indexed lines)
            const position = new vscode.Position(Math.max(0, line - 1), column);
            editor.selection = new vscode.Selection(position, position);
            editor.revealRange(new vscode.Range(position, position), vscode.TextEditorRevealType.InCenter);
        }
        catch (error) {
            vscode.window.showErrorMessage(`Failed to open file: ${error}`);
        }
    }
    dispose() {
        AutopsyPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const d = this._disposables.pop();
            if (d)
                d.dispose();
        }
    }
}
exports.AutopsyPanel = AutopsyPanel;
function getNonce() {
    let text = '';
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return text;
}
//# sourceMappingURL=webviewPanel.js.map