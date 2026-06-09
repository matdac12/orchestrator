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


if __name__ == "__main__":
    unittest.main()
