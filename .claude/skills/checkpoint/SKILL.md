---
name: checkpoint
description: Project-agnostic post-work workflow for orchestrator worker agents. Runs code review, optional Codex review, commit, and auto-reports done to the orch DB. Invoke with /checkpoint after finishing a plan.
user-invocable: true
---

# Checkpoint — Worker Post-Work Workflow

Run this after completing the plan's implementation, before the work is considered
done. Execute the steps in order; do not skip Step 1 or Step 4.

Resolve `<path>` = the orchestrator repo path
(`C:/Users/MattiaDaCampo/Documents/orchestrator` — NOT your current project; you run
inside the target project but `orch.py` lives in the orchestrator repo). Your identity
is `ORCH_AGENT`, project `ORCH_PROJECT` — both exported in the terminal before `claude`
launched (they do not persist if set from inside the session). If a command reports
`no agent given`, that is why.

**Never degrade silently.** If you skip or downgrade any step below (Codex
unavailable, token expired, review run at a lower effort than the change deserved,
tests not run), post a warning event so the orchestrator sees it before merging
instead of discovering it in your report:

`python <path>/orch.py post --agent $ORCH_AGENT --kind warning --msg "<step> skipped: <why>"`

## Step 1 — Code Review

Run `/code-review` on all changed code at an honestly chosen effort level:
- `/code-review low` — trivial change (typo, one-line tweak, mechanical rename)
- `/code-review` (default) — normal feature work or a single-area refactor
- `/code-review high` — risky or large change: new module, cross-cutting refactor,
  migration, anything touching money or production data

If unsure between two levels, go higher. Apply any fixes it makes; if it changed code,
note what changed.

## Step 2 — Codex Review (optional)

If the `codex` plugin is available, get a second opinion:
1. Invoke `/codex:rescue` (review-only): summarize what changed, point at the
   diff/files, ask for feedback on correctness/design/risk. Be explicit it is a review
   pass, not an edit pass.
2. Reason critically about the output — do not accept it at face value.
3. Present your analysis (agree/disagree + why) and discuss with the user.
4. Apply agreed changes, then re-run `/code-review` if code was modified.

If the `codex` plugin is not installed, the token expired mid-review, or the user
says "skip codex," post the warning event from the header (`<step> skipped: <why>`)
and go to Step 3.

## Step 3 — Commit

1. `git status` and `git diff` to review all changes.
2. Draft a clear commit message in English describing the "why."
3. Commit to your working branch (HEREDOC format, Co-Authored-By line).

## Step 4 — Report Done

Report completion to the orchestrator (auto-detects the branch):

`python <path>/orch.py report --status done --msg "ready for review"`

Do NOT update Linear — in the orchestrator system the orchestrator owns Linear updates
when it merges your branch. Your job ends at a committed branch + a `done` report.
