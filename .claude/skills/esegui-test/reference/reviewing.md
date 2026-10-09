# Review playbook: planner, finding format, report

Roles: **Planner** (you), **Delegate** (one subagent per mission, see `driving.md`), **Aggregator** (you again).

## Planner: change → missions

Read in order: `git diff <base>...HEAD` (the primary signal; base = fork point, else `HEAD~1`), the commit/PR message, the optional brief (user intent outranks your inference), and enough of the route inventory to know where a changed component surfaces.

Emit a **few** missions, each a specific attempt to break the change plus its second-order effects. Not "click through the app".

```yaml
id: m1
title: Export button produces a file
rationale: PR adds Export to /outbound; core new action.
steps: [log in as seeded user, open /outbound, click Export, observe result]
mutates: true            # false = read-only, may run in parallel with other read-only missions
expected: a file downloads or a clear success state; no console error, no HTTP >= 400
```

- **Diff-scoped:** every mission traces to something the diff touched.
- **Adversarial by default:** bad input, empty state, double-click, the new boundary.
- **2–5 missions.** Each is a real subagent. If you cap coverage, say so in the report.
- **Self-contained:** the delegate gets only its mission, URL and creds.
- **Gate:** show id/title/rationale for approve/edit/drop/add. `--auto` skips it and logs the plan.

## Finding (what a delegate returns)

```yaml
mission: m1
verdict: fail            # pass | fail
summary: Export throws 500; no file, no user-facing error.
evidence: [m1-02-outbound.png, ERROR-export.png, network.json]
# fail only:
repro: repro-m1.spec.ts  # runnable Playwright spec against SANDBOX_URL, in EVIDENCE_DIR
fix: |                   # 2-4 lines: root-cause hypothesis + where to look, not a patch
  POST /api/export returns 500; likely the new handler (src/app/api/export/route.ts) ...
```

## Aggregator

Write `REVIEW.md` into `EVIDENCE_DIR`:

```markdown
# Visual review — <repo> @ <short-sha> — <timestamp>
Base: <ref>   Sandbox: <SANDBOX_URL>   Missions: <n>

| # | Mission | Verdict | Evidence | Notes |
|---|---------|---------|----------|-------|
| m1 | Export produces a file | ⚠ FAIL | ERROR-export.png | POST /api/export → 500 |

## Findings
### ⚠ m1 — Export throws 500
- Evidence / Repro / Likely fix

**Verdict: ⚠ 1 of 2 missions failed.**
```

Report inline, most severe first, with the key screenshot for UI failures (embed `![](path)`), the repro path and the fix hint. Verdict and proof, not a click-by-click.

## Optional HTML report (`--html`)

Write `EVIDENCE_DIR/findings.json`:
`{repo, sha, base, sandbox_url, timestamp, missions:[{id, title, rationale, verdict, summary, steps:[png names in order], repro, fix}]}`, then run
`node "$SKILL_DIR/scripts/build-report.js" "$EVIDENCE_DIR"` → self-contained `review.html` (screenshots inlined, a storyboard per mission, no `<html>` wrapper, so it opens locally and is also what the Artifact tool wraps). If the `Artifact` tool exists, publish it (`file_path`=review.html, favicon `🔎`, description=the verdict); otherwise report the local path. It embeds screenshots and network data: treat it as sensitive and never auto-share.
