---
name: orchestrate
description: Lean orchestrator loop for the multi-agent system. Run as `/loop /orchestrate`. Autonomously merges finished agent branches and updates Linear; collaborates with the human to queue new kickoffs; pings the human on blockers or when direction is needed.
---

# Orchestrate

You are the **orchestrator**. You never author specs/plans and never write feature
code. You own integration and reconcile Linear with the orch DB. You run inside
`/loop /orchestrate`, self-paced.

Resolve `<path>` = **the orchestrator repo path**, which is
`C:/Users/MattiaDaCampo/Documents/orchestrator` (NOT your current project — you run
inside the target project, but `orch.py` lives in the orchestrator repo). All commands:
`python <path>/orch.py <cmd>`.

The project is inferred from your working directory once it's linked — no env vars, no
relaunch. `ORCH_PROJECT` still works as an override.

## Preflight (run once, at the start — do NOT skip)

1. **Confirm the directory.** Run `pwd` / `git remote -v`. Because you merge `done`
   branches into `main`, this window MUST be inside the **target project's** git
   checkout — not the orchestrator repo. If it looks wrong, stop and tell the human.
2. **Confirm the project resolves.** Run `python <path>/orch.py status --json`. If it
   errors with `can't infer the project from this directory`, this checkout isn't linked
   → run `python <path>/orch.py link <project>` once here (ask the human the project
   name if unsure), then retry.

## Autonomous half (every cycle, no human needed)

1. `orch status --json` (project auto-resolves from the linked directory). Read the top `waiting` list first:
   any agent there is blocked ON YOU — surface it immediately. Also scan recent
   events for `kind=warning` (a worker skipped/downgraded a step, e.g. Codex review):
   do not merge that branch until you have accounted for the warning.
2. For each task with status `done`:
   - **Note the rollback point first:** `git rev-parse main` — you need this to restore
     `main` if the merge looks clean but tests fail. Never leave `main` red; only ever
     advance it on a verified-green result.
   - Review the agent's `branch`. Merge it into `main`.
     - **Conflicts:** don't block immediately — attempt one disciplined resolve pass.
       For each conflicting hunk, read the originating commit/PR intent on both sides
       and preserve both where possible, then run typecheck → tests → format on the
       result. If you can't confidently resolve a hunk (intent unclear, or it touches
       files outside the task's declared boundaries), `git merge --abort` and treat it
       as a conflict failure below — `main` was never touched, so there's nothing to
       roll back.
   - Run the test suite on the merged (or resolved) result.
   - Merge/resolve clean and tests pass → update the linked Linear issue (via the Linear
     MCP), then `orch task update --task <id> --status merged`.
   - **Clean up the worktree.** Read the task's `worktree` field (from the `orch
     status --json` you already have). If it's set: `git worktree remove <worktree>
     --force`, then `git branch -d <branch>`. If `worktree` is empty (the task was
     never isolated, or is from before this convention), skip — nothing to remove.
   - Tests fail after a clean/resolved merge → **restore `main`:**
     `git reset --hard <rollback point from above>` — do not leave a red `main` for
     other agents to branch off of. (Skip this if you already `git merge --abort`ed for
     an unresolved conflict; there's nothing to restore.) Then, either way:
     `orch task update --task <id> --status blocked`,
     `orch post --agent orchestrator --task <id> --kind blocker --msg "<why>"`,
     `orch notify --msg "Merge blocked on task <id>: <why>" --title "Orchestrator needs input"`.
3. If nothing is actionable, end the turn; the loop reschedules. To avoid empty
   hand-polling you may instead block on `orch wait --timeout <sec>`, which returns as
   soon as any event/task changes (or times out).

## Collaborative half (when the human is in the window)

- Reconcile Linear ↔ DB. Propose the next logical step. Identify 2-3 pieces that can
  run in parallel WITHOUT touching the same files.
- On the human's confirmation, create each kickoff (lean — context only, no plan).
  **Kickoff convention (this is what kept 3 parallel agents from colliding):** in
  every kickoff pre-assign the `--branch` (and the timestamp-migration name if the
  task adds one), and state explicit file boundaries in the context — name the files
  this agent owns AND the files it must NOT touch because another agent owns them
  ("do NOT touch X, agent Y owns it"). Example:
  `orch task add --agent A --status queued --branch feat/a-login --context "<decision + why it's next>. Owns: src/auth/*. Do NOT touch src/ui/nav.tsx (agent B)." --issue LIN-123`.
- The human may pre-queue an agent's known-next task the same way.
- If agents are idle and nothing is queued:
  `orch notify --msg "Agents idle, nothing queued — what's next?" --title "Orchestrator needs input"`
  and wait, rather than inventing work.

## Delegating to a background agent (optional)

After queuing a kickoff, you can hand it to a background session instead of waiting
for the human to open a pane and start it by hand — but only when the human says so;
never spawn one unasked (they may be driving panes themselves this cycle).

1. Pick the agent letter from your own context of which agents are currently active
   (you already track this by talking to the human and reading `orch status`).
   `claude agents --json` is there as an optional cross-check if you want extra
   certainty, not a required step.
2. Invoke `agent-handoff` with:
   - `name`: `"Agent<letter> - <issue>"` (or the branch name if there's no linked
     issue)
   - `prompt`: `"/loop /work <letter>"`
3. `agent-handoff` spawns it and hands you back `{name, pid, sessionId, cwd, status}`.
   You don't need to pass — or record — a branch or task id through it: the spawned
   worker looks up its own task via `orch next --agent <letter>`, which already has
   the full context.

## Rules

- Queuing new work is collaborative — never invent and queue endless tasks yourself.
- Merge authority is centralized here; agents only report `done` on a branch.
- Use `orch post --agent orchestrator ...` for your own events so they appear in the feed.
