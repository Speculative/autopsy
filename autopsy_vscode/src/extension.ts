import * as vscode from 'vscode';
import { AutopsyPanel } from './webviewPanel';
import { AutopsyCodeLensProvider } from './codeLensProvider';

// Create output channel for debugging
export const outputChannel = vscode.window.createOutputChannel('Autopsy Viewer');

export function activate(context: vscode.ExtensionContext) {
  outputChannel.appendLine('Autopsy Viewer extension activated');
  console.log('Autopsy Viewer extension activated');

  // Initialize CodeLens provider
  const codeLensProvider = new AutopsyCodeLensProvider(outputChannel);

  // Register CodeLens provider for Python files
  const codeLensDisposable = vscode.languages.registerCodeLensProvider(
    { language: 'python', scheme: 'file' },
    codeLensProvider
  );

  // Function to handle log data updates
  const handleLogDataUpdate = (locations: any[]) => {
    outputChannel.appendLine(`Extension: Received ${locations.length} log locations`);
    codeLensProvider.updateLogLocations(locations);
  };

  // Register command to open the Autopsy viewer
  const openViewerCmd = vscode.commands.registerCommand('autopsy.openViewer', () => {
    outputChannel.appendLine('Opening Autopsy Viewer...');
    outputChannel.show(true); // Show output channel (preserveFocus=true)
    try {
      AutopsyPanel.createOrShow(context.extensionUri, outputChannel, handleLogDataUpdate, codeLensProvider);
      outputChannel.appendLine('Autopsy Viewer panel created successfully');
    } catch (error) {
      outputChannel.appendLine(`Error creating panel: ${error}`);
      vscode.window.showErrorMessage(`Failed to open Autopsy Viewer: ${error}`);
    }
  });

  // Register command to show a specific call site in the viewer
  const showCallSiteCmd = vscode.commands.registerCommand(
    'autopsy.showCallSite',
    (filename: string, line: number) => {
      outputChannel.appendLine(`Showing call site: ${filename}:${line}`);

      // Open the Autopsy viewer if not already open
      if (!AutopsyPanel.currentPanel) {
        vscode.commands.executeCommand('autopsy.openViewer');
      } else {
        AutopsyPanel.currentPanel.reveal();
      }

      // TODO: Send message to webview to scroll to and highlight the specific call site
      // This will require additional message passing to the webview
      vscode.window.showInformationMessage(
        `Viewing logs from ${filename}:${line} in Autopsy viewer`
      );
    }
  );

  // Register command to show output logs
  const showLogsCmd = vscode.commands.registerCommand('autopsy.showLogs', () => {
    outputChannel.show();
  });

  // Register navigation commands
  const navigateToPreviousLogCmd = vscode.commands.registerCommand(
    'autopsy.navigateToPreviousLog',
    () => {
      if (AutopsyPanel.currentPanel) {
        AutopsyPanel.currentPanel.navigateToPreviousLog();
      }
    }
  );

  const navigateToNextLogCmd = vscode.commands.registerCommand(
    'autopsy.navigateToNextLog',
    () => {
      if (AutopsyPanel.currentPanel) {
        AutopsyPanel.currentPanel.navigateToNextLog();
      }
    }
  );

  context.subscriptions.push(openViewerCmd);
  context.subscriptions.push(showCallSiteCmd);
  context.subscriptions.push(showLogsCmd);
  context.subscriptions.push(navigateToPreviousLogCmd);
  context.subscriptions.push(navigateToNextLogCmd);
  context.subscriptions.push(codeLensDisposable);
  context.subscriptions.push(outputChannel);
  context.subscriptions.push(codeLensProvider);
}

export function deactivate() {
  outputChannel.appendLine('Autopsy Viewer extension deactivated');
  console.log('Autopsy Viewer extension deactivated');
}
