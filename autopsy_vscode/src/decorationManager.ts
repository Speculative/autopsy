import * as vscode from 'vscode';
import { LogLocation } from './types';

/**
 * Manages inline decorations for histogram sparklines
 * Shows mini visualizations next to code lines that have histogram logs
 */
export class DecorationManager {
  private decorationType: vscode.TextEditorDecorationType;
  private logLocations: Map<string, LogLocation[]> = new Map();
  private outputChannel: vscode.OutputChannel;

  constructor(outputChannel: vscode.OutputChannel) {
    this.outputChannel = outputChannel;

    // Create decoration type for histogram sparklines
    this.decorationType = vscode.window.createTextEditorDecorationType({
      after: {
        margin: '0 0 0 2em',
        fontWeight: 'normal',
      },
      rangeBehavior: vscode.DecorationRangeBehavior.ClosedClosed,
    });
  }

  /**
   * Update log locations from autopsy data
   */
  updateLogLocations(locations: LogLocation[]) {
    this.outputChannel.appendLine(`DecorationManager: Updating ${locations.length} log locations`);

    // Group locations by filename
    this.logLocations.clear();
    for (const location of locations) {
      const existing = this.logLocations.get(location.filename) || [];
      existing.push(location);
      this.logLocations.set(location.filename, existing);
    }

    // Update all visible editors
    this.updateAllEditors();
  }

  /**
   * Update decorations in all visible editors
   */
  private updateAllEditors() {
    for (const editor of vscode.window.visibleTextEditors) {
      this.updateEditor(editor);
    }
  }

  /**
   * Update decorations for a specific editor
   */
  updateEditor(editor: vscode.TextEditor) {
    const filename = editor.document.uri.fsPath;
    const locations = this.logLocations.get(filename);

    if (!locations || locations.length === 0) {
      // Clear decorations if no logs for this file
      editor.setDecorations(this.decorationType, []);
      return;
    }

    const decorations: vscode.DecorationOptions[] = [];

    for (const location of locations) {
      // Only show decorations for histograms (which have sparklines)
      if (location.dashboardType !== 'hist' || !location.histogramValues || location.histogramValues.length === 0) {
        continue;
      }

      const lineIndex = location.line - 1; // VS Code uses 0-indexed lines

      // Ensure line is within document bounds
      if (lineIndex < 0 || lineIndex >= editor.document.lineCount) {
        continue;
      }

      const textLine = editor.document.lineAt(lineIndex);
      // Create range at the end of the line content
      const range = new vscode.Range(lineIndex, textLine.range.end.character, lineIndex, textLine.range.end.character);

      // Generate sparkline from histogram values
      const sparkline = this.generateSparkline(location.histogramValues);

      // Create decoration with sparkline and count
      const decoration: vscode.DecorationOptions = {
        range,
        renderOptions: {
          after: {
            contentText: ` { ${sparkline} n=${location.histogramValues.length} }`,
            color: new vscode.ThemeColor('editorCodeLens.foreground'),
          },
        },
        hoverMessage: this.createHoverMessage(location),
      };

      decorations.push(decoration);
    }

    editor.setDecorations(this.decorationType, decorations);
    this.outputChannel.appendLine(`DecorationManager: Applied ${decorations.length} decorations to ${filename}`);
  }

  /**
   * Generate a sparkline from histogram values showing distribution (PDF)
   * Uses Unicode block characters: ▁▂▃▄▅▆▇█
   */
  private generateSparkline(values: number[]): string {
    if (values.length === 0) {
      return '';
    }

    // Create histogram bins
    const numBins = 20;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min;

    if (range === 0) {
      // All values are the same
      return '█';
    }

    // Initialize bins
    const bins = new Array(numBins).fill(0);
    const binWidth = range / numBins;

    // Count values in each bin
    for (const value of values) {
      const binIndex = Math.min(Math.floor((value - min) / binWidth), numBins - 1);
      bins[binIndex]++;
    }

    // Find max bin count for normalization
    const maxBinCount = Math.max(...bins);

    // Generate sparkline
    const blocks = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█'];

    return bins.map(count => {
      if (count === 0) {
        return '▁';  // Empty bins show as lowest bar
      }
      const normalized = count / maxBinCount;
      const index = Math.floor(normalized * (blocks.length - 1));
      return blocks[index];
    }).join('');
  }

  /**
   * Create hover message with histogram statistics
   */
  private createHoverMessage(location: LogLocation): vscode.MarkdownString {
    const md = new vscode.MarkdownString();
    md.supportHtml = true;
    md.isTrusted = true;

    if (location.histogramValues && location.histogramValues.length > 0) {
      const values = location.histogramValues;
      const min = Math.min(...values);
      const max = Math.max(...values);
      const mean = values.reduce((a, b) => a + b, 0) / values.length;

      md.appendMarkdown(`**Histogram Statistics**\n\n`);
      md.appendMarkdown(`- Count: ${values.length}\n`);
      md.appendMarkdown(`- Min: ${min.toFixed(2)}\n`);
      md.appendMarkdown(`- Max: ${max.toFixed(2)}\n`);
      md.appendMarkdown(`- Mean: ${mean.toFixed(2)}\n`);
      md.appendMarkdown(`\nClick the CodeLens above to view in Autopsy viewer.`);
    }

    return md;
  }

  /**
   * Clear all decorations
   */
  clear() {
    this.logLocations.clear();
    for (const editor of vscode.window.visibleTextEditors) {
      editor.setDecorations(this.decorationType, []);
    }
  }

  /**
   * Dispose of resources
   */
  dispose() {
    this.decorationType.dispose();
    this.clear();
  }
}
