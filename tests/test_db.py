import os
import sqlite3
import tempfile
import unittest

from orch import db


class DBSetupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "state.db")

    def test_default_db_path_uses_env(self):
        os.environ["ORCH_DB"] = "/custom/x.db"
        try:
            self.assertEqual(db.default_db_path(), "/custom/x.db")
        finally:
            del os.environ["ORCH_DB"]

    def test_connect_creates_schema_and_wal(self):
        conn = db.connect(self.path)
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual({"projects", "tasks", "events"}, names)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual("wal", mode.lower())


class RetryTest(unittest.TestCase):
    def test_with_retry_recovers_from_locked(self):
        calls = {"n": 0}

        def action():
            calls["n"] += 1
            if calls["n"] < 3:
                raise sqlite3.OperationalError("database is locked")
            return "ok"

        self.assertEqual(db.with_retry(action, base_delay=0.0), "ok")
        self.assertEqual(calls["n"], 3)

    def test_with_retry_reraises_other_errors(self):
        def action():
            raise sqlite3.OperationalError("no such table")

        with self.assertRaises(sqlite3.OperationalError):
            db.with_retry(action, base_delay=0.0)


class ProjectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))

    def test_create_is_get_or_create(self):
        pid1, created1 = db.create_project(self.conn, "demo", notes="hi")
        pid2, created2 = db.create_project(self.conn, "demo")
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(pid1, pid2)

    def test_get_project_returns_none_when_missing(self):
        self.assertIsNone(db.get_project(self.conn, "nope"))
        db.create_project(self.conn, "demo")
        row = db.get_project(self.conn, "demo")
        self.assertEqual(row["name"], "demo")

    def test_require_project_raises_when_missing(self):
        with self.assertRaises(db.NotFound):
            db.require_project(self.conn, "nope")


class TaskTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")

    def test_add_task_returns_id_and_defaults_todo(self):
        tid = db.add_task(self.conn, "demo", "B", "build X", issue_ref="LIN-1")
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()
        self.assertEqual(row["status"], "todo")
        self.assertEqual(row["agent"], "B")
        self.assertEqual(row["issue_ref"], "LIN-1")

    def test_update_task_changes_fields_and_touches_updated_at(self):
        tid = db.add_task(self.conn, "demo", "B", "build X")
        before = self.conn.execute(
            "SELECT updated_at FROM tasks WHERE id=?", (tid,)).fetchone()[0]
        db.update_task(self.conn, tid, status="merged", branch="feat/x")
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        self.assertEqual(row["status"], "merged")
        self.assertEqual(row["branch"], "feat/x")
        self.assertNotEqual(row["updated_at"], before)

    def test_update_task_rejects_bad_status(self):
        tid = db.add_task(self.conn, "demo", "B", "build X")
        with self.assertRaises(ValueError):
            db.update_task(self.conn, tid, status="nonsense")

    def test_update_task_missing_id_raises(self):
        with self.assertRaises(db.NotFound):
            db.update_task(self.conn, 999, status="done")


class PostTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")

    def test_post_appends_event(self):
        tid = db.add_task(self.conn, "demo", "B", "build X")
        eid = db.post_event(self.conn, "demo", "B", kind="note",
                            message="hi", task_id=tid)
        row = self.conn.execute(
            "SELECT * FROM events WHERE id=?", (eid,)).fetchone()
        self.assertEqual(row["message"], "hi")
        self.assertEqual(row["kind"], "note")
        self.assertEqual(row["task_id"], tid)

    def test_post_with_status_updates_linked_task(self):
        tid = db.add_task(self.conn, "demo", "B", "build X")
        db.post_event(self.conn, "demo", "B", status="done",
                     branch="feat/x", message="ready")
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["branch"], "feat/x")

    def test_post_auto_targets_single_active_task(self):
        tid = db.add_task(self.conn, "demo", "B", "build X")
        eid = db.post_event(self.conn, "demo", "B", message="working")
        row = self.conn.execute(
            "SELECT task_id FROM events WHERE id=?", (eid,)).fetchone()
        self.assertEqual(row["task_id"], tid)

    def test_post_ambiguous_active_tasks_without_status(self):
        db.add_task(self.conn, "demo", "B", "task1")
        db.add_task(self.conn, "demo", "B", "task2")
        # ambiguous only matters when we must pick a task to update;
        # a plain note with no task and no status is allowed (task_id None)
        eid = db.post_event(self.conn, "demo", "B", message="generic")
        row = self.conn.execute(
            "SELECT task_id FROM events WHERE id=?", (eid,)).fetchone()
        self.assertIsNone(row["task_id"])

    def test_post_status_ambiguous_raises(self):
        db.add_task(self.conn, "demo", "B", "task1")
        db.add_task(self.conn, "demo", "B", "task2")
        with self.assertRaises(db.Ambiguous):
            db.post_event(self.conn, "demo", "B", status="done")


if __name__ == "__main__":
    unittest.main()
