import * as vscode from 'vscode';
import * as path from 'path';
import { StudyLogger } from './studyLogger';

/** Returns just the basename to avoid logging full absolute paths. */
function shortName(fileName: string): string {
  return path.basename(fileName);
}

/** Returns true only if the file is inside one of the workspace folders. */
function isWorkspaceFile(uri: vscode.Uri): boolean {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders) return false;
  return folders.some((f) => uri.fsPath.startsWith(f.uri.fsPath));
}

/** Creates a debounced version of a logger call. The last invocation within `delayMs` wins. */
function debounce<T>(fn: (arg: T) => void, delayMs: number): (arg: T) => void {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let pending: T;
  return (arg: T) => {
    pending = arg;
    if (timer === null) {
      timer = setTimeout(() => {
        fn(pending);
        timer = null;
      }, delayMs);
    }
  };
}

/** DAP commands/events we care about. */
const DAP_STEP_COMMANDS = new Set(['next', 'stepIn', 'stepOut', 'continue', 'stepBack', 'reverseContinue']);
const DAP_INSPECT_COMMANDS = new Set(['variables', 'evaluate']);
const DAP_STOPPED_EVENT = 'stopped';

export function registerStudySubscriptions(
  context: vscode.ExtensionContext,
  logger: StudyLogger
): void {
  // ── Editor: file open/close/save ──────────────────────────────────────────
  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument((doc) => {
      if (doc.uri.scheme !== 'file') return;
      if (!isWorkspaceFile(doc.uri)) return;
      logger.logEvent('editor.fileOpen', 'vscode', {
        fileName: shortName(doc.fileName),
        languageId: doc.languageId,
      });
    })
  );

  context.subscriptions.push(
    vscode.workspace.onDidCloseTextDocument((doc) => {
      if (doc.uri.scheme !== 'file') return;
      if (!isWorkspaceFile(doc.uri)) return;
      logger.logEvent('editor.fileClose', 'vscode', {
        fileName: shortName(doc.fileName),
      });
    })
  );

  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument((doc) => {
      if (doc.uri.scheme !== 'file') return;
      if (!isWorkspaceFile(doc.uri)) return;
      logger.logEvent('editor.fileSave', 'vscode', {
        fileName: shortName(doc.fileName),
      });
    })
  );

  // ── Editor: active editor change ──────────────────────────────────────────
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (editor) {
        logger.logEvent('editor.activeChange', 'vscode', {
          fileName: shortName(editor.document.fileName),
          languageId: editor.document.languageId,
        });
      } else {
        logger.logEvent('editor.activeChange', 'vscode', null as any);
      }
    })
  );

  // ── Editor: selection change (debounced 750ms) ────────────────────────────
  const logSelectionChange = debounce((e: vscode.TextEditorSelectionChangeEvent) => {
    logger.logEvent('editor.selectionChange', 'vscode', {
      fileName: shortName(e.textEditor.document.fileName),
      kind: e.kind != null ? vscode.TextEditorSelectionChangeKind[e.kind] : undefined,
      selectionCount: e.selections.length,
    });
  }, 750);

  context.subscriptions.push(
    vscode.window.onDidChangeTextEditorSelection((e) => {
      if (e.textEditor.document.uri.scheme !== 'file') return;
      logSelectionChange(e);
    })
  );

  // ── Editor: scroll (debounced 750ms) ─────────────────────────────────────
  const logScroll = debounce((e: vscode.TextEditorVisibleRangesChangeEvent) => {
    const ranges = e.visibleRanges;
    if (ranges.length === 0) return;
    logger.logEvent('editor.scroll', 'vscode', {
      fileName: shortName(e.textEditor.document.fileName),
      startLine: ranges[0].start.line + 1,
      endLine: ranges[ranges.length - 1].end.line + 1,
    });
  }, 750);

  context.subscriptions.push(
    vscode.window.onDidChangeTextEditorVisibleRanges((e) => {
      if (e.textEditor.document.uri.scheme !== 'file') return;
      logScroll(e);
    })
  );

  // ── Editor: text change (debounced 1000ms, aggregate changeCount) ─────────
  const pendingChanges = new Map<string, number>();
  let textChangeTimer: ReturnType<typeof setTimeout> | null = null;

  context.subscriptions.push(
    vscode.workspace.onDidChangeTextDocument((e) => {
      if (e.document.uri.scheme !== 'file' || e.contentChanges.length === 0) return;
      const key = e.document.fileName;
      pendingChanges.set(key, (pendingChanges.get(key) ?? 0) + e.contentChanges.length);
      if (textChangeTimer === null) {
        textChangeTimer = setTimeout(() => {
          textChangeTimer = null;
          for (const [fileName, changeCount] of pendingChanges.entries()) {
            logger.logEvent('editor.textChange', 'vscode', {
              fileName: shortName(fileName),
              changeCount,
            });
          }
          pendingChanges.clear();
        }, 1000);
      }
    })
  );

  // ── Terminal ──────────────────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.window.onDidOpenTerminal((terminal) => {
      logger.logEvent('terminal.created', 'vscode', { name: terminal.name });
    })
  );

  context.subscriptions.push(
    vscode.window.onDidCloseTerminal((terminal) => {
      logger.logEvent('terminal.closed', 'vscode', {
        name: terminal.name,
        exitStatus: terminal.exitStatus?.code ?? null,
      });
    })
  );

  context.subscriptions.push(
    vscode.window.onDidChangeActiveTerminal((terminal) => {
      logger.logEvent('terminal.activeChange', 'vscode',
        terminal ? { name: terminal.name } : null as any
      );
    })
  );

  // Shell execution APIs (VS Code 1.93+; graceful skip if unavailable)
  if ('onDidStartTerminalShellExecution' in vscode.window) {
    context.subscriptions.push(
      (vscode.window as any).onDidStartTerminalShellExecution((e: any) => {
        logger.logEvent('terminal.shellExecStart', 'vscode', {
          command: e.execution?.commandLine?.value ?? null,
          cwd: e.execution?.cwd?.fsPath ?? null,
        });
      })
    );
    context.subscriptions.push(
      (vscode.window as any).onDidEndTerminalShellExecution((e: any) => {
        logger.logEvent('terminal.shellExecEnd', 'vscode', {
          command: e.execution?.commandLine?.value ?? null,
          exitCode: e.exitCode ?? null,
        });
      })
    );
  }

  // ── Debugger ──────────────────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.debug.onDidStartDebugSession((session) => {
      logger.logEvent('debug.sessionStart', 'vscode', {
        name: session.name,
        type: session.type,
      });
    })
  );

  context.subscriptions.push(
    vscode.debug.onDidTerminateDebugSession((session) => {
      logger.logEvent('debug.sessionEnd', 'vscode', {
        name: session.name,
        type: session.type,
      });
    })
  );

  context.subscriptions.push(
    vscode.debug.onDidChangeBreakpoints((e) => {
      if (e.added.length === 0 && e.removed.length === 0 && e.changed.length === 0) return;
      logger.logEvent('debug.breakpointChange', 'vscode', {
        added: e.added.length,
        removed: e.removed.length,
        changed: e.changed.length,
      });
    })
  );

  // DAP tracker — intercept key messages passively
  context.subscriptions.push(
    vscode.debug.registerDebugAdapterTrackerFactory('*', {
      createDebugAdapterTracker(_session: vscode.DebugSession) {
        return {
          onWillReceiveMessage(message: any) {
            // Client→adapter: step commands, evaluate
            if (message.type !== 'request') return;
            if (DAP_STEP_COMMANDS.has(message.command)) {
              logger.logEvent('debug.dapMessage', 'vscode', {
                direction: 'request',
                command: message.command,
              });
            } else if (message.command === 'evaluate') {
              logger.logEvent('debug.dapMessage', 'vscode', {
                direction: 'request',
                command: 'evaluate',
                context: message.arguments?.context ?? null,
              });
            } else if (message.command === 'variables') {
              logger.logEvent('debug.dapMessage', 'vscode', {
                direction: 'request',
                command: 'variables',
              });
            }
          },
          onDidSendMessage(message: any) {
            // Adapter→client: stopped events
            if (message.type !== 'event') return;
            if (message.event === DAP_STOPPED_EVENT) {
              logger.logEvent('debug.dapMessage', 'vscode', {
                direction: 'event',
                event: 'stopped',
                reason: message.body?.reason ?? null,
              });
            }
          },
        };
      },
    })
  );
}
