# Workers: models, tools, briefs

## Models

Mattia picks the model. These two are only the defaults when he names none (say which you used). When he names another (another OpenCode model, Opus, ...), find its exact `instanceId` and model id with `jq` on the `orchestrator_capabilities` result (for example `jq -r '.providers[]|select(.driverKind=="claudeAgent")|.models[].id'`, and `.models[]|select(.id=="<id>")|.options` for options such as effort), and copy the `Co-Authored-By` trailer to match the model. Never choose another model yourself.

| Worker | `modelSelection` for `t3_thread_launch` | Use for |
| --- | --- | --- |
| DeepSeek 4.1 Flash (OpenCode) | `{"instanceId":"opencode","provider":"opencode","model":"opencode-go/deepseek-v4.1-flash"}` | Guide and interview threads, reliability and test work, docs. Not `deepseek-v4-pro` unless Mattia asks for it. |
| Claude Sonnet 5.5 | `{"instanceId":"claudeAgent","provider":"claudeAgent","model":"claude-sonnet-5-5","options":[{"id":"effort","value":"medium"}]}` | Feature and fix implementation, refactors, review passes (`simplify`, `code-review`). Raise effort only if a task needs it. |

Many more models exist (`orchestrator_capabilities` output is huge: `jq '.providers[]|{providerInstanceId,driverKind,models:(.models|length)}'`). Change a running thread's model with `t3_thread_configure` (takes effect next turn), only when Mattia asks.

## Which tool

- Mattia says "spawn a thread/agent" or wants to talk to it: `t3_thread_launch` (top-level thread in his sidebar). Always `runtimeMode: "full-access"`.
- Quick in-session child work you will consume yourself: the `Agent` tool or `delegate_task`; use `task_status` / `task_cancel`. Do not use `t3_thread_launch` for it.
- Talk to a running worker: `t3_thread_send` (steers it if mid-run), read with `t3_thread_read`, wait with `t3_thread_wait`.
- `t3_thread_launch` has no retry key. After an error or lost response check `t3_thread_list` before retrying.
- Workspace: code work gets `{"type":"worktree","baseRef":"<default branch>","branch":"<issue-id>-slug","startFromOrigin":false}`. Only threads that write nothing (read-only investigation, pure Q&A) can use `{"type":"root"}`; a guide thread that commits decisions needs a worktree too.

## Worktree seeding

`t3_thread_launch` makes the worktree, but gitignored files do not come with it. For a project with a `.mcp.json`, copy `<repo root>/.claude/settings.local.json` into the worktree's `.claude/` (`mkdir -p` first; skip only if the source does not exist; a `cp` that fails is a stop-and-report) so the worker does not stall on "New MCP servers found". If the source is missing but `.mcp.json` exists, write `{"enableAllProjectMcpServers": true}`. Do this right after launch if the worker is not yet past startup, or tell Mattia if it already stalled. Take the repo root from `git rev-parse --show-toplevel`. A worker's first act is to confirm `git rev-parse --path-format=absolute --git-common-dir` prints `<repo root>/.git`; if not, it reports blocked "wrong repo" and stops.

## Inline vs handoff

Small, clear task: the brief template below, sent as the launch message. Big task (context, several files, plan gate): write a handoff document and send only the short pointer message (see [handoff.md](handoff.md)). The "Rules" and "Report back" blocks below go in either way: inline in the message for a small task, copied into the handoff document's Reporting section for a big one.

## Brief template (copy, fill, keep the rules)

```
Do <ISSUE-ID> in the <project> repo (this worktree, branch `<issue-id>-slug`, based on the local <default branch>).

## The issue
<title, the file(s), the expected result, the constraints>
Owns: <files you may change>. Do NOT touch: <files owned by another worker, and who>.
<Gate: "investigate what already exists, write the plan, report to me and wait for 'go'" OR none>

## Rules
- Read AGENTS.md / CLAUDE.md and any docs they point to first. Issues live in <Linear|Traccia> via its MCP tools (Traccia: call whoami first). Do not write to the other tracker.
- Set <ISSUE-ID> In Progress when you start, with a short comment about what you chose. The orchestrator sets every later status; do not change it after your report. If the MCP is not available in this worktree, say so in your final report.
- Tests: add or update them; run the project's check command and any e2e the change touches; report real output, including failures.
- Commit with a message ending `Co-Authored-By: <model name> <noreply@anthropic.com>` (DeepSeek: `Co-Authored-By: DeepSeek <noreply@opencode.ai>`), and mention `<ISSUE-ID>` in it. **Stay local: commit on your branch in this worktree, leave the worktree clean, and do not push, open a PR, merge or publish anything** (tracker MCP calls and dependency installs are fine). The orchestrator merges and pushes. Do not change repo visibility or tokens.
- If you cannot see the running app, say what Mattia should check visually.

## Report back (mandatory, every worker, every time)
Final report to me (the orchestrator, thread <ORCHESTRATOR_THREAD_ID>): what changed, design decisions you took alone (flag so Mattia can veto), test results, what you did NOT verify, findings you did not fix (one line each: file, why, size) and anything for Mattia to decide. If t3_thread_send is available, also send a 5-line summary with the branch name and last commit SHA to that thread id. Say the worktree is clean and everything is committed.
```

Your thread id is `parentThreadId` in the `orchestrator_capabilities` result (query it with `jq -r .parentThreadId`).

## Guide threads (interview or walkthrough)

One question at a time, short, 2 or 3 options with a recommendation, Mattia answers in a word. Decisions get written to a local branch (committed, not pushed), plus a comment on the relevant issues. They file no new issues unless asked, and list implied work for the orchestrator instead.
