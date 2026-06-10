# Autonomous Loop (v2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Layer an autonomous loop on the v1 comm layer — worker agents poll for kickoff tasks, brainstorm with the human, then execute/self-review/report automatically; a looping orchestrator merges finished work; Telegram pings summon the human only when needed.

**Architecture:** Extend `orch/db.py` (new columns, widened status enum, `next_task`/`claim_next`), add CLI commands (`next`, `claim`, `notify`) and a `orch/notify.py` Telegram helper, refresh the dashboard CSS, and add two skills (`/work <AGENT>`, `/orchestrate`) that sequence existing superpowers skills around the `orch` CLI.

**Tech Stack:** Python 3 standard library only — `sqlite3`, `argparse`, `urllib.request`, `json`, `unittest`. No pip installs.

**Clean-slate note:** The user has no real data, so there is no migration. The new columns are added directly to `CREATE TABLE`. If a stale dev DB exists at `~/.orchestrator/state.db`, delete it before manual testing. All automated tests use a temp `ORCH_DB`, so they are unaffected.

---

## File Structure

- `orch/db.py` — MODIFY: schema columns `context`/`plan_path`, `TASK_STATUSES`/`ACTIVE_STATUSES`, `add_task`/`update_task` params, new `next_task`/`claim_next`
- `orch/cli.py` — MODIFY: `task add`/`task update` flags, `post --kind` choices, new `next`/`claim`/`notify` subcommands
- `orch/notify.py` — CREATE: `resolve_creds` + `send` (Telegram Bot API, dry-run fallback)
- `orch/dashboard.py` — MODIFY: badge CSS classes for the new statuses
- `.claude/skills/work/SKILL.md` — CREATE: the worker loop skill
- `.claude/skills/orchestrate/SKILL.md` — CREATE: the orchestrator loop skill
- `.claude/skills/orchestrating/SKILL.md` — DELETE: superseded by `orchestrate`
- `tests/test_db.py` — MODIFY: update v1 tests to v2 statuses; add `next_task`/`claim_next` tests
- `tests/test_cli.py` — MODIFY/ADD: new-flag and new-command tests
- `tests/test_server.py` — MODIFY: v2 statuses in setup/assert
- `tests/test_notify.py` — CREATE: notify unit tests
- `README.md` — MODIFY: document v2 commands, skills, env vars

---

### Task 1: Schema columns, widened statuses, `add_task` gains `status`/`context`

**Files:**
- Modify: `orch/db.py`
- Modify: `tests/test_db.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Update the failing tests**

In `tests/test_db.py`, replace the `test_add_task_returns_id_and_defaults_todo` method (in `TaskTest`) with:

```python
    def test_add_task_defaults_queued_and_stores_context(self):
        tid = db.add_task(self.conn, "demo", "B", "build X",
                          issue_ref="LIN-1", context="do the thing next")
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()
        self.assertEqual(row["status"], "queued")
        self.assertEqual(row["agent"], "B")
        self.assertEqual(row["issue_ref"], "LIN-1")
        self.assertEqual(row["context"], "do the thing next")
        self.assertIsNone(row["plan_path"])

    def test_add_task_accepts_explicit_status(self):
        tid = db.add_task(self.conn, "demo", "B", "x", status="executing")
        row = self.conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (tid,)).fetchone()
        self.assertEqual(row["status"], "executing")
```

In `tests/test_db.py`, in `DBSetupTest.test_connect_creates_schema_and_wal`, append a column check after the table-name assertion:

```python
        cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)")}
        self.assertTrue({"context", "plan_path"}.issubset(cols))
```

In `tests/test_db.py`, in `StateTest.test_get_state_shape`, change the `post_event` status from `"in_progress"` to `"executing"` and the agent-status assertion accordingly:

```python
        db.post_event(self.conn, "demo", "B", status="executing",
                     message="starting")
        ...
        self.assertEqual(agents["B"]["status"], "executing")
```

In `tests/test_server.py`, in `ServerTest.setUp`, change the seeded event status, and in `test_api_state_returns_json` change the assertion:

```python
        db.post_event(conn, "demo", "B", status="executing", message="go")
        ...
        self.assertEqual(state["agents"][0]["status"], "executing")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_db.py::TaskTest::test_add_task_defaults_queued_and_stores_context tests/test_db.py::DBSetupTest -q`
Expected: FAIL — `add_task() got an unexpected keyword argument 'context'` and/or missing columns.

- [ ] **Step 3: Update the schema and enums**

In `orch/db.py`, replace the `tasks` table block inside `SCHEMA` with:

```python
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
```

In `orch/db.py`, replace the two status constants with:

```python
ACTIVE_STATUSES = ("queued", "discussing", "executing", "blocked")
TASK_STATUSES = ("queued", "discussing", "executing", "blocked",
                 "done", "merged")
```

- [ ] **Step 4: Update `add_task`**

In `orch/db.py`, replace the whole `add_task` function with:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_db.py tests/test_server.py -q`
Expected: PASS (all db + server tests).

- [ ] **Step 6: Commit**

```bash
git add orch/db.py tests/test_db.py tests/test_server.py
git commit -m "feat: v2 schema columns and widened status enum"
```

---

### Task 2: `update_task` gains `plan_path` and `context`

**Files:**
- Modify: `orch/db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_db.py, inside TaskTest
    def test_update_task_sets_plan_and_context(self):
        tid = db.add_task(self.conn, "demo", "B", "build X")
        db.update_task(self.conn, tid,
                       plan_path="docs/plan.md", context="revised brief")
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        self.assertEqual(row["plan_path"], "docs/plan.md")
        self.assertEqual(row["context"], "revised brief")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py::TaskTest::test_update_task_sets_plan_and_context -q`
Expected: FAIL — `update_task() got an unexpected keyword argument 'plan_path'`.

- [ ] **Step 3: Update `update_task`**

In `orch/db.py`, replace the whole `update_task` function with:

```python
def update_task(conn, task_id, status=None, branch=None, issue_ref=None,
                plan_path=None, context=None):
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py::TaskTest -q`
Expected: PASS (all TaskTest cases).

- [ ] **Step 5: Commit**

```bash
git add orch/db.py tests/test_db.py
git commit -m "feat: update_task accepts plan_path and context"
```

---

### Task 3: `next_task` — the worker heartbeat query

**Files:**
- Modify: `orch/db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_db.py
class NextTaskTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")

    def test_next_task_none_when_empty(self):
        self.assertIsNone(db.next_task(self.conn, "demo", "A"))

    def test_next_task_returns_oldest_active_for_agent(self):
        t1 = db.add_task(self.conn, "demo", "A", "first")
        db.add_task(self.conn, "demo", "A", "second")
        nxt = db.next_task(self.conn, "demo", "A")
        self.assertEqual(nxt["id"], t1)

    def test_next_task_ignores_closed_and_other_agents(self):
        db.add_task(self.conn, "demo", "A", "done one", status="merged")
        db.add_task(self.conn, "demo", "B", "b task")
        self.assertIsNone(db.next_task(self.conn, "demo", "A"))

    def test_next_task_includes_discussing_and_executing(self):
        tid = db.add_task(self.conn, "demo", "A", "x", status="executing")
        nxt = db.next_task(self.conn, "demo", "A")
        self.assertEqual(nxt["id"], tid)
        self.assertEqual(nxt["status"], "executing")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py::NextTaskTest -q`
Expected: FAIL — `AttributeError: module 'orch.db' has no attribute 'next_task'`.

- [ ] **Step 3: Write `next_task`**

```python
# add to orch/db.py (after get_state)
def next_task(conn, project, agent):
    pid = require_project(conn, project)["id"]
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    row = conn.execute(
        f"SELECT * FROM tasks WHERE project_id = ? AND agent = ? "
        f"AND status IN ({placeholders}) ORDER BY created_at, id LIMIT 1",
        (pid, agent, *ACTIVE_STATUSES),
    ).fetchone()
    return dict(row) if row else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py::NextTaskTest -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add orch/db.py tests/test_db.py
git commit -m "feat: next_task heartbeat query"
```

---

### Task 4: `claim_next` — atomic queued→discussing

**Files:**
- Modify: `orch/db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_db.py
class ClaimTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")

    def test_claim_transitions_oldest_queued(self):
        t1 = db.add_task(self.conn, "demo", "A", "first")
        db.add_task(self.conn, "demo", "A", "second")
        claimed = db.claim_next(self.conn, "demo", "A")
        self.assertEqual(claimed["id"], t1)
        self.assertEqual(claimed["status"], "discussing")
        row = self.conn.execute(
            "SELECT status FROM tasks WHERE id=?", (t1,)).fetchone()
        self.assertEqual(row["status"], "discussing")

    def test_claim_returns_none_when_nothing_queued(self):
        db.add_task(self.conn, "demo", "A", "x", status="executing")
        self.assertIsNone(db.claim_next(self.conn, "demo", "A"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py::ClaimTest -q`
Expected: FAIL — `AttributeError: ... 'claim_next'`.

- [ ] **Step 3: Write `claim_next`**

```python
# add to orch/db.py (after next_task)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py::ClaimTest -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add orch/db.py tests/test_db.py
git commit -m "feat: claim_next atomic queued-to-discussing"
```

---

### Task 5: CLI — `task add`/`task update` flags, `post` new kind

**Files:**
- Modify: `orch/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_cli.py, inside CLITest
    def test_task_add_context_and_status_persist(self):
        run(["init", "demo"], self.db)
        add = run(["task", "add", "--project", "demo", "--agent", "A",
                   "--title", "X", "--context", "kickoff brief",
                   "--status", "queued"], self.db)
        self.assertEqual(add.returncode, 0)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["context"], "kickoff brief")
        self.assertEqual(state["tasks"][0]["status"], "queued")

    def test_task_update_plan_path(self):
        run(["init", "demo"], self.db)
        add = run(["task", "add", "--project", "demo", "--agent", "A",
                   "--title", "X"], self.db)
        tid = int(add.stdout.strip().split()[-1])
        upd = run(["task", "update", "--project", "demo", "--task", str(tid),
                   "--plan", "docs/p.md"], self.db)
        self.assertEqual(upd.returncode, 0)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["plan_path"], "docs/p.md")

    def test_post_needs_discussion_kind(self):
        run(["init", "demo"], self.db)
        run(["task", "add", "--project", "demo", "--agent", "A",
             "--title", "X"], self.db)
        out = run(["post", "--project", "demo", "--agent", "A",
                   "--kind", "needs_discussion", "--msg", "come talk"], self.db)
        self.assertEqual(out.returncode, 0)
        log = run(["log", "--project", "demo"], self.db)
        self.assertIn("needs_discussion", log.stdout)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::CLITest::test_task_add_context_and_status_persist tests/test_cli.py::CLITest::test_post_needs_discussion_kind -q`
Expected: FAIL — argparse `unrecognized arguments: --context` and `invalid choice: 'needs_discussion'`.

- [ ] **Step 3: Update `cmd_task_add`, `cmd_task_update`, and the parsers**

In `orch/cli.py`, replace `cmd_task_add` and `cmd_task_update` with:

```python
def cmd_task_add(conn, args):
    tid = db.add_task(conn, _project(args), args.agent, args.title,
                      issue_ref=args.issue, branch=args.branch,
                      worktree=args.worktree, context=args.context,
                      status=args.status)
    print(f"task added: {tid}")
    return 0


def cmd_task_update(conn, args):
    db.update_task(conn, args.task, status=args.status,
                   branch=args.branch, issue_ref=args.issue,
                   plan_path=args.plan, context=args.context)
    print(f"task {args.task} updated")
    return 0
```

In `orch/cli.py`, in `build_parser`, replace the `ta` (task add) block with:

```python
    ta = tsub.add_parser("add")
    ta.add_argument("--project")
    ta.add_argument("--agent", required=True)
    ta.add_argument("--title", required=True)
    ta.add_argument("--issue")
    ta.add_argument("--branch")
    ta.add_argument("--worktree")
    ta.add_argument("--context")
    ta.add_argument("--status", default="queued")
    ta.set_defaults(func=cmd_task_add)
```

In `orch/cli.py`, in `build_parser`, replace the `tu` (task update) block with:

```python
    tu = tsub.add_parser("update")
    tu.add_argument("--project")
    tu.add_argument("--task", type=int, required=True)
    tu.add_argument("--status")
    tu.add_argument("--branch")
    tu.add_argument("--issue")
    tu.add_argument("--plan")
    tu.add_argument("--context")
    tu.set_defaults(func=cmd_task_update)
```

In `orch/cli.py`, in `build_parser`, update the `post` parser's `--kind` choices line to:

```python
    pp.add_argument("--kind", default="status",
                    choices=["status", "note", "blocker", "handoff",
                             "needs_discussion"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py -q`
Expected: PASS (all CLI tests).

- [ ] **Step 5: Commit**

```bash
git add orch/cli.py tests/test_cli.py
git commit -m "feat: CLI flags for context/status/plan and needs_discussion kind"
```

---

### Task 6: CLI — `next` and `claim` commands

**Files:**
- Modify: `orch/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_cli.py, inside CLITest
    def test_next_empty_then_returns_task(self):
        run(["init", "demo"], self.db)
        empty = run(["next", "--project", "demo", "--agent", "A", "--json"],
                    self.db)
        self.assertEqual(empty.returncode, 0)
        self.assertEqual(empty.stdout.strip(), "")
        run(["task", "add", "--project", "demo", "--agent", "A",
             "--title", "X"], self.db)
        got = run(["next", "--project", "demo", "--agent", "A", "--json"],
                  self.db)
        self.assertEqual(json.loads(got.stdout)["title"], "X")

    def test_claim_transitions_and_prints(self):
        run(["init", "demo"], self.db)
        run(["task", "add", "--project", "demo", "--agent", "A",
             "--title", "X"], self.db)
        claimed = run(["claim", "--project", "demo", "--agent", "A",
                       "--json"], self.db)
        self.assertEqual(claimed.returncode, 0)
        self.assertEqual(json.loads(claimed.stdout)["status"], "discussing")
        # second claim finds nothing queued
        again = run(["claim", "--project", "demo", "--agent", "A", "--json"],
                    self.db)
        self.assertEqual(again.stdout.strip(), "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::CLITest::test_next_empty_then_returns_task tests/test_cli.py::CLITest::test_claim_transitions_and_prints -q`
Expected: FAIL — argparse `invalid choice: 'next'` / `'claim'`.

- [ ] **Step 3: Add the command handlers and parsers**

In `orch/cli.py`, add these handlers above `build_parser`:

```python
def cmd_next(conn, args):
    task = db.next_task(conn, _project(args), args.agent)
    if task is None:
        if not args.json:
            print("no task")
        return 0
    if args.json:
        print(json.dumps(task, indent=2))
    else:
        print(f"{task['id']} {task['status']} {task['title']}")
    return 0


def cmd_claim(conn, args):
    task = db.claim_next(conn, _project(args), args.agent)
    if task is None:
        if not args.json:
            print("no queued task")
        return 0
    if args.json:
        print(json.dumps(task, indent=2))
    else:
        print(f"claimed {task['id']}: {task['title']}")
    return 0
```

In `orch/cli.py`, in `build_parser`, add these before `return p`:

```python
    pn = sub.add_parser("next")
    pn.add_argument("--project")
    pn.add_argument("--agent", required=True)
    pn.add_argument("--json", action="store_true")
    pn.set_defaults(func=cmd_next)

    pc = sub.add_parser("claim")
    pc.add_argument("--project")
    pc.add_argument("--agent", required=True)
    pc.add_argument("--json", action="store_true")
    pc.set_defaults(func=cmd_claim)
```

Note: `cmd_next`/`cmd_claim` print nothing to stdout in `--json` mode when there is no task, so the worker skill can treat empty stdout as "idle."

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py -q`
Expected: PASS (all CLI tests).

- [ ] **Step 5: Commit**

```bash
git add orch/cli.py tests/test_cli.py
git commit -m "feat: orch next and claim commands"
```

---

### Task 7: Telegram notify helper

**Files:**
- Create: `orch/notify.py`
- Create: `tests/test_notify.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_notify.py
import json
import os
import tempfile
import unittest

from orch import notify


class NotifyTest(unittest.TestCase):
    def setUp(self):
        for k in ("ORCH_TG_TOKEN", "ORCH_TG_CHAT", "ORCH_TG_CONFIG"):
            os.environ.pop(k, None)

    def tearDown(self):
        for k in ("ORCH_TG_TOKEN", "ORCH_TG_CHAT", "ORCH_TG_CONFIG"):
            os.environ.pop(k, None)

    def test_resolve_creds_from_env(self):
        os.environ["ORCH_TG_TOKEN"] = "tok"
        os.environ["ORCH_TG_CHAT"] = "123"
        self.assertEqual(notify.resolve_creds(), ("tok", "123"))

    def test_resolve_creds_from_config_file(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "telegram.json")
        with open(path, "w") as f:
            json.dump({"token": "ftok", "chat_id": 999}, f)
        os.environ["ORCH_TG_CONFIG"] = path
        self.assertEqual(notify.resolve_creds(), ("ftok", "999"))

    def test_send_dry_run_without_creds_returns_false(self):
        self.assertFalse(notify.send("hello"))

    def test_send_calls_transport_with_creds(self):
        os.environ["ORCH_TG_TOKEN"] = "tok"
        os.environ["ORCH_TG_CHAT"] = "123"
        captured = {}

        def fake(url, payload):
            captured["url"] = url
            captured["payload"] = payload

        self.assertTrue(notify.send("hi", title="A needs you",
                                    transport=fake))
        self.assertIn("bottok/sendMessage", captured["url"])
        self.assertEqual(captured["payload"]["chat_id"], "123")
        self.assertIn("A needs you", captured["payload"]["text"])
        self.assertIn("hi", captured["payload"]["text"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_notify.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'orch.notify'`.

- [ ] **Step 3: Write `orch/notify.py`**

```python
import json
import os
import urllib.request
from pathlib import Path

CONFIG = Path.home() / ".orchestrator" / "telegram.json"


def resolve_creds(config_path=None):
    token = os.environ.get("ORCH_TG_TOKEN")
    chat = os.environ.get("ORCH_TG_CHAT")
    if token and chat:
        return token, chat
    path = Path(config_path or os.environ.get("ORCH_TG_CONFIG") or CONFIG)
    if path.exists():
        data = json.loads(path.read_text())
        tok = data.get("token")
        cid = data.get("chat_id")
        if tok and cid is not None:
            return tok, str(cid)
    return None, None


def _http_post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10)


def send(msg, title=None, config_path=None, transport=_http_post):
    text = f"*{title}*\n{msg}" if title else msg
    token, chat = resolve_creds(config_path)
    if not token or not chat:
        print(f"[notify dry-run] {text}")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    transport(url, {"chat_id": chat, "text": text, "parse_mode": "Markdown"})
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_notify.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add orch/notify.py tests/test_notify.py
git commit -m "feat: telegram notify helper with dry-run fallback"
```

---

### Task 8: CLI — `notify` command

**Files:**
- Modify: `orch/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_cli.py, inside CLITest
    def test_notify_dry_run_succeeds(self):
        # No token configured -> dry-run, prints message, exit 0
        env = dict(os.environ, ORCH_DB=self.db)
        for k in ("ORCH_TG_TOKEN", "ORCH_TG_CHAT", "ORCH_TG_CONFIG"):
            env.pop(k, None)
        out = subprocess.run(
            [sys.executable, os.path.join(ROOT, "orch.py"),
             "notify", "--msg", "ping", "--title", "T"],
            capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0)
        self.assertIn("ping", out.stdout)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::CLITest::test_notify_dry_run_succeeds -q`
Expected: FAIL — argparse `invalid choice: 'notify'`.

- [ ] **Step 3: Add the handler and parser**

In `orch/cli.py`, add the handler above `build_parser`:

```python
def cmd_notify(conn, args):
    from orch.notify import send
    send(args.msg, title=args.title)
    return 0
```

In `orch/cli.py`, in `build_parser`, add before `return p`:

```python
    pnf = sub.add_parser("notify")
    pnf.add_argument("--project")
    pnf.add_argument("--msg", required=True)
    pnf.add_argument("--title")
    pnf.set_defaults(func=cmd_notify)
```

Note: `cmd_notify` ignores `conn` (a DB connection is opened by `main` regardless; harmless). It always returns 0 so a notification failure never breaks a loop.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py -q`
Expected: PASS (all CLI tests).

- [ ] **Step 5: Commit**

```bash
git add orch/cli.py tests/test_cli.py
git commit -m "feat: orch notify command"
```

---

### Task 9: Dashboard CSS for v2 statuses

**Files:**
- Modify: `orch/dashboard.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_server.py, inside ServerTest
    def test_index_has_v2_status_classes(self):
        html, _ = server.render_index("demo")
        for cls in ("queued", "discussing", "executing",
                    "blocked", "done", "merged"):
            self.assertIn("." + cls, html)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_server.py::ServerTest::test_index_has_v2_status_classes -q`
Expected: FAIL — `.discussing` / `.executing` / `.queued` not present.

- [ ] **Step 3: Update the badge CSS**

In `orch/dashboard.py`, replace the three badge-color CSS lines (currently `.todo`, `.in_progress`, `.blocked`, `.done`, `.merged`, `.idle`) with:

```python
 .queued{{background:#444}} .discussing{{background:#1f6feb}}
 .executing{{background:#0e7490}} .blocked{{background:#b54708}}
 .done{{background:#238636}} .merged{{background:#8957e5}}
 .idle{{background:#333}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_server.py -q`
Expected: PASS (all server tests).

- [ ] **Step 5: Commit**

```bash
git add orch/dashboard.py tests/test_server.py
git commit -m "feat: dashboard badge colors for v2 statuses"
```

---

### Task 10: The `/work <AGENT>` worker skill

**Files:**
- Create: `.claude/skills/work/SKILL.md`

- [ ] **Step 1: Write the skill file**

```markdown
---
name: work
description: Worker-agent loop for the orchestrator system. Run as `/loop /work A` (or B/C). Polls the orch DB for this agent's task; on a queued kickoff it pings the human and brainstorms the spec/plan, then on approval executes the plan and reports — all via the orch CLI.
---

# Work (Agent <AGENT>)

You are a **worker agent**. Your identity is the single argument passed to this
skill (e.g. `A`). You run inside `/loop /work A`, self-paced — never poll on a tight
timer; do one cycle, and if idle, let the loop reschedule you.

Resolve `<path>` = the orchestrator repo path once, and set `ORCH_PROJECT` for the
project you serve (the human tells you, or it is already exported). All commands:
`python <path>/orch.py <cmd>`.

## One cycle

1. **Find my task:** `orch next --agent <AGENT> --json`.
   - Empty output → say "idle, nothing queued" and end the turn. The loop rechecks later.
2. **Branch on `status`:**

   - **`queued`** → `orch claim --agent <AGENT> --json` to take it (→ `discussing`).
     Then:
     - `orch notify --msg "Agent <AGENT>: <title> — <context>" --title "Come discuss"`
     - Post the signal: `orch post --agent <AGENT> --kind needs_discussion --msg "claimed, awaiting brainstorm"`
     - Brainstorm WITH the human: invoke `superpowers:brainstorming`, using the
       task's `context` as the starting brief, through to `superpowers:writing-plans`.
     - When the plan file exists: `orch task update --task <id> --plan <plan_path>`.
     - Ask the human to approve the plan. On approval, continue to step 3.

   - **`discussing`** (resumed) → continue the brainstorm/plan from where it stands.

   - **`executing`** (resumed) → resume the plan from the first unchecked box.

   - **`blocked`** → do nothing; the human must intervene. End the turn.

3. **Execute (after plan approval):**
   - `orch post --agent <AGENT> --status executing --msg "executing plan"` (this also
     flips the task to `executing`).
   - Implement the plan via `superpowers:executing-plans`. After each plan task:
     `orch post --agent <AGENT> --msg "plan task N done"`.
   - Self-review: run the project's `/checkpoint` skill if present, then
     `superpowers:requesting-code-review`. Address findings.
   - Commit to a branch named `feat/<short-task-slug>`.

4. **Finish:**
   - `orch post --agent <AGENT> --status done --branch <branch> --msg "ready for review"`.
   - Loop back to step 1 for the next task.

## Blockers

If you cannot proceed at any point:
- `orch post --agent <AGENT> --status blocked --kind blocker --msg "<why>"`
- `orch notify --msg "Agent <AGENT> blocked: <why>" --title "Blocked"`
- End the turn and wait for the human.

## Rules

- Never merge to main — that is the orchestrator's job. You only push/commit a branch
  and report `done`.
- The human is only present for the brainstorm/plan-approval. Everything after
  approval is autonomous.
- Keep `orch` posts short and frequent so the orchestrator and dashboard see live
  progress.
```

- [ ] **Step 2: Verify the suite still passes (no code change)**

Run: `python -m pytest -q`
Expected: PASS (unchanged — this task only adds a markdown file).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/work/SKILL.md
git commit -m "feat: /work worker-agent loop skill"
```

---

### Task 11: The `/orchestrate` skill, remove `orchestrating`, update README

**Files:**
- Create: `.claude/skills/orchestrate/SKILL.md`
- Delete: `.claude/skills/orchestrating/SKILL.md`
- Modify: `README.md`

- [ ] **Step 1: Write the orchestrator skill**

```markdown
---
name: orchestrate
description: Lean orchestrator loop for the multi-agent system. Run as `/loop /orchestrate`. Autonomously merges finished agent branches and updates Linear; collaborates with the human to queue new kickoffs; pings the human on blockers or when direction is needed.
---

# Orchestrate

You are the **orchestrator**. You never author specs/plans and never write feature
code. You own integration and reconcile Linear with the orch DB. You run inside
`/loop /orchestrate`, self-paced.

Resolve `<path>` = this repo's path and set `ORCH_PROJECT`. All commands:
`python <path>/orch.py <cmd>`.

## Autonomous half (every cycle, no human needed)

1. `orch status --project $ORCH_PROJECT --json`.
2. For each task with status `done`:
   - Review the agent's `branch`. Merge it into `main`, then run the test suite on the
     merged result.
   - Merge clean and tests pass → update the linked Linear issue (via the Linear MCP),
     then `orch task update --task <id> --status merged`.
   - Merge conflicts OR tests fail → do NOT force it:
     `orch task update --task <id> --status blocked`,
     `orch post --agent orchestrator --task <id> --kind blocker --msg "<why>"`,
     `orch notify --msg "Merge blocked on task <id>: <why>" --title "Orchestrator needs input"`.
3. If nothing is actionable, end the turn; the loop reschedules.

## Collaborative half (when the human is in the window)

- Reconcile Linear ↔ DB. Propose the next logical step. Identify 2-3 pieces that can
  run in parallel WITHOUT touching the same files.
- On the human's confirmation, create each kickoff (lean — context only, no plan):
  `orch task add --agent A --status queued --context "<decision + why it's next>" --issue LIN-123`.
- The human may pre-queue an agent's known-next task the same way.
- If agents are idle and nothing is queued:
  `orch notify --msg "Agents idle, nothing queued — what's next?" --title "Orchestrator needs input"`
  and wait, rather than inventing work.

## Rules

- Queuing new work is collaborative — never invent and queue endless tasks yourself.
- Merge authority is centralized here; agents only report `done` on a branch.
- Use `orch post --agent orchestrator ...` for your own events so they appear in the feed.
```

- [ ] **Step 2: Remove the superseded v1 skill**

```bash
git rm .claude/skills/orchestrating/SKILL.md
```

- [ ] **Step 3: Update the README**

In `README.md`, replace the `## Commands` table and the `## Orchestrating skill`
section with:

```markdown
## Commands

| command | purpose |
|---|---|
| `init <name>` | register a project |
| `task add` | create a task (`--agent --title [--context --status --issue --branch --worktree]`); default status `queued` |
| `task update` | amend a task (`--task <id> [--status --branch --issue --plan --context]`) |
| `next --agent A [--json]` | the agent's single active task, or empty |
| `claim --agent A [--json]` | atomically take the agent's oldest `queued` task (→ `discussing`) |
| `post` | append an event; updates the task on `--status`/`--branch`; `--kind status\|note\|blocker\|handoff\|needs_discussion` |
| `status [--json]` | current agent/task state + recent events |
| `log [--agent -n]` | recent event feed |
| `notify --msg ... [--title ...]` | send a Telegram ping (dry-run if no token) |
| `serve [--port]` | on-demand web dashboard |

Task lifecycle: `queued → discussing → executing → done → merged` (plus `blocked`).

## Skills (the autonomous loop)

- **`/work <AGENT>`** — run a worker window as `/loop /work A`. Polls for its task,
  brainstorms with you on a kickoff, then executes the plan and reports.
- **`/orchestrate`** — run the orchestrator window as `/loop /orchestrate`. Merges
  finished branches, updates Linear, and pings you for direction or blockers.

Both live in `.claude/skills/`.

## Telegram notifications

`orch notify` reads `ORCH_TG_TOKEN` + `ORCH_TG_CHAT`, or a JSON file at
`~/.orchestrator/telegram.json` (`{"token": "...", "chat_id": ...}`; override the path
with `ORCH_TG_CONFIG`). With no credentials it prints the message and exits 0, so the
loop never breaks.
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (all tests across db/cli/server/notify).

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/orchestrate/SKILL.md README.md
git commit -m "feat: /orchestrate loop skill, remove v1 orchestrating, update README"
```

---

## Notes for the implementer

- **Run from the repo root** so `python orch.py ...` and `python -m pytest` resolve the
  `orch` package. Tests set `ORCH_DB`/`ORCH_TG_*` to temp values, so they never touch
  your real DB or send real Telegram messages.
- **Fresh DB:** if `~/.orchestrator/state.db` exists from earlier experiments, delete
  it before manual testing so the v2 schema is created cleanly.
- **`unittest` fallback:** every test file also runs under
  `python -m unittest discover -s tests -v`.
- **TDD discipline:** write/adjust the test, watch it fail, implement, watch it pass,
  commit. The skill files (Tasks 10-11) have no unit tests — verify the suite is still
  green and commit.
```
