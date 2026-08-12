import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from orch import db
from orch import progress as progress_mod
from orch.progress import PHASES


def _project(conn, args):
    """Resolve the project: explicit flag, env var, the project linked to the
    current directory (via `orch link`), or the sole project if only one
    exists. Multi-project safe — agents run inside their target checkout."""
    name = args.project or os.environ.get("ORCH_PROJECT")
    if name:
        return name
    name = db.find_project_by_path(conn, os.getcwd())
    if name:
        return name
    projs = db.list_projects(conn)
    if len(projs) == 1:
        return projs[0]["name"]
    if not projs:
        raise db.NotFound("no projects exist (run: orch init <name>)")
    names = ", ".join(p["name"] for p in projs)
    raise db.Ambiguous(
        f"can't infer the project from this directory ({names}); run "
        f"`orch link <name>` here, or pass --project / set ORCH_PROJECT")


def cmd_init(conn, args):
    pid, created = db.create_project(conn, args.name, notes=args.notes)
    print(f"{'created' if created else 'exists'} project '{args.name}' "
          f"(id {pid})")
    return 0


def cmd_task_add(conn, args):
    tid = db.add_task(conn, _project(conn, args), args.agent, args.title,
                      issue_ref=args.issue, branch=args.branch,
                      worktree=args.worktree, context=args.context,
                      status=args.status)
    print(f"task added: {tid}")
    return 0


def cmd_task_update(conn, args):
    db.update_task(conn, args.task, status=args.status,
                   branch=args.branch, issue_ref=args.issue,
                   plan_path=args.plan, context=args.context,
                   worktree=args.worktree)
    print(f"task {args.task} updated")
    return 0


def _age(iso_ts):
    """'12m ago' for an ISO timestamp. Shown without judgement: 41 minutes on
    awaiting_approval means the human hasn't answered, not that anything is
    wrong."""
    try:
        then = datetime.fromisoformat(iso_ts)
    except (TypeError, ValueError):
        return ""
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    secs = max(int((datetime.now(timezone.utc) - then).total_seconds()), 0)
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


def _format_status(state):
    lines = [f"project: {state['project']['name']}", ""]
    waiting = state.get("waiting") or []
    if waiting:
        parts = ", ".join(f"{w['agent']} ({w['reason']})" if w['reason']
                          else w['agent'] for w in waiting)
        lines.append(f"** WAITING ON YOU: {parts}")
        lines.append("")
    lines.append("agents:")
    for a in state["agents"]:
        ct = a["current_task"]
        title = f" — {ct['title']}" if ct else ""
        branch = f" [{ct['branch']}]" if ct and ct["branch"] else ""
        lines.append(f"  {a['agent']}: {a['status']}{title}{branch}")
        prog = ct.get("progress") if ct else None
        if prog:
            lines.append(f"       {progress_mod.format_line(prog)}")
            nxt = f"next: {prog['next_step']} · " if prog["next_step"] else ""
            lines.append(f"       {nxt}{_age(prog['updated_at'])}")
    lines.append("")
    lines.append("recent events:")
    for e in state["events"][:15]:
        lines.append(f"  [{e['agent']}/{e['kind']}] {e['message']}")
    return "\n".join(lines)


def cmd_status(conn, args):
    state = db.get_state(conn, _project(conn, args))
    if args.json:
        print(json.dumps(state, indent=2))
    else:
        print(_format_status(state))
    return 0


def cmd_log(conn, args):
    state = db.get_state(conn, _project(conn, args), events_limit=args.n)
    for e in state["events"]:
        if args.agent and e["agent"] != args.agent:
            continue
        print(f"[{e['created_at']}] {e['agent']}/{e['kind']}: {e['message']}")
    return 0


def cmd_next(conn, args):
    task = db.next_task(conn, _project(conn, args), args.agent)
    if task is None:
        if not args.json:
            print("no task")
        return 0
    if args.json:
        print(json.dumps(task, indent=2))
    else:
        print(f"{task['id']} {task['status']} {task['title']}")
    return 0


def cmd_claim(conn, args):
    task = db.claim_next(conn, _project(conn, args), args.agent)
    if task is None:
        if not args.json:
            print("no queued task")
        return 0
    if args.json:
        print(json.dumps(task, indent=2))
    else:
        print(f"claimed {task['id']}: {task['title']}")
    return 0


def cmd_post(conn, args):
    eid = db.post_event(conn, _project(conn, args), args.agent,
                        kind=args.kind, message=args.msg,
                        task_id=args.task, status=args.status,
                        branch=args.branch)
    print(f"event posted: {eid}")
    return 0


def _is_inside_worktree(cwd):
    """True if cwd is a git worktree other than the repo's main checkout —
    ruling out a submodule, which also has its own private git-dir. Same
    detection the work skill's isolation check uses:
    `git rev-parse --git-dir` vs `--git-common-dir`."""
    def _git(args):
        try:
            out = subprocess.run(
                ["git", *args], cwd=cwd, capture_output=True, text=True,
                timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    git_dir = _git(["rev-parse", "--git-dir"])
    common_dir = _git(["rev-parse", "--git-common-dir"])
    if git_dir is None or common_dir is None:
        return False
    norm = lambda p: os.path.normcase(os.path.abspath(os.path.join(cwd, p)))
    if norm(git_dir) == norm(common_dir):
        return False
    if _git(["rev-parse", "--show-superproject-working-tree"]):
        return False  # submodule, not a worktree
    return True


def cmd_link(conn, args):
    if _is_inside_worktree(os.getcwd()):
        print("error: refusing to link from inside a git worktree — cd to "
              "the main checkout and run `orch link` there instead",
              file=sys.stderr)
        return 1
    db.require_project(conn, args.name)
    path = db.set_project_path(conn, args.name, os.getcwd())
    print(f"linked '{args.name}' to {path}")
    return 0


def cmd_report(conn, args):
    from orch import report as report_mod
    agent = args.agent or os.environ.get("ORCH_AGENT")
    if not agent:
        print("error: no agent given (use --agent or ORCH_AGENT)",
              file=sys.stderr)
        return 1
    report_mod.report(conn, _project(conn, args), agent, args.status,
                      msg=args.msg, branch=args.branch)
    print("reported")
    return 0


def cmd_progress(conn, args):
    from orch import progress as progress_mod
    agent = args.agent or os.environ.get("ORCH_AGENT")
    if not agent:
        print("error: no agent given (use --agent or ORCH_AGENT)",
              file=sys.stderr)
        return 1
    result = progress_mod.record(
        conn, _project(conn, args), agent, args.phase, message=args.msg,
        step=args.step, step_total=args.step_total, next_step=args.next,
        task_id=args.task)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    suffix = "" if result["recorded"] else " (unchanged)"
    print(f"progress: {progress_mod.format_line(result)}{suffix}")
    if result["next_step"]:
        print(f"next: {result['next_step']}")
    if result["truncated"]:
        print(f"note: message shortened to {progress_mod.MAX_MESSAGE} chars")
    return 0


def cmd_notify(conn, args):
    from orch.notify import send
    send(args.msg, title=args.title)
    return 0


def cmd_serve(conn, args):
    from orch.server import serve
    serve(_project(conn, args), port=args.port)
    return 0


def cmd_wait(conn, args):
    changed = db.wait_for_change(conn, _project(conn, args), args.timeout,
                                 interval=args.interval)
    print("changed" if changed else "timeout")
    return 0 if changed else 2


def cmd_deps(conn, args):
    from orch import deps as deps_mod
    try:
        msg = deps_mod.sync(conn, _project(conn, args))
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(msg)
    return 0


def cmd_prompt(conn, args):
    from orch import prompt as prompt_mod
    project = _project(conn, args)
    db.require_project(conn, project)
    if args.orchestrator:
        print(prompt_mod.orchestrator_prompt(conn, project))
    else:
        print(prompt_mod.worker_prompt(conn, project, args.agent))
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="orch")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init")
    pi.add_argument("name")
    pi.add_argument("--notes")
    pi.set_defaults(func=cmd_init)

    pk = sub.add_parser("link")
    pk.add_argument("name")
    pk.set_defaults(func=cmd_link)

    pt = sub.add_parser("task")
    tsub = pt.add_subparsers(dest="task_cmd", required=True)
    ta = tsub.add_parser("add")
    ta.add_argument("--project")
    ta.add_argument("--agent", required=True)
    ta.add_argument("--title", required=True)
    ta.add_argument("--issue")
    ta.add_argument("--branch")
    ta.add_argument("--worktree")
    ta.add_argument("--context")
    ta.add_argument("--status", default="queued")
    ta.set_defaults(func=cmd_task_add)
    tu = tsub.add_parser("update", aliases=["amend"])
    tu.add_argument("--project")
    tu.add_argument("--task", type=int, required=True)
    tu.add_argument("--status")
    tu.add_argument("--branch")
    tu.add_argument("--worktree")
    tu.add_argument("--issue")
    tu.add_argument("--plan")
    tu.add_argument("--context")
    tu.set_defaults(func=cmd_task_update)

    ps = sub.add_parser("status")
    ps.add_argument("--project")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_status)

    pl = sub.add_parser("log")
    pl.add_argument("--project")
    pl.add_argument("--agent")
    pl.add_argument("-n", type=int, default=20)
    pl.set_defaults(func=cmd_log)

    pp = sub.add_parser("post")
    pp.add_argument("--project")
    pp.add_argument("--agent", required=True)
    pp.add_argument("--task", type=int)
    pp.add_argument("--kind", default="status",
                    choices=["status", "note", "blocker", "handoff",
                             "needs_discussion", "needs_human", "warning"])
    pp.add_argument("--status")
    pp.add_argument("--branch")
    pp.add_argument("--msg", default="")
    pp.set_defaults(func=cmd_post)

    pn = sub.add_parser("next")
    pn.add_argument("--project")
    pn.add_argument("--agent", required=True)
    pn.add_argument("--json", action="store_true")
    pn.set_defaults(func=cmd_next)

    pc = sub.add_parser("claim")
    pc.add_argument("--project")
    pc.add_argument("--agent", required=True)
    pc.add_argument("--json", action="store_true")
    pc.set_defaults(func=cmd_claim)

    pr = sub.add_parser("report")
    pr.add_argument("--project")
    pr.add_argument("--agent")
    pr.add_argument("--status", required=True,
                    choices=["executing", "done", "blocked", "note"])
    pr.add_argument("--msg", default="")
    pr.add_argument("--branch")
    pr.set_defaults(func=cmd_report)

    # --phase is validated twice on purpose: argparse rejects it here with
    # the valid list, and progress.record rejects it for any non-CLI caller.
    pg = sub.add_parser("progress")
    pg.add_argument("--project")
    pg.add_argument("--agent")
    pg.add_argument("--task", type=int)
    pg.add_argument("--phase", required=True, choices=list(PHASES))
    pg.add_argument("--step", type=int)
    pg.add_argument("--step-total", type=int)
    pg.add_argument("--msg", default="")
    pg.add_argument("--next", default="")
    pg.add_argument("--json", action="store_true")
    pg.set_defaults(func=cmd_progress)

    pnf = sub.add_parser("notify")
    pnf.add_argument("--project")
    pnf.add_argument("--msg", required=True)
    pnf.add_argument("--title")
    pnf.set_defaults(func=cmd_notify)

    pv = sub.add_parser("serve")
    pv.add_argument("--project")
    pv.add_argument("--port", type=int, default=8787)
    pv.set_defaults(func=cmd_serve)

    pw = sub.add_parser("wait")
    pw.add_argument("--project")
    pw.add_argument("--timeout", type=float, default=300.0)
    pw.add_argument("--interval", type=float, default=2.0)
    pw.set_defaults(func=cmd_wait)

    pd = sub.add_parser("deps")
    pd.add_argument("--project")
    pd.set_defaults(func=cmd_deps)

    pp2 = sub.add_parser("prompt")
    pp2.add_argument("--project")
    grp = pp2.add_mutually_exclusive_group(required=True)
    grp.add_argument("--agent")
    grp.add_argument("--orchestrator", action="store_true")
    pp2.set_defaults(func=cmd_prompt)

    return p


def _force_utf8():
    """Print UTF-8 regardless of the console codepage (Windows cp1252 turns
    arrows/em-dashes in the event feed into '?')."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass  # not a reconfigurable TextIO (e.g. a pipe wrapper in tests)


def main(argv=None):
    _force_utf8()
    parser = build_parser()
    args = parser.parse_args(argv)
    conn = db.connect()
    try:
        return args.func(conn, args)
    except (db.NotFound, db.Ambiguous, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()
