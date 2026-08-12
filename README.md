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
   link this repo's `.claude/skills/*` into `~/.claude/skills/`
   (see [Installing skills](#installing-skills-for-worker-windows)).
2. **Register the project and bind it to its directory, once:**

   ```bash
   python orch.py init myproject
   cd /path/to/myproject/checkout && python /path/to/orchestrator/orch.py link myproject
   ```

   `link` records the checkout's path, so from then on every orch command run inside
   that directory (or any worktree under it) infers the project automatically — **no
   env vars, no relaunch.** This is what makes the multi-project, multi-window setup
   painless. `orch prompt --agent A` / `--orchestrator` prints the exact per-window
   setup if you want it.
3. **Open each window inside its checkout and start the loop** — nothing else to wire:
   - orchestrator window (run inside the project's main checkout): `/loop /orchestrate`
   - each worker window (A/B/C): `/loop /work A`

   The orchestrator window queues 2-3 parallel kickoffs with you on start. Workers pass
   `--agent A` themselves; the project resolves from the linked directory. (`ORCH_PROJECT`
   still works as an override if you ever need it.)
4. **Watch progress** with `orch serve` (dashboard) or via Telegram pings.

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
| `link <name>` | bind the current directory to a project, so commands run here (and in worktrees under it) infer it automatically — no `--project`/env needed |
| `task add` | create a task (`--agent --title [--context --status --issue --branch --worktree]`); default status `queued` |
| `task update` (alias `task amend`) | amend a live task (`--task <id> [--status --branch --worktree --issue --plan --context]`) |
| `deps` | fast-sync `node_modules` into the current worktree, for **every** npm project in the tree (root, `app/`, one per workspace — anywhere a `package-lock.json` lives outside `node_modules`): copies from the matching directory of the linked project root when the lockfile matches (no network, no reinstall — a fully independent copy, not a hardlink), else runs `npm ci` there; no-op if not an npm project or that `node_modules` is already present |
| `next --agent A [--json]` | the agent's single active task, or empty |
| `claim --agent A [--json]` | atomically take the agent's oldest `queued` task (→ `discussing`) |
| `report --status S [--msg --agent --branch]` | worker shortcut: post `executing\|done\|blocked\|note`; agent from `ORCH_AGENT`; `done` auto-detects branch (never records `main`/`master`); `blocked` pings you |
| `progress --agent A --phase P [--step N --step-total M --msg --next --task --json]` | record what this worker is doing and how far into its plan it is; phases: `setup` `investigation` `planning` `awaiting_approval` `implementation` `checkpoint` `blocked`. Never changes task status, never pings the human |
| `post` | append an event; updates the task on `--status`/`--branch`; `--kind status\|note\|blocker\|handoff\|needs_discussion\|needs_human\|warning` |
| `status [--json]` | current agent/task state + recent events; surfaces a `WAITING ON YOU` banner |
| `prompt --agent A \| --orchestrator` | print a self-contained, terminal-readable bootstrap prompt (repo path, identity vars, loop cmd, queued task) |
| `wait [--timeout --interval]` | block until project state changes (new event / task transition) or timeout; exit 0 on change, 2 on timeout |
| `log [--agent -n]` | recent event feed |
| `notify --msg ... [--title ...]` | send a Telegram ping (dry-run if no token) |
| `serve [--port]` | on-demand web dashboard: working agents with phase and step progress, tasks waiting to merge, and a collapsed event feed (defaults to the only project if there is one) |

**Waiting on the human.** Posting `needs_discussion`, `blocker`, or `needs_human` — or
reporting a `blocked` status (`orch report --status blocked` / `/report blocked ...`) —
raises a `needs_human` flag on the task; `status` then lists those agents under
`WAITING ON YOU: A (reason), …` (also highlighted on the dashboard, which shows a
connected/disconnected health indicator). The flag clears automatically when the task
moves to `executing`/`done`/`merged`. Workers post `kind=warning` when they skip or
downgrade a step (e.g. Codex review unavailable) so the orchestrator sees it before
merging.

**Worker progress.** Lifecycle status answers "what state is this task in?"; progress
answers "what is the worker doing, and how much is left?" Workers call `orch progress`
at phase boundaries and at the start of each plan task, carrying `step N/total` taken
from the plan's task count. It is event-driven — there is no heartbeat and no timer —
and purely informational: progress never changes a task's status, never raises
`needs_human`, and never authorizes a merge. `orch status` shows the latest snapshot
per agent; `--json` exposes it as a `progress` object (`null` when nothing was
reported):

```
A: executing — Progress reporting [feat/progress]
     implementation 3/6 · wiring the orch progress CLI
     next: status output · 12m ago
```

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
  (`executing`/`done`/`blocked`/`note`), plus `/report progress <phase> [N/total]
  <message>` for a structured progress update; no flags to remember.
- **`/checkpoint`** — worker post-work flow: code review → optional Codex review →
  commit → auto-report `done`. Does not touch Linear (the orchestrator owns that).
- **`/agent-handoff`** — spawn a named background `claude` session with a given
  prompt. Standalone (no orchestrator knowledge) — use it any time you want to hand
  off work without opening a pane by hand. `/orchestrate` uses it to delegate
  kickoffs when you ask it to.

All five live in `.claude/skills/`.

## Installing skills for worker windows

Worker agents run inside the *target* projects they build, not this repo, so the
skills must be reachable everywhere. Install them at user level by **linking** this
repo's `.claude/skills/*` into `~/.claude/skills/` (link, not copy — a copy goes stale
and your edits never reach running agents).

macOS / Linux:

```bash
for s in work report checkpoint orchestrate agent-handoff; do
  ln -s "$(pwd)/.claude/skills/$s" ~/.claude/skills/$s
done
```

Windows — `ln -s` from Git Bash often silently falls back to a copy, so use a directory
**junction** (no admin needed), pointing at this repo:

```cmd
for %d in (orchestrate work report checkpoint agent-handoff) do mklink /J "%USERPROFILE%\.claude\skills\%d" "C:\path\to\orchestrator\.claude\skills\%d"
```

Verify the link is live (not a stale copy) by diffing a skill against this repo; they
must be identical. Note: Git Bash `[ -L ]`/`ls -la` does **not** flag junctions as
symlinks — use `diff` to check, not `ls`.

No per-window environment setup is needed: the project resolves from the linked
directory (`orch link myproject`, see [Getting started](#getting-started)) and workers
pass `--agent A` themselves. If you prefer env vars, `ORCH_PROJECT` (and `ORCH_AGENT`)
still override resolution when set — but they must be exported **before** `claude`
launches, since env vars set from inside a session do not persist between commands.

## Recommended: git safety hook

Worker/orchestrator agents run unattended for long stretches — nobody is watching the
moment a command actually executes. `hooks/git_guardrails.py` is a `PreToolUse` hook
that blocks the small set of git commands that destroy history or uncommitted work
outright: force push, `clean -f`, `branch -D`, `checkout .` / `restore .`, and a hard
reset to a moving target (no arg, `HEAD~n`, a branch/tag name, `origin/main`, ...). A
hard reset to a **specific full commit SHA** is deliberately allowed — that's the shape
of a recorded rollback point, which is exactly what `orchestrate/SKILL.md`'s merge
safety step uses to restore `main` if tests fail after a clean merge; a blanket
`reset --hard` block would silently defeat that safety net. It's **not installed by
default** — this repo only ships the script; you decide whether and where to wire it in
(globally in `~/.claude/settings.json` so it covers every agent regardless of target
project, or per-project if you'd rather scope it narrower):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python C:/Users/MattiaDaCampo/Documents/orchestrator/hooks/git_guardrails.py"
          }
        ]
      }
    ]
  }
}
```

It only inspects `Bash` tool calls and only matches the specific destructive patterns
above — normal git usage (commit, push, merge, checkout a branch, etc.) is unaffected.

## Telegram notifications

`orch notify` reads `ORCH_TG_TOKEN` + `ORCH_TG_CHAT`, or a JSON file at
`~/.orchestrator/telegram.json` (`{"token": "...", "chat_id": ...}`; override the path
with `ORCH_TG_CONFIG`). With no credentials it prints the message and exits 0, so the
loop never breaks.

## Development

```bash
python -m pytest -q   # or: python -m unittest discover -s tests
```
