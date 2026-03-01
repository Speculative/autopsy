import Database from 'better-sqlite3';

export interface SessionInfo {
  participant_id: string;
  task: 'gateway' | 'sensors';
  condition: 'breakpoint' | 'logger' | 'tracer';
}

interface BatchEvent {
  eventType: string;
  source: 'vscode' | 'webview';
  timestamp: string;
  data?: Record<string, unknown>;
}

export class StudyLogger {
  private db: Database.Database | null = null;
  private insertStmt: Database.Statement | null = null;
  private getSessionStmt: Database.Statement | null = null;
  private countStmt: Database.Statement | null = null;

  /** Returns an error string on failure, undefined on success. */
  initialize(dbPath: string): string | undefined {
    try {
      this.db = new Database(dbPath);
      this.db.pragma('journal_mode = WAL');
      this.db.pragma('synchronous = NORMAL');

      this.db.exec(`
        CREATE TABLE IF NOT EXISTS current_session (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          participant_id TEXT NOT NULL,
          task TEXT NOT NULL CHECK (task IN ('gateway', 'sensors')),
          condition TEXT NOT NULL CHECK (condition IN ('breakpoint', 'logger', 'tracer')),
          set_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          participant_id TEXT NOT NULL,
          task TEXT NOT NULL,
          condition TEXT NOT NULL,
          timestamp TEXT NOT NULL,
          event_type TEXT NOT NULL,
          source TEXT NOT NULL,
          data TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_events_participant ON events(participant_id);
        CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_events_session ON events(participant_id, task, condition);
      `);

      this.insertStmt = this.db.prepare(`
        INSERT INTO events (participant_id, task, condition, timestamp, event_type, source, data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `);

      this.getSessionStmt = this.db.prepare(`
        SELECT participant_id, task, condition FROM current_session WHERE id = 1
      `);

      this.countStmt = this.db.prepare(`
        SELECT COUNT(*) as count FROM events
        WHERE participant_id = ? AND task = ? AND condition = ?
      `);
      return undefined;
    } catch (err) {
      this.db = null;
      return String(err);
    }
  }

  /** Always reads from DB — never cached. Facilitator can change externally at any time. */
  getCurrentSession(): SessionInfo | null {
    if (!this.db || !this.getSessionStmt) return null;
    try {
      const row = this.getSessionStmt.get() as SessionInfo | undefined;
      return row ?? null;
    } catch {
      return null;
    }
  }

  isActive(): boolean {
    return this.getCurrentSession() !== null;
  }

  /** Count events for the current session (for status bar display). */
  getEventCount(): number {
    if (!this.db || !this.countStmt) return 0;
    const session = this.getCurrentSession();
    if (!session) return 0;
    try {
      const row = this.countStmt.get(
        session.participant_id,
        session.task,
        session.condition
      ) as { count: number } | undefined;
      return row?.count ?? 0;
    } catch {
      return 0;
    }
  }

  /** Set the current session (called from the convenience VS Code command). */
  setSession(participant_id: string, task: 'gateway' | 'sensors', condition: 'breakpoint' | 'logger' | 'tracer'): void {
    if (!this.db) return;
    try {
      this.db.prepare(`
        INSERT INTO current_session (id, participant_id, task, condition, set_at)
        VALUES (1, ?, ?, ?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
          participant_id = excluded.participant_id,
          task = excluded.task,
          condition = excluded.condition,
          set_at = excluded.set_at
      `).run(participant_id, task, condition);
    } catch (err) {
      console.error('[StudyLogger] Failed to set session:', err);
    }
  }

  /** Clear the current session. */
  clearSession(): void {
    if (!this.db) return;
    try {
      this.db.prepare('DELETE FROM current_session WHERE id = 1').run();
    } catch (err) {
      console.error('[StudyLogger] Failed to clear session:', err);
    }
  }

  /** Log a single event. Reads session from DB every time. No-ops if no session. */
  logEvent(eventType: string, source: 'vscode' | 'webview', data?: Record<string, unknown>): void {
    const session = this.getCurrentSession();
    if (!session || !this.insertStmt) return;
    try {
      this.insertStmt.run(
        session.participant_id,
        session.task,
        session.condition,
        new Date().toISOString(),
        eventType,
        source,
        data !== undefined ? JSON.stringify(data) : null
      );
    } catch (err) {
      console.error('[StudyLogger] Failed to insert event:', err);
    }
  }

  /** Batch insert events in a single transaction. Reads session once per batch. */
  logEventBatch(events: BatchEvent[]): void {
    if (!this.db || !this.insertStmt || events.length === 0) return;
    const session = this.getCurrentSession();
    if (!session) return;
    try {
      const insertMany = this.db.transaction((evts: BatchEvent[]) => {
        for (const evt of evts) {
          this.insertStmt!.run(
            session.participant_id,
            session.task,
            session.condition,
            evt.timestamp,
            evt.eventType,
            evt.source,
            evt.data !== undefined ? JSON.stringify(evt.data) : null
          );
        }
      });
      insertMany(events);
    } catch (err) {
      console.error('[StudyLogger] Failed to insert event batch:', err);
    }
  }

  dispose(): void {
    try {
      this.db?.close();
    } catch {
      // ignore
    }
    this.db = null;
    this.insertStmt = null;
    this.getSessionStmt = null;
    this.countStmt = null;
  }
}
