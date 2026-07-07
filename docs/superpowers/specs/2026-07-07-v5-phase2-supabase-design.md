# v5 Phase 2 — Local Supabase in the sandbox (design + outcome)

**Skill:** `bedigital-visual-tests`. Builds on Phase 1 (PR #13, merged). Goal: apps
that authenticate against **Supabase** must be able to log in and be seeded, without
ever touching the real Supabase project.

Authoritative design: `bedigital-visual-tests-roadmap` memory (v5). Facts verified
this session against `github.com/supabase/supabase` `docker/` and the current
`@supabase/ssr` Next.js guide (per the supabase skill's rule #1 — don't trust memory).

## Decision: run a trimmed local Supabase stack, ride the Phase-1 seed hook

Rather than add Supabase-specific machinery to `sandbox.sh`, Phase 2 is delivered as
**configuration**: a compose template for a trimmed local Supabase stack + a
confirmed-user seed script invoked through the **existing** v5 `seed_db` hook. Net
`sandbox.sh` change for Phase 2 = one bug fix (see below), no new subcommands.

### Stack (trimmed from the official self-hosted compose)
`db` (supabase/postgres) + `auth` (GoTrue) + `rest` (PostgREST) + `gateway` (nginx,
routes `/auth/v1`→auth and `/rest/v1`→rest like Kong) + `frontend` (the app).
Well-known public dev keys only (sandbox-only, safe to commit).

### Seeding — reuse Phase 1
`DATA_SERVICES="db auth rest gateway"`, `SEED_STRATEGY=synthetic`,
`SEED_CMD="node scripts/seed-supabase-user.mjs"`. The two-phase `up` brings the
whole stack up (health-gated) before the app, runs the seed against the live
gateway (admin API: `POST /auth/v1/admin/users {email,password,email_confirm:true}`),
then starts the app. `reset` recreates the stack (dropping `db` wipes `auth.users`)
and re-seeds. This validated the Phase-1 design generalizing cleanly.

### The crux: NEXT_PUBLIC inlining + ephemeral port → server-side auth
`NEXT_PUBLIC_SUPABASE_URL` is inlined at build; the app port is ephemeral per run,
so you can't bake the app's own public URL into a browser Supabase client. Resolution
(the pattern the sample uses and the docs prescribe): **all auth server-side**
(`@supabase/ssr` cookies) so the browser never dials Supabase; `NEXT_PUBLIC_SUPABASE_URL`
= the **internal** gateway, **baked as a build ARG**. Session lands in **chunked
`sb-*-auth-token` cookies** (verified) — which is why form-login is the default and
storageState injection stays a documented fallback.

## Deliverables
- `templates/supabase.sandbox.compose.example.yml`, `templates/supabase/{roles,jwt}.sql`,
  `templates/supabase/gateway.conf`, `templates/seed-supabase-user.mjs`.
- `reference/supabase.md` (the playbook) + pointers from SKILL.md, onboarding.md §5,
  recipe.env.example.
- `sandbox.sh` fix: the EXIT-trap `up_ok` local is out of scope on the failure path
  under `set -u` → guard with `${up_ok:-}` (surfaced by a Phase-2 up failure).

## Dogfood evidence (real, against a created @supabase/ssr sample)
Built `visual-test-supabase-demo` (Next 14 + @supabase/ssr, server-side auth). Then:
- `up` → stack healthy; `SEED_OK created confirmed user` via the admin API; app healthy.
- Browser: unauth `/` → `/login`; filled seeded creds → logged in; protected home
  showed `Signed in as tester@sandbox.local` + a real GoTrue UUID; the session cookie
  was the chunked `sb-gateway-auth-token=base64-…`, decoding to `email_confirmed_at`
  set (proves `email_confirm:true`).
- `reset` → stack recreated + reseeded (`SEED_OK created`), app port stable,
  stale-cookie browser logged out (old user id gone), re-login works.
- Two bugs found + fixed mid-dogfood: `roles.sql` altering roles the trimmed image
  doesn't create (initdb exit 3); the `up_ok` unbound-variable trap on the failure path.

## Deferred
- Phase 3: sanitized real-data snapshot with PII masking.
- storageState/cookie-injection fallback for OAuth-only apps (documented, not built —
  form login is proven and preferred).
