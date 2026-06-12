import os
import tempfile
import unittest

from orch import db, report


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")
        self.tid = db.add_task(self.conn, "demo", "A", "x",
                               status="discussing")

    def _task(self):
        return self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (self.tid,)).fetchone()

    def test_note_posts_note_without_status_change(self):
        report.report(self.conn, "demo", "A", "note", msg="hi")
        ev = self.conn.execute(
            "SELECT kind, message FROM events ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(ev["kind"], "note")
        self.assertEqual(self._task()["status"], "discussing")

    def test_executing_updates_task(self):
        report.report(self.conn, "demo", "A", "executing", msg="go")
        self.assertEqual(self._task()["status"], "executing")

    def test_done_with_explicit_branch(self):
        report.report(self.conn, "demo", "A", "done", branch="feat/x")
        self.assertEqual(self._task()["status"], "done")
        self.assertEqual(self._task()["branch"], "feat/x")

    def test_done_autodetects_branch(self):
        orig = report.current_branch
        report.current_branch = lambda cwd=None: "auto/branch"
        try:
            report.report(self.conn, "demo", "A", "done")
        finally:
            report.current_branch = orig
        self.assertEqual(self._task()["branch"], "auto/branch")

    def test_blocked_notifies(self):
        calls = []
        report.report(self.conn, "demo", "A", "blocked", msg="stuck",
                      notifier=lambda m, title=None: calls.append((m, title)))
        self.assertEqual(self._task()["status"], "blocked")
        self.assertEqual(len(calls), 1)
        self.assertIn("stuck", calls[0][0])

    def test_current_branch_returns_str_or_none(self):
        b = report.current_branch()
        self.assertTrue(b is None or isinstance(b, str))

    def test_done_autodetect_main_does_not_overwrite_feature_branch(self):
        # Pre-assigned feature branch (the kickoff convention) must survive a
        # `done` reported from a window that happens to sit on main.
        db.update_task(self.conn, self.tid, branch="feat/x")
        orig = report.current_branch
        report.current_branch = lambda cwd=None: "main"
        try:
            report.report(self.conn, "demo", "A", "done")
        finally:
            report.current_branch = orig
        self.assertEqual(self._task()["status"], "done")
        self.assertEqual(self._task()["branch"], "feat/x")

    def test_done_autodetect_main_leaves_branch_unset(self):
        orig = report.current_branch
        report.current_branch = lambda cwd=None: "master"
        try:
            report.report(self.conn, "demo", "A", "done")
        finally:
            report.current_branch = orig
        self.assertEqual(self._task()["status"], "done")
        self.assertIsNone(self._task()["branch"])

    def test_done_explicit_main_branch_is_honored(self):
        # An explicit --branch main is a deliberate choice; respect it.
        report.report(self.conn, "demo", "A", "done", branch="main")
        self.assertEqual(self._task()["branch"], "main")


if __name__ == "__main__":
    unittest.main()
