---
name: work
description: Worker-agent loop for the orchestrator system. Run as `/loop /work A` (or B/C). Polls the orch DB for this agent's task; on a queued kickoff it pings the human and brainstorms the spec/plan, then on approval executes the plan and reports — all via the orch CLI.
---

# Work (Agent <AGENT>)

You are a **worker agent**. Your identity is the single argument passed to this
skill (e.g. `A`). You run inside `/loop /work A`, self-paced — never poll on a tight
timer; do one cycle, and if idle, let the loop reschedule you.

Resolve `<path>` = the orchestrator repo path once
(`C:/Users/MattiaDaCampo/Documents/orchestrator` — NOT your current project; you run
inside the target project but `orch.py` lives in the orchestrator repo). All commands:
`python <path>/orch.py <cmd>`.

## Preflight (run once, at the start — do NOT skip)

Your identity and project come from `ORCH_AGENT`/`ORCH_PROJECT`, which the human must
have exported **in the terminal before launching `claude`**. You CANNOT set them from
inside the session — env vars do not persist between commands here. So:

1. **Confirm the directory.** Run `pwd` (and `git remote -v`). You must be inside the
   target project's checkout (where the code you build lives), NOT the orchestrator
   repo. If it looks wrong, stop and tell the human.
2. **Confirm identity is wired.** Run `python <path>/orch.py next --agent <AGENT> --json`.
   If it errors with `no project given`/`no agent given`, the env vars are missing →
   **stop**. Tell the human: "export `ORCH_PROJECT` and `ORCH_AGENT` in this terminal,
   then relaunch `claude` from the same shell" (or run `python <path>/orch.py prompt
   --agent <AGENT> --project <name>` for the exact setup). Do not try to `export` them
   yourself — it will not stick.

## One cycle

1. **Find my task:** `orch next --agent <AGENT> --json`.
   - Empty output → say "idle, nothing queued" and end the turn. The loop rechecks later.
2. **Branch on `status`:**

   - **`queued`** → `orch claim --agent <AGENT> --json` to take it (→ `discussing`).
     Then:
     - `orch notify --msg "Agent <AGENT>: <title> — <context>" --title "Come discuss"`
     - Post the signal: `orch post --agent <AGENT> --kind needs_discussion --msg "claimed, awaiting brainstorm"` (this specific kind has no /report alias; use it as-is). This raises the `needs_human` flag so the human's `orch status` shows you under "WAITING ON YOU".
     - **Investigation-first for dated/old issues.** If the issue is not freshly
       written (it references work that may already be underway or shipped — drift
       risk), do NOT start brainstorming a build. First run **PHASE 1 = gap-analysis**:
       read the current code vs the issue and report what is already done, partial, or
       missing — write NO code. Then **PHASE 2 = decide with the human** what (if
       anything) still needs building, and only then proceed to the brainstorm. If
       PHASE 1 shows the issue is already satisfied, say so and propose closing it
       rather than inventing work.
     - Brainstorm WITH the human: invoke `superpowers:brainstorming`, using the
       task's `context` as the starting brief, through to `superpowers:writing-plans`.
     - When the plan file exists: `orch task update --task <id> --plan <plan_path>`.
     - Ask the human to approve the plan. On approval, continue to step 3.

   - **`discussing`** (resumed) → continue the brainstorm/plan from where it stands.

   - **`executing`** (resumed) → resume the plan from the first unchecked box.

   - **`blocked`** → do nothing; the human must intervene. End the turn.

3. **Execute (after plan approval):**
   - `/report executing executing plan` (flips the task to `executing`).
   - Implement the plan via `superpowers:executing-plans`. After each plan task:
     `/report plan task N done` (recorded as a note).
   - Self-review and finish with `/checkpoint` — it runs code review, optional Codex
     review, commits your branch, and reports `done` for you.

4. **Finish:**
   - `/checkpoint` (Step 3 above) already reported `done`. Loop back to step 1 for the
     next task.

## Blockers

If you cannot proceed at any point:
- `/report blocked <why>` — records the blocker and pings the human automatically.
- End the turn and wait for the human.

## Rules

- Never merge to main — that is the orchestrator's job. You only push/commit a branch
  and report `done`.
- The human is only present for the brainstorm/plan-approval. Everything after
  approval is autonomous.
- Report via `/report` (short, frequent) so the orchestrator and dashboard stay live.
- `ORCH_AGENT` and `ORCH_PROJECT` must be exported in the terminal **before** `claude`
  was launched (they do not persist if set from inside the session), so `/report` and
  `/checkpoint` know who and where you are. If a command reports `no agent given`, that
  is the cause — see Preflight.
