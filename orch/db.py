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
