# Deps Copy-Not-Hardlink Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the cross-worktree `node_modules` corruption risk in `orch deps` by
replacing its hardlink-based fast sync with a plain recursive copy.

**Architecture:** Single-function swap: `orch/deps.py`'s `_hardlink_tree` (hand-rolled
`os.walk` + `os.link`/`os.symlink`) becomes `_copy_tree`, a thin wrapper around stdlib
`shutil.copytree(src, dst, symlinks=True)`. `sync()`'s control flow, return-message
shape, and fallback-to-`npm ci` behavior are unchanged — only the mechanism and its
user-facing wording change, from "link" to "copy".

**Tech Stack:** Python 3.8+ stdlib (`shutil.copytree`), `unittest`.

## Global Constraints

- No new dependencies — stdlib only, matching the rest of `orch/`.
- `sync()`'s public behavior (no-op conditions, return message *shape*, `RuntimeError`
  on `npm ci` failure) is unchanged — only "linked" → "copied" in the success message
  and the underlying mechanism change.
- Every place that currently says "hardlink(s)" in code, tests, or docs is updated to
  "copy/copies" — no stale wording left describing the old mechanism.

---

### Task 1: Replace hardlinking with copying in `orch/deps.py`

**Files:**
- Modify: `orch/deps.py`
- Modify: `tests/test_deps.py`
- Modify: `.claude/skills/work/SKILL.md`
- Modify: `README.md`

**Interfaces:**
- Produces: `_copy_tree(src_root: str, dst_root: str) -> None` in `orch/deps.py`,
  replacing `_hardlink_tree` (same signature, same raise-on-failure contract — callers
  discard the partial `dst_root` and fall back to `npm ci`). No other module calls
  `_hardlink_tree`/`_copy_tree` directly; it's `sync()`'s private helper, matching
  today's structure.

- [ ] **Step 1: Write the failing tests first**

In `tests/test_deps.py`, replace `test_hardlinks_node_modules_when_lockfile_matches`
with:

```python
    def test_copies_node_modules_when_lockfile_matches(self):
        lock = '{"lockfileVersion": 3}'
        self._write(os.path.join(self.root, "package-lock.json"), lock)
        self._write(os.path.join(self.root, "node_modules", "left-pad",
                                  "index.js"), "module.exports = 1;")
        self._write(os.path.join(self.worktree, "package-lock.json"), lock)

        msg = deps.sync(self.conn, "demo", cwd=self.worktree)

        self.assertIn("copied node_modules", msg)
        copied = os.path.join(self.worktree, "node_modules", "left-pad",
                              "index.js")
        self.assertTrue(os.path.isfile(copied))
        with open(copied) as f:
            self.assertEqual(f.read(), "module.exports = 1;")

    def test_copy_is_independent_of_root(self):
        # The whole point of switching from hardlinks to copies: writing
        # into the worktree's copy must never affect the root's file.
        lock = '{"lockfileVersion": 3}'
        self._write(os.path.join(self.root, "package-lock.json"), lock)
        root_file = os.path.join(self.root, "node_modules", "left-pad",
                                 "index.js")
        self._write(root_file, "module.exports = 1;")
        self._write(os.path.join(self.worktree, "package-lock.json"), lock)

        deps.sync(self.conn, "demo", cwd=self.worktree)

        copied = os.path.join(self.worktree, "node_modules", "left-pad",
                              "index.js")
        with open(copied, "w") as f:
            f.write("module.exports = 999; // mutated in the worktree")

        with open(root_file) as f:
            self.assertEqual(f.read(), "module.exports = 1;")
```

Replace `test_falls_back_to_npm_ci_when_hardlink_fails` with:

```python
    def test_falls_back_to_npm_ci_when_copy_fails(self):
        lock = '{"v": 1}'
        self._write(os.path.join(self.root, "package-lock.json"), lock)
        self._write(os.path.join(self.root, "node_modules", "pkg", "a.js"),
                    "x")
        self._write(os.path.join(self.worktree, "package-lock.json"), lock)

        def boom(src, dst):
            raise OSError("disk full")

        orig_copy = deps._copy_tree
        orig_ci = deps._npm_ci
        deps._copy_tree = boom
        deps._npm_ci = lambda cwd: (True, "npm ci completed")
        try:
            msg = deps.sync(self.conn, "demo", cwd=self.worktree)
        finally:
            deps._copy_tree = orig_copy
            deps._npm_ci = orig_ci

        self.assertEqual(msg, "npm ci completed")
```

Leave every other test in the file unchanged.

- [ ] **Step 2: Run the new/changed tests to verify they fail**

Run: `python -m pytest tests/test_deps.py -v`
Expected: `test_copies_node_modules_when_lockfile_matches` FAILs (message still says
"linked node_modules", not "copied node_modules"); `test_copy_is_independent_of_root`
FAILs with an `AttributeError`-free but assertion failure — the current hardlink
implementation means the root file *does* change when the copy is mutated, since it's
the same inode, so `self.assertEqual(f.read(), "module.exports = 1;")` fails, showing
`"module.exports = 999; // mutated in the worktree"` instead; `test_falls_back_to_npm_ci_when_copy_fails`
FAILs with `AttributeError: module 'orch.deps' has no attribute '_copy_tree'`.

- [ ] **Step 3: Replace `_hardlink_tree` with `_copy_tree` in `orch/deps.py`**

Replace the entire `_hardlink_tree` function:

```python
def _hardlink_tree(src_root, dst_root):
    """Recreate src_root at dst_root using hardlinks for files (near-instant,
    no content duplication) and real symlinks for symlinked entries (e.g.
    node_modules/.bin). Raises OSError on failure (e.g. cross-device);
    callers should discard the partial dst_root and fall back to a real
    install."""
    os.makedirs(dst_root, exist_ok=True)
    for dirpath, dirnames, filenames in os.walk(src_root):
        rel = os.path.relpath(dirpath, src_root)
        dst_dir = dst_root if rel == "." else os.path.join(dst_root, rel)
        os.makedirs(dst_dir, exist_ok=True)

        real_dirnames = []
        for name in dirnames:
            src_path = os.path.join(dirpath, name)
            if os.path.islink(src_path):
                os.symlink(os.readlink(src_path), os.path.join(dst_dir, name))
            else:
                real_dirnames.append(name)
        dirnames[:] = real_dirnames

        for name in filenames:
            src_path = os.path.join(dirpath, name)
            dst_path = os.path.join(dst_dir, name)
            if os.path.islink(src_path):
                os.symlink(os.readlink(src_path), dst_path)
            else:
                os.link(src_path, dst_path)
```

with:

```python
def _copy_tree(src_root, dst_root):
    """Recreate src_root at dst_root as a fully independent copy — no shared
    inodes with the source, so nothing written into dst_root's files can
    ever affect src_root's (the reason this isn't a hardlink: some tools,
    e.g. `prisma generate` or `patch-package`, write into existing files
    inside node_modules rather than replacing them). Raises OSError or
    shutil.Error on failure; callers should discard the partial dst_root
    and fall back to a real install."""
    shutil.copytree(src_root, dst_root, symlinks=True)
```

- [ ] **Step 4: Update `sync()`'s docstring, call site, and message text**

Replace:

```python
def sync(conn, project_name, cwd=None):
    """Fast-sync node_modules into `cwd` (a worker's worktree). Hardlinks
    node_modules from the linked project root when its package-lock.json is
    byte-identical to this one (near-instant); otherwise runs a real
    `npm ci` here. No-op if this isn't an npm project, or node_modules is
    already present (idempotent across resumed cycles)."""
```

with:

```python
def sync(conn, project_name, cwd=None):
    """Fast-sync node_modules into `cwd` (a worker's worktree). Copies
    node_modules from the linked project root when its package-lock.json is
    byte-identical to this one (no network, no reinstall — just a local
    file copy, fully independent of the root so nothing written into it
    later can corrupt the shared root or any other worktree); otherwise
    runs a real `npm ci` here. No-op if this isn't an npm project, or
    node_modules is already present (idempotent across resumed cycles)."""
```

Replace:

```python
    if can_link:
        try:
            _hardlink_tree(src_modules, dst_modules)
            return f"linked node_modules from {root} (lockfile match)"
        except OSError:
            shutil.rmtree(dst_modules, ignore_errors=True)
```

with:

```python
    if can_link:
        try:
            _copy_tree(src_modules, dst_modules)
            return f"copied node_modules from {root} (lockfile match)"
        except (OSError, shutil.Error):
            shutil.rmtree(dst_modules, ignore_errors=True)
```

(The `can_link` variable itself is unchanged — renaming it isn't necessary for
correctness and is out of scope for this task.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_deps.py -v`
Expected: all tests in the file PASS, including
`test_copies_node_modules_when_lockfile_matches`,
`test_copy_is_independent_of_root`, and `test_falls_back_to_npm_ci_when_copy_fails`.

- [ ] **Step 6: Update `work/SKILL.md`'s deps wording**

Replace:

```markdown
   - **Sync dependencies fast:** `python <path>/orch.py deps`. Hardlinks `node_modules`
     from the project root when the lockfile matches (near-instant); otherwise runs a
     real `npm ci`. Safe to call every cycle — it no-ops if `node_modules` is already
     here (resumed task) or this isn't an npm project.
```

with:

```markdown
   - **Sync dependencies fast:** `python <path>/orch.py deps`. Copies `node_modules`
     from the project root when the lockfile matches (no network, no reinstall — just a
     local file copy, independent of the root so nothing this worktree does to it can
     affect anyone else's); otherwise runs a real `npm ci`. Safe to call every cycle —
     it no-ops if `node_modules` is already here (resumed task) or this isn't an npm
     project.
```

- [ ] **Step 7: Update `README.md`'s `deps` command-table entry**

Replace:

```markdown
| `deps` | fast-sync `node_modules` into the current worktree: hardlinks from the linked project root when `package-lock.json` matches (near-instant), else runs `npm ci`; no-op if not an npm project or `node_modules` is already present |
```

with:

```markdown
| `deps` | fast-sync `node_modules` into the current worktree: copies from the linked project root when `package-lock.json` matches (no network, no reinstall — a fully independent copy, not a hardlink), else runs `npm ci`; no-op if not an npm project or `node_modules` is already present |
```

- [ ] **Step 8: Run the full suite to confirm no regressions**

Run: `python -m pytest -q`
Expected: all tests pass (same total count as before this task — this task renames
tests, it doesn't add or remove any).

- [ ] **Step 9: Commit**

```bash
git add orch/deps.py tests/test_deps.py .claude/skills/work/SKILL.md README.md
git commit -m "$(cat <<'EOF'
fix(deps): copy node_modules instead of hardlinking it

Hardlinked files share an inode across the root and every worktree that
linked it — anything that writes into an existing file inside
node_modules (prisma generate, patch-package, some postinstall scripts)
silently corrupts the shared root and every other worktree. A plain copy
(shutil.copytree) makes each worktree's node_modules fully independent,
closing the whole risk category instead of chasing known-risky tooling
case by case. Still far faster than a cold npm ci (no network, no
extraction, no postinstall re-run) even though it's slower than a
hardlink and uses more disk.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes (from the plan author, not a task to execute)

- **Spec coverage:** the design's four sections (drop hardlinking, keep the fallback
  contract, update wording, update tests) are all covered by this single task — the
  spec itself is small enough not to need more than one.
- **Type/name consistency:** `_copy_tree(src_root, dst_root)` has the exact same
  signature and raise-on-failure contract as the `_hardlink_tree` it replaces, so
  `sync()`'s surrounding try/except needs no other changes.
- **Placeholder scan:** no TBD/TODO; every step shows exact code or exact text.
- **Out-of-scope reminder:** the design doc explicitly excludes filesystem-level
  copy-on-write clones and an opt-in hardlink toggle — neither appears in this plan,
  correctly.
