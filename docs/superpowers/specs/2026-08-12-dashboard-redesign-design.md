# Dashboard Redesign

## Status

Approved — ready for planning.

Follow-up to `2026-08-12-worker-progress-reporting-design.md`, which deliberately
deferred this until real progress data existed.

## Summary

The dashboard renders one flat card per agent (name, status badge, task title, branch,
progress line) above a 50-event feed. That was adequate when the DB only knew a task's
lifecycle status. Now that workers report phase and `step N/total`, the page can answer
the question it exists for:

> What is everyone doing, and how much is left?

This redesign reorganises the page around that question: agents that are working, tasks
that are waiting to merge, and everything else out of the way.

## Goals

- Show the whole situation at a glance for ~5 simultaneous agents.
- Make "how much is left" readable per agent, from the plan's own step count.
- Surface tasks sitting `done` with a branch, since those are waiting on a single
  `/orchestrate` pass.
- Keep the page honest: never imply progress that wasn't reported.
- Make the client JS verifiable rather than hand-checked.

## Non-goals

- Triage. Mattia's other tools (T3 Code, the Claude Code app, cloud agents) already
  tell him when an agent needs him; the dashboard does not need to compete with them.
  The existing `WAITING ON YOU` banner stays as a safety net, not as the organising
  principle.
- A project management board. Queued work is not shown — it is not happening yet.
- Time estimates or ETAs, consistent with the progress spec.
- Server-side rendering, auth, or multi-project views.

## Usage context

The page is opened deliberately, read for ten seconds, and closed — not left open on a
second monitor. That favours **density and completeness** over large glanceable type:
more detail per agent, and the event history reachable without leaving the page.

## Layout

```text
┌──────────────────────────────────────────────────────────────┐
│ orch — myproject          3 working · 2 ready · connected ✓   │
├──────────────────────────────────────────────────────────────┤
│ ** WAITING ON YOU: D (missing API key)                        │
├──────────────────────────────────────────────────────────────┤
│ WORKING                                                       │
│                                                               │
│  A  executing   Progress reporting            feat/a-progress │
│     implementation  ███████████░░░░░░░  3/6                   │
│     wiring the orch progress CLI                              │
│     next: status output                              2m ago   │
│                                                               │
│  B  discussing  Login form                                    │
│     awaiting_approval                                         │
│     plan ready: docs/superpowers/plans/login.md               │
│     next: human approval                            41m ago   │
├──────────────────────────────────────────────────────────────┤
│ READY TO MERGE                                                │
│  D  feat/d-api      Notifications      done 12m ago           │
│  E  feat/e-search   Search indexing    done 41m ago           │
├──────────────────────────────────────────────────────────────┤
│ idle: F, G                                                    │
│ ▸ recent activity (50)                                        │
└──────────────────────────────────────────────────────────────┘
```

### Header

Project name, an aggregate count (`3 working · 2 ready`), and the existing
connected/disconnected health indicator. The aggregate answers "how much is going on"
before any card is read.

### Working section

One block per working agent, in **stable alphabetical order**. Ordering by recency or
staleness would make blocks jump between polls, moving the thing being read; on a page
re-read every few minutes, position is memory.

Each block shows: agent letter, lifecycle status, task title, branch (when set), then
the progress snapshot — phase, a bar with `N/total` when steps exist, the message, the
next step, and the age of the update.

**The bar renders only when `step` and `step_total` are both present.** Phases without
a finite plan (`planning`, `awaiting_approval`, `checkpoint`, `setup`) show the phase
name alone. A bar that silently means nothing is worse than no bar; there is no
"halfway because it is the middle phase".

An agent with no progress reported renders its status and title exactly as today.

### Ready to merge

A compact strip — not cards — for tasks with `status === 'done'`: agent, branch, title,
and how long it has been sitting. These tasks are not doing anything; they are waiting
on one `/orchestrate` pass. The age is the point: 41 minutes means it was forgotten.

### Idle and activity

Idle agents get a single line (`idle: F, G`). The 50-event feed is retained but
**collapsed behind a toggle**, so the default view is state-only while the history
stays one click away.

## Data and partitioning

No changes to `get_state`. `/api/state` already returns `agents` (each with
`current_task` carrying `progress`), `tasks`, `events`, and `waiting`.

The client partitions as follows:

- **working** — agents whose `status` is `queued`, `discussing`, `executing`, or
  `blocked`
- **ready to merge** — tasks with `status === 'done'`, independent of agents
- **idle** — agents in neither group

This partition is load-bearing. `get_state` falls back to an agent's most recent task
when it has no active one, so an agent whose task is `done` currently renders as a card
with status `done`. Under this split it appears once, in the merge strip.

A JS `ago()` helper mirrors `cli._age` so both surfaces read the same
(`2m ago`, `41m ago`, `3h ago`).

## Template mechanism

`PAGE` is currently a `.format()` string, so every CSS and JS brace must be doubled.
That is already error-prone and becomes untenable as the JS grows.

**The JS moves to `orch/dashboard.js`, served at `/dashboard.js`.** This removes brace
escaping entirely, gives the file real syntax highlighting, and — the deciding
reason — makes `node --check` a test rather than a manual step. `dashboard.py` keeps
the HTML and CSS, with `{project}` remaining its only substitution.

The cost is one extra route in `server.py` and reading a file from the package
directory. Both are small and contained.

## Escaping

Every user-controlled string — task title, branch, progress message, next step, event
message, blocker reason — passes through `esc()` before reaching `innerHTML`. Titles
and messages are written by agents and by Mattia, so markup in them must render as
text, not as HTML.

## Testing

**`tests/test_server.py`**

- The page renders and contains its section markers (`WORKING`, `READY TO MERGE`,
  the activity toggle) and the script tag for `/dashboard.js`.
- `/dashboard.js` is served with a JavaScript content type and a non-empty body.
- An unknown path still 404s.
- `node --check` over `orch/dashboard.js` passes; the test skips cleanly when node is
  not installed, so the suite stays green on a machine without it.

**Behavioural checks run in node** (not pytest, which cannot execute JS): the partition
puts a `done` task in the merge strip and not in working; the bar appears only with
steps; `esc()` neutralises markup; `ago()` matches `_age`'s thresholds.

## Compatibility

- `orch serve` keeps its CLI surface, port, and project resolution.
- `/api/state` is unchanged, so anything reading it keeps working.
- A DB with no progress data renders the same information the current dashboard shows.

## Acceptance criteria

1. With five agents running, the page shows what each is doing and, where the phase has
   steps, how many remain.
2. Tasks sitting `done` with a branch are visible with their age, separately from
   working agents, and appear exactly once.
3. Agent order does not change between polls.
4. No progress bar is drawn for a phase without a step count.
5. Markup in a task title or progress message renders as text.
6. The JS is syntax-checked by the test suite, not by hand.
