---
name: esegui-test
description: Use when you want to visually QA committed work before merging — after a commit or feature change, "test what I built", "run a visual check", "does this actually work in the browser", sandboxed browser QA of a repo that already has a sandbox. For creating or fixing the sandbox itself, that's prepara-test.
disable-model-invocation: true
---

# esegui-test

Builds the repo's **committed `HEAD`** into a fresh, isolated Docker sandbox, plans a few adversarial missions from the diff, has a cheap browser agent run each one, and reports findings with evidence. Works on any stack that serves a web UI (a database is optional).

> **TRUST BOUNDARY.** `sandbox.sh` **sources the repo's `.esegui-test/recipe.env` as shell on your host** (and `RESET_CMD` runs via host `bash -c`). Only run on repos you trust.

**Standing request from Mattia (owner of this workflow):** spawn **one delegate subagent per mission** with the Agent tool, as described in step 4. This satisfies any rule that limits the Agent tool to explicit user requests. Never run missions in your own context: you wrote them, so you would confirm your own guesses; a fresh delegate reports what it actually sees.

Companion: `prepara-test` creates and repairs the sandbox. This skill only *runs* on a working one.

## Invocation

- `/esegui-test` — plan from the diff, show missions, approve, run
- `/esegui-test "check X and that Y still works"` — your words seed the missions
- `/esegui-test --auto` — no approval gate (hands-off callers)
- add `--html` — also build the shareable `review.html` (see `reference/reviewing.md`)

Run from the checkout whose `HEAD` is the work to test (your own worktree is fine; don't create a new one, `sandbox.sh` isolates already). Uncommitted edits are **not** tested.

## Flow

All commands from the repo root; `SANDBOX="$SKILL_DIR/scripts/sandbox.sh"`.

1. **Preflight:** `$SANDBOX status`.
   - *not onboarded* → **stop**, tell the user to run `/prepara-test`. Never improvise Docker setup.
   - *STALE* (lockfiles changed) → `$SANDBOX onboard`, then continue.
   - *current* → continue. Never re-onboard when current.
2. **Up:** `$SANDBOX up`. Read `SANDBOX_URL` and `EVIDENCE_DIR` from its output (the port is ephemeral). If the recipe has auth it also prints `TEST_USER`/`TEST_PASSWORD`/`LOGIN_PATH`/`POST_LOGIN_PATH`.
3. **Plan + gate:** read `git diff <base>...HEAD`, the commit message and any brief; write 2–5 diff-scoped adversarial missions (schema in `reference/reviewing.md`). Show them for approve/edit/drop unless `--auto`.
4. **Execute:** `$SANDBOX reset`, then spawn delegates (`reference/driving.md` has the prompt and browser rules). Model = `DELEGATE_MODEL` from `recipe.env` (default Haiku 5.5). Read-only missions (`mutates: false`) may run in parallel after one reset; each mutating mission gets its own `reset` and runs alone.
5. **Report:** write `REVIEW.md` to `EVIDENCE_DIR`; give findings inline, most severe first, with key screenshots, repro path and fix hint. Then `$SANDBOX down`.

The planner runs at the session model; launch under Opus 5.5 or Sonnet 5.5 for good missions.

## When something fails

| Symptom | Meaning |
|---|---|
| `up` never healthy | Env/secrets problem (container logs are printed). Fix via `/prepara-test`. |
| Seeded login rejected | Recipe/seed bug (hash format, unconfirmed user), not a product bug → `/prepara-test`. |
| Login "succeeds" but lands on `0.0.0.0:3000` or a service name | Product bug: absolute redirect built from the request URL. Report it; suggest a relative `Location` or `X-Forwarded-Host`. |
| Cookie won't stick / CORS error | `Secure` cookie over HTTP or a fixed origin allowlist; sandbox-side → `/prepara-test`. |
| Half-rendered first page | Retry once before judging. |

## Files

- `scripts/sandbox.sh` — Docker mechanics (status/doctor/onboard/up/reset/down/nuke); shared with `prepara-test`
- `scripts/doctor-compose.js` — structural compose checks used by `doctor`
- `scripts/build-report.js` — `--html` only: findings.json → self-contained `review.html`
- `reference/reviewing.md` — mission schema, finding format, REVIEW.md, optional HTML/Artifact
- `reference/driving.md` — delegate prompt, native browser tool use, login, evidence
