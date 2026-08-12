# Worker Progress Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let worker agents report what they are doing and how much of their plan is left, so the orchestrator can answer "who is where" without asking the human.

**Architecture:** A `progress` event kind on the existing `events` table, with four nullable columns carrying phase / step / step_total / next_step. A task's current progress is *derived* — the newest progress event for that task — never a stored snapshot, so there is nothing to keep in sync. A new `orch progress` CLI command validates and appends; `orch status` and the dashboard read. Progress never writes lifecycle status and never raises `needs_human`.

**Tech Stack:** Python 3.8+, standard library only (`sqlite3`, `argparse`, `unittest`). No new dependencies. Tests run with `python -m pytest -q` or `python -m unittest discover -s tests`.

**Spec:** `docs/superpowers/specs/2026-08-12-worker-progress-reporting-design.md`

## Global Constraints

- **Standard library only.** No `pip install`, no new imports outside the stdlib.
- **Python 3.8+ compatible.** No walrus-in-comprehension tricks, no `match`, no `|` type unions.
- **Never break existing behaviour.** `orch report`, `orch post`, `orch status`, and every existing test must keep working unchanged.
- **Progress is telemetry.** It must never write `tasks.status` and never set `needs_human`. Only `report`/`post` do those.
- **Migrations use the existing helper** `db._add_column` (`orch/db.py:61`), which tolerates two agents migrating the same legacy DB at once.
- **Phase vocabulary is exactly these seven:** `setup`, `investigation`, `planning`, `awaiting_approval`, `implementation`, `checkpoint`, `blocked`. No others.
- **Message cap is 200 characters**, truncated (never rejected).
- **Style:** 4-space indent, ~79-column lines, docstrings that explain *why* on anything non-obvious — match the surrounding code in `orch/db.py`.

---

### Task 1: Progress storage and derived read

Adds the columns, the migration, and the two DB-layer reads everything else builds on. No user-visible behaviour yet.

**Files:**
- Modify: `orch/db.py:32-41` (SCHEMA events table), `orch/db.py:73-87` (`_migrate`), `orch/db.py:252-311` (`post_event`)
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `db.resolve_task(conn, project, agent, task_id=None, required=True) -> dict | None` — the task an event attaches to; raises `db.NotFound` / `db.Ambiguous` when `required` and there is no single answer.
  - `db.latest_progress(conn, task_id) -> dict | None` — keys `phase`, `step`, `step_total`, `message`, `next_step`, `updated_at`.
  - `db.post_event(..., progress=None)` — `progress` is a dict with keys `phase`, `step`, `step_total`, `next_step`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_db.py`, before the `if __name__ == "__main__":` block:

```python
class ProgressStorageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")
        self.tid = db.add_task(self.conn, "demo", "A", "x",
                               status="executing")

    def _post(self, message, phase, step=None, step_total=None,
              next_step=None):
        return db.post_event(
            self.conn, "demo", "A", kind="progress", message=message,
            task_id=self.tid,
            progress={"phase": phase, "step": step,
                      "step_total": step_total, "next_step": next_step})

    def test_fresh_schema_has_progress_columns(self):
        cols = {r[1] for r in self.conn.execute(
            "PRAGMA table_info(events)")}
        self.assertTrue({"progress_phase", "progress_step",
                         "progress_step_total",
                         "progress_next_step"}.issubset(cols))

    def test_latest_progress_is_none_without_events(self):
        self.assertIsNone(db.latest_progress(self.conn, self.tid))

    def test_latest_progress_returns_newest_row(self):
        self._post("drafting the plan", "planning")
        self._post("wiring the CLI", "implementation", step=2, step_total=5,
                   next_step="status output")
        p = db.latest_progress(self.conn, self.tid)
        self.assertEqual(p["phase"], "implementation")
        self.assertEqual(p["step"], 2)
        self.assertEqual(p["step_total"], 5)
        self.assertEqual(p["message"], "wiring the CLI")
        self.assertEqual(p["next_step"], "status output")
        self.assertTrue(p["updated_at"])

    def test_progress_event_leaves_status_and_needs_human_alone(self):
        self._post("wiring the CLI", "implementation")
        row = self.conn.execute(
            "SELECT status, needs_human FROM tasks WHERE id = ?",
            (self.tid,)).fetchone()
        self.assertEqual(row["status"], "executing")
        self.assertEqual(row["needs_human"], 0)

    def test_resolve_task_finds_single_active_task(self):
        self.assertEqual(
            db.resolve_task(self.conn, "demo", "A")["id"], self.tid)

    def test_resolve_task_ambiguous_raises(self):
        db.add_task(self.conn, "demo", "A", "y", status="executing")
        with self.assertRaises(db.Ambiguous):
            db.resolve_task(self.conn, "demo", "A")

    def test_resolve_task_no_active_task_raises(self):
        with self.assertRaises(db.NotFound):
            db.resolve_task(self.conn, "demo", "Z")

    def test_resolve_task_optional_returns_none(self):
        self.assertIsNone(
            db.resolve_task(self.conn, "demo", "Z", required=False))

    def test_resolve_task_explicit_id_outside_project_raises(self):
        db.create_project(self.conn, "other")
        with self.assertRaises(db.NotFound):
            db.resolve_task(self.conn, "other", "A", task_id=self.tid)


class ProgressMigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "legacy.db")
        legacy = sqlite3.connect(self.path)
        legacy.executescript(
            "CREATE TABLE projects (id INTEGER PRIMARY KEY, "
            " name TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, "
            " notes TEXT);"
            "CREATE TABLE events (id INTEGER PRIMARY KEY, "
            " project_id INTEGER NOT NULL, task_id INTEGER, "
            " agent TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'status', "
            " message TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);")
        legacy.commit()
        legacy.close()

    def _event_cols(self, conn):
        return {r[1] for r in conn.execute("PRAGMA table_info(events)")}

    def test_legacy_db_gains_progress_columns(self):
        conn = db.connect(self.path)
        try:
            self.assertTrue({"progress_phase", "progress_step",
                             "progress_step_total", "progress_next_step"}
                            .issubset(self._event_cols(conn)))
        finally:
            conn.close()

    def test_migration_is_idempotent(self):
        db.connect(self.path).close()
        conn = db.connect(self.path)
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(events)")]
            self.assertEqual(cols.count("progress_phase"), 1)
        finally:
            conn.close()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_db.py -q`
Expected: FAIL — `AttributeError: module 'orch.db' has no attribute 'latest_progress'` and `no such column: progress_phase`.

- [ ] **Step 3: Add the columns to the schema**

In `orch/db.py`, replace the `events` table in `SCHEMA` (currently `orch/db.py:32-40`) with:

```python
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    task_id    INTEGER REFERENCES tasks(id),
    agent      TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT 'status',
    message    TEXT NOT NULL DEFAULT '',
    progress_phase       TEXT,
    progress_step        INTEGER,
    progress_step_total  INTEGER,
    progress_next_step   TEXT,
    created_at TEXT NOT NULL
);
```

- [ ] **Step 4: Migrate existing databases**

In `orch/db.py`, inside `_migrate`, immediately before the closing `conn.commit()` (currently `orch/db.py:87`), add:

```python
    ecols = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
    if ecols:
        # Progress: what a worker is doing and how far into its plan it is.
        # Checked one column at a time, not gated on the first, so a run
        # interrupted midway through completes on the next connect.
        for name, ddl in (
                ("progress_phase", "progress_phase TEXT"),
                ("progress_step", "progress_step INTEGER"),
                ("progress_step_total", "progress_step_total INTEGER"),
                ("progress_next_step", "progress_next_step TEXT")):
            if name not in ecols:
                _add_column(conn, "events", ddl)
```

- [ ] **Step 5: Add `resolve_task` and `latest_progress`**

In `orch/db.py`, insert both functions immediately after `_active_tasks` (which ends at `orch/db.py:249`) and before `post_event`:

```python
def resolve_task(conn, project, agent, task_id=None, required=True):
    """The task an event attaches to: an explicit id, else the agent's single
    active task. With `required=False`, returns None instead of raising when
    the agent has no active task or more than one — the shape `post_event`
    needs for a bare note, which may legitimately have no task."""
    pid = require_project(conn, project)["id"]
    if task_id is not None:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND project_id = ?",
            (task_id, pid)).fetchone()
        if row is None:
            raise NotFound(f"task {task_id} not found in '{project}'")
        return dict(row)
    active = _active_tasks(conn, pid, agent)
    if len(active) == 1:
        return dict(active[0])
    if not required:
        return None
    if not active:
        raise NotFound(
            f"agent '{agent}' has no active task in '{project}'; pass --task")
    raise Ambiguous(
        f"agent '{agent}' has {len(active)} active tasks; pass --task <id>")


def latest_progress(conn, task_id):
    """A task's current progress: the newest kind='progress' event, or None.

    Derived rather than stored. A denormalized snapshot on `tasks` would be a
    second source of truth for the same fact, with an atomicity requirement
    to keep the two agreeing; this query costs nothing at our scale."""
    if task_id is None:
        return None
    row = conn.execute(
        "SELECT message, progress_phase, progress_step, "
        "progress_step_total, progress_next_step, created_at "
        "FROM events WHERE task_id = ? AND kind = 'progress' "
        "ORDER BY id DESC LIMIT 1", (task_id,)).fetchone()
    if row is None:
        return None
    return {
        "phase": row["progress_phase"],
        "step": row["progress_step"],
        "step_total": row["progress_step_total"],
        "message": row["message"],
        "next_step": row["progress_next_step"],
        "updated_at": row["created_at"],
    }
```

- [ ] **Step 6: Accept progress fields in `post_event`**

In `orch/db.py`, change the `post_event` signature (`orch/db.py:252-253`) to:

```python
def post_event(conn, project, agent, kind="status", message="",
               task_id=None, status=None, branch=None, progress=None):
```

Replace the task-resolution block (`orch/db.py:259-275`, from the `# Resolve target task` comment through `task_id = active[0]["id"]`) with:

```python
    # Resolve target task when we need one (status/branch update) or when a
    # single active task exists to attach the event to.
    if task_id is None:
        need_task = status is not None or branch is not None
        found = resolve_task(conn, project, agent, required=need_task)
        task_id = found["id"] if found else None

    prog = progress or {}
```

Then replace the INSERT inside `_do` (`orch/db.py:280-284`) with:

```python
        cur = conn.execute(
            "INSERT INTO events (project_id, task_id, agent, kind, message, "
            "progress_phase, progress_step, progress_step_total, "
            "progress_next_step, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (pid, task_id, agent, kind, message, prog.get("phase"),
             prog.get("step"), prog.get("step_total"),
             prog.get("next_step"), ts),
        )
```

Leave the rest of `_do` — the `needs_human` and status/branch handling — exactly as it is. `kind="progress"` is not in `RAISE_HUMAN_KINDS` and progress passes no `status`, so that block is a no-op for progress by construction.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest tests/test_db.py -q`
Expected: PASS, all tests including the pre-existing ones.

- [ ] **Step 8: Run the full suite (nothing else may regress)**

Run: `python -m pytest -q`
Expected: PASS. `post_event`'s resolution was refactored, so `test_cli.py` and `test_report.py` are the ones that would catch a mistake.

- [ ] **Step 9: Commit**

```bash
git add orch/db.py tests/test_db.py
git commit -m "feat(progress): progress columns on events, derived latest read"
```

---

### Task 2: The progress module — validation and recording

The rules live here, in one importable place, so the CLI and `report` share them.

**Files:**
- Create: `orch/progress.py`
- Test: `tests/test_progress.py` (create)

**Interfaces:**
- Consumes: `db.resolve_task`, `db.latest_progress`, `db.post_event(..., progress=...)` from Task 1.
- Produces:
  - `progress.PHASES` — tuple of the seven valid phase strings.
  - `progress.MAX_MESSAGE` — `200`.
  - `progress.record(conn, project, agent, phase, message="", step=None, step_total=None, next_step=None, task_id=None) -> dict` with keys `task_id`, `phase`, `step`, `step_total`, `message`, `next_step`, `recorded`, `truncated`.
  - `progress.format_line(snapshot) -> str` — accepts any dict with `phase`/`step`/`step_total`/`message`, including a `db.latest_progress` result.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_progress.py`:

```python
import os
import tempfile
import unittest

from orch import db, progress


class RecordTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")
        self.tid = db.add_task(self.conn, "demo", "A", "x",
                               status="executing")

    def test_records_a_progress_event(self):
        out = progress.record(self.conn, "demo", "A", "implementation",
                              message="wiring the CLI", step=2, step_total=5,
                              next_step="status output")
        self.assertTrue(out["recorded"])
        self.assertEqual(out["task_id"], self.tid)
        p = db.latest_progress(self.conn, self.tid)
        self.assertEqual(p["phase"], "implementation")
        self.assertEqual(p["step"], 2)
        self.assertEqual(p["next_step"], "status output")

    def test_does_not_touch_status_or_needs_human(self):
        progress.record(self.conn, "demo", "A", "checkpoint",
                        message="codex review")
        row = self.conn.execute(
            "SELECT status, needs_human FROM tasks WHERE id = ?",
            (self.tid,)).fetchone()
        self.assertEqual(row["status"], "executing")
        self.assertEqual(row["needs_human"], 0)

    def test_unknown_phase_rejected_and_lists_valid_ones(self):
        with self.assertRaises(ValueError) as ctx:
            progress.record(self.conn, "demo", "A", "deploying")
        self.assertIn("implementation", str(ctx.exception))

    def test_step_without_total_rejected(self):
        with self.assertRaises(ValueError):
            progress.record(self.conn, "demo", "A", "implementation", step=2)

    def test_total_without_step_rejected(self):
        with self.assertRaises(ValueError):
            progress.record(self.conn, "demo", "A", "implementation",
                            step_total=5)

    def test_step_below_one_rejected(self):
        with self.assertRaises(ValueError):
            progress.record(self.conn, "demo", "A", "implementation",
                            step=0, step_total=5)

    def test_step_past_total_rejected(self):
        with self.assertRaises(ValueError):
            progress.record(self.conn, "demo", "A", "implementation",
                            step=6, step_total=5)

    def test_long_message_is_truncated_not_rejected(self):
        out = progress.record(self.conn, "demo", "A", "implementation",
                              message="x" * 500)
        self.assertTrue(out["truncated"])
        self.assertEqual(len(out["message"]), progress.MAX_MESSAGE)

    def test_identical_consecutive_report_is_a_no_op(self):
        args = ("demo", "A", "implementation")
        kw = {"message": "same", "step": 1, "step_total": 3}
        progress.record(self.conn, *args, **kw)
        out = progress.record(self.conn, *args, **kw)
        self.assertFalse(out["recorded"])
        count = self.conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 'progress'"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_changed_report_records_again(self):
        progress.record(self.conn, "demo", "A", "implementation",
                        message="one", step=1, step_total=3)
        out = progress.record(self.conn, "demo", "A", "implementation",
                              message="two", step=2, step_total=3)
        self.assertTrue(out["recorded"])

    def test_done_task_is_refused(self):
        db.update_task(self.conn, self.tid, status="done")
        with self.assertRaises(ValueError) as ctx:
            progress.record(self.conn, "demo", "A", "checkpoint",
                            task_id=self.tid)
        self.assertIn("orch report", str(ctx.exception))

    def test_blocked_task_is_allowed(self):
        db.update_task(self.conn, self.tid, status="blocked")
        out = progress.record(self.conn, "demo", "A", "blocked",
                              message="missing credentials")
        self.assertTrue(out["recorded"])

    def test_no_active_task_raises_rather_than_orphaning(self):
        with self.assertRaises(db.NotFound):
            progress.record(self.conn, "demo", "Z", "setup")
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM events").fetchone()[0], 0)


class FormatLineTest(unittest.TestCase):
    def test_with_steps_and_message(self):
        self.assertEqual(
            progress.format_line({"phase": "implementation", "step": 3,
                                  "step_total": 6, "message": "the CLI"}),
            "implementation 3/6 · the CLI")

    def test_without_steps(self):
        self.assertEqual(
            progress.format_line({"phase": "planning", "step": None,
                                  "step_total": None, "message": "drafting"}),
            "planning · drafting")

    def test_empty_snapshot(self):
        self.assertEqual(progress.format_line(None), "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_progress.py -q`
Expected: FAIL — `ImportError: cannot import name 'progress' from 'orch'`.

- [ ] **Step 3: Write `orch/progress.py`**

```python
"""Worker progress: what an agent is doing, and how much of its plan is left.

Progress runs alongside the task lifecycle without touching it. A progress
event never writes `tasks.status` and never raises `needs_human` — only
`orch report`/`orch post` do those — and a late phase never authorizes a
merge. Reporting is event-driven: workers report at phase boundaries and at
the start of each plan task. There is no heartbeat, because a worker agent
has no timer and can only report when it happens to look up.
"""

from orch import db

PHASES = ("setup", "investigation", "planning", "awaiting_approval",
          "implementation", "checkpoint", "blocked")

# A `done` or `merged` task is over; progress against it would describe work
# that already finished, so it is refused rather than silently recorded.
CLOSED_STATUSES = ("done", "merged")

MAX_MESSAGE = 200


def _validate_steps(step, step_total):
    if (step is None) != (step_total is None):
        raise ValueError(
            "step and step_total go together — pass both or neither")
    if step is None:
        return
    if step < 1:
        raise ValueError(f"step must be 1 or more (got {step})")
    if step_total < 1:
        raise ValueError(f"step_total must be 1 or more (got {step_total})")
    if step > step_total:
        raise ValueError(f"step {step} is past step_total {step_total}")


def record(conn, project, agent, phase, message="", step=None,
           step_total=None, next_step=None, task_id=None):
    """Append one progress event for the agent's task.

    Returns {task_id, phase, step, step_total, message, next_step, recorded,
    truncated}. `recorded` is False when this repeats the task's current
    progress exactly — a resumed worker re-reporting the milestone it already
    reported should not leave a second identical row."""
    if phase not in PHASES:
        raise ValueError(
            f"unknown phase '{phase}', expected one of: {', '.join(PHASES)}")
    _validate_steps(step, step_total)

    task = db.resolve_task(conn, project, agent, task_id=task_id)
    if task["status"] in CLOSED_STATUSES:
        raise ValueError(
            f"task {task['id']} is {task['status']} — progress only applies "
            f"to a task still in flight (use `orch report` for lifecycle "
            f"changes)")

    text = (message or "").strip()
    truncated = len(text) > MAX_MESSAGE
    snapshot = {
        "phase": phase,
        "step": step,
        "step_total": step_total,
        "message": text[:MAX_MESSAGE],
        "next_step": (next_step or "").strip() or None,
    }

    current = db.latest_progress(conn, task["id"])
    unchanged = current is not None and all(
        current[k] == v for k, v in snapshot.items())
    if not unchanged:
        db.post_event(conn, project, agent, kind="progress",
                      message=snapshot["message"], task_id=task["id"],
                      progress=snapshot)

    return dict(snapshot, task_id=task["id"], recorded=not unchanged,
                truncated=truncated)


def format_line(snapshot):
    """One line: 'implementation 3/6 · wiring the CLI'. Takes any snapshot
    dict — a `db.latest_progress` result or a `record` return value."""
    if not snapshot:
        return ""
    parts = [snapshot["phase"]]
    if snapshot.get("step") and snapshot.get("step_total"):
        parts.append(f"{snapshot['step']}/{snapshot['step_total']}")
    if snapshot.get("message"):
        parts.append(f"· {snapshot['message']}")
    return " ".join(parts)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_progress.py -q`
Expected: PASS (16 tests).

- [ ] **Step 5: Commit**

```bash
git add orch/progress.py tests/test_progress.py
git commit -m "feat(progress): validation and recording module"
```

---

### Task 3: A blocked report also records a blocked phase

So a blocked worker still runs one command, and the display shows `blocked` without a second call.

**Files:**
- Modify: `orch/report.py:39-42`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `progress.record` from Task 2.
- Produces: no new API. `report.report(..., status="blocked")` now also writes one `kind=progress` event with `phase="blocked"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_report.py`, inside `ReportTest`, before the closing `if __name__`:

```python
    def test_blocked_also_records_blocked_progress(self):
        report.report(self.conn, "demo", "A", "blocked", msg="no creds",
                      notifier=lambda m, title=None: None)
        p = db.latest_progress(self.conn, self.tid)
        self.assertEqual(p["phase"], "blocked")
        self.assertEqual(p["message"], "no creds")

    def test_executing_records_no_progress(self):
        report.report(self.conn, "demo", "A", "executing", msg="go")
        self.assertIsNone(db.latest_progress(self.conn, self.tid))

    def test_blocked_still_reports_when_progress_fails(self):
        # Telemetry must never be able to swallow a blocker. Force the
        # progress write to explode and assert the status still landed.
        from orch import progress as progress_mod
        orig = progress_mod.record
        progress_mod.record = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("boom"))
        try:
            report.report(self.conn, "demo", "A", "blocked", msg="stuck",
                          notifier=lambda m, title=None: None)
        finally:
            progress_mod.record = orig
        self.assertEqual(self._task()["status"], "blocked")
        self.assertEqual(self._task()["needs_human"], 1)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_report.py -q`
Expected: FAIL — `test_blocked_also_records_blocked_progress` gets `None` from `latest_progress`.

- [ ] **Step 3: Record blocked progress in `report`**

In `orch/report.py`, replace the blocked branch (`orch/report.py:39-40`) with:

```python
    if status == "blocked":
        # The blocker itself is already recorded above. The progress row is
        # telemetry on top of it: best-effort, and never allowed to raise
        # past a blocker the human needs to see.
        try:
            progress.record(conn, project, agent, "blocked", message=msg)
        except Exception:
            pass
        notifier(f"Agent {agent} blocked: {msg}", title="Blocked")
```

And add to the imports at the top of `orch/report.py` (after `from orch import notify as notify_mod`, `orch/report.py:4`):

```python
from orch import progress
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_report.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add orch/report.py tests/test_report.py
git commit -m "feat(progress): a blocked report records a blocked phase"
```

---

### Task 4: The `orch progress` command

**Files:**
- Modify: `orch/cli.py` (new `cmd_progress`, new subparser in `build_parser`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `progress.record`, `progress.format_line`, `progress.PHASES`, `progress.MAX_MESSAGE` from Task 2.
- Produces: the CLI surface `orch progress --agent A --phase P [--step N --step-total M] [--msg ...] [--next ...] [--task N] [--json]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`, inside `CLITest`, before the closing `if __name__`:

```python
    def _project_with_task(self, agent="A", status="executing"):
        run(["init", "demo"], self.db)
        add = run(["task", "add", "--project", "demo", "--agent", agent,
                   "--title", "X", "--status", status], self.db)
        return int(add.stdout.strip().split()[-1])

    def test_progress_records_and_prints(self):
        self._project_with_task()
        out = run(["progress", "--project", "demo", "--agent", "A",
                   "--phase", "implementation", "--step", "3",
                   "--step-total", "6", "--msg", "wiring the CLI",
                   "--next", "status output"], self.db)
        self.assertEqual(out.returncode, 0)
        self.assertIn("implementation 3/6", out.stdout)
        self.assertIn("status output", out.stdout)

    def test_progress_json_shape(self):
        tid = self._project_with_task()
        out = run(["progress", "--project", "demo", "--agent", "A",
                   "--phase", "planning", "--msg", "drafting", "--json"],
                  self.db)
        self.assertEqual(out.returncode, 0)
        payload = json.loads(out.stdout)
        self.assertEqual(payload["task_id"], tid)
        self.assertEqual(payload["phase"], "planning")
        self.assertIsNone(payload["step"])
        self.assertTrue(payload["recorded"])

    def test_progress_repeat_reports_unchanged(self):
        self._project_with_task()
        args = ["progress", "--project", "demo", "--agent", "A",
                "--phase", "setup", "--msg", "worktree ready"]
        run(args, self.db)
        out = run(args, self.db)
        self.assertEqual(out.returncode, 0)
        self.assertIn("unchanged", out.stdout)

    def test_progress_unknown_phase_errors(self):
        self._project_with_task()
        out = run(["progress", "--project", "demo", "--agent", "A",
                   "--phase", "deploying"], self.db)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("implementation", out.stderr)

    def test_progress_bad_step_pair_errors(self):
        self._project_with_task()
        out = run(["progress", "--project", "demo", "--agent", "A",
                   "--phase", "implementation", "--step", "7",
                   "--step-total", "5"], self.db)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("step", out.stderr)

    def test_progress_on_done_task_errors(self):
        tid = self._project_with_task()
        run(["task", "update", "--project", "demo", "--task", str(tid),
             "--status", "done"], self.db)
        out = run(["progress", "--project", "demo", "--agent", "A",
                   "--phase", "checkpoint", "--task", str(tid)], self.db)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("orch report", out.stderr)

    def test_progress_ambiguous_requires_task(self):
        self._project_with_task()
        run(["task", "add", "--project", "demo", "--agent", "A",
             "--title", "Y", "--status", "executing"], self.db)
        out = run(["progress", "--project", "demo", "--agent", "A",
                   "--phase", "setup"], self.db)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("--task", out.stderr)

    def test_progress_truncates_long_message(self):
        self._project_with_task()
        out = run(["progress", "--project", "demo", "--agent", "A",
                   "--phase", "implementation", "--msg", "x" * 400,
                   "--json"], self.db)
        payload = json.loads(out.stdout)
        self.assertTrue(payload["truncated"])
        self.assertEqual(len(payload["message"]), 200)

    def test_progress_without_agent_errors(self):
        self._project_with_task()
        out = run(["progress", "--project", "demo", "--phase", "setup"],
                  self.db)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("agent", out.stderr.lower())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -q`
Expected: FAIL — `argument cmd: invalid choice: 'progress'`.

- [ ] **Step 3: Add the command handler**

In `orch/cli.py`, add after `cmd_report` (which ends at `orch/cli.py:178`):

```python
def cmd_progress(conn, args):
    from orch import progress as progress_mod
    agent = args.agent or os.environ.get("ORCH_AGENT")
    if not agent:
        print("error: no agent given (use --agent or ORCH_AGENT)",
              file=sys.stderr)
        return 1
    result = progress_mod.record(
        conn, _project(conn, args), agent, args.phase, message=args.msg,
        step=args.step, step_total=args.step_total, next_step=args.next,
        task_id=args.task)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    suffix = "" if result["recorded"] else " (unchanged)"
    print(f"progress: {progress_mod.format_line(result)}{suffix}")
    if result["next_step"]:
        print(f"next: {result['next_step']}")
    if result["truncated"]:
        print(f"note: message truncated to {progress_mod.MAX_MESSAGE} chars")
    return 0
```

- [ ] **Step 4: Add the subparser**

In `orch/cli.py`, in `build_parser`, add immediately after the `report` parser block (which ends at `orch/cli.py:300` with `pr.set_defaults(...)`):

```python
    from orch.progress import PHASES
    pg = sub.add_parser("progress")
    pg.add_argument("--project")
    pg.add_argument("--agent")
    pg.add_argument("--task", type=int)
    pg.add_argument("--phase", required=True, choices=list(PHASES))
    pg.add_argument("--step", type=int)
    pg.add_argument("--step-total", type=int)
    pg.add_argument("--msg", default="")
    pg.add_argument("--next", default="")
    pg.add_argument("--json", action="store_true")
    pg.set_defaults(func=cmd_progress)
```

Note: `--phase` is validated twice on purpose — argparse rejects it at the CLI with the valid list, and `progress.record` rejects it for any non-CLI caller. `main`'s existing `except (db.NotFound, db.Ambiguous, ValueError)` handler (`orch/cli.py:350`) already turns every `record` failure into `error: ...` on stderr with exit code 1, so nothing new is needed there.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add orch/cli.py tests/test_cli.py
git commit -m "feat(progress): orch progress command"
```

---

### Task 5: Progress in `orch status` and `--json`

**Files:**
- Modify: `orch/db.py:318-356` (`get_state`), `orch/cli.py:56-74` (`_format_status`)
- Test: `tests/test_db.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `db.latest_progress` from Task 1, `progress.format_line` from Task 2.
- Produces: every task dict in `get_state` gains a `progress` key (snapshot dict or `None`). `current_task` inside each agent entry is the same dict object, so it carries progress too.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_db.py`, inside `ProgressStorageTest`:

```python
    def test_get_state_attaches_progress_to_tasks(self):
        self._post("wiring the CLI", "implementation", step=2, step_total=5)
        state = db.get_state(self.conn, "demo")
        task = next(t for t in state["tasks"] if t["id"] == self.tid)
        self.assertEqual(task["progress"]["phase"], "implementation")
        self.assertEqual(task["progress"]["step"], 2)

    def test_get_state_progress_is_none_when_unreported(self):
        state = db.get_state(self.conn, "demo")
        task = next(t for t in state["tasks"] if t["id"] == self.tid)
        self.assertIsNone(task["progress"])

    def test_get_state_agent_current_task_carries_progress(self):
        self._post("codex review", "checkpoint")
        state = db.get_state(self.conn, "demo")
        agent = next(a for a in state["agents"] if a["agent"] == "A")
        self.assertEqual(
            agent["current_task"]["progress"]["phase"], "checkpoint")
```

Append to `tests/test_cli.py`, inside `CLITest`:

```python
    def test_status_shows_progress_line(self):
        self._project_with_task()
        run(["progress", "--project", "demo", "--agent", "A",
             "--phase", "implementation", "--step", "3", "--step-total", "6",
             "--msg", "wiring the CLI", "--next", "status output"], self.db)
        out = run(["status", "--project", "demo"], self.db)
        self.assertEqual(out.returncode, 0)
        self.assertIn("implementation 3/6", out.stdout)
        self.assertIn("next: status output", out.stdout)
        self.assertIn("ago", out.stdout)

    def test_status_without_progress_is_unchanged(self):
        self._project_with_task()
        out = run(["status", "--project", "demo"], self.db)
        self.assertEqual(out.returncode, 0)
        self.assertIn("A: executing", out.stdout)
        self.assertNotIn("next:", out.stdout)

    def test_status_json_exposes_progress(self):
        self._project_with_task()
        run(["progress", "--project", "demo", "--agent", "A",
             "--phase", "planning", "--msg", "drafting"], self.db)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["progress"]["phase"], "planning")
        self.assertIsNone(state["tasks"][0]["progress"]["step"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_db.py tests/test_cli.py -q`
Expected: FAIL — `KeyError: 'progress'` on the task dicts.

- [ ] **Step 3: Attach progress in `get_state`**

In `orch/db.py`, in `get_state`, immediately after the `tasks = [...]` list comprehension (`orch/db.py:322-324`), add:

```python
    for t in tasks:
        t["progress"] = latest_progress(conn, t["id"])
```

The agent entries below reference these same dict objects, so `current_task["progress"]` comes along for free.

- [ ] **Step 4: Add the age helper and the status lines**

In `orch/cli.py`, add to the imports at the top (after `import sys`, `orch/cli.py:5`):

```python
from datetime import datetime, timezone

from orch import progress as progress_mod
```

(`orch/progress.py` imports only `orch.db`, so this is not a cycle. `cmd_progress`
from Task 4 keeps its local import; both names resolve to the same module.)

Add above `_format_status` (`orch/cli.py:56`):

```python
def _age(iso_ts):
    """'12m ago' for an ISO timestamp. Shown without judgement: 41 minutes on
    awaiting_approval means the human hasn't answered, not that anything is
    wrong."""
    try:
        then = datetime.fromisoformat(iso_ts)
    except (TypeError, ValueError):
        return ""
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    secs = max(int((datetime.now(timezone.utc) - then).total_seconds()), 0)
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"
```

In `_format_status`, replace the agent loop (`orch/cli.py:65-69`) with:

```python
    for a in state["agents"]:
        ct = a["current_task"]
        title = f" — {ct['title']}" if ct else ""
        branch = f" [{ct['branch']}]" if ct and ct["branch"] else ""
        lines.append(f"  {a['agent']}: {a['status']}{title}{branch}")
        prog = ct.get("progress") if ct else None
        if prog:
            lines.append(f"       {progress_mod.format_line(prog)}")
            nxt = f"next: {prog['next_step']} · " if prog["next_step"] else ""
            lines.append(f"       {nxt}{_age(prog['updated_at'])}")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_db.py tests/test_cli.py -q`
Expected: PASS.

- [ ] **Step 6: Eyeball the real output**

Run:

```bash
python orch.py status --project demo
```

against any project that has a task, and confirm the layout reads well. This is the surface you will look at every day; adjust spacing here if it doesn't.

- [ ] **Step 7: Commit**

```bash
git add orch/db.py orch/cli.py tests/test_db.py tests/test_cli.py
git commit -m "feat(progress): show progress in orch status and --json"
```

---

### Task 6: Dashboard shows the snapshot

Minimal pass only. The multi-agent redesign is a separate spec — do not start it here.

**Files:**
- Modify: `orch/dashboard.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: the `progress` key on `current_task` from Task 5, served by the existing `/api/state`.
- Produces: no Python API. A `progressLine(task)` JS function inside `PAGE`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_server.py`, before the closing `if __name__`:

```python
class DashboardProgressTest(unittest.TestCase):
    def test_page_renders_progress_and_escapes(self):
        from orch.dashboard import PAGE
        page = PAGE.format(project="demo")
        self.assertIn("progressLine", page)
        self.assertIn("function esc(", page)
        # .format() must not have eaten the JS braces
        self.assertNotIn("{{", page)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_server.py -q`
Expected: FAIL — `progressLine` not found in the page.

- [ ] **Step 3: Add the style rule**

In `orch/dashboard.py`, add to the `<style>` block, after the `.muted` rule:

```css
 .phase{{color:#58a6ff;font-size:12px}}
```

- [ ] **Step 4: Add the JS helpers**

In `orch/dashboard.py`, insert immediately after the `setHealth` function and before `async function tick()`:

```javascript
function esc(s){{
  return String(s==null?'':s).replace(/[&<>"]/g, c=>(
    {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
}}
function progressLine(t){{
  const p = t && t.progress;
  if(!p) return '';
  const step = (p.step && p.step_total) ? ' '+p.step+'/'+p.step_total : '';
  const msg = p.message ? ' · '+esc(p.message) : '';
  const nxt = p.next_step ?
    '<br><span class=muted>next: '+esc(p.next_step)+'</span>' : '';
  return '<br><span class=phase>'+esc(p.phase)+step+'</span>'+msg+nxt;
}}
```

- [ ] **Step 5: Render it on the agent card**

In `orch/dashboard.py`, in the `cols` renderer, change the `return` line so the card includes the progress block:

```javascript
    return '<div class=agent><b>'+a.agent+'</b> '+
      '<span class="badge '+a.status+'">'+a.status+'</span><br>'+ct+br+
      progressLine(a.current_task)+'</div>';
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/test_server.py -q`
Expected: PASS.

- [ ] **Step 7: Look at it**

Run `python orch.py serve --project demo`, open http://127.0.0.1:8787/, and confirm an agent with progress shows its phase line. Ctrl+C to stop.

- [ ] **Step 8: Commit**

```bash
git add orch/dashboard.py tests/test_server.py
git commit -m "feat(progress): show the progress snapshot on the dashboard"
```

---

### Task 7: Worker skills report progress

Prose only — no code. Verify by re-reading each file against the table in the spec.

**Files:**
- Modify: `.claude/skills/work/SKILL.md`, `.claude/skills/checkpoint/SKILL.md`, `.claude/skills/report/SKILL.md`

**Interfaces:**
- Consumes: the `orch progress` CLI from Task 4.
- Produces: no code. Worker sessions now emit progress at the eight points in the spec.

- [ ] **Step 1: Add the reporting points to `/work`**

In `.claude/skills/work/SKILL.md`, at the end of step 2 (after the `**Sync dependencies fast:**` bullet, which ends at `work/SKILL.md:88`), add:

```markdown
   - **Report progress:**
     `python <path>/orch.py progress --agent <AGENT> --phase setup --msg "worktree ready, deps synced"`
```

In the `queued` branch, after the investigation bullet (`work/SKILL.md:97-103`), add:

```markdown
     - Investigation pass → `orch progress --agent <AGENT> --phase investigation
       --msg "<what's already shipped vs missing>"`.
     - Brainstorming/plan writing → `orch progress --agent <AGENT> --phase planning
       --msg "<what you're designing>"`.
     - Plan written, waiting on the human → `orch progress --agent <AGENT>
       --phase awaiting_approval --msg "plan ready: <plan_path>"`.
```

Replace step 4's plan-task bullet (`work/SKILL.md:117-118`) with:

```markdown
   - Count the tasks in the approved plan — that number is `--step-total`.
   - Implement the plan via `superpowers:executing-plans`. **At the start of each
     plan task** (not at each checkbox), report which one you are on:
     `python <path>/orch.py progress --agent <AGENT> --phase implementation
     --step <N> --step-total <total> --msg "<the task you're starting>"
     --next "<the one after>"`.
     `--step` is the task you are starting, never the one you just finished —
     that is what makes `3/6` answer "how much is left". This replaces the old
     `/report plan task N done` note; don't send both.
```

Update the Rules section (`work/SKILL.md:147`) to:

```markdown
- Report via `/report` for lifecycle (`executing`/`done`/`blocked`) and via
  `orch progress` at phase boundaries and each plan task, so the orchestrator
  and dashboard stay live. There is no heartbeat — report at boundaries, not on
  a timer.
- **Progress is telemetry: never let it stop the work.** If an `orch progress`
  call fails, retry it once. If it fails again, post
  `orch post --agent <AGENT> --kind warning --msg "progress write failed: <why>"`
  if you can, then carry on with the actual task. A failed progress write is
  never a reason to report `blocked`, and never a reason to stop.
```

- [ ] **Step 2: Add the checkpoint reporting points**

In `.claude/skills/checkpoint/SKILL.md`, add after the "Never degrade silently" block (`checkpoint/SKILL.md:25`):

```markdown
**Report the phase as you go.** At the start of Step 1:

`python <path>/orch.py progress --agent <AGENT> --phase checkpoint --msg "self-review"`

and again at the start of Step 2 with `--msg "codex review"`. Step 4's `done`
report is unchanged — there is no `complete` phase, because the lifecycle status
already says it.
```

- [ ] **Step 3: Document the `/report progress` form**

In `.claude/skills/report/SKILL.md`, add to the Usage section after the `/report done` bullet (`report/SKILL.md:23`):

```markdown
- First word is `progress` → parse `progress <phase> [N/total] <message>[; next: <next>]`
  and run:
  `python <path>/orch.py progress --agent <AGENT> --phase <phase> [--step N --step-total total] --msg "<message>" [--next "<next>"]`
  Valid phases: `setup` · `investigation` · `planning` · `awaiting_approval` ·
  `implementation` · `checkpoint` · `blocked`. Example:
  `/report progress implementation 3/6 wiring the CLI; next: status output`
```

And to the Notes section:

```markdown
- Progress never changes the task's status and never pings the human — it is
  telemetry the orchestrator reads. Use `/report blocked` when you actually need
  intervention (that one also records a `blocked` phase for you).
```

- [ ] **Step 4: Verify against the spec**

Re-read the reporting-points table in
`docs/superpowers/specs/2026-08-12-worker-progress-reporting-design.md` and confirm
each of the eight rows has a corresponding instruction in one of the three files.
Row 7 (`done`) and row 8 (`blocked`) are covered by existing behaviour plus Task 3.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/work/SKILL.md .claude/skills/checkpoint/SKILL.md .claude/skills/report/SKILL.md
git commit -m "docs(progress): worker skills report phase and plan-step progress"
```

---

### Task 8: The orchestrator reads progress

**Files:**
- Modify: `.claude/skills/orchestrate/SKILL.md`

**Interfaces:**
- Consumes: `orch status --json` with the `progress` key, from Task 5.
- Produces: no code.

- [ ] **Step 1: Add the reading section**

In `.claude/skills/orchestrate/SKILL.md`, insert a new section between the Preflight section and "## When the human tells you an agent finished" (i.e. after `orchestrate/SKILL.md:40`):

```markdown
## Reading worker progress

Workers report what they are doing through `orch progress`. Every task in
`orch status --json` carries a `progress` object (or `null` if nothing was
reported):

```json
"progress": {"phase": "implementation", "step": 3, "step_total": 6,
             "message": "wiring the orch progress CLI",
             "next_step": "status output",
             "updated_at": "2026-08-12T10:30:00Z"}
```

Phases: `setup` · `investigation` · `planning` · `awaiting_approval` ·
`implementation` · `checkpoint` · `blocked`.

- **Open every invocation with a roll call.** Before anything else, read
  `orch status --json` and give the human one line per active agent from these
  snapshots — phase, `N/total` where present, and the message. This is how the
  human learns how much work is left without asking each window.
- **Read the structured fields, never the prose.** The `progress` object is
  authoritative; don't parse phases out of event messages.
- **A late phase is NOT a merge signal.** `phase=checkpoint` means the worker is
  reviewing its own code — it is not done, and it may still fail its own review.
  Only `status=done`, plus the branch, plus a green test run authorizes a merge.
  Never merge because progress "looks nearly finished."
- **Old progress is information, not a verdict.** An agent sitting on
  `awaiting_approval` for an hour is waiting on the human, not broken. Surface
  it; don't diagnose it.
```

- [ ] **Step 2: Carry the last phase into merge-blocked notifications**

In `.claude/skills/orchestrate/SKILL.md`, in the "Tests fail after a clean/resolved merge" bullet (`orchestrate/SKILL.md:110-119`), change the `orch notify` line to:

```markdown
     `orch notify --msg "Merge blocked on task <id>: <why> (last progress: <phase> <N/total> — <message>)" --title "Orchestrator needs input"`.
```

- [ ] **Step 3: Note it in the Rules**

Add to the Rules section at the bottom of `.claude/skills/orchestrate/SKILL.md`:

```markdown
- Progress is informational. It tells you what an agent is doing and how far in
  it is — it never authorizes a merge and never changes a task's status.
```

- [ ] **Step 4: Verify**

Re-read the `/orchestrate` section of the spec and confirm all three changes are
present: the reading section, the roll call, and the explicit "a late phase is not
a merge signal" rule.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/orchestrate/SKILL.md
git commit -m "docs(progress): orchestrator reads progress, roll call, not a merge gate"
```

---

### Task 9: README and full-suite verification

**Files:**
- Modify: `README.md`
- Possibly delete: `progress-reporting-spec.md` (the superseded draft — Step 6 asks the human; never delete it unprompted)

**Interfaces:**
- Consumes: everything above.
- Produces: nothing new.

- [ ] **Step 1: Document the command**

In `README.md`, add to the Commands table, immediately after the `report` row:

```markdown
| `progress --agent A --phase P [--step N --step-total M --msg --next --task --json]` | record what this worker is doing and how far into its plan it is; phases: `setup` `investigation` `planning` `awaiting_approval` `implementation` `checkpoint` `blocked`. Never changes task status, never pings the human |
```

- [ ] **Step 2: Explain the model**

In `README.md`, add a short subsection immediately after the "Waiting on the human" paragraph:

```markdown
**Worker progress.** Lifecycle status answers "what state is this task in?";
progress answers "what is the worker doing, and how much is left?" Workers call
`orch progress` at phase boundaries and at the start of each plan task, carrying
`step N/total` taken from the plan's task count. It is event-driven — there is no
heartbeat and no timer — and purely informational: progress never changes a task's
status, never raises `needs_human`, and never authorizes a merge. `orch status`
shows the latest snapshot per agent; `--json` exposes it as a `progress` object
(`null` when nothing was reported).
```

- [ ] **Step 3: Mention it in the skills list**

In `README.md`, in the Skills section, extend the `/report` bullet:

```markdown
- **`/report <status> <message>`** — worker shortcut to record progress
  (`executing`/`done`/`blocked`/`note`), plus `/report progress <phase> [N/total]
  <message>` for a structured progress update.
```

- [ ] **Step 4: Run the complete suite**

Run: `python -m pytest -q`
Expected: PASS — every test, old and new.

- [ ] **Step 5: Smoke-test the real flow end to end**

```bash
python orch.py init smoke
python orch.py task add --project smoke --agent A --title "smoke" --status executing
python orch.py progress --project smoke --agent A --phase implementation --step 1 --step-total 3 --msg "first task" --next "second task"
python orch.py status --project smoke
python orch.py status --project smoke --json
```

Expected: the status output shows `implementation 1/3 · first task`, a `next:` line,
and an age; the JSON carries a populated `progress` object.

- [ ] **Step 6: Retire the superseded draft**

Ask the human whether to delete `progress-reporting-spec.md` (untracked, superseded
by the spec in `docs/superpowers/specs/`) or keep it. Do not delete it unprompted.

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs(progress): document the progress command and model"
```

---

## Verification checklist

Against the spec's acceptance criteria:

1. A worker on a multi-task plan leaves milestones automatically — Tasks 7, 8.
2. `orch status` and `--json` show phase, step, message, next step, update time — Task 5.
3. `/orchestrate` can state who is where, including work remaining — Task 8.
4. Progress never alters lifecycle status or raises `needs_human` — Tasks 1, 2 (tested).
5. A late phase never triggers a merge — Task 8.
6. Existing databases, tasks, commands, merge behaviour unaffected — Task 1 (migration tests), full suite each task.
7. Tests cover migration, validation, persistence, CLI, rendering, compatibility — Tasks 1-6.
