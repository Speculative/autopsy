# Autopsy Viewer - VS Code Extension

Live debugging visualization for Python autopsy logs within VS Code.

## Features

- **Live Mode**: Automatically connects to autopsy server (default: `ws://localhost:8765/ws`)
- **Click-to-Navigate**: Click on code locations in logs to jump to the file and line in VS Code
- **Webview Panel**: View autopsy logs in a dedicated panel within VS Code
- **Real-time Updates**: Stream logs from your running Python application

## Installation

### From Source

1. Build the webview:
   ```bash
   cd ../autopsy_html
   npm install
   npm run build:vscode
   ```

2. Build the extension:
   ```bash
   cd ../autopsy_vscode
   npm install
   npm run compile
   ```

3. Install the extension:
   - Open VS Code
   - Press F5 to launch the Extension Development Host
   - Or package with `vsce package` and install the `.vsix` file

## Usage

1. Start your Python application with autopsy logging
2. In VS Code, open the Command Palette (Cmd/Ctrl+Shift+P)
3. Run command: `Autopsy: Open Viewer`
4. The viewer will automatically connect to `ws://localhost:8765/ws`
5. Click on any code location to navigate to that file/line

## Testing During Development

### Method 1: Using F5 (Recommended)

1. Open the `autopsy_vscode` folder in VS Code (must be the root folder)
2. Ensure the extension is compiled: `npm run compile`
3. Press **F5** - this will:
   - Launch a new VS Code window (Extension Development Host)
   - Your extension will be loaded in that window
4. In the new window, press Cmd/Ctrl+Shift+P and run `Autopsy: Open Viewer`

### Method 2: Install Locally

1. Package the extension:
   ```bash
   npm install -g @vscode/vsce
   vsce package
   ```
2. Install the `.vsix` file:
   - Open VS Code
   - Go to Extensions view
   - Click "..." menu → "Install from VSIX"
   - Select the generated `.vsix` file

### Debugging

The extension creates an output channel called **"Autopsy Viewer"** that logs all activity.

**To view logs:**
1. Open the Output panel: View → Output (or Ctrl/Cmd+Shift+U)
2. Select "Autopsy Viewer" from the dropdown
3. Or run command: `Autopsy: Show Logs`

**What gets logged:**
- Extension activation/deactivation
- Panel creation events
- File opening attempts
- All console messages from the webview (console.log, console.error, etc.)
- WebSocket connection status
- Errors and warnings

### Troubleshooting

**Blank white screen:**
- Check the Output panel (select "Autopsy Viewer") for errors
- The webview HTML file might be missing - run `cd ../autopsy_html && npm run build:vscode`
- Look for "ERROR: Failed to read HTML file" in the output

**F5 doesn't show debug options:**
- Make sure you have the `autopsy_vscode` folder open (not the parent directory)
- Check that `out/extension.js` exists (run `npm run compile`)
- Look for the debug configurations in the Run and Debug panel (Ctrl/Cmd+Shift+D)

**Webview not connecting to Python:**
- Check the Output panel for WebSocket connection errors
- Verify your Python autopsy server is running on port 8765
- Look for "[Webview LOG]" or "[Webview ERROR]" messages in the output

## Development

### Building

```bash
# Watch mode for extension TypeScript
npm run watch

# Build webview
cd ../autopsy_html && npm run build:vscode
```

### Testing

Press F5 in VS Code to launch the Extension Development Host for testing.

## Requirements

- VS Code 1.85.0 or higher
- Python autopsy library with live mode server running

## Architecture

- Extension Host: TypeScript code that registers commands and manages webview
- Webview: Svelte app built with Vite, packaged as single HTML file
- Communication: postMessage API for webview ↔ extension

## File Structure

```
autopsy_vscode/
├── src/
│   ├── extension.ts        # Extension entry point
│   └── webviewPanel.ts     # Webview management
├── media/
│   └── webview.html        # Built Svelte app
├── out/                    # Compiled JavaScript
├── package.json
└── tsconfig.json
```
