# Handoff document for big kickoffs

Use it when the brief is more than a screenful: a feature with context, several files, a plan gate, or a lot of "read first". Small, clear tasks keep the inline brief from workers.md.

The substance lives in a file; the worker's first message is two or three lines pointing at it. Never send the document's contents as the first message.

## Where it goes

`docs/handoff/<YYYY-MM-DD>-<issue-id>-<short-kebab-slug>.md` in the **main checkout** (today's date from the environment, not a guess). Create `docs/handoff/` if missing; if the exact path exists, append `-2`, `-3`.

The worker runs in its own worktree, which will not contain this uncommitted file, so reference it by **absolute path** in the message. Do not commit it, and tell the worker not to commit it unless Mattia asks. If the project does not gitignore `docs/handoff/` and Mattia wants it tracked, that is his call.

## Rules

- **Do not duplicate other artifacts.** Specs, plans, ADRs, issues, commits, diffs: reference by path, issue id or URL and say why they matter. Never paste them in; the copy goes stale.
- **Redact secrets and PII.** Never write keys, tokens, passwords, connection strings, client names, emails or phone numbers. Where the worker needs a credential, say where to find it (the env var name and its source).
- Only write what is true. No invented progress.
- **Suggested skills:** list only skills that genuinely apply and say when to use each (e.g. `superpowers:systematic-debugging` before touching the failing test, `/esegui-test` to QA the change). An empty section beats filler.

## Template (task brief)

```markdown
# Task: <short title>

**Date:** <YYYY-MM-DD> · **Repo:** <repo name> · **Issue:** <ISSUE-ID> · **Branch:** <branch> (based on <defaultBranch>)

## What to do
The task in 2-5 sentences. Plain, unambiguous.

## Context you need
Why this is being asked, and background that is not obvious from the code.

## Read first
- `path/to/file.ts` — what to look for in it
- <issue / doc / URL> — what it covers

## Ownership
- Owns: <files or directories this worker may change>
- Do NOT touch: <files owned by another worker or off limits, and who owns them>

## Constraints
Conventions to follow, things that break if changed.

## Gate
<"Investigate and write the plan, report to the orchestrator and wait for 'go'"  OR  "No gate, execute directly">

## Definition of done
A checklist the worker can verify against, with the commands to run (the project's own check / test commands).

## Out of scope
Listed explicitly so the worker does not widen the work.

## Reporting
<Copy the "Rules" and "Report back" blocks from workers.md here, filled in: tracker, issue id, orchestrator thread id.>

## Suggested skills
- `<skill>` — when to reach for it
```

For a context summary (continuing work already started, not a fresh task) use instead: Goal, Where we are (be concrete; say if tests failed or a step was skipped), Key decisions (and what was rejected), Open questions, Next steps (first one actionable immediately), Files that matter, Suggested skills.

## The message to the worker

Sent as the `message` of `t3_thread_launch` (or `t3_thread_send` for a running thread). Short is the point:

```
Your task for <ISSUE-ID> is in /abs/path/to/docs/handoff/<file>.md (outside your worktree; do not commit it).
Read it first, then carry out the task.
The rules and the mandatory final report are in its Reporting section. Report to thread <ORCHESTRATOR_THREAD_ID>.
```

Then tell Mattia the path and which thread got it. If you have to restart or hand the task to a fresh worker, the document is what carries the context.
