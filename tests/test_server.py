import json
import os
import tempfile
import unittest

from orch import db, server


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "state.db")
        os.environ["ORCH_DB"] = self.db
        conn = db.connect(self.db)
        db.create_project(conn, "demo")
        db.add_task(conn, "demo", "B", "build X")
        db.post_event(conn, "demo", "B", status="executing", message="go")
        conn.close()

    def tearDown(self):
        del os.environ["ORCH_DB"]

    def test_api_state_returns_json(self):
        body, ctype = server.render_api_state("demo")
        self.assertIn("application/json", ctype)
        state = json.loads(body)
        self.assertEqual(state["project"]["name"], "demo")
        self.assertEqual(state["agents"][0]["status"], "executing")

    def test_api_state_unknown_project(self):
        body, ctype = server.render_api_state("nope")
        self.assertIn("application/json", ctype)
        self.assertIn("error", json.loads(body))

    def test_index_html_served(self):
        html, ctype = server.render_index("demo")
        self.assertIn("text/html", ctype)
        self.assertIn("demo", html)

    def test_index_has_v2_status_classes(self):
        html, _ = server.render_index("demo")
        for cls in ("queued", "discussing", "executing",
                    "blocked", "done", "merged"):
            self.assertIn("." + cls, html)


if __name__ == "__main__":
    unittest.main()
