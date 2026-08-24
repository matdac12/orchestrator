---
name: prepara-test
description: Use when a repo needs its visual-test sandbox created or fixed — first time on a client repo, esegui-test reports "not onboarded", the recipe or base image is broken, the sandbox never goes healthy, the app's service shape changed, or the onboarding must be redone from scratch.
disable-model-invocation: true
---

# prepara-test

> **TRUST BOUNDARY.** The recipe you author here (`.bedigital-visual-tests/recipe.env`) is later **sourced as a shell script on the host** by `sandbox.sh`, and `RESET_CMD` runs via host `bash -c`. Only author/onboard repositories you trust, and never put real secrets or a real `DATABASE_URL` in the recipe — throwaway values only.

**REQUIRED COMPANION:** the `esegui-test` skill runs the actual browser QA. This skill's single goal is to leave the repo in a state where `/esegui-test` works first try: a committed recipe + sandbox compose, a built base image, and a verified-healthy smoke boot.

## Overview

Onboard a repo **once** into the visual-test system: detect the stack, author the recipe around the app's **web surface**, build a base Docker image with all dependencies baked in (tagged by lockfile hash), and verify the sandbox actually boots healthy. Every later `/esegui-test` run reuses that base and boots in seconds.

This skill also owns **repair**: whenever the environment stops working — recipe drift, broken seeds, secrets changes, a new service shape — fix it here, not mid-test-run.

## When to Use

- First time on a (client) repo — no `.bedigital-visual-tests/` yet
- `esegui-test` stopped with "not onboarded — run /prepara-test"
- The sandbox is broken: `up` never goes healthy, the seeded login is rejected, `doctor` FAILs
- The app's shape changed (e.g. a separate API service appeared) → re-author the recipe
- A bad onboarding needs a from-scratch redo (`nuke`, then onboard again)

**When NOT to use:**
- The repo is onboarded and healthy and you just want to test → `/esegui-test`
- `status` says STALE (only the lockfiles changed) → `esegui-test` rebuilds that inline; no re-authoring needed

## Scripts live in the sibling skill

The deterministic mechanics are shared with `esegui-test` and live there (single source of truth):

```bash
ESEGUI_DIR="$SKILL_DIR/../esegui-test"   # sibling skill directory
"$ESEGUI_DIR/scripts/sandbox.sh" <subcommand>
```

References to `gotchas.md` inside this skill's docs resolve to `$ESEGUI_DIR/reference/gotchas.md`.

## Quick Reference

All commands run from the target repo root.

| Goal | Command |
|------|---------|
| Where does this repo stand? | `"$ESEGUI_DIR/scripts/sandbox.sh" status` |
| Static preflight: validate recipe + compose (no build) | `"$ESEGUI_DIR/scripts/sandbox.sh" doctor` |
| Build the base image (after authoring the recipe) | `"$ESEGUI_DIR/scripts/sandbox.sh" onboard` |
| Smoke-verify the environment (boot + health) | `"$ESEGUI_DIR/scripts/sandbox.sh" up` … then `down` |
| Wipe base image + stamp for a from-scratch redo | `"$ESEGUI_DIR/scripts/sandbox.sh" nuke` |

## Workflow: first-time onboard

Follow **`reference/onboarding.md`** — it is the playbook. The spine:

1. **Onboard around the web surface** — *what single URL does the browser hit, and does the app already produce it from a clean checkout?* Pick one of the four shapes (`single-web-no-db`, `single-web-db`, `split-web-api-db`, `existing-compose-override`); starters in `templates/` (see `templates/README.md`). An existing `docker-compose.yml` does NOT mean it serves the browser-facing app.
2. **Author the recipe** into the target repo's `.bedigital-visual-tests/`: `recipe.env` (from `templates/recipe.env.example`) + `sandbox.compose.yml` (sanitizing override or self-contained). If the app has **auth** or needs **seeding beyond initdb**, fill the auth block (`TEST_USER`/`TEST_PASSWORD`/`LOGIN_PATH` — the seed creates that user *confirmed*) and `SEED_STRATEGY` (+ in-container `MIGRATE_CMD`/`SEED_CMD`). **Supabase apps:** run a local Supabase stack inside the sandbox — `reference/supabase.md`. **Real data:** only via the PII-masking snapshot — `reference/snapshot.md`.
3. **Confirm the recipe with the user before building.** Always.
4. **`doctor`** — fix every FAIL (it runs again inside `onboard` and blocks on FAIL). Secrets are the #1 real blocker: inject throwaway values for everything the app needs to boot.
5. **`onboard`** — builds the base image from committed HEAD, stamps the lockfile hash. Slow, once.
6. **Smoke-verify** — `up`, confirm `SANDBOX_URL` answers (and the test login works if auth is configured), then `down`. Only now is the job done.
7. **Commit EVERYTHING the compose references** into the target repo — not just `recipe.env` + `sandbox.compose.yml` (+ Dockerfiles), but every bind-mount source: `schema.sql`, `seed.sql`, `supabase/*.sql`, `gateway.conf`, seed scripts. `up`/`onboard` build from a **committed-HEAD worktree** and only overlay `recipe.env`, `sandbox.compose.yml`, `Dockerfile.*`, `.dockerignore` uncommitted. Anything else the compose mounts but that is **absent from HEAD** makes Docker create an **empty directory** at the mount target → psql dies with `could not read from input file: Is a directory` and the `db` service exits (1). So: author, smoke-verify uncommitted (the overlaid files iterate fine), then commit the rest *before the real* `up`. Then hand off: *"onboarded — run `/esegui-test` to test."*

## Workflow: repair / re-onboard

| Symptom | Action |
|---------|--------|
| `up` never goes healthy | Read the container logs. Almost always a missing boot secret/env → add a throwaway value in the recipe/compose (see `gotchas.md` in `$ESEGUI_DIR/reference/`). |
| `db` exits (1): `could not read ...: Is a directory` | A bind-mounted file (`schema.sql`/`seed.sql`/`supabase/*.sql`) is **not committed at HEAD**. `up` builds from the HEAD worktree; a missing mount source becomes an empty dir. Commit the file. |
| App builds locally but `up`'s image build fails reaching the DB | The framework prerenders data-fetching pages at build time (`next build`, SSG/ISR), but the sandbox DB/gateway isn't reachable during `docker build` and runtime-only secrets aren't build args. Run the **dev server** instead — see `reference/supabase.md`. |
| Seeded login rejected | Recipe bug, not a product bug: wrong password-hash format, unconfirmed user, or cookie `Secure` over HTTP. See `reference/onboarding.md` §5a. |
| `doctor` FAILs after repo changes | Fix what it names (uncommitted lockfiles/env_files, missing services, fixed `container_name`, bind-mounts). |
| App gained/changed services (new API, new DB) | Re-author: possibly a different shape/template. Update recipe + compose, `doctor`, `onboard`, smoke-verify. |
| Onboarding was wrong from the start | `nuke` (drops base image + stamp), then run the first-time flow again. |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Building before the user confirmed the recipe | The confirmation gate is part of the contract — recipes encode judgment calls (ports, health path, secrets, seed). |
| Skipping the smoke `up` after `onboard` | "It built" ≠ "it boots healthy". Verify, then hand off. |
| Real secrets / real `DATABASE_URL` in the recipe | Throwaway values only; replicate remote DBs locally. Real data ONLY via `reference/snapshot.md`'s masking pipeline. |
| Re-onboarding when only deps changed | That's the STALE case — `esegui-test` handles the rebuild inline. This skill is for authoring/repair. |
| Pointing the sandbox at a real Supabase project | Run the LOCAL Supabase stack in the sandbox (`reference/supabase.md`). Adversarial missions mutate and reset data. |
| Assuming the repo's compose serves the browser surface | Verify the surface first; pick the shape from what the browser hits, not from which files exist. |
| Leaving `schema.sql`/`seed.sql`/support files uncommitted | Only `recipe.env`/compose/`Dockerfile.*`/`.dockerignore` are overlaid uncommitted; everything else the compose mounts must be committed at HEAD or Docker mounts an empty dir (see the repair table). |
| App lives in a subdirectory (monorepo) | `.bedigital-visual-tests/` still sits at the **git root** (where `sandbox.sh` runs); the Dockerfiles `COPY <subdir>/…` and `LOCKFILES` is root-relative (`web/app/package-lock.json`). Add a whitelist `.dockerignore` so the repo-root build context stays small. |
| Windows: init `.sql`/scripts checked out as CRLF | Commit `.bedigital-visual-tests/.gitattributes` with `* text eol=lf` — CRLF breaks psql `\set … \`echo\`` backtick meta-commands and script shebangs inside the Linux containers. |

## Files

- `reference/onboarding.md` — THE playbook: surface-first shapes, recipe authoring, doctor, secrets, auth (§5a) + seeding (§5b)
- `reference/supabase.md` — local-Supabase-in-sandbox: stack, confirmed-user seed via admin API, the NEXT_PUBLIC/ephemeral-port trap → server-side auth
- `reference/snapshot.md` — sanitized real-data snapshot: OPT-IN masking guardrails (read-only pull, mask PII before it lands, runtime load, scoped)
- `templates/README.md` — the four surface-typed shapes → which template to start from
- `templates/single-web-db/`, `templates/split-web-api-db/` — fill-in-the-blanks recipe + compose scaffolds
- `templates/recipe.env.example` — the recipe schema, documented (auth block, seed strategies, model policy)
- `templates/sandbox.compose.example.yml`, `templates/Dockerfile.base.example`, `templates/Dockerfile.sandbox.example` — compose/Dockerfile starting points
- `templates/supabase.sandbox.compose.example.yml` + `templates/supabase/` + `templates/seed-supabase-user.mjs` — the Supabase sandbox stack
- `templates/snapshot-and-mask.mjs` + `templates/snapshot.config.example.json` — the read-only, PII-masking snapshot tool + config schema

Run-time material (mission planning, browser driving, reporting, `sandbox.sh` itself) lives in the **`esegui-test`** sibling skill.
