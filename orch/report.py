import subprocess

from orch import db
from orch import notify as notify_mod


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
        eff_branch = current_branch()

    eid = db.post_event(conn, project, agent, kind="status",
                        message=msg, status=status, branch=eff_branch)

    if status == "blocked":
        notifier(f"Agent {agent} blocked: {msg}", title="Blocked")

    return eid
