# Review, merge, push, clean up

## Review

When a worker reports, read the real diff (`git diff <defaultBranch>...<branch>`, `git log`), not the report. Check: tests claimed, file list within the owned files, worktree clean and committed (`git -C <path> status --porcelain`), no overlap with other unmerged branches, any warning the worker raised. For execute-a-plan work, review against the plan. Tell Mattia in a few lines: what changed, tests, caveats, what to look at by eye, a recommendation.

## Merge (only on his yes, one branch at a time)

A yes that names the branches ("merge all three") counts, once you have reviewed them and nothing alarms you; anything below that stops you (dirty main, red checks, out-of-boundary conflicts) means stop and ask. A yes to merge is never a yes to push. Merge in the order he gave unless dependencies force another, otherwise the larger branch first. Wait (`t3_thread_wait`) for the worker's thread to be idle before touching its branch; never interrupt it.

1. **Preconditions, every time:** main checkout is on `<defaultBranch>`, no merge or rebase in progress, `git status --porcelain --untracked-files=no` empty (untracked handoff docs are fine). If not, ask Mattia whether to commit or stash; once he says which, do it and tell him (restoring a stash is his call).
2. Note `git rev-parse <defaultBranch>`. Merge: `git merge --no-ff <branch>`.
3. **Conflicts:** `git merge --abort` in the main checkout (never leave it half-merged). Then **you** resolve them in the worker's worktree once its thread is idle and its tree clean: merge `<defaultBranch>` into the branch, resolve only the conflicting hunks keeping both sides' intent, rerun the project's checks, commit, retry. If intent is unclear or it touches files outside the task's boundaries, stop and ask Mattia.
4. **Verify the merged result** with the project's own declared commands (package.json scripts with its lockfile's manager, pytest, Makefile `test`): typecheck and lint before tests. Never invent a command. No harness: say it is unverified and ask before Done. Record the command and exit code.
5. **Green:** set the issue Done. **Red:** undo only this merge with `git revert -m 1 HEAD` (non-destructive; never `reset --hard` or other workarounds), set the issue back to In Review or blocked with a comment, tell Mattia. Never leave `<defaultBranch>` red for others to branch from. To merge a reverted branch again, first `git revert` the revert commit. If `<defaultBranch>` is still red after the revert, stop and tell Mattia; find the culprit among the recent merges before merging anything else.
6. **Merge the next branch only after this one is verified green.** Merge dependent branches in dependency order, otherwise the larger first.

## After each merge verified green: tell the others to rebase

Only once the merge is verified green (never before a possible revert). For every still-active worker whose branch is unmerged (running or idle), send with `t3_thread_send` (mode `queue`, so it lands after their current turn): "`<defaultBranch>` moved: `<ISSUE>` is merged. When your current step is committed, rebase your branch onto `<defaultBranch>`, rerun your checks, and report. If the rebase conflicts, abort it and report; do not resolve it." Conflicts they report are yours to resolve at merge time (step 3). Launch no new worker from `<defaultBranch>` until the merge is verified green.

## Push

Merge and verify everything locally first, then **ask Mattia**: `git fetch origin`, show `git log origin/<defaultBranch>..<defaultBranch>`, and push once with `git push origin <defaultBranch>` (never `--force`). If origin moved or the push is rejected: merge or rebase the new commits locally, re-verify, show the revised set, ask again. Ambiguous failure (timeout): fetch and inspect before retrying. Nothing else goes to the network (no feature branches, no PRs) unless Mattia asks for a PR.

## Clean up

After the whole task is merged and verified: `git worktree remove <path>` (no `--force`), then `git branch -d <branch>`. If it fails for uncommitted changes, leave it and tell Mattia; if the directory is in use (a thread parked there; normal on Windows), settle its threads, retry once, and if it is still in use tell Mattia the folder is a leftover for him to delete once the thread is closed. Branches were never pushed, so there are no remote branches to delete.

## Settle threads

Mattia does not want finished threads cluttering his sidebar, so you settle them yourself: `t3_thread_organize {"action":"settle","threadId":"<id>"}` (reversible with `unsettle`; archive only if he asks). Settle a thread when its job is over and nothing is left in it:
- **Implement / fix / execute threads and the whole task:** once the task is merged, verified and its issue is Done.
- **Design and guide threads:** once the execution thread has been launched from their plan (or he says the design is dropped).
- **Review and investigate threads:** once the report is recorded in the tracker and acted on.
- **Never settle** a thread that is running, has a pending request (`t3_pending_request_list`), has an unrecorded report, or whose branch is unmerged. Settling does not touch the worktree; clean that up separately.

Do it in the same step as the tracker update, and tell Mattia in a line which threads you settled.

## Deploy

Only when Mattia asks, with the project's documented procedure, from the clean main checkout; long steps in the background. Verify health and report the version afterwards.
