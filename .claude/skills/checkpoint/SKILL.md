---
name: checkpoint
description: Post-work review workflow — quality pass, fresh-eyes code review, an optional extra Codex or Fable review, then commit. Solo it also syncs Linear; in orchestrator worker mode (`--agent <AGENT>`) it reports progress and `done` to the orch DB instead. Invoke with /checkpoint.
user-invocable: true
---

# Checkpoint — Post-Work Review Workflow

Run this when the work is written and you want it reviewed before it's considered
finished. The core is the same everywhere: **quality pass → fresh-eyes correctness
review → an optional extra review from a different model → commit.** Steps 1 and 3
always run. Step 2 is a judgement call: in solo mode it's Mattia's call, not yours;
orchestrated, it's yours, and only a trivial change may skip it.

## Which mode are you in

Look at the invocation for an explicit `--agent` flag.

- **`/checkpoint --agent <AGENT>`** → **orchestrated mode.** You are a worker in the
  multi-agent system. Everything below applies, including the orchestrated-only
  callouts and Step 5.
- **`/checkpoint` with anything else, or nothing** → **solo mode.** Mattia is in the
  conversation with you. Run Steps 0–4b, skip Step 5, and talk to him directly instead
  of posting events to a database. Solo mode has exactly one human gate — the Step 2
  review choice. Everything else, Linear included, you decide and do yourself.

**Only a literal `--agent` as the first token selects orchestrated mode.** Everything
else after `/checkpoint` is operator context (next section), never an agent letter —
including the string `--agent` if it turns up mid-sentence.

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

## Step 2 — Extra Fresh-Eyes Review

An extra pass is **not automatic**. First decide whether it's worth one, then — in
solo mode — put the decision to Mattia.

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

### 2b — Ask Mattia (solo mode only)

*(Orchestrated mode: skip this section — there is no human to ask, checkpoint is
autonomous. **Your 2a assessment decides instead.** A trivial change may skip Step 2
outright; post a note event saying so and why
(`orch.py post --agent <AGENT> --kind note --msg "step 2 skipped: trivial change"`).
Anything above trivial runs the review — Codex first, and the Fable subagent if Codex
is unavailable. Then go to 2c.)*

Present it compactly and stop for an answer:

1. **What was done** — the change in a couple of lines.
2. **What the reviews found** — `simplify`'s changes and `code-reviewer`'s findings by
   severity, with what you fixed.
3. **Your read** — your risk call, and whether you think another pass is warranted
   and why.
4. **The three options**, with your recommendation marked:
   - **(a) Codex** — the `codex-reviewer` agent. A genuinely different model; best
     when you want the implementation checked against a different set of priors, or
     the design challenged adversarially.
   - **(b) Fable** — a fresh-eyes subagent on the `fable` model (Agent tool,
     `model: "fable"`). Strong reasoning, no memory of this session. Best when the
     question is about design judgement, subtle logic, or "is this the right shape",
     and when Codex is unavailable or you've already used it.
   - **(c) Skip** — Step 1 was sufficient, ship it.

Then **wait.** Do not pick for him. If he answers with a focus ("do Fable but only on
the migration"), that scopes the review.

### 2c — Run the chosen review

**Codex.** **Preferred: spawn the global `codex-reviewer` agent** (Agent tool —
authorized in the standing request above) with
your repo dir, the diff to review, and the specific question — it runs the whole Codex
pass in its own context and returns a compact cited report. Fallback (agent type
unavailable): follow the `/ask-codex` skill yourself (direct `codex exec
--dangerously-bypass-approvals-and-sandbox`; the codex plugin is disabled on this
machine), using its review template — including its REQUIRED output contract
(proof-of-read + file:line+quote citations) — on the Step 0 range, e.g. "Review ONLY —
do not edit any files. Review these changes for correctness, design, and risk:
<point at the diff>." Use an "adversarial review … challenge the approach/assumptions"
framing if you want the design questioned.

**Fable.** Dispatch a subagent via the Agent tool with `model: "fable"` (authorized in
the standing request above — this is the same fresh-eyes dispatch, on a different
model). Give it: the repo dir, the Step 0 diff range, the reconstructed intent from
Step 1b, what Step 1 already found and fixed, and the specific question. Tell it
explicitly it is **review-only — it must not edit any files**, and require the same
output contract as Codex: proof it read the code, and `file:line` + quote citations
for every finding. Unsupported claims get discarded.

**Then, whichever you ran:**

1. Reason critically about the output — do not accept it at face value.
2. Apply only the fixes you clearly agree with (obviously correct, in scope, low
   risk).
3. Handle the findings you did **not** apply — the ones you disagree with, are unsure
   about, or deliberately left:
   - **Solo mode:** surface them to Mattia in your reply, briefly, with your reasoning.
     He is right there; a contested finding is worth thirty seconds of his attention.
   - **Orchestrated mode:** do NOT stop to discuss — checkpoint is autonomous. Post
     each one as a warning event (`review finding not applied: <file:line> <why>`) so
     the orchestrator sees it before merging.
4. If the fixes changed non-trivial logic, re-run the Step 1b review
   (`superpowers:requesting-code-review`) on the updated diff.

**Chose (c) skip, or Mattia declined, or assessed it trivial in orchestrated mode?**
That's a decision, not a degradation — no warning needed (orchestrated still posts the
note event from 2b).

**Wanted a review and couldn't get one?** Different situation — flag it per **Never
degrade silently**. But first, fall back rather than giving up: Codex unavailable (CLI
not installed, token expired mid-review) → **run the Fable subagent instead**, in both
modes. It's one Agent call away, always available, and delivers the same fresh-eyes
value from a non-Opus model. Note the substitution. Only if that also fails do you
skip Step 2 and warn.

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

*(Orchestrated mode: skip. The orchestrator owns Linear and updates it when it merges
your branch — see Step 5.)*

**Assume the work maps to a Linear issue and go find out.** Mattia works out of Linear
and almost never says the issue key out loud, so waiting to be told means it never
gets updated. This is your job, not his.

**Identify the project and issue.** In order:

1. An issue key in the invocation (`/checkpoint MAT-123`) — that's the answer.
   A key mentioned elsewhere in the conversation is a *candidate*, not an answer:
   Mattia references past issues in passing ("like we did for MAT-87"), and more than
   one key can be live in a session.
2. An issue key in the branch name or in the commits in your Step 0 range.
3. Otherwise: work out the Linear project from the repo you are in (repo name,
   `package.json`, the client folder it sits under), then use the Linear MCP —
   `list_projects` / `list_issues` — to find the in-progress issue whose description
   matches what you just built.

**Whichever rule produced the key, `get_issue` it and read it before you write.**
Matching on a title or a remembered key is how you update the wrong issue. If the
description doesn't describe the work you just did, it's the wrong issue — go back to
the list.

**Then update it, in proportion to the work.** Use the Linear MCP:

- **Comment** on the issue with what changed and the commit SHA(s) — do this whenever
  you found an issue at all.
- **Move the status** if the work actually moved it. If the issue is now genuinely
  finished, say so and close it. If it's partly done, move it to in-progress and note
  what remains.
- **Note anything the work revealed** — a follow-up, a finding you deliberately didn't
  apply, a caveat. Better in the issue than in a chat log that scrolls away.

**Write it yourself — don't ask first.** You did the work, you reviewed it, you just
committed it; you are the one who knows what the issue should now say. Update Linear
and report what you did in Step 4b. This step has no human gate.

Two limits on that autonomy:

- **Only act on a match you're actually confident in.** If the best candidate is a
  guess — several issues plausibly fit, or the description only loosely matches what
  you built — don't write. Say which issues you considered and ask. A wrong close is
  visible to everyone else in the workspace, and unlike a bad commit it isn't yours
  to quietly fix.
- **Never invent or create.** No matching issue found → say so in one line and move
  on. Don't open a new issue unless asked.

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
