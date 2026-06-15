---
name: report
description: One-word progress reporting for a worker agent in the orchestrator system. Usage `/report <status> <message>` (e.g. `/report executing wiring auth`, `/report blocked need API key`, `/report done`). Wraps `orch report`.
user-invocable: true
---

# Report

Report your progress to the orchestrator with no flags to remember. You are a worker
agent; your identity is in `ORCH_AGENT` and the project in `ORCH_PROJECT` — exported in
the terminal **before** `claude` was launched (they do not persist if set from inside
the session). Resolve `<path>` = the orchestrator repo path
(`C:/Users/MattiaDaCampo/Documents/orchestrator` — NOT your current project).

## Usage

`/report <status> <message>` where `<status>` is one of
`executing` · `done` · `blocked` · `note`.

- First word is a known status → run:
  `python <path>/orch.py report --status <status> --msg "<the rest>"`
- First word is NOT a known status → treat the whole input as a note:
  `python <path>/orch.py report --status note --msg "<the whole input>"`
- `/report done` needs no message — the branch is auto-detected from git.

## Notes

- `blocked` automatically pings the human on Telegram — use it only when you truly need
  intervention.
- Keep messages short; report often so the orchestrator and dashboard stay live.
- Do not pass `--agent`/`--project`; they come from `ORCH_AGENT`/`ORCH_PROJECT`. If a
  report fails with `no agent given`, those env vars were not exported before `claude`
  launched — tell the human to set them and relaunch from the same shell.
