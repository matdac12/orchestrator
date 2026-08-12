# Worker Progress Reporting

## Status

Approved — ready for planning.

Supersedes the draft at `progress-reporting-spec.md` (repo root). Where the two
disagree, this document wins; the differences are deliberate and recorded under
[Departures from the draft](#departures-from-the-draft).

## Summary

The orchestrator sees only coarse lifecycle transitions today: a task is claimed,
eventually reported `done`, then merged. That is enough to drive merges and nothing
else. It cannot answer the question that actually comes up when several agents are
running — *what is each one doing, and how much is left?*

This feature adds a progress channel alongside the existing lifecycle. Workers report
at the boundaries their own workflow already has (phase changes, and each task of the
approved plan), carrying a `step N/total` drawn from the plan itself. The orchestrator
reads those snapshots when it runs.

> Lifecycle status answers "what state is this task in?" Progress answers "what is the
> worker doing right now, and how much is left?"

The lifecycle is unchanged:

```text
queued -> discussing -> executing -> done -> merged
                                      +-> blocked
```

Progress is informational. It never alters lifecycle status, never raises
`needs_human`, and never authorizes a merge.

## Goals

- Make worker activity visible before completion, in units of work remaining.
- Let the orchestrator report "who is where" without asking the human.
- Keep reporting event-driven and anchored to the existing `/work` workflow — no
  timers, no heartbeats, no polling hooks.
- Preserve the one-pass-per-invocation model for both workers and the orchestrator.
- Stay backward compatible with existing databases, tasks, commands, and scripts.

## Non-goals

- Time estimates or ETAs of any kind.
- Streaming tool calls, commands, checkboxes, or model thoughts.
- Deciding a worker is stuck, or acting on that decision.
- Giving progress any authority over merges.
- Redesigning the dashboard. That is a follow-up spec (see [Out of scope](#out-of-scope)).

## Design decisions

Four choices shape everything below.

**Event-driven, never timed.** A Claude worker has no timer; it exists only between
tool calls, so any interval-based heartbeat is really "at the next natural boundary, if
enough time has passed" — unpredictable in exactly the way it was meant to fix. Instead
reporting is pinned to boundaries the workflow already produces. There is no
`heartbeat` kind.

**The plan file is the unit.** `/work` writes a plan with a countable number of tasks
before implementation starts. That count is `step_total`; the task being worked is
`step`. Work remaining is therefore read off the plan, never estimated.

**No ETA.** `3/6` plus a timestamp is honest and cheap. A derived projection is naive
about an unusually large step; an agent-declared ETA is confidently optimistic. Both
are worse than a number the reader can interpret.

**Events only; the snapshot is derived.** Storing a denormalized snapshot on `tasks`
alongside the event creates two sources of truth for one fact, an atomicity
requirement, and tests to prove they agree. Deriving current progress from the newest
progress event removes all three for the cost of one `SELECT ... ORDER BY id DESC LIMIT
1` per task — a cost that does not register at this scale (one SQLite file, a handful of
agents, tens of events per task).

## Data model

Four nullable columns on `events`, plus `progress` in the validated event-kind set:

```sql
progress_phase       TEXT
progress_step        INTEGER
progress_step_total  INTEGER
progress_next_step   TEXT
```

The existing `message` column carries the human-readable description. The `tasks` table
is not modified.

A task's current progress is the newest `kind=progress` event for that `task_id`, read
on demand. The events table remains the append-only history and the audit trail.

### Phases

A closed set of seven, matching `/work`'s actual shape:

| Phase | Meaning | Typical lifecycle |
|---|---|---|
| `setup` | Worktree created or re-entered, dependencies synced | discussing/executing |
| `investigation` | Gap-analysis of existing code against a dated issue, no code written | discussing |
| `planning` | Brainstorming, writing the spec, writing the plan | discussing |
| `awaiting_approval` | Plan written, waiting on the human | discussing |
| `implementation` | Applying the approved plan; carries `step N/total` | executing |
| `checkpoint` | Self-review, Codex review, commit | executing |
| `blocked` | Cannot continue without the human | blocked |

An unknown phase is rejected with the valid values listed. Task-specific detail belongs
in `message`, never in a new phase.

`complete` and `merged` are deliberately absent: the lifecycle status already states
both, and two fields claiming the same fact drift apart.

### Steps

`step` is the plan task **currently in progress**, not the last one completed —
reporting at the start of each task is what makes `3/6` answer "how much is left", and
keeps `message` describing work that is happening rather than work that is over.

`step` and `step_total` are supplied together or not at all. Rejected combinations:

- `step` without `step_total`, or `step_total` without `step`
- `step < 1`
- `step_total < 1`
- `step > step_total`

Steps belong to `implementation`. Other phases omit them.

## CLI contract

```bash
python <path>/orch.py progress \
  --agent A \
  --phase implementation \
  --step 3 --step-total 6 \
  --msg "wiring the orch progress CLI" \
  --next "status output"
```

Behaviour:

- Resolves the project from the linked directory, exactly as `orch report` does.
- Resolves the agent's single active task; requires `--task` when the agent has more
  than one and no unique target exists.
- Validates the phase against the closed set and the step pair against the rules above,
  failing loudly with the valid values listed.
- Truncates `--msg` at 200 characters and states the truncation in its result. A worker
  never fails because a message was long.
- Appends one `kind=progress` event. Never writes lifecycle status. Never sets
  `needs_human`.
- Rejects tasks in `done` or `merged`, pointing at `orch report` for lifecycle changes.
  Permitted on `queued`, `discussing`, `executing`, and `blocked`.
- Treats a row identical to the task's current progress (same phase, step, step_total,
  message, next_step) as a no-op, so re-reporting the same milestone after a resume
  does not duplicate.
- Supports `--json` for the orchestrator.

`orch report --status blocked` additionally writes a `phase=blocked` progress row,
carrying the blocker reason as its message. This keeps a blocked worker to a single
command; the preceding progress row survives in history as context for what it was
doing when it stopped.

### `/report` convenience form

```text
/report progress implementation 3/6 wiring the CLI; next: status output
```

Parses into the structured call above, for when the human tells a running agent to
update the orchestrator. `/work` and `/checkpoint` call the CLI directly so the
structured fields cannot be lost in prose. The existing forms are unchanged:

```text
/report executing executing plan
/report note discovered an existing helper
/report blocked missing API credentials
/report done ready for review
```

## Reporting points

Wired into the skills as they already run.

| # | Moment in `/work` | Phase | Carries |
|---|---|---|---|
| 1 | Worktree created/re-entered and `orch deps` finished (`work/SKILL.md:44-88`) | `setup` | "worktree ready, deps synced" |
| 2 | Gap-analysis pass on a dated issue (`work/SKILL.md:97-103`) | `investigation` | what is already shipped vs missing |
| 3 | Brainstorm, spec, and plan writing | `planning` | what is being designed |
| 4 | Plan file written, awaiting approval | `awaiting_approval` | plan path |
| 5 | On approval, then at the **start of each plan task** | `implementation` | `step N/total`; message = the task being started; next = the one after |
| 6 | Entering `/checkpoint` steps 1-2 | `checkpoint` | "self-review", then "codex review" |
| 7 | Commit and completion (`checkpoint/SKILL.md:80-89`) | — | existing `report --status done`, unchanged |
| 8 | Any blocker | `blocked` | written automatically by `report --status blocked` |

`step_total` comes from counting the tasks in the approved plan file — a number that
exists before implementation begins.

This **replaces** `/report plan task N done` (`work/SKILL.md:118`) rather than running
beside it; keeping both would write two rows per plan task in two vocabularies.

A six-task plan produces roughly eleven updates across a session.

### Reporting rule for workers

- Always report a phase transition.
- Report at the start of each plan task, not at each checkbox or command.
- Report when the expected next step changes materially.
- Never report to signal that you are still alive. There is no heartbeat.

## Read paths

### `orch status` (human)

One extra line per active agent, shown only when progress exists:

```text
A  executing   implementation  3/6  wiring the orch progress CLI
     next: status output · 12m ago
B  discussing  awaiting_approval     plan ready: docs/.../plan.md
     next: human approval · 41m ago
C  executing   checkpoint            codex review
     next: commit · 3m ago
```

Tasks without progress render exactly as they do today. Age is shown plainly, with no
staleness verdict attached — 41 minutes on `awaiting_approval` means the human has not
answered, not that anything is wrong.

### `orch status --json`

Each task gains a `progress` object, or `null` when nothing was reported, so consumers
can tell "not reported" from "reported with no detail":

```json
{
  "id": 42,
  "agent": "A",
  "status": "executing",
  "progress": {
    "phase": "implementation",
    "step": 3,
    "step_total": 6,
    "message": "wiring the orch progress CLI",
    "next_step": "status output",
    "updated_at": "2026-08-12T10:30:00Z"
  }
}
```

### `/orchestrate`

Three changes, all in the reading direction:

1. A new short section, *Reading worker progress*: progress is informational, read from
   `orch status --json`, never parsed out of event prose.
2. The opening report of any invocation includes a one-line roll call of active agents
   built from those snapshots, so "who is where" is answered before the human asks.
3. An explicit non-rule alongside the existing merge authority rules: **a late phase is
   not a merge signal.** `phase=checkpoint` means the worker is reviewing its own code.
   Only `status=done`, plus the branch, plus green tests authorizes a merge. Left
   unstated, an agent reading `checkpoint` will eventually decide it is close enough.

Progress also joins the pre-merge read: the orchestrator already scans for
`kind=warning` events before merging (`orchestrate/SKILL.md:51`), and now carries the
last phase and message into any merge-blocked notification, so a blocker records what
the worker was doing when it stopped.

### Dashboard

Minimal pass only: the agent card shows the same snapshot line, and progress events
appear in the existing feed. Rendering must be null-safe and escape-safe for messages
containing punctuation.

## Failure and recovery

Progress is telemetry and must never damage the work it describes.

- A failed progress write is retried once. If it still fails, the worker posts a
  `kind=warning` event if it can and **continues the actual task**. Telemetry failure
  never converts a task to `done` or `blocked`.
- A worker that cannot resolve its task uses the existing blocker path; it does not
  write an orphan progress row.
- A rejected phase or step pair fails loudly at the CLI. The worker corrects the call or
  drops that one report and proceeds.
- After a crash, the last progress row remains as recovery context. On resume the
  worker's next report supersedes it for display; the no-op rule keeps a re-reported
  identical milestone from duplicating.
- When a task reaches `done` or `merged`, its final progress row is retained and the
  lifecycle status is authoritative for display.

## Compatibility

- All new columns are nullable and added through `_add_column` (`db.py:61`), which
  already tolerates the concurrent-migration race of A/B/C starting at once against a
  legacy database. The migration is idempotent.
- Existing tasks read back `progress: null`.
- Existing events render unchanged.
- `orch report` and `orch post` keep their current signatures and behaviour.
- Anything inspecting only `status` needs no modification.

## Testing

Extending the existing test files.

**`test_db.py`**

- A fresh schema contains the progress columns.
- A legacy database migrates successfully, and idempotently on a second open.
- Latest progress returns the newest row, and `None` when no progress exists.
- Progress leaves lifecycle `status` untouched.
- Progress never sets `needs_human`.
- A row identical to the current progress is a no-op.
- `report --status blocked` writes a `phase=blocked` progress row.

**`test_cli.py`**

- Progress resolves the task from the agent when unambiguous.
- An agent with multiple active tasks requires `--task`.
- Rejects unpaired steps, `step < 1`, `step_total < 1`, and `step > step_total`.
- Rejects unknown phases, listing the valid ones.
- Truncates an over-long `--msg` and reports it.
- Refuses `done` and `merged` tasks.
- `--json` matches the documented shape.
- Existing `report` and `post` invocations are unaffected.

**`test_server.py`**

- Status renders with and without progress.
- Rendering is null-safe and escape-safe with punctuation in messages.

Skill changes (`/work`, `/report`, `/checkpoint`, `/orchestrate`) are prose and are
verified by review against the reporting-points table, not by automated test.

Run the full existing suite before considering the feature complete.

## Implementation sequence

1. Migration and the derived latest-progress read.
2. The `orch progress` command, with validation, no-op rule, and JSON output.
3. Tests for 1 and 2.
4. `orch status` human output and `--json` shape.
5. Skill instructions: `/work`, `/report`, `/checkpoint`, `/orchestrate`.
6. Dashboard minimal pass.
7. Full test suite.

Each step is independently reviewable. Nothing about merge behaviour changes at any
point.

## Out of scope

The dashboard redesign — a glanceable view of five simultaneous agents — is a separate
spec, to be written after living with real progress data. Designing that view before
seeing a single real progress event would be guessing.

## Departures from the draft

Relative to `progress-reporting-spec.md`:

- **No heartbeats.** The `kind` field (`milestone` | `heartbeat`), the interval, the
  deduplication window, and the configuration setting are all removed. Workers report at
  boundaries or not at all.
- **Events only.** The seven `progress_*` columns on `tasks`, the atomic dual-write, and
  its tests are dropped in favour of deriving the snapshot from the newest event.
- **Seven phases, not thirteen.** `preflight`, `isolation`, and `dependencies` collapse
  into `setup`; `validation` and `review` fold into `checkpoint`; `complete` and `merged`
  are dropped as duplicates of the lifecycle status.
- **`phase_label` dropped.** A human-readable label derived from the phase is a second
  name for the same thing.
- **Steps mean the current task, not the last completed one** — stated explicitly rather
  than left implied.
- **`/report plan task N done` is replaced**, not kept alongside.
- **No ETA**, in any form.

## Acceptance criteria

1. A worker running a multi-task plan leaves visible milestones throughout, without
   being asked.
2. `orch status` and `orch status --json` show the current phase, step, message, next
   step, and update time for each active agent.
3. `/orchestrate` can state who is where — including how many plan tasks remain —
   without the human telling it.
4. Progress never alters lifecycle status and never raises `needs_human`.
5. A late phase never triggers a merge; only `done` does.
6. Existing databases, tasks, commands, and merge behaviour are unaffected.
7. Tests cover migration, validation, persistence, CLI behaviour, rendering, and
   backward compatibility.
