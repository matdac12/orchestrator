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
