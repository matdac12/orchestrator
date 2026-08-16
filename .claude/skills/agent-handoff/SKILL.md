---
name: agent-handoff
description: Hand off work to another agent, either as a named background `claude` session or as a markdown handoff document in the repo (context summary, or a task brief for a fresh agent) plus a short prompt to paste into the desktop app. Standalone — no orchestrator/project knowledge required.
user-invocable: true
disable-model-invocation: true
argument-hint: "What will the next session focus on?"
---

# Agent Handoff

Hand the current work to another agent. There are two delivery paths, and they
are mutually exclusive.

## Step 0 — Ask which path

**If arguments were passed**, treat them as a description of what the next
session will focus on. Use them to pick the document kind yourself instead of
asking (a description of work to *do* → task brief; a description of work to
*continue* → context summary), and tailor the whole document to that focus —
drop sections of the conversation that don't serve it. Still ask which *path*
(background agent vs. document) unless that's obvious from the arguments too.

Always ask first, unless the invoker already said which one:

> Background agent, or handoff document?
>
> 1. **Background agent** — spawn a named `claude --bg` session right now (terminal workflow).
> 2. **Handoff document** — write a markdown file in the repo and give you a short prompt to paste into a fresh chat (desktop-app workflow).

If **2**, ask the second question immediately:

> What kind of document?
>
> - **a. Context summary** — where we are, what's done, what's next, so a fresh chat can pick up.
> - **b. Task brief** — instructions for another agent: what to read, what to do, what "done" looks like.

Then follow the matching section below. Never write the document *and* spawn a
background session.

---

## Path 1 — Background agent

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
