import os
import tempfile
import unittest

from orch import db, deps


class DepsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")
        self.root = os.path.join(self.tmp, "root")
        self.worktree = os.path.join(self.tmp, "worktree")
        os.makedirs(self.root)
        os.makedirs(self.worktree)
        db.set_project_path(self.conn, "demo", self.root)

    def _write(self, path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    def test_noop_without_lockfile(self):
        msg = deps.sync(self.conn, "demo", cwd=self.worktree)
        self.assertIn("no package-lock.json", msg)

    def test_noop_when_node_modules_already_present(self):
        self._write(os.path.join(self.worktree, "package-lock.json"), "{}")
        os.makedirs(os.path.join(self.worktree, "node_modules"))
        msg = deps.sync(self.conn, "demo", cwd=self.worktree)
        self.assertIn("already present", msg)

    def test_noop_at_project_root(self):
        self._write(os.path.join(self.root, "package-lock.json"), "{}")
        msg = deps.sync(self.conn, "demo", cwd=self.root)
        self.assertIn("project root", msg)

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

    def test_falls_back_to_npm_ci_when_lockfile_differs(self):
        self._write(os.path.join(self.root, "package-lock.json"), '{"v": 1}')
        self._write(os.path.join(self.root, "node_modules", "pkg", "a.js"),
                    "x")
        self._write(os.path.join(self.worktree, "package-lock.json"),
                    '{"v": 2}')

        calls = []
        orig = deps._npm_ci
        deps._npm_ci = lambda cwd: (calls.append(cwd) or (True, "npm ci completed"))
        try:
            msg = deps.sync(self.conn, "demo", cwd=self.worktree)
        finally:
            deps._npm_ci = orig

        self.assertEqual(calls, [self.worktree])
        self.assertIn("npm ci completed", msg)
        self.assertFalse(
            os.path.exists(os.path.join(self.worktree, "node_modules")))

    def test_falls_back_to_npm_ci_when_no_root_node_modules(self):
        lock = '{"v": 1}'
        self._write(os.path.join(self.root, "package-lock.json"), lock)
        self._write(os.path.join(self.worktree, "package-lock.json"), lock)

        calls = []
        orig = deps._npm_ci
        deps._npm_ci = lambda cwd: (calls.append(cwd) or (True, "npm ci completed"))
        try:
            msg = deps.sync(self.conn, "demo", cwd=self.worktree)
        finally:
            deps._npm_ci = orig

        self.assertEqual(calls, [self.worktree])
        self.assertIn("npm ci completed", msg)

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

        self.assertIn("npm ci completed", msg)

    def test_raises_when_npm_ci_fails(self):
        self._write(os.path.join(self.worktree, "package-lock.json"), "{}")

        orig = deps._npm_ci
        deps._npm_ci = lambda cwd: (False, "npm ci failed:\nboom")
        try:
            with self.assertRaises(RuntimeError):
                deps.sync(self.conn, "demo", cwd=self.worktree)
        finally:
            deps._npm_ci = orig

    def test_no_linked_path_falls_back_to_npm_ci(self):
        db.create_project(self.conn, "unlinked")
        self._write(os.path.join(self.worktree, "package-lock.json"), "{}")

        orig = deps._npm_ci
        deps._npm_ci = lambda cwd: (True, "npm ci completed")
        try:
            msg = deps.sync(self.conn, "unlinked", cwd=self.worktree)
        finally:
            deps._npm_ci = orig
        self.assertIn("npm ci completed", msg)

    # --- nested npm projects (package.json not at the repo root) ---

    def test_copies_node_modules_for_every_nested_project(self):
        # Repo with tooling deps at the root AND the real app in app/.
        # Both must land in the worktree, not just the root one.
        root_lock = '{"lockfileVersion": 3, "name": "tooling"}'
        app_lock = '{"lockfileVersion": 3, "name": "app"}'
        self._write(os.path.join(self.root, "package-lock.json"), root_lock)
        self._write(os.path.join(self.root, "node_modules", "eslint",
                                 "index.js"), "tooling")
        self._write(os.path.join(self.root, "app", "package-lock.json"),
                    app_lock)
        self._write(os.path.join(self.root, "app", "node_modules", "next",
                                 "index.js"), "app dep")
        self._write(os.path.join(self.worktree, "package-lock.json"), root_lock)
        self._write(os.path.join(self.worktree, "app", "package-lock.json"),
                    app_lock)

        msg = deps.sync(self.conn, "demo", cwd=self.worktree)

        self.assertTrue(os.path.isfile(os.path.join(
            self.worktree, "node_modules", "eslint", "index.js")), msg)
        self.assertTrue(os.path.isfile(os.path.join(
            self.worktree, "app", "node_modules", "next", "index.js")), msg)

    def test_syncs_nested_project_when_repo_root_has_no_lockfile(self):
        # package.json lives only in app/ — the root isn't an npm project.
        lock = '{"lockfileVersion": 3}'
        self._write(os.path.join(self.root, "app", "package-lock.json"), lock)
        self._write(os.path.join(self.root, "app", "node_modules", "next",
                                 "index.js"), "app dep")
        self._write(os.path.join(self.worktree, "app", "package-lock.json"),
                    lock)

        msg = deps.sync(self.conn, "demo", cwd=self.worktree)

        self.assertTrue(os.path.isfile(os.path.join(
            self.worktree, "app", "node_modules", "next", "index.js")), msg)

    def test_nested_project_falls_back_to_npm_ci_on_its_own(self):
        # Root lockfile matches (copy), app/ lockfile differs (npm ci there).
        root_lock = '{"v": 1}'
        self._write(os.path.join(self.root, "package-lock.json"), root_lock)
        self._write(os.path.join(self.root, "node_modules", "eslint", "a.js"),
                    "x")
        self._write(os.path.join(self.root, "app", "package-lock.json"),
                    '{"v": 1}')
        self._write(os.path.join(self.root, "app", "node_modules", "next",
                                 "a.js"), "x")
        self._write(os.path.join(self.worktree, "package-lock.json"), root_lock)
        self._write(os.path.join(self.worktree, "app", "package-lock.json"),
                    '{"v": 2}')

        calls = []
        orig = deps._npm_ci
        deps._npm_ci = lambda cwd: (calls.append(cwd) or (True, "npm ci completed"))
        try:
            deps.sync(self.conn, "demo", cwd=self.worktree)
        finally:
            deps._npm_ci = orig

        self.assertEqual(calls, [os.path.join(self.worktree, "app")])
        self.assertTrue(os.path.isfile(os.path.join(
            self.worktree, "node_modules", "eslint", "a.js")))

    def test_ignores_lockfiles_inside_node_modules(self):
        # A dependency's own lockfile is not a project to sync.
        lock = '{"v": 1}'
        self._write(os.path.join(self.worktree, "package-lock.json"), lock)
        self._write(os.path.join(self.worktree, "node_modules", "pkg",
                                 "package-lock.json"), '{"v": 9}')

        calls = []
        orig = deps._npm_ci
        deps._npm_ci = lambda cwd: (calls.append(cwd) or (True, "npm ci completed"))
        try:
            msg = deps.sync(self.conn, "demo", cwd=self.worktree)
        finally:
            deps._npm_ci = orig

        self.assertEqual(calls, [])
        self.assertIn("already present", msg)

    def test_one_failing_project_still_syncs_the_others(self):
        lock = '{"v": 1}'
        self._write(os.path.join(self.root, "package-lock.json"), lock)
        self._write(os.path.join(self.root, "node_modules", "eslint", "a.js"),
                    "x")
        self._write(os.path.join(self.worktree, "package-lock.json"), lock)
        self._write(os.path.join(self.worktree, "app", "package-lock.json"),
                    '{"v": 2}')

        orig = deps._npm_ci
        deps._npm_ci = lambda cwd: (False, "npm ci failed:\nboom")
        try:
            with self.assertRaises(RuntimeError) as ctx:
                deps.sync(self.conn, "demo", cwd=self.worktree)
        finally:
            deps._npm_ci = orig

        self.assertIn("app", str(ctx.exception))
        self.assertTrue(os.path.isfile(os.path.join(
            self.worktree, "node_modules", "eslint", "a.js")))


if __name__ == "__main__":
    unittest.main()
