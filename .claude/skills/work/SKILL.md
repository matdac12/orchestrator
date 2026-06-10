---
name: work
description: Worker-agent loop for the orchestrator system. Run as `/loop /work A` (or B/C). Polls the orch DB for this agent's task; on a queued kickoff it pings the human and brainstorms the spec/plan, then on approval executes the plan and reports — all via the orch CLI.
---

# Work (Agent <AGENT>)

You are a **worker agent**. Your identity is the single argument passed to this
skill (e.g. `A`). You run inside `/loop /work A`, self-paced — never poll on a tight
timer; do one cycle, and if idle, let the loop reschedule you.

Resolve `<path>` = the orchestrator repo path once, and set `ORCH_PROJECT` for the
project you serve (the human tells you, or it is already exported). All commands:
`python <path>/orch.py <cmd>`.

## One cycle

1. **Find my task:** `orch next --agent <AGENT> --json`.
   - Empty output → say "idle, nothing queued" and end the turn. The loop rechecks later.
2. **Branch on `status`:**

   - **`queued`** → `orch claim --agent <AGENT> --json` to take it (→ `discussing`).
     Then:
     - `orch notify --msg "Agent <AGENT>: <title> — <context>" --title "Come discuss"`
     - Post the signal: `orch post --agent <AGENT> --kind needs_discussion --msg "claimed, awaiting brainstorm"`
     - Brainstorm WITH the human: invoke `superpowers:brainstorming`, using the
       task's `context` as the starting brief, through to `superpowers:writing-plans`.
     - When the plan file exists: `orch task update --task <id> --plan <plan_path>`.
     - Ask the human to approve the plan. On approval, continue to step 3.

   - **`discussing`** (resumed) → continue the brainstorm/plan from where it stands.

   - **`executing`** (resumed) → resume the plan from the first unchecked box.

   - **`blocked`** → do nothing; the human must intervene. End the turn.

3. **Execute (after plan approval):**
   - `orch post --agent <AGENT> --status executing --msg "executing plan"` (this also
     flips the task to `executing`).
   - Implement the plan via `superpowers:executing-plans`. After each plan task:
     `orch post --agent <AGENT> --msg "plan task N done"`.
   - Self-review: run the project's `/checkpoint` skill if present, then
     `superpowers:requesting-code-review`. Address findings.
   - Commit to a branch named `feat/<short-task-slug>`.

4. **Finish:**
   - `orch post --agent <AGENT> --status done --branch <branch> --msg "ready for review"`.
   - Loop back to step 1 for the next task.

## Blockers

If you cannot proceed at any point:
- `orch post --agent <AGENT> --status blocked --kind blocker --msg "<why>"`
- `orch notify --msg "Agent <AGENT> blocked: <why>" --title "Blocked"`
- End the turn and wait for the human.

## Rules

- Never merge to main — that is the orchestrator's job. You only push/commit a branch
  and report `done`.
- The human is only present for the brainstorm/plan-approval. Everything after
  approval is autonomous.
- Keep `orch` posts short and frequent so the orchestrator and dashboard see live
  progress.
