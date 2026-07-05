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

    def test_hardlinks_node_modules_when_lockfile_matches(self):
        lock = '{"lockfileVersion": 3}'
        self._write(os.path.join(self.root, "package-lock.json"), lock)
        self._write(os.path.join(self.root, "node_modules", "left-pad",
                                  "index.js"), "module.exports = 1;")
        self._write(os.path.join(self.worktree, "package-lock.json"), lock)

        msg = deps.sync(self.conn, "demo", cwd=self.worktree)

        self.assertIn("linked node_modules", msg)
        linked = os.path.join(self.worktree, "node_modules", "left-pad",
                              "index.js")
        self.assertTrue(os.path.isfile(linked))
        with open(linked) as f:
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
        self.assertEqual(msg, "npm ci completed")
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
        self.assertEqual(msg, "npm ci completed")

    def test_falls_back_to_npm_ci_when_hardlink_fails(self):
        lock = '{"v": 1}'
        self._write(os.path.join(self.root, "package-lock.json"), lock)
        self._write(os.path.join(self.root, "node_modules", "pkg", "a.js"),
                    "x")
        self._write(os.path.join(self.worktree, "package-lock.json"), lock)

        def boom(src, dst):
            raise OSError("cross-device link")

        orig_link = deps._hardlink_tree
        orig_ci = deps._npm_ci
        deps._hardlink_tree = boom
        deps._npm_ci = lambda cwd: (True, "npm ci completed")
        try:
            msg = deps.sync(self.conn, "demo", cwd=self.worktree)
        finally:
            deps._hardlink_tree = orig_link
            deps._npm_ci = orig_ci

        self.assertEqual(msg, "npm ci completed")

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
        self.assertEqual(msg, "npm ci completed")


if __name__ == "__main__":
    unittest.main()
