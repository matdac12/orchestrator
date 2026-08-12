import subprocess

from orch import db
from orch import notify as notify_mod
from orch import progress

# Auto-detection must never record one of these as a task's feature branch:
# a `done` reported from a window sitting on main would otherwise clobber the
# pre-assigned feature branch. An explicit --branch is always honored.
DEFAULT_BRANCH_NAMES = {"main", "master"}


def current_branch(cwd=None):
    try:
        out = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=cwd, timeout=5)
        if out.returncode == 0:
            branch = out.stdout.strip()
            return branch or None
    except Exception:
        return None
    return None


def report(conn, project, agent, status, msg="", branch=None,
           notifier=notify_mod.send):
    if status == "note":
        return db.post_event(conn, project, agent, kind="note", message=msg)

    eff_branch = branch
    if status == "done" and eff_branch is None:
        detected = current_branch()
        if detected not in DEFAULT_BRANCH_NAMES:
            eff_branch = detected

    eid = db.post_event(conn, project, agent, kind="status",
                        message=msg, status=status, branch=eff_branch)

    if status == "blocked":
        # The blocker itself is already recorded above. The progress row is
        # telemetry on top of it: best-effort, and never allowed to raise
        # past a blocker the human needs to see.
        try:
            progress.record(conn, project, agent, "blocked", message=msg)
        except Exception:
            pass
        notifier(f"Agent {agent} blocked: {msg}", title="Blocked")

    return eid
