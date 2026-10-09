---
name: prepara-test
description: Use when a repo needs its visual-test sandbox created or fixed — first time on a repo, esegui-test reports "not onboarded", the recipe or base image is broken, the sandbox never goes healthy, the app's service shape changed, or the onboarding must be redone from scratch.
disable-model-invocation: true
---

# prepara-test

> **TRUST BOUNDARY.** The recipe you author (`.esegui-test/recipe.env`) is later **sourced as shell on the host** by `sandbox.sh`, and `RESET_CMD` runs via host `bash -c`. Only onboard repos you trust, and put only throwaway values in the recipe: never real secrets or a real `DATABASE_URL`.

Goal: leave the repo so `/esegui-test` works first try: a committed recipe + sandbox compose, a built base image, and a verified-healthy smoke boot. This skill also owns **repair** (recipe drift, broken seeds, new service shape). It works for any stack that serves a web UI; Supabase and real-data snapshots are optional add-ons.

## Use when / not

Use: first time on a repo; `esegui-test` says "not onboarded"; `up` never healthy; seeded login rejected; `doctor` FAILs; app shape changed; from-scratch redo (`nuke`).
Not: repo healthy and you just want to test → `/esegui-test`. `status` says STALE (only lockfiles changed) → `esegui-test` rebuilds inline.

## Scripts live in the sibling skill

```bash
ESEGUI_DIR="$SKILL_DIR/../esegui-test"
"$ESEGUI_DIR/scripts/sandbox.sh" {status|doctor|onboard|up|down|nuke}   # from the target repo root
```

`doctor` = static check (no build); `onboard` = build base image; `up`+`down` = smoke test; `nuke` = wipe base image + stamp.

## First-time onboard (playbook: `reference/onboarding.md`)

1. **Find the web surface:** what single URL does the browser hit, and does the app produce it from a clean checkout? Pick a shape (`templates/README.md`): no-db, single-web-db, split-web-api-db, or existing-compose-override.
2. **Author** `recipe.env` (from `templates/recipe.env.example`, ~8 core keys) + `sandbox.compose.yml` into the target repo's `.esegui-test/`. Add auth (`TEST_USER`/…) and seeding (`SEED_STRATEGY`) only if the app needs them. Optional add-ons: `addons/supabase/` (Supabase apps), `addons/snapshot/` (masked real data).
3. **Confirm the recipe with the user before building.** Always.
4. **`doctor`**, fix every FAIL. Secrets are the #1 blocker: inject throwaway values for everything the app needs to boot.
5. **`onboard`** (slow, once), then **smoke-verify**: `up`, confirm `SANDBOX_URL` answers (and login works if configured), `down`.
6. **Commit** everything the compose references, not just the recipe. `up`/`onboard` build from a committed-HEAD worktree and overlay only `recipe.env`, `sandbox.compose.yml`, `Dockerfile.*`, `.dockerignore`; any other bind-mount source must exist at HEAD or Docker makes an empty directory. Iterate uncommitted, commit before the real `up`.
7. Hand off: *"onboarded — run `/esegui-test`."*

## Repair

| Symptom | Action |
|---|---|
| `up` never healthy | Read the container logs; usually a missing boot secret/env → throwaway value in the compose. |
| `db` exits: `Is a directory` | A bind-mounted file isn't committed at HEAD. Commit it. |
| `up`'s image build can't reach the DB | The framework prerenders data pages at build time. Run the dev server instead of a prod build (see `addons/supabase/README.md` for the pattern). |
| Seeded login rejected | Recipe bug: wrong hash format, unconfirmed user, or `Secure` cookie over HTTP (`onboarding.md` §5). |
| `doctor` FAILs | Fix what it names. |
| Service shape changed | Re-author recipe/compose, `doctor`, `onboard`, smoke-verify. |
| Wrong from the start | `nuke`, then first-time flow. |

## Files

- `reference/onboarding.md` — the playbook: shapes, recipe, secrets, auth, seeding, compose gotchas
- `templates/` — `README.md` (shape picker), `recipe.env.example`, compose/Dockerfile examples, `single-web-db/`, `split-web-api-db/`
- `addons/supabase/` — local Supabase stack in the sandbox (only for Supabase apps)
- `addons/snapshot/` — opt-in PII-masked real-data snapshot (sensitive; read its README first)

Run-time work (missions, browser, reports) lives in **`esegui-test`**.
