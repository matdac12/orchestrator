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
    status     TEXT NOT NULL DEFAULT 'queued',
    issue_ref  TEXT,
    branch     TEXT,
    worktree   TEXT,
    context    TEXT,
    plan_path  TEXT,
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

ACTIVE_STATUSES = ("queued", "discussing", "executing", "blocked")
TASK_STATUSES = ("queued", "discussing", "executing", "blocked",
                 "done", "merged")

# Allowed lifecycle transitions (self-transitions are always allowed).
# Active statuses move freely among themselves and forward; 'done' can
# only move forward to 'merged' or be reopened into executing/blocked
# for rework; 'merged' is terminal.
TRANSITIONS = {
    "queued": {"discussing", "executing", "blocked", "done", "merged"},
    "discussing": {"queued", "executing", "blocked", "done", "merged"},
    "executing": {"queued", "discussing", "blocked", "done", "merged"},
    "blocked": {"queued", "discussing", "executing", "done"},
    "done": {"executing", "blocked", "merged"},
    "merged": set(),
}


class InvalidTransition(Exception):
    pass


def check_transition(current, new, force=False):
    if force or new == current:
        return
    if new not in TRANSITIONS.get(current, set()):
        raise InvalidTransition(
            f"invalid transition '{current}' -> '{new}' "
            f"(allowed from '{current}': "
            f"{sorted(TRANSITIONS.get(current, set())) or 'none — terminal'}; "
            f"use --force to override)")


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


def add_task(conn, project, agent, title, issue_ref=None, branch=None,
             worktree=None, context=None, status="queued"):
    if status not in TASK_STATUSES:
        raise ValueError(
            f"invalid status '{status}', expected one of {TASK_STATUSES}")
    pid = require_project(conn, project)["id"]
    ts = now()

    def _do():
        cur = conn.execute(
            "INSERT INTO tasks (project_id, agent, title, status, issue_ref, "
            "branch, worktree, context, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (pid, agent, title, status, issue_ref, branch, worktree,
             context, ts, ts),
        )
        conn.commit()
        return cur.lastrowid

    return with_retry(_do)


def update_task(conn, task_id, status=None, branch=None, issue_ref=None,
                plan_path=None, context=None, force=False):
    if status is not None and status not in TASK_STATUSES:
        raise ValueError(
            f"invalid status '{status}', expected one of {TASK_STATUSES}")
    row = conn.execute(
        "SELECT id, status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise NotFound(f"task {task_id} not found")
    if status is not None:
        check_transition(row["status"], status, force=force)

    sets, params = [], []
    if status is not None:
        sets.append("status = ?"); params.append(status)
    if branch is not None:
        sets.append("branch = ?"); params.append(branch)
    if issue_ref is not None:
        sets.append("issue_ref = ?"); params.append(issue_ref)
    if plan_path is not None:
        sets.append("plan_path = ?"); params.append(plan_path)
    if context is not None:
        sets.append("context = ?"); params.append(context)
    sets.append("updated_at = ?"); params.append(now())
    params.append(task_id)

    def _do():
        conn.execute(
            f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()

    with_retry(_do)


def _active_tasks(conn, project_id, agent):
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    return conn.execute(
        f"SELECT * FROM tasks WHERE project_id = ? AND agent = ? "
        f"AND status IN ({placeholders}) ORDER BY updated_at DESC",
        (project_id, agent, *ACTIVE_STATUSES),
    ).fetchall()


def post_event(conn, project, agent, kind="status", message="",
               task_id=None, status=None, branch=None, force=False):
    if status is not None and status not in TASK_STATUSES:
        raise ValueError(
            f"invalid status '{status}', expected one of {TASK_STATUSES}")
    pid = require_project(conn, project)["id"]

    # Resolve target task when we need one (status/branch update) or when a
    # single active task exists to attach the event to.
    need_task = status is not None or branch is not None
    if task_id is None:
        active = _active_tasks(conn, pid, agent)
        if need_task:
            if len(active) == 0:
                raise NotFound(
                    f"agent '{agent}' has no active task in '{project}' "
                    f"to apply status/branch to; pass --task")
            if len(active) > 1:
                raise Ambiguous(
                    f"agent '{agent}' has {len(active)} active tasks; "
                    f"pass --task <id>")
            task_id = active[0]["id"]
        elif len(active) == 1:
            task_id = active[0]["id"]

    if status is not None and task_id is not None:
        cur_row = conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if cur_row is None:
            raise NotFound(f"task {task_id} not found")
        check_transition(cur_row["status"], status, force=force)

    ts = now()

    def _do():
        cur = conn.execute(
            "INSERT INTO events (project_id, task_id, agent, kind, message, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (pid, task_id, agent, kind, message, ts),
        )
        if need_task:
            sets, params = [], []
            if status is not None:
                sets.append("status = ?"); params.append(status)
            if branch is not None:
                sets.append("branch = ?"); params.append(branch)
            sets.append("updated_at = ?"); params.append(ts)
            params.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
        return cur.lastrowid

    return with_retry(_do)


def _row_to_dict(row):
    return dict(row) if row is not None else None


def get_state(conn, project, events_limit=50):
    proj = require_project(conn, project)
    pid = proj["id"]

    tasks = [dict(r) for r in conn.execute(
        "SELECT * FROM tasks WHERE project_id = ? ORDER BY updated_at DESC",
        (pid,))]
    events = [dict(r) for r in conn.execute(
        "SELECT * FROM events WHERE project_id = ? "
        "ORDER BY id DESC LIMIT ?", (pid, events_limit))]

    agents = []
    for agent in sorted({t["agent"] for t in tasks}
                        | {e["agent"] for e in events}):
        agent_tasks = [t for t in tasks if t["agent"] == agent]
        active = [t for t in agent_tasks if t["status"] in ACTIVE_STATUSES]
        current = active[0] if active else (
            agent_tasks[0] if agent_tasks else None)
        last_event = next((e for e in events if e["agent"] == agent), None)
        agents.append({
            "agent": agent,
            "status": current["status"] if current else "idle",
            "current_task": current,
            "last_event": last_event,
        })

    return {
        "project": dict(proj),
        "agents": agents,
        "tasks": tasks,
        "events": events,
    }


def next_task(conn, project, agent):
    pid = require_project(conn, project)["id"]
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    row = conn.execute(
        f"SELECT * FROM tasks WHERE project_id = ? AND agent = ? "
        f"AND status IN ({placeholders}) ORDER BY created_at, id LIMIT 1",
        (pid, agent, *ACTIVE_STATUSES),
    ).fetchone()
    return dict(row) if row else None


def claim_next(conn, project, agent):
    pid = require_project(conn, project)["id"]

    def _do():
        row = conn.execute(
            "SELECT id FROM tasks WHERE project_id = ? AND agent = ? "
            "AND status = 'queued' ORDER BY created_at, id LIMIT 1",
            (pid, agent),
        ).fetchone()
        if row is None:
            return None
        cur = conn.execute(
            "UPDATE tasks SET status = 'discussing', updated_at = ? "
            "WHERE id = ? AND status = 'queued'", (now(), row["id"]))
        conn.commit()
        if cur.rowcount == 0:
            return None
        return dict(conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (row["id"],)).fetchone())

    return with_retry(_do)


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
