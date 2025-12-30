import * as vscode from 'vscode';
import { AutopsyPanel } from './webviewPanel';

// Create output channel for debugging
export const outputChannel = vscode.window.createOutputChannel('Autopsy Viewer');

export function activate(context: vscode.ExtensionContext) {
  outputChannel.appendLine('Autopsy Viewer extension activated');
  console.log('Autopsy Viewer extension activated');

  // Register command to open the Autopsy viewer
  const openViewerCmd = vscode.commands.registerCommand('autopsy.openViewer', () => {
    outputChannel.appendLine('Opening Autopsy Viewer...');
    outputChannel.show(true); // Show output channel (preserveFocus=true)
    try {
      AutopsyPanel.createOrShow(context.extensionUri, outputChannel);
      outputChannel.appendLine('Autopsy Viewer panel created successfully');
    } catch (error) {
      outputChannel.appendLine(`Error creating panel: ${error}`);
      vscode.window.showErrorMessage(`Failed to open Autopsy Viewer: ${error}`);
    }
  });

  // Register command to show output logs
  const showLogsCmd = vscode.commands.registerCommand('autopsy.showLogs', () => {
    outputChannel.show();
  });

  context.subscriptions.push(openViewerCmd);
  context.subscriptions.push(showLogsCmd);
  context.subscriptions.push(outputChannel);
}

export function deactivate() {
  outputChannel.appendLine('Autopsy Viewer extension deactivated');
  console.log('Autopsy Viewer extension deactivated');
}
