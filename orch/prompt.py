"""Generate self-contained bootstrap prompts for orchestrator/worker windows.

The prompt becomes part of the orchestrator's state (read it from any terminal
with `orch prompt ...`) instead of a volatile chat message that the client can
drop. Output is intentionally ASCII-only so it is readable on any console.
"""
from pathlib import Path

from orch import db

# Repo root = parent of the `orch` package directory (where orch.py lives).
REPO_PATH = str(Path(__file__).resolve().parents[1])


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
Orchestrator repo (CLI + skills): {repo_path}
All commands run as: python {repo_path}/orch.py <cmd>

In THIS window first export your identity, then start the loop:
  export ORCH_PROJECT={project}
  export ORCH_AGENT={agent}
  /loop /work {agent}

{_task_brief(task)}

Rules: never merge to main (the orchestrator owns merge). For dated/old issues,
do gap-analysis vs the existing code BEFORE writing any code, then confirm scope
with the human. Report progress with /report; finish with /checkpoint."""


def orchestrator_prompt(conn, project, repo_path=REPO_PATH):
    return f"""You are the ORCHESTRATOR of the multi-agent system.
Orchestrator repo (CLI + skills): {repo_path}
All commands run as: python {repo_path}/orch.py <cmd>

In THIS window:
  export ORCH_PROJECT={project}
  /loop /orchestrate

You own integration only: merge `done` branches into main + run tests, reconcile
Linear, and ping the human on blockers. You never write specs, plans, or feature
code. When you queue kickoffs, pre-assign each task's branch and state explicit
file boundaries (\"do NOT touch X, agent Y owns it\") so parallel agents never
collide."""
