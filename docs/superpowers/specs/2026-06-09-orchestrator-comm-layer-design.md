# Orchestrator Communication Layer — Design

**Date:** 2026-06-09
**Status:** Approved design, pending implementation plan

## Problem

When running multi-agent Claude Code / Codex sessions, the human is currently the
message bus. One terminal runs an **orchestrator** agent (plans, splits work, hands
out prompts, reconciles with Linear). Three+ other terminals run **worker agents**
(A/B/C) in separate git worktrees. The orchestrator is blind to worker progress until
the human manually pastes status updates back and forth.

**Goal:** a shared communication layer so worker agents record their own progress and
the orchestrator reads live state directly — removing the human from the message loop.

## Scope (v1)

Communication layer **+ web dashboard**, started on demand. No always-on background
service yet. Linear stays the home of issues; this DB is the real-time coordination
layer for a session.

Explicitly **out of scope** for v1: a background Windows service, automatic Linear
API sync, remote agents, any dashboard control that mutates state.

## Architecture

- **`orch`** — a single Python CLI, standard library only (`sqlite3`, `argparse`,
  `http.server`, `json`, `unittest`). No pip installs. Runs anywhere Python 3 exists.
- **One global SQLite DB** at `~/.orchestrator/state.db`, shared by every terminal on
  the machine, in **WAL mode** for concurrent multi-terminal writes. Every command
  takes `--project <name>` (with an `ORCH_PROJECT` env-var fallback) to separate
  projects inside the one DB.
- **`orch serve`** — launches a stdlib web dashboard on demand that reads the DB.
- **`/orchestrating`** — a project-level Claude skill that teaches the orchestrator
  session to read state via `orch status` and run the human's workflow.

### Why a global DB

Worker agents A/B/C run in **separate git worktrees** (different directories) of the
same project. A repo-local DB would be a different file per worktree, so agents would
never see each other. A single global DB keyed by `--project` solves this and survives
across sessions, building a history.

## Data model

Agent "current status" is **derived** from the latest task/event data, not stored
separately.

### `projects`
| column | notes |
|---|---|
| `id` | PK |
| `name` | UNIQUE (e.g. `orchestrator`, `acme-app`) |
| `created_at` | timestamp |
| `notes` | optional free text |

### `tasks` — a unit of work assigned to an agent
| column | notes |
|---|---|
| `id` | PK |
| `project_id` | FK → projects |
| `agent` | free text (`A`/`B`/`C`, not hard-limited to 3) |
| `title` | short description |
| `status` | `todo` / `in_progress` / `blocked` / `done` / `merged` |
| `issue_ref` | optional Linear ID/URL (loose link) |
| `branch` | optional, e.g. `feat/x` |
| `worktree` | optional path |
| `created_at`, `updated_at` | timestamps |

### `events` — append-only message/activity log (agents → orchestrator)
| column | notes |
|---|---|
| `id` | PK |
| `project_id` | FK → projects |
| `task_id` | FK → tasks, nullable |
| `agent` | who posted |
| `kind` | `status` / `note` / `blocker` / `handoff` |
| `message` | text |
| `created_at` | timestamp |

**Status flow:** `orch post ... --status done` appends an `event` *and* updates the
linked task's `status`. Orchestrator and dashboard read current task statuses plus the
recent event feed.

## CLI surface

Every command takes `--project <name>` (except `init`), with `ORCH_PROJECT` env-var
fallback. `orch status` prints clean text by default and JSON with `--json` (dashboard
and skill use `--json`).

**Orchestrator / setup:**
- `orch init <name> [--notes "..."]` — register a project
- `orch task add --agent B --title "..." [--issue LIN-123] [--branch feat/x] [--worktree path]` — create a task; prints the new task ID
- `orch task update --task <id> [--status merged] [--branch ...] [--issue LIN-123]` — orchestrator-side amend (e.g. mark merged after merging)
- `orch status [--json]` — each agent's current task + status, plus latest events
- `orch log [--agent B] [-n 20]` — recent event feed
- `orch serve [--port 8787]` — launch the dashboard

**Worker agent reporting:**
- `orch post --agent B [--task <id>] --status in_progress --msg "starting X"`
- `orch post --agent B [--task <id>] --kind blocker --msg "need decision on Y"`
- `orch post --agent B [--task <id>] --status done --branch feat/x --msg "ready for review"`

`post` is the workhorse: appends an event and, when `--status`/`--branch` are given,
updates the task. `--task` is optional — if the agent has exactly one active task in
the project, `post` targets it automatically; ambiguity is a clear error.

## Web dashboard

`orch serve` starts a stdlib `http.server` on a fixed port (default 8787). Two routes:
- `GET /` — a single self-contained HTML page (inline CSS/JS, no build step, no
  external assets).
- `GET /api/state?project=<name>` — same data as `orch status --json`; the page polls
  it every ~3s and re-renders.

**Layout:** a column per agent showing current task + status (color-coded:
in_progress / blocked / done / merged), and below, a chronological event feed across
all agents. Read-only in v1.

## The `/orchestrating` skill

Project-level skill at `.claude/skills/orchestrating/`. When invoked in the
orchestrator session, it teaches that Claude to:

1. Run `orch status --project <name> --json` and read live agent/task state.
2. Pull the Linear project state (via the existing Linear MCP) and reconcile with the DB.
3. Run the workflow: discuss the next logical step → propose 2-3 parallel,
   non-file-conflicting tasks → create them with `orch task add` → hand the human
   ready-to-paste prompts for Agents A/B/C that already embed the right `orch post`
   commands and the `/checkpoint` step → acknowledge completions and mark tasks
   `merged` with `orch task update`.

This is the human's hand-written starting prompt encoded as a repeatable skill, wired
to live DB state instead of copy-paste.

## Error handling

- WAL mode + short retry-with-backoff on `database is locked` (concurrent writers).
- Friendly errors for unknown project/agent/task.
- `post` auto-targets the agent's single active task when `--task` is omitted; clear
  error when ambiguous.
- Dashboard renders an empty state gracefully if the DB or project doesn't exist yet.

## Testing

- `unittest` (stdlib) against a temp DB for the data layer: init, task add/update,
  post (event + task-status side effect), status query, locked-retry.
- CLI smoke tests via `subprocess`.
- A test that `/api/state` returns correct JSON.
