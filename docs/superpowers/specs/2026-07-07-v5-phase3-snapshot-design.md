# v5 Phase 3 — Sanitized real-data snapshot (design + outcome)

**Skill:** `bedigital-visual-tests`. Builds on Phases 1–2. The most sensitive phase:
getting **real** data into the sandbox safely. Real data + a published Artifact report
= GDPR/leak risk, so PII **masking is non-negotiable**.

## Decision: a masking tool behind the existing seed hook, guardrails enforced in code

Like Phase 2, Phase 3 is **configuration + tooling, no `sandbox.sh` changes**. A new
`SEED_STRATEGY=snapshot` is just a documented non-`initdb` strategy: `MIGRATE_CMD`
builds the schema, `SEED_CMD=node scripts/snapshot-and-mask.mjs` pulls + masks + loads.
The two-phase `up` and `reset` from Phase 1 carry it.

## The tool (`templates/snapshot-and-mask.mjs`)

Pulls a **scoped, read-only** slice of the real DB, **masks PII in memory**, loads the
masked rows into the ephemeral sandbox DB. Guardrails **enforced in code**:
- Refuses if `SOURCE_DB_URL` is unset (runtime-injected, never committed).
- Forces the source session read-only (`SET default_transaction_read_only`, `BEGIN READ
  ONLY`) — a bug can't mutate the real DB.
- Refuses any table without an explicit row `limit` (scoped, not a whole-DB dump).
- Masks every configured column before any INSERT; `keep` columns pass through and are
  printed as a warning each run.
- Writes to disk only if `SNAPSHOT_DUMP` is set, and then only the **masked** data (path
  must be gitignored). Never baked into an image.

Mask strategies (`snapshot.config.json`, committed, no secrets): `email`, `name`,
`phone`, `hash`, `null`, `redact`, `keep`. Value-derived masks are deterministic by the
original, so references stay consistent without revealing anything.

## Deliverables
- `templates/snapshot-and-mask.mjs`, `templates/snapshot.config.example.json`.
- `reference/snapshot.md` (guardrail playbook) + a new gotcha + pointers from SKILL.md,
  onboarding.md §5b, recipe.env.example.

## Dogfood evidence (real, two throwaway Postgres DBs)
Source DB: 7 PII users + 3 orders (real-looking emails, names, phones, bcrypt hashes,
`tok_live_*` tokens, street addresses). Config scoped to 5 users / 2 orders. Result:
- Sandbox received exactly **5 users + 2 orders** (limits enforced).
- emails → `masked_<hash>@example.invalid`, names → `Test User <hash>`, phones masked,
  `password_hash` + `api_token` → `NULL`, `shipping_address` → `REDACTED`.
- Leak check: **0 rows** with a real domain / `tok_live` token / real address.
- Source DB **untouched** (7 real users intact).
- Guardrails: refused with `SOURCE_DB_URL` missing; refused a table with no `limit`.

## Status
v5 complete: Phase 1 (local-Postgres auth + seeding, #13), Phase 2 (local Supabase, #14),
Phase 3 (sanitized snapshot). storageState fallback for OAuth-only apps remains the one
documented-but-unbuilt escape hatch (form login is proven and preferred).
