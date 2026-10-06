# Review, merge, push, settle

## Review

Read the real diff (`git diff <defaultBranch>...<branch>`, `git log`), not the report. Check the claimed tests, that changed files stay within the owned files, that the worktree is clean and committed (`git -C <path> status --porcelain`), overlap with other unmerged branches, and any warning the worker raised. Execute-a-plan work is reviewed against the plan. Tell Mattia in a few lines: what changed, tests, caveats, what to look at by eye, a recommendation.

## Merge

A yes naming the branches ("merge all three") counts once you have reviewed them and nothing alarms you; dirty main, red checks or out-of-boundary conflicts mean stop and ask. A yes to merge is never a yes to push. One branch at a time, in his order unless dependencies force another, else the larger first. Wait (`t3_thread_wait`) until the worker's thread is idle before touching its branch; never interrupt it.

1. **Preconditions, every time:** main checkout on `<defaultBranch>`, no merge or rebase in progress, `git status --porcelain --untracked-files=no` empty (untracked handoff docs are fine). Otherwise ask whether to commit or stash; once he says which, do it and tell him (restoring a stash is his call).
2. Note `git rev-parse <defaultBranch>`, then `git merge --no-ff <branch>`.
3. **Conflicts:** `git merge --abort` first (never leave main half-merged). Then **you** resolve them in the worker's idle, clean worktree: merge `<defaultBranch>` into the branch, resolve only the conflicting hunks keeping both sides' intent, rerun the project's checks, commit, retry. Unclear intent, or files outside the task's boundaries: stop and ask.
4. **Verify** the merged result with the project's own declared commands (package.json scripts via its lockfile's manager, pytest, Makefile `test`), typecheck and lint before tests. Never invent a command; no harness means say it is unverified and ask before Done. Record command and exit code.
5. **Green:** set the issue Done, then tell the others to rebase (below). **Red:** undo only this merge with `git revert -m 1 HEAD` (never `reset --hard` or other workarounds), set the issue back to In Review or blocked with a comment, tell Mattia. Never leave `<defaultBranch>` red for others to branch from. To merge a reverted branch again, first revert the revert. Still red after the revert: stop, tell him, and find the culprit among recent merges before merging more.
6. Only then the next branch.

## Rebase notice (after each merge verified green)

For every active worker with an unmerged branch (running or idle), `t3_thread_send` with mode `queue` (lands after their current turn): "`<defaultBranch>` moved: `<ISSUE>` is merged. When your current step is committed, rebase onto `<defaultBranch>`, rerun your checks and report. If the rebase conflicts, abort it and report; do not resolve it." Their conflicts are yours at merge time (step 3). Launch no worker from `<defaultBranch>` until the merge is verified green.

## Push

Merge and verify everything locally, then **ask**: `git fetch origin`, show `git log origin/<defaultBranch>..<defaultBranch>`, push once with `git push origin <defaultBranch>` (never `--force`). Rejected or origin moved: merge or rebase locally, re-verify, show the revised set, ask again. Timeout: fetch and inspect before retrying. Nothing else goes to the network (no feature branches, no PRs) unless he asks for a PR.

## Clean up and settle

After the whole task is merged and verified, in the same step as the tracker update:
- **Worktree:** `git worktree remove <path>` (no `--force`), then `git branch -d <branch>`; no remote branches exist. Uncommitted changes: leave it and tell Mattia. Directory in use (a parked thread; normal on Windows): settle the threads, retry once, then tell him the folder is a leftover to delete after the thread is closed.
- **Settle threads** so they leave his sidebar: `t3_thread_organize {"action":"settle","threadId":"<id>"}` (reversible with `unsettle`; archive only if he asks), and tell him which. Implement, fix and execute threads: when the task is merged, verified and Done. Design and guide threads: once the execution thread is launched from their plan (or the design is dropped). Review and investigate threads: once the report is recorded and acted on. **Never** settle a thread that is running, has a pending request, has an unrecorded report, or has an unmerged branch.

## Deploy

Only when asked, with the project's documented procedure, from the clean main checkout; long steps in the background. Verify health and report the version.
