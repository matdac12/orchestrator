"""Generate self-contained bootstrap prompts for orchestrator/worker windows.

The prompt becomes part of the orchestrator's state (read it from any terminal
with `orch prompt ...`) instead of a volatile chat message that the client can
drop. Output is intentionally ASCII-only so it is readable on any console.
"""
from pathlib import Path

from orch import db

# Repo root = parent of the `orch` package directory (where orch.py lives).
# Use POSIX-style separators so `<repo>/orch.py` reads cleanly on every platform
# (Windows `python C:/.../orch.py` works fine; avoids ugly mixed back/forward slashes).
REPO_PATH = Path(__file__).resolve().parents[1].as_posix()


def _agent_task(conn, project, agent):
    """The agent's single active task (queued/discussing/executing/blocked)."""
    return db.next_task(conn, project, agent)


def _task_brief(task):
    if not task:
        return "No task queued for this agent yet."
    lines = [f"Current task #{task['id']} [{task['status']}]: {task['title']}"]
    if task.get("issue_ref"):
        lines.append(f"  issue:   {task['issue_ref']}")
    if task.get("branch"):
        lines.append(f"  branch:  {task['branch']}")
    if task.get("worktree"):
        lines.append(f"  worktree: {task['worktree']}")
    if task.get("context"):
        lines.append(f"  context: {task['context']}")
    return "\n".join(lines)


def worker_prompt(conn, project, agent, repo_path=REPO_PATH):
    task = _agent_task(conn, project, agent)
    return f"""You are WORKER AGENT {agent} in the orchestrator multi-agent system.
Project: {project}
Orchestrator repo (CLI + skills): {repo_path}
All orch commands run as: python {repo_path}/orch.py <cmd>

STEP 1 - in your TERMINAL, set up the window, THEN launch Claude Code from it.
Do this in the shell BEFORE `claude` starts: env vars do NOT persist if you set
them from inside the session, and `/report`/`/checkpoint` need them.
  cd <your local checkout of the {project} project>   # this window works INSIDE the target project
  export ORCH_PROJECT={project}
  export ORCH_AGENT={agent}
  claude                                               # launch from THIS same shell

STEP 2 - once Claude Code is open in this window, type:
  /loop /work {agent}

{_task_brief(task)}

Rules: never merge to main (the orchestrator owns merge). For dated/old issues,
do gap-analysis vs the existing code BEFORE writing any code, then confirm scope
with the human. Report progress with /report; finish with /checkpoint."""


def orchestrator_prompt(conn, project, repo_path=REPO_PATH):
    return f"""You are the ORCHESTRATOR of the multi-agent system.
Project: {project}
Orchestrator repo (CLI + skills): {repo_path}
All orch commands run as: python {repo_path}/orch.py <cmd>

STEP 1 - in your TERMINAL, set up the window, THEN launch Claude Code from it.
Do this in the shell BEFORE `claude` starts (env vars do NOT persist if set from
inside the session). You merge branches, so this window MUST run inside the target
project's git checkout.
  cd <your local checkout of the {project} project>
  export ORCH_PROJECT={project}
  claude                                               # launch from THIS same shell

STEP 2 - once Claude Code is open in this window, type:
  /loop /orchestrate

You own integration only: merge `done` branches into main + run tests, reconcile
Linear, and ping the human on blockers. You never write specs, plans, or feature
code. When you queue kickoffs, pre-assign each task's branch and state explicit
file boundaries (\"do NOT touch X, agent Y owns it\") so parallel agents never
collide."""
