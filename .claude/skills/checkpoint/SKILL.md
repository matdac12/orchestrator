---
name: checkpoint
description: Project-agnostic post-work workflow for orchestrator worker agents. Runs code review, optional Codex review, commit, and auto-reports done to the orch DB. Invoke with /checkpoint after finishing a plan.
user-invocable: true
---

# Checkpoint — Worker Post-Work Workflow

Run this after completing the plan's implementation, before the work is considered
done. Execute the steps in order. Only Step 2 (Codex review) is optional — Steps 1, 3
and 4 are mandatory: the job ends at a committed branch plus a `done` report.

Resolve `<path>` = the orchestrator repo path
(`C:/Users/MattiaDaCampo/Documents/orchestrator` — NOT your current project; you run
inside the target project but `orch.py` lives in the orchestrator repo). Pass your
worker letter as `--agent <AGENT>` (the letter you were invoked with as `/work <AGENT>`); the project
resolves from your linked directory — no env vars needed. (If a command reports `can't
infer the project`, run `python <path>/orch.py link <project>` once in this checkout.)

**Never degrade silently.** If you skip or downgrade any step below (Codex
unavailable, token expired, review run at a lower effort than the change deserved,
tests not run), post a warning event so the orchestrator sees it before merging
instead of discovering it in your report:

`python <path>/orch.py post --agent <AGENT> --kind warning --msg "<step> skipped: <why>"`

## Step 1 — Code Review

Run `/code-review` on all changed code at an honestly chosen effort level:
- `/code-review low` — trivial change (typo, one-line tweak, mechanical rename)
- `/code-review` (default) — normal feature work or a single-area refactor
- `/code-review high` — risky or large change: new module, cross-cutting refactor,
  migration, anything touching money or production data

If unsure between two levels, go higher. Apply any fixes it makes; if it changed code,
note what changed.

## Step 2 — Codex Review (optional)

If Codex is available, get a second opinion. **Preferred: spawn the global
`codex-reviewer` agent** (Agent tool) with your repo dir, the branch/diff to review,
and the specific question — it runs the whole Codex pass in its own context and
returns a compact cited report. Fallback (agent type unavailable): follow the
`/ask-codex` skill yourself (direct `codex exec
--dangerously-bypass-approvals-and-sandbox`; the codex plugin is disabled on this
machine), using its review template — including its REQUIRED output contract
(proof-of-read + file:line+quote citations) — on your branch's changes, e.g. "Review ONLY — do not edit
any files. Review the changes on this branch for correctness, design, and risk:
<point at the diff>." Use an "adversarial review … challenge the approach/assumptions"
framing if you want the design questioned.
1. Reason critically about the output — do not accept it at face value.
2. Apply only the fixes you clearly agree with (obviously correct, in scope, low
   risk). Do NOT stop to discuss with the user — checkpoint is autonomous.
3. Post every finding you disagree with, are unsure about, or deliberately did not
   apply as a warning event (`codex finding not applied: <file:line> <why>`), so the
   orchestrator sees it before merging.
4. Re-run `/code-review` if code was modified.

If the `codex` CLI is not installed, the token expired mid-review, or the user
says "skip codex," post the warning event from the header (`<step> skipped: <why>`)
and go to Step 3.

## Step 3 — Commit

1. `git status` and `git diff` to review all changes.
2. Draft a clear commit message in English describing the "why."
3. Commit to your working branch (HEREDOC format, Co-Authored-By line).

## Step 4 — Report Done

Report completion to the orchestrator (auto-detects the branch):

`python <path>/orch.py report --agent <AGENT> --status done --msg "ready for review"`

Do NOT update Linear — in the orchestrator system the orchestrator owns Linear updates
when it merges your branch. Your job ends at a committed branch + a `done` report.
