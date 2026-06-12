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
        cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)")}
        self.assertTrue({"context", "plan_path"}.issubset(cols))


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

    def test_add_task_defaults_queued_and_stores_context(self):
        tid = db.add_task(self.conn, "demo", "B", "build X",
                          issue_ref="LIN-1", context="do the thing next")
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()
        self.assertEqual(row["status"], "queued")
        self.assertEqual(row["agent"], "B")
        self.assertEqual(row["issue_ref"], "LIN-1")
        self.assertEqual(row["context"], "do the thing next")
        self.assertIsNone(row["plan_path"])

    def test_add_task_accepts_explicit_status(self):
        tid = db.add_task(self.conn, "demo", "B", "x", status="executing")
        row = self.conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (tid,)).fetchone()
        self.assertEqual(row["status"], "executing")

    def test_update_task_changes_fields_and_touches_updated_at(self):
        # Drive db.now() with a deterministic clock so the assertion never
        # depends on wall-clock resolution (coarse on Windows).
        stamps = iter(["2026-01-01T00:00:00", "2026-01-01T00:00:01"])
        orig_now = db.now
        db.now = lambda: next(stamps)
        try:
            tid = db.add_task(self.conn, "demo", "B", "build X")
            before = self.conn.execute(
                "SELECT updated_at FROM tasks WHERE id=?", (tid,)).fetchone()[0]
            db.update_task(self.conn, tid, status="merged", branch="feat/x")
        finally:
            db.now = orig_now
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        self.assertEqual(row["status"], "merged")
        self.assertEqual(row["branch"], "feat/x")
        self.assertNotEqual(row["updated_at"], before)

    def test_update_task_sets_plan_and_context(self):
        tid = db.add_task(self.conn, "demo", "B", "build X")
        db.update_task(self.conn, tid,
                       plan_path="docs/plan.md", context="revised brief")
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        self.assertEqual(row["plan_path"], "docs/plan.md")
        self.assertEqual(row["context"], "revised brief")

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


class NextTaskTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")

    def test_next_task_none_when_empty(self):
        self.assertIsNone(db.next_task(self.conn, "demo", "A"))

    def test_next_task_returns_oldest_active_for_agent(self):
        t1 = db.add_task(self.conn, "demo", "A", "first")
        db.add_task(self.conn, "demo", "A", "second")
        nxt = db.next_task(self.conn, "demo", "A")
        self.assertEqual(nxt["id"], t1)

    def test_next_task_ignores_closed_and_other_agents(self):
        db.add_task(self.conn, "demo", "A", "done one", status="merged")
        db.add_task(self.conn, "demo", "B", "b task")
        self.assertIsNone(db.next_task(self.conn, "demo", "A"))

    def test_next_task_includes_discussing_and_executing(self):
        tid = db.add_task(self.conn, "demo", "A", "x", status="executing")
        nxt = db.next_task(self.conn, "demo", "A")
        self.assertEqual(nxt["id"], tid)
        self.assertEqual(nxt["status"], "executing")


class ClaimTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")

    def test_claim_transitions_oldest_queued(self):
        t1 = db.add_task(self.conn, "demo", "A", "first")
        db.add_task(self.conn, "demo", "A", "second")
        claimed = db.claim_next(self.conn, "demo", "A")
        self.assertEqual(claimed["id"], t1)
        self.assertEqual(claimed["status"], "discussing")
        row = self.conn.execute(
            "SELECT status FROM tasks WHERE id=?", (t1,)).fetchone()
        self.assertEqual(row["status"], "discussing")

    def test_claim_returns_none_when_nothing_queued(self):
        db.add_task(self.conn, "demo", "A", "x", status="executing")
        self.assertIsNone(db.claim_next(self.conn, "demo", "A"))


class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")

    def test_get_state_shape(self):
        tid = db.add_task(self.conn, "demo", "B", "build X")
        db.post_event(self.conn, "demo", "B", status="executing",
                     message="starting")
        state = db.get_state(self.conn, "demo")
        self.assertEqual(state["project"]["name"], "demo")
        self.assertEqual(len(state["tasks"]), 1)
        self.assertEqual(len(state["events"]), 1)
        agents = {a["agent"]: a for a in state["agents"]}
        self.assertIn("B", agents)
        self.assertEqual(agents["B"]["status"], "executing")
        self.assertEqual(agents["B"]["current_task"]["id"], tid)
        self.assertEqual(agents["B"]["last_event"]["message"], "starting")

    def test_get_state_idle_agent_when_all_tasks_closed(self):
        db.add_task(self.conn, "demo", "B", "build X")
        db.post_event(self.conn, "demo", "B", status="merged")
        agents = {a["agent"]: a
                  for a in db.get_state(self.conn, "demo")["agents"]}
        self.assertEqual(agents["B"]["status"], "merged")

    def test_get_state_events_limit(self):
        for i in range(10):
            db.post_event(self.conn, "demo", "B", message=f"e{i}")
        state = db.get_state(self.conn, "demo", events_limit=3)
        self.assertEqual(len(state["events"]), 3)
        self.assertEqual(state["events"][0]["message"], "e9")


if __name__ == "__main__":
    unittest.main()


class StaleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")

    def tearDown(self):
        self.conn.close()

    def _age(self, minutes):
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc)
                - timedelta(minutes=minutes)).isoformat()

    def _backdate_task(self, tid, minutes):
        self.conn.execute("UPDATE tasks SET updated_at = ? WHERE id = ?",
                          (self._age(minutes), tid))
        self.conn.commit()

    def test_quiet_active_task_is_stale(self):
        tid = db.add_task(self.conn, "demo", "A", "build X",
                          status="executing")
        self._backdate_task(tid, 60)
        stale = db.stale_tasks(self.conn, "demo", minutes=30)
        self.assertEqual([t["id"] for t in stale], [tid])

    def test_recent_task_not_stale(self):
        db.add_task(self.conn, "demo", "A", "build X", status="executing")
        self.assertEqual(db.stale_tasks(self.conn, "demo", minutes=30), [])

    def test_recent_event_counts_as_heartbeat(self):
        tid = db.add_task(self.conn, "demo", "A", "build X",
                          status="executing")
        self._backdate_task(tid, 60)
        db.post_event(self.conn, "demo", "A", kind="note", message="alive")
        self.assertEqual(db.stale_tasks(self.conn, "demo", minutes=30), [])

    def test_old_events_do_not_mask_staleness(self):
        tid = db.add_task(self.conn, "demo", "A", "build X",
                          status="executing")
        db.post_event(self.conn, "demo", "A", kind="note", message="old")
        self.conn.execute("UPDATE events SET created_at = ?",
                          (self._age(90),))
        self.conn.commit()
        self._backdate_task(tid, 60)
        stale = db.stale_tasks(self.conn, "demo", minutes=30)
        self.assertEqual([t["id"] for t in stale], [tid])

    def test_done_and_merged_tasks_ignored(self):
        tid = db.add_task(self.conn, "demo", "A", "build X", status="done")
        self._backdate_task(tid, 120)
        self.assertEqual(db.stale_tasks(self.conn, "demo", minutes=30), [])

    def test_other_agents_events_do_not_count(self):
        tid = db.add_task(self.conn, "demo", "A", "build X",
                          status="executing")
        self._backdate_task(tid, 60)
        db.post_event(self.conn, "demo", "B", kind="note", message="hi")
        stale = db.stale_tasks(self.conn, "demo", minutes=30)
        self.assertEqual([t["id"] for t in stale], [tid])


class StaleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")

    def tearDown(self):
        self.conn.close()

    def _age(self, minutes):
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc)
                - timedelta(minutes=minutes)).isoformat()

    def _backdate_task(self, tid, minutes):
        self.conn.execute("UPDATE tasks SET updated_at = ? WHERE id = ?",
                          (self._age(minutes), tid))
        self.conn.commit()

    def test_quiet_active_task_is_stale(self):
        tid = db.add_task(self.conn, "demo", "A", "build X",
                          status="executing")
        self._backdate_task(tid, 60)
        stale = db.stale_tasks(self.conn, "demo", minutes=30)
        self.assertEqual([t["id"] for t in stale], [tid])

    def test_recent_task_not_stale(self):
        db.add_task(self.conn, "demo", "A", "build X", status="executing")
        self.assertEqual(db.stale_tasks(self.conn, "demo", minutes=30), [])

    def test_recent_event_counts_as_heartbeat(self):
        tid = db.add_task(self.conn, "demo", "A", "build X",
                          status="executing")
        self._backdate_task(tid, 60)
        db.post_event(self.conn, "demo", "A", kind="note", message="alive")
        self.assertEqual(db.stale_tasks(self.conn, "demo", minutes=30), [])

    def test_old_events_do_not_mask_staleness(self):
        tid = db.add_task(self.conn, "demo", "A", "build X",
                          status="executing")
        db.post_event(self.conn, "demo", "A", kind="note", message="old")
        self.conn.execute("UPDATE events SET created_at = ?",
                          (self._age(90),))
        self.conn.commit()
        self._backdate_task(tid, 60)
        stale = db.stale_tasks(self.conn, "demo", minutes=30)
        self.assertEqual([t["id"] for t in stale], [tid])

    def test_done_and_merged_tasks_ignored(self):
        tid = db.add_task(self.conn, "demo", "A", "build X", status="done")
        self._backdate_task(tid, 120)
        self.assertEqual(db.stale_tasks(self.conn, "demo", minutes=30), [])

    def test_other_agents_events_do_not_count(self):
        tid = db.add_task(self.conn, "demo", "A", "build X",
                          status="executing")
        self._backdate_task(tid, 60)
        db.post_event(self.conn, "demo", "B", kind="note", message="hi")
        stale = db.stale_tasks(self.conn, "demo", minutes=30)
        self.assertEqual([t["id"] for t in stale], [tid])
