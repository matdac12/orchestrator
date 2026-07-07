# Onboarding a repo

First time only. Goal: produce a committed recipe the scripts can drive, then build the base image once. **Confirm the recipe with the user before building anything.**

> **TRUST BOUNDARY.** `sandbox.sh` **sources `recipe.env` as a shell script on your host**, and `RESET_CMD` runs through `bash -c` on the host — not inside Docker. Only the app code is sandboxed; the recipe is executed with your user's privileges. A committed recipe from an untrusted repo can therefore run arbitrary commands on your machine. **Only onboard/run repositories you trust.** For untrusted code, read `recipe.env` first and prefer running the reseed **in-container** (a compose `run` against the DB service) over a host-side `RESET_CMD`.

## 1. Detect the stack — signal ladder (stop at the first that applies)

1. **Explicit config wins.** `docker-compose.yml` / `compose.yaml` → reuse it (SHAPE A override). `devcontainer.json` → honor its image/build/postCreate. A `Dockerfile` → reuse as the app image.
2. **Lockfile picks the package manager** — never guess. `pnpm-lock.yaml`→pnpm, `package-lock.json`→npm, `yarn.lock`→yarn, `bun.lockb`→bun; `uv.lock`→uv, `poetry.lock`→poetry, `requirements.txt`→pip; `go.mod`, `Cargo.toml`, etc.
3. **Marker files pick the runtime/version.** `engines`/`packageManager` in package.json, `.nvmrc`, `.python-version`, `go.mod` version.
4. **Scripts / framework config infer build & start.** `package.json` scripts (`build`, `start`, `dev`), `next.config.*`, framework defaults (Next→3000, Vite preview→4173, Express→often 3000/4000/8000).
5. **Find the data + env contract.** ORM/migrations (`prisma/`, `alembic`, `knexfile`, `drizzle.config`) and their migrate+seed commands; `.env.example` lists every required variable; note the **connection string var** (usually `DATABASE_URL`).
6. **Fallback: ask the user.** If any of the above is ambiguous, ask — don't guess build/start/health.

## 2. Author the recipe (into the target repo's `.bedigital-visual-tests/`)

- `recipe.env` — from `templates/recipe.env.example`. Set `APP_SERVICE`, `APP_PORT`, `HEALTH_PATH`, `LOCKFILES` (list EVERY lockfile), and `BASE_COMPOSE` if reusing an existing compose.
- `sandbox.compose.yml` — from `templates/sandbox.compose.example.yml`:
  - **Repo has compose → SHAPE A override:** ephemeral ports (`"0:<port>"`), throwaway env/secrets, drop host source bind-mounts (test the built image), disable dev-only services via `profiles`. **Critical — Compose CONCATENATES `ports`/`volumes` across files; it does not replace them.** A bare `ports: []` / `volumes: []` in the override does NOT remove the base's entries, so the base's host bind-mount and published DB ports survive and the sandbox is not actually sanitized. Use the reset/override tags (Compose 2.24+): `volumes: !reset []` to drop inherited bind-mounts, and `ports: !override ["0:<port>"]` (or `ports: !reset []` for a service that shouldn't publish at all). Two more easy-to-miss items: (a) if the base sets a fixed **`container_name`** on any service, override it to `container_name: bdvt-${BDVT_RUN}-<svc>` — fixed names are global and break per-run isolation; (b) for every **`env_file`** the base declares, ensure a throwaway **stub file** exists at that path (an override can't remove it and compose errors if it's missing).
  - **No compose → SHAPE B self-contained:** also add `Dockerfile.base` (from `templates/Dockerfile.base.example`) and `Dockerfile.sandbox` (`FROM ${BASE_IMAGE}`), plus a `.dockerignore` excluding `node_modules`, build output, `.env`, `.git`, and `.bedigital-visual-tests/evidence`.
- Add `.bedigital-visual-tests/evidence/` and the gitignored state files to the repo's `.gitignore`:
  ```
  .bedigital-visual-tests/evidence/
  .bedigital-visual-tests/.base.hash
  .bedigital-visual-tests/.last-run
  .bedigital-visual-tests/.runs/
  ```
- **Commit `recipe.env` + `sandbox.compose.yml` (+ Dockerfiles).** The recipe may be iterated uncommitted (`up` copies it into the HEAD worktree), but the app code it builds is always committed HEAD.

## 3. Health check must be real

Prefer an endpoint that proves the app AND its dependencies are up (e.g. one that touches the DB). If the app has none, add `HEALTH_PATH=/` and accept a weaker signal, or point at a lightweight route that renders server-side.

## 4. Secrets — the #1 reason a sandbox never goes healthy

Many apps refuse to boot without secrets (JWT/RSA keys, vault master keys, API keys). During onboarding:
- Read `.env.example` and the startup code for required secrets.
- Put **throwaway** values in the `environment:` of `sandbox.compose.yml` (or generate ephemeral ones in a one-shot init service). Never depend on the developer's real `.env`.
- If a secret must be generated (e.g. an RSA keypair), record the exact generation command in the recipe as a comment so it's reproducible.

## 5. Auth & DB seeding (v5) — arrive logged-in, with data

Two optional recipe blocks. Skip both for a public, no-auth, initdb-seeded app
(behavior is then exactly pre-v5).

### 5a. Auth — the delegate must be able to log in

Detect during onboarding whether the app gates pages behind a login. If it does,
the **default, library-agnostic path** is: seed a **confirmed** throwaway test
user, and let the delegate log in through the app's **real login form**. In the
recipe set `TEST_USER` / `TEST_PASSWORD` (throwaway, sandbox-only → safe to
commit — **never a real user's creds**), `LOGIN_PATH`, and optionally
`POST_LOGIN_PATH` (where a good login lands, so the delegate can assert it).
`sandbox.sh up` echoes these so the planner passes them to each delegate.

The seeded user must be created **already confirmed** (no email-verification
step), because the delegate can't click a confirmation link. How you seed it
depends on the app's auth family:

- **Local-Postgres auth (this phase):** the repo's own seed/migration inserts the
  confirmed user into the users table. Match the app's password hashing (bcrypt /
  argon2 / a demo SHA-256) — a wrong hash format is the usual "login rejected"
  cause, and that's a recipe bug, not a product bug.
- **Cloud-Supabase auth:** run the Supabase LOCAL stack in the sandbox (db + GoTrue
  + PostgREST + gateway) and seed a confirmed user via the admin API. Full playbook +
  templates in **`reference/supabase.md`**. Never point the sandbox at the real
  Supabase project.

Also carry the HTTP-cookie gotchas: the session cookie must stick over plain HTTP
on `localhost` (`AUTH_COOKIE_SECURE=false` or equivalent), and any CORS allowlist
must accept the ephemeral sandbox origin. See `gotchas.md`.

### 5b. DB seeding strategy

Pick `SEED_STRATEGY` in the recipe:

- **`initdb`** (default) — the Postgres image's `/docker-entrypoint-initdb.d`
  scripts only (e.g. a `seed.sql` mounted into the postgres service). Nothing else
  runs. This is the pre-v5 SHAPE B behavior; leave the strategy unset to get it.
- **`migrations`** — set `MIGRATE_CMD` to the repo's migration tool
  (`npx prisma migrate deploy`, `alembic upgrade head`, `knex migrate:latest`,
  `drizzle-kit push`, or `psql -f schema.sql`). It runs **in-container** against
  the throwaway DB before the app boots. Add `SEED_CMD` to load data + the
  confirmed test user.
- **`synthetic`** — just `SEED_CMD`: fake data + the confirmed test user.

`MIGRATE_CMD`/`SEED_CMD` run as a one-shot `docker compose run --rm` using
`SEED_SERVICE` (default: the app service, whose image usually carries the
migration CLI). They run **in-container, never on the host**, and can only reach
the throwaway sandbox DB.

**Isolation rule (non-negotiable, same as Supabase):** a remote/VPS/cloud Postgres
app must be **replicated locally** — add a throwaway `postgres` service to
`sandbox.compose.yml`, point the app's `DATABASE_URL` at it, and migrate+seed that.
**Never** inject the real/VPS `DATABASE_URL` into the sandbox: adversarial missions
create/delete + `reset` data, and the report may be published as an Artifact.
(The Phase-3 sanitized-snapshot strategy — opt-in, read-only pull, mask PII before
it lands, load at runtime, scoped — is designed in the roadmap but not yet built.)

`sandbox.sh reset` re-runs the seed after recreating the data services, so every
mission still starts from an identical seeded slate.

## 6. Build the base

`scripts/sandbox.sh onboard`. It builds the base image (SHAPE B) or warms the composed build (SHAPE A) and stamps the lockfile hash. Re-run only when a lockfile changes (`status` tells you).
