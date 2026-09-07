---
name: agent-handoff
description: Hand off work to another agent as a markdown handoff document in the repo (context summary, or a task brief for a fresh agent) plus a short prompt pointing at it — either handed to you to paste anywhere, or sent automatically to an agent spawned in a new Herdr tab in this workspace, on this checkout or on its own worktree. Also spawns a named background `claude` session when a caller supplies the prompt. Standalone — no orchestrator/project knowledge required.
disable-model-invocation: true
user-invocable: true
argument-hint: "What will the next session focus on?"
---

# Agent Handoff

Hand the current work to another agent. The handoff itself is always a markdown
document in the repo plus a short prompt pointing at it; what varies is delivery —
Mattia pastes the prompt himself, or (in Herdr) a fresh agent is spawned in a tab
and sent it. The plain-terminal `claude --bg` path is the exception: it forwards a
caller-supplied prompt and writes nothing.

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

- **Background agent** — I write the handoff document and spawn a named `claude --bg` session on it right now (terminal workflow).
- **Prompt to paste** — I write the handoff document and give you the short prompt to paste into a fresh chat (desktop-app workflow).

Background agent → Path 1, with the document written first and its paste prompt used
as the spawn prompt. Prompt to paste → Path 2. As in Herdr, both write the document;
only the delivery differs.

### Herdr question

**Being inside Herdr is not a reason to assume he wants an agent spawned.** He may
well want the prompt to paste somewhere else entirely, and guessing wrong leaves a
live pane he has to go clean up. Ask, every time.

Question — *"How do you want to hand this off?"*, header `Handoff`:

- **New tab here** — I write the handoff document, open a tab in this workspace, start an agent in it, and point it at the document.
- **Prompt to paste** — I write the handoff document and give you the short prompt to paste wherever you like.

**Both write the document.** The only difference is who gets the short prompt: the
new agent, or Mattia's clipboard. Inside Herdr the tab path is Path 2 with the last
step automated — never a big prompt pasted in as the agent's first message.

If he picks the tab, ask the second one immediately — *"Should it have its own
branch?"*, header `Isolation`:

- **Its own worktree** — new branch and checkout, isolated from what you're doing here.
- **This checkout** — same working directory. For work that needs no isolation.

Tab → Path 1H, with the isolation he chose. Prompt to paste → Path 2.

### Document kind

Ask this immediately — *"What kind of document?"*, header `Doc kind`:

- **Context summary** — where we are, what's done, what's next, so a fresh chat can pick up.
- **Task brief** — instructions for another agent: what to read, what to do, what "done" looks like.

Ask it whenever the human is the one invoking — Path 2, Path 1H and Path 1 alike all
write a document. Skip it only when a caller supplied the prompt (below). If the
invocation arguments already make the kind obvious, pick it yourself instead of
asking.

Then follow the matching section below.

### When a caller supplied the prompt

If another skill or agent invoked this one with an explicit `prompt` (e.g.
`/work B`), that prompt is the handoff — send it verbatim, write no document, and
skip the questions above entirely. The document flow is for the human path.

---

## Path 1H — Herdr agent (in Herdr only)

Takes the same two things as Path 1 — a **name** and a **prompt** — plus the isolation
chosen in Step 0. Nothing else: no notion of orchestrators, tasks or tickets.

### First: write the document

Before touching Herdr, write the handoff document exactly as Path 2 describes —
same location, same template for the kind chosen in Step 0, same rules about not
duplicating other artifacts and redacting secrets. **The prompt you will send the
agent is Path 2's paste prompt, verbatim**: the two or three lines that name the
file and give the one-line ask. Nothing more.

Never send the document's contents — or a reconstruction of them — as the agent's
first message. The substance lives in the file; the agent reads it there. A wall of
text as the opening prompt is the thing this path exists to avoid.

Write the file on the checkout the agent will actually run on: for **this checkout**
that's here; for **its own worktree** create the worktree first (below), then write
the document inside it and reference it by its repo-relative path, so the path in
the prompt resolves from the agent's cwd.

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
WT="$REPO/.claude/worktrees/<name>"
git -C "$REPO" worktree add -b <branch> "$WT"
mkdir -p "$WT/.claude"
[ -f "$REPO/.claude/settings.local.json" ] && cp "$REPO/.claude/settings.local.json" "$WT/.claude/settings.local.json"
herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd "$WT" --label "<Work name>" --no-focus
```

**Copy `.claude/settings.local.json` across.** It is gitignored, so a fresh worktree
starts without it — and it is where `enableAllProjectMcpServers` / `enabledMcpjsonServers`
live. Without them a repo with a `.mcp.json` greets the new agent with **"New MCP servers
found — do you want to enable them?"**, which blocks startup exactly the way the trust
dialog used to, with nobody there to press Enter. Copying the file also gives the agent
the same permission allowlist Mattia already approved here. If the source repo has no
such file and its `.mcp.json` exists, write `{"enableAllProjectMcpServers": true}` into
the worktree's copy instead.

**Take the repo root from `git rev-parse --show-toplevel`, never from `$PWD`.** On
Windows a path can reach you with the wrong casing — the same folder, a different
string. The recurring one is `ProgettoCOntrattiAdesione`, a typo for the real folder
`C:\Users\MattiaDaCampo\Documents\Publiscoop\ProgettoContrattiAdesione`: lowercase
`o` in `Contratti`. `rev-parse` returns git's canonical casing; PowerShell's
`Resolve-Path` and `Get-Item` just echo whatever casing you handed them, and stale
`~/.claude.json` entries carry the typo forward — so never copy a casing out of a
prompt, a typed path, or that file. Casing matters because Claude Code maps a
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
2. **Send the prompt — the short one.** It is the paste prompt from the document you
   wrote in "First: write the document": two or three lines naming the file and the
   one-line ask, not the document itself. Prefix with `MSYS_NO_PATHCONV=1` when it starts with
   `/`, for the same reason it is on `claude --bg` in Path 1: through Git Bash an
   argument with a leading `/` is rewritten into a Windows path, so a slash-command
   prompt like `/work B` would arrive as `C:/Program Files/Git/work B`. Only a leading
   `/` or `//` is affected — slashes inside the text are safe.
   ```
   MSYS_NO_PATHCONV=1 herdr agent prompt <name> "<prompt>" --wait --until working --until blocked --timeout 15000
   ```
   `--until working --until blocked` is deliberate. Bare `--wait` matches `idle`,
   `done` or `blocked` — it blocks until the agent's whole first turn is *over*, a
   minute or two you then throw away in step 3. Herdr confirms `working`-or-`blocked`
   within 5s of an accepted submission, so these two states return in seconds and still
   prove the submission was accepted and that the agent left idle. Herdr does not track
   turns, so it is not a per-turn receipt — but a just-started agent has no other turn in
   flight, and step 3 needs no more than that.
   Don't carry that prefix onto a command that passes `$PWD`: it is a POSIX path in
   Git Bash and only reaches Herdr correctly *because* conversion is on.
   If it returns `agent_blocked` the agent is sitting on a dialog: read it, describe
   it, and let Mattia answer. Never answer it yourself.
3. **Report** `{tab label, name, tab id, pane id, cwd, branch, handoff doc path}` and
   how to reach it (`herdr agent read <name>`, or just click the tab). Lead with the
   tab label — that's the row he'll look for, grouped under this workspace.
   `--no-focus` throughout means his focus never moved; say so. Don't re-print the
   paste prompt: it's already been delivered.

Never `--focus` unless he asked to switch context, and never rename or close a pane,
tab or workspace you didn't create.

---

## Path 1 — Background agent (not in Herdr)

Takes exactly two things: a **session name** and a **prompt**. Nothing else — no
notion of the orchestrator, tasks, branches, or worktrees; whoever invokes it
decides what those two strings are.

When *Mattia* picked this path, write the handoff document first (Path 2) and use
its paste prompt as the spawn prompt — short, pointing at the file, never the
document's contents inlined. When a *caller* supplied the prompt, use it verbatim
and write nothing.

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

**Path 1H uses this whole section too** — it writes the same document and then sends
the paste prompt to the agent instead of handing it to Mattia. Everything below
applies to both.

### Where it goes

`docs/handoff/<YYYY-MM-DD>-<short-kebab-slug>.md`, relative to the repo root
(the working directory you were invoked in — or, in Path 1H's worktree case, the
worktree the agent will run in). Create `docs/handoff/` if it doesn't exist. The
slug describes the work, not the date — e.g.
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
  paste prompt. Do not commit it unless he asks. In Path 1H, send that same prompt
  to the agent instead of handing it over.
- If you're not in a git repo, still write to `docs/handoff/` under the working
  directory and drop the Branch field from the header.
