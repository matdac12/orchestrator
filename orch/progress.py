"""Worker progress: what an agent is doing, and how much of its plan is left.

Progress runs alongside the task lifecycle without touching it. A progress
event never writes `tasks.status` and never raises `needs_human` — only
`orch report`/`orch post` do those — and a late phase never authorizes a
merge. Reporting is event-driven: workers report at phase boundaries and at
the start of each plan task. There is no heartbeat, because a worker agent
has no timer and can only report when it happens to look up.
"""

from orch import db

PHASES = ("setup", "investigation", "planning", "awaiting_approval",
          "implementation", "checkpoint", "blocked")

# A `done` or `merged` task is over; progress against it would describe work
# that already finished, so it is refused rather than silently recorded.
CLOSED_STATUSES = ("done", "merged")

MAX_MESSAGE = 200


def _validate_steps(step, step_total):
    if (step is None) != (step_total is None):
        raise ValueError(
            "step and step_total go together — pass both or neither")
    if step is None:
        return
    if step < 1:
        raise ValueError(f"step must be 1 or more (got {step})")
    if step_total < 1:
        raise ValueError(f"step_total must be 1 or more (got {step_total})")
    if step > step_total:
        raise ValueError(f"step {step} is past step_total {step_total}")


def record(conn, project, agent, phase, message="", step=None,
           step_total=None, next_step=None, task_id=None):
    """Append one progress event for the agent's task.

    Returns {task_id, phase, step, step_total, message, next_step, recorded,
    truncated}. `recorded` is False when this repeats the task's current
    progress exactly — a resumed worker re-reporting the milestone it already
    reported should not leave a second identical row."""
    if phase not in PHASES:
        raise ValueError(
            f"unknown phase '{phase}', expected one of: {', '.join(PHASES)}")
    _validate_steps(step, step_total)

    task = db.resolve_task(conn, project, agent, task_id=task_id)
    if task["status"] in CLOSED_STATUSES:
        raise ValueError(
            f"task {task['id']} is {task['status']} — progress only applies "
            f"to a task still in flight (use `orch report` for lifecycle "
            f"changes)")

    text = (message or "").strip()
    truncated = len(text) > MAX_MESSAGE
    snapshot = {
        "phase": phase,
        "step": step,
        "step_total": step_total,
        "message": text[:MAX_MESSAGE],
        "next_step": (next_step or "").strip() or None,
    }

    current = db.latest_progress(conn, task["id"])
    unchanged = current is not None and all(
        current[k] == v for k, v in snapshot.items())
    if not unchanged:
        db.post_event(conn, project, agent, kind="progress",
                      message=snapshot["message"], task_id=task["id"],
                      progress=snapshot)

    return dict(snapshot, task_id=task["id"], recorded=not unchanged,
                truncated=truncated)


def format_line(snapshot):
    """One line: 'implementation 3/6 · wiring the CLI'. Takes any snapshot
    dict — a `db.latest_progress` result or a `record` return value."""
    if not snapshot:
        return ""
    parts = [snapshot["phase"]]
    if snapshot.get("step") and snapshot.get("step_total"):
        parts.append(f"{snapshot['step']}/{snapshot['step_total']}")
    if snapshot.get("message"):
        parts.append(f"· {snapshot['message']}")
    return " ".join(parts)
