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
| `task add` | create a task for an agent (`--agent --title [--issue --branch --worktree]`) |
| `task update` | amend a task (`--task <id> [--status --branch --issue]`) |
| `post` | append an event; updates the task on `--status`/`--branch` |
| `status [--json]` | current agent/task state + recent events |
| `log [--agent -n]` | recent event feed |
| `serve [--port]` | on-demand web dashboard |

## Orchestrating skill

`.claude/skills/orchestrating/SKILL.md` drives the orchestrator session: read state,
reconcile with Linear, split parallel work, hand out worker prompts, acknowledge
completions.

## Development

```bash
python -m pytest -q   # or: python -m unittest discover -s tests
```
