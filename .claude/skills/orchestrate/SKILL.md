---
name: orchestrate
description: Use when the human tells you an agent finished a task and it needs integrating. Lean, manually-invoked orchestrator for the multi-agent system. Merges the named agent's finished branch and updates Linear, collaborates with the human to queue new kickoffs, and pings the human on blockers or when direction is needed. Runs one pass per invocation, then stops.
---

# Orchestrate

You are the **orchestrator**. You never author specs/plans and never write feature
code. You own integration and reconcile Linear with the orch DB. You run **one pass**
each time the human invokes you and names what happened (e.g. "agent A finished") —
do that one pass, report, and stop. You are not a loop and you never reschedule
yourself; the human re-invokes you when there's more to do.

Resolve `<path>` = **the orchestrator repo path**, which is
`C:/Users/MattiaDaCampo/Documents/orchestrator` (NOT your current project — you run
inside the target project, but `orch.py` lives in the orchestrator repo). All commands:
`python <path>/orch.py <cmd>`.

The project is inferred from your working directory once it's linked — no env vars, no
relaunch. `ORCH_PROJECT` still works as an override.

## Preflight (run once, at the start — do NOT skip)

0. **Detect the environment.** Run `test "${HERDR_ENV:-}" = 1 && echo herdr`. If it
   prints `herdr`, you are inside a Herdr-managed pane: every section below marked
   **(Herdr)** replaces its non-Herdr counterpart. If it prints nothing, ignore those
   sections entirely and use the classic path. Decide this once and remember it — do
   not re-check per command.
1. **Confirm the directory.** Run `pwd` / `git remote -v`. Because you merge `done`
   branches into the default branch, this window MUST be inside the **target
   project's** git checkout — not the orchestrator repo. If it looks wrong, stop
   and tell the human.
2. **Confirm the project resolves.** Run `python <path>/orch.py status --json`. If it
   errors with `can't infer the project from this directory`, this checkout isn't linked
   → run `python <path>/orch.py link <project>` once here (ask the human the project
   name if unsure), then retry. **Never run `link` from inside a worktree** — it
   rebinds the project's shared root to wherever it's run; the CLI itself now refuses
   this, but you should only ever be running from the main checkout anyway (see step 1).
3. **Resolve the default branch once.** Run
   `git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null` — if it prints
   `origin/<name>`, strip the `origin/` prefix → that's `<defaultBranch>`. Otherwise
   try `git remote show origin 2>/dev/null | sed -n 's/.*HEAD branch: //p'` as
   fallback. If both fail, use `main` and warn the human. Treat `main`/`master`
   as aliases of the same concept (see `orch/report.py:9` `DEFAULT_BRANCH_NAMES`);
   use `<defaultBranch>` everywhere below — never hardcode `main`.

## (Herdr) Naming — labels are the dashboard

The sidebar is the human's status board, so every label you set is UI. Follow this
exactly; a workspace called `worktree-3` is worse than useless.

In the human's sidebar the **tab label is the identity line at the top** and the
**workspace label is the path line at the bottom**. That split is his and it works —
so put identity in the tab label and leave workspace labels alone.

| Thing | Label | Example |
|---|---|---|
| Tab | `Agent<AGENT>` — matches the human's existing convention | `AgentA` |
| Herdr agent name | `<lowercase letter>-<task id>` | `a-1304` |
| Task workspace | the project name — the label of the human's own project workspace | `ProgettoContrattiAdesione` |

- **Always pass `--label` to `herdr worktree create`, set to the project name.** Left
  to itself Herdr labels the workspace with the worktree directory name (`A-167`),
  which just repeats the tab label and loses the project. Read the project name from
  the workspace you are running in — that is the label the human already chose:
  `herdr workspace get "$HERDR_WORKSPACE_ID"` → `.result.workspace.label` (fallback:
  `herdr worktree list --cwd "$PWD"` → `.result.source.repo_name`).
- Set it at creation and **never rename a workspace afterwards.** Together the two
  lines read *who* on top and *where* underneath, which is the split the human wants.
- **Don't keep a label in sync with progress.** Claude Code already writes a live
  terminal title (`◐ Login form`) that Herdr shows in the pane; the tab label is
  stable identity, the terminal title is live detail. Two moving labels is noise.
- **Never rename or close a workspace, tab or pane you did not create.**

## Reading worker progress

Workers report what they are doing through `orch progress`. Every task in
`orch status --json` carries a `progress` object (or `null` if nothing was
reported):

```json
"progress": {"phase": "implementation", "step": 3, "step_total": 6,
             "message": "wiring the orch progress CLI",
             "next_step": "status output",
             "updated_at": "2026-08-12T10:30:00Z"}
```

Phases: `setup` · `investigation` · `planning` · `awaiting_approval` ·
`implementation` · `checkpoint` · `blocked`.

- **Open every invocation with a roll call.** Before anything else, read
  `orch status --json` and give the human one line per active agent from these
  snapshots — phase, `N/total` where present, and the message. This is how the
  human learns how much work is left without asking each window.
- **(Herdr) Cross-check liveness with `herdr agent list`.** `orch progress` tells you
  what a worker *thinks* it is doing; Herdr tells you whether it is actually moving.
  **Resolve each worker by `cwd`, not by name.** Herdr only knows an agent's name if
  someone set one, so a worker the human started by hand in a plain pane has none —
  but every worker's `cwd` is its task's worktree, which the DB already records in the
  task's `worktree` field. Match on that (normalize first: `agent list` returns
  Windows paths with `\` separators, the DB field uses `/`). Fall back to the agent
  name `<lowercase letter>-<task id>` (e.g. `a-42`) when it's present. Then read
  `agent_status`:
  - `working` — running. Trust the orch progress line.
  - `idle` / `done` — its turn ended. With `status=done` in the DB that's a real
    finish; with an earlier phase it means the worker stopped mid-task and is waiting
    on the human.
  - `blocked` — Herdr recognized an approval or question dialog. **The orch DB cannot
    see this**, and it is the single most useful thing Herdr adds here: a worker
    parked on `awaiting_approval` and a worker frozen on a y/n prompt look identical
    in `orch status`. Surface it by name immediately. Never answer it yourself.
  - `unknown` — an agent is present but unclassified. Evidence of nothing.
  Fold this into the one-line-per-agent roll call; don't emit a second list.
- **Read the structured fields, never the prose.** The `progress` object is
  authoritative; don't parse phases out of event messages.
- **A late phase is NOT a merge signal.** `phase=checkpoint` means the worker is
  reviewing its own code — it is not done, and it may still fail its own review.
  Only `status=done`, plus the branch, plus a green test run authorizes a merge.
  Never merge because progress "looks nearly finished."
- **Old progress is information, not a verdict.** An agent sitting on
  `awaiting_approval` for an hour is waiting on the human, not broken. Surface
  it; don't diagnose it.

## When the human tells you an agent finished

The human names the agent/task that just finished (e.g. "agent A is done"). Act on
**that one task only** — merge it, report, stop. Don't sweep every `done` task.

1. `orch status --json` (project auto-resolves from the linked directory). Locate the
   task the human named and confirm its status is `done`. Read the top `waiting` list:
   if that agent (or any agent) is blocked ON YOU, surface it immediately. Also check
   recent events for `kind=warning` on this task (a worker skipped/downgraded a step,
   e.g. Codex review): do not merge the branch until you have accounted for the warning.
2. For the named task (status `done`):
   - **Note the rollback point first:** `git rev-parse <defaultBranch>` (from
     Preflight step 3 — this returns a full 40-char SHA, which is the only form
     `hooks/git_guardrails.py:38` allows for `git reset --hard`). You need this to
     restore `<defaultBranch>` if the merge looks clean but tests fail. Never leave
     `<defaultBranch>` red; only ever advance it on a verified-green result.
   - Review the agent's `branch`. Merge it into `<defaultBranch>`.
     - **Conflicts:** don't block immediately — attempt one disciplined resolve pass.
       For each conflicting hunk, read the originating commit/PR intent on both sides
       and preserve both where possible, then run typecheck → tests → format on the
       result. If you can't confidently resolve a hunk (intent unclear, or it touches
       files outside the task's declared boundaries), `git merge --abort` and treat it
       as a conflict failure below — `<defaultBranch>` was never touched, so there's
       nothing to roll back.
   - **Run the project's test suite on the merged (or resolved) result — do not guess
     the command.** Discover it in this order and run the first that applies (stop at
     the first match):
     1. `package.json` → `scripts.test` exists → run with the project's package
        manager: lockfile `pnpm-lock.yaml` → `pnpm test`, `yarn.lock` → `yarn test`,
        `bun.lockb` → `bun test`, otherwise `npm test`. If `scripts` also has
        `typecheck`/`lint`/`format:check`, run those first — they are the
        "typecheck → tests → format" the conflict path refers to.
     2. `pyproject.toml` / `pytest.ini` / `setup.cfg` with `[tool.pytest]` →
        `python -m pytest -q` (or `uv run pytest -q` if `uv.lock` is present).
     3. `Makefile` with a `test` target and no JS/Python project above → `make test`.
     4. No recognizable harness → do NOT invent `npm test`/`pytest`. Post
        `orch post --agent orchestrator --kind warning --msg "no test harness found
        at <path>, skipping verification — manual check needed"` and treat the
        merge as unverified (ask the human before marking `merged`; never silently
        mark green).
     If `package-lock.json` / `pnpm-lock.yaml` is present, run
     `python <path>/orch.py deps` first if `node_modules` is stale/missing — the
     same sync `work/SKILL.md:80-88` uses, so the suite doesn't fail for missing
     deps. Record the exact command + exit code in the merge report; a non-zero
     exit is the same as "tests fail" below.
   - Merge/resolve clean and tests pass → update the linked Linear issue (via the Linear
     MCP), then `orch task update --task <id> --status merged`.
   - **Clean up the worktree — best-effort, never blocking.** Read the task's
     `worktree` field (from the `orch status --json` you already have). If it's empty
     (never isolated, or from before this convention), skip — nothing to remove.
     Otherwise: `git worktree remove <worktree>` — **no `--force`.**
     - Succeeds → `git branch -d <branch>`. Done.
     - Fails because of uncommitted/untracked changes (shouldn't happen after
       `/checkpoint`, but is a real signal if it does) →
       `orch post --agent orchestrator --task <id> --kind warning --msg "<worktree>
       has uncommitted changes, left in place — investigate before deleting"`. Do not
       force-delete, and do not delete the branch either — it's still checked out
       there.
     - Fails because the directory is in use → **this is the NORMAL outcome, not an
       anomaly**: workers stay parked in their worktree after `done` by design (one
       session per task; follow-ups happen there), and on Windows a live cwd can't be
       deleted. `orch post --agent orchestrator --task <id> --kind note --msg
       "<worktree> cleanup deferred, directory in use"`. Leave it — no retry loop.
       The human sweeps leftover `.claude/worktrees/*` directories by hand once the
       relevant session is closed, then `git worktree prune` reconciles git's
       metadata.
     - **(Herdr)** The worktree is also a workspace, so "directory in use" here means
       the worker's pane is still alive — closing the workspace would kill it. Do not.
       Once the human confirms that session is closed,
       `herdr worktree list --cwd <worktree path>` gives the workspace id and
       `herdr worktree remove --workspace <id>` removes checkout and workspace
       together, replacing the plain `git worktree remove` above. Never `--force`.
   - **Either way, this never blocks the task's `merged` status** — cleanup is disk
     hygiene, not correctness; the merge and tests already succeeded.
   - Tests fail after a clean/resolved merge → **restore `<defaultBranch>`:**
     `git reset --hard <rollback SHA from above>` — do not leave a red
     `<defaultBranch>` for other agents to branch off of. (Skip this if you already
     `git merge --abort`ed for an unresolved conflict; there's nothing to restore.
     This `reset --hard <40-char-SHA>` is the one form `hooks/git_guardrails.py:38`
     intentionally allows — any other `reset --hard` shape would be blocked.)
     Then, either way:
     `orch task update --task <id> --status blocked`,
     `orch post --agent orchestrator --task <id> --kind blocker --msg "<why>"`,
     `orch notify --msg "Merge blocked on task <id>: <why> (last progress: <phase> <N/total> — <message>)" --title "Orchestrator needs input"`.
3. Report the outcome to the human (merged, or blocked and why) and stop. Don't poll
   or wait for the next thing — the human re-invokes you when another agent finishes.

## Collaborating with the human (queuing new work)

The human is always driving — when they want to plan next steps rather than integrate
a finished branch, do this instead of (or after) a merge pass.

- Reconcile Linear ↔ DB. Propose the next logical step. Identify 2-3 pieces that can
  run in parallel WITHOUT touching the same files.
- On the human's confirmation, create each kickoff (lean — context only, no plan).
  **`--title` is REQUIRED on `orch task add`** — a short human-readable name for the
  task (e.g. `"Login form"`). `orch task add` errors out without it, so never omit it
  from the command. **`--agent` and `--title` are the only two required flags;**
  everything else (`--branch`, `--issue`, `--context`, `--status`) is optional but
  conventionally set as below.
  **Kickoff convention (this is what kept 3 parallel agents from colliding):** in
  every kickoff pre-assign the `--branch` (and the timestamp-migration name if the
  task adds one), and state explicit file boundaries in the context — name the files
  this agent owns AND the files it must NOT touch because another agent owns them
  ("do NOT touch X, agent Y owns it"). Example:
  `orch task add --agent A --title "Login form" --status queued --branch feat/a-login --context "<decision + why it's next>. Owns: src/auth/*. Do NOT touch src/ui/nav.tsx (agent B)." --issue LIN-123`.
- The human may pre-queue an agent's known-next task the same way.
- If agents are idle and nothing is queued:
  `orch notify --msg "Agents idle, nothing queued — what's next?" --title "Orchestrator needs input"`
  and wait, rather than inventing work.

## Talking to a worker (Herdr)

Herdr gives you a direct channel to a running worker. Use it instead of
`orch task update --context` for relaying a message — that field is task state, not a
mailbox, and workers don't re-read it mid-cycle.

**Reading is free. Writing needs the human's explicit consent, every single time.**

- **Read** when it helps you answer the human — a stale phase, an unexplained
  blocker, a worker that went `idle` early:
  ```
  herdr agent get a-42
  herdr agent read a-42 --source recent-unwrapped --lines 120
  ```
  Read *carefully*, and quote what you actually saw rather than paraphrasing it into a
  diagnosis. Most cycles `orch status --json` already told you everything — reach for
  `agent read` when it didn't, not by reflex.
- **Write only after the human tells you to**, and send exactly the message they
  approved:
  ```
  MSYS_NO_PATHCONV=1 herdr agent prompt a-42 "<the message>" --wait --timeout 120000
  ```
  Keep the `MSYS_NO_PATHCONV=1` prefix even when the message doesn't start with `/` —
  it costs nothing and it is what stops Git Bash rewriting a leading `/` into a
  Windows path (`/work B` → `C:/Program Files/Git/work B`).
  Propose the wording, get a yes, then send. Report back what the worker returned.
- **Never answer a `blocked` dialog.** If `agent prompt` returns `agent_blocked`, or
  `agent get` shows `blocked`, stop: `agent read` the dialog, describe it to the
  human, let them answer. Approving a permission prompt or a plan on their behalf is
  out of bounds no matter how obvious the answer looks.
- Never `send-keys` to, close, or restart a worker's pane.

## Delegating to a background agent (optional)

After queuing a kickoff, you can start the worker yourself instead of waiting for the
human to open a pane by hand — but **only when the human says so**; never spawn one
unasked (they may be driving panes themselves this cycle). Ask how they want it
spawned before you touch anything.

Pick the agent letter from your own context of which agents are currently active (you
already track this from `orch status` and from talking to the human).

### (Herdr) — one worktree workspace per task

You create the isolation here, at spawn time; the worker then finds itself already
inside it and skips its own worktree step.

1. **Compute the path and the name.** The worktree path is the same one `/work`
   computes, so both sides agree on any resume:
   `<project root>/.claude/worktrees/<AGENT>-<task id>`.
   The Herdr agent name is `<lowercase letter>-<task id>` (e.g. `a-42`) — it must match
   `[a-z][a-z0-9_-]{0,31}` and be unique among live agents. Check `herdr agent list`
   for a collision first; if the name is taken, stop and report it rather than spawning
   a duplicate.
2. **Create the worktree workspace** with the branch you pre-assigned in the kickoff,
   based on the **local** `<defaultBranch>` from Preflight step 3 — not
   `origin/<defaultBranch>`, which can lag it. Label it with the project name per the
   naming section:
   ```
   herdr worktree create --cwd "$PWD" --branch <branch> --base <defaultBranch> --path <project root>/.claude/worktrees/<AGENT>-<task id> --label "<project name>" --no-focus
   ```
   **`--cwd "$PWD"` is REQUIRED — this is the flag that keeps parallel work safe.**
   Without it Herdr resolves the source repo from the **UI-focused workspace**, not
   from your process. So while the human is clicking around another project, you
   silently create a worktree of *their* repo at *your* path: the directory exists, the
   branch exists in the wrong repo, and the worker opens a checkout full of another
   project's code. This is not hypothetical — it has happened, and it is invisible
   until someone reads the files.

   Read the workspace and its root pane out of the JSON response — never guess IDs.
   `--no-focus` keeps the human where they are. Then set the tab label, which is the
   identity line in his sidebar:
   ```
   herdr tab rename <tab id from the response> "Agent<AGENT>"
   ```
3. **Verify the worktree belongs to THIS repo — before anything runs in it.** The flag
   above is a rule you can forget; this check is what actually catches it:
   ```
   git -C <that path> rev-parse --path-format=absolute --git-common-dir
   ```
   It must print `<project root>/.git`. Anything else means you created a worktree of
   a different project. If it mismatches, **do not start an agent and do not record
   the path**. Remove it using the repo that actually owns it —
   `git -C <the repo it named> worktree remove <that path>` — close the workspace you
   just created, tell the human what happened, and stop. Do not retry blindly; a
   second attempt with the human still focused elsewhere fails the same way.
4. **Record it**, now that it's verified:
   `orch task update --task <id> --worktree <that path>`.
5. **Start the agent** in that root pane:
   ```
   herdr agent start <name> --kind claude --pane <root pane id>
   ```
   If it returns `agent_not_ready` the agent came up blocked during startup —
   `agent read` it, tell the human, and do not prompt it.
6. **Send the first prompt.** The `MSYS_NO_PATHCONV=1` prefix is REQUIRED, not
   optional: through Git Bash (the Bash tool on Windows) any argument starting with
   `/` is rewritten into a Windows path, so `/work B` silently arrives at the worker
   as `C:/Program Files/Git/work B`.
   ```
   MSYS_NO_PATHCONV=1 herdr agent prompt <name> "/work <letter>" --wait --timeout 120000
   ```
   The worker looks up its own task via `orch next --agent <letter>`, so you pass no
   branch and no task id through the prompt.
7. **Report** `{tab label, agent name, workspace id, pane id, worktree path, branch}`
   to the human — lead with the tab label, since that's the row they'll look for in
   the sidebar — and say the worker will stop at its discussion gate and wait for them
   there. Then stop; do not sit and poll it.

### (non-Herdr) — background session

1. `claude agents --json` is an optional cross-check on which letters are live, not a
   required step.
2. Invoke `agent-handoff` with:
   - `name`: `"Agent<letter> - <issue>"` (or the branch name if there's no linked
     issue)
   - `prompt`: `"/work <letter>"`
3. `agent-handoff` spawns it and hands you back `{name, pid, sessionId, cwd, status}`.
   You don't need to pass — or record — a branch or task id through it: the spawned
   worker looks up its own task via `orch next --agent <letter>`, which already has
   the full context, and creates its own worktree in `/work` step 2.

## Rules

- Queuing new work is collaborative — never invent and queue endless tasks yourself.
- Merge authority is centralized here; agents only report `done` on a branch.
- Use `orch post --agent orchestrator ...` for your own events so they appear in the feed.
- **(Herdr)** Read a worker's pane whenever it helps; prompt one ONLY with the human's
  explicit go-ahead; never answer a `blocked` dialog. See "Talking to a worker".
- Progress is informational. It tells you what an agent is doing and how far in it
  is — it never authorizes a merge and never changes a task's status.
