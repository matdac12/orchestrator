---
name: bedigital-visual-tests
description: Use when you want to visually QA work you just built before merging — spin the app up in an isolated Docker sandbox and drive a real browser through it to capture screenshot evidence. Triggers: after a commit or feature change, "test what I built", "run a visual check", "does this actually work in the browser", per-change ephemeral test environment, sandboxed browser QA of a repo.
---

# bedigital-visual-tests

> **TRUST BOUNDARY — read before running on a repo you didn't write.** This skill executes the target repo's **committed `.bedigital-visual-tests/recipe.env` as a shell script on your host** (`sandbox.sh` does `source recipe.env`), and its `RESET_CMD` runs via `bash -c` on the host too — neither is sandboxed inside Docker. Only the app code is isolated; the recipe is not. A malicious recipe could run arbitrary commands on your machine. **Only run this skill on repositories you trust.** (Safer for untrusted repos: run reset in-container, and review `recipe.env` before the first `up`.)

## Overview

Spin the repo you're working on up in a **fresh, isolated Docker sandbox** built from your **committed** code, then drive a **real browser** through it to visually verify what you built — capturing screenshots, console, and network as evidence.

**Core principle:** onboard a repo **once** (build a base image with all dependencies baked in), then every subsequent run reuses that base and boots a disposable sandbox in seconds. You test a reproducible build of what will merge, not your live working tree.

On each run the skill **reads what changed**, decides a few **targeted adversarial missions** (tied to the diff, optionally steered by a spec/plan brief), delegates **one browser-driving agent per mission**, and aggregates findings — each failure with a runnable repro + a short fix suggestion. You approve the mission list before it runs (unless `--auto`).

## When to Use

- After a commit / finishing a feature, before opening a PR — "does this actually work in the browser?"
- You want repeatable, isolated browser QA of a repo without hand-rolling Docker each time
- You want screenshot/console/network evidence of a flow working (or breaking)

**Invocation** (single command — no subcommands, no modes):
- `/bedigital-visual-tests` → plan missions from the diff, show them, approve, run
- `/bedigital-visual-tests "check X and that Y still works"` → your words seed the missions
- `/bedigital-visual-tests --auto` → plan + run with no approval gate, report at the end (for hands-off callers)

**When NOT to use:**
- Pure unit/logic testing with no runtime UI → just run the test suite
- You need to test uncommitted scratch edits live with HMR → that's `next dev`, not this (this builds committed code on purpose)

## The one decision that matters: onboarded or not?

```dot
digraph d {
  rankdir=TB; node [shape=box];
  q1 [shape=diamond, label="Does .bedigital-visual-tests/recipe.env exist\nAND its base image is present?"];
  q2 [shape=diamond, label="Lockfile hash changed\nsince the base was built?"];
  onboard [label="ONBOARD (first time):\ndetect stack, author recipe,\nconfirm with user, build base image"];
  rebuild [label="Rebuild base image\n(deps changed)"];
  test [label="Spin sandbox → plan missions →\ngate → delegate → aggregate"];
  q1 -> onboard [label="no"];
  q1 -> q2 [label="yes"];
  q2 -> rebuild [label="yes"];
  q2 -> test [label="no  (fast path)"];
  onboard -> test;
  rebuild -> test;
}
```

`scripts/sandbox.sh status` answers this for you. Never re-onboard when already onboarded and the lockfiles are unchanged — that throws away the whole point (reusing the baked base).

## Quick Reference

All commands run from the target repo root. `SKILL_DIR` = this skill's directory.

| Goal | Command |
|------|---------|
| Is this repo onboarded? / is the base current? | `"$SKILL_DIR/scripts/sandbox.sh" status` |
| First-time onboard (after you've authored the recipe) | `"$SKILL_DIR/scripts/sandbox.sh" onboard` |
| Spin a fresh isolated sandbox, print its URL | `"$SKILL_DIR/scripts/sandbox.sh" up` |
| Restore a clean seeded DB between missions (recreate data → migrate → seed → restart app → re-gate health) | `"$SKILL_DIR/scripts/sandbox.sh" reset` |
| Tear down THIS run's sandbox | `"$SKILL_DIR/scripts/sandbox.sh" down` |
| Remove the base image too (force re-onboard) | `"$SKILL_DIR/scripts/sandbox.sh" nuke` |

`up` prints `SANDBOX_URL=http://localhost:<port>` and `EVIDENCE_DIR=...` — read both from its output; the host port is **ephemeral per run** (never assume 3000).

## Workflow

### 1. Onboard (first time on a repo only)

Follow `reference/onboarding.md`. In short: detect the stack via the signal ladder (existing `docker-compose.yml`/`devcontainer.json`/`Dockerfile` win → lockfile picks the package manager → marker files pick the runtime → scripts infer build/start → else ask), then **write the recipe** into the target repo and **confirm it with the user before building**:

- `.bedigital-visual-tests/recipe.env` — sourced by the scripts (app service, container port, health path, lockfile globs, optional base compose to layer under).
- `.bedigital-visual-tests/sandbox.compose.yml` — the sandbox definition: either a **sanitizing override** layered on the repo's existing compose, or a self-contained compose that builds from `templates/Dockerfile.base.example`.
- Commit `recipe.env` + `sandbox.compose.yml`. `.bedigital-visual-tests/evidence/` is gitignored.

Then run `sandbox.sh onboard` to build the base image. **Secrets are the #1 real blocker** — if the app needs vault keys / JWT / API keys to boot, record them in the recipe and inject throwaway values; the health-gate will otherwise hang. See `reference/gotchas.md`.

### 2. Spin the sandbox

`sandbox.sh up`. It builds from your **committed** code (a detached git worktree of `HEAD`, so uncommitted edits are excluded), uses a **unique project name per run** and an **ephemeral host port** (so runs never collide), waits on the health check, and prints `SANDBOX_URL` + `EVIDENCE_DIR`.

### 3. Plan → gate → execute → report

The autonomous review flow. Full playbook in **`reference/reviewing.md`**; in short:

- **PLAN** (you, the agent running the skill — the *planner*): read `git diff <base>...HEAD` + the commit/PR message + repo routes + the optional brief, and produce a few **targeted adversarial missions** (each tied to the diff). Mission schema + rules are in `reference/reviewing.md`.
- **GATE**: interactive by default — show the mission list, let the user approve/edit/drop/add. With `--auto`, skip and proceed. (This *is* how you steer — there's no separate guided mode.)
- **EXECUTE** (sequential, one mission at a time): `sandbox.sh reset` (clean seeded DB) → spawn **one delegate subagent** (model = recipe `DELEGATE_MODEL`, default Sonnet 5) with the mission + `SANDBOX_URL` + `EVIDENCE_DIR` → it drives agent-browser per `reference/driving-the-app.md` and returns a finding (pass → evidence; fail → evidence + runnable repro + short fix suggestion).
- **AGGREGATE**: write `REVIEW.md` (agent-facing) into `EVIDENCE_DIR`, then build a self-contained **`review.html`** (screenshots inlined, a storyboard per mission) via `scripts/build-report.js` and **publish it as a shareable Artifact** when the `Artifact` tool is available — see `reference/reporting.md`. Report inline, findings ranked most-severe first, with the artifact link.

**Model policy:** the planner runs at the *session* model (launch the skill under Opus for good missions); delegates are spawned as `DELEGATE_MODEL` subagents. Both set in `recipe.env`.

### 4. Tear down

`sandbox.sh down`. The base image stays cached for next time.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Re-onboarding / rebuilding deps every run | Check `status` first; reuse the base image. Rebuild only on lockfile-hash change. |
| Assuming the app is on port 3000 | Read `SANDBOX_URL` from `up` — the host port is ephemeral per run. |
| Reusing the repo's compose as-is | Layer the sanitizing override: ephemeral ports, throwaway env, drop dev-only services, no host bind-mounts. See `reference/gotchas.md`. |
| Testing the working tree instead of committed code | `up` builds from a detached `HEAD` worktree by design. Commit first. |
| Browser can't log in / blank network tab | Seeded test user + `AUTH_COOKIE_SECURE=false` over HTTP + CORS allows the sandbox origin. |
| App never goes healthy | Almost always missing secrets/env. Read the container logs; inject throwaway secrets in the recipe. |
| Driving a browser *inside* a container to `http://<service>:<port>` | Chromium force-upgrades single-label hosts to HTTPS → `ERR_SSL_PROTOCOL_ERROR`. Use a dotted alias, or (default) drive from the host against the published port. |
| Running missions in parallel | They share one app + DB and would corrupt each other. Run sequentially with `sandbox.sh reset` between them. |
| A broad mission list "to be thorough" | Missions must be diff-scoped and few (2–5). Each is a real subagent + wall-clock. Tie every mission to the change. |
| Skipping `reset` between missions | Adversarial missions mutate state; the next mission then starts dirty. Always `reset` first. |

## Files

- `scripts/sandbox.sh` — deterministic Docker mechanics (status/onboard/up/reset/down/nuke)
- `scripts/build-report.js` — Node (no deps): findings.json + evidence → self-contained `review.html`
- `templates/recipe.env.example` — the recipe schema, documented (incl. model policy + reset)
- `templates/sandbox.compose.example.yml` — sanitizing-override + self-contained examples
- `templates/Dockerfile.base.example` — fallback base image when the repo has no Docker assets
- `reference/onboarding.md` — stack detection signal ladder + authoring the recipe + secrets
- `reference/reviewing.md` — the review-mode playbook: planner (diff → missions), delegate (drive + repro + fix), aggregator (REVIEW.md)
- `reference/reporting.md` — the rich report: findings.json → `review.html` (inlined screenshots + storyboard) → published Artifact
- `reference/driving-the-app.md` — agent-browser usage + evidence conventions + REPORT.md format
- `reference/gotchas.md` — hard-won failure modes and their fixes
