# Agent Handoff — Design

**Date:** 2026-07-03
**Status:** Approved design, pending implementation plan
**Builds on:** [v2 autonomous loop](2026-06-10-autonomous-loop-design.md)

## Problem

Today, delegating a queued kickoff to a worker still costs the human a manual step:
open a new pane/window, `cd` into the checkout, type `/loop /work A`. The orchestrator
already knows everything needed to do this itself — the agent letter, the fact that
the prompt is always `/loop /work <letter>` — but nothing automates the handoff.
Separately, worker windows sharing one checkout can't each sit on a different branch
at once, so isolation is currently up to the human to arrange by hand.

## Scope

In scope:
- A new, generic `agent-handoff` skill: a "spawn a named background `claude` session"
  primitive, usable standalone (not just from the orchestrator).
- A small addition to `/orchestrate` teaching it to call `agent-handoff` when
  delegating a kickoff.
- A small addition to `/work` making it self-isolate into a git worktree branched
  from local HEAD before it starts.

Out of scope:
- Any `orch.py`/CLI changes — `task update --worktree` already exists and is enough.
- Automatic worktree cleanup/removal policy (left to the human / existing
  `using-git-worktrees` conventions).
- Changing how `/orchestrate` decides *what* to delegate — only *how* it hands it off.

## `agent-handoff` skill

A generic, orchestrator-agnostic primitive. Takes exactly two inputs: a **session
name** and a **prompt**. Nothing else — no branch, no worktree, no task lookup. Any
agent (orchestrator, worker, or the human directly) can invoke it whenever they want
to fire off a named background session.

Steps:
1. **Collision check:** `claude agents --json`, filter for a non-completed session
   whose `name` matches. If one exists, report that back instead of spawning a
   duplicate — the caller decides how to proceed (pick a different name, or accept
   there's already one running).
2. **Spawn:** `claude --bg --name "<name>" "<prompt>"`.
3. **Confirm:** re-query `claude agents --json`, match by `name`, capture `pid`,
   `sessionId`, `cwd`, `status`.
4. **Report back** `{name, pid, sessionId, cwd, status}` to whoever invoked it.

Installed as a fifth skill (`.claude/skills/agent-handoff/`), junction-linked at user
level alongside the existing four so it's reachable from any worker/orchestrator
window (see README's "Installing skills for worker windows").

## `/orchestrate` addition

New section, "Delegating to a background agent": when the human confirms a queued
kickoff should run unattended, the orchestrator picks the next available agent letter
from its own context of which agents are currently active (`claude agents --json` is
available as an optional cross-check, not a required step), then invokes
`agent-handoff` with:
- `name`: `"Agent<letter> - <issue>"` (fall back to the branch name if there's no
  linked issue)
- `prompt`: `"/loop /work <letter>"`

No branch or task detail is passed through agent-handoff — the spawned worker looks
up its own task via `orch next --agent <letter>`, which already carries the full
context/branch.

## `/work` addition

New preflight step, run before the existing directory/project checks: **ensure
isolation before doing anything else.**

1. Detect existing isolation the same way `using-git-worktrees` does (compare
   `git rev-parse --git-dir` vs `--git-common-dir`). If already isolated, skip to the
   existing preflight.
2. If not isolated: read the branch to isolate on from the active task
   (`orch next --agent <AGENT> --json` → its `--branch` field, pre-assigned by the
   kickoff convention). If the task has no branch set, skip worktree creation
   entirely and proceed in place (nothing to isolate on).
3. Skip `using-git-worktrees`'s human-consent gate — this runs unattended in a
   background session; the human already opted in by using the orchestrator system.
4. Prefer the native `EnterWorktree` tool, but first check the project's
   `worktree.baseRef` setting. Default (`fresh`) branches from
   `origin/<default-branch>`, which can lag local `main` — if it isn't `head`, fall
   back to a plain `git worktree add -b <branch> <path>` instead (bases off local
   HEAD with no setting needed) rather than silently isolating from the wrong point.
5. Record the result: `orch task update --task <id> --worktree <path>` (the field
   already exists on `task update`, previously unused).
6. **Resuming** a `discussing`/`executing` task: if `--worktree` is already recorded
   and matches the current directory, skip creation — this step is idempotent across
   loop cycles.

## Data / CLI changes

None. `orch task update --worktree <path>` already exists.

## Installation

- New `.claude/skills/agent-handoff/SKILL.md`.
- README: add `agent-handoff` to the skills list and to both junction-link loops
  (macOS/Linux `ln -s`, Windows `mklink /J`) in "Installing skills for worker windows."

## Error handling

- `agent-handoff`: if `claude --bg` itself fails to start, surface the raw error to
  the caller rather than swallowing it — never silently report success.
- `/work`'s isolation step: if worktree creation fails (e.g. a sandboxed environment
  denies it), fall back to working in place and say so in the next status report,
  matching `using-git-worktrees`'s own sandbox fallback.

## Testing

Skills are markdown; no unit tests apply. Verification is manual:
- Run `agent-handoff` standalone with a throwaway name/prompt and confirm the session
  appears in `claude agents --json` with the right name and a live `pid`.
- Run a mock `/orchestrate` → `/work` cycle end-to-end and confirm the worker ends up
  isolated in a worktree branched from local `main` (not `origin/main`), and that the
  task's `--worktree` column gets populated.
