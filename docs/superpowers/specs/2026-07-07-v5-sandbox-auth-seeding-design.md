# v5 — Sandbox Auth + DB Seeding (Phase 1 spec)

**Skill:** `bedigital-visual-tests`. **Scope of this doc:** Phase 1 only — the
local-Postgres / SHAPE B case. Phase 2 (local-Supabase stack) and Phase 3
(sanitized real-data snapshot) are designed in the roadmap memory but out of
scope here; each lands as its own PR.

Authoritative design: the `bedigital-visual-tests-roadmap` memory, v5 section
(co-designed with Mattia). This spec only fixes the *build plan* for Phase 1.

## Problem

Delegates can drive a browser but there is no defined way to **log in** to an
app that has auth, and no defined way to **populate** the throwaway sandbox DB
beyond whatever the Postgres image's `initdb` seed happens to do. v5 closes both
gaps for the local-Postgres case.

## Two workstreams

### A — Auth (arrive able to log in)

Default, library-agnostic path: the recipe holds **throwaway** creds
(`TEST_USER`/`TEST_PASSWORD`) that are sandbox-only and therefore safe to commit;
the seed inserts that user **already confirmed**; the delegate logs in through
the app's **real login form**. No session injection, no auth-library coupling.

Recipe additions (all optional; absent ⇒ no-auth app, unchanged behavior):

| Key | Meaning |
|-----|---------|
| `TEST_USER` | throwaway login identifier (email/username) the seed creates, confirmed |
| `TEST_PASSWORD` | throwaway password for that user |
| `LOGIN_PATH` | path to the login form, e.g. `/login` |
| `POST_LOGIN_PATH` | where a successful login lands (for the delegate to assert), optional |

`sandbox.sh up` echoes `TEST_USER` / `TEST_PASSWORD` / `LOGIN_PATH` /
`POST_LOGIN_PATH` alongside `SANDBOX_URL` (only the keys that are set), so the
planner can hand them to each delegate. Creds are throwaway and already in the
committed recipe, so echoing them is not a secret leak.

Docs: `driving-the-app.md` and `reviewing.md` gain a short "logging in" section —
where the creds are, use the **seeded** user, **never real creds**, and treat
"login form present but seeded user rejected" as a recipe/seed bug, not a
product bug.

### B — DB seeding (populate the throwaway DB)

Recipe selects a strategy:

| `SEED_STRATEGY` | Behavior (Phase 1) |
|-----------------|--------------------|
| unset / `initdb` | today's behavior — Postgres image `/docker-entrypoint-initdb.d` only |
| `migrations` | run `MIGRATE_CMD` (repo's migration tool) against the throwaway DB, then optional `SEED_CMD` |
| `synthetic` | run `SEED_CMD` (fake data + the confirmed test user) against the throwaway DB |

`MIGRATE_CMD` / `SEED_CMD` run **in-container** as a one-shot on the sandbox
network (`docker compose run --rm`), never on the host. The throwaway
`DATABASE_URL` is the only DB they can reach; real/VPS secrets never enter the
sandbox (that is a hard rule carried from the roadmap and enforced by only
injecting throwaway env into the sandbox compose).

## Where seeding runs in the lifecycle

A new internal `run_seed` step, invoked in **both** `up` (after the DB is healthy,
before the app health-gate) and `reset` (after the data services are recreated).
This keeps every mission starting from the same seeded slate, matching v2's
reset contract.

- SHAPE B default (`initdb`): `run_seed` is a no-op — the anonymous-volume drop +
  image initdb already reseeds. Fully backward-compatible with existing recipes.
- `migrations` / `synthetic`: `run_seed` runs `MIGRATE_CMD` then `SEED_CMD` via
  `docker compose run --rm` against a seeding service (or the app image) on the
  sandbox network, with `DATABASE_URL` pointing at the throwaway Postgres.

### Seeding service

To run a migration/seed command in-container we need an image that has the repo's
tooling + code. Two supportable forms, recipe-selected via `SEED_SERVICE`:

- **`SEED_SERVICE=<app service>`** (default when a strategy is set): reuse the
  already-built app image via `docker compose run --rm --no-deps <app> sh -lc
  "$MIGRATE_CMD && $SEED_CMD"`. Works when migrations/seed are runnable from the
  app image (the common Prisma/Knex/Drizzle case — the CLI is a dep).
- A dedicated seed service defined in `sandbox.compose.yml` for repos whose
  tooling isn't in the app image.

Commands are recipe-authored strings; they run in-container, so the host trust
boundary is unchanged (still: only run this skill on repos you trust, because
`recipe.env` is sourced on the host — that caveat already exists).

## Reset interaction

`reset` currently, for SHAPE B, drops+recreates the data services so initdb
reseeds. With a strategy set, after recreate it must also re-run `run_seed`
(migrations are gone with the dropped volume). So `reset` = recreate data
services → `run_seed`. `RESET_CMD` (SHAPE A custom) still fully overrides and is
responsible for its own reseed, unchanged.

## Dogfood target — extend `visual-test-demo`

Add a minimal auth gate to prove the whole flow:

- `users` table + a confirmed test user in `seed.sql` (bcrypt-free: store a
  SHA-256 hash to avoid adding a dep — this is a throwaway demo credential).
- `/login` page (form) + `/api/login` route: verify credentials against Postgres,
  set an httpOnly session cookie (`Secure=false` so it sticks over sandbox HTTP).
- `middleware.ts` gating `/` and `/widgets` → redirect to `/login` when no valid
  session cookie; `/api/health` and `/login`/`/api/login` stay public.
- Recipe gains `TEST_USER`/`TEST_PASSWORD`/`LOGIN_PATH`/`POST_LOGIN_PATH`.
- Keep `SEED_STRATEGY` unset (the demo seeds via initdb) so the demo also
  exercises the backward-compatible path. (A follow-up commit can flip it to
  `migrations` to exercise strategy (a), but Phase 1's must-have is auth + the
  generic hook existing and being backward-compatible.)

Dogfood run: `onboard` (rebuild base — new dep? no, SHA-256 is stdlib) → `up` →
a delegate that loads `/widgets` unauthenticated (expect redirect to `/login`),
logs in with seeded creds, reaches `/widgets` authed and sees the widget list →
screenshots at each step → `reset` → confirm still logged-out after reset →
`down`. Evidence: screenshots proving the redirect, the filled login form, and
the post-login authed page.

## Non-goals (Phase 1)

- Supabase local stack + `auth.admin.createUser` (Phase 2).
- storageState / cookie-injection fallback (only after form-login proven; Phase 2+).
- Sanitized real-data snapshot + masking (Phase 3).
- Remote/VPS-Postgres → local-replica repointing (the *mechanism* — throwaway
  `DATABASE_URL` + in-container seed — is laid here; the onboarding detection for
  it is documented but a repo-specific concern).

## Verification

- `bash -n scripts/sandbox.sh`; `node --check scripts/build-report.js`.
- Real dogfood run against the extended demo showing a login actually happening
  and an auth-gated page verified with a screenshot (evidence, not assertion).
