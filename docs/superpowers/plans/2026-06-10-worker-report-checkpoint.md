# Worker `/report` + generic `/checkpoint` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make worker reporting frictionless — a tested `orch report` command plus thin `/report` and generic `/checkpoint` skills, wired into `/work`.

**Architecture:** New focused `orch/report.py` holds the reporting logic (git-branch auto-detect, blocked-notify, delegation to `db.post_event`); a `report` CLI subcommand resolves identity from `--agent`/`ORCH_AGENT` and calls it. Two markdown skills (`/report`, `/checkpoint`) sit on top, and `/work` is updated to use them.

**Tech Stack:** Python 3 standard library only — `sqlite3`, `subprocess`, `argparse`, `unittest`. No pip installs.

---

## File Structure

- `orch/report.py` — CREATE: `current_branch()` + `report()` (the tested logic)
- `orch/cli.py` — MODIFY: add `cmd_report` + `report` subparser
- `.claude/skills/report/SKILL.md` — CREATE: thin `/report` wrapper
- `.claude/skills/checkpoint/SKILL.md` — CREATE: generic post-work flow with reporting
- `.claude/skills/work/SKILL.md` — MODIFY: use `/report` and `/checkpoint`
- `tests/test_report.py` — CREATE: unit tests for `report()` + `current_branch()`
- `tests/test_cli.py` — MODIFY: `report` command tests
- `README.md` — MODIFY: document `report`, the skills, `ORCH_AGENT`, user-level install

---

### Task 1: `orch/report.py` — `current_branch` + `report`

**Files:**
- Create: `orch/report.py`
- Create: `tests/test_report.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report.py
import os
import tempfile
import unittest

from orch import db, report


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")
        self.tid = db.add_task(self.conn, "demo", "A", "x",
                               status="discussing")

    def _task(self):
        return self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (self.tid,)).fetchone()

    def test_note_posts_note_without_status_change(self):
        report.report(self.conn, "demo", "A", "note", msg="hi")
        ev = self.conn.execute(
            "SELECT kind, message FROM events ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(ev["kind"], "note")
        self.assertEqual(self._task()["status"], "discussing")

    def test_executing_updates_task(self):
        report.report(self.conn, "demo", "A", "executing", msg="go")
        self.assertEqual(self._task()["status"], "executing")

    def test_done_with_explicit_branch(self):
        report.report(self.conn, "demo", "A", "done", branch="feat/x")
        self.assertEqual(self._task()["status"], "done")
        self.assertEqual(self._task()["branch"], "feat/x")

    def test_done_autodetects_branch(self):
        orig = report.current_branch
        report.current_branch = lambda cwd=None: "auto/branch"
        try:
            report.report(self.conn, "demo", "A", "done")
        finally:
            report.current_branch = orig
        self.assertEqual(self._task()["branch"], "auto/branch")

    def test_blocked_notifies(self):
        calls = []
        report.report(self.conn, "demo", "A", "blocked", msg="stuck",
                      notifier=lambda m, title=None: calls.append((m, title)))
        self.assertEqual(self._task()["status"], "blocked")
        self.assertEqual(len(calls), 1)
        self.assertIn("stuck", calls[0][0])

    def test_current_branch_returns_str_or_none(self):
        b = report.current_branch()
        self.assertTrue(b is None or isinstance(b, str))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'orch.report'`.

- [ ] **Step 3: Write `orch/report.py`**

```python
import subprocess

from orch import db
from orch import notify as notify_mod


def current_branch(cwd=None):
    try:
        out = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=cwd, timeout=5)
        if out.returncode == 0:
            branch = out.stdout.strip()
            return branch or None
    except Exception:
        return None
    return None


def report(conn, project, agent, status, msg="", branch=None,
           notifier=notify_mod.send):
    if status == "note":
        return db.post_event(conn, project, agent, kind="note", message=msg)

    eff_branch = branch
    if status == "done" and eff_branch is None:
        eff_branch = current_branch()

    eid = db.post_event(conn, project, agent, kind="status",
                        message=msg, status=status, branch=eff_branch)

    if status == "blocked":
        notifier(f"Agent {agent} blocked: {msg}", title="Blocked")

    return eid
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_report.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add orch/report.py tests/test_report.py
git commit -m "feat: report() with branch auto-detect and blocked-notify"
```

---

### Task 2: `orch report` CLI command

**Files:**
- Modify: `orch/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_cli.py, inside CLITest
    def _run_agent(self, args, agent="A"):
        env = dict(os.environ, ORCH_DB=self.db, ORCH_AGENT=agent)
        for k in ("ORCH_TG_TOKEN", "ORCH_TG_CHAT", "ORCH_TG_CONFIG"):
            env.pop(k, None)
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "orch.py"), *args],
            capture_output=True, text=True, env=env)

    def test_report_executing_uses_env_agent(self):
        run(["init", "demo"], self.db)
        run(["task", "add", "--project", "demo", "--agent", "A",
             "--title", "X", "--status", "discussing"], self.db)
        out = self._run_agent(
            ["report", "--project", "demo", "--status", "executing",
             "--msg", "go"])
        self.assertEqual(out.returncode, 0)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["status"], "executing")

    def test_report_done_records_branch(self):
        run(["init", "demo"], self.db)
        run(["task", "add", "--project", "demo", "--agent", "A",
             "--title", "X", "--status", "executing"], self.db)
        out = self._run_agent(
            ["report", "--project", "demo", "--status", "done",
             "--branch", "feat/z"])
        self.assertEqual(out.returncode, 0)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["status"], "done")
        self.assertEqual(state["tasks"][0]["branch"], "feat/z")

    def test_report_blocked_notifies_dry_run(self):
        run(["init", "demo"], self.db)
        run(["task", "add", "--project", "demo", "--agent", "A",
             "--title", "X", "--status", "executing"], self.db)
        out = self._run_agent(
            ["report", "--project", "demo", "--status", "blocked",
             "--msg", "stuck"])
        self.assertEqual(out.returncode, 0)
        self.assertIn("dry-run", out.stdout)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["status"], "blocked")

    def test_report_agent_flag_overrides_env(self):
        run(["init", "demo"], self.db)
        run(["task", "add", "--project", "demo", "--agent", "B",
             "--title", "Y", "--status", "executing"], self.db)
        out = self._run_agent(
            ["report", "--project", "demo", "--agent", "B",
             "--status", "done", "--branch", "b/x"])
        self.assertEqual(out.returncode, 0)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["status"], "done")

    def test_report_missing_identity_errors(self):
        run(["init", "demo"], self.db)
        env = dict(os.environ, ORCH_DB=self.db)
        env.pop("ORCH_AGENT", None)
        out = subprocess.run(
            [sys.executable, os.path.join(ROOT, "orch.py"),
             "report", "--project", "demo", "--status", "note",
             "--msg", "hi"],
            capture_output=True, text=True, env=env)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("agent", out.stderr.lower())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::CLITest::test_report_executing_uses_env_agent -q`
Expected: FAIL — argparse `invalid choice: 'report'`.

- [ ] **Step 3: Add the handler and parser**

In `orch/cli.py`, add the handler above `build_parser`:

```python
def cmd_report(conn, args):
    import os
    from orch import report as report_mod
    agent = args.agent or os.environ.get("ORCH_AGENT")
    if not agent:
        print("error: no agent given (use --agent or ORCH_AGENT)",
              file=sys.stderr)
        return 1
    report_mod.report(conn, _project(args), agent, args.status,
                      msg=args.msg, branch=args.branch)
    print("reported")
    return 0
```

In `orch/cli.py`, in `build_parser`, add before `return p`:

```python
    pr = sub.add_parser("report")
    pr.add_argument("--project")
    pr.add_argument("--agent")
    pr.add_argument("--status", required=True,
                    choices=["executing", "done", "blocked", "note"])
    pr.add_argument("--msg", default="")
    pr.add_argument("--branch")
    pr.set_defaults(func=cmd_report)
```

Note: `report` resolves the project via `_project(args)`, which raises a clean
`NotFound` (caught by `main`) if neither `--project` nor `ORCH_PROJECT` is set.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py -q`
Expected: PASS (all CLI tests).

- [ ] **Step 5: Commit**

```bash
git add orch/cli.py tests/test_cli.py
git commit -m "feat: orch report command with env-agent identity"
```

---

### Task 3: The `/report` skill

**Files:**
- Create: `.claude/skills/report/SKILL.md`

- [ ] **Step 1: Write the skill**

```markdown
---
name: report
description: One-word progress reporting for a worker agent in the orchestrator system. Usage `/report <status> <message>` (e.g. `/report executing wiring auth`, `/report blocked need API key`, `/report done`). Wraps `orch report`.
user-invocable: true
---

# Report

Report your progress to the orchestrator with no flags to remember. You are a worker
agent; your identity is in `ORCH_AGENT` and the project in `ORCH_PROJECT` (set per
window). Resolve `<path>` = the orchestrator repo path.

## Usage

`/report <status> <message>` where `<status>` is one of
`executing` · `done` · `blocked` · `note`.

- First word is a known status → run:
  `python <path>/orch.py report --status <status> --msg "<the rest>"`
- First word is NOT a known status → treat the whole input as a note:
  `python <path>/orch.py report --status note --msg "<the whole input>"`
- `/report done` needs no message — the branch is auto-detected from git.

## Notes

- `blocked` automatically pings the human on Telegram — use it only when you truly need
  intervention.
- Keep messages short; report often so the orchestrator and dashboard stay live.
- Do not pass `--agent`/`--project`; they come from `ORCH_AGENT`/`ORCH_PROJECT`.
```

- [ ] **Step 2: Verify the suite still passes (no code change)**

Run: `python -m pytest -q`
Expected: PASS (unchanged — markdown only).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/report/SKILL.md
git commit -m "feat: /report worker reporting skill"
```

---

### Task 4: The generic `/checkpoint` skill

**Files:**
- Create: `.claude/skills/checkpoint/SKILL.md`

- [ ] **Step 1: Write the skill**

```markdown
---
name: checkpoint
description: Project-agnostic post-work workflow for orchestrator worker agents. Runs code review, optional Codex review, commit, and auto-reports done to the orch DB. Invoke with /checkpoint after finishing a plan.
user-invocable: true
---

# Checkpoint — Worker Post-Work Workflow

Run this after completing the plan's implementation, before the work is considered
done. Execute the steps in order; do not skip Step 1 or Step 4.

Resolve `<path>` = the orchestrator repo path. Your identity is `ORCH_AGENT`, project
`ORCH_PROJECT`.

## Step 1 — Code Review

Run `/code-review` on all changed code at an honestly chosen effort level:
- `/code-review low` — trivial change (typo, one-line tweak, mechanical rename)
- `/code-review` (default) — normal feature work or a single-area refactor
- `/code-review high` — risky or large change: new module, cross-cutting refactor,
  migration, anything touching money or production data

If unsure between two levels, go higher. Apply any fixes it makes; if it changed code,
note what changed.

## Step 2 — Codex Review (optional)

If the `codex` plugin is available, get a second opinion:
1. Invoke `/codex:rescue` (review-only): summarize what changed, point at the
   diff/files, ask for feedback on correctness/design/risk. Be explicit it is a review
   pass, not an edit pass.
2. Reason critically about the output — do not accept it at face value.
3. Present your analysis (agree/disagree + why) and discuss with the user.
4. Apply agreed changes, then re-run `/code-review` if code was modified.

If the `codex` plugin is not installed, or the user says "skip codex," go to Step 3.

## Step 3 — Commit

1. `git status` and `git diff` to review all changes.
2. Draft a clear commit message in English describing the "why."
3. Commit to your working branch (HEREDOC format, Co-Authored-By line).

## Step 4 — Report Done

Report completion to the orchestrator (auto-detects the branch):

`python <path>/orch.py report --status done --msg "ready for review"`

Do NOT update Linear — in the orchestrator system the orchestrator owns Linear updates
when it merges your branch. Your job ends at a committed branch + a `done` report.
```

- [ ] **Step 2: Verify the suite still passes (no code change)**

Run: `python -m pytest -q`
Expected: PASS (unchanged — markdown only).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/checkpoint/SKILL.md
git commit -m "feat: generic /checkpoint worker post-work skill"
```

---

### Task 5: Update `/work` to use `/report` and `/checkpoint`

**Files:**
- Modify: `.claude/skills/work/SKILL.md`

- [ ] **Step 1: Replace the raw post commands**

In `.claude/skills/work/SKILL.md`, replace the `2. Branch on status:` `queued`
sub-bullet block (the lines from `Post the signal:` through the brainstorm bullet's
`orch post` usage) so the progress post uses `/report`. Specifically, replace:

```
     - Post the signal: `orch post --agent <AGENT> --kind needs_discussion --msg "claimed, awaiting brainstorm"`
```

with:

```
     - Post the signal: `orch post --agent <AGENT> --kind needs_discussion --msg "claimed, awaiting brainstorm"` (this specific kind has no /report alias; use it as-is)
```

In `.claude/skills/work/SKILL.md`, replace the entire `3. Execute (after plan
approval):` block with:

```
3. **Execute (after plan approval):**
   - `/report executing executing plan` (flips the task to `executing`).
   - Implement the plan via `superpowers:executing-plans`. After each plan task:
     `/report plan task N done` (recorded as a note).
   - Self-review and finish with `/checkpoint` — it runs code review, optional Codex
     review, commits your branch, and reports `done` for you.
```

In `.claude/skills/work/SKILL.md`, replace the entire `4. Finish:` block with:

```
4. **Finish:**
   - `/checkpoint` (Step 3 above) already reported `done`. Loop back to step 1 for the
     next task.
```

In `.claude/skills/work/SKILL.md`, replace the `## Blockers` body with:

```
If you cannot proceed at any point:
- `/report blocked <why>` — records the blocker and pings the human automatically.
- End the turn and wait for the human.
```

In `.claude/skills/work/SKILL.md`, in the `## Rules` list, replace the last bullet:

```
- Keep `orch` posts short and frequent so the orchestrator and dashboard see live
  progress.
```

with:

```
- Report via `/report` (short, frequent) so the orchestrator and dashboard stay live.
- `ORCH_AGENT` and `ORCH_PROJECT` must be exported in this window so `/report` and
  `/checkpoint` know who and where you are.
```

- [ ] **Step 2: Verify the suite still passes (no code change)**

Run: `python -m pytest -q`
Expected: PASS (unchanged — markdown only).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/work/SKILL.md
git commit -m "feat: /work uses /report and /checkpoint"
```

---

### Task 6: README — `report`, skills, `ORCH_AGENT`, install

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the `report` row to the commands table**

In `README.md`, in the `## Commands` table, add this row immediately after the
`claim ...` row:

```markdown
| `report --status S [--msg --agent --branch]` | worker shortcut: post `executing\|done\|blocked\|note`; agent from `ORCH_AGENT`; `done` auto-detects branch; `blocked` pings you |
```

- [ ] **Step 2: Expand the skills section**

In `README.md`, in the `## Skills (the autonomous loop)` list, add these two bullets
after the `/orchestrate` bullet:

```markdown
- **`/report <status> <message>`** — worker shortcut to record progress
  (`executing`/`done`/`blocked`/`note`); no flags to remember.
- **`/checkpoint`** — worker post-work flow: code review → optional Codex review →
  commit → auto-report `done`. Does not touch Linear (the orchestrator owns that).
```

- [ ] **Step 3: Document `ORCH_AGENT` and user-level install**

In `README.md`, immediately after the `## Skills (the autonomous loop)` section
(before `## Telegram notifications`), add:

```markdown
## Installing skills for worker windows

Worker agents run inside the *target* projects they build, not this repo, so the
skills must be reachable everywhere. Install them at user level — symlink (or copy)
this repo's `.claude/skills/*` into `~/.claude/skills/`:

```bash
ln -s "$(pwd)/.claude/skills/work" ~/.claude/skills/work
ln -s "$(pwd)/.claude/skills/report" ~/.claude/skills/report
ln -s "$(pwd)/.claude/skills/checkpoint" ~/.claude/skills/checkpoint
ln -s "$(pwd)/.claude/skills/orchestrate" ~/.claude/skills/orchestrate
```

Per worker window, export both identity vars before starting `/loop /work A`:

```bash
export ORCH_PROJECT=myproject
export ORCH_AGENT=A
```
```

- [ ] **Step 4: Verify the suite still passes**

Run: `python -m pytest -q`
Expected: PASS (unchanged — docs only).

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: report command, report/checkpoint skills, ORCH_AGENT install"
```

---

## Notes for the implementer

- **Run from the repo root** so `python orch.py ...` and `python -m pytest` resolve the
  `orch` package. Tests set `ORCH_DB`/`ORCH_AGENT`/`ORCH_TG_*` to temp/cleared values,
  so they never touch your real DB or send real Telegram messages.
- **`unittest` fallback:** every test file also runs under
  `python -m unittest discover -s tests -v`.
- **TDD discipline:** write the test, watch it fail, implement, watch it pass, commit.
  Skill/README tasks (3-6) have no unit tests — verify the suite is still green and
  commit.
```
