# Onboarding a repo

First time only. Produce a committed recipe the scripts can drive, then build the base image once. **Confirm the recipe with the user before building.** Trust boundary: `recipe.env` runs as shell on the host; only onboard repos you trust.

## 1. Onboard around the web surface

Decide by what the browser hits, not by which config files exist (a `docker-compose.yml` may run only backing services or depend on gitignored env).

1. **`single-web-no-db`** — one app on one port, no database (SPA, static server, lone SSR). Build, publish `"0:<port>"`, health-gate `/`.
2. **`single-web-db`** — app + a database it migrates/seeds (Rails, Django, Laravel, FastAPI, Next-with-DB). Wire `MIGRATE_CMD`/`SEED_CMD`. Template: `templates/single-web-db/`.
3. **`split-web-api-db`** — separate frontend and backend that must look like **one origin** (cookies/CORS/build-time public env). Put a reverse proxy in front and make it `APP_SERVICE`. Template: `templates/split-web-api-db/`.
4. **`existing-compose-override`** — the repo's compose already serves the full surface. Layer a sanitizing override on it (SHAPE A); set `BASE_COMPOSE`. Confirm it really serves the surface first, else use 1–3.

Mechanics (none framework-specific):
- **Lockfile picks the package manager** and feeds `LOCKFILES`: `pnpm-lock.yaml`, `package-lock.json`, `yarn.lock`, `bun.lockb`, `uv.lock`, `poetry.lock`; else the manifest (`pyproject.toml`, `go.mod`, `Cargo.toml`). List every lockfile that affects deps.
- **Runtime/version** from `engines`/`packageManager`, `.nvmrc`, `.python-version`, `go.mod`. **Build/start** from scripts/framework defaults (Next→3000, Vite preview→4173).
- **Monorepo:** `.esegui-test/` lives at the **git root**. Dockerfiles `COPY <subdir>/…`, `LOCKFILES` is root-relative, and a whitelist `.dockerignore` at the root keeps the build context small.
- **Health check must be real:** an endpoint that proves app + dependencies (touches the DB), else `HEALTH_PATH=/` as a weaker signal.
- When in doubt about build/start/health, ask the user.

Then run `sandbox.sh doctor`: it validates recipe + rendered compose before the slow build, and `onboard` refuses to build on any FAIL.

## 2. Author the recipe (into `.esegui-test/`)

- `recipe.env` from `templates/recipe.env.example`: core keys `APP_SERVICE`, `APP_PORT`, `LOCKFILES` (+ `HEALTH_PATH`, `BASE_COMPOSE` when needed).
- `sandbox.compose.yml` from `templates/sandbox.compose.example.yml`:
  - **Repo has compose → SHAPE A override:** ephemeral ports, throwaway env, no host source bind-mounts, dev-only services behind `profiles`.
  - **No compose → SHAPE B self-contained:** also `Dockerfile.base` + `Dockerfile.sandbox` (`FROM ${BASE_IMAGE}`) and a `.dockerignore` excluding `node_modules`, build output, `.env`, `.git`, `.esegui-test/evidence`.
- Add to `.gitignore`: `.esegui-test/evidence/`, `.esegui-test/.base.hash`, `.esegui-test/.runs/`.
- **Windows/CRLF:** commit `.esegui-test/.gitattributes` with `* text eol=lf` (CRLF breaks psql backtick meta-commands and script shebangs in Linux containers).
- **Commit** the recipe, compose, Dockerfiles **and every other file the compose mounts** (see SKILL.md step 6).

## 3. Compose gotchas (SHAPE A)

- **Compose CONCATENATES `ports`/`volumes` across files.** A bare `ports: []` or `volumes: []` does not sanitize. Use `volumes: !reset []`, `ports: !override ["0:<port>"]` (or `!reset []` to publish nothing). Verify with `docker compose config`.
- **Fixed `container_name` is global** and breaks isolation: override as `container_name: bdvt-${BDVT_RUN}-<svc>`.
- **`env_file:` can't be removed** and compose errors if missing: ensure a committed throwaway stub exists at each path; per-key `environment:` still wins.
- **Chromium upgrades single-label hosts to HTTPS.** Driving from the host against the published `localhost` port is exempt; this only bites a browser inside a container (use a dotted alias there).
- **`NEXT_PUBLIC_*` / client API URLs** are read in the browser on the host, which can't resolve service names; they must be the published `localhost:<port>` or same-origin, and are inlined at **build** time (rebuild, don't restart).
- **Windows/WSL2:** `EAI_AGAIN` during a base build is a VPN DNS blip; re-run. Don't build on `docker checkpoint`.

## 4. Secrets: the #1 reason a sandbox never goes healthy

Read `.env.example` and startup code for required secrets (JWT/RSA keys, vault keys, API keys). Put **throwaway** values in the compose `environment:`; never depend on the developer's `.env`. Record any keygen command as a recipe comment. Never inject a real/VPS/cloud `DATABASE_URL`: replicate the DB locally (a throwaway service) and point `DATABASE_URL` at it, because missions mutate and `reset` data and reports can be shared.

## 5. Auth and seeding (optional; skip for public no-auth apps)

**Auth:** set `TEST_USER`, `TEST_PASSWORD` (throwaway, safe to commit), `LOGIN_PATH`, optionally `POST_LOGIN_PATH`. The seed creates that user **already confirmed** (the delegate can't click an email link) and the delegate logs in through the real form. Match the app's hash format (bcrypt/argon2/…): a wrong hash is the usual "seeded login rejected", a recipe bug rather than a product bug. Over plain HTTP the session cookie must stick (`AUTH_COOKIE_SECURE=false` or equivalent) and any CORS allowlist must accept the ephemeral origin. For Supabase auth see `addons/supabase/README.md`.

**Seeding** (`SEED_STRATEGY`):
- `initdb` (default): only the DB image's `/docker-entrypoint-initdb.d`.
- `migrations`: `MIGRATE_CMD` (`prisma migrate deploy`, `alembic upgrade head`, `rails db:migrate`, `psql -f schema.sql`, …) then optional `SEED_CMD`.
- `synthetic`: `SEED_CMD` only (fake data + the test user).
- `snapshot`: masked real data, opt-in and sensitive: read `addons/snapshot/README.md` first.

These run **in-container** via `compose run` on `SEED_SERVICE` (default `APP_SERVICE`), against the throwaway DB only. `up` seeds before the app boots (an app that queries an unmigrated DB on boot would fail its health gate); `reset` recreates `DATA_SERVICES`, reseeds and restarts the app in place. No database at all (or SQLite inside the app image)? Leave `DATA_SERVICES` unset; `SEED_CMD` alone still runs.

## 6. Build the base

`sandbox.sh onboard` builds the base image (SHAPE B) or warms the composed build (SHAPE A) and stamps the lockfile hash. Re-run only when `status` says STALE.
