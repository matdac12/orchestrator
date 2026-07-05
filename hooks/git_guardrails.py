#!/usr/bin/env python3
"""PreToolUse hook: block irreversible/destructive git commands.

Worker and orchestrator agents run unattended for long stretches (per
/loop /work A, /loop /orchestrate) — nobody is watching the moment a
command actually executes. This blocks the small set of git commands that
destroy history or uncommitted work outright, so a confused or looping
agent can't force-push, hard-reset, or wipe a worktree clean without a
human explicitly stepping in.

Not installed automatically — see the README's "Recommended: git safety
hook" section for how to wire this into .claude/settings.json (globally,
or per target project).

`git reset --hard` is special-cased: reset to a bare/moving target (no
arg, HEAD~n, a branch/tag name, origin/main, ...) is blocked, but reset to
a specific full commit SHA is allowed — that's the shape of a recorded
rollback point (e.g. orchestrate/SKILL.md captures `git rev-parse main`
before merging and restores to it if tests fail after a clean merge; a
bare "hard reset" rule would silently defeat that safety net for anyone
who installs this hook).

Exit 0: allow. Exit 2: block: stderr is shown back to the calling model.
"""
import json
import re
import sys

BLOCKED = [
    (r"\bgit\s+push\b[^&|;]*(--force\b|(?<!--)\s-f\b)", "force push"),
    (r"\bgit\s+clean\s+-[a-zA-Z]*f", "force clean"),
    (r"\bgit\s+branch\s+-D\b", "force branch delete"),
    (r"\bgit\s+checkout\s+\.(\s|$)", "checkout . (discards all changes)"),
    (r"\bgit\s+restore\s+\.(\s|$)", "restore . (discards all changes)"),
]

HARD_RESET_RE = re.compile(r"\bgit\s+reset\s+--hard\b")
SHA_RESET_RE = re.compile(r"\bgit\s+reset\s+--hard\s+[0-9a-fA-F]{40}\b")


def main():
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        return 0
    command = payload.get("tool_input", {}).get("command", "")

    if HARD_RESET_RE.search(command) and not SHA_RESET_RE.search(command):
        print(
            f"git-guardrails: blocked (hard reset to a moving target): "
            f"{command!r}\nA hard reset with no arg, HEAD~n, or a "
            f"branch/tag name is destructive and hard to reverse. A reset "
            f"to a specific full commit SHA is allowed — ask the human to "
            f"run anything else directly.",
            file=sys.stderr,
        )
        return 2

    for pattern, label in BLOCKED:
        if re.search(pattern, command):
            print(
                f"git-guardrails: blocked ({label}): {command!r}\n"
                f"This command is destructive/hard to reverse — ask the "
                f"human to run it directly if it's genuinely needed.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
