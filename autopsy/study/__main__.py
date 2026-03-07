import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from simple_term_menu import TerminalMenu

DB_NAME = ".autopsy-study.db"
console = Console()


def find_db() -> Path:
    """Look for the study DB in the current directory or parents."""
    p = Path.cwd()
    while True:
        candidate = p / DB_NAME
        if candidate.exists():
            return candidate
        if p.parent == p:
            break
        p = p.parent
    # Default to cwd
    return Path.cwd() / DB_NAME


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    # Ensure tables exist (mirrors the extension schema)
    conn.executescript("""
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
    """)
    return conn


def time_ago(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h {minutes % 60}m ago"
        days = hours // 24
        return f"{days}d {hours % 24}h ago"
    except Exception:
        return "unknown"


def show_status(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT participant_id, task, condition FROM current_session WHERE id = 1").fetchone()
    if not row:
        console.print("[dim]No active session.[/dim]")
        return

    pid, task, condition = row["participant_id"], row["task"], row["condition"]

    stats = conn.execute(
        "SELECT COUNT(*) as count, MAX(timestamp) as latest FROM events WHERE participant_id = ? AND task = ? AND condition = ?",
        (pid, task, condition),
    ).fetchone()

    table = Table(title="Current Session", show_header=False)
    table.add_column("Key", style="bold")
    table.add_column("Value")
    table.add_row("Participant", pid)
    table.add_row("Task", task)
    table.add_row("Condition", condition)
    table.add_row("Events", str(stats["count"]))
    if stats["latest"]:
        table.add_row("Latest event", f"{stats['latest']}  ({time_ago(stats['latest'])})")
    else:
        table.add_row("Latest event", "none")
    console.print(table)


def set_session(conn: sqlite3.Connection) -> None:
    current = conn.execute("SELECT participant_id, task, condition FROM current_session WHERE id = 1").fetchone()
    default_pid = current["participant_id"] if current else ""

    pid = Prompt.ask("Participant ID", default=default_pid or None)
    if not pid:
        return

    tasks = ["gateway", "sensors"]
    task_idx = TerminalMenu(tasks, title="Task").show()
    if task_idx is None:
        return
    task = tasks[task_idx]

    conditions = ["breakpoint", "logger", "tracer"]
    cond_idx = TerminalMenu(conditions, title="Condition").show()
    if cond_idx is None:
        return
    condition = conditions[cond_idx]

    conn.execute(
        """INSERT INTO current_session (id, participant_id, task, condition, set_at)
           VALUES (1, ?, ?, ?, datetime('now'))
           ON CONFLICT(id) DO UPDATE SET
             participant_id = excluded.participant_id,
             task = excluded.task,
             condition = excluded.condition,
             set_at = excluded.set_at""",
        (pid, task, condition),
    )
    conn.commit()
    console.print(f"[green]Session set:[/green] {pid} | {task} | {condition}")


def clear_session(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT participant_id, task, condition FROM current_session WHERE id = 1").fetchone()
    if not row:
        console.print("[dim]No active session to clear.[/dim]")
        return
    conn.execute("DELETE FROM current_session WHERE id = 1")
    conn.commit()
    console.print(f"[yellow]Cleared session:[/yellow] {row['participant_id']} | {row['task']} | {row['condition']}")


def next_participant(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        """SELECT participant_id FROM events
           UNION SELECT participant_id FROM current_session
           ORDER BY participant_id"""
    ).fetchall()

    max_id = 20  # start at 21
    for r in row:
        try:
            val = int(r["participant_id"])
            if val > max_id:
                max_id = val
        except ValueError:
            pass

    console.print(f"Next participant ID: [bold green]{max_id + 1}[/bold green]")


def main() -> None:
    db_path = find_db()
    console.print(f"[dim]DB: {db_path}[/dim]\n")
    conn = get_connection(db_path)

    actions = [show_status, set_session, clear_session, next_participant]
    menu = TerminalMenu(
        ["Show status", "Set session", "Clear session", "Next participant ID", "Quit"],
        title="\nStudy Manager",
    )

    while True:
        idx = menu.show()
        if idx is None or idx == len(actions):
            break
        actions[idx](conn)

    conn.close()


if __name__ == "__main__":
    main()
