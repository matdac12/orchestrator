import os
import tempfile
import unittest

from orch import db, progress


class RecordTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")
        self.tid = db.add_task(self.conn, "demo", "A", "x",
                               status="executing")

    def test_records_a_progress_event(self):
        out = progress.record(self.conn, "demo", "A", "implementation",
                              message="wiring the CLI", step=2, step_total=5,
                              next_step="status output")
        self.assertTrue(out["recorded"])
        self.assertEqual(out["task_id"], self.tid)
        p = db.latest_progress(self.conn, self.tid)
        self.assertEqual(p["phase"], "implementation")
        self.assertEqual(p["step"], 2)
        self.assertEqual(p["next_step"], "status output")

    def test_does_not_touch_status_or_needs_human(self):
        progress.record(self.conn, "demo", "A", "checkpoint",
                        message="codex review")
        row = self.conn.execute(
            "SELECT status, needs_human FROM tasks WHERE id = ?",
            (self.tid,)).fetchone()
        self.assertEqual(row["status"], "executing")
        self.assertEqual(row["needs_human"], 0)

    def test_unknown_phase_rejected_and_lists_valid_ones(self):
        with self.assertRaises(ValueError) as ctx:
            progress.record(self.conn, "demo", "A", "deploying")
        self.assertIn("implementation", str(ctx.exception))

    def test_step_without_total_rejected(self):
        with self.assertRaises(ValueError):
            progress.record(self.conn, "demo", "A", "implementation", step=2)

    def test_total_without_step_rejected(self):
        with self.assertRaises(ValueError):
            progress.record(self.conn, "demo", "A", "implementation",
                            step_total=5)

    def test_step_below_one_rejected(self):
        with self.assertRaises(ValueError):
            progress.record(self.conn, "demo", "A", "implementation",
                            step=0, step_total=5)

    def test_step_past_total_rejected(self):
        with self.assertRaises(ValueError):
            progress.record(self.conn, "demo", "A", "implementation",
                            step=6, step_total=5)

    def test_long_message_is_truncated_not_rejected(self):
        out = progress.record(self.conn, "demo", "A", "implementation",
                              message="x" * 500)
        self.assertTrue(out["truncated"])
        self.assertEqual(len(out["message"]), progress.MAX_MESSAGE)

    def test_identical_consecutive_report_is_a_no_op(self):
        args = ("demo", "A", "implementation")
        kw = {"message": "same", "step": 1, "step_total": 3}
        progress.record(self.conn, *args, **kw)
        out = progress.record(self.conn, *args, **kw)
        self.assertFalse(out["recorded"])
        count = self.conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 'progress'"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_changed_report_records_again(self):
        progress.record(self.conn, "demo", "A", "implementation",
                        message="one", step=1, step_total=3)
        out = progress.record(self.conn, "demo", "A", "implementation",
                              message="two", step=2, step_total=3)
        self.assertTrue(out["recorded"])

    def test_done_task_is_refused(self):
        db.update_task(self.conn, self.tid, status="done")
        with self.assertRaises(ValueError) as ctx:
            progress.record(self.conn, "demo", "A", "checkpoint",
                            task_id=self.tid)
        self.assertIn("orch report", str(ctx.exception))

    def test_blocked_task_is_allowed(self):
        db.update_task(self.conn, self.tid, status="blocked")
        out = progress.record(self.conn, "demo", "A", "blocked",
                              message="missing credentials")
        self.assertTrue(out["recorded"])

    def test_no_active_task_raises_rather_than_orphaning(self):
        with self.assertRaises(db.NotFound):
            progress.record(self.conn, "demo", "Z", "setup")
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM events").fetchone()[0], 0)


class FormatLineTest(unittest.TestCase):
    def test_with_steps_and_message(self):
        self.assertEqual(
            progress.format_line({"phase": "implementation", "step": 3,
                                  "step_total": 6, "message": "the CLI"}),
            "implementation 3/6 · the CLI")

    def test_without_steps(self):
        self.assertEqual(
            progress.format_line({"phase": "planning", "step": None,
                                  "step_total": None, "message": "drafting"}),
            "planning · drafting")

    def test_empty_snapshot(self):
        self.assertEqual(progress.format_line(None), "")


if __name__ == "__main__":
    unittest.main()
