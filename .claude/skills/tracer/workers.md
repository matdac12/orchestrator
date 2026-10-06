# Workers: models, briefs, pitfalls

## Models

Mattia picks. Only when he names none, default to the table and say so; for a **Design or Guide** thread always ask him, it is his thread. For any other model find the exact ids with `jq` on the file named in the `orchestrator_capabilities` result (it is huge; never read it whole): e.g. `jq -r '.providers[]|select(.driverKind=="claudeAgent")|.models[].id'`, `.models[]|select(.id=="<id>")|.options` for effort. His choice overrides the "use for" column. `t3_thread_configure` changes a running thread's model, only when he asks.

| Worker | `modelSelection` | Default for |
| --- | --- | --- |
| DeepSeek 4.1 Flash | `{"instanceId":"opencode","provider":"opencode","model":"opencode-go/deepseek-v4.1-flash"}` | Guide, tests, docs. Not `deepseek-v4-pro` unless asked. |
| Claude Sonnet 5.5 | `{"instanceId":"claudeAgent","provider":"claudeAgent","model":"claude-sonnet-5-5","options":[{"id":"effort","value":"medium"}]}` | Implementation, execute-a-plan, fixes, refactors, review passes. |

Co-Authored-By trailer matches the model: `Claude Sonnet 5.5 <noreply@anthropic.com>`, `DeepSeek <noreply@opencode.ai>`; for others use the model's name.

## Tools

- A thread Mattia sees: `t3_thread_launch` (`runtimeMode: "full-access"`). Quick child work you consume yourself: `Agent` or `delegate_task`.
- Talk: `t3_thread_send` (`queue` for a follow-up after the current turn, `auto` steers); read `t3_thread_read`; wait `t3_thread_wait`. No retry key on launch: after an error, check `t3_thread_list` before retrying.
- Your thread id: `jq -r .parentThreadId` on the capabilities result.

## Worktree seeding (first thread of a task)

Gitignored files do not come with a worktree. If the project has a `.mcp.json`, copy `<repo root>/.claude/settings.local.json` into the worktree's `.claude/` (`mkdir -p` first; a failing `cp` is a stop-and-report), or write `{"enableAllProjectMcpServers": true}` if the source is missing; otherwise the worker stalls on "New MCP servers found". A worktree whose path casing differs from the repo's stalls on "Do you trust the files in this folder?". A stalled worker cannot report that: shortly after launch, `t3_thread_read` it and `t3_pending_request_list`; if stuck, tell Mattia (he accepts trust prompts). The worker's first act: `git rev-parse --path-format=absolute --git-common-dir` must print `<repo root>/.git`, else report blocked "wrong repo". If a worker says its tracker MCP is missing in the worktree, tell Mattia; it must not fall back to the other tracker.

## Brief

Small, clear task: this brief as the launch message. Big task: write a handoff document (handoff.md) containing it and send only the short pointer; the Rules and Report back blocks go in either way.

```
Do <ISSUE-ID> in the <project> repo (this worktree, branch `<issue-id>-slug`, based on the local <defaultBranch>).

## The issue
<title, expected result, constraints>
Owns: <files you may change>. Do NOT touch: <files owned by another worker, and who>.

## Rules
- Read AGENTS.md / CLAUDE.md first. Issues live in <Linear|Traccia> (Traccia: call whoami first); do not write to the other tracker. Set <ISSUE-ID> In Progress when you start, with a short comment; the orchestrator sets every later status.
- Add or update tests; run the project's check command and any e2e the change touches; report real output, failures included.
- Stay local: commit on your branch (message mentions <ISSUE-ID> and ends `Co-Authored-By: <model> <email>`), leave the worktree clean, do not push, open a PR, merge or publish. When the orchestrator tells you `<defaultBranch>` moved, rebase onto it after your current step, rerun checks and report; if the rebase conflicts, abort it and report. No tracker MCP or skill available? Say so in your report.
- Say what Mattia should check by eye if you cannot see the running app.

## Report back (mandatory)
To the orchestrator, thread <ORCHESTRATOR_THREAD_ID>: what changed, branch and last commit SHA, that the worktree is clean, decisions you took alone (so he can veto), test results, what you did NOT verify, findings you did not fix (file, why, size), anything for Mattia to decide. Also send a 5-line summary with `t3_thread_send`.
```
