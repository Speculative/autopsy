import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { AutopsyPanel } from './webviewPanel';
import { AutopsyCodeLensProvider } from './codeLensProvider';
import { StudyLogger } from './studyLogger';
import { registerStudySubscriptions } from './studySubscriptions';

// Create output channel for debugging
export const outputChannel = vscode.window.createOutputChannel('Autopsy Viewer');

export const studyLogger = new StudyLogger();

export function activate(context: vscode.ExtensionContext) {
  outputChannel.appendLine('Autopsy Viewer extension activated');
  console.log('Autopsy Viewer extension activated');

  // ── Study logger initialization ─────────────────────────────────────────
  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (workspaceFolders && workspaceFolders.length > 0) {
    const dbPath = path.join(workspaceFolders[0].uri.fsPath, '.autopsy-study.db');
    const initError = studyLogger.initialize(dbPath);
    if (initError) {
      outputChannel.appendLine(`Study logger FAILED to initialize at: ${dbPath}`);
      outputChannel.appendLine(`Error: ${initError}`);
      vscode.window.showWarningMessage(`Autopsy Study: DB init failed — ${initError}`);
    } else {
      outputChannel.appendLine(`Study logger initialized at: ${dbPath}`);
    }
  } else {
    outputChannel.appendLine('Study logger: no workspace folder, logging disabled');
  }

  // Register VS Code event subscriptions for study logging
  registerStudySubscriptions(context, studyLogger);

  // ── Status bar item (polls DB every 2s) ────────────────────────────────
  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBar.command = 'autopsy.studySetSession';
  statusBar.show();
  context.subscriptions.push(statusBar);

  function updateStatusBar() {
    const session = studyLogger.getCurrentSession();
    if (session) {
      const count = studyLogger.getEventCount();
      statusBar.text = `$(record) ${session.participant_id} | ${session.task} | ${session.condition} | ${count} events`;
      statusBar.tooltip = 'Autopsy Study: session active. Click to change session.';
    } else {
      statusBar.text = `$(circle-slash) Study: inactive`;
      statusBar.tooltip = 'Autopsy Study: no session. Click to set session.';
    }
  }

  updateStatusBar();
  const statusBarInterval = setInterval(updateStatusBar, 2000);
  context.subscriptions.push({ dispose: () => clearInterval(statusBarInterval) });

  // ── Study session management commands ──────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand('autopsy.studySetSession', async () => {
      const participantId = await vscode.window.showInputBox({
        prompt: 'Enter participant ID',
        placeHolder: 'e.g. P01',
        value: studyLogger.getCurrentSession()?.participant_id ?? '',
      });
      if (participantId === undefined) return; // cancelled

      const task = await vscode.window.showQuickPick(
        ['gateway', 'sensors'],
        { placeHolder: 'Select task', title: 'Study Task' }
      ) as 'gateway' | 'sensors' | undefined;
      if (!task) return;

      const condition = await vscode.window.showQuickPick(
        ['breakpoint', 'logger', 'tracer'],
        { placeHolder: 'Select condition', title: 'Study Condition' }
      ) as 'breakpoint' | 'logger' | 'tracer' | undefined;
      if (!condition) return;

      studyLogger.setSession(participantId, task, condition);
      studyLogger.logEvent('study.sessionSet', 'vscode', { participant_id: participantId, task, condition });
      updateStatusBar();
      vscode.window.showInformationMessage(`Study session set: ${participantId} | ${task} | ${condition}`);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('autopsy.studyClearSession', () => {
      studyLogger.logEvent('study.sessionCleared', 'vscode', {});
      studyLogger.clearSession();
      updateStatusBar();
      vscode.window.showInformationMessage('Study session cleared.');
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('autopsy.studyShowStatus', () => {
      const session = studyLogger.getCurrentSession();
      if (session) {
        const count = studyLogger.getEventCount();
        vscode.window.showInformationMessage(
          `Study session: ${session.participant_id} | ${session.task} | ${session.condition} | ${count} events logged`
        );
      } else {
        vscode.window.showInformationMessage('Study: no active session. Use "Autopsy Study: Set Session" to start.');
      }
    })
  );

  // ── Autopsy viewer ──────────────────────────────────────────────────────
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
    try {
      AutopsyPanel.createOrShow(context.extensionUri, outputChannel, handleLogDataUpdate, codeLensProvider, studyLogger);
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

  // Watch for autopsy_report.json in the workspace
  const jsonWatcher = vscode.workspace.createFileSystemWatcher('**/autopsy_report.json');

  const loadJsonReport = (uri: vscode.Uri) => {
    if (!AutopsyPanel.currentPanel) {
      return;
    }
    try {
      const content = fs.readFileSync(uri.fsPath, 'utf8');
      const data = JSON.parse(content);
      outputChannel.appendLine(`Loaded autopsy_report.json (${content.length} bytes)`);
      AutopsyPanel.currentPanel.loadJsonData(data);
    } catch (error) {
      outputChannel.appendLine(`Error loading autopsy_report.json: ${error}`);
    }
  };

  jsonWatcher.onDidCreate(loadJsonReport);
  jsonWatcher.onDidChange(loadJsonReport);

  context.subscriptions.push(openViewerCmd);
  context.subscriptions.push(showCallSiteCmd);
  context.subscriptions.push(showLogsCmd);
  context.subscriptions.push(navigateToPreviousLogCmd);
  context.subscriptions.push(navigateToNextLogCmd);
  context.subscriptions.push(codeLensDisposable);
  context.subscriptions.push(outputChannel);
  context.subscriptions.push(codeLensProvider);
  context.subscriptions.push(jsonWatcher);
}

export function deactivate() {
  outputChannel.appendLine('Autopsy Viewer extension deactivated');
  console.log('Autopsy Viewer extension deactivated');
  studyLogger.dispose();
}
