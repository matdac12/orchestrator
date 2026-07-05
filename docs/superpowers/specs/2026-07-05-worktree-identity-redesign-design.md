# Worktree identity redesign

## Problem

A three-agent adversarial review (fable, opus, Codex) of the orchestrator skill set
converged on the same root issue from different angles: **worktree isolation is
advisory, not enforced.**

- The work skill's isolation check only confirms "am I in *some* worktree" (comparing
  `git rev-parse --git-dir` to `--git-common-dir`) — never that it's *this task's*
  worktree. A worker idling in task 1's worktree passes the check when task 2 arrives,
  silently building task 2 on task 1's branch.
- Worktrees can land outside the linked project root (the fallback
  `git worktree add -b <branch> <new-path>` never pins `<new-path>`), which breaks
  `find_project_by_path`'s prefix match — every `orch` command run there falls back to
  the "sole project" heuristic, masking the bug until a second project exists.
- The documented recovery for that same generic resolution error
  (`can't infer the project from this directory` → run `orch link <project>` here) is
  itself destructive: `orch link` unconditionally overwrites the project's shared root
  path to wherever it's run. A worker following the skill literally, from inside a
  worktree, silently corrupts resolution for every other agent and the `orch deps`
  hardlink source.
- The "work in place" fallback (when worktree creation fails) voids every isolation
  guarantee — commits can land on the shared checkout, even on `main`.
- Cleanup (`git worktree remove --force`, run by the orchestrator post-merge) routinely
  fails on Windows when the worker's session is still sitting inside that directory as
  its cwd — a directory in use by a live process can't be deleted.

## Design

### 1. Deterministic worktree placement

Every worktree lives at `<linked project root>/.claude/worktrees/<agent>-<task-id>` —
never wherever `EnterWorktree`'s auto-generated name or an unpinned `git worktree add`
happens to put it.

- Preferred path (`worktree.baseRef: head` set): `EnterWorktree` with
  `name: "<agent>-<task-id>"` — `EnterWorktree` already places new worktrees under
  `.claude/worktrees/` relative to cwd, so calling it from the linked root naturally
  produces the deterministic path.
- Fallback path (`baseRef` isn't `head`): `git worktree add -b <branch>
  <root>/.claude/worktrees/<agent>-<task-id>` — same destination, explicit.
- Recommend (README + skill note) that target projects gitignore `.claude/worktrees/`.

This fixes project-inference (always under the linked root) and makes resume
deterministic: the path can always be *recomputed* from `<agent>` + `<task-id>`,
independent of whether the DB's `worktree` field made it through a crash.

### 2. Isolation tied to the task, not "any worktree"

The work skill's step 2 changes from "am I in a worktree?" to "am I in *this task's*
worktree?": compute the deterministic path for the current task, and compare against
it explicitly (not just check git-dir vs git-common-dir in the abstract).

- Task's `worktree` field set and matches the deterministic path, directory exists →
  `EnterWorktree path: <path>` (or plain `cd`) to resume.
- Not set (fresh claim) → create at the deterministic path (§1), then immediately
  `orch task update --task <id> --worktree <path>` before doing anything else there.
- Creation fails for any reason → **`/report blocked <why>` and stop.** The "work in
  place" fallback is removed entirely — no silent de-isolation, ever.

### 3. Return to the project root after checkpoint

Immediately after `/checkpoint` reports `done`, the worker returns to the shared
project root (`ExitWorktree action=keep`, or `cd`) before ending the cycle. The
worker's cwd is only ever inside a worktree while actively executing a task — never
while idling between tasks. This is what makes cleanup (§4) safe: the orchestrator
never races a live cwd.

### 4. Orchestrator cleanup: best-effort, never blocking

After a successful merge, the orchestrator attempts cleanup but never lets it block the
task's `merged` status or force-delete something it isn't sure about:

1. `git worktree remove <path>` — **no `--force`.**
2. Fails because of uncommitted/untracked changes (shouldn't happen post-checkpoint,
   but is a real signal if it does) → `orch post --kind warning` and leave the
   worktree + branch alone. Do not force-delete potentially-unsaved work.
3. Fails because the directory is in use (the Windows live-cwd case) → `orch post
   --kind note` that cleanup is deferred, and leave it. No retry loop.
4. Succeeds → `git branch -d <branch>`.

The human periodically sweeps leftover `.claude/worktrees/*` directories by hand
(e.g. via File Explorer, once the relevant session window is closed) and runs a plain
`git worktree prune` to reconcile git's metadata for whatever was removed manually.

### 5. `orch link` refuses to run inside a worktree

`orch link` is meant to bind the *canonical* project root, once, from the main
checkout. It now refuses unconditionally when cwd is a worktree (detected the same way
the work skill already does: `git rev-parse --git-common-dir` differs from `--git-dir`,
ruling out a submodule via `git rev-parse --show-superproject-working-tree`) —
regardless of whether that repo happens to be linked elsewhere already. The error
message tells the user to run it from the main checkout instead.

This is a blanket rule rather than a conditional one ("only refuse if already linked
elsewhere") because it's simpler to implement, simpler to explain, and there's no
legitimate reason to link from a worktree — worktrees are inherently transient/per-task.

### 6. Preflight prose fix (defense in depth)

The work skill's preflight recovery text ("if `orch next` errors with `can't infer the
project`, run `orch link <project>` here") is narrowed to make clear it's for a
genuinely fresh, never-linked checkout — and explicitly states: never run this from a
worktree. With placement now deterministic and always under the linked root (§1), the
scenario that used to trigger this confusing error from inside a worktree shouldn't
occur anymore; the prose fix plus the code guard (§5) are belt-and-suspenders.

## Out of scope

- Automatic retry/sweep of deferred cleanup (§4) — the human's manual sweep is the
  agreed mechanism; adding a retry loop is unnecessary complexity for a disk-hygiene
  concern, not a correctness one.
- The `orch deps` hardlink corruption risk and the lower-confidence concurrency notes
  (`with_retry` rollback, `claim_next` atomicity) — separate topics, tracked
  separately.

## Testing

- `orch link` refuses from inside a worktree (new test, using a temp repo +
  `git worktree add`).
- Existing worktree-related tests continue to pass; no schema changes needed (the
  `worktree` column already exists and is already settable via `task update`).
