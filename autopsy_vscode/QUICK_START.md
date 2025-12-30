# Quick Start Guide

## First Time Setup

```bash
# 1. Build the webview
cd ../autopsy_html
npm install
npm run build:vscode

# 2. Build the extension
cd ../autopsy_vscode
npm install
npm run compile
```

## Testing the Extension

### Option A: Use Extension Development Host (F5)

1. **Open ONLY the autopsy_vscode folder in VS Code**
   ```bash
   cd /home/jtao/phd/projects/autopsy/autopsy_vscode
   code .
   ```

2. **Press F5** or go to Run and Debug (Ctrl/Cmd+Shift+D) and select "Run Extension"

3. **In the new window that opens:**
   - Press Cmd/Ctrl+Shift+P
   - Type "Autopsy: Open Viewer"
   - The viewer panel should appear

4. **Test with a Python app:**
   ```python
   # In your Python code
   from autopsy import log

   # Start live server (in a separate terminal)
   python -m autopsy.live_server

   # Then run your app with logging
   log("Hello from Python!")
   ```

### Option B: Install as VSIX

```bash
# In autopsy_vscode directory
npm install -g @vscode/vsce
vsce package

# This creates autopsy-viewer-0.0.1.vsix
# Then: Extensions → Install from VSIX
```

## Verifying It Works

1. ✅ Command appears in Command Palette: "Autopsy: Open Viewer"
2. ✅ Panel opens with "Autopsy Viewer" title
3. ✅ If webview is missing, you'll see an error with instructions
4. ✅ When Python app runs, logs stream into the viewer
5. ✅ Clicking `filename:line` opens that file in VS Code

## Common Issues

**"Command not found"**
- Extension isn't loaded - check you're in Extension Development Host window
- Run `npm run compile` to rebuild

**"Could not find webview.html"**
- Run `cd ../autopsy_html && npm run build:vscode`

**F5 doesn't work**
- Make sure you opened the `autopsy_vscode` folder specifically
- Check `.vscode/launch.json` exists
- Try closing VS Code and reopening just the autopsy_vscode folder

**Webview shows but doesn't connect**
- Make sure your Python app is running the live server
- Check it's on port 8765: `ws://localhost:8765/ws`
- Look for connection errors in VS Code Dev Tools (Help → Toggle Developer Tools)
