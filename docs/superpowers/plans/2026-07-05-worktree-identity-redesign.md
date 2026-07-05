# Worktree Identity Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make worktree isolation enforced instead of advisory — deterministic per-task
worktree paths, isolation checks tied to the specific task, no silent de-isolation
fallback, non-blocking best-effort orchestrator cleanup, and a CLI guard against the
single most dangerous documented instruction in the review (`orch link` from inside a
worktree).

**Architecture:** Two of three changes are prose-only rewrites of existing skill steps
(`work/SKILL.md`, `orchestrate/SKILL.md`) — no new mechanism, just closing the gaps a
three-agent review found in the existing worktree-isolation and merge-cleanup steps.
The third is a small, testable code change: `orch link` refuses to run when cwd is a
git worktree, detected via the same `git rev-parse --git-dir` /
`--git-common-dir` comparison the work skill's isolation check already uses.

**Tech Stack:** Python 3.8+ stdlib (`orch/cli.py`), `unittest` + real `git`/`orch.py`
subprocess invocations (`tests/test_cli.py`), Markdown skill docs.

## Global Constraints

- No new dependencies — stdlib only, matching the rest of `orch/`.
- Every worktree path is `<linked project root>/.claude/worktrees/<agent>-<task-id>` —
  exact format, used consistently across both skill docs.
- The "work in place" fallback is removed, not hardened — worktree creation failure is
  always a hard block (`/report blocked`), never a silent degrade.
- Orchestrator cleanup never force-deletes and never blocks the task's `merged` status
  on a cleanup failure.

---

### Task 1: Guard `orch link` against running inside a worktree

**Files:**
- Modify: `orch/cli.py` (add `_is_inside_worktree` helper; guard `cmd_link`)
- Test: `tests/test_cli.py` (add `test_link_refuses_inside_worktree`)

**Interfaces:**
- Produces: `_is_inside_worktree(cwd: str) -> bool` in `orch/cli.py` — a private
  helper, not exported/used elsewhere in this plan.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli.py`, right after `test_link_unknown_project_fails` (uses the
same `run()`/`self.tmp`/`self.db` fixtures already defined in that file):

```python
    def test_link_refuses_inside_worktree(self):
        run(["init", "alpha"], self.db)
        repo = os.path.join(self.tmp, "repo")
        os.makedirs(repo)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo,
                       check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo,
                       check=True)
        open(os.path.join(repo, "f.txt"), "w").close()
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo,
                       check=True)
        worktree = os.path.join(self.tmp, "wt")
        subprocess.run(["git", "worktree", "add", "-b", "feat/x", worktree],
                       cwd=repo, check=True)

        out = run(["link", "alpha"], self.db, cwd=worktree)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("worktree", out.stderr.lower())

        # the main checkout of that same repo still links fine
        ok = run(["link", "alpha"], self.db, cwd=repo)
        self.assertEqual(ok.returncode, 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::CLITest::test_link_refuses_inside_worktree -v`
Expected: FAIL — `link` currently succeeds unconditionally, so
`self.assertNotEqual(out.returncode, 0)` fails (`out.returncode` is `0`).

- [ ] **Step 3: Add the guard helper and wire it into `cmd_link`**

In `orch/cli.py`, add `import subprocess` to the top-level imports (alongside the
existing `argparse`, `json`, `os`, `sys`):

```python
import argparse
import json
import os
import subprocess
import sys

from orch import db
```

Then, immediately above the existing `def cmd_link(conn, args):` (around line 128),
add the helper and change `cmd_link` to:

```python
def _is_inside_worktree(cwd):
    """True if cwd is a git worktree other than the repo's main checkout —
    ruling out a submodule, which also has its own private git-dir. Same
    detection the work skill's isolation check uses:
    `git rev-parse --git-dir` vs `--git-common-dir`."""
    def _git(args):
        try:
            out = subprocess.run(
                ["git", *args], cwd=cwd, capture_output=True, text=True,
                timeout=5)
        except OSError:
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    git_dir = _git(["rev-parse", "--git-dir"])
    common_dir = _git(["rev-parse", "--git-common-dir"])
    if git_dir is None or common_dir is None:
        return False
    norm = lambda p: os.path.normcase(os.path.abspath(os.path.join(cwd, p)))
    if norm(git_dir) == norm(common_dir):
        return False
    if _git(["rev-parse", "--show-superproject-working-tree"]):
        return False  # submodule, not a worktree
    return True


def cmd_link(conn, args):
    if _is_inside_worktree(os.getcwd()):
        print("error: refusing to link from inside a git worktree — cd to "
              "the main checkout and run `orch link` there instead",
              file=sys.stderr)
        return 1
    db.require_project(conn, args.name)
    path = db.set_project_path(conn, args.name, os.getcwd())
    print(f"linked '{args.name}' to {path}")
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py::CLITest::test_link_refuses_inside_worktree -v`
Expected: PASS

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `python -m pytest -q`
Expected: all tests pass (99, up from 98) — in particular
`test_link_resolves_project_from_directory` and `test_link_unknown_project_fails` must
still pass unchanged, since they link from a plain (non-git) temp directory, which
`_is_inside_worktree` correctly treats as "not a worktree" (git commands fail there,
so both `_git` calls return `None`, and the function returns `False`).

- [ ] **Step 6: Commit**

```bash
git add orch/cli.py tests/test_cli.py
git commit -m "$(cat <<'EOF'
fix(cli): refuse orch link from inside a git worktree

orch link unconditionally rebinds the project's shared root path to
wherever it's run. Run from a worktree (e.g. a worker following the
preflight's generic recovery instructions), it silently breaks project
resolution for every other agent and the orch deps hardlink source — the
single most dangerous documented instruction the multi-agent skill review
found. Guard it at the CLI layer instead of relying on prose alone.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Rewrite `work/SKILL.md`'s isolation step, remove the work-in-place fallback, return to root after checkpoint

**Files:**
- Modify: `.claude/skills/work/SKILL.md`

**Interfaces:**
- Consumes: Task 1's guarded `orch link` (referenced in the preflight text, not called
  directly by this task).
- Produces: none consumed by later tasks — this task and Task 3 are independent
  rewrites of two different files.

- [ ] **Step 1: Update the preflight's `link` recovery text**

In `.claude/skills/work/SKILL.md`, replace:

```markdown
2. **Confirm the project resolves.** Run `python <path>/orch.py next --agent <AGENT> --json`.
   If it errors with `can't infer the project from this directory`, this checkout isn't
   linked yet → run `python <path>/orch.py link <project>` once here (ask the human the
   project name if unsure), then retry. (`ORCH_PROJECT` still works as an override if
   you ever need it.)
```

with:

```markdown
2. **Confirm the project resolves.** Run `python <path>/orch.py next --agent <AGENT> --json`.
   If it errors with `can't infer the project from this directory`, this is a genuinely
   fresh checkout that's never been linked → run `python <path>/orch.py link <project>`
   once here (ask the human the project name if unsure), then retry. **Never run `link`
   from inside a worktree** — it rebinds the project's shared root to wherever it's
   run, silently breaking resolution for every other agent; the CLI itself now refuses
   this, but if you ever see the error while inside a worktree, `cd` to the main
   checkout and link from there instead. (`ORCH_PROJECT` still works as an override if
   you ever need it.)
```

- [ ] **Step 2: Rewrite the "Ensure isolation" step**

Replace the entire numbered item 2 under "## One cycle" — from `2. **Ensure
isolation.**` through the line ending `...or this isn't an npm project.` (i.e. through
the end of the `deps` bullet, just before `3. **Branch on \`status\`:**`) — with:

```markdown
2. **Ensure isolation for THIS task, specifically.** Compute this task's fixed
   worktree path: `<project root>/.claude/worktrees/<AGENT>-<task id>` — always the
   same for a given task, so you can recompute it on any resume without trusting a
   possibly-stale DB field.
   - **Already there?** Compare your cwd to that *exact* path — not just "am I in some
     worktree." A stale worktree left over from a *previous* task would pass a looser
     check; comparing the exact path catches that. If they match, skip to step 3.
   - **Task's `worktree` field is set and the directory exists** (resuming after a
     restart) → re-enter it: `EnterWorktree` with `path: <that path>` (or plain
     `cd <that path>` if the tool isn't available).
   - **Not set yet (fresh claim) → create it at the computed path.** Skip
     `using-git-worktrees`'s human-consent gate — you're unattended, and the human
     already opted in by using the orchestrator system. Prefer the native
     `EnterWorktree` tool with `name: "<AGENT>-<task id>"` (it places new worktrees
     under `.claude/worktrees/` relative to cwd, which is exactly the computed path
     when called from the project root). First check this project's `worktree.baseRef`
     setting (`.claude/settings.json`): its default, `fresh`, branches off
     `origin/<default-branch>`, which can lag your local `main`. If it is not `head`,
     skip `EnterWorktree` and fall back to
     `git worktree add -b <branch> <project root>/.claude/worktrees/<AGENT>-<task id>`
     instead — same destination, bases off local HEAD with no setting needed. Either
     way, immediately record it — before doing anything else in the worktree:
     `python <path>/orch.py task update --task <id> --worktree <that path>`.
   - **Creation fails for any reason** (e.g. a sandboxed environment denies it) →
     `/report blocked <why>` and stop. Do not fall back to working in the shared
     checkout — that would silently drop every isolation guarantee, including the
     possibility of committing straight to `main`.
   - If this project doesn't already gitignore `.claude/worktrees/`, mention it to the
     human — worktrees under it are transient and shouldn't be tracked.
   - **Sync dependencies fast:** `python <path>/orch.py deps`. Hardlinks `node_modules`
     from the project root when the lockfile matches (near-instant); otherwise runs a
     real `npm ci`. Safe to call every cycle — it no-ops if `node_modules` is already
     here (resumed task) or this isn't an npm project.
```

- [ ] **Step 3: Rewrite the "Finish" step to return to the project root**

Replace:

```markdown
5. **Finish:**
   - `/checkpoint` (Step 4 above) already reported `done`. Loop back to step 1 for the
     next task.
```

with:

```markdown
5. **Finish:**
   - `/checkpoint` (Step 4 above) already reported `done`. **Return to the shared
     project root** — `ExitWorktree` with `action: "keep"` (or `cd` back if the tool
     isn't available) — before ending the turn. Your cwd must never sit inside a
     worktree between tasks: the branch isn't merged yet, so this is always `keep`,
     never `remove` — the orchestrator owns cleanup after merge, and on Windows it
     can't remove a directory your session is still parked in.
   - Loop back to step 1 for the next task.
```

- [ ] **Step 4: Manual verification checklist**

This is a prose/skill-doc change with no automated test — re-read the full modified
file and confirm each design point from
`docs/superpowers/specs/2026-07-05-worktree-identity-redesign-design.md` is satisfied:

- [ ] Worktree path is deterministic (`<project root>/.claude/worktrees/<AGENT>-<task id>`)
      and computed the same way in both the "already there" check and the "fresh claim"
      creation branch.
- [ ] The isolation check compares against *this task's* exact path, not "any worktree."
- [ ] The "work in place" fallback no longer exists anywhere in the file — search for
      the phrase "work in place" and confirm zero matches.
- [ ] Step 5 returns to the project root via `ExitWorktree action: "keep"` before
      ending the turn.
- [ ] The preflight's `link` recovery text warns against running it from a worktree.

Run: `grep -n "work in place" .claude/skills/work/SKILL.md`
Expected: no output (zero matches).

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/work/SKILL.md
git commit -m "$(cat <<'EOF'
fix(work): tie worktree isolation to the specific task, drop work-in-place

The isolation check only confirmed "in some worktree," so a worker idling
in task 1's worktree would pass the check when task 2 arrived and silently
build it on the wrong branch. Worktree paths are now deterministic
(<root>/.claude/worktrees/<agent>-<task id>>), computed the same way on
every resume instead of trusted from a possibly-stale DB field, and the
worker returns to the shared root after checkpoint so its cwd is never
inside a worktree the orchestrator might try to remove. The work-in-place
fallback on creation failure is removed entirely — it silently voided
every isolation guarantee (commits could land on the shared checkout, even
main); now it's an unconditional /report blocked.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Rewrite `orchestrate/SKILL.md`'s cleanup step to be best-effort and never blocking

**Files:**
- Modify: `.claude/skills/orchestrate/SKILL.md`

**Interfaces:**
- Consumes: none (independent of Tasks 1 and 2 — different file, no shared state).
- Produces: none.

- [ ] **Step 1: Update the preflight's `link` recovery text**

Replace:

```markdown
2. **Confirm the project resolves.** Run `python <path>/orch.py status --json`. If it
   errors with `can't infer the project from this directory`, this checkout isn't linked
   → run `python <path>/orch.py link <project>` once here (ask the human the project
   name if unsure), then retry.
```

with:

```markdown
2. **Confirm the project resolves.** Run `python <path>/orch.py status --json`. If it
   errors with `can't infer the project from this directory`, this checkout isn't linked
   → run `python <path>/orch.py link <project>` once here (ask the human the project
   name if unsure), then retry. **Never run `link` from inside a worktree** — it
   rebinds the project's shared root to wherever it's run; the CLI itself now refuses
   this, but you should only ever be running from the main checkout anyway (see step 1).
```

- [ ] **Step 2: Rewrite the worktree cleanup bullet**

Replace:

```markdown
   - **Clean up the worktree.** Read the task's `worktree` field (from the `orch
     status --json` you already have). If it's set: `git worktree remove <worktree>
     --force`, then `git branch -d <branch>`. If `worktree` is empty (the task was
     never isolated, or is from before this convention), skip — nothing to remove.
```

with:

```markdown
   - **Clean up the worktree — best-effort, never blocking.** Read the task's
     `worktree` field (from the `orch status --json` you already have). If it's empty
     (never isolated, or from before this convention), skip — nothing to remove.
     Otherwise: `git worktree remove <worktree>` — **no `--force`.**
     - Succeeds → `git branch -d <branch>`. Done.
     - Fails because of uncommitted/untracked changes (shouldn't happen after
       `/checkpoint`, but is a real signal if it does) →
       `orch post --agent orchestrator --task <id> --kind warning --msg "<worktree>
       has uncommitted changes, left in place — investigate before deleting"`. Do not
       force-delete, and do not delete the branch either — it's still checked out
       there.
     - Fails because the directory is in use (the worker's session is likely still
       parked there — common on Windows, where a live cwd can't be deleted) →
       `orch post --agent orchestrator --task <id> --kind note --msg "<worktree>
       cleanup deferred, directory in use"`. Leave it — no retry loop. The human
       sweeps leftover `.claude/worktrees/*` directories by hand once the relevant
       session is closed, then `git worktree prune` reconciles git's metadata.
   - **Either way, this never blocks the task's `merged` status** — cleanup is disk
     hygiene, not correctness; the merge and tests already succeeded.
```

- [ ] **Step 3: Manual verification checklist**

No automated test for this prose change — re-read the full modified file and confirm:

- [ ] Cleanup tries `git worktree remove` **without** `--force` first.
- [ ] Uncommitted-changes failure posts a `warning` and leaves worktree + branch
      alone (no force-delete).
- [ ] In-use failure posts a `note`, leaves it, and does **not** retry.
- [ ] None of the cleanup failure branches change the task's `merged` status set two
      bullets above.
- [ ] The preflight's `link` recovery text warns against running it from a worktree.

Run: `grep -n -- "--force" .claude/skills/orchestrate/SKILL.md`
Expected: no output (zero matches — the old unconditional `--force` is gone).

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/orchestrate/SKILL.md
git commit -m "$(cat <<'EOF'
fix(orchestrate): make worktree cleanup best-effort, never blocking

git worktree remove --force after merge routinely fails on Windows when
the worker's session is still parked in that directory as its cwd (can't
delete a directory a live process is sitting in), and --force would also
silently discard any uncommitted changes without warning. Cleanup now
tries a plain remove first, posts a warning (not a force-delete) if
there are uncommitted changes, posts a note and backs off with no retry
loop if the directory is in use, and never blocks the task's already-set
merged status either way — the human sweeps leftover worktree
directories by hand and runs `git worktree prune` to reconcile.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes (from the plan author, not a task to execute)

- **Spec coverage:** §1 (deterministic placement) → Task 2 Step 2. §2 (task-tied
  isolation) → Task 2 Step 2. §3 (return to root) → Task 2 Step 3. §4 (best-effort
  cleanup) → Task 3 Step 2. §5 (`orch link` guard) → Task 1. §6 (preflight prose) →
  Task 2 Step 1 and Task 3 Step 1. All six spec sections have a task.
- **Type/name consistency:** the worktree path format
  (`<project root>/.claude/worktrees/<AGENT>-<task id>`) and the `EnterWorktree`
  `name`/`path` parameter usage are worded identically across Task 2's two edits.
  `_is_inside_worktree` (Task 1) is a private, single-use helper — not referenced by
  Tasks 2 or 3, which are pure prose changes.
- **Placeholder scan:** no TBD/TODO; every step shows exact text or exact code.
