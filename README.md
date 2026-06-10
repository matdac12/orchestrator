# orchestrator

A standard-library Python tool that gives multi-agent Claude Code / Codex sessions a
shared communication layer: worker agents report progress to one global SQLite DB and
the orchestrator reads live state instead of relying on copy-paste.

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
| `task update` | amend a task (`--task <id> [--status --branch --issue --plan --context]`) |
| `next --agent A [--json]` | the agent's single active task, or empty |
| `claim --agent A [--json]` | atomically take the agent's oldest `queued` task (→ `discussing`) |
| `post` | append an event; updates the task on `--status`/`--branch`; `--kind status\|note\|blocker\|handoff\|needs_discussion` |
| `status [--json]` | current agent/task state + recent events |
| `log [--agent -n]` | recent event feed |
| `notify --msg ... [--title ...]` | send a Telegram ping (dry-run if no token) |
| `serve [--port]` | on-demand web dashboard |

Task lifecycle: `queued → discussing → executing → done → merged` (plus `blocked`).

## Skills (the autonomous loop)

- **`/work <AGENT>`** — run a worker window as `/loop /work A`. Polls for its task,
  brainstorms with you on a kickoff, then executes the plan and reports.
- **`/orchestrate`** — run the orchestrator window as `/loop /orchestrate`. Merges
  finished branches, updates Linear, and pings you for direction or blockers.

Both live in `.claude/skills/`.

## Telegram notifications

`orch notify` reads `ORCH_TG_TOKEN` + `ORCH_TG_CHAT`, or a JSON file at
`~/.orchestrator/telegram.json` (`{"token": "...", "chat_id": ...}`; override the path
with `ORCH_TG_CONFIG`). With no credentials it prints the message and exits 0, so the
loop never breaks.

## Development

```bash
python -m pytest -q   # or: python -m unittest discover -s tests
```
