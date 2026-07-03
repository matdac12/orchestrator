---
name: agent-handoff
description: Spawn a named background `claude` session with a given prompt, so work can be handed off without opening a new pane by hand. Usage: give it a session name and a prompt (e.g. name "AgentA - LIN-298", prompt "/loop /work A"). Standalone — no orchestrator/project knowledge required.
user-invocable: true
---

# Agent Handoff

Spawn a background `claude` session and hand it a prompt in one step, instead of
opening a pane and typing it yourself. This skill takes exactly two things: a
**session name** and a **prompt**. Nothing else — it has no notion of the
orchestrator, tasks, branches, or worktrees; whoever invokes it (you, or another
skill/agent) decides what those two strings should be.

## Usage

Given a `name` and a `prompt`:

1. **Check for a collision.** Run `claude agents --json` and look for a
   non-completed session whose `name` matches. If one exists, stop and report it —
   do not spawn a duplicate. Let whoever invoked you decide (pick a different name,
   or treat the existing session as the answer).
2. **Spawn it:**

   ```
   claude --bg --name "<name>" "<prompt>"
   ```

3. **Confirm it started.** Run `claude agents --json` again, find the entry whose
   `name` matches, and read its `pid`, `sessionId`, `cwd`, `status`.
4. **Report back** `{name, pid, sessionId, cwd, status}` to whoever invoked you (a
   human, or the skill/agent that called this one).

## Notes

- Runs in whatever directory you invoke it from — it does not create or manage
  worktrees. If the target work needs isolation, that's the spawned session's job
  (or set it up yourself first).
- If `claude --bg` itself fails to start, report the raw error — never claim success
  you haven't confirmed via step 3.
