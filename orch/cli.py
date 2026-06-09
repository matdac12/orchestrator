import argparse
import json
import sys

from orch import db


def _project(args):
    import os
    name = args.project or os.environ.get("ORCH_PROJECT")
    if not name:
        raise db.NotFound("no project given (use --project or ORCH_PROJECT)")
    return name


def cmd_init(conn, args):
    pid, created = db.create_project(conn, args.name, notes=args.notes)
    print(f"{'created' if created else 'exists'} project '{args.name}' "
          f"(id {pid})")
    return 0


def cmd_task_add(conn, args):
    tid = db.add_task(conn, _project(args), args.agent, args.title,
                      issue_ref=args.issue, branch=args.branch,
                      worktree=args.worktree)
    print(f"task added: {tid}")
    return 0


def cmd_task_update(conn, args):
    db.update_task(conn, args.task, status=args.status,
                   branch=args.branch, issue_ref=args.issue)
    print(f"task {args.task} updated")
    return 0


def _format_status(state):
    lines = [f"project: {state['project']['name']}", "", "agents:"]
    for a in state["agents"]:
        ct = a["current_task"]
        title = f" — {ct['title']}" if ct else ""
        branch = f" [{ct['branch']}]" if ct and ct["branch"] else ""
        lines.append(f"  {a['agent']}: {a['status']}{title}{branch}")
    lines.append("")
    lines.append("recent events:")
    for e in state["events"][:15]:
        lines.append(f"  [{e['agent']}/{e['kind']}] {e['message']}")
    return "\n".join(lines)


def cmd_status(conn, args):
    state = db.get_state(conn, _project(args))
    if args.json:
        print(json.dumps(state, indent=2))
    else:
        print(_format_status(state))
    return 0


def cmd_log(conn, args):
    state = db.get_state(conn, _project(args), events_limit=args.n)
    for e in state["events"]:
        if args.agent and e["agent"] != args.agent:
            continue
        print(f"[{e['created_at']}] {e['agent']}/{e['kind']}: {e['message']}")
    return 0


def cmd_post(conn, args):
    eid = db.post_event(conn, _project(args), args.agent,
                        kind=args.kind, message=args.msg,
                        task_id=args.task, status=args.status,
                        branch=args.branch)
    print(f"event posted: {eid}")
    return 0


def cmd_serve(conn, args):
    from orch.server import serve
    serve(_project(args), port=args.port)
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="orch")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init")
    pi.add_argument("name")
    pi.add_argument("--notes")
    pi.set_defaults(func=cmd_init)

    pt = sub.add_parser("task")
    tsub = pt.add_subparsers(dest="task_cmd", required=True)
    ta = tsub.add_parser("add")
    ta.add_argument("--project")
    ta.add_argument("--agent", required=True)
    ta.add_argument("--title", required=True)
    ta.add_argument("--issue")
    ta.add_argument("--branch")
    ta.add_argument("--worktree")
    ta.set_defaults(func=cmd_task_add)
    tu = tsub.add_parser("update")
    tu.add_argument("--project")
    tu.add_argument("--task", type=int, required=True)
    tu.add_argument("--status")
    tu.add_argument("--branch")
    tu.add_argument("--issue")
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
                    choices=["status", "note", "blocker", "handoff"])
    pp.add_argument("--status")
    pp.add_argument("--branch")
    pp.add_argument("--msg", default="")
    pp.set_defaults(func=cmd_post)

    pv = sub.add_parser("serve")
    pv.add_argument("--project")
    pv.add_argument("--port", type=int, default=8787)
    pv.set_defaults(func=cmd_serve)

    return p


def main(argv=None):
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
