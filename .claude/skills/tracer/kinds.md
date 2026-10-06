# Task kinds

## 1. Readiness: does it need discussion first?

Before choosing a kind, judge whether the task is ready to build. Read the issue and, if it is not obviously fresh, the code it touches, then put it in one bucket and tell Mattia in a line:

- **Ready.** Clear outcome, bounded scope, you can name the files it owns, and nothing in it needs a decision from him. → Implement / Fix / Review / Investigate directly.
- **Needs discussion.** Several reasonable approaches, product or design decisions only he can make, unclear scope, or it touches something that needs a spec. → Design thread, with him in it.
- **Needs triage.** The issue is vague, old, a duplicate, or may already be done or obsolete (check what shipped: SKILL.md "Planning"). → a short read-only Investigate first, then recommend to Mattia: do it (ready or design), backlog (say what would promote it), or drop. He decides.

When unsure between ready and discussion, say which you lean towards and why, and let him choose: a wrongly "ready" task wastes a worker, a wrongly "discussion" task wastes a few minutes of his.

## 2. One worktree per task

A task is one issue = one branch = **one worktree**. Threads come and go inside it, one at a time: the design thread, then the execution thread, then a follow-up fix after review. They all work in the same checkout, so the spec and plan are already there, dependencies are already installed, and the executor starts with the full context on disk and nothing to merge or copy first.

- The first thread for the task creates the worktree (`t3_thread_launch` with `workspaceStrategy` worktree, branch `<issue-id>-slug`, base the local `<defaultBranch>`). Record its path and branch in the tracker issue.
- Every later thread for that task is launched with `{"type":"existing_worktree","worktreePath":"<path>","branch":"<branch>"}`. Look the path up with `t3_worktree_list` / `t3_thread_read` rather than guessing it.
- **Only one thread active in a worktree at a time.** Before launching the next one, check the previous thread is idle or finished (`t3_thread_list`) and its work is committed (`git -C <path> status --porcelain` empty). Parallel work means parallel tasks, each with its own worktree.
- Seed the worktree and install dependencies **once**, in the first thread (workers.md "Worktree seeding"); later threads inherit it.
- The worktree is cleaned up only after the whole task is merged and verified (SKILL.md "Cleanup"), not after each thread.
- Read-only kinds (Review of someone else's branch, Investigate) don't need a worktree; root workspace is fine.

## 3. Kind

Classify every piece of work before you spawn it, say the kind to Mattia in a word, and use the matching recipe. Models: Mattia picks, as always (workers.md). Skills below are Claude Code skills: they only exist for Claude workers. For a non-Claude worker (OpenCode, Codex, ...) put the equivalent steps in the brief instead of naming the skill.

| Kind | Who drives | Workspace | Output |
| --- | --- | --- | --- |
| Design (brainstorm → spec → plan) | Mattia, in the thread | the task's worktree (created here) | spec and plan files, committed |
| Execute a plan | the worker, alone | the same worktree as the design thread | code, committed |
| Implement (small, clear task) | the worker, alone | worktree | code, committed |
| Fix / debug | the worker, alone | worktree | fix + test, committed |
| Review | the worker, alone | root or the branch's worktree | findings report, no edits |
| Investigate / research | the worker, alone | root | findings report |
| Guide (interview, walkthrough) | Mattia, in the thread | worktree if it commits decisions | decisions, committed |

## Design: brainstorm, spec, plan

This is where Mattia makes the decisions, so the thread is **his**: he talks to the agent directly in the sidebar. Do not steer it, answer for it or rush it; you wait for its report. Never spawn the execution thread before the plan is ready and Mattia has approved it.

Ask Mattia which skill family if he has not said (default: superpowers):

- **superpowers:** `superpowers:brainstorming` through the spec, then `superpowers:writing-plans` to the plan.
- **Matt Pocock:** `grill-with-docs` (or `grill-me`) to sharpen the design, then `to-spec`, and `to-tickets` if he wants it broken into tickets. For something too big for one session, `wayfinder`. These write to the project's tracker or local docs per its setup (`setup-matt-pocock-skills`); make sure they target the tracker you chose, and tell the worker which one.

Brief (short, or a handoff doc if the context is big; handoff.md): the goal and issue id, which skill family, where the spec and plan go (the project's convention, else `docs/superpowers/specs/` and `docs/superpowers/plans/`), file ownership if it touches existing docs, and the rules and report-back from workers.md. Add: **commit the spec and plan on your branch, do not start implementing, and report to me when the plan is approved by Mattia** (not before: a draft is not a report). The report gives the spec path, the plan path, the branch and commit, the task count in the plan, and any open decision.

When the report arrives: record it in the tracker (comment with the paths, issue stays In Progress or moves to a "planned" state if the tracker has one), tell Mattia in two lines, and propose the execution thread. Spawn it only on his yes.

## Execute a plan

A fresh thread (clean context, only the plan) in the same worktree as the design thread.

1. **Launch into the design thread's worktree** (`existing_worktree`, section 2), once the design thread is idle and the spec and plan are committed. The plan is already on the branch, so there is nothing to merge first and the executor sees everything the design thread produced. Spec, plan and implementation all land on the one task branch and merge into `<defaultBranch>` together at the end.
2. **Brief:** use `superpowers:executing-plans` on `<repo-relative path to the plan>`, the issue id, the file boundaries from the plan, the rules, and the report-back. Tell it to follow the plan as written, flag deviations in its report rather than silently changing scope, run the project's checks, and finish with a quality pass (`simplify`, `code-review`) before committing.
3. Report-back as usual; then the normal loop: record, review the real diff **against the plan**, tell Mattia, merge when he says.

For a plan with independent parts, split it into separate tasks (each its own issue, branch and worktree, boundaries from the plan, dependency order respected) rather than running several executors in one worktree; otherwise one executor takes the whole plan.

## The simpler kinds

- **Implement (small, clear):** the inline brief from workers.md. No design step. If it turns out to be bigger or ambiguous than it looked, the worker stops and reports, and you reclassify as Design.
- **Fix / debug:** `superpowers:systematic-debugging`; the brief names the symptom, how to reproduce, and asks for the root cause in the report, not just a patch. Add a regression test.
- **Review:** `code-review` or `simplify` on a named branch or diff; findings only, no edits. For a second model's opinion use `ask-codex` yourself rather than a worker.
- **Investigate / research:** read-only, root workspace, nothing committed. The report is the deliverable; findings you will act on become issues.
- **Guide:** one question at a time, 2 or 3 options with a recommendation (workers.md "Guide threads").
