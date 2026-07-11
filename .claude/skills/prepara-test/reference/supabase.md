# Local Supabase in the sandbox (v5 Phase 2)

When the app authenticates against **Supabase**, you cannot point the sandbox at
the real Supabase project — adversarial missions create/delete data and `reset`
wipes it. Instead run a **local Supabase stack inside the sandbox** (Postgres +
GoTrue auth + PostgREST + a gateway), seed a confirmed test user, and log in
through the app's real form. This is the heaviest onboarding path; this doc is the
playbook. It was proven end-to-end against a minimal `@supabase/ssr` Next.js sample.

> **Verify against current docs, not memory (supabase skill rule #1).** Image tags,
> GoTrue env, `@supabase/ssr` cookie shape, and the admin API all drift. The values
> in `templates/` were checked against `github.com/supabase/supabase` `docker/` this
> release — re-check the changelog before trusting them on a new app.

## 1. Detect "uses Supabase"

Signals: `@supabase/supabase-js` / `@supabase/ssr` in `package.json`; a
`utils/supabase/` (server/client/middleware) or `lib/supabase` module;
`NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY` in `.env.example`; a
`supabase/` dir with `config.toml`/migrations. If present, use this path instead of
the plain SHAPE-B compose.

## 2. Stand up the local stack

Copy `templates/supabase.sandbox.compose.example.yml` → the app's
`.bedigital-visual-tests/sandbox.compose.yml`, and the three bootstrap files from
`templates/supabase/` → `.bedigital-visual-tests/supabase/`
(`roles.sql`, `jwt.sql`, `gateway.conf`). Commit them. The stack is trimmed to the
minimum for email/password auth + a REST API:

| Service | Image | Role |
|---------|-------|------|
| `db` | `supabase/postgres` | Postgres with the auth schema + roles baked in |
| `auth` | `supabase/gotrue` | email/password auth, JWT issuance, admin API |
| `rest` | `postgrest/postgrest` | the `/rest/v1` data API (drop if the app only needs auth) |
| `gateway` | `nginx` | one origin (`:8000`) routing `/auth/v1`→auth, `/rest/v1`→rest (Kong's job in the full stack) |
| `frontend` | your app | == `APP_SERVICE` |

**Well-known dev keys only.** The compose hard-codes the public Supabase local-dev
JWT secret + anon/service_role keys. They are sandbox-only and safe to commit. The
anon/service keys are JWTs *signed with* that secret — change one, regenerate all
three (the supabase repo's `utils/generate-keys.sh`).

Two gotchas that actually bit during the dogfood:
- **`roles.sql` must only touch roles this image variant creates.** The official
  `roles.sql` also alters `supabase_functions_admin` / `supabase_storage_admin`,
  which the trimmed stack's Postgres image doesn't create — `ALTER`ing a missing
  role aborts initdb (exit 3). The template keeps only `authenticator` (PostgREST)
  and `supabase_auth_admin` (GoTrue). Add a role back only if you add its service.
- **The gateway is internal — do NOT publish it to the host.** Only `frontend`
  publishes an (ephemeral) port. See §4.

## 3. Seed a confirmed test user (reuses the v5 seed hook)

No new machinery: the Phase-1 `seed_db` hook does it. In `recipe.env`:

```sh
DATA_SERVICES="db auth rest gateway"   # reset recreates the whole stack; wipes auth.users
SEED_STRATEGY=synthetic
SEED_SERVICE=frontend                  # the app image has node; runs the seed script
SEED_CMD="node scripts/seed-supabase-user.mjs"
TEST_USER=tester@sandbox.local
TEST_PASSWORD=sandbox-only-pw
LOGIN_PATH=/login
POST_LOGIN_PATH=/
```

Copy `templates/seed-supabase-user.mjs` into the app repo (`scripts/`). It POSTs to
GoTrue's admin API — the HTTP equivalent of
`auth.admin.createUser({email,password,email_confirm:true})`:

```
POST {gateway}/auth/v1/admin/users
  apikey: <service_role>        Authorization: Bearer <service_role>
  { "email": ..., "password": ..., "email_confirm": true }
```

`email_confirm:true` is what lets the delegate log in immediately (no email link to
click). The script is idempotent (treats "already registered" as success).

Because `DATA_SERVICES` includes `db auth rest gateway`, the skill's two-phase `up`
brings the **whole stack up (health-gated) before the app**, then runs the seed
against the live gateway, then starts the app. `reset` recreates the stack
(dropping `db` wipes `auth.users`) and re-runs the seed — so every mission starts
with the same confirmed user and no leftover state. **Zero `sandbox.sh` changes** —
Phase 2 rides entirely on the Phase-1 seed hook + two-phase up + reset.

## 3b. Real schema + synthetic data (when the repo has no schema baseline)

Many apps carry only **incremental** migrations (they `ALTER`/patch an existing DB) — the real `CREATE TABLE`s live in the cloud project, not the repo. An empty local Postgres + those migrations then fails. Path that works for "schema + fake data":

1. **Dump the schema from prod, once** (safe to commit — no rows, no secrets):
   `supabase db dump --db-url "<conn>" --schema public -f .bedigital-visual-tests/schema.sql`.
   Get `<conn>` right: the direct `db.<ref>.supabase.co` host is often **IPv6-only** and unresolvable from the dump container — use the **session pooler** `postgresql://postgres.<ref>:<pw>@aws-<N>-<region>.pooler.supabase.com:5432/postgres`. The region/`aws-N` prefix must match the project (probe: a wrong one fails fast with `Tenant or user not found`). Needs the DB password (not the service-role JWT) — have the user run it, or pass it once for a local-only dump.
2. **Author `seed.sql`** = copy the non-PII reference rows verbatim from prod (lookups, template cycles, staff — preserve the real UUIDs so FKs resolve; anonymize any employee names) + synthesize the PII/volume tables (patients, orders, phases) referencing the copied rows **by natural key** (`(SELECT id FROM forniture WHERE codice_esterno=…)`), so you never hardcode UUIDs. Build child rows with `INSERT … SELECT` from the copied templates. Wrap the load in `SET session_replication_role = replica; … SET session_replication_role = DEFAULT;` to defer FK/triggers during bulk insert. If the app has a global data cutoff/filter setting, force it off in the seed so the synthetic rows are visible.
3. **Apply both via the `db` service's initdb mounts** — NOT a `MIGRATE_CMD` (the app image has no psql). Mount into `/docker-entrypoint-initdb.d/init-scripts/`, numbered to run **after** the image's baked scripts (`…3-post-setup`) that create `anon`/`authenticated`/`service_role`:
   ```
   - ./.bedigital-visual-tests/schema.sql:/docker-entrypoint-initdb.d/init-scripts/50-schema.sql:ro
   - ./.bedigital-visual-tests/seed.sql:/docker-entrypoint-initdb.d/init-scripts/55-seed.sql:ro
   ```
   The image's `migrate.sh` globs `init-scripts/*.sql` sorted, with `ON_ERROR_STOP=1` (a real SQL error aborts init and the container exits 1 — fail-loud). The base postgres entrypoint prints `ignoring …/init-scripts` — that's expected; `migrate.sh` is what runs them. `reset` recreates the ephemeral `db`, so schema+seed reapply every mission. A defensive `45-ensure-roles.sql` (`CREATE ROLE … IF NOT EXISTS` via a `DO` block) makes the schema's `GRANT`s robust across image variants. `SEED_STRATEGY` stays `synthetic` with `SEED_CMD` doing only the confirmed-user admin-API seed.

**Read-path note:** many server components read via a **service-role** client (`createServiceClient`, bypasses RLS), not the SSR cookie client — so the synthetic rows just need to *exist*; you don't need RLS-visible data. But the confirmed test user is still required to pass the middleware auth gate and reach those pages.

## 4. The NEXT_PUBLIC / ephemeral-port trap → do auth SERVER-SIDE

This is the crux. `NEXT_PUBLIC_SUPABASE_URL` is **inlined at build time** into both
server and client bundles, and the sandbox's app port is **ephemeral per run** —
so you cannot bake the app's own public URL into a browser-side Supabase client.

The clean resolution (what the sample does, and the pattern to prefer):
- **All auth runs server-side** via `@supabase/ssr` `createServerClient` (a login
  server action calling `signInWithPassword`, `getUser()` to protect pages,
  `middleware` to refresh). The browser only ever talks to the app on its published
  ephemeral port; it never dials Supabase, so there's no CORS and no build-time URL
  problem.
- `NEXT_PUBLIC_SUPABASE_URL` is set to the **internal gateway** `http://gateway:8000`
  and **baked as a build ARG** in `Dockerfile.sandbox` (not just runtime env, or
  `next build` inlines `undefined`). The server resolves `gateway` over the compose
  network; the value being "wrong" for a browser is irrelevant because the browser
  never uses it.
- The session lands in **chunked cookies** `sb-<ref>-auth-token(.N)` (the
  `@supabase/ssr` shape) — verified in the dogfood. This is exactly why **form
  login is the default** and storageState injection is only a fragile fallback (§6).

If an app does client-side Supabase auth (browser calls Supabase directly), you'd
have to publish the gateway on a fixed host port and satisfy CORS for the app's
ephemeral origin — brittle. Prefer steering such apps to server-side auth, or use
the fallback in §6.

## 4b. `next build` prerenders DB-backed pages → run the DEV server

A production `next build` **prerenders** pages at build time. Any `(app)` page that
fetches Supabase in a static/cached way (commonly via the **service-role** client,
which reads no cookies so Next treats it as static) is evaluated during
`docker build` — where the sandbox gateway is **not on the network** and the
service-role key is a **runtime-only** secret, not a build ARG. The build then dies
(`createServiceClient: … mancanti`, or a fetch/connect error, `Export encountered
an error on /<page>`). On the cloud it builds only because the real DB is reachable
at build.

The robust sandbox fix: **run the dev server** — `Dockerfile.sandbox` does
`COPY <app>/ ./` then `CMD ["npm","run","dev","-- -H 0.0.0.0 -p <port>"]`, no
`next build`. `next dev` defers every fetch to request time, when the full stack is
up, so no build-time DB and no build-ARG secret juggling. Trade-offs: the first hit
to each route compiles (health-gate on a light route like `/login` and allow retries;
`wait_for_health` already polls). Keep the base image's `npm ci` (dev deps included).
The alternative — forcing those routes dynamic — means editing app code; prefer dev.

## 5. Health gate

Point `HEALTH_PATH` at a route that proves the app can reach the auth gateway (the
sample's `/api/health` fetches `${SUPABASE_URL}/auth/v1/health` server-side). That
gates the browser on the whole chain (app → gateway → GoTrue → db) being live.

## 6. Fallback: storageState / cookie injection (only if form login can't work)

For OAuth-only apps with no password form, inject a pre-authenticated session
instead. **Version-fragile — verify the exact shape against the app's installed lib
at build time (supabase skill rule #1):** `supabase-js` stores the session in
localStorage `sb-<ref>-auth-token`; `@supabase/ssr` (Next.js) uses **chunked
cookies**, not localStorage. Mint a session via the admin API / a password grant,
write it into the browser context as the right cookies/localStorage, and drive from
there. Build this only after confirming form login genuinely can't be used — it's
the escape hatch, not the default.

## 7. Reset between missions

`reset` recreates `DATA_SERVICES` (`db auth rest gateway`) and re-seeds. Dropping
`db` takes `auth.users` with it, so a stale browser session (its JWT references a
now-deleted user id) fails `getUser()` and the app redirects to login — a clean
slate, exactly like a fresh `up`. The app's ephemeral port stays stable (the app
service isn't recreated).
