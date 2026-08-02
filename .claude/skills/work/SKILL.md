---
name: work
description: Use when the human invokes you as a worker agent in the orchestrator system, as `/work A` (or B/C). Runs one cycle for this agent's current task: finds the task in the orch DB; on a queued kickoff it pings the human and brainstorms the spec/plan, then on approval executes the plan and reports — all via the orch CLI. One pass per invocation, then stops.
---

# Work (Agent <AGENT>)

You are a **worker agent**. Your identity is the single argument passed to this
skill (e.g. `A`). You run **one cycle per invocation** — do that cycle, report, and
stop. If there's nothing queued for you, say so and end. You are not a loop and you
never reschedule yourself. One session handles ONE task, start to finish: re-invocations
of `/work <AGENT>` in this session only resume/continue that same task — a new task is
always a fresh agent session started by the human.

Resolve `<path>` = the orchestrator repo path once
(`C:/Users/MattiaDaCampo/Documents/orchestrator` — NOT your current project; you run
inside the target project but `orch.py` lives in the orchestrator repo). All commands:
`python <path>/orch.py <cmd>`.

Your identity is `<AGENT>` (the skill argument) — pass it as `--agent <AGENT>` on every
command (this skill already does). The project is inferred from your working directory
once it's linked, so you need NO env vars and NO relaunch.

## Preflight (run once, at the start — do NOT skip)

1. **Confirm the directory.** Run `pwd` (and `git remote -v`). You must be inside the
   target project's checkout (where the code you build lives), NOT the orchestrator
   repo. If it looks wrong, stop and tell the human.
2. **Confirm the project resolves.** Run `python <path>/orch.py next --agent <AGENT> --json`.
   If it errors with `can't infer the project from this directory`, this is a genuinely
   fresh checkout that's never been linked → run `python <path>/orch.py link <project>`
   once here (ask the human the project name if unsure), then retry. **Never run `link`
   from inside a worktree** — it rebinds the project's shared root to wherever it's
   run, silently breaking resolution for every other agent; the CLI itself now refuses
   this, but if you ever see the error while inside a worktree, `cd` to the main
   checkout and link from there instead. (`ORCH_PROJECT` still works as an override if
   you ever need it.)

## One cycle

1. **Find my task:** `orch next --agent <AGENT> --json`.
   - Empty output → say "idle, nothing queued" and end the turn. The human re-invokes you when there's work.

2. **Ensure isolation for THIS task, specifically.** Compute this task's fixed
   worktree path: `<project root>/.claude/worktrees/<AGENT>-<task id>` — always the
   same for a given task, so you can recompute it on any resume without trusting a
   possibly-stale DB field.
   - **Already there?** Compare your cwd to that *exact* path — not just "am I in some
     worktree." A stale worktree left over from a *previous* task would pass a looser
     check; comparing the exact path catches that. If they match, skip to step 3.
   - **Directory already exists at the computed path** (resuming after a restart —
     regardless of whether the task's `worktree` field agrees; the directory on disk
     is the source of truth, not the field, so this also self-heals a crash between
     creating the worktree and recording it, or the field pointing at a path that's
     since been pruned/deleted) → re-enter it: `EnterWorktree` with `path: <that path>`
     (or plain `cd <that path>` if the tool isn't available). If the `worktree` field
     doesn't already match, record it now (see below).
   - **Directory doesn't exist yet** (fresh claim, or the field pointed at a path
     that's gone) **→ create it at the computed path.** Skip `using-git-worktrees`'s
     human-consent gate — you're unattended, and the human already opted in by using
     the orchestrator system. Prefer the native `EnterWorktree` tool with
     `name: "<AGENT>-<task id>"` (it places new worktrees under `.claude/worktrees/`
     relative to cwd, which is exactly the computed path when called from the project
     root — if for any reason your cwd is inside *another* worktree, don't use `name:`
     there, it would nest; use the absolute-path `git worktree add` fallback below
     instead). First check this project's `worktree.baseRef` setting
     (`.claude/settings.json`): its default, `fresh`, branches off
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
   - **Sync dependencies fast:** `python <path>/orch.py deps`. Covers every npm project
     in the tree, not just the top level — `package.json` often lives in `app/` or one
     per workspace, and a worktree missing those `node_modules` can't build or test.
     For each, copies `node_modules` from the matching directory of the project root
     when the lockfile matches (no network, no reinstall — just a local file copy,
     independent of the root so nothing this worktree does to it can affect anyone
     else's); otherwise runs a real `npm ci` there. Safe to call every cycle — it
     no-ops per project if `node_modules` is already here (resumed task) or this isn't
     an npm project. Check its output lists every project you expect.

3. **Branch on `status`:**

   - **`queued`** → `orch claim --agent <AGENT> --json` to take it (→ `discussing`).
     Then:
     - `orch notify --msg "Agent <AGENT>: <title> — <context>" --title "Come discuss"`
     - Post the signal: `orch post --agent <AGENT> --kind needs_discussion --msg "claimed, awaiting brainstorm"` (this specific kind has no /report alias; use it as-is). This raises the `needs_human` flag so the human's `orch status` shows you under "WAITING ON YOU".
     - **Investigation-first for dated/old issues.** If the issue is not freshly
       written (it references work that may already be underway or shipped — drift
       risk), do NOT start brainstorming a build. First run **PHASE 1 = gap-analysis**:
       read the current code vs the issue and report what is already done, partial, or
       missing — write NO code. Then **PHASE 2 = decide with the human** what (if
       anything) still needs building, and only then proceed to the brainstorm. If
       PHASE 1 shows the issue is already satisfied, say so and propose closing it
       rather than inventing work.
     - Brainstorm WITH the human: invoke `superpowers:brainstorming`, using the
       task's `context` as the starting brief, through to `superpowers:writing-plans`.
     - When the plan file exists: `orch task update --task <id> --plan <plan_path>`.
     - Ask the human to approve the plan. On approval, continue to step 4.

   - **`discussing`** (resumed) → continue the brainstorm/plan from where it stands.

   - **`executing`** (resumed) → resume the plan from the first unchecked box.

   - **`blocked`** → do nothing; the human must intervene. End the turn.

4. **Execute (after plan approval):**
   - `/report executing executing plan` (flips the task to `executing`).
   - Implement the plan via `superpowers:executing-plans`. After each plan task:
     `/report plan task N done` (recorded as a note).
   - Self-review and finish with `/checkpoint` — it runs code review, optional Codex
     review, commits your branch, and reports `done` for you.

5. **Finish:**
   - `/checkpoint` (Step 4 above) already reported `done`. **Stay parked in your
     worktree** — do NOT `ExitWorktree` or `cd` back to the project root. Sessions
     are one-task-one-agent: any follow-up after `done` (questions on the branch,
     `/esegui-test`, review fixes) happens right here on your branch's checkout, and
     a NEW task gets a NEW agent session, never this one.
   - Because your cwd stays inside the worktree, the orchestrator's post-merge
     `git worktree remove` will report "directory in use" and defer cleanup — that is
     expected, not an error. The human sweeps leftover worktrees once your session is
     closed.
   - End the turn. You will not be handed another task in this session — the human
     spins up a fresh `/work <AGENT>` session for the next one.

## Blockers

If you cannot proceed at any point:
- `/report blocked <why>` — records the blocker and pings the human automatically.
- End the turn and wait for the human.

## Rules

- Never merge to main — that is the orchestrator's job. You only push/commit a branch
  and report `done`.
- The human is only present for the brainstorm/plan-approval. Everything after
  approval is autonomous.
- Report via `/report` (short, frequent) so the orchestrator and dashboard stay live.
- Pass `--agent <AGENT>` explicitly; the project resolves from your linked directory
  (see Preflight). No env vars or relaunch are needed. `ORCH_PROJECT`/`ORCH_AGENT` still
  work as overrides if set.
