# Linear sync (solo mode only)

Step 4 of `checkpoint`. Orchestrated mode never runs this — the orchestrator owns
Linear and updates it when it merges your branch (see Step 5).

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
