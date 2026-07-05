# `orch deps`: copy instead of hardlink

## Problem

`orch/deps.py`'s fast path hardlinks `node_modules` from the linked project root into
each worktree when the lockfile matches. Hardlinked files share the same inode across
the root and every worktree that linked it. Anything that writes *into* an existing
file inside `node_modules` — rather than deleting and recreating it, which is what
`npm install`/`npm ci` normally do — mutates that shared inode, corrupting the root's
"canonical" copy and every other worktree that already linked it. This isn't
hypothetical: `prisma generate` writes into `node_modules/.prisma/client`,
`patch-package` patches files in place, and some postinstall/build caches behave the
same way. The original design accepted this as a documented risk; a multi-agent review
found it underestimated — real, common tooling triggers it, not just edge cases.

## Design

Replace hardlinking with a plain recursive copy (`shutil.copytree(src, dst,
symlinks=True)`), when the lockfile matches. Each worktree's `node_modules` becomes
fully independent of the root's and of every other worktree's — no shared inode exists,
so nothing any tool does inside one worktree's copy can ever affect another. This
closes the entire risk category rather than mitigating known cases (Prisma,
patch-package, ...) while leaving unknown ones exposed.

**Speed trade-off, accepted:** a copy duplicates bytes on disk and takes longer than a
hardlink (which only creates directory entries). It remains far faster than a cold
`npm ci`, though, since it's a local file copy with no network round-trip, no tarball
extraction, and no postinstall script re-execution — the dominant costs of a real
install. Disk usage per worktree grows (no shared blocks), which is an acceptable cost
given "usually npm, single `package.json`" workloads, not large monorepos.

**Code impact:** this is a simplification, not just a swap. The current hand-rolled
`_hardlink_tree` (`orch/deps.py`) walks the tree manually, distinguishing files,
directories, and symlinks to hardlink or recreate each correctly (~30 lines). Python's
stdlib `shutil.copytree(src, dst, symlinks=True)` already does exactly this — copy
files, recreate directories, preserve symlinks as symlinks rather than following them —
in one call. The function is renamed `_copy_tree` (kept as a thin, separately-callable
wrapper so existing tests can still monkeypatch it to simulate failure) and its body
shrinks to essentially one line plus the failure-cleanup contract it already had:
raise on failure, let the caller (`sync()`) catch it, discard the partial `dst`, and
fall back to `npm ci` — unchanged from today, now catching `shutil.Error` alongside
`OSError` (`copytree` raises `shutil.Error`, an aggregate of per-file failures, not
always a plain `OSError`).

**User-facing wording:** every place that currently says "hardlink(s)" — `deps.py`'s
returned message, `work/SKILL.md`'s deps bullet, the README's `deps` command-table
entry — changes to "cop(y/ies)", with the near-instant framing softened to "fast — no
network, no reinstall" rather than implying it's as cheap as a hardlink.

**Testing:** the existing hardlink-path test (`test_hardlinks_node_modules_when_lockfile_matches`)
is renamed and adjusted to assert a copy happened (same content-matches assertion as
today). A new regression test proves the actual fix: write new content into the
*worktree's* copy of a file after `sync()`, then assert the *root's* copy of that same
file is unchanged — demonstrating no shared inode exists. The existing
"hardlink fails partway → falls back to npm ci" test is retargeted at `_copy_tree`
under the same name/behavior (a failure during copy still discards the partial `dst`
and falls back).

## Out of scope

- Filesystem-level copy-on-write clones (e.g. Linux `FICLONE`, macOS `clonefile()`,
  which would give hardlink-speed with copy-safety on filesystems that support it) —
  no stdlib primitive, and the target environment (Windows/NTFS) doesn't support it
  transparently. Worth a future look if this ever runs on a COW-capable filesystem, not
  built now.
- An opt-in "I know my stack never writes into `node_modules`, use the old hardlink
  behavior" toggle — not requested, and adds a footgun back in for a marginal speed
  gain; YAGNI.

## Testing

- `tests/test_deps.py`: rename/adjust the lockfile-match test to assert a copy (not a
  hardlink); add the source-independence regression test described above; retarget the
  partial-failure fallback test at `_copy_tree`.
- Full suite must stay green.
