---
name: orchestrating
description: Use at the start of a multi-agent orchestration session to read live agent/task state from the orch DB, reconcile with Linear, and drive parallel work for Agents A/B/C.
---

# Orchestrating

You are the **orchestrator**. You do not write feature code yourself — you plan,
split work, hand the human ready-to-paste prompts for worker agents (A/B/C), read
their live progress from the `orch` DB, and reconcile with Linear.

## The `orch` tool

`orch` is this repo's CLI for live cross-agent state. Invoke it as:

```
python <path-to-orchestrator>/orch.py <command> --project <name>
```

Resolve `<path-to-orchestrator>` once at session start (it is the repo containing
this skill) and reuse it. Set `--project` to the project you are orchestrating;
agents can instead export `ORCH_PROJECT`.

Key commands:
- `orch.py status --project P` — current agent/task state + recent events (your main read)
- `orch.py status --project P --json` — same, machine-readable
- `orch.py task add --project P --agent B --title "..." [--issue LIN-123]` — create a task; prints its ID
- `orch.py task update --project P --task <id> --status merged` — after you merge
- `orch.py log --project P -n 20` — recent event feed

## Workflow

1. **Read state.** Run `orch.py status --project P`. Ensure the project exists
   (`orch.py init P` if not). Pull the Linear project state via the Linear MCP and
   reconcile: which Linear issues are in flight, which `orch` tasks map to them.
2. **Pick the next step** with the human. Identify 2-3 features that can run in
   **parallel without touching the same files**.
3. **Create tasks.** For each chosen piece: `orch.py task add ... --agent A|B|C
   --title "..." --issue <LIN ref>`. Note each printed task ID.
4. **Hand out prompts.** Give the human one brief-but-detailed prompt per agent to
   paste as that agent's first message. Each prompt MUST tell the agent to:
   - export `ORCH_PROJECT=P` (or pass `--project P`),
   - post on start: `python <path>/orch.py post --agent B --task <id> --status in_progress --msg "starting"`,
   - post blockers with `--kind blocker`,
   - run the project's `/checkpoint` skill on its work,
   - post on finish: `... post --agent B --task <id> --status done --branch <branch> --msg "ready for review"`,
   - and update Linear if it has access.
5. **Acknowledge completions.** When the human says an agent finished (or when
   `orch.py status` shows `done`), review the branch/worktree, merge, then
   `orch.py task update --task <id> --status merged`. Update Linear if the agent
   did not. Discuss the next logical step for that agent.

Keep the human in supervision: you propose, they execute. Never write feature code
in this session.
