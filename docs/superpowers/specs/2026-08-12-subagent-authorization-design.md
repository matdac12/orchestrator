# Standing Subagent Authorization in Skills

## Status

Approved — apply directly. This is a prose change to two skill files; no code, no
tests, no plan document.

## Problem

Worker agents refuse to dispatch subagents, reporting some variation of:

> La revisione di correttezza dello Step 1b l'ho fatta in linea invece che con un
> subagent a occhi freschi — la tua istruzione permanente vieta il tool Agent.

They are not malfunctioning. Claude Code injects a dynamic system-prompt section,
internally named `heron_brook`, containing:

```text
Do not call the AgentTool unless the user requested it
Do not use workflows or deep-research unless the user requested it
```

Established facts, from [claude-code#80988](https://github.com/anthropics/claude-code/issues/80988):

- Introduced in Claude Code **2.1.219**; not present in 2.1.217/2.1.218.
- Gated to **Opus 5 only**, via the `opus_5_prompt_bundle` capability. Fable 5 and
  other models do not receive it.
- **No opt-out**: no `settings.json` key, no CLI flag, no `CLAUDE_CODE_*` variable.
  The GrowthBook killswitch (`tengu_fennel_godwit`) also disables five unrelated
  prompt sections, so it is not a usable lever.
- Open since 24 July 2026 with no Anthropic response. Still active in 2.1.228.

It is not stored anywhere on this machine. A full search of `~/.claude/CLAUDE.md`,
`~/.claude/settings.json`, `settings.local.json`, `~/.claude.json`, project settings,
output styles, and `C:/ProgramData/ClaudeCode/managed-settings.json` found nothing —
the text arrives with the session.

The failure mode is specific and severe for this repo: `/checkpoint` Step 1b exists to
get a **fresh-eyes** review of the diff. An agent that reviews inline is the author
reviewing their own work, which is the one thing that step exists to prevent — and it
reports success either way.

## Key insight

The injected instruction is not a ban. It is `unless the user requested it` — an
escape clause.

What fails is a **skill** saying "spawn a subagent": the model reads that as the
skill's initiative, not the user's request. What works is the request coming from the
**user**. Community guidance converges on the same lever: naming the specific subagent
in an explicit user request is the reliable trigger.

So the fix is not to argue with the instruction. It is to put the user's standing
request where the agent reads it.

## Design

A short authorization block near the top of each skill that dispatches subagents,
written in the human's voice, naming the specific agents, and explaining why the
delegation is load-bearing. Plus a one-line pointer at each dispatch site.

Three properties do the work:

1. **The human's voice, as a request.** "I am requesting the Agent tool" satisfies the
   escape clause. "This skill uses subagents" does not.
2. **Named agents.** `code-reviewer`, `codex-reviewer`, and the mission delegates are
   named explicitly rather than referred to as "a subagent".
3. **Stated rationale.** An agent weighing "is inline good enough here?" gets the
   answer instead of guessing.

**Placement is before the steps, not at the dispatch site.** The agent must read it
while forming its plan, not once it is already mid-Step-1 and committed to an approach.

### `/checkpoint`

Inserted after the "never degrade silently" block:

```markdown
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
2. `code-reviewer` reads the final diff against the plan **with fresh eyes** — a
   context that never watched you write the code. That is the entire point of it.
3. Codex gives an independent second opinion from a different model.

Reviewing inline collapses this into the author reviewing their own work, which is the
one thing this workflow exists to prevent.
```

Plus, at Steps 1b and 2: `(dispatched as a subagent — see the standing request above;
don't inline it)`.

### `/esegui-test`

The same shape, naming its own dispatch: the planner requests one delegate subagent per
mission and must not run missions itself, because the delegate's clean context is what
makes the evidence trustworthy. A planner that both writes and runs its missions has
already seen what it is looking for.

## Decisions taken

- **No fallback and no warning event.** Considered making an inline review post
  `kind=warning` so the orchestrator sees the downgrade before merging. Rejected: the
  authorization text is the fix, and the extra machinery would mostly document a
  failure we expect not to happen.
- **No shared reference file.** Considered writing the block once and pointing both
  skills at it. Rejected: indirection weakens exactly the property that makes it work —
  it should be read verbatim, in the human's voice, in place.
- **Both skills, not just `/checkpoint`.** `/esegui-test` has the same exposure and
  fails harder: no delegates means the planner runs its own missions, losing the
  isolation the design depends on.

## Out of scope

- Changing the account or machine configuration. There is nothing to change; the
  instruction is server-side.
- Any attempt to suppress `heron_brook` (killswitch, `CLAUDE_INTERNAL_FC_OVERRIDES`).
  Undocumented internal levers with unrelated side effects are not a maintainable fix.
- Other skills. Only `/checkpoint` and `/esegui-test` dispatch subagents today.

## Acceptance

1. A worker running `/checkpoint` under Opus 5 dispatches `code-reviewer` for Step 1b
   rather than reviewing inline.
2. `/esegui-test` spawns one delegate per mission rather than running them in the
   planner's context.
3. Both skills state why the delegation matters, so the rationale survives a future
   reader who does not know about `heron_brook`.

## Revisit when

Anthropic ships an opt-out or removes the section. At that point this text becomes
harmless but redundant — the rationale paragraphs are worth keeping regardless, since
they document why the review chain has the shape it has.
