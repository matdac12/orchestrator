# Orchestrator Communication Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `orch`, a Python-stdlib CLI + on-demand web dashboard backed by one global SQLite DB, so worker agents record progress and the orchestrator reads live state.

**Architecture:** A `orch/` package with a focused data layer (`db.py`), a CLI (`cli.py`), and an HTTP dashboard (`server.py` + `dashboard.py`). One global SQLite DB at `~/.orchestrator/state.db` in WAL mode, keyed by `--project`. A root `orch.py` shim makes it runnable from any directory via `python <path>/orch.py ...`. A project-level `/orchestrating` skill drives the workflow.

**Tech Stack:** Python 3 standard library only — `sqlite3`, `argparse`, `http.server`, `json`, `datetime`, `unittest`. No pip installs.

---

## File Structure

- `orch/__init__.py` — package marker + version
- `orch/db.py` — data layer: connection, schema, retry, project/task/event CRUD, `get_state`
- `orch/cli.py` — argparse CLI, command handlers, `main()`
- `orch/server.py` — `http.server` handler: `GET /` and `GET /api/state`; `serve()`
- `orch/dashboard.py` — the dashboard HTML as a string (keeps `server.py` focused)
- `orch.py` — root shim: path setup → `cli.main()`
- `tests/test_db.py` — data layer tests
- `tests/test_cli.py` — CLI smoke tests via `subprocess`
- `tests/test_server.py` — `/api/state` JSON test
- `.claude/skills/orchestrating/SKILL.md` — the orchestrator workflow skill
- `README.md` — usage (modify existing)

All DB functions accept an explicit `db_path`; `default_db_path()` reads env `ORCH_DB`, falling back to `~/.orchestrator/state.db`. Tests pass a temp path so they never touch the real DB.

---

### Task 1: Package scaffold + DB connection & schema

**Files:**
- Create: `orch/__init__.py`
- Create: `orch/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db.py
import os
import sqlite3
import tempfile
import unittest

from orch import db


class DBSetupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "state.db")

    def test_default_db_path_uses_env(self):
        os.environ["ORCH_DB"] = "/custom/x.db"
        try:
            self.assertEqual(db.default_db_path(), "/custom/x.db")
        finally:
            del os.environ["ORCH_DB"]

    def test_connect_creates_schema_and_wal(self):
        conn = db.connect(self.path)
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual({"projects", "tasks", "events"}, names)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual("wal", mode.lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py -q` (or `python -m unittest tests.test_db -v`)
Expected: FAIL — `ModuleNotFoundError: No module named 'orch'` / `AttributeError`.

- [ ] **Step 3: Write minimal implementation**

```python
# orch/__init__.py
__version__ = "0.1.0"
```

```python
# orch/db.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add orch/__init__.py orch/db.py tests/test_db.py
git commit -m "feat: db connection and schema in WAL mode"
```

---

### Task 2: Retry-on-locked helper

**Files:**
- Modify: `orch/db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_db.py
class RetryTest(unittest.TestCase):
    def test_with_retry_recovers_from_locked(self):
        calls = {"n": 0}

        def action():
            calls["n"] += 1
            if calls["n"] < 3:
                raise sqlite3.OperationalError("database is locked")
            return "ok"

        self.assertEqual(db.with_retry(action, base_delay=0.0), "ok")
        self.assertEqual(calls["n"], 3)

    def test_with_retry_reraises_other_errors(self):
        def action():
            raise sqlite3.OperationalError("no such table")

        with self.assertRaises(sqlite3.OperationalError):
            db.with_retry(action, base_delay=0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py::RetryTest -q`
Expected: FAIL — `AttributeError: module 'orch.db' has no attribute 'with_retry'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to orch/db.py (after now())
def with_retry(action, attempts=5, base_delay=0.05):
    for i in range(attempts):
        try:
            return action()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and i < attempts - 1:
                time.sleep(base_delay * (2 ** i))
                continue
            raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py::RetryTest -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add orch/db.py tests/test_db.py
git commit -m "feat: with_retry helper for locked-db backoff"
```

---

### Task 3: Project create/get

**Files:**
- Modify: `orch/db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_db.py
class ProjectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))

    def test_create_is_get_or_create(self):
        pid1, created1 = db.create_project(self.conn, "demo", notes="hi")
        pid2, created2 = db.create_project(self.conn, "demo")
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(pid1, pid2)

    def test_get_project_returns_none_when_missing(self):
        self.assertIsNone(db.get_project(self.conn, "nope"))
        db.create_project(self.conn, "demo")
        row = db.get_project(self.conn, "demo")
        self.assertEqual(row["name"], "demo")

    def test_require_project_raises_when_missing(self):
        with self.assertRaises(db.NotFound):
            db.require_project(self.conn, "nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py::ProjectTest -q`
Expected: FAIL — `AttributeError: ... 'create_project'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to orch/db.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py::ProjectTest -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add orch/db.py tests/test_db.py
git commit -m "feat: project get-or-create and require_project"
```

---

### Task 4: Task add/update

**Files:**
- Modify: `orch/db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_db.py
class TaskTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")

    def test_add_task_returns_id_and_defaults_todo(self):
        tid = db.add_task(self.conn, "demo", "B", "build X", issue_ref="LIN-1")
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()
        self.assertEqual(row["status"], "todo")
        self.assertEqual(row["agent"], "B")
        self.assertEqual(row["issue_ref"], "LIN-1")

    def test_update_task_changes_fields_and_touches_updated_at(self):
        tid = db.add_task(self.conn, "demo", "B", "build X")
        before = self.conn.execute(
            "SELECT updated_at FROM tasks WHERE id=?", (tid,)).fetchone()[0]
        db.update_task(self.conn, tid, status="merged", branch="feat/x")
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        self.assertEqual(row["status"], "merged")
        self.assertEqual(row["branch"], "feat/x")
        self.assertNotEqual(row["updated_at"], before)

    def test_update_task_rejects_bad_status(self):
        tid = db.add_task(self.conn, "demo", "B", "build X")
        with self.assertRaises(ValueError):
            db.update_task(self.conn, tid, status="nonsense")

    def test_update_task_missing_id_raises(self):
        with self.assertRaises(db.NotFound):
            db.update_task(self.conn, 999, status="done")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py::TaskTest -q`
Expected: FAIL — `AttributeError: ... 'add_task'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to orch/db.py
def add_task(conn, project, agent, title,
             issue_ref=None, branch=None, worktree=None):
    pid = require_project(conn, project)["id"]
    ts = now()

    def _do():
        cur = conn.execute(
            "INSERT INTO tasks (project_id, agent, title, status, issue_ref, "
            "branch, worktree, created_at, updated_at) "
            "VALUES (?, ?, ?, 'todo', ?, ?, ?, ?, ?)",
            (pid, agent, title, issue_ref, branch, worktree, ts, ts),
        )
        conn.commit()
        return cur.lastrowid

    return with_retry(_do)


def update_task(conn, task_id, status=None, branch=None, issue_ref=None):
    if status is not None and status not in TASK_STATUSES:
        raise ValueError(
            f"invalid status '{status}', expected one of {TASK_STATUSES}")
    row = conn.execute(
        "SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise NotFound(f"task {task_id} not found")

    sets, params = [], []
    if status is not None:
        sets.append("status = ?"); params.append(status)
    if branch is not None:
        sets.append("branch = ?"); params.append(branch)
    if issue_ref is not None:
        sets.append("issue_ref = ?"); params.append(issue_ref)
    sets.append("updated_at = ?"); params.append(now())
    params.append(task_id)

    def _do():
        conn.execute(
            f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()

    with_retry(_do)
```

Note: `update_task` always advances `updated_at`; tests run fast, but `now()` is microsecond-precision ISO so consecutive calls differ. If a flake ever appears, add `time.sleep(0.001)` in the test before the update.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py::TaskTest -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add orch/db.py tests/test_db.py
git commit -m "feat: add_task and update_task with validation"
```

---

### Task 5: Post event (with task auto-targeting & side effects)

**Files:**
- Modify: `orch/db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_db.py
class PostTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")

    def test_post_appends_event(self):
        tid = db.add_task(self.conn, "demo", "B", "build X")
        eid = db.post_event(self.conn, "demo", "B", kind="note",
                            message="hi", task_id=tid)
        row = self.conn.execute(
            "SELECT * FROM events WHERE id=?", (eid,)).fetchone()
        self.assertEqual(row["message"], "hi")
        self.assertEqual(row["kind"], "note")
        self.assertEqual(row["task_id"], tid)

    def test_post_with_status_updates_linked_task(self):
        tid = db.add_task(self.conn, "demo", "B", "build X")
        db.post_event(self.conn, "demo", "B", status="done",
                     branch="feat/x", message="ready")
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["branch"], "feat/x")

    def test_post_auto_targets_single_active_task(self):
        tid = db.add_task(self.conn, "demo", "B", "build X")
        eid = db.post_event(self.conn, "demo", "B", message="working")
        row = self.conn.execute(
            "SELECT task_id FROM events WHERE id=?", (eid,)).fetchone()
        self.assertEqual(row["task_id"], tid)

    def test_post_ambiguous_active_tasks_without_status(self):
        db.add_task(self.conn, "demo", "B", "task1")
        db.add_task(self.conn, "demo", "B", "task2")
        # ambiguous only matters when we must pick a task to update;
        # a plain note with no task and no status is allowed (task_id None)
        eid = db.post_event(self.conn, "demo", "B", message="generic")
        row = self.conn.execute(
            "SELECT task_id FROM events WHERE id=?", (eid,)).fetchone()
        self.assertIsNone(row["task_id"])

    def test_post_status_ambiguous_raises(self):
        db.add_task(self.conn, "demo", "B", "task1")
        db.add_task(self.conn, "demo", "B", "task2")
        with self.assertRaises(db.Ambiguous):
            db.post_event(self.conn, "demo", "B", status="done")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py::PostTest -q`
Expected: FAIL — `AttributeError: ... 'post_event'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to orch/db.py
def _active_tasks(conn, project_id, agent):
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    return conn.execute(
        f"SELECT * FROM tasks WHERE project_id = ? AND agent = ? "
        f"AND status IN ({placeholders}) ORDER BY updated_at DESC",
        (project_id, agent, *ACTIVE_STATUSES),
    ).fetchall()


def post_event(conn, project, agent, kind="status", message="",
               task_id=None, status=None, branch=None):
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py::PostTest -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add orch/db.py tests/test_db.py
git commit -m "feat: post_event with task auto-targeting and side effects"
```

---

### Task 6: get_state aggregation

**Files:**
- Modify: `orch/db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_db.py
class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")

    def test_get_state_shape(self):
        tid = db.add_task(self.conn, "demo", "B", "build X")
        db.post_event(self.conn, "demo", "B", status="in_progress",
                     message="starting")
        state = db.get_state(self.conn, "demo")
        self.assertEqual(state["project"]["name"], "demo")
        self.assertEqual(len(state["tasks"]), 1)
        self.assertEqual(len(state["events"]), 1)
        agents = {a["agent"]: a for a in state["agents"]}
        self.assertIn("B", agents)
        self.assertEqual(agents["B"]["status"], "in_progress")
        self.assertEqual(agents["B"]["current_task"]["id"], tid)
        self.assertEqual(agents["B"]["last_event"]["message"], "starting")

    def test_get_state_idle_agent_when_all_tasks_closed(self):
        db.add_task(self.conn, "demo", "B", "build X")
        db.post_event(self.conn, "demo", "B", status="merged")
        agents = {a["agent"]: a
                  for a in db.get_state(self.conn, "demo")["agents"]}
        self.assertEqual(agents["B"]["status"], "merged")

    def test_get_state_events_limit(self):
        for i in range(10):
            db.post_event(self.conn, "demo", "B", message=f"e{i}")
        state = db.get_state(self.conn, "demo", events_limit=3)
        self.assertEqual(len(state["events"]), 3)
        self.assertEqual(state["events"][0]["message"], "e9")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py::StateTest -q`
Expected: FAIL — `AttributeError: ... 'get_state'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to orch/db.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py::StateTest -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add orch/db.py tests/test_db.py
git commit -m "feat: get_state aggregation for status and dashboard"
```

---

### Task 7: CLI wiring (init, task add/update, status, log) + root shim

**Files:**
- Create: `orch/cli.py`
- Create: `orch.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(args, db_path):
    env = dict(os.environ, ORCH_DB=db_path)
    return subprocess.run(
        [sys.executable, os.path.join(ROOT, "orch.py"), *args],
        capture_output=True, text=True, env=env)


class CLITest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "state.db")

    def test_init_then_status_json(self):
        self.assertEqual(run(["init", "demo"], self.db).returncode, 0)
        out = run(["status", "--project", "demo", "--json"], self.db)
        self.assertEqual(out.returncode, 0)
        state = json.loads(out.stdout)
        self.assertEqual(state["project"]["name"], "demo")

    def test_task_add_prints_id_and_status_shows_it(self):
        run(["init", "demo"], self.db)
        add = run(["task", "add", "--project", "demo", "--agent", "B",
                   "--title", "build X", "--issue", "LIN-1"], self.db)
        self.assertEqual(add.returncode, 0)
        tid = int(add.stdout.strip().split()[-1])
        upd = run(["task", "update", "--project", "demo", "--task", str(tid),
                   "--status", "merged"], self.db)
        self.assertEqual(upd.returncode, 0)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["status"], "merged")

    def test_status_unknown_project_errors(self):
        out = run(["status", "--project", "nope", "--json"], self.db)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("not found", out.stderr.lower())

    def test_log_outputs_events(self):
        run(["init", "demo"], self.db)
        run(["task", "add", "--project", "demo", "--agent", "B",
             "--title", "X"], self.db)
        run(["post", "--project", "demo", "--agent", "B",
             "--msg", "hello"], self.db)
        out = run(["log", "--project", "demo"], self.db)
        self.assertEqual(out.returncode, 0)
        self.assertIn("hello", out.stdout)


if __name__ == "__main__":
    unittest.main()
```

Note: `post` is exercised here but implemented in Task 8 — the `test_log_outputs_events` test will fail until Task 8 lands. That is expected; run only the first three CLI tests in this task's Step 4, and the full file at the end of Task 8.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::CLITest::test_init_then_status_json -q`
Expected: FAIL — `orch.py` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
# orch.py  (root shim — runnable from any directory)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orch.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
```

```python
# orch/cli.py
import argparse
import json
import sys

from orch import db


def _project(args):
    import os
    name = args.project or os.environ.get("ORCH_PROJECT")
    if not name:
        raise db.NotFound("no project given (use --project or ORCH_PROJECT)")
    return name


def cmd_init(conn, args):
    pid, created = db.create_project(conn, args.name, notes=args.notes)
    print(f"{'created' if created else 'exists'} project '{args.name}' "
          f"(id {pid})")
    return 0


def cmd_task_add(conn, args):
    tid = db.add_task(conn, _project(args), args.agent, args.title,
                      issue_ref=args.issue, branch=args.branch,
                      worktree=args.worktree)
    print(f"task added: {tid}")
    return 0


def cmd_task_update(conn, args):
    db.update_task(conn, args.task, status=args.status,
                   branch=args.branch, issue_ref=args.issue)
    print(f"task {args.task} updated")
    return 0


def _format_status(state):
    lines = [f"project: {state['project']['name']}", "", "agents:"]
    for a in state["agents"]:
        ct = a["current_task"]
        title = f" — {ct['title']}" if ct else ""
        branch = f" [{ct['branch']}]" if ct and ct["branch"] else ""
        lines.append(f"  {a['agent']}: {a['status']}{title}{branch}")
    lines.append("")
    lines.append("recent events:")
    for e in state["events"][:15]:
        lines.append(f"  [{e['agent']}/{e['kind']}] {e['message']}")
    return "\n".join(lines)


def cmd_status(conn, args):
    state = db.get_state(conn, _project(args))
    if args.json:
        print(json.dumps(state, indent=2))
    else:
        print(_format_status(state))
    return 0


def cmd_log(conn, args):
    state = db.get_state(conn, _project(args), events_limit=args.n)
    for e in state["events"]:
        if args.agent and e["agent"] != args.agent:
            continue
        print(f"[{e['created_at']}] {e['agent']}/{e['kind']}: {e['message']}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="orch")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init")
    pi.add_argument("name")
    pi.add_argument("--notes")
    pi.set_defaults(func=cmd_init)

    pt = sub.add_parser("task")
    tsub = pt.add_subparsers(dest="task_cmd", required=True)
    ta = tsub.add_parser("add")
    ta.add_argument("--project")
    ta.add_argument("--agent", required=True)
    ta.add_argument("--title", required=True)
    ta.add_argument("--issue")
    ta.add_argument("--branch")
    ta.add_argument("--worktree")
    ta.set_defaults(func=cmd_task_add)
    tu = tsub.add_parser("update")
    tu.add_argument("--project")
    tu.add_argument("--task", type=int, required=True)
    tu.add_argument("--status")
    tu.add_argument("--branch")
    tu.add_argument("--issue")
    tu.set_defaults(func=cmd_task_update)

    ps = sub.add_parser("status")
    ps.add_argument("--project")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_status)

    pl = sub.add_parser("log")
    pl.add_argument("--project")
    pl.add_argument("--agent")
    pl.add_argument("-n", type=int, default=20)
    pl.set_defaults(func=cmd_log)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    conn = db.connect()
    try:
        return args.func(conn, args)
    except (db.NotFound, db.Ambiguous, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest "tests/test_cli.py::CLITest::test_init_then_status_json" "tests/test_cli.py::CLITest::test_task_add_prints_id_and_status_shows_it" "tests/test_cli.py::CLITest::test_status_unknown_project_errors" -q`
Expected: PASS (3 tests). `test_log_outputs_events` deferred to Task 8.

- [ ] **Step 5: Commit**

```bash
git add orch/cli.py orch.py tests/test_cli.py
git commit -m "feat: orch CLI (init, task add/update, status, log) + shim"
```

---

### Task 8: CLI `post` and `serve` commands

**Files:**
- Modify: `orch/cli.py`

- [ ] **Step 1: Write the failing test**

(Reuse `tests/test_cli.py::CLITest::test_log_outputs_events`, written in Task 7. Add the `post`-specific test below.)

```python
# add to tests/test_cli.py (inside CLITest)
    def test_post_status_updates_task(self):
        run(["init", "demo"], self.db)
        add = run(["task", "add", "--project", "demo", "--agent", "B",
                   "--title", "X"], self.db)
        tid = int(add.stdout.strip().split()[-1])
        out = run(["post", "--project", "demo", "--agent", "B",
                   "--status", "done", "--branch", "feat/x",
                   "--msg", "ready"], self.db)
        self.assertEqual(out.returncode, 0)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["status"], "done")
        self.assertEqual(state["tasks"][0]["branch"], "feat/x")
        self.assertEqual(state["agents"][0]["agent"], "B")
        _ = tid
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::CLITest::test_post_status_updates_task -q`
Expected: FAIL — `invalid choice: 'post'` from argparse.

- [ ] **Step 3: Write minimal implementation**

```python
# add to orch/cli.py (above build_parser)
def cmd_post(conn, args):
    eid = db.post_event(conn, _project(args), args.agent,
                        kind=args.kind, message=args.msg,
                        task_id=args.task, status=args.status,
                        branch=args.branch)
    print(f"event posted: {eid}")
    return 0


def cmd_serve(conn, args):
    from orch.server import serve
    serve(_project(args), port=args.port)
    return 0
```

```python
# add inside build_parser(), before `return p`
    pp = sub.add_parser("post")
    pp.add_argument("--project")
    pp.add_argument("--agent", required=True)
    pp.add_argument("--task", type=int)
    pp.add_argument("--kind", default="status",
                    choices=["status", "note", "blocker", "handoff"])
    pp.add_argument("--status")
    pp.add_argument("--branch")
    pp.add_argument("--msg", default="")
    pp.set_defaults(func=cmd_post)

    pv = sub.add_parser("serve")
    pv.add_argument("--project")
    pv.add_argument("--port", type=int, default=8787)
    pv.set_defaults(func=cmd_serve)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py -q`
Expected: PASS (all CLI tests, including `test_log_outputs_events` and `test_post_status_updates_task`). `serve` is covered in Task 9. If import of `orch.server` fails here, it is only invoked by `serve`, not by these tests — the file is created in Task 9; do not run `serve` until then.

- [ ] **Step 5: Commit**

```bash
git add orch/cli.py tests/test_cli.py
git commit -m "feat: orch post and serve commands"
```

---

### Task 9: Web dashboard (server + HTML)

**Files:**
- Create: `orch/dashboard.py`
- Create: `orch/server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server.py
import json
import os
import tempfile
import unittest

from orch import db, server


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "state.db")
        os.environ["ORCH_DB"] = self.db
        conn = db.connect(self.db)
        db.create_project(conn, "demo")
        db.add_task(conn, "demo", "B", "build X")
        db.post_event(conn, "demo", "B", status="in_progress", message="go")
        conn.close()

    def tearDown(self):
        del os.environ["ORCH_DB"]

    def test_api_state_returns_json(self):
        body, ctype = server.render_api_state("demo")
        self.assertIn("application/json", ctype)
        state = json.loads(body)
        self.assertEqual(state["project"]["name"], "demo")
        self.assertEqual(state["agents"][0]["status"], "in_progress")

    def test_api_state_unknown_project(self):
        body, ctype = server.render_api_state("nope")
        self.assertIn("application/json", ctype)
        self.assertIn("error", json.loads(body))

    def test_index_html_served(self):
        html, ctype = server.render_index("demo")
        self.assertIn("text/html", ctype)
        self.assertIn("demo", html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_server.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'orch.server'`.

- [ ] **Step 3: Write minimal implementation**

The HTML uses `str.format`, so all literal CSS/JS braces are doubled (`{{`/`}}`)
and only `{project}` is substituted. Copy the block exactly.

```python
# orch/dashboard.py
PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>orch — {project}</title>
<style>
 body{{font:14px system-ui,sans-serif;margin:0;background:#0f1115;color:#e6e6e6}}
 header{{padding:12px 20px;background:#171a21;font-weight:600}}
 .cols{{display:flex;gap:12px;padding:16px;flex-wrap:wrap}}
 .agent{{flex:1;min-width:200px;background:#171a21;border-radius:8px;padding:12px}}
 .badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px}}
 .todo{{background:#444}} .in_progress{{background:#1f6feb}}
 .blocked{{background:#b54708}} .done{{background:#238636}}
 .merged{{background:#8957e5}} .idle{{background:#333}}
 .feed{{padding:0 16px 24px}} .ev{{padding:6px 0;border-top:1px solid #222}}
 .muted{{color:#8b949e;font-size:12px}}
</style></head><body>
<header>orch — {project}</header>
<div id="cols" class="cols"></div>
<div class="feed"><h3>events</h3><div id="feed"></div></div>
<script>
async function tick(){{
  const r = await fetch('/api/state?project={project}');
  const s = await r.json();
  if(s.error){{document.getElementById('cols').innerHTML =
    '<div class=agent>'+s.error+'</div>';return;}}
  document.getElementById('cols').innerHTML = s.agents.map(a=>{{
    const ct = a.current_task ? a.current_task.title : '<span class=muted>no task</span>';
    const br = a.current_task && a.current_task.branch ?
      ' <span class=muted>['+a.current_task.branch+']</span>' : '';
    return '<div class=agent><b>'+a.agent+'</b> '+
      '<span class="badge '+a.status+'">'+a.status+'</span><br>'+ct+br+'</div>';
  }}).join('');
  document.getElementById('feed').innerHTML = s.events.map(e=>
    '<div class=ev><span class=muted>'+e.created_at+'</span> '+
    '<b>'+e.agent+'</b>/'+e.kind+': '+e.message+'</div>').join('');
}}
tick(); setInterval(tick, 3000);
</script></body></html>"""
```

```python
# orch/server.py
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from orch import db
from orch.dashboard import PAGE


def render_api_state(project):
    conn = db.connect()
    try:
        state = db.get_state(conn, project)
        return json.dumps(state), "application/json; charset=utf-8"
    except db.NotFound as e:
        return json.dumps({"error": str(e)}), "application/json; charset=utf-8"
    finally:
        conn.close()


def render_index(project):
    return PAGE.format(project=project), "text/html; charset=utf-8"


def make_handler(default_project):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, body, ctype, code=200):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            project = qs.get("project", [default_project])[0]
            if parsed.path == "/api/state":
                body, ctype = render_api_state(project)
                self._send(body, ctype)
            elif parsed.path == "/":
                body, ctype = render_index(project)
                self._send(body, ctype)
            else:
                self._send("not found", "text/plain; charset=utf-8", 404)

        def log_message(self, *args):
            pass  # quiet

    return Handler


def serve(project, port=8787):
    httpd = HTTPServer(("127.0.0.1", port), make_handler(project))
    print(f"orch dashboard: http://127.0.0.1:{port}/  (project: {project})")
    print("Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
        httpd.server_close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_server.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Manually verify the dashboard once**

Run: `python orch.py init demo` then `python orch.py task add --project demo --agent B --title "smoke"` then `python orch.py serve --project demo`
Open `http://127.0.0.1:8787/` — confirm the agent column and event feed render. Ctrl+C to stop.

- [ ] **Step 6: Commit**

```bash
git add orch/server.py orch/dashboard.py tests/test_server.py
git commit -m "feat: on-demand web dashboard (server + html)"
```

---

### Task 10: The `/orchestrating` skill + README

**Files:**
- Create: `.claude/skills/orchestrating/SKILL.md`
- Modify: `README.md`

- [ ] **Step 1: Write the skill**

```markdown
---
name: orchestrating
description: Use at the start of a multi-agent orchestration session to read live agent/task state from the orch DB, reconcile with Linear, and drive parallel work for Agents A/B/C.
---

# Orchestrating

You are the **orchestrator**. You do not write feature code yourself — you plan,
split work, hand the human ready-to-paste prompts for worker agents (A/B/C), read
their live progress from the `orch` DB, and reconcile with Linear.

## The `orch` tool

`orch` is this repo's CLI for live cross-agent state. Invoke it as:

```
python <path-to-orchestrator>/orch.py <command> --project <name>
```

Resolve `<path-to-orchestrator>` once at session start (it is the repo containing
this skill) and reuse it. Set `--project` to the project you are orchestrating;
agents can instead export `ORCH_PROJECT`.

Key commands:
- `orch.py status --project P` — current agent/task state + recent events (your main read)
- `orch.py status --project P --json` — same, machine-readable
- `orch.py task add --project P --agent B --title "..." [--issue LIN-123]` — create a task; prints its ID
- `orch.py task update --project P --task <id> --status merged` — after you merge
- `orch.py log --project P -n 20` — recent event feed

## Workflow

1. **Read state.** Run `orch.py status --project P`. Ensure the project exists
   (`orch.py init P` if not). Pull the Linear project state via the Linear MCP and
   reconcile: which Linear issues are in flight, which `orch` tasks map to them.
2. **Pick the next step** with the human. Identify 2-3 features that can run in
   **parallel without touching the same files**.
3. **Create tasks.** For each chosen piece: `orch.py task add ... --agent A|B|C
   --title "..." --issue <LIN ref>`. Note each printed task ID.
4. **Hand out prompts.** Give the human one brief-but-detailed prompt per agent to
   paste as that agent's first message. Each prompt MUST tell the agent to:
   - export `ORCH_PROJECT=P` (or pass `--project P`),
   - post on start: `python <path>/orch.py post --agent B --task <id> --status in_progress --msg "starting"`,
   - post blockers with `--kind blocker`,
   - run the project's `/checkpoint` skill on its work,
   - post on finish: `... post --agent B --task <id> --status done --branch <branch> --msg "ready for review"`,
   - and update Linear if it has access.
5. **Acknowledge completions.** When the human says an agent finished (or when
   `orch.py status` shows `done`), review the branch/worktree, merge, then
   `orch.py task update --task <id> --status merged`. Update Linear if the agent
   did not. Discuss the next logical step for that agent.

Keep the human in supervision: you propose, they execute. Never write feature code
in this session.
```

- [ ] **Step 2: Update the README**

```markdown
# orchestrator

A standard-library Python tool that gives multi-agent Claude Code / Codex sessions a
shared communication layer: worker agents report progress to one global SQLite DB and
the orchestrator reads live state instead of relying on copy-paste.

## Requirements

Python 3.8+. No pip installs.

## Quick start

```bash
python orch.py init myproject
python orch.py task add --project myproject --agent B --title "build login" --issue LIN-12
python orch.py post --project myproject --agent B --status in_progress --msg "starting"
python orch.py status --project myproject
python orch.py serve --project myproject   # dashboard at http://127.0.0.1:8787
```

The DB lives at `~/.orchestrator/state.db` (override with the `ORCH_DB` env var). Set
`ORCH_PROJECT` to avoid repeating `--project`.

## Commands

| command | purpose |
|---|---|
| `init <name>` | register a project |
| `task add` | create a task for an agent (`--agent --title [--issue --branch --worktree]`) |
| `task update` | amend a task (`--task <id> [--status --branch --issue]`) |
| `post` | append an event; updates the task on `--status`/`--branch` |
| `status [--json]` | current agent/task state + recent events |
| `log [--agent -n]` | recent event feed |
| `serve [--port]` | on-demand web dashboard |

## Orchestrating skill

`.claude/skills/orchestrating/SKILL.md` drives the orchestrator session: read state,
reconcile with Linear, split parallel work, hand out worker prompts, acknowledge
completions.

## Development

```bash
python -m pytest -q   # or: python -m unittest discover -s tests
```
```

- [ ] **Step 3: Run the full test suite**

Run: `python -m pytest -q`
Expected: PASS — all tests across `test_db.py`, `test_cli.py`, `test_server.py`.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/orchestrating/SKILL.md README.md
git commit -m "feat: orchestrating skill and README usage docs"
```

---

## Notes for the implementer

- **Run from the repo root** so `python orch.py ...` and `python -m pytest` resolve
  the `orch` package. Tests set `ORCH_DB` to a temp path, so they never touch the real
  `~/.orchestrator/state.db`.
- **If `pytest` is unavailable**, every test file also runs under
  `python -m unittest discover -s tests -v`.
- **TDD discipline:** write the test, watch it fail, implement, watch it pass, commit.
  Tasks 7 and 8 are intentionally coupled (the `post`/`log` CLI tests span both) — the
  notes in those tasks say exactly which tests to run when.
```
