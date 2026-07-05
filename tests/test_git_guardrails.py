import json
import os
import subprocess
import sys
import unittest

HOOK = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "hooks", "git_guardrails.py")


def run_hook(command, tool_name="Bash"):
    payload = json.dumps({"tool_name": tool_name,
                          "tool_input": {"command": command}})
    return subprocess.run(
        [sys.executable, HOOK], input=payload, capture_output=True,
        text=True)


class GitGuardrailsTest(unittest.TestCase):
    def test_allows_ordinary_commands(self):
        out = run_hook("git status")
        self.assertEqual(out.returncode, 0)

    def test_ignores_non_bash_tools(self):
        out = run_hook("git reset --hard", tool_name="Read")
        self.assertEqual(out.returncode, 0)

    def test_blocks_force_push(self):
        out = run_hook("git push --force origin main")
        self.assertEqual(out.returncode, 2)
        self.assertIn("force push", out.stderr)

    def test_blocks_force_clean(self):
        out = run_hook("git clean -fd")
        self.assertEqual(out.returncode, 2)

    def test_blocks_force_branch_delete(self):
        out = run_hook("git branch -D feat/x")
        self.assertEqual(out.returncode, 2)

    def test_blocks_checkout_dot(self):
        out = run_hook("git checkout .")
        self.assertEqual(out.returncode, 2)

    def test_blocks_bare_hard_reset(self):
        out = run_hook("git reset --hard")
        self.assertEqual(out.returncode, 2)
        self.assertIn("moving target", out.stderr)

    def test_blocks_hard_reset_to_branch(self):
        out = run_hook("git reset --hard origin/main")
        self.assertEqual(out.returncode, 2)

    def test_blocks_hard_reset_to_head_tilde(self):
        out = run_hook("git reset --hard HEAD~3")
        self.assertEqual(out.returncode, 2)

    def test_allows_hard_reset_to_full_sha(self):
        sha = "a" * 40
        out = run_hook(f"git reset --hard {sha}")
        self.assertEqual(out.returncode, 0)

    def test_blocks_hard_reset_to_short_sha(self):
        # A short SHA is still a somewhat-moving/ambiguous target — only a
        # full 40-char SHA is treated as a disciplined rollback point.
        out = run_hook("git reset --hard a1b2c3d")
        self.assertEqual(out.returncode, 2)


if __name__ == "__main__":
    unittest.main()
