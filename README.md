# orchestrator

A shared communication layer for multi-agent Claude Code / Codex sessions. Worker
agents report progress to one global SQLite DB; the orchestrator reads live state
instead of relying on copy-paste between windows.

## The problem

When you run several Claude Code windows in parallel — one coordinating, two or three
writing code — those windows **can't see each other**. Each session is isolated, so
keeping them in sync means copy-pasting status by hand ("agent B finished login", "C
is blocked", "this branch is ready to merge"). It's fragile and the thread gets lost.

## What this is

A single shared source of truth: a small standard-library Python CLI (`orch.py`, no
`pip install`) backed by **one global SQLite DB** at `~/.orchestrator/state.db`. Every
session — in any project — reads and writes the same DB, so the orchestrator sees
**live** state. On top of the CLI, four skills turn this into an autonomous loop.

## How it works

### Task lifecycle

```
queued → discussing → executing → done → merged     (+ blocked)
```

- `queued` — kickoff in the queue, not yet claimed
- `discussing` — a worker claimed it and is brainstorming the spec/plan with the human
- `executing` — plan approved, the worker is writing code
- `done` — branch ready, code committed, awaiting merge
- `merged` — the orchestrator integrated it into `main`
- `blocked` — something broke; the human must step in

### Roles

| role | windows | does | never does |
|---|---|---|---|
| **Orchestrator** | 1 | merges `done` branches into `main` + runs tests, reconciles Linear, pings the human on blockers | writes specs, plans, or feature code |
| **Worker** (A/B/C) | 1 each | claims a task, brainstorms the plan with the human, executes autonomously, reviews + commits, reports `done` | merges to `main` |
| **Human** | — | present only at kickoff / plan approval and for direction or blockers | babysits execution |

### Why it's designed this way

- **One source of truth** — no copy-paste, no lost state.
- **Centralized merge authority** — only the orchestrator touches `main`; agents work on
  isolated branches and don't clobber each other.
- **Human in the loop only where judgment matters** — planning and blockers; everything
  else is autonomous.
- **Self-paced loops** — `/loop` reschedules itself; no tight polling that burns tokens.
- **Standard library only** — runs anywhere with Python 3.8+, zero dependencies.

## Getting started

1. **Install the skills at user level** so worker windows in any project can see them —
   symlink (or copy) this repo's `.claude/skills/*` into `~/.claude/skills/`
   (see [Installing skills](#installing-skills-for-worker-windows)).
2. **Open Claude Code inside the target project** you want built.
3. **Paste the orchestrator bootstrap prompt** — it registers the project, queues 2-3
   parallel kickoffs with you, then starts `/loop /orchestrate`.
4. **Open N worker windows** (one per agent); in each, export `ORCH_PROJECT` and
   `ORCH_AGENT=A`, then run `/loop /work A`.
5. **Watch progress** with `orch serve` (dashboard) or via Telegram pings.

## Requirements

Python 3.8+. No pip installs.

## Quick start

```bash
python orch.py init myproject
python orch.py task add --project myproject --agent B --title "build login" --issue LIN-12
python orch.py post --project myproject --agent B --status in_progress --msg "starting"
python orch.py status --project myproject
python orch.py serve --project myproject   # dashboard at http://127.0.0.1:8787
```

The DB lives at `~/.orchestrator/state.db` (override with the `ORCH_DB` env var). Set
`ORCH_PROJECT` to avoid repeating `--project`.

## Commands

| command | purpose |
|---|---|
| `init <name>` | register a project |
| `task add` | create a task (`--agent --title [--context --status --issue --branch --worktree]`); default status `queued` |
| `task update` (alias `task amend`) | amend a live task (`--task <id> [--status --branch --issue --plan --context]`) |
| `next --agent A [--json]` | the agent's single active task, or empty |
| `claim --agent A [--json]` | atomically take the agent's oldest `queued` task (→ `discussing`) |
| `report --status S [--msg --agent --branch]` | worker shortcut: post `executing\|done\|blocked\|note`; agent from `ORCH_AGENT`; `done` auto-detects branch (never records `main`/`master`); `blocked` pings you |
| `post` | append an event; updates the task on `--status`/`--branch`; `--kind status\|note\|blocker\|handoff\|needs_discussion\|needs_human\|warning` |
| `status [--json]` | current agent/task state + recent events; surfaces a `WAITING ON YOU` banner |
| `prompt --agent A \| --orchestrator` | print a self-contained, terminal-readable bootstrap prompt (repo path, identity vars, loop cmd, queued task) |
| `wait [--timeout --interval]` | block until project state changes (new event / task transition) or timeout; exit 0 on change, 2 on timeout |
| `log [--agent -n]` | recent event feed |
| `notify --msg ... [--title ...]` | send a Telegram ping (dry-run if no token) |
| `serve [--port]` | on-demand web dashboard (defaults to the only project if there is one) |

**Waiting on the human.** Posting `needs_discussion`, `blocker`, or `needs_human`
raises a `needs_human` flag on the task; `status` then lists those agents under
`WAITING ON YOU: A (reason), …` (also highlighted on the dashboard, which shows a
connected/disconnected health indicator). The flag clears automatically when the task
moves to `executing`/`done`/`merged`. Workers post `kind=warning` when they skip or
downgrade a step (e.g. Codex review unavailable) so the orchestrator sees it before
merging.

## Skills (the autonomous loop)

- **`/work <AGENT>`** — run a worker window as `/loop /work A`. Polls for its task,
  brainstorms with you on a kickoff, then executes the plan and reports. For
  dated/old issues it does an **investigation-first** pass (gap-analysis code-vs-issue,
  no code) and confirms scope with you before building, to avoid re-shipping work.
- **`/orchestrate`** — run the orchestrator window as `/loop /orchestrate`. Merges
  finished branches, updates Linear, and pings you for direction or blockers. Its
  kickoffs follow a **collision-avoidance convention**: pre-assign each task's branch
  (and migration name) and state explicit file boundaries ("owns X; do NOT touch Y,
  agent Z owns it") so parallel agents never clobber each other.
- **`/report <status> <message>`** — worker shortcut to record progress
  (`executing`/`done`/`blocked`/`note`); no flags to remember.
- **`/checkpoint`** — worker post-work flow: code review → optional Codex review →
  commit → auto-report `done`. Does not touch Linear (the orchestrator owns that).

Both live in `.claude/skills/`.

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

## Telegram notifications

`orch notify` reads `ORCH_TG_TOKEN` + `ORCH_TG_CHAT`, or a JSON file at
`~/.orchestrator/telegram.json` (`{"token": "...", "chat_id": ...}`; override the path
with `ORCH_TG_CONFIG`). With no credentials it prints the message and exits 0, so the
loop never breaks.

## Development

```bash
python -m pytest -q   # or: python -m unittest discover -s tests
```
