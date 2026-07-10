# Gotchas (hard-won)

Failure modes we actually hit or that reliably bite, with fixes.

## App never becomes healthy → almost always secrets/env
The single most common blocker. Apps refuse to boot without JWT/RSA keys, vault master keys, or API keys, and the health poll just times out. Fix: read `.env.example` + startup code during onboarding; inject **throwaway** values in the sandbox compose; record any keygen command in the recipe. Read the container logs (`sandbox.sh` prints the tail on failure) — the missing var is usually named there.

## Chromium force-upgrades single-label hosts to HTTPS
Navigating a browser **inside a container** to `http://<service>:<port>` (e.g. `http://app:3000`) fails with `ERR_SSL_PROTOCOL_ERROR` even though the server is plain HTTP — Chromium auto-upgrades single-label hostnames (no dot) to HTTPS. Raw IPs and dotted hosts are exempt; `node fetch`/health checks are NOT affected (which masks it). **Default fix: drive from the host against the published `localhost` port (exempt).** If you must drive in-container, give the app a dotted network alias (`app.test`) and target that.

## `NEXT_PUBLIC_*` / client-vs-server API URLs
Vars prefixed for the client are read **in the browser on the host**, which cannot resolve compose service names. Server-side code uses `http://<service>:<port>`; client-side must use the published `http://localhost:<port>`. Also: `NEXT_PUBLIC_*` are inlined at **build** time — changing them means rebuilding the image, not just restarting.

## Reusing the repo's compose as-is
A dev compose assumes the developer's laptop. Sanitize via the override: **unique project name** (scripts do this), **ephemeral host ports** (`"0:<port>"`) to avoid collisions, **inject your own throwaway env/secrets** (don't rely on their `.env`), **drop host source bind-mounts** (test the built image, not the working tree) and named-volume data, and **disable dev-only services** via `profiles`.

## Compose CONCATENATES `ports`/`volumes` — a bare `[]` does NOT sanitize
The single most dangerous override mistake. When you layer files with `-f base -f override`, Compose **appends** list-valued fields like `ports` and `volumes` — it does not replace them. So writing `volumes: []` or `ports: []` in the override leaves the base's entries fully intact: the host source **bind-mount still mounts**, the **DB port is still published**, and your "sanitized" sandbox is anything but. You get no error — it silently does the wrong thing. Fix (Compose 2.24+): tag the field to reset the inherited value — `volumes: !reset []` drops the list entirely; `ports: !override ["0:<port>"]` replaces it wholesale (use `!reset []` for a service that must publish nothing). The repo uses a modern Docker Compose, so these tags are available. Verify after `up` with `docker inspect` (no unexpected `Binds`) or `docker compose ... config` (the merged, resolved spec).

## Fixed `container_name:` breaks isolation
Container names are **global**, not scoped to the compose project — so a base compose with `container_name: pec-backend` collides between two concurrent sandbox runs AND with the developer's dev stack, even though each run has a unique project name. Fix: in the override, set `container_name: bdvt-${BDVT_RUN}-<svc>` for every service the base names (`sandbox.sh` exports `BDVT_RUN` per run). If a service has no fixed name in the base, leave it alone — Docker auto-names it per project.

## `env_file:` you can't remove and can't be missing
An override **cannot unset** an `env_file:` the base compose declares, and `docker compose` **errors if the referenced file doesn't exist**. So a base with `env_file: ./backend/.env` will fail on any machine lacking that file, and its values load whether you want them or not. Fix: onboarding must ensure a throwaway **stub** exists at each `env_file` path (create one if missing). Your override's `environment:` block still wins **per-key** over the file's values — use it for the vars that must be sandbox-specific.

## Login fails / blank network tab
Cookie won't stick over HTTP → set `AUTH_COOKIE_SECURE=false` (or equivalent) in the sandbox. Backend CORS must allow the sandbox origin (`http://localhost:<ephemeral>`); if it's a fixed allowlist, that's the culprit. And the seed must create a deterministic test user.

## Windows / WSL2
- Transient `EAI_AGAIN <registry>` during a base build is usually a VPN DNS blip, not a config error — just re-run `onboard`.
- CRIU / `docker checkpoint` for warm snapshots is experimental and fragile on WSL2 — don't build on it.
- If you ever fall back to bind-mounts, enable file-watch polling (`WATCHPACK_POLLING`/`CHOKIDAR_USEPOLLING`) or clone inside the WSL2 filesystem, not `/mnt/c`.

## Dev-mode ≠ prod parity (why we build committed code)
Running `next dev` on a bind-mounted working tree is faster but tests uncommitted code and misses prod-only bugs (bundling, RSC/edge, build-time inlining). This skill builds a clean image of committed `HEAD` on purpose — reproducible and equal to what will merge.

## Port assumptions
The host port is **ephemeral per run**. Always read `SANDBOX_URL` from `up`; never hard-code 3000.

## Review mode: missions mutate state → reset between them
Adversarial missions create/delete/edit data. Two missions against the same live app + DB corrupt each other's assumptions, so review mode runs missions **sequentially** and calls `sandbox.sh reset` before each one. Never fan missions out in parallel against one sandbox. The default `reset` recreates the data services + their anonymous volumes (fresh empty DB), re-runs the seed per `SEED_STRATEGY` (`MIGRATE_CMD`/`SEED_CMD` in-container; no-op for `initdb`), restarts the app **in place** so it drops any stale DB pool (the container is kept, so `SANDBOX_URL` survives), and re-polls `HEALTH_PATH` before returning. Set `SEED_STRATEGY` + the slots for any DB-backed app — the DB image will not seed your app's data itself. `RESET_CMD` remains only as a full override (e.g. a DB on a **named** volume that `rm` won't wipe).

## v5 seeding: schema must exist before the app boots
With `SEED_STRATEGY=migrations`/`synthetic`, `up` brings the **data services up
first** (health-gated), runs `MIGRATE_CMD`/`SEED_CMD` **in-container**
(`compose run --rm --build --no-deps` on `SEED_SERVICE`, default the app image),
**then** starts the app. Don't collapse that back into one `up` — an app that
queries a not-yet-migrated DB on boot will fail its health-gate. `reset` re-runs
the same seed after recreating the data services, because the dropped volume took
the schema with it (initdb-only sandboxes need no re-seed, so `seed_db` no-ops
for `SEED_STRATEGY=initdb`). Never inject a real/VPS `DATABASE_URL` into the
sandbox — replicate that DB locally (a throwaway `postgres` service) and point
`DATABASE_URL` at the replica; adversarial missions mutate + `reset` data and the
report can be published as an Artifact.

## v5 auth: post-login redirect points at the container origin, not localhost
An app that builds an **absolute** redirect from the request URL (e.g. Next's
`new URL(req.url).origin`, `request.nextUrl.origin`) resolves it to the app's
**internal** bind — `http://0.0.0.0:3000` / `http://<service>:3000` — because that's
where the server actually listens. In the sandbox the browser is on the **published**
`http://localhost:<ephemeral>` port, so following that Location dead-ends and login
looks broken even though auth succeeded. This is usually a **product** bug worth
reporting (it also bites real reverse-proxy deploys): prefer a **relative** Location
(browsers resolve it against the address-bar URL) or derive the origin from the
`Host`/`X-Forwarded-Host` header, not from the socket. (We hit exactly this in the
v5 dogfood.) Distinguish it from the recipe-side cookie/CORS issues below.

## v5 snapshot: real data must be MASKED, runtime-loaded, and never committed/baked
`SEED_STRATEGY=snapshot` is the only sanctioned way to get real data into the sandbox,
and only through `reference/snapshot.md`'s masking pipeline. The traps that make it a
leak if you get them wrong: (1) `SOURCE_DB_URL` is **runtime-injected**, never in
`recipe.env`/compose — a committed real connection string is a credential leak; (2) PII
is masked **in memory before any INSERT** — masking after load, or `keep`ing a PII
column, leaks it into the sandbox and thus into screenshots/the published Artifact; (3)
the snapshot loads **at runtime into the ephemeral DB** — never bake a dump into the base
image (a cached layer is a frozen leak); (4) any `SNAPSHOT_DUMP` holds masked data only
and its path **must be gitignored**; (5) tables are **scoped** (row-limited) — the tool
refuses an unscoped table. When in doubt, don't enable it — synthetic seed is safe.

## v5 auth: "seeded user rejected" is a recipe bug, not a broken login
If the login **form renders** but the seeded `TEST_USER`/`TEST_PASSWORD` is
rejected, suspect the recipe/seed — not the product. Usual causes: the seed wrote
the wrong password-hash format (app uses bcrypt, seed wrote plaintext/SHA-256), the
user wasn't created **confirmed** (app blocks unconfirmed logins and the delegate
can't click an email link), or the seed didn't run at all. Fix the seed; don't file
a product finding. Genuine product-side login failures (cookie won't stick over
HTTP, CORS rejects the sandbox origin) are covered above under "Login fails".

## Review mode: keep the mission list small
Each mission is a real delegate subagent (Sonnet 5 by default) plus a sandbox reset — cost and wall-clock scale with mission count, and they run one at a time. Prefer 2–5 sharp, diff-scoped missions over a broad sweep. If you cap coverage, say so in the report.
