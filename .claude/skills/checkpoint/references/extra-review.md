# Extra fresh-eyes review — dispatch mechanics

Read this once Step 2 of `checkpoint` has decided to run an extra pass and which
reviewer to use. The decision lives in SKILL.md; this file is only how to run it.

## The contract both reviewers get

Whichever you dispatch, the brief and the constraints are the same:

- **Review only — it must not edit any files.** Say this explicitly.
- Give it the repo dir, the Step 0 range (`BASE_SHA`…`HEAD_SHA`), the reconstructed
  intent from Step 1b, what Step 1 already found and fixed, and the specific question
  you want answered.
- **Output contract:** proof it actually read the code, and `file:line` + quote
  citations for every finding. Unsupported claims get discarded.
- If the review was scoped ("only the migration"), pass that down.

## Which one

- **Codex** when you want the implementation checked against a different set of priors,
  or the design challenged adversarially.
- **Fable** when the question is design judgement, subtle logic, or "is this the right
  shape" — and whenever Codex is unavailable or you have already used it on this diff.

## Codex

**Preferred: spawn the global `codex-reviewer` agent** (Agent tool — authorized by the
standing request in SKILL.md) with the contract above. It runs the whole Codex pass in
its own context and returns a compact cited report.

**Fallback** (agent type unavailable): follow the `/ask-codex` skill yourself — direct
`codex exec --dangerously-bypass-approvals-and-sandbox`, since the codex plugin is
disabled on this machine — using its review template, including its REQUIRED output
contract, on the Step 0 range. For example:

> Review ONLY — do not edit any files. Review these changes for correctness, design,
> and risk: \<point at the diff\>

Use an "adversarial review … challenge the approach/assumptions" framing when you want
the design questioned rather than the implementation checked.

## Fable

Dispatch a subagent via the Agent tool with `model: "fable"` — authorized by the same
standing request, since it is the same fresh-eyes dispatch on a different model. Give
it the contract above.

## When Codex is unavailable

Fall back rather than giving up. CLI not installed, token expired mid-review → **run
the Fable subagent instead**, in both modes. It is one Agent call away, always
available, and delivers the same fresh-eyes value from a non-Opus model. Note the
substitution. Only if that also fails do you skip Step 2 and flag it per **Never
degrade silently**.
