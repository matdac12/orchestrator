import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path.home() / ".orchestrator" / "state.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id         INTEGER PRIMARY KEY,
    name       TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    notes      TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    agent      TEXT NOT NULL,
    title      TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'todo',
    issue_ref  TEXT,
    branch     TEXT,
    worktree   TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    task_id    INTEGER REFERENCES tasks(id),
    agent      TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT 'status',
    message    TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""

ACTIVE_STATUSES = ("todo", "in_progress", "blocked")
TASK_STATUSES = ("todo", "in_progress", "blocked", "done", "merged")


def default_db_path():
    return os.environ.get("ORCH_DB") or str(DEFAULT_DB)


def now():
    return datetime.now(timezone.utc).isoformat()


def with_retry(action, attempts=5, base_delay=0.05):
    for i in range(attempts):
        try:
            return action()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and i < attempts - 1:
                time.sleep(base_delay * (2 ** i))
                continue
            raise


class NotFound(Exception):
    pass


class Ambiguous(Exception):
    pass


def create_project(conn, name, notes=None):
    existing = get_project(conn, name)
    if existing:
        return existing["id"], False

    def _do():
        cur = conn.execute(
            "INSERT INTO projects (name, created_at, notes) VALUES (?, ?, ?)",
            (name, now(), notes),
        )
        conn.commit()
        return cur.lastrowid

    return with_retry(_do), True


def get_project(conn, name):
    return conn.execute(
        "SELECT * FROM projects WHERE name = ?", (name,)
    ).fetchone()


def require_project(conn, name):
    row = get_project(conn, name)
    if row is None:
        raise NotFound(f"project '{name}' not found (run: orch init {name})")
    return row


def connect(db_path=None):
    path = db_path or default_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
