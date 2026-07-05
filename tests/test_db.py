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


class ProjectPathTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))

    def test_link_and_resolve_by_path(self):
        db.create_project(self.conn, "alpha")
        root = os.path.join(self.tmp, "alpha-checkout")
        db.set_project_path(self.conn, "alpha", root)
        # exact dir and a nested worktree both resolve to the project
        self.assertEqual(db.find_project_by_path(self.conn, root), "alpha")
        nested = os.path.join(root, ".claude", "worktrees", "agent-x")
        self.assertEqual(db.find_project_by_path(self.conn, nested), "alpha")

    def test_unlinked_dir_resolves_to_none(self):
        db.create_project(self.conn, "alpha")
        self.assertIsNone(
            db.find_project_by_path(self.conn, os.path.join(self.tmp, "x")))

    def test_longest_prefix_wins(self):
        db.create_project(self.conn, "outer")
        db.create_project(self.conn, "inner")
        outer = os.path.join(self.tmp, "repo")
        inner = os.path.join(outer, "sub")
        db.set_project_path(self.conn, "outer", outer)
        db.set_project_path(self.conn, "inner", inner)
        self.assertEqual(
            db.find_project_by_path(self.conn, os.path.join(inner, "deep")),
            "inner")
        self.assertEqual(
            db.find_project_by_path(self.conn, os.path.join(outer, "other")),
            "outer")

    def test_sibling_prefix_not_matched(self):
        # /repo must not match /repo-two (guard the startswith boundary)
        db.create_project(self.conn, "repo")
        db.set_project_path(self.conn, "repo", os.path.join(self.tmp, "repo"))
        self.assertIsNone(db.find_project_by_path(
            self.conn, os.path.join(self.tmp, "repo-two")))


class RetryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))

    def test_with_retry_recovers_from_locked(self):
        calls = {"n": 0}

        def action():
            calls["n"] += 1
            if calls["n"] < 3:
                raise sqlite3.OperationalError("database is locked")
            return "ok"

        self.assertEqual(
            db.with_retry(self.conn, action, base_delay=0.0), "ok")
        self.assertEqual(calls["n"], 3)

    def test_with_retry_reraises_other_errors(self):
        def action():
            raise sqlite3.OperationalError("no such table")

        with self.assertRaises(sqlite3.OperationalError):
            db.with_retry(self.conn, action, base_delay=0.0)

    def test_with_retry_rolls_back_before_retrying(self):
        # If the "locked" error fires at commit() rather than at the first
        # write, the transaction is still open with that write already
        # applied. Without a rollback, retrying re-runs the write a second
        # time inside the same open transaction, leaving 2 rows once the
        # retry finally commits instead of 1.
        self.conn.execute("CREATE TABLE t (x TEXT)")
        self.conn.commit()
        calls = {"n": 0}

        def action():
            calls["n"] += 1
            self.conn.execute("INSERT INTO t (x) VALUES ('row')")
            if calls["n"] < 2:
                raise sqlite3.OperationalError("database is locked")
            self.conn.commit()
            return "ok"

        self.assertEqual(
            db.with_retry(self.conn, action, base_delay=0.0), "ok")
        rows = self.conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
        self.assertEqual(rows, 1)


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

    def test_update_task_sets_worktree(self):
        tid = db.add_task(self.conn, "demo", "B", "build X")
        db.update_task(self.conn, tid, worktree="/repo/.claude/worktrees/b-x")
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        self.assertEqual(row["worktree"], "/repo/.claude/worktrees/b-x")

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


class NeedsHumanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")

    def _task(self, tid):
        return self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()

    def test_schema_has_needs_human_columns(self):
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(tasks)")}
        self.assertTrue({"needs_human", "needs_human_reason"}.issubset(cols))

    def test_needs_discussion_raises_flag_with_reason(self):
        tid = db.add_task(self.conn, "demo", "A", "x", status="discussing")
        db.post_event(self.conn, "demo", "A", kind="needs_discussion",
                      message="come brainstorm")
        row = self._task(tid)
        self.assertEqual(row["needs_human"], 1)
        self.assertEqual(row["needs_human_reason"], "come brainstorm")

    def test_blocked_status_raises_flag_even_with_status_kind(self):
        # orch.report always posts blocked with kind="status" (never
        # "blocker"), so the flag must be raised off the status too.
        tid = db.add_task(self.conn, "demo", "A", "x", status="executing")
        db.post_event(self.conn, "demo", "A", kind="status", status="blocked",
                      message="need api key")
        row = self._task(tid)
        self.assertEqual(row["status"], "blocked")
        self.assertEqual(row["needs_human"], 1)
        self.assertEqual(row["needs_human_reason"], "need api key")

    def test_blocker_raises_flag(self):
        tid = db.add_task(self.conn, "demo", "A", "x", status="executing")
        db.post_event(self.conn, "demo", "A", kind="blocker",
                      message="need api key")
        self.assertEqual(self._task(tid)["needs_human"], 1)

    def test_executing_clears_flag(self):
        tid = db.add_task(self.conn, "demo", "A", "x", status="discussing")
        db.post_event(self.conn, "demo", "A", kind="needs_discussion",
                      message="talk")
        self.assertEqual(self._task(tid)["needs_human"], 1)
        db.post_event(self.conn, "demo", "A", status="executing", message="go")
        row = self._task(tid)
        self.assertEqual(row["needs_human"], 0)
        self.assertIsNone(row["needs_human_reason"])

    def test_get_state_exposes_waiting(self):
        db.add_task(self.conn, "demo", "A", "login", status="discussing")
        db.add_task(self.conn, "demo", "C", "search", status="executing")
        db.post_event(self.conn, "demo", "A", kind="needs_discussion",
                      message="review spec")
        db.post_event(self.conn, "demo", "C", kind="blocker",
                      message="which file?")
        waiting = db.get_state(self.conn, "demo")["waiting"]
        by_agent = {w["agent"]: w for w in waiting}
        self.assertEqual(set(by_agent), {"A", "C"})
        self.assertEqual(by_agent["A"]["reason"], "review spec")
        self.assertEqual(by_agent["C"]["reason"], "which file?")

    def test_migrate_adds_columns_to_legacy_table(self):
        path = os.path.join(self.tmp, "legacy.db")
        raw = sqlite3.connect(path)
        raw.executescript(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY, agent TEXT, "
            "status TEXT, updated_at TEXT);")
        raw.commit()
        db._migrate(raw)
        cols = {r[1] for r in raw.execute("PRAGMA table_info(tasks)")}
        self.assertTrue({"needs_human", "needs_human_reason"}.issubset(cols))
        # idempotent
        db._migrate(raw)
        raw.close()

    def test_migrate_tolerates_concurrent_duplicate_column(self):
        # Simulates two agents starting at once against the same legacy DB:
        # both see the column missing, both attempt to add it; the loser's
        # ALTER must not raise.
        path = os.path.join(self.tmp, "legacy2.db")
        raw = sqlite3.connect(path)
        raw.executescript(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY, agent TEXT, "
            "status TEXT, updated_at TEXT);")
        raw.commit()
        raw.execute("ALTER TABLE tasks ADD COLUMN needs_human INTEGER "
                    "NOT NULL DEFAULT 0")
        raw.commit()
        # needs_human already exists as if another process just added it;
        # _migrate must still succeed and add the remaining columns.
        db._migrate(raw)
        cols = {r[1] for r in raw.execute("PRAGMA table_info(tasks)")}
        self.assertTrue({"needs_human", "needs_human_reason"}.issubset(cols))
        raw.close()


class WaitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = db.connect(os.path.join(self.tmp, "state.db"))
        db.create_project(self.conn, "demo")

    def test_signature_changes_on_new_event(self):
        db.add_task(self.conn, "demo", "A", "x")
        sig1 = db.state_signature(self.conn, "demo")
        db.post_event(self.conn, "demo", "A", message="tick")
        self.assertNotEqual(sig1, db.state_signature(self.conn, "demo"))

    def test_signature_changes_on_task_status(self):
        tid = db.add_task(self.conn, "demo", "A", "x")
        sig1 = db.state_signature(self.conn, "demo")
        db.update_task(self.conn, tid, status="merged")
        self.assertNotEqual(sig1, db.state_signature(self.conn, "demo"))

    def test_wait_returns_true_when_baseline_is_stale(self):
        db.add_task(self.conn, "demo", "A", "x")
        baseline = db.state_signature(self.conn, "demo")
        db.post_event(self.conn, "demo", "A", message="changed")
        # No sleeping needed: the change already happened vs the baseline.
        self.assertTrue(db.wait_for_change(
            self.conn, "demo", timeout=5, baseline=baseline,
            sleep=lambda s: None))

    def test_wait_times_out_without_change(self):
        db.add_task(self.conn, "demo", "A", "x")
        ticks = iter([0.0, 0.0, 1.0])  # start, first check, past deadline
        self.assertFalse(db.wait_for_change(
            self.conn, "demo", timeout=0.5, interval=0.1,
            sleep=lambda s: None, clock=lambda: next(ticks)))


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
