#!/usr/bin/env python3
"""Clockify CLI for the clockify-report skill.

Stdlib only. No venv, no pip, runs from any project.

Subcommands:
  whoami                      identity + workspace + timezone sanity check
  projects [--search Q]       fuzzy-match projects, or list recently used ones
  recent [--limit N]          recent time entries (local times, descriptions)
  log ...                     create one time entry (the only write)
  delete --id ID              delete a time entry (undo a test write)

Exit codes:
  0 ok | 1 API error | 2 usage/config error | 3 refused (overlap)
"""

import argparse
import difflib
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

API = "https://api.clockify.me/api/v1"
KEY_FILE = Path.home() / ".claude" / ".clockify-api-key"

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# --------------------------------------------------------------------------
# timezone: Europe/Rome, with a dependency-free fallback
# --------------------------------------------------------------------------
# Windows Python often ships without the IANA database, so ZoneInfo can raise.
# The EU rule is simple enough to hardcode: CEST (+2) from the last Sunday of
# March 01:00 UTC to the last Sunday of October 01:00 UTC, CET (+1) otherwise.

try:
    from zoneinfo import ZoneInfo

    TZ = ZoneInfo("Europe/Rome")
except Exception:
    TZ = None


def _last_sunday(year, month):
    d = date(year, month, 31)  # only ever called for March and October
    while d.weekday() != 6:  # Monday=0 ... Sunday=6
        d -= timedelta(days=1)
    return d


def _offset_for_utc(dt_utc):
    y = dt_utc.year
    start = datetime.combine(_last_sunday(y, 3), datetime.min.time()) + timedelta(hours=1)
    end = datetime.combine(_last_sunday(y, 10), datetime.min.time()) + timedelta(hours=1)
    return 2 if start <= dt_utc.replace(tzinfo=None) < end else 1


def _offset_for_local(dt_local):
    y = dt_local.year
    start = datetime.combine(_last_sunday(y, 3), datetime.min.time()) + timedelta(hours=2)
    end = datetime.combine(_last_sunday(y, 10), datetime.min.time()) + timedelta(hours=3)
    return 2 if start <= dt_local < end else 1


def local_to_utc(naive_local):
    """Naive Europe/Rome datetime -> aware UTC datetime."""
    if TZ is not None:
        return naive_local.replace(tzinfo=TZ).astimezone(timezone.utc)
    return (naive_local - timedelta(hours=_offset_for_local(naive_local))).replace(
        tzinfo=timezone.utc
    )


def utc_to_local(dt_utc):
    """Aware UTC datetime -> naive Europe/Rome datetime."""
    if TZ is not None:
        return dt_utc.astimezone(TZ).replace(tzinfo=None)
    return (dt_utc + timedelta(hours=_offset_for_utc(dt_utc))).replace(tzinfo=None)


def parse_api_ts(s):
    """'2026-08-06T16:00:00Z' -> aware UTC datetime."""
    return datetime.strptime(s.replace("Z", ""), "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=timezone.utc
    )


def fmt_api_ts(dt_utc):
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# http
# --------------------------------------------------------------------------


def api_key():
    key = os.environ.get("CLOCKIFY_API_KEY")
    if key:
        return key.strip()
    if KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8").strip()
        if key:
            return key
    die(
        2,
        f"no API key: set $CLOCKIFY_API_KEY or write it to {KEY_FILE}",
    )


def die(code, msg):
    print(f"clockify: {msg}", file=sys.stderr)
    sys.exit(code)


def request(method, path, body=None, base=API):
    url = base + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-Api-Key", api_key())
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        hint = ""
        if e.code == 401:
            hint = "  (API key rejected — check the key, it may have been rotated)"
        elif e.code in (403, 400) and re.search(r"approv|lock", detail, re.I):
            hint = "  (that week looks submitted/approved — Clockify locks it; ask an admin to reopen)"
        elif e.code == 403:
            hint = "  (forbidden — the key may lack rights on this workspace)"
        die(1, f"HTTP {e.code} on {method} {path}\n{detail}{hint}")
    except urllib.error.URLError as e:
        die(1, f"network error on {method} {path}: {e.reason}")
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        die(1, f"non-JSON reply from {path}: {raw[:200]}")


# --------------------------------------------------------------------------
# identity / data
# --------------------------------------------------------------------------


def me():
    u = request("GET", "/user")
    return {
        "user_id": u["id"],
        "workspace_id": u.get("activeWorkspace") or u["defaultWorkspace"],
        "name": u.get("name"),
        "email": u.get("email"),
        "timezone": u.get("settings", {}).get("timeZone"),
    }


def all_projects(ws):
    out, page = [], 1
    while True:
        chunk = request(
            "GET",
            f"/workspaces/{ws}/projects?archived=false&page-size=200&page={page}",
        )
        if not chunk:
            break
        out.extend(chunk)
        if len(chunk) < 200:
            break
        page += 1
    return out


def entries(ws, uid, limit=50, start=None, end=None):
    q = f"?page-size={limit}"
    if start:
        q += f"&start={fmt_api_ts(start)}"
    if end:
        q += f"&end={fmt_api_ts(end)}"
    return request("GET", f"/workspaces/{ws}/user/{uid}/time-entries{q}") or []


# --------------------------------------------------------------------------
# fuzzy matching
# --------------------------------------------------------------------------


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def score(query, haystack):
    """How well a query matches "Project · Client".

    Token coverage dominates; whole-string similarity is only a tiebreaker.
    Weighting it any higher lets an unrelated project whose letters happen to
    line up ("PEC MANAGER" for "orange crm") outrank a real half-match.
    """
    q, h = norm(query), norm(haystack)
    if not q or not h:
        return 0.0
    if q in h:
        return 1.0
    words = h.split()

    def tok(t):
        if t in h:
            return 1.0
        best = max((difflib.SequenceMatcher(None, t, w).ratio() for w in words), default=0.0)
        return best if best >= 0.75 else 0.0  # typo tolerance, not free association

    toks = q.split()
    cov = sum(tok(t) for t in toks) / len(toks)
    ratio = difflib.SequenceMatcher(None, q, h).ratio()
    return cov * 0.85 + ratio * 0.15


def label(p):
    client = p.get("clientName") or "—"
    return f"{p['name']} · {client}"


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


def cmd_whoami(args):
    i = me()
    print(f"user       {i['name']} <{i['email']}>")
    print(f"user_id    {i['user_id']}")
    print(f"workspace  {i['workspace_id']}")
    print(f"timezone   {i['timezone']}  (script uses Europe/Rome, "
          f"{'zoneinfo' if TZ else 'built-in EU DST rule'})")
    return 0


def cmd_projects(args):
    i = me()
    projects = all_projects(i["workspace_id"])

    if args.search:
        ranked = sorted(
            ((score(args.search, label(p)), p) for p in projects),
            key=lambda t: -t[0],
        )[: args.limit]
        ranked = [(s, p) for s, p in ranked if s > 0.3]
        if not ranked:
            print(f"no project matches {args.search!r} among {len(projects)} active projects")
            return 0
        print(f"matches for {args.search!r}:")
        for s, p in ranked:
            print(f"  {s:.2f}  {p['id']}  {label(p)}")
        return 0

    by_id = {p["id"]: p for p in projects}
    seen = []
    for e in entries(i["workspace_id"], i["user_id"], limit=100):
        pid = e.get("projectId")
        if pid and pid in by_id and pid not in seen:
            seen.append(pid)
        if len(seen) >= args.limit:
            break
    print(f"recently used ({len(projects)} active projects total):")
    for pid in seen:
        print(f"  {pid}  {label(by_id[pid])}")
    return 0


def cmd_recent(args):
    i = me()
    by_id = {p["id"]: p for p in all_projects(i["workspace_id"])}
    for e in entries(i["workspace_id"], i["user_id"], limit=args.limit):
        if args.project_id and e.get("projectId") != args.project_id:
            continue
        ti = e["timeInterval"]
        s = utc_to_local(parse_api_ts(ti["start"]))
        end_raw = ti.get("end")
        en = utc_to_local(parse_api_ts(end_raw)).strftime("%H:%M") if end_raw else "…"
        proj = by_id.get(e.get("projectId"))
        print(
            f"{s:%d/%m} {s:%H:%M}-{en}  {label(proj) if proj else '(no project)'}"
            f"\n            {e.get('description') or ''}"
        )
    return 0


def cmd_log(args):
    i = me()
    ws, uid = i["workspace_id"], i["user_id"]

    try:
        d = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        die(2, f"--date must be YYYY-MM-DD, got {args.date!r}")
    try:
        sh, sm = [int(x) for x in args.start.split(":")]
        eh, em = [int(x) for x in args.end.split(":")]
    except ValueError:
        die(2, "--start/--end must be HH:MM")

    start_local = datetime.combine(d, datetime.min.time()).replace(hour=sh, minute=sm)
    end_local = datetime.combine(d, datetime.min.time()).replace(hour=eh, minute=em)
    if end_local <= start_local:
        die(2, f"end {args.end} is not after start {args.start} (no overnight entries)")

    desc = args.description.strip()
    if not desc:
        die(2, "--description is empty")

    project = None
    for p in all_projects(ws):
        if p["id"] == args.project_id:
            project = p
            break
    if project is None:
        die(2, f"no active project with id {args.project_id}")

    start_utc, end_utc = local_to_utc(start_local), local_to_utc(end_local)
    hours = (end_local - start_local).total_seconds() / 3600

    # overlap guard: look at the whole local day, generously padded
    if not args.allow_overlap:
        day_start = local_to_utc(datetime.combine(d, datetime.min.time()) - timedelta(hours=6))
        day_end = local_to_utc(datetime.combine(d, datetime.min.time()) + timedelta(hours=30))
        for e in entries(ws, uid, limit=100, start=day_start, end=day_end):
            ti = e["timeInterval"]
            if not ti.get("end"):
                continue
            es, ee = parse_api_ts(ti["start"]), parse_api_ts(ti["end"])
            if es < end_utc and start_utc < ee:
                ls, le = utc_to_local(es), utc_to_local(ee)
                die(
                    3,
                    f"overlaps an existing entry {ls:%d/%m %H:%M}-{le:%H:%M} "
                    f"— {e.get('description') or '(no description)'}\n"
                    f"        pass --allow-overlap if that is intentional",
                )

    line = (
        f"{start_local:%d/%m/%Y} {start_local:%H:%M}-{end_local:%H:%M} "
        f"({hours:g}h) · {label(project)} · {desc} · "
        f"{'fatturabile' if not args.no_billable else 'non fatturabile'}"
    )

    if args.dry_run:
        print("DRY RUN — nothing written")
        print(line)
        print(f"  as:  {i['name']} <{i['email']}>")
        print(f"  UTC: {fmt_api_ts(start_utc)} -> {fmt_api_ts(end_utc)}")
        return 0

    created = request(
        "POST",
        f"/workspaces/{ws}/time-entries",
        {
            "start": fmt_api_ts(start_utc),
            "end": fmt_api_ts(end_utc),
            "billable": not args.no_billable,
            "description": desc,
            "projectId": args.project_id,
        },
    )
    print("logged")
    print(line)
    print(f"  as: {i['name']} <{i['email']}>")
    print(f"  id: {created['id']}")
    return 0


def cmd_delete(args):
    i = me()
    request("DELETE", f"/workspaces/{i['workspace_id']}/time-entries/{args.id}")
    print(f"deleted {args.id}")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="clockify.py", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami").set_defaults(fn=cmd_whoami)

    p = sub.add_parser("projects")
    p.add_argument("--search", help="fuzzy query against project + client name")
    p.add_argument("--limit", type=int, default=6)
    p.set_defaults(fn=cmd_projects)

    p = sub.add_parser("recent")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--project-id")
    p.set_defaults(fn=cmd_recent)

    p = sub.add_parser("log")
    p.add_argument("--project-id", required=True)
    p.add_argument("--date", required=True, help="YYYY-MM-DD (local)")
    p.add_argument("--start", required=True, help="HH:MM (local)")
    p.add_argument("--end", required=True, help="HH:MM (local)")
    p.add_argument("--description", required=True)
    p.add_argument("--no-billable", action="store_true")
    p.add_argument("--allow-overlap", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_log)

    p = sub.add_parser("delete")
    p.add_argument("--id", required=True)
    p.set_defaults(fn=cmd_delete)

    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
