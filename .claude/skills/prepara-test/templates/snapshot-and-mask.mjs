// snapshot-and-mask.mjs — v5 Phase 3: sanitized real-data snapshot (OPT-IN).
//
// Pull a SCOPED, READ-ONLY slice of a real database, MASK all PII in memory, and
// load the masked rows into the ephemeral sandbox DB — at runtime, never baked into
// an image, never written to disk unless explicitly asked (and then gitignored).
//
// This exists because the review report can be published as an Artifact (rows end up
// in screenshots), so unmasked real data here is a GDPR/data-leak path. Masking is
// NON-NEGOTIABLE and happens BEFORE anything is inserted anywhere.
//
// Runs in-container via the v5 seed hook: SEED_CMD="node scripts/snapshot-and-mask.mjs".
// Requires the `pg` package (present in Postgres Node apps; that's the SEED_SERVICE).
//
// Env (SOURCE_DB_URL is RUNTIME-INJECTED and NEVER committed — see reference/onboarding.md §5):
//   SOURCE_DB_URL   read-only connection string to the REAL db (used only to pull, then discarded)
//   DATABASE_URL    the ephemeral sandbox db to load into (already migrated)
//   SNAPSHOT_CONFIG path to the masking config JSON (committed; contains NO secrets)
//   SNAPSHOT_DUMP   optional path to also write the MASKED rows as JSON (must be gitignored)
//
// Config shape (SNAPSHOT_CONFIG):
//   { "tables": [
//       { "table": "public.users", "limit": 200, "orderBy": "id",
//         "columns": { "email": "email", "full_name": "name",
//                      "api_token": "null", "id": "keep", "created_at": "keep" } } ] }
// Mask strategies: email | name | phone | null | hash | redact | keep.

import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import pg from "pg";

const { Client } = pg;

const SOURCE = process.env.SOURCE_DB_URL;
const TARGET = process.env.DATABASE_URL;
const CONFIG = process.env.SNAPSHOT_CONFIG;
const DUMP = process.env.SNAPSHOT_DUMP || "";

function die(msg) {
  console.error("SNAPSHOT_FAIL " + msg);
  process.exit(1);
}

if (!SOURCE) die("SOURCE_DB_URL not set (runtime-injected, read-only). Refusing to guess.");
if (!TARGET) die("DATABASE_URL (sandbox target) not set.");
if (!CONFIG) die("SNAPSHOT_CONFIG (masking config path) not set.");

const cfg = JSON.parse(readFileSync(CONFIG, "utf8"));
if (!Array.isArray(cfg.tables) || cfg.tables.length === 0) die("config has no tables[]");

const sha8 = (s) => createHash("sha256").update(String(s)).digest("hex").slice(0, 8);

// Masking functions. Deterministic by original value so references stay consistent
// (same source email → same fake email) without revealing the original.
const MASKERS = {
  keep: (v) => v,
  null: () => null,
  redact: () => "REDACTED",
  email: (v) => (v == null ? null : `masked_${sha8(v)}@example.invalid`),
  name: (v) => (v == null ? null : `Test User ${sha8(v)}`),
  phone: (v) => (v == null ? null : `+100000${sha8(v).replace(/\D/g, "0").slice(0, 4)}`),
  hash: (v) => (v == null ? null : sha8(v)),
};

function maskValue(strategy, value) {
  const fn = MASKERS[strategy];
  if (!fn) die(`unknown mask strategy "${strategy}"`);
  return fn(value);
}

async function main() {
  const src = new Client({ connectionString: SOURCE });
  const dst = new Client({ connectionString: TARGET });
  await src.connect();
  await dst.connect();

  // Belt-and-suspenders: make the SOURCE session physically read-only so a bug here
  // can never mutate the real db. Any write attempt will error out.
  await src.query("SET default_transaction_read_only = on");
  await src.query("BEGIN READ ONLY");

  const dumpOut = [];
  let grandTotal = 0;

  try {
    for (const t of cfg.tables) {
      const { table, limit, orderBy, columns } = t;
      if (!table) die("a table entry is missing `table`");
      // SCOPED guardrail: refuse any table without an explicit positive row limit.
      if (!Number.isInteger(limit) || limit <= 0)
        die(`table ${table} needs an integer "limit" > 0 (scoped snapshots only)`);
      if (!columns || typeof columns !== "object")
        die(`table ${table} needs a "columns" mask map`);

      const cols = Object.keys(columns);
      const order = orderBy ? ` ORDER BY ${orderBy}` : "";
      const sql = `SELECT ${cols.map((c) => `"${c}"`).join(", ")} FROM ${table}${order} LIMIT ${limit}`;
      const { rows } = await src.query(sql);

      // Warn loudly about any masked-as-passthrough columns so the author is aware.
      const passthrough = cols.filter((c) => columns[c] === "keep");
      console.log(
        `>> ${table}: pulled ${rows.length} row(s); masking [${cols
          .filter((c) => columns[c] !== "keep")
          .join(", ")}]; PASSTHROUGH(keep) [${passthrough.join(", ") || "none"}]`,
      );

      // Mask every row in memory BEFORE any write.
      const masked = rows.map((r) => {
        const out = {};
        for (const c of cols) out[c] = maskValue(columns[c], r[c]);
        return out;
      });

      // Load into the sandbox target.
      for (const row of masked) {
        const vals = cols.map((c) => row[c]);
        const ph = cols.map((_, i) => `$${i + 1}`).join(", ");
        const colList = cols.map((c) => `"${c}"`).join(", ");
        await dst.query(
          `INSERT INTO ${table} (${colList}) VALUES (${ph}) ON CONFLICT DO NOTHING`,
          vals,
        );
      }
      grandTotal += masked.length;
      if (DUMP) dumpOut.push({ table, rows: masked });
    }
  } finally {
    await src.query("ROLLBACK").catch(() => {}); // source was read-only; nothing to commit
    await src.end();
    await dst.end();
  }

  if (DUMP) {
    // Only the MASKED data is ever written, and only to a gitignored path.
    writeFileSync(DUMP, JSON.stringify(dumpOut, null, 2));
    console.log(`>> wrote masked dump to ${DUMP} (must be gitignored)`);
  }
  console.log(`SNAPSHOT_OK loaded ${grandTotal} masked row(s) into the sandbox`);
}

main().catch((e) => die(e.message));
