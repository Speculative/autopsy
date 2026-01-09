import * as vscode from 'vscode';
import { LogLocation } from './types';

/**
 * Provides CodeLens for log locations
 * Shows clickable "View logs in Autopsy" links above lines with logs
 */
export class AutopsyCodeLensProvider implements vscode.CodeLensProvider {
  private logLocations: Map<string, LogLocation[]> = new Map();
  private _onDidChangeCodeLenses = new vscode.EventEmitter<void>();
  public readonly onDidChangeCodeLenses = this._onDidChangeCodeLenses.event;
  private outputChannel: vscode.OutputChannel;

  constructor(outputChannel: vscode.OutputChannel) {
    this.outputChannel = outputChannel;
  }

  /**
   * Update log locations from autopsy data
   */
  updateLogLocations(locations: LogLocation[]) {
    this.outputChannel.appendLine(`CodeLensProvider: Updating ${locations.length} log locations`);

    // Group locations by filename
    this.logLocations.clear();
    for (const location of locations) {
      const existing = this.logLocations.get(location.filename) || [];
      existing.push(location);
      this.logLocations.set(location.filename, existing);
    }

    // Notify VS Code to refresh CodeLens
    this._onDidChangeCodeLenses.fire();
  }

  /**
   * Provide CodeLens for a document
   */
  provideCodeLenses(
    document: vscode.TextDocument,
    token: vscode.CancellationToken
  ): vscode.CodeLens[] | Thenable<vscode.CodeLens[]> {
    const filename = document.uri.fsPath;
    const locations = this.logLocations.get(filename);

    if (!locations || locations.length === 0) {
      return [];
    }

    const codeLenses: vscode.CodeLens[] = [];

    for (const location of locations) {
      const line = location.line - 1; // VS Code uses 0-indexed lines

      // Ensure line is within document bounds
      if (line < 0 || line >= document.lineCount) {
        continue;
      }

      const range = new vscode.Range(line, 0, line, 0);

      // Create appropriate CodeLens based on log type
      const codeLens = this.createCodeLens(location, range);
      if (codeLens) {
        codeLenses.push(codeLens);
      }
    }

    this.outputChannel.appendLine(`CodeLensProvider: Provided ${codeLenses.length} CodeLens for ${filename}`);
    return codeLenses;
  }

  /**
   * Create CodeLens for a log location
   */
  private createCodeLens(location: LogLocation, range: vscode.Range): vscode.CodeLens | null {
    let title: string;
    let tooltip: string;

    if (location.isDashboard) {
      // Dashboard call sites
      switch (location.dashboardType) {
        case 'count':
          const countTotal = location.countTotal || 0;
          title = `$(graph) View count (${countTotal} total)`;
          tooltip = `View count dashboard in Autopsy viewer - ${countTotal} total occurrences`;
          break;
        case 'hist':
          const histCount = location.histogramValues?.length || location.logCount;
          title = `$(graph-line) View histogram (n=${histCount})`;
          tooltip = `View histogram in Autopsy viewer - ${histCount} values`;
          break;
        case 'timeline':
          const timelineCount = location.timelineEventCount || location.logCount;
          title = `$(timeline-view-icon) View timeline (${timelineCount} events)`;
          tooltip = `View timeline in Autopsy viewer - ${timelineCount} events`;
          break;
        case 'happened':
          const happenedCount = location.happenedCount || location.logCount;
          title = `$(check) View happened (${happenedCount}×)`;
          tooltip = `View happened events in Autopsy viewer - occurred ${happenedCount} times`;
          break;
        default:
          title = `$(eye) View logs (${location.logCount})`;
          tooltip = 'View logs in Autopsy viewer';
      }
    } else {
      // Regular log() call sites
      const plural = location.logCount === 1 ? 'log' : 'logs';
      title = `$(eye) View ${location.logCount} ${plural} in Autopsy`;
      tooltip = `View ${location.logCount} log entries in Autopsy viewer`;
    }

    return new vscode.CodeLens(range, {
      title,
      tooltip,
      command: 'autopsy.showCallSite',
      arguments: [location.filename, location.line],
    });
  }

  /**
   * Clear all log locations
   */
  clear() {
    this.logLocations.clear();
    this._onDidChangeCodeLenses.fire();
  }

  /**
   * Dispose of resources
   */
  dispose() {
    this._onDidChangeCodeLenses.dispose();
    this.clear();
  }
}
