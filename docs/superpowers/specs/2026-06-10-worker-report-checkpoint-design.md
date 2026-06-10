# Worker-side `/report` + generic `/checkpoint` — Design

**Date:** 2026-06-10
**Status:** Approved design, pending implementation plan
**Builds on:** [autonomous loop v2](2026-06-10-autonomous-loop-design.md)

## Problem

In v2 the worker `/work` skill hands agents raw `orch post ...` commands to run at
each step. Reporting therefore depends on the agent remembering the exact CLI, which
is unreliable — if an agent forgets, the orchestrator and dashboard go blind. We want
reporting to be frictionless and the self-review to report automatically.

## Goal

- A lean **`/report`** primitive: one word + a phrase, no flags, to record progress.
- A project-agnostic **`/checkpoint`** skill modelled on the user's preferred Publiscoop
  checkpoint (code-review → Codex → commit), with orch reporting baked into its final
  step.
- Push the reporting logic into a **tested `orch report` CLI command** so the skills
  stay thin and the behavior is verifiable.

## Scope

`orch report` command, the `/report` and `/checkpoint` skills, an update to `/work` to
use them, and install/docs. **Out of scope:** harness hooks (the mechanism stays
skill-driven), and any change to the orchestrator's Linear ownership.

## `orch report` command

A convenience wrapper around the existing `post_event` path:

```
orch report --status <executing|done|blocked|note> [--msg "..."] [--agent A] [--branch X] [--project P]
```

`--msg` is optional (defaults to empty), so `orch report --status done` works on its own.

- **Identity:** agent resolves from `--agent`, else the `ORCH_AGENT` env var. If neither
  is set, error clearly. Project resolves from `--project`/`ORCH_PROJECT` as elsewhere.
- **`note`:** posts an event with `kind="note"` and no status change.
- **`executing`/`done`/`blocked`:** posts via `post_event` with that status (event +
  task side-effects), reusing the existing single-active-task auto-targeting.
- **`done` branch auto-detect:** if `--branch` is omitted, attempt
  `git branch --show-current` (in the current working directory); on success use it, on
  any failure (not a git repo, git missing) leave branch unset — never crash.
- **`blocked` auto-notify:** after posting, call `orch notify` with a "blocked" message
  so a blocker can never be recorded without summoning the human. Notify failure is
  swallowed (dry-run/no-token still exits 0).
- Delegates all DB writes to `db.post_event`; adds only identity resolution, branch
  detection, and the blocked-notify side effect.

## `/report` skill

Thin wrapper. Usage: `/report <status> <message>`.

- If the first token is a known status (`executing`/`done`/`blocked`/`note`), map to
  `orch report --status <token> --msg "<rest>"`.
- Otherwise treat the whole input as a note: `orch report --status note --msg "<all>"`.
- `done` needs no message (branch is auto-detected): `/report done` works.

## `/checkpoint` skill (generic)

Project-agnostic post-work flow with reporting baked in. Steps, in order:

1. **Code review** — run `/code-review` at an honestly chosen effort (`low` / default /
   `high`); apply fixes. Never skip.
2. **Codex review (optional)** — if the `codex` plugin is available, invoke
   `/codex:rescue` review-only, reason critically about the output, present analysis,
   discuss with the user, apply agreed changes, and re-run `/code-review` if code
   changed. If codex is not installed, skip cleanly.
3. **Commit** to the agent's branch with a clear message and the Co-Authored-By line.
4. **Report** — `orch report --status done` (auto-detects the branch).

**Deliberate difference from the Publiscoop checkpoint:** this generic checkpoint does
**not** update Linear. In v2 the orchestrator owns Linear updates (on merge), so a
worker updating Linear would double-own that state. Worker checkpoint = quality +
commit + report; Linear remains the orchestrator's responsibility.

## `/work` update

Replace the raw `orch post ...` instructions in `.claude/skills/work/SKILL.md` with
`/report` calls:
- on claim/brainstorm: `/report` for the `needs_discussion`/notify already handled by
  the claim step stays, but progress posts become `/report executing ...`.
- after each plan task: `/report <short progress note>`.
- self-review: run `/checkpoint` (which ends by reporting `done`), instead of a manual
  `orch post --status done`.
- blockers: `/report blocked <why>` (which auto-notifies).

## Install & docs

The skills must be reachable from worker windows in any project, so the README
documents:
- installing `/report` and `/checkpoint` at user level (`~/.claude/skills/`, e.g. a
  symlink from this repo) so every project's worker window has them;
- setting `ORCH_AGENT` (the agent's identity) alongside `ORCH_PROJECT` per worker
  window.

## Error handling

- Missing identity (`--agent` and `ORCH_AGENT` both unset) → clear error, exit 1.
- `done` branch auto-detect failures are swallowed (branch left unset).
- `blocked` notify failures are swallowed (loop never breaks).
- Invalid status → reuse the existing `TASK_STATUSES`/post validation error.

## Testing

The logic lives in `orch report`, so that is what we test (CLI via subprocess):
- `report --status executing` with `ORCH_AGENT` set posts for that agent and flips the
  active task to `executing`.
- `report --status done --branch X` records branch `X`; `report --status done` with no
  `--branch` from a non-git directory does not crash and leaves branch null.
- `report --status blocked` posts the blocker event and triggers notify (dry-run prints,
  exit 0).
- `--agent` overrides `ORCH_AGENT`.
- missing identity errors (exit 1).
- The skills are markdown; we test the CLI they call, not the skills themselves.
