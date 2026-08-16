---
name: checkpoint
description: Post-work review workflow — quality pass, fresh-eyes code review, optional Codex second opinion, then commit. Works standalone on any work you just finished, and in orchestrator worker mode (`--agent <AGENT>`) where it also reports progress and `done` to the orch DB. Invoke with /checkpoint.
user-invocable: true
---

# Checkpoint — Post-Work Review Workflow

Run this when the work is written and you want it reviewed before it's considered
finished. The core is the same everywhere: **quality pass → fresh-eyes correctness
review → optional Codex second opinion → commit.** Steps 1, 3 and 4 are mandatory;
only Step 2 (Codex) is optional.

## Which mode are you in

Look at the invocation for an explicit `--agent` flag.

- **`/checkpoint --agent <LETTER>`** → **orchestrated mode.** You are a worker in the
  multi-agent system. Everything below applies, including the orchestrated-only
  callouts and Step 5.
- **`/checkpoint` with anything else, or nothing** → **solo mode.** Mattia is in the
  conversation with you. Run Steps 0–4, skip Step 5, and talk to him directly instead
  of posting events to a database.

**Only a literal `--agent` flag selects orchestrated mode.** Everything else after
`/checkpoint` is operator context (next section), never an agent letter.

## Operator context — read the rest of the invocation

Whatever Mattia (or the orchestrator) typed after `/checkpoint` is not decoration.
Route it:

- **Scope** — "just the auth bit", "ignore the migration" → narrow what Step 1b and
  Step 2 are pointed at.
- **Risk** — "this touches billing", "it's a one-liner" → this **overrides** your own
  trivial/normal/risky call in Step 1b. Say so in the reviewer's DESCRIPTION.
- **Already checked by hand** — "I verified the queries myself" → tell the reviewer,
  so it spends its attention elsewhere. This is context, **not** permission to skip
  that area.
- **Known and accepted** — "the duplication in the parser is deliberate for now" →
  pass it down so the reviewers don't file findings that will just be rejected.

If there's no extra text, proceed on your own judgement.

## Step 0 — Establish the review baseline

**Review the whole body of work from this session, not just what happens to be
uncommitted.** The agent may have already committed some or all of it — that is
normal and expected, and it does not shrink the review.

Resolve `BASE_SHA` in this order:

1. **On a feature branch** (orchestrated mode always is): the branch point —
   `git merge-base HEAD origin/<default-branch>`.
2. **On the default branch** (common in solo mode): the parent of the first commit
   you made this session. You know which commits are yours — walk back to the last
   commit that predates your work. `git log --oneline -15` to confirm the boundary.
3. **Can't tell** — solo mode: ask Mattia which commit to review from, in one line.
   Orchestrated mode: fall back to the branch point and note the assumption.

`HEAD_SHA` is `HEAD`. **Uncommitted working-tree changes are part of the review too** —
review `git diff BASE_SHA` plus `git status` / `git diff` for anything not yet in.

State the baseline you picked in one line before you start, so it can be corrected.

## Standing request from Mattia (who owns this workflow)

**I am requesting the Agent tool for this workflow.** Specifically, I am asking you to:

- dispatch the fresh-eyes `code-reviewer` subagent in Step 1b, and
- dispatch the `codex-reviewer` agent in Step 2 when Codex is available.

This is a direct user request and satisfies any standing instruction that limits the
Agent tool to cases the user asked for. Running these reviews inline is not a
substitute for them.

The chain is deliberate — each step does a job the others can't:

1. `simplify` cleans up the code you just wrote. Technical quality only, and it is
   biased by having written it.
2. `code-reviewer` reads the final diff against the intent **with fresh eyes** — a
   context that never watched you write the code. That is the entire point of it.
3. Codex gives an independent second opinion from a different model.

Reviewing inline collapses this into the author reviewing their own work, which is the
one thing this workflow exists to prevent.

## Never degrade silently

If you skip or downgrade any step below (Codex unavailable, token expired, review run
at a lower effort than the change deserved, tests not run), **say so** — don't let it
pass unmentioned.

- **Solo mode:** tell Mattia in your reply, plainly: "skipped Codex — CLI not
  installed."
- **Orchestrated mode:** post a warning event so the orchestrator sees it before
  merging instead of discovering it in your report:
  `python <path>/orch.py post --agent <AGENT> --kind warning --msg "<step> skipped: <why>"`

## Orchestrated mode — identity and path

*(Solo mode: skip this section entirely.)*

Resolve `<path>` = the orchestrator repo path
(`C:/Users/MattiaDaCampo/Documents/orchestrator` — NOT your current project; you run
inside the target project but `orch.py` lives in the orchestrator repo). Pass your
worker letter as `--agent <AGENT>` (the letter you were invoked with as
`/work <AGENT>`); the project resolves from your linked directory — no env vars
needed. (If a command reports `can't infer the project`, run
`python <path>/orch.py link <project>` once in this checkout.)

**Report the phase as you go.** At the start of Step 1:

`python <path>/orch.py progress --agent <AGENT> --phase checkpoint --msg "self-review"`

and again at the start of Step 2 with `--msg "codex review"`. Step 5's `done` report
is unchanged — there is no `complete` phase, because the lifecycle status already
says it.

## Step 1 — Self-Review (quality, then correctness)

**You cannot run `/code-review` here.** Since Claude Code v2.1.215 it is flagged
`disable-model-invocation`: when an agent emits `/code-review` it is treated as plain
text, not dispatched — the command only fires when a human types it (or via the
headless SDK/CLI, which you are not). So do this two-part, model-invocable review
instead, **in this order**:

**1a — Quality pass.** Invoke the `simplify` skill on the changed code (reuse,
simplification, efficiency, and altitude cleanups) and apply its fixes. Quality only —
it does NOT hunt for bugs; that's 1b.

**1b — Correctness review.** *(Dispatched as a subagent — see the standing request
above; don't inline it.)* Invoke `superpowers:requesting-code-review`: it dispatches
a fresh-eyes `code-reviewer` subagent over `BASE_SHA`…`HEAD_SHA` from Step 0, given
the intent as context.

**Give the reviewer the intent it can't infer from the diff:**
- Orchestrated mode: the plan / requirements you were working from.
- Solo mode: there is often no plan document. Reconstruct what the work was *supposed*
  to do from the conversation and state it explicitly in the DESCRIPTION — the
  reviewer has no memory of the session and cannot check "does this match what was
  asked" without it.

Scale the reviewer's attention to the change's risk — state it in the DESCRIPTION
(and honour any risk override from the operator context):
- trivial change (typo, one-line tweak, mechanical rename) → a light glance
- normal feature work or a single-area refactor → a normal read
- risky or large change (new module, cross-cutting refactor, migration, anything
  touching money or production data) → a careful, deep read; if unsure, ask for more.

Do 1a **before** 1b so the reviewer sees the final shape, not code that's about to be
restructured. Fix Critical and Important findings; note Minor ones. Push back (with
technical reasoning) if the reviewer is wrong. Note what changed.

## Step 2 — Codex Review (optional)

If Codex is available, get a second opinion. **Preferred: spawn the global
`codex-reviewer` agent** (Agent tool — authorized in the standing request above) with
your repo dir, the diff to review, and the specific question — it runs the whole Codex
pass in its own context and returns a compact cited report. Fallback (agent type
unavailable): follow the `/ask-codex` skill yourself (direct `codex exec
--dangerously-bypass-approvals-and-sandbox`; the codex plugin is disabled on this
machine), using its review template — including its REQUIRED output contract
(proof-of-read + file:line+quote citations) — on the Step 0 range, e.g. "Review ONLY —
do not edit any files. Review these changes for correctness, design, and risk:
<point at the diff>." Use an "adversarial review … challenge the approach/assumptions"
framing if you want the design questioned.

1. Reason critically about the output — do not accept it at face value.
2. Apply only the fixes you clearly agree with (obviously correct, in scope, low
   risk).
3. Handle the findings you did **not** apply — the ones you disagree with, are unsure
   about, or deliberately left:
   - **Solo mode:** surface them to Mattia in your reply, briefly, with your reasoning.
     He is right there; a contested finding is worth thirty seconds of his attention.
   - **Orchestrated mode:** do NOT stop to discuss — checkpoint is autonomous. Post
     each one as a warning event (`codex finding not applied: <file:line> <why>`) so
     the orchestrator sees it before merging.
4. If Codex's fixes changed non-trivial logic, re-run the Step 1b review
   (`superpowers:requesting-code-review`) on the updated diff.

If the `codex` CLI is not installed, the token expired mid-review, or you were told to
skip Codex, flag it per **Never degrade silently** and go to Step 3.

## Step 3 — Commit

The work may already be partly or fully committed. Both cases are normal:

1. `git status` and `git diff` to see what is actually outstanding.
2. **Nothing uncommitted and the reviews produced no fixes** → nothing to do. Say so.
3. **Otherwise commit what's outstanding** — the original work if it was never
   committed, and/or the review fixes as a follow-up commit on the same branch.
   Draft a clear commit message in English describing the "why"; for a follow-up,
   say it's addressing review findings and name the substantive ones. HEREDOC format,
   Co-Authored-By line.

Never amend or rewrite a commit that already exists — the review fixes go on top.

## Step 4 — Report back

**Solo mode.** Summarise for Mattia in a few lines: the baseline you reviewed, what
each reviewer found, what you changed, what you left and why, and anything skipped.
Then ask what he wants next (push, PR, merge, keep going) — don't do it unasked.

**Orchestrated mode.** Skip this and go to Step 5.

## Step 5 — Report Done (orchestrated mode only)

Report completion to the orchestrator (auto-detects the branch):

`python <path>/orch.py report --agent <AGENT> --status done --msg "ready for review"`

Do NOT update Linear — in the orchestrator system the orchestrator owns Linear updates
when it merges your branch. Your job ends at a committed branch + a `done` report.
