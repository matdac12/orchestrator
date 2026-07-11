---
name: report
description: One-word progress reporting for a worker agent in the orchestrator system. Usage `/report <status> <message>` (e.g. `/report executing wiring auth`, `/report blocked need API key`, `/report done`). Wraps `orch report`.
user-invocable: true
---

# Report

Report your progress to the orchestrator. You are a worker agent; pass your worker
letter as `--agent <AGENT>` (the letter you were invoked with as `/work <AGENT>`). The project resolves
from your linked directory — no env vars needed. Resolve `<path>` = the orchestrator
repo path (`C:/Users/MattiaDaCampo/Documents/orchestrator` — NOT your current project).

## Usage

`/report <status> <message>` where `<status>` is one of
`executing` · `done` · `blocked` · `note`.

- First word is a known status → run:
  `python <path>/orch.py report --agent <AGENT> --status <status> --msg "<the rest>"`
- First word is NOT a known status → treat the whole input as a note:
  `python <path>/orch.py report --agent <AGENT> --status note --msg "<the whole input>"`
- `/report done` needs no message — the branch is auto-detected from git.

## Notes

- `blocked` automatically pings the human on Telegram — use it only when you truly need
  intervention.
- Keep messages short; report often so the orchestrator and dashboard stay live.
- Pass `--agent <AGENT>` (your worker letter). The project resolves from the linked
  directory; `--project`/`ORCH_PROJECT` are optional overrides. If a report fails with
  `can't infer the project`, the checkout isn't linked — run `orch link <project>` once.
