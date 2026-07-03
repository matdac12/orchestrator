# Agent Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the manual "open a pane, type `/loop /work A`" step from delegating a
kickoff — a generic `agent-handoff` skill spawns a named background `claude` session,
`/orchestrate` learns to call it, and `/work` learns to isolate itself into a worktree
branched from local `main` before starting a claimed task.

**Architecture:** `agent-handoff` is a standalone, orchestrator-agnostic skill: given a
session name and a prompt, it spawns `claude --bg --name ... "<prompt>"` and reports
back the running session's info. `/orchestrate` gets a short new section teaching it
to call `agent-handoff` with `name = "Agent<letter> - <issue>"` and
`prompt = "/loop /work <letter>"`. `/work` gets a new per-cycle step that ensures it's
isolated in a git worktree for the task's branch (creating one off local HEAD if
needed) before touching the task.

**Tech Stack:** Markdown skills only — no `orch.py`/Python changes; `orch task update
--worktree` already exists.

## Global Constraints

- No `orch.py`/CLI changes — the existing `task update --worktree <path>` covers all
  the DB bookkeeping this needs.
- `agent-handoff` must stay fully independent of the orchestrator: no `orch`
  references, no branch/worktree parameters, no task lookups inside it.
- Skills are markdown; there is no unit-test suite for them — verification is running
  `python -m pytest -q` (must stay green, since these are docs-only changes) plus a
  manual dry run described in each task.

---

## File Structure

- `.claude/skills/agent-handoff/SKILL.md` — CREATE: the generic spawn primitive
  (name + prompt in, spawned session info out)
- `.claude/skills/orchestrate/SKILL.md` — MODIFY: add a "Delegating to a background
  agent" section to the collaborative half
- `.claude/skills/work/SKILL.md` — MODIFY: add a per-cycle "Ensure isolation" step
  before branching on task status
- `README.md` — MODIFY: list `/agent-handoff` in the skills section and add it to
  both user-level install loops

---

### Task 1: The `agent-handoff` skill

**Files:**
- Create: `.claude/skills/agent-handoff/SKILL.md`

- [ ] **Step 1: Write the skill**

```markdown
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
```

- [ ] **Step 2: Verify the suite still passes (no code change)**

Run: `python -m pytest -q`
Expected: PASS (unchanged — markdown only).

- [ ] **Step 3: Manual dry run**

From any git checkout, run the skill by hand once: pick a throwaway name (e.g.
`"agent-handoff-smoke-test"`) and prompt (e.g. `"/help"`), follow its four steps, and
confirm `claude agents --json` shows an entry with that exact `name` and a live `pid`.
Then clean it up: `claude agents` (interactively stop it) or let it finish on its own.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/agent-handoff/SKILL.md
git commit -m "feat: agent-handoff skill to spawn named background sessions"
```

---

### Task 2: `/orchestrate` — delegate via `agent-handoff`

**Files:**
- Modify: `.claude/skills/orchestrate/SKILL.md`

- [ ] **Step 1: Add the delegation section**

In `.claude/skills/orchestrate/SKILL.md`, the file currently ends with:

```markdown
## Rules

- Queuing new work is collaborative — never invent and queue endless tasks yourself.
- Merge authority is centralized here; agents only report `done` on a branch.
- Use `orch post --agent orchestrator ...` for your own events so they appear in the feed.
```

Insert a new section immediately **before** `## Rules`, so the file ends with:

```markdown
## Delegating to a background agent (optional)

After queuing a kickoff, you can hand it to a background session instead of waiting
for the human to open a pane and start it by hand — but only when the human says so;
never spawn one unasked (they may be driving panes themselves this cycle).

1. Pick the agent letter from your own context of which agents are currently active
   (you already track this by talking to the human and reading `orch status`).
   `claude agents --json` is there as an optional cross-check if you want extra
   certainty, not a required step.
2. Invoke `agent-handoff` with:
   - `name`: `"Agent<letter> - <issue>"` (or the branch name if there's no linked
     issue)
   - `prompt`: `"/loop /work <letter>"`
3. `agent-handoff` spawns it and hands you back `{name, pid, sessionId, cwd, status}`.
   You don't need to pass — or record — a branch or task id through it: the spawned
   worker looks up its own task via `orch next --agent <letter>`, which already has
   the full context.

## Rules

- Queuing new work is collaborative — never invent and queue endless tasks yourself.
- Merge authority is centralized here; agents only report `done` on a branch.
- Use `orch post --agent orchestrator ...` for your own events so they appear in the feed.
```

- [ ] **Step 2: Verify the suite still passes (no code change)**

Run: `python -m pytest -q`
Expected: PASS (unchanged — markdown only).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/orchestrate/SKILL.md
git commit -m "feat(orchestrate): delegate kickoffs to background agents via agent-handoff"
```

---

### Task 3: `/work` — ensure isolation before working a task

**Files:**
- Modify: `.claude/skills/work/SKILL.md`

- [ ] **Step 1: Replace the `## One cycle` section**

In `.claude/skills/work/SKILL.md`, replace the entire `## One cycle` section (from
the `## One cycle` heading through the end of step `4. **Finish:**`, i.e. everything
up to but not including `## Blockers`) with:

```markdown
## One cycle

1. **Find my task:** `orch next --agent <AGENT> --json`.
   - Empty output → say "idle, nothing queued" and end the turn. The loop rechecks later.

2. **Ensure isolation.** Before touching this task, confirm you're working in a git
   worktree branched from local HEAD, not the shared checkout:
   - Detect existing isolation the way `using-git-worktrees` does: compare
     `git rev-parse --git-dir` to `git rev-parse --git-common-dir` (and rule out a
     submodule via `git rev-parse --show-superproject-working-tree`). If they differ
     and you're not in a submodule, you're already isolated — skip the rest of this
     step.
   - Not isolated and the task has no `branch` set → skip this step; nothing to
     isolate on yet.
   - Not isolated, task has a `branch`, and its `worktree` field is already set
     (resuming after a restart) → re-enter it: `EnterWorktree` with
     `path: <that worktree path>` (or plain `cd <that path>` if the tool isn't
     available).
   - Not isolated, task has a `branch`, no `worktree` recorded yet (fresh claim) →
     create one. Skip `using-git-worktrees`'s human-consent gate — you're unattended,
     and the human already opted in by using the orchestrator system. Prefer the
     native `EnterWorktree` tool, but first check this project's `worktree.baseRef`
     setting (`.claude/settings.json`): its default, `fresh`, branches off
     `origin/<default-branch>`, which can lag your local `main`. If it is not `head`,
     skip `EnterWorktree` and fall back to plain
     `git worktree add -b <branch> <new-path>` instead — it bases off local HEAD
     with no setting needed. Either way, once created:
     `python <path>/orch.py task update --task <id> --worktree <new-path>`.
   - If creation fails (e.g. a sandboxed environment denies it), work in place and
     mention the fallback in your next `/report`.

3. **Branch on `status`:**

   - **`queued`** → `orch claim --agent <AGENT> --json` to take it (→ `discussing`).
     Then:
     - `orch notify --msg "Agent <AGENT>: <title> — <context>" --title "Come discuss"`
     - Post the signal: `orch post --agent <AGENT> --kind needs_discussion --msg "claimed, awaiting brainstorm"` (this specific kind has no /report alias; use it as-is). This raises the `needs_human` flag so the human's `orch status` shows you under "WAITING ON YOU".
     - **Investigation-first for dated/old issues.** If the issue is not freshly
       written (it references work that may already be underway or shipped — drift
       risk), do NOT start brainstorming a build. First run **PHASE 1 = gap-analysis**:
       read the current code vs the issue and report what is already done, partial, or
       missing — write NO code. Then **PHASE 2 = decide with the human** what (if
       anything) still needs building, and only then proceed to the brainstorm. If
       PHASE 1 shows the issue is already satisfied, say so and propose closing it
       rather than inventing work.
     - Brainstorm WITH the human: invoke `superpowers:brainstorming`, using the
       task's `context` as the starting brief, through to `superpowers:writing-plans`.
     - When the plan file exists: `orch task update --task <id> --plan <plan_path>`.
     - Ask the human to approve the plan. On approval, continue to step 4.

   - **`discussing`** (resumed) → continue the brainstorm/plan from where it stands.

   - **`executing`** (resumed) → resume the plan from the first unchecked box.

   - **`blocked`** → do nothing; the human must intervene. End the turn.

4. **Execute (after plan approval):**
   - `/report executing executing plan` (flips the task to `executing`).
   - Implement the plan via `superpowers:executing-plans`. After each plan task:
     `/report plan task N done` (recorded as a note).
   - Self-review and finish with `/checkpoint` — it runs code review, optional Codex
     review, commits your branch, and reports `done` for you.

5. **Finish:**
   - `/checkpoint` (Step 4 above) already reported `done`. Loop back to step 1 for the
     next task.
```

- [ ] **Step 2: Verify the suite still passes (no code change)**

Run: `python -m pytest -q`
Expected: PASS (unchanged — markdown only).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/work/SKILL.md
git commit -m "feat(work): ensure worktree isolation before working a claimed task"
```

---

### Task 4: README — document `/agent-handoff` and install it

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the skill to the skills list**

In `README.md`, in the `## Skills (the autonomous loop)` section, replace:

```markdown
- **`/checkpoint`** — worker post-work flow: code review → optional Codex review →
  commit → auto-report `done`. Does not touch Linear (the orchestrator owns that).

Both live in `.claude/skills/`.
```

with:

```markdown
- **`/checkpoint`** — worker post-work flow: code review → optional Codex review →
  commit → auto-report `done`. Does not touch Linear (the orchestrator owns that).
- **`/agent-handoff`** — spawn a named background `claude` session with a given
  prompt. Standalone (no orchestrator knowledge) — use it any time you want to hand
  off work without opening a pane by hand. `/orchestrate` uses it to delegate
  kickoffs when you ask it to.

All five live in `.claude/skills/`.
```

- [ ] **Step 2: Add it to both install loops**

In `README.md`, in `## Installing skills for worker windows`, replace the macOS/Linux
loop:

```bash
for s in work report checkpoint orchestrate; do
  ln -s "$(pwd)/.claude/skills/$s" ~/.claude/skills/$s
done
```

with:

```bash
for s in work report checkpoint orchestrate agent-handoff; do
  ln -s "$(pwd)/.claude/skills/$s" ~/.claude/skills/$s
done
```

and replace the Windows loop:

```cmd
for %d in (orchestrate work report checkpoint) do mklink /J "%USERPROFILE%\.claude\skills\%d" "C:\path\to\orchestrator\.claude\skills\%d"
```

with:

```cmd
for %d in (orchestrate work report checkpoint agent-handoff) do mklink /J "%USERPROFILE%\.claude\skills\%d" "C:\path\to\orchestrator\.claude\skills\%d"
```

- [ ] **Step 3: Verify the suite still passes**

Run: `python -m pytest -q`
Expected: PASS (unchanged — docs only).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: agent-handoff skill, install it alongside the other four"
```

---

## Notes for the implementer

- **Run from the repo root** so `python -m pytest` resolves the `orch` package. These
  four tasks touch only markdown/docs, so the suite should be a no-op green check
  each time — its purpose here is only to catch an accidental typo breaking something
  unrelated (e.g. a stray file edit).
- **Update the user-level skill links after Task 1 is committed:** the four existing
  skills are junction-linked (Windows) / symlinked (macOS/Linux) from
  `~/.claude/skills/*` into this repo per the README, so edits propagate without a
  resync. `agent-handoff` needs the same one-time link
  (`mklink /J "%USERPROFILE%\.claude\skills\agent-handoff" "<repo>\.claude\skills\agent-handoff"`
  on Windows) before it's usable from another project's window — this is a manual,
  one-time step outside the plan's git history (same as the original four skills were
  installed), not a task by itself.
- **Order matters for Task 3's manual verification:** you can't fully dry-run `/work`'s
  new isolation step without a real queued task with a `branch` set — reviewing the
  wording for correctness against the design doc is the practical check here; an
  end-to-end run happens naturally the next time a real kickoff is delegated.
