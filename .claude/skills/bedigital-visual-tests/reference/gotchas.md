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
Adversarial missions create/delete/edit data. Two missions against the same live app + DB corrupt each other's assumptions, so review mode runs missions **sequentially** and calls `sandbox.sh reset` (fresh seeded DB, app stays up) before each one. Never fan missions out in parallel against one sandbox. The default `reset` drops the data services + their anonymous volumes so the image's `initdb`/seed re-runs (SHAPE B); a repo whose DB uses a **named** volume or a migrate/seed profile must set `RESET_CMD` in the recipe (SHAPE A) or the reset won't actually wipe the data.

## Review mode: keep the mission list small
Each mission is a real delegate subagent (Sonnet 5 by default) plus a sandbox reset — cost and wall-clock scale with mission count, and they run one at a time. Prefer 2–5 sharp, diff-scoped missions over a broad sweep. If you cap coverage, say so in the report.
