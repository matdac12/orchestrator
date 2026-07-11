# Onboarding a repo

First time only. Goal: produce a committed recipe the scripts can drive, then build the base image once. **Confirm the recipe with the user before building anything.**

> **TRUST BOUNDARY.** `sandbox.sh` **sources `recipe.env` as a shell script on your host**, and `RESET_CMD` runs through `bash -c` on the host — not inside Docker. Only the app code is sandboxed; the recipe is executed with your user's privileges. A committed recipe from an untrusted repo can therefore run arbitrary commands on your machine. **Only onboard/run repositories you trust.** For untrusted code, read `recipe.env` first and prefer running the reseed **in-container** (a compose `run` against the DB service) over a host-side `RESET_CMD`.

## 1. Onboard around the web SURFACE, not the config files

The one question that decides everything: **what single URL does the browser hit, and does the app already produce it from a clean checkout?** Answer that first — a `docker-compose.yml` existing does *not* mean it serves the browser-facing app (it may run backing services only, omit the frontend, or depend on gitignored env). Pick the shape from the surface, then fill in the mechanics.

**Four shapes (choose by the surface):**

1. **`single-web-no-db`** — one static/SSR app on one port, no database. SPA (Vite/CRA/Next-export), a static server, a lone SSR app. Simplest: build it, publish `"0:<port>"`, health-gate `/`.
2. **`single-web-db`** — one app server + a database it migrates/seeds. Rails/Django/Laravel/FastAPI/Next-with-DB. Wire `MIGRATE_CMD`/`SEED_CMD` (the DB image will **not** seed your app's data). Template: `templates/single-web-db/`.
3. **`split-web-api-db`** — a separate frontend and backend the browser must see as **one origin** (so auth cookies/CORS/build-time public env work). Put a reverse proxy in front (`/api`→backend, rest→frontend) and make it `APP_SERVICE`. Template: `templates/split-web-api-db/`.
4. **`existing-compose-override`** — the repo's own compose already serves the full browser surface and is close to sandbox-ready. Layer a sanitizing SHAPE A override on it. Only choose this once you've confirmed the compose actually serves the surface — otherwise fall back to 1–3 (SHAPE B).

Then fill in the mechanics, none framework-specific:
- **Lockfile picks the package manager** (for `LOCKFILES` + the base build) — never guess. `pnpm-lock.yaml`→pnpm, `package-lock.json`→npm, `yarn.lock`→yarn, `bun.lockb`→bun; `uv.lock`→uv, `poetry.lock`→poetry; else the dependency **manifest** (`pyproject.toml`, `go.mod`, `Cargo.toml`, bare `package.json`) — hash whatever declares deps.
- **App in a subdirectory (monorepo):** `sandbox.sh` runs from the **git root** and `.bedigital-visual-tests/` lives there — NOT next to the app. The build context is the git root, so the Dockerfiles reach into the subdir (`COPY web/app/package.json …`, `COPY web/app/ ./`), `LOCKFILES` is root-relative (`web/app/package-lock.json`), and you add a whitelist `.dockerignore` at the root (`*` then `!web/ !.bedigital-visual-tests/`, then re-exclude `node_modules`/build output/dev assets) so the whole repo isn't shipped as build context.
- **Runtime/version** from `engines`/`packageManager`, `.nvmrc`, `.python-version`, `go.mod`.
- **Build & start** from `package.json` scripts / framework defaults (Next→3000, Vite preview→4173, Express→3000/4000/8000).
- **Data + env contract:** ORM/migrations (`prisma/`, `alembic`, `knexfile`, `drizzle.config`) and their migrate+seed commands → `SEED_STRATEGY` + `MIGRATE_CMD`/`SEED_CMD` (plain commands, run in-container via `compose run` on `SEED_SERVICE`, default the app image); `.env.example` lists required vars; note the connection-string var (usually `DATABASE_URL`).
- **When in doubt, ask the user** — don't guess build/start/health.

**Then run `sandbox.sh doctor`** — it statically validates the authored recipe + rendered compose (lockfiles committed, `APP_SERVICE` publishes `APP_PORT` ephemerally, no fixed `container_name`/bind-mounts/ports, the seed service exists, env_files committed) and prints concrete FAIL/WARN lines *before* the slow build. `onboard` runs it automatically and refuses to build on any FAIL.

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
- **Commit `recipe.env` + `sandbox.compose.yml` (+ Dockerfiles) — AND every other file the compose bind-mounts.** `up`/`onboard` build from a **detached HEAD worktree** and overlay ONLY `recipe.env`, `sandbox.compose.yml`, `Dockerfile.*`, and `.dockerignore` uncommitted (so those iterate freely). Every other mount source — `schema.sql`, `seed.sql`, `supabase/*.sql`, `gateway.conf`, `scripts/seed-*.mjs` — must exist at **committed HEAD**, or Docker silently creates an **empty directory** at the mount target and the service dies (`could not read from input file: Is a directory`, `db` exits 1). Practical loop: iterate the overlaid files uncommitted while smoke-testing, then commit the rest *before the real* `up`.
- **Windows / CRLF:** commit a `.bedigital-visual-tests/.gitattributes` with `* text eol=lf`. The `.sql` init scripts and shell/node scripts are read inside Linux containers; `autocrlf` on checkout injects `\r` that breaks psql `\set … \`echo "$X"\`` backtick meta-commands and script shebangs.

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
- **`snapshot`** — a **sanitized real-data snapshot** (opt-in; the sensitive path).
  Runs `MIGRATE_CMD` (build the schema), then `SEED_CMD=node scripts/snapshot-and-mask.mjs`
  which pulls a **scoped, read-only, PII-masked** slice of the real DB into the
  sandbox at runtime. **Read `reference/snapshot.md` before enabling it — the
  masking guardrails are non-negotiable.**

`MIGRATE_CMD`/`SEED_CMD` run as a one-shot `docker compose run --rm` using
`SEED_SERVICE` (default: the app service, whose image usually carries the
migration CLI). They run **in-container, never on the host**, and can only reach
the throwaway sandbox DB.

**Isolation rule (non-negotiable, same as Supabase):** a remote/VPS/cloud Postgres
app must be **replicated locally** — add a throwaway `postgres` service to
`sandbox.compose.yml`, point the app's `DATABASE_URL` at it, and migrate+seed that.
**Never** inject the real/VPS `DATABASE_URL` into the sandbox: adversarial missions
create/delete + `reset` data, and the report may be published as an Artifact.
The `snapshot` strategy is the ONLY sanctioned way to get real data into the
sandbox, and only through the masking pipeline in `reference/snapshot.md`.

`sandbox.sh reset` re-runs the seed after recreating the data services, so every
mission still starts from an identical seeded slate.

## 6. Build the base

`scripts/sandbox.sh onboard`. It builds the base image (SHAPE B) or warms the composed build (SHAPE A) and stamps the lockfile hash. Re-run only when a lockfile changes (`status` tells you).
