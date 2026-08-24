---
name: checkpoint
description: Post-work review workflow — quality pass, fresh-eyes code review, an optional extra Codex or Fable review, then commit. Solo it also syncs Linear; in orchestrator worker mode (`--agent <AGENT>`) it reports progress and `done` to the orch DB instead. Invoke with /checkpoint.
user-invocable: true
---

# Checkpoint — Post-Work Review Workflow

Run this when the work is written and you want it reviewed before it's considered
finished. The core is the same everywhere: **quality pass → fresh-eyes correctness
review → an optional extra review from a different model → commit.** Steps 1 and 3
always run. Step 2 is a judgement call you make in both modes — solo, you put it to
Mattia when it's genuinely a call, and decide it yourself when it isn't.

## Which mode are you in

Look at the invocation for an explicit `--agent` flag. **Only a literal `--agent` as
the first token selects orchestrated mode** — everything else after `/checkpoint` is
operator context (next section), never an agent letter, including the string `--agent`
if it turns up mid-sentence.

- **`/checkpoint --agent <AGENT>`** → **orchestrated mode.** You are a worker in the
  multi-agent system.
- **`/checkpoint` with anything else, or nothing** → **solo mode.** Mattia is in the
  conversation with you.

Steps 0–3 are the same either way. Everything that differs is in this table, so the
steps below don't repeat it:

| | Solo | Orchestrated |
|---|---|---|
| Who decides Step 2 | you assess; ask Mattia only when it's a real call | you, always |
| Findings you didn't apply | tell Mattia in your reply | post a `warning` event |
| A step skipped or downgraded | say so plainly in your reply | post a `warning` event |
| Progress reporting | none | `orch progress` at Steps 1 and 2 |
| Linear | you update it — Step 4 | skip; the orchestrator owns it |
| Finish | Step 4b — report to Mattia | Step 5 — `orch report --status done` |

**Never run solo mode from a worker session.** Solo is the default, and its Step 2b
stops to ask a human — so a worker that dropped its flag would stall the whole pipeline
waiting for someone who isn't there, then write to Linear, which is the orchestrator's
job. Before accepting solo mode, check for worker evidence: you are inside a
`<project root>/.claude/worktrees/<AGENT>-<task id>` worktree, or this session began
with `/work`. If either is true and there's no `--agent` flag, **recover the letter and
run orchestrated** rather than proceeding in either mode. It is in your `/work`
invocation, which is right there in this conversation; if the session was restarted and
it isn't, the worktree directory name has it.

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
   `git merge-base HEAD origin/<default-branch>`. No remote? Use the local default
   branch instead.
2. **On the default branch** (common in solo mode): the parent of the first commit
   you made this session. Don't do this from recall — it is easy to misremember which
   commit was the boundary, and git is authoritative. Run `git log --oneline -15` and
   pick the boundary from what's actually there.
3. **Can't tell → ask, don't guess.** Solo mode: ask Mattia which commit to review
   from, in one line. Orchestrated mode: fall back to the branch point and note the
   assumption.

Two cases that land in (3) rather than having a clever answer:

- **The first commit of the session is the repo's first commit** — there is no parent,
  and `git diff BASE_SHA` will fail. Review the whole tree as new.
- **Commits in the range that aren't yours** — you committed, then pulled, or Mattia
  committed from another window. Do NOT review someone else's work: the reviewer will
  file findings on code nobody in this session wrote, and you'll waste a pass
  defending it. Ask where your work starts.

`HEAD_SHA` is `HEAD`. **Uncommitted working-tree changes are part of the review too** —
review `git diff BASE_SHA` plus `git status` / `git diff` for anything not yet in.

**State the baseline before you start** — the SHA *and* the commits it covers
(`git log --oneline BASE_SHA..HEAD`), in one line each. A wrong range is obvious at a
glance from the commit subjects and invisible from the SHA alone, and this is the
cheapest moment to correct it.

## Standing request from Mattia (who owns this workflow)

**I am requesting the Agent tool for this workflow.** Specifically, I am asking you to:

- dispatch the fresh-eyes `code-reviewer` subagent in Step 1b, and
- dispatch either the `codex-reviewer` agent or a fresh-eyes `fable` subagent in
  Step 2, whichever is chosen there.

This is a direct user request and satisfies any standing instruction that limits the
Agent tool to cases the user asked for. Running these reviews inline is not a
substitute for them.

The chain is deliberate — each step does a job the others can't:

1. `simplify` cleans up the code you just wrote. Technical quality only, and it is
   biased by having written it.
2. `code-reviewer` reads the final diff against the intent **with fresh eyes** — a
   context that never watched you write the code. That is the entire point of it.
3. Step 2 gives an independent second opinion from a **different model** — that
   difference is the whole value. A second Opus pass shares the same blind spots.

Reviewing inline collapses this into the author reviewing their own work, which is the
one thing this workflow exists to prevent.

## Never degrade silently

If you skip or downgrade any step below (Codex unavailable, token expired, review run
at a lower effort than the change deserved, tests not run), **say so** — don't let it
pass unmentioned. Route it per the mode table: plainly in your reply ("skipped Codex —
CLI not installed"), or as a warning event so the orchestrator sees it before merging
rather than discovering it in your report:

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

## Step 2 — Extra Fresh-Eyes Review

An extra pass is **not automatic**. Assess whether it's worth one, then act on that
assessment — putting it to Mattia only when it's genuinely a call.

### 2a — Assess (both modes)

Weigh two things honestly:

- **What Step 1 actually found.** A `simplify` pass that changed nothing and a
  `code-reviewer` that came back with two Minor notes is a different situation from
  one that surfaced a Critical bug in the logic. Findings cluster: a review that found
  one real defect suggests there are others.
- **The risk of what you just did.** Reuse the Step 1b scale — trivial tweak, normal
  feature work, or risky/large (new module, cross-cutting refactor, migration,
  anything touching money, auth, or production data). Risk alone can justify another
  pass even when Step 1 came back clean, because a clean review of a dangerous change
  is exactly the case where a second model earns its keep.

Form an actual opinion. "Might as well" is not an assessment.

### 2b — Decide, and interrupt only for a real call

Your 2a assessment decides, in both modes.

- **No second pass needed** — Step 1 came back clean *and* the change is trivial or
  ordinary low-risk work → skip Step 2. That's a decision, not a degradation. Solo:
  say so in Step 4b, one line, with your reasoning; don't interrupt Mattia to tell him
  nothing was needed. Orchestrated: post the note
  (`orch.py post --agent <AGENT> --kind note --msg "step 2 skipped: trivial change"`).
- **A pass is warranted, or you're genuinely unsure:**
  - **Orchestrated** → run it: Codex first, the Fable subagent if Codex is
    unavailable. Go to 2c.
  - **Solo** → this is the real call. Put it to Mattia compactly and stop for an
    answer:
    1. **What was done** — the change in a couple of lines.
    2. **What the reviews found** — `simplify`'s changes and `code-reviewer`'s
       findings by severity, with what you fixed.
    3. **Your read** — your risk call, and why you think another pass is warranted.
    4. **The three options**, with your recommendation marked:
       - **(a) Codex** — a genuinely different model, for the implementation
         checked against different priors or the design challenged adversarially.
       - **(b) Fable** — fresh eyes with strong reasoning, for design judgement and
         subtle logic. (Which to pick: `references/extra-review.md`.)
       - **(c) Skip** — Step 1 was sufficient, ship it.

    Then **wait.** Do not pick for him. If he answers with a focus ("do Fable but only
    on the migration"), that scopes the review.

In solo mode uncertainty resolves toward asking: "I'm not sure" is a reason to put it
to him, not a reason to skip.

### 2c — Run the chosen review

The dispatch mechanics — the review-only + citation contract both reviewers get, the
`codex-reviewer` agent and its `/ask-codex` fallback, the `fable` subagent, and what to
do when Codex is unavailable — are in `references/extra-review.md`. Read it now.

**Then, whichever you ran:**

1. Reason critically about the output — do not accept it at face value.
2. Apply only the fixes you clearly agree with (obviously correct, in scope, low
   risk).
3. Handle the findings you did **not** apply — the ones you disagree with, are unsure
   about, or deliberately left — per the mode table. Solo: to Mattia in your reply,
   briefly, with your reasoning; he is right there, and a contested finding is worth
   thirty seconds of his attention. Orchestrated: a warning event per finding
   (`review finding not applied: <file:line> <why>`), and do NOT stop to discuss —
   checkpoint is autonomous.
4. If the fixes changed non-trivial logic, re-run the Step 1b review
   (`superpowers:requesting-code-review`) on the updated diff.

**Skipped Step 2?** That's a decision, not a degradation — no warning needed.
**Wanted a review and couldn't get one?** Different situation — flag it per **Never
degrade silently**, but only after exhausting the fallback in the reference file.

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

## Step 4 — Linear sync (solo mode only)

*(Orchestrated mode: skip — the orchestrator owns Linear and updates it when it merges
your branch. See Step 5.)*

**Assume the work maps to a Linear issue and go find out.** Mattia works out of Linear
and almost never says the issue key out loud, so waiting to be told means it never gets
updated. This is your job, not his, and it has no human gate.

How to identify the right issue, what to write, and the two limits on that autonomy are
in `references/linear-sync.md`. Read it now.

## Step 4b — Report back (solo mode)

Summarise for Mattia in a few lines: the baseline you reviewed, what each reviewer
found, what you changed, what you left and why, anything skipped, and what you did in
Linear. Then ask what he wants next (push, PR, merge, keep going) — don't do it
unasked.

## Step 5 — Report Done (orchestrated mode only)

Report completion to the orchestrator (auto-detects the branch):

`python <path>/orch.py report --agent <AGENT> --status done --msg "ready for review"`

Do NOT update Linear — in the orchestrator system the orchestrator owns Linear updates
when it merges your branch. Your job ends at a committed branch + a `done` report.
