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

Exit 0: allow. Exit 2: block: stderr is shown back to the calling model.
"""
import json
import re
import sys

BLOCKED = [
    (r"\bgit\s+push\b[^&|;]*(--force\b|(?<!--)\s-f\b)", "force push"),
    (r"\bgit\s+reset\s+--hard\b", "hard reset"),
    (r"\bgit\s+clean\s+-[a-zA-Z]*f", "force clean"),
    (r"\bgit\s+branch\s+-D\b", "force branch delete"),
    (r"\bgit\s+checkout\s+\.(\s|$)", "checkout . (discards all changes)"),
    (r"\bgit\s+restore\s+\.(\s|$)", "restore . (discards all changes)"),
]


def main():
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        return 0
    command = payload.get("tool_input", {}).get("command", "")
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
