# Autonomous Loop (v2) — Design

**Date:** 2026-06-10
**Status:** Approved design, pending implementation plan
**Builds on:** [v1 comm layer](2026-06-09-orchestrator-comm-layer-design.md)

## Problem

v1 removed the human as the *message bus* but the human still drives every step:
generating prompts, ferrying status, deciding each transition. The goal of v2 is to
remove the human from execution entirely. The human stays involved only in the part
they value — the **discussion**: kickoff brainstorm → spec → plan approval — and in
**judgment calls** (blockers, direction). Everything after plan approval (execute,
self-review, report) and all integration (merge, Linear update) becomes automatic.

## Scope (v2)

The autonomous loop layered on v1: a worker loop, an orchestrator loop, polling, a
task lifecycle state machine, kickoff-context handoff, and Telegram pings for the
three "human needed" moments.

**Out of scope:** an external watcher/daemon that launches headless sessions; the
always-on Windows dashboard service (still deferred from v1).

## Roles

- **Human** — present only for *discussion* (kickoff brainstorm → spec → plan
  approval) and *judgment* (blockers, deciding direction). Summoned by Telegram.
- **Worker agent (A/B/C)** — started with `you are Agent A`; runs `/loop /work A`.
  Lives the per-task lifecycle below.
- **Orchestrator** — runs `/loop /orchestrate`. Lean. Reconciles Linear+DB, owns
  integration (merge, Linear update, surface blockers). Never authors specs/plans.

## Worker task lifecycle

```
queued ──(agent picks up, pings you)──▶ discussing ──(you+agent: spec→plan→approve)──▶
executing ──(plan done, self-review)──▶ done ──(orchestrator merges)──▶ merged
                  │                          │
                  └────── blocked ◀──────────┘   (pings you)
```

- `queued → discussing`: the worker loop finds a kickoff for the agent, claims it,
  and **pings the human** to come brainstorm.
- `discussing → executing`: happens **only after the human approves the plan**
  in-window. This is the line between human and machine.
- `executing → done`: agent ran the plan + self-review autonomously, posting events
  along the way, and committed to a branch.
- `done → merged`: the orchestrator does this.
- Any active state `→ blocked`: agent/orchestrator cannot proceed; **pings the human**.

**Queuing stays collaborative.** The orchestrator never invents and queues endless
work. Deciding "what's next" is a lightweight discussion the human has with the
orchestrator (it proposes from Linear, the human confirms, it creates the `queued`
kickoff). The human may also pre-queue an agent's known-next task so delegation
happens without waiting — but nothing executes without the human in the discussion.

## Schema & data changes (extend v1, no rebuild)

`tasks` gains two columns:
- **`context`** (TEXT) — the orchestrator's kickoff brief: the decision/direction and
  why it is next. The lean handoff — no spec, no plan.
- **`plan_path`** (TEXT, nullable) — recorded by the *agent* once the plan is written,
  for traceability and the dashboard. The orchestrator never writes this.

**Status enum** grows to: `queued`, `discussing`, `executing`, `blocked`, `done`,
`merged`. (`queued` replaces v1's `todo`; `discussing`/`executing` split v1's
`in_progress` so the dashboard distinguishes *brainstorming-with-human* from
*auto-executing*.)

`ACTIVE_STATUSES` becomes `(queued, discussing, executing, blocked)`.

**Events** gain one `kind`: `needs_discussion` (alongside `status`/`note`/`blocker`/
`handoff`). It is the first-class "come brainstorm" signal that drives the ping.

**Migration** runs in `connect()`: idempotent `ALTER TABLE ADD COLUMN` for `context`
and `plan_path` (guarded by a check of `PRAGMA table_info(tasks)`), so existing v1 DBs
upgrade in place.

## CLI additions (v1 commands unchanged)

- **`orch next --agent A [--json]`** — returns the agent's single active task
  (`queued`/`discussing`/`executing`, oldest first), or nothing (empty output, exit 0).
  The worker loop's heartbeat.
- **`orch task add`** gains `--status` (default `queued`) and `--context "<brief>"`.
- **`orch task update`** gains `--plan <path>` and `--context "<brief>"`.
- **`orch notify --msg "..." [--title "..."]`** — sends an immediate Telegram message
  via the user's bot. Token/chat from `ORCH_TG_TOKEN`/`ORCH_TG_CHAT`, falling back to
  the telegram plugin's config file. If unconfigured, prints the message and exits 0
  (a missing token never breaks the loop).

## The `/work <AGENT>` worker skill

Started as `/loop /work A` (self-paced — never interrupts itself mid-work; reschedules
a poll only when idle). Each cycle:

1. `orch next --agent A` → the agent's single active task or nothing.
2. **Nothing** → report "idle," end the turn; the loop rechecks later.
3. **`queued`** → claim (→ `discussing`, guarded `UPDATE ... WHERE status='queued'`),
   post a `needs_discussion` event, `orch notify` the human with title + context. Then
   run the interactive brainstorm with the human (`brainstorming` → `writing-plans`).
   When the plan file is written: `orch task update --plan <path>`.
4. **Human approves the plan** → transition to `executing`.
5. **Execute autonomously** via `executing-plans`, posting an event per completed plan
   task. Then self-review (project `/checkpoint` + `requesting-code-review`), commit to
   a branch.
6. **Finish** → `orch post --status done --branch <branch> --msg "ready for review"`,
   then loop back to step 1.

**Resumability:** state lives in the DB + the plan's checkboxes. Restarting `/work A`
re-reads the active task — `discussing` resumes the brainstorm, `executing` resumes the
plan from the first unchecked box.

**Blocked:** on an unrecoverable problem, set `blocked`, post a `blocker` event,
`orch notify` the human, and stop until they intervene.

The skill is thin glue sequencing existing superpowers skills and the `orch` CLI.

## The `/orchestrate` skill

Started as `/loop /orchestrate` (self-paced). Two halves.

**Autonomous (every cycle):**
1. Read `orch status --json`.
2. For each `done` task: review the branch, merge to `main`, run the test suite on the
   merged result, update Linear, set `merged`.
3. If a merge conflicts or tests fail: set the task `blocked`, post a `blocker` event,
   `orch notify` the human ("orchestrator needs input"). Never force-merge past a problem.
4. Otherwise idle and reschedule.

Every agent branch lives in the one shared repo (worktrees share it), so the
orchestrator in the main repo can merge any agent's branch with no extra plumbing.

**Collaborative (when the human is in the window):**
- Reconcile Linear ↔ DB, propose the next step, and on confirmation create the kickoff:
  `orch task add --agent A --status queued --context "<brief>" --issue LIN-123`.
- The human may pre-queue an agent's known-next task here.
- If agents are idle and nothing is queued, `orch notify` the human for direction
  rather than inventing work.

## Notifications

Three moments ping the human via `orch notify`:
1. **Agent needs discussion** — worker claimed a `queued` task and awaits the brainstorm.
2. **Blocked** — agent or orchestrator hit a problem needing a human call.
3. **Orchestrator needs input** — e.g. nothing queued while agents idle, or a
   merge-conflict judgment call.

(Merge/milestone pings are intentionally omitted — when the human is engaged in a
window they are already watching the screen.)

## Error handling

- **Graceful notify:** missing token → print + exit 0; the loop survives.
- **Guarded claim:** `queued → discussing` is a conditional UPDATE so a task is never
  double-claimed.
- **Idempotent migration:** `ALTER TABLE ADD COLUMN` only when the column is absent.
- **Loop resilience:** transient errors are logged as a `note` event; the loop
  continues rather than dying.

## Testing

- Unit: migration adds columns idempotently; `next` selects the right single active
  task in the right order; the guarded claim transition; the widened status enum is
  accepted by `add_task`/`update_task`/`post_event`.
- CLI: `next`, `task add --status/--context`, `task update --plan`, and `notify` in
  dry-run (token unset → prints intended message, exit 0).
- The skills are markdown; we test the `orch` surface they depend on, not the skills
  themselves.
