---
name: ask-codex
description: Use when the human asks you to consult Codex for a code review, a second opinion, or an adversarial critique of an approach/design. Read-only review/investigation only — tells you exactly how to reach Codex via the plain CLI on this machine, and what to do with the result. Does not delegate fixes/edits (that's a separate, not-yet-built skill).
user-invocable: true
---

# Ask Codex

When the human says "ask codex", "get a codex review", "second opinion from codex",
"adversarial review", "have codex look at this", etc., this skill tells you **exactly**
how to reach Codex and what to do with the answer. Codex is a separate model (OpenAI)
reached via the plain `codex` CLI — treat it as an independent reviewer, not as ground
truth.

**The codex *plugin* is intentionally disabled on this machine** (2026-07-08) — do not
try any `/codex:*` command; they don't exist here. The plain CLI is the only path.

**Scope: review and investigation only.** This skill does not delegate fixes or edits to
Codex. If the human wants Codex to actually change files, tell them that capability
doesn't exist yet as a skill — don't improvise it by widening this skill's invocation.

## Why `--dangerously-bypass-approvals-and-sandbox`, and what it really means

Root cause (confirmed 2026-07-07/08): on this Windows/AzureAD laptop, every Codex
sandbox mode except `danger-full-access` (`read-only`, `workspace-write`) invokes the
Windows OS sandbox runner (`codex-command-runner.exe`), which fails with
`CreateProcessAsUserW failed: 5` (ERROR_ACCESS_DENIED — almost certainly corporate
EDR/restricted-token policy). There is no working sandboxed path on this machine, so
`codex exec --dangerously-bypass-approvals-and-sandbox` is the **only** reliable way to
get Codex to actually read files here.

Consequences:
1. **"Read-only" is enforced by prompt instruction, not by the sandbox.** The flag is
   mechanically write-capable; "Review ONLY — do not edit any files" is a request to
   Codex, not a technical boundary. Say this plainly to the human if asked.
2. **Silent read failures produce plausible guesses.** When a sandboxed read fails,
   Codex has been observed inventing an answer from the file *path* instead of its
   contents. That's why the output contract below requires proof-of-read: verify the
   reported line counts and quotes against the real files (`wc -l`, `tail`), and grep
   raw output for `CreateProcessAsUserW`. Proof missing or wrong → discard and re-run.
3. **Staleness guard:** this is an environmental diagnosis; a future Codex release or
   IT policy change could fix it. If it's been a while since the date above,
   occasionally re-test `codex exec -s read-only` with a trivial read prompt; if it
   works, tell the human this skill can be re-based on a real read-only sandbox.

## How to run a review / investigation / adversarial critique

Run in Claude's Bash tool (Git Bash) — the template will not work pasted into
PowerShell (heredocs and `<` redirection are POSIX constructs).

### Two rules that make or break this (read before writing the command)

1. **One single Bash call. Write the prompt AND launch Codex in the same call.**
   The Bash tool does not persist shell state between calls: files survive, variables
   do not. Splitting "write the prompt" and "run codex" into two calls leaves `$P`
   empty in the second one and the run dies on `- < ""`. This is *the* recurring
   failure mode of this skill — if you catch yourself planning a separate "write the
   prompt to a file" step, stop and merge it back in.
2. **Never `mktemp`. Use fixed, self-chosen paths under the session scratchpad.**
   You need to read `$OUT` from a *later* call, and `mktemp`'s name dies with the call
   that made it. Pick a short slug per review (`otp-dialog`, `mat1222`) so concurrent
   reviews in one session don't collide.

```bash
S="<paste the scratchpad path from your system prompt>"   # no env var holds it
SLUG=<short-slug-for-this-review>
P="$S/codex-$SLUG.prompt.md"
OUT="$S/codex-$SLUG.out.md"

cat > "$P" <<'EOF'
Review ONLY — do not edit any files.
<goal, exact repo + paths, what to look at, the specific question>

Output contract (REQUIRED — the reader of your output is another agent that
must locate every finding without re-deriving it):
1. PROOF OF READ — before any findings, report for each file you reviewed:
   its exact path and total line count, plus a verbatim quote of its last
   non-empty line. If you could not read a file, say so explicitly instead
   of guessing.
2. Every finding MUST cite: exact file path, line number(s), and a short
   verbatim quote of the offending code/text.
3. A finding without a file+line+quote citation is invalid — omit it or mark
   it explicitly as UNVERIFIED SPECULATION.
EOF
codex exec -C "<repo dir>" -m gpt-5.6-sol -c model_reasoning_effort="<medium|high>" \
  --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check \
  -o "$OUT" - < "$P"
```

Pick `<medium|high>` per the **review presets** below. Keep `-m`/`-c` *before*
`--dangerously-bypass-approvals-and-sandbox` so the literal flag stays intact and the
permission allowlist still matches.

- The output contract block is **not optional boilerplate** — include it verbatim in
  every review prompt. Proof-of-read detects the silent-read-failure mode; per-finding
  citations let the orchestrator or a downstream agent jump straight to each issue.
- Always include the literal instruction **"do not edit any files"** — it's the only
  thing keeping the call read-only in practice.
- Prompt via file + stdin (`< "$P"`), never inline — avoids quoting hell. Write it with
  the heredoc *inside this same Bash call*, not with the Write tool in a previous step.
- `-o "$OUT"` captures the rendered result; read that file with the Read tool afterwards.
  The `$SLUG` is what keeps two reviews in one session from overwriting each other.
- `--skip-git-repo-check` is needed outside a git repo; harmless inside one.
- **Backgrounding:** if you background this, background *the whole call above* — prompt
  write plus `codex exec` together. Never background a bare "write the prompt" step: it
  buys nothing, and when it fails you lose the error. Once it completes, read `$OUT` by
  its literal path (you cannot re-expand `$OUT` in a later call). Don't kill a quiet run
  early.
- Follow-up on the same thread (cheaper, keeps context) — same one-call rule, new slug:
  ```bash
  S="<scratchpad path>"; SLUG=<slug>-followup
  P2="$S/codex-$SLUG.prompt.md"; OUT2="$S/codex-$SLUG.out.md"
  cat > "$P2" <<'EOF'
  <follow-up question>
  EOF
  (cd "<repo dir>" && codex exec resume --last --dangerously-bypass-approvals-and-sandbox \
    -o "$OUT2" - < "$P2")
  ```

**Permissions:** a `~/.claude/settings.json` `permissions.allow` entry
(`Bash(codex exec * --dangerously-bypass-approvals-and-sandbox*)`) pre-authorizes this
command shape, and a matching natural-language rule in `autoMode.allow` (added
2026-07-08, verified working) covers auto-mode/background sessions — so do NOT
preemptively stop and hand the command to the human just because you're in auto mode.
Attempt the call first; escalate only on an *actual* runtime denial. These rules match
the shell command, not prompt content — they don't themselves distinguish a review
invocation from a write-capable one, which is fine only as long as this skill emits
review-only prompts. A future edit-delegating skill must re-review whether the
allowlist should cover it.

### When the run fails, check these first

| Symptom | Cause | Fix |
|---|---|---|
| Bash call fails on the *prompt-writing* step, no Codex output | you split the flow into two calls and/or backgrounded the write | merge into one call per rule 1 above |
| `codex exec` exits immediately, empty/absent `$OUT` | `$P` or `$OUT` was set in an earlier call and is now empty | fixed scratchpad paths per rule 2; never `mktemp` |
| `$OUT` unreadable later because you don't know its name | `mktemp` name lost with the call | fixed `codex-$SLUG.out.md` path |
| `CreateProcessAsUserW failed: 5` in the output | a sandbox mode slipped in | keep `--dangerously-bypass-approvals-and-sandbox` (see above) |

Don't re-diagnose these from scratch each session — they're the same four every time.

## Review presets: model + reasoning effort

Two knobs, both verified on this machine (2026-07-10):

- **Model** — `-m <slug>`. Your ChatGPT account is entitled to the GPT-5.6 family
  (`gpt-5.6-sol` flagship, `gpt-5.6-terra` mid, `gpt-5.6-luna` cheap/fast) plus the older
  `gpt-5.5`. A slug the account can't use fails fast with a 400 ("… not supported when
  using Codex with a ChatGPT account") — so a typo can't silently downgrade you.
- **Reasoning effort** — `-c model_reasoning_effort="<value>"`, one of
  `none | minimal | low | medium | high | xhigh` (CLI ceiling is `xhigh`; the `Max`/`Ultra`
  levels in OpenAI's docs are interactive-picker only and don't apply to `codex exec`). A
  bad value fails fast with a 400 listing the enum. Higher effort visibly costs more tokens.

**For reviews, always use `gpt-5.6-sol`** — it's the flagship built for advanced coding and
security work, i.e. exactly adversarial review. (Terra/Luna are entitlement facts, not
review options: sol at `medium` is more token-efficient and reviews better.)

| Preset | `model_reasoning_effort` | Use when |
|--------|--------------------------|----------|
| **Standard** | `medium` | Almost every review — this is the correct choice ~all the time. Routine *and* large diffs, security passes, refactors, checkpoint reviews, "sanity-check this". When in doubt, medium. |
| **Deep** | `high` | Extremely hard cases only: (a) the human explicitly asked for a deep/hard adversarial pass, or (b) the target is a suspected subtle bug — races, corrupted state, unreproducible failures — where a medium pass or your own analysis already came up empty. |

**`high` visibly costs several× the time and tokens of `medium`** — that cost must be
justified before you pick it. "Security-sensitive" or "big diff" alone does NOT justify
Deep; those are Standard. Deep is an escalation, not a classification. State which preset
you used when you report findings, so the human knows how hard Codex looked.

## Use the answer critically

Codex's output comes back **verbatim**. Once you have it:
1. **Reason about it — don't accept it at face value.** It can be wrong, outdated, or
   miss project context; and check the proof-of-read per above.
2. State your own view: where you **agree/disagree and why**.
3. Surface the findings to the human and apply only the changes you both agree on —
   *you* (Claude) make those edits as normal work; never send them back to Codex to
   apply. If you changed code as a result, re-run your normal code review.

## If Codex isn't available

1. Install: `npm install -g @openai/codex`
2. Authenticate: `codex login` is interactive — ask the human to run it themselves
   (suggest `! codex login` in their prompt).

Do not silently skip a requested Codex pass — tell the human it's unavailable and why.

## Note for orchestrator worker agents

`/checkpoint` Step 2 calls for an optional Codex review, running in the **autonomous**
phase (no human typing) — use the template above on your branch's changes. Reason about
the output, then continue. If you skip Codex (unavailable, expired, user said skip),
post the checkpoint warning event so the orchestrator knows before merging.
