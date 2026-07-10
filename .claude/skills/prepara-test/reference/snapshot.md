# Sanitized real-data snapshot (v5 Phase 3) — READ BEFORE ENABLING

`SEED_STRATEGY=snapshot` pulls a slice of a **real** database into the sandbox so
missions run against realistic data. Real data in the sandbox is a **GDPR / data-leak
path** — the review report can be published as an Artifact, so rows end up in
screenshots. The masking below is **non-negotiable**; without it, do not use this.

## The guardrails (all enforced or documented; none optional)

1. **OPT-IN per repo.** Never enable `snapshot` by default. It only runs when a repo's
   recipe sets `SEED_STRATEGY=snapshot` *and* a `SOURCE_DB_URL` is injected at runtime.
2. **Read-only pull.** `SOURCE_DB_URL` must be a **read-only** connection string. The
   tool also forces the source session read-only (`SET default_transaction_read_only`,
   `BEGIN READ ONLY`) as a belt — a bug still can't mutate the real DB.
3. **Runtime-injected, never committed.** `SOURCE_DB_URL` is passed as an environment
   variable at `up` time (e.g. `SOURCE_DB_URL=... bash sandbox.sh up`), read by the
   compose seed service via `${SOURCE_DB_URL}`. It must **never** appear in
   `recipe.env`, `sandbox.compose.yml`, or any committed file. Used only to pull, then
   discarded when the seed container exits.
4. **Mask/anonymize PII before it lands.** Every PII column maps to a mask strategy in
   the committed `snapshot.config.json`; masking happens **in memory before any INSERT**.
   Fake emails/names/phones, `null` for tokens/secrets/hashes, `redact` for free-text
   PII. `keep` columns pass through unmasked and are printed as a **warning** each run —
   review that list every time.
5. **Load at runtime, not baked.** The masked rows go straight into the **ephemeral**
   sandbox DB via the seed hook. Do **not** bake a dump into the base image (a frozen
   cached layer is a leak). If you set `SNAPSHOT_DUMP`, it writes **only the masked
   data** and the path **must be gitignored** (add it to `.gitignore` at onboarding).
6. **Scoped.** Every table needs an explicit row `limit` — the tool refuses an unscoped
   table. Snapshot specific tables with row caps (e.g. "these 5 tables, 200 rows each"),
   never a whole-DB dump.

## Wiring

Recipe (note `SOURCE_DB_URL` is NOT here — it's injected at runtime):

```sh
SEED_STRATEGY=snapshot
SEED_SERVICE=frontend               # app image (has `pg`)
MIGRATE_CMD="npx prisma migrate deploy"          # build the schema first
SEED_CMD="node scripts/snapshot-and-mask.mjs"    # then pull+mask+load
SNAPSHOT_CONFIG=.bedigital-visual-tests/snapshot.config.json
```

In `sandbox.compose.yml`, the seed service reads the runtime-injected source URL and
the committed config path — the URL value is never stored:

```yaml
  frontend:
    environment:
      SOURCE_DB_URL: ${SOURCE_DB_URL:-}     # injected at `up`; empty ⇒ tool refuses
      SNAPSHOT_CONFIG: /app/.bedigital-visual-tests/snapshot.config.json
      # SNAPSHOT_DUMP: /app/.bedigital-visual-tests/evidence/snapshot.json  # optional; gitignored
```

Copy `templates/snapshot-and-mask.mjs` → the app's `scripts/`, and
`templates/snapshot.config.example.json` → `.bedigital-visual-tests/snapshot.config.json`;
fill in the real tables/columns. Add to `.gitignore` any `SNAPSHOT_DUMP` path.

Run: `SOURCE_DB_URL='postgresql://readonly_user:pw@real-host/db' bash "$ESEGUI_DIR/scripts/sandbox.sh" up` (`ESEGUI_DIR` = the esegui-test sibling skill dir, which owns the scripts).
Because `snapshot` is a non-`initdb` strategy, the two-phase `up` builds the schema
(`MIGRATE_CMD`) and loads the masked slice (`SEED_CMD`) before the app boots; `reset`
re-pulls a fresh masked slice between missions.

## Mask strategies (`snapshot.config.json`)

`email` (→ `masked_<hash>@example.invalid`), `name` (→ `Test User <hash>`), `phone`,
`hash` (opaque but consistent), `null`, `redact` (→ `"REDACTED"`), `keep` (unmasked —
warned). All value-derived masks are deterministic by the original value, so
references stay consistent (same source email → same fake) without revealing anything.

## Verified behavior (dogfood)

Against a source DB of 7 PII users + 3 orders, config scoped to 5 users / 2 orders:
the sandbox received exactly 5 users and 2 orders; emails/names/phones masked, password
hashes + API tokens `NULL`, addresses `REDACTED`; **0 rows contained real PII**; the
source DB was **untouched** (7 real users intact). The tool refused when `SOURCE_DB_URL`
was missing and when a table had no row `limit`.
