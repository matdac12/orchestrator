import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(args, db_path):
    env = dict(os.environ, ORCH_DB=db_path)
    return subprocess.run(
        [sys.executable, os.path.join(ROOT, "orch.py"), *args],
        capture_output=True, text=True, env=env)


class CLITest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "state.db")

    def test_init_then_status_json(self):
        self.assertEqual(run(["init", "demo"], self.db).returncode, 0)
        out = run(["status", "--project", "demo", "--json"], self.db)
        self.assertEqual(out.returncode, 0)
        state = json.loads(out.stdout)
        self.assertEqual(state["project"]["name"], "demo")

    def test_task_add_prints_id_and_status_shows_it(self):
        run(["init", "demo"], self.db)
        add = run(["task", "add", "--project", "demo", "--agent", "B",
                   "--title", "build X", "--issue", "LIN-1"], self.db)
        self.assertEqual(add.returncode, 0)
        tid = int(add.stdout.strip().split()[-1])
        upd = run(["task", "update", "--project", "demo", "--task", str(tid),
                   "--status", "merged"], self.db)
        self.assertEqual(upd.returncode, 0)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["status"], "merged")

    def test_status_unknown_project_errors(self):
        out = run(["status", "--project", "nope", "--json"], self.db)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("not found", out.stderr.lower())

    def test_log_outputs_events(self):
        run(["init", "demo"], self.db)
        run(["task", "add", "--project", "demo", "--agent", "B",
             "--title", "X"], self.db)
        run(["post", "--project", "demo", "--agent", "B",
             "--msg", "hello"], self.db)
        out = run(["log", "--project", "demo"], self.db)
        self.assertEqual(out.returncode, 0)
        self.assertIn("hello", out.stdout)

    def test_task_add_context_and_status_persist(self):
        run(["init", "demo"], self.db)
        add = run(["task", "add", "--project", "demo", "--agent", "A",
                   "--title", "X", "--context", "kickoff brief",
                   "--status", "queued"], self.db)
        self.assertEqual(add.returncode, 0)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["context"], "kickoff brief")
        self.assertEqual(state["tasks"][0]["status"], "queued")

    def test_task_update_plan_path(self):
        run(["init", "demo"], self.db)
        add = run(["task", "add", "--project", "demo", "--agent", "A",
                   "--title", "X"], self.db)
        tid = int(add.stdout.strip().split()[-1])
        upd = run(["task", "update", "--project", "demo", "--task", str(tid),
                   "--plan", "docs/p.md"], self.db)
        self.assertEqual(upd.returncode, 0)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["plan_path"], "docs/p.md")

    def test_post_needs_discussion_kind(self):
        run(["init", "demo"], self.db)
        run(["task", "add", "--project", "demo", "--agent", "A",
             "--title", "X"], self.db)
        out = run(["post", "--project", "demo", "--agent", "A",
                   "--kind", "needs_discussion", "--msg", "come talk"], self.db)
        self.assertEqual(out.returncode, 0)
        log = run(["log", "--project", "demo"], self.db)
        self.assertIn("needs_discussion", log.stdout)

    def test_next_empty_then_returns_task(self):
        run(["init", "demo"], self.db)
        empty = run(["next", "--project", "demo", "--agent", "A", "--json"],
                    self.db)
        self.assertEqual(empty.returncode, 0)
        self.assertEqual(empty.stdout.strip(), "")
        run(["task", "add", "--project", "demo", "--agent", "A",
             "--title", "X"], self.db)
        got = run(["next", "--project", "demo", "--agent", "A", "--json"],
                  self.db)
        self.assertEqual(json.loads(got.stdout)["title"], "X")

    def test_claim_transitions_and_prints(self):
        run(["init", "demo"], self.db)
        run(["task", "add", "--project", "demo", "--agent", "A",
             "--title", "X"], self.db)
        claimed = run(["claim", "--project", "demo", "--agent", "A",
                       "--json"], self.db)
        self.assertEqual(claimed.returncode, 0)
        self.assertEqual(json.loads(claimed.stdout)["status"], "discussing")
        # second claim finds nothing queued
        again = run(["claim", "--project", "demo", "--agent", "A", "--json"],
                    self.db)
        self.assertEqual(again.stdout.strip(), "")

    def test_post_status_updates_task(self):
        run(["init", "demo"], self.db)
        add = run(["task", "add", "--project", "demo", "--agent", "B",
                   "--title", "X"], self.db)
        tid = int(add.stdout.strip().split()[-1])
        out = run(["post", "--project", "demo", "--agent", "B",
                   "--status", "done", "--branch", "feat/x",
                   "--msg", "ready"], self.db)
        self.assertEqual(out.returncode, 0)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["status"], "done")
        self.assertEqual(state["tasks"][0]["branch"], "feat/x")
        self.assertEqual(state["agents"][0]["agent"], "B")
        _ = tid


    def _run_agent(self, args, agent="A"):
        env = dict(os.environ, ORCH_DB=self.db, ORCH_AGENT=agent)
        for k in ("ORCH_TG_TOKEN", "ORCH_TG_CHAT", "ORCH_TG_CONFIG"):
            env.pop(k, None)
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "orch.py"), *args],
            capture_output=True, text=True, env=env)

    def test_report_executing_uses_env_agent(self):
        run(["init", "demo"], self.db)
        run(["task", "add", "--project", "demo", "--agent", "A",
             "--title", "X", "--status", "discussing"], self.db)
        out = self._run_agent(
            ["report", "--project", "demo", "--status", "executing",
             "--msg", "go"])
        self.assertEqual(out.returncode, 0)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["status"], "executing")

    def test_report_done_records_branch(self):
        run(["init", "demo"], self.db)
        run(["task", "add", "--project", "demo", "--agent", "A",
             "--title", "X", "--status", "executing"], self.db)
        out = self._run_agent(
            ["report", "--project", "demo", "--status", "done",
             "--branch", "feat/z"])
        self.assertEqual(out.returncode, 0)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["status"], "done")
        self.assertEqual(state["tasks"][0]["branch"], "feat/z")

    def test_report_blocked_notifies_dry_run(self):
        run(["init", "demo"], self.db)
        run(["task", "add", "--project", "demo", "--agent", "A",
             "--title", "X", "--status", "executing"], self.db)
        out = self._run_agent(
            ["report", "--project", "demo", "--status", "blocked",
             "--msg", "stuck"])
        self.assertEqual(out.returncode, 0)
        self.assertIn("dry-run", out.stdout)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["status"], "blocked")

    def test_report_agent_flag_overrides_env(self):
        run(["init", "demo"], self.db)
        run(["task", "add", "--project", "demo", "--agent", "B",
             "--title", "Y", "--status", "executing"], self.db)
        out = self._run_agent(
            ["report", "--project", "demo", "--agent", "B",
             "--status", "done", "--branch", "b/x"])
        self.assertEqual(out.returncode, 0)
        state = json.loads(
            run(["status", "--project", "demo", "--json"], self.db).stdout)
        self.assertEqual(state["tasks"][0]["status"], "done")

    def test_report_missing_identity_errors(self):
        run(["init", "demo"], self.db)
        env = dict(os.environ, ORCH_DB=self.db)
        env.pop("ORCH_AGENT", None)
        out = subprocess.run(
            [sys.executable, os.path.join(ROOT, "orch.py"),
             "report", "--project", "demo", "--status", "note",
             "--msg", "hi"],
            capture_output=True, text=True, env=env)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("agent", out.stderr.lower())

    def test_notify_dry_run_succeeds(self):
        # No token configured -> dry-run, prints message, exit 0
        env = dict(os.environ, ORCH_DB=self.db)
        for k in ("ORCH_TG_TOKEN", "ORCH_TG_CHAT", "ORCH_TG_CONFIG"):
            env.pop(k, None)
        out = subprocess.run(
            [sys.executable, os.path.join(ROOT, "orch.py"),
             "notify", "--msg", "ping", "--title", "T"],
            capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0)
        self.assertIn("ping", out.stdout)


if __name__ == "__main__":
    unittest.main()
