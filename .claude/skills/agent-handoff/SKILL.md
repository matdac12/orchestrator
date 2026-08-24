---
name: agent-handoff
description: Hand off work to another agent — in Herdr by spawning it in a new tab in this workspace, on this checkout or on its own worktree, otherwise as a named background `claude` session — or as a markdown handoff document in the repo (context summary, or a task brief for a fresh agent) plus a short prompt to paste anywhere. Standalone — no orchestrator/project knowledge required.
disable-model-invocation: true
user-invocable: true
argument-hint: "What will the next session focus on?"
---

# Agent Handoff

Hand the current work to another agent. Two mutually exclusive delivery paths —
spawn the agent now, or write a handoff document — and the spawn path has a Herdr
flavour and a plain-terminal flavour.

## Step 0 — Detect the environment, then ask which path

Run `test "${HERDR_ENV:-}" = 1 && echo herdr` once. If it prints `herdr`, you're inside
a Herdr-managed pane and can spawn a real, visible, promptable agent — use the **Herdr
question** below. Otherwise use the **classic question**.

**If arguments were passed**, treat them as a description of what the next
session will focus on. Use them to pick the document kind yourself instead of
asking (a description of work to *do* → task brief; a description of work to
*continue* → context summary), and tailor the whole document to that focus —
drop sections of the conversation that don't serve it. Still ask which *path*
(spawn an agent vs. write a document) unless that's obvious from the arguments too.

Always ask first, unless the invoker already said which one.

**Ask every one of these with the `AskUserQuestion` tool, not in prose.**

### Classic question (not in Herdr)

Question — *"How do you want to hand this off?"*, header `Handoff`:

- **Background agent** — spawn a named `claude --bg` session right now (terminal workflow).
- **Prompt to paste** — write a markdown file in the repo and give you a short prompt to paste into a fresh chat (desktop-app workflow).

Background agent → Path 1. Prompt to paste → Path 2.

### Herdr question

**Being inside Herdr is not a reason to assume he wants an agent spawned.** He may
well want the prompt to paste somewhere else entirely, and guessing wrong leaves a
live pane he has to go clean up. Ask, every time.

Question — *"How do you want to hand this off?"*, header `Handoff`:

- **New tab here** — I open a tab in this workspace, start an agent in it, and send it the prompt.
- **Prompt to paste** — I write the handoff document and give you a short prompt to paste wherever you like.

If he picks the tab, ask the second one immediately — *"Should it have its own
branch?"*, header `Isolation`:

- **Its own worktree** — new branch and checkout, isolated from what you're doing here.
- **This checkout** — same working directory. For work that needs no isolation.

Tab → Path 1H, with the isolation he chose. Prompt to paste → Path 2.

### Document kind

If he chose the document, ask this immediately — *"What kind of document?"*, header
`Doc kind`:

- **Context summary** — where we are, what's done, what's next, so a fresh chat can pick up.
- **Task brief** — instructions for another agent: what to read, what to do, what "done" looks like.

Then follow the matching section below. Never write the document *and* spawn an
agent.

---

## Path 1H — Herdr agent (in Herdr only)

Takes the same two things as Path 1 — a **name** and a **prompt** — plus the isolation
chosen in Step 0. Nothing else: no notion of orchestrators, tasks or tickets.

The agent name must match `[a-z][a-z0-9_-]{0,31}` and be unique among live agents.
Derive a short descriptive one from the work (`auth-refactor`, `flaky-tests`) and check
`herdr agent list` for a collision first — if it's taken, pick another rather than
spawning a duplicate.

**Always a tab in the workspace you are already in — never a workspace of its own.**
Herdr's agent sidebar sorts by workspace and has no notion of worktree parentage, so
an agent given its own workspace becomes a detached row with nothing tying it to the
project it belongs to. A tab keeps it grouped with everything else here.

**Labels.** In Mattia's sidebar the **tab label is the identity line at the top** and
the **workspace label is the place line at the bottom**. You set the tab label only:
a short human-readable name for the work — Title Case, a few words, not the kebab
agent name (`Auth refactor`, not `auth-refactor`), and under ~26 characters or the
sidebar clips it. **Never set or rename a workspace label** — it is the line that
tells him which project this row is in, and it is shared by everything in that
workspace.

### This checkout

```
herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd "$(git rev-parse --show-toplevel)" --label "<Work name>" --no-focus
```

### Its own worktree

Ask for the branch name if it isn't obvious from the work; base it on the current
branch unless told otherwise. Make the worktree with `git`, then open a tab on it:

```
REPO="$(git rev-parse --show-toplevel)"
git -C "$REPO" worktree add -b <branch> "$REPO/.claude/worktrees/<name>"
herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd "$REPO/.claude/worktrees/<name>" --label "<Work name>" --no-focus
```

**Take the repo root from `git rev-parse --show-toplevel`, never from `$PWD`.** On
Windows a path can reach you with the wrong casing (`ProgettoCOntrattiAdesione` for a
folder git knows as `ProgettoContrattiAdesione`) — the same folder, a different string.
`rev-parse` returns git's canonical casing; PowerShell's `Resolve-Path` and `Get-Item`
just echo whatever casing you handed them. Casing matters because Claude Code maps a
worktree back to its main repo by comparing realpaths, and Node on Windows doesn't
canonicalise case: one wrong letter and the mapping fails, the worktree counts as an
unknown folder, and the new tab stalls on **"Do you trust the files in this folder?"**
with nobody there to answer. Get the casing right and the worktree inherits the repo's
trust silently.

**Use `git`, not `herdr worktree create`.** `git -C "$REPO"` names the source repo
explicitly, from your own process. `herdr worktree create` without `--cwd` resolves it
from the **UI-focused workspace** instead, so if Mattia is looking at another project
you silently create a worktree of *that* repo at *this* path — and it also puts the
result in its own workspace, which is the detached row above. Doing it with `git`
removes both problems rather than guarding against them.

If the `git` command fails (branch exists, path occupied), stop and report it — don't
retry with `--force` or improvise a different path. If the repo doesn't already
gitignore `.claude/worktrees/`, mention it.

### Either way

`--workspace "$HERDR_WORKSPACE_ID"` is required: omitted, `tab create` targets the
UI-focused workspace, which may be another project entirely. `--no-focus` keeps Mattia
where he is. Read the root pane id from `.result.root_pane` in the JSON response —
never guess IDs. Then:

1. **Start the agent** in that root pane:
   ```
   herdr agent start <name> --kind claude --pane <root pane id> --timeout 120000
   ```
   The default startup timeout is 30s, which a cold agent with MCP servers attached
   can exceed — hence the explicit `--timeout`. Ask which `--kind` if Mattia wants
   something other than `claude`; `herdr agent` lists the installed kinds. If it
   returns `agent_not_ready` the agent came up blocked during startup — `agent read`
   it and report; do not prompt it.
2. **Send the prompt.** Prefix with `MSYS_NO_PATHCONV=1` when the prompt starts with
   `/`, for the same reason it is on `claude --bg` in Path 1: through Git Bash an
   argument with a leading `/` is rewritten into a Windows path, so a slash-command
   prompt like `/work B` would arrive as `C:/Program Files/Git/work B`. Only a leading
   `/` or `//` is affected — slashes inside the text are safe.
   ```
   MSYS_NO_PATHCONV=1 herdr agent prompt <name> "<prompt>" --wait --timeout 120000
   ```
   Don't carry that prefix onto a command that passes `$PWD`: it is a POSIX path in
   Git Bash and only reaches Herdr correctly *because* conversion is on.
   If it returns `agent_blocked` the agent is sitting on a dialog: read it, describe
   it, and let Mattia answer. Never answer it yourself.
3. **Report** `{tab label, name, tab id, pane id, cwd, branch}` and how to reach it
   (`herdr agent read <name>`, or just click the tab). Lead with the tab label —
   that's the row he'll look for, grouped under this workspace. `--no-focus`
   throughout means his focus never moved; say so.

Never `--focus` unless he asked to switch context, and never rename or close a pane,
tab or workspace you didn't create.

---

## Path 1 — Background agent (not in Herdr)

Takes exactly two things: a **session name** and a **prompt**. Nothing else — no
notion of the orchestrator, tasks, branches, or worktrees; whoever invokes it
decides what those two strings are.

1. **Check for a collision.** Run `claude agents --json` and look for a
   non-completed session whose `name` matches. If one exists, stop and report it —
   do not spawn a duplicate. Let whoever invoked you decide (pick a different name,
   or treat the existing session as the answer).
2. **Spawn it:**

   ```
   MSYS_NO_PATHCONV=1 claude --bg --permission-mode auto --name "<name>" "<prompt>"
   ```

   Always pass `--permission-mode auto` so the spawned session starts in auto
   mode even if a project-level setting says otherwise.

   Always prefix with `MSYS_NO_PATHCONV=1` when running this through Git Bash
   (the Bash tool on Windows). Without it, Git Bash's automatic path conversion
   treats any prompt starting with `/` (e.g. a slash-command prompt like
   `/work A`) as a POSIX path and rewrites it into a Windows path rooted at the
   Git install dir — e.g. `/work A` silently becomes
   `C:/Program Files/Git/work A`, corrupting the prompt the spawned session
   receives.

3. **Confirm it started.** Run `claude agents --json` again, find the entry whose
   `name` matches, and read its `pid`, `sessionId`, `cwd`, `status`.
4. **Report back** `{name, pid, sessionId, cwd, status}` to whoever invoked you (a
   human, or the skill/agent that called this one).

### Notes

- In Herdr, prefer Path 1H: a `claude --bg` session can't be talked to, whereas a
  Herdr agent is visible, attachable and promptable by name.
- Runs in whatever directory you invoke it from — it does not create or manage
  worktrees. If the target work needs isolation, that's the spawned session's job
  (or set it up yourself first).
- If `claude --bg` itself fails to start, report the raw error — never claim success
  you haven't confirmed via step 3.

---

## Path 2 — Handoff document

### Where it goes

`docs/handoff/<YYYY-MM-DD>-<short-kebab-slug>.md`, relative to the repo root
(the working directory you were invoked in). Create `docs/handoff/` if it
doesn't exist. The slug describes the work, not the date — e.g.
`docs/handoff/2026-08-16-auth-refactor.md`. If that exact path already exists,
append `-2`, `-3`, … rather than overwriting.

Get today's date from the environment context; don't guess it.

### Rules for both document kinds

**Don't duplicate what other artifacts already say.** Specs, plans, ADRs, Linear
issues, commits, diffs, existing docs — reference them by path, ticket ID, or
URL and say *why they matter*. Never restate a diff or paste a plan's contents
into the handoff; it doubles the token cost and creates a second copy that goes
stale the moment someone edits the original.

**Redact secrets and PII.** This file is written inside the repo and may get
committed. Never write API keys, tokens, passwords, connection strings, or
personal data (client names, emails, phone numbers) into it. Where the next
agent will need a credential, say *where to find it* instead — the env var name
and its source, e.g. "needs `SUPABASE_SERVICE_ROLE_KEY` — in `.env.local`, or
the Supabase dashboard under Project Settings → API". Same for anything from a
password manager or a client's dashboard: name the location, never the value.

**Suggested skills.** Both templates end with this section. List the skills the
receiving agent should invoke, and when — pull from the skills actually
available in this session, one line each:

```markdown
## Suggested skills
- `superpowers:systematic-debugging` — before touching the failing test
- `/esegui-test` — to visually QA the change once it builds
```

Only list skills that genuinely apply. An empty section is better than filler.

### 2a — Context summary

For picking the current conversation back up in a fresh chat. Write the file
with this shape:

```markdown
# Handoff: <topic>

**Date:** <YYYY-MM-DD> · **Repo:** <repo name> · **Branch:** <branch>

## Goal
One paragraph: what we're trying to achieve overall.

## Where we are
What is done and verified, what is half-done, what is untouched.
Be concrete — name files with paths, name the commands that were run.

## Key decisions
Decisions made and *why*, so the next agent doesn't relitigate them.
Include things we explicitly rejected.

## Open questions
Anything unresolved that the next agent (or Mattia) has to decide.

## Next steps
Ordered, concrete. First item should be actionable immediately.

## Files that matter
- `path/to/file.ts` — why it matters

## Suggested skills
- `<skill>` — when to reach for it
```

Rules:
- Only write what actually happened in this conversation. No invented progress,
  no aspirational "we also should" items dressed up as done.
- If tests failed or a step was skipped, say so explicitly in **Where we are**.

### 2b — Task brief

For an agent that has to go read things and do work. Same location, this shape:

```markdown
# Task: <short title>

**Date:** <YYYY-MM-DD> · **Repo:** <repo name> · **Branch:** <branch>

## What to do
The task in 2–5 sentences. Plain, unambiguous.

## Context you need
Why this is being asked, and any background that isn't obvious from the code.

## Read first
- `path/to/file.ts` — what to look for in it
- <URL or doc path> — what it covers

## Constraints
What not to touch, conventions to follow, things that will break if changed.

## Definition of done
A checklist the agent can verify against. Include how to verify (commands to run).

## Out of scope
Explicitly listed, so the agent doesn't widen the work.

## Suggested skills
- `<skill>` — when to reach for it
```

### The paste prompt

After writing the file, output a **short** prompt for Mattia to paste into the
new chat. Short is the point — all the substance lives in the document. Fence it
so it's easy to copy. Shape:

```
I've written a handoff document at `docs/handoff/<file>.md`.
Read it first, then <the one-line ask>.
```

Where `<the one-line ask>` is:
- for a **context summary**: `pick up from the "Next steps" section.`
- for a **task brief**: `carry out the task described there.`

Do not restate the document's contents in the prompt. Two or three lines, max.

### Notes

- Write the file with the Write tool, then tell Mattia the path and hand him the
  paste prompt. Do not commit it unless he asks.
- If you're not in a git repo, still write to `docs/handoff/` under the working
  directory and drop the Branch field from the header.
