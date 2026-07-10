# Review mode — the adversarial brain

This is the playbook for the autonomous flow: read what changed → decide what to hunt for → delegate one agent per mission → aggregate. It sits on top of the v1 sandbox core (`sandbox.sh` + `driving-the-app.md`), which is unchanged.

Three roles: **Planner** (you, the agent running the skill), **Delegate** (one spawned subagent per mission), **Aggregator** (you again, after delegates return).

---

## 1. Planner — turn the change into missions

Read, in order:
1. **The diff** — `git diff <base>...HEAD` (base = the branch's fork point, or `HEAD~1` if unknown). This is the primary signal: what actually changed.
2. **The commit / PR message** — intent in the author's words.
3. **The optional brief** — a spec/plan or free-text checklist the caller passed. If present, it *steers*: the user's stated intent outranks your inference. If absent, work from the diff alone.
4. **Repo route/page inventory** — enough of the app's routes/pages to know where a changed component surfaces (e.g. a changed `InvoiceExport` component → the `/outbound` page).

Then emit a **small set of missions** — each a specific, adversarial objective tied to the change. Think: *"what can I do to break this change, and what second-order effects does it have?"* — not "click through the whole app."

### Mission schema

```yaml
id: m1
title: Export button produces a file
rationale: PR adds an Export control to /outbound; core new user-facing action.
steps:
  - log in as the seeded user
  - open /outbound
  - click the new Export button
  - observe the result (download / toast / error)
lens: adversarial            # default — try to break it, not just confirm the happy path
expected: a file downloads (or a clear success state); no console error, no HTTP >= 400
```

Rules for good missions:
- **Diff-scoped.** Every mission traces to something the diff touched (a new control, a changed query, a touched route) or a direct second-order effect. Don't test unrelated features.
- **Adversarial by default.** Bad input, empty state, double-click, the boundary the change introduced — not just the happy path. Set `lens` to something else only when a mission is genuinely non-adversarial.
- **Few.** Prefer 2–5 sharp missions over a broad sweep. Each mission = one Sonnet 5 delegate = real tokens + wall-clock (they run sequentially). Say so if you're deliberately capping coverage.
- **Self-contained.** A delegate gets only its mission + the sandbox URL — bake in what it needs (which page, which control, the seeded creds hint).

### The gate

- **Interactive (default):** present the mission list (id, title, one-line rationale) and let the user approve / edit / drop / add before any delegate runs. This is where steering happens — there is no separate "guided mode."
- **`--auto`:** skip the gate. Log the plan, proceed. (For hands-off callers like a finishing `/work` agent.)

---

## 2. Delegate — run one mission

Spawn **one subagent per mission**, sequentially, using `DELEGATE_MODEL` from the recipe (default `claude-sonnet-5`). Before each delegate: `sandbox.sh reset` so it starts from a clean, seeded DB (adversarial missions mutate state). `reset` recreates the data services, re-runs the seed per `SEED_STRATEGY` (`MIGRATE_CMD`/`SEED_CMD` in-container), restarts the app in place (fresh DB pool, same `SANDBOX_URL`), and re-polls `HEALTH_PATH` — so a mission never starts against a half-reset app. It fails loudly if health doesn't come back.

Give the delegate: the **mission**, the **`SANDBOX_URL`** and **`EVIDENCE_DIR`** from `up`, the **seeded auth creds** if `up` printed them (`TEST_USER`/`TEST_PASSWORD`/`LOGIN_PATH`/`POST_LOGIN_PATH` — pass them verbatim so the delegate can log in), and a pointer to `reference/driving-the-app.md`. The delegate:
- If the app has auth, **logs in first** through the real form with the seeded creds (per `driving-the-app.md` → "Logging in"), then runs the mission steps.
- Drives the app with **agent-browser** per `driving-the-app.md` (screenshots each step into `EVIDENCE_DIR`, captures console + network, uses the seeded test user — never real creds).
- Judges each step ✓ / ⚠ against the mission's `expected`, pushing adversarially (bad input, empty state, the boundary).
- Returns a **finding**:

```yaml
mission: m1
verdict: fail            # pass | fail
summary: Export button throws 500; no file, no user-facing error.
evidence: [04-outbound.png, ERROR-export.png, network.json]
# present only when verdict: fail —
repro: repro-m1.spec.ts  # runnable Playwright spec targeting SANDBOX_URL, written to EVIDENCE_DIR
fix: |                   # short root-cause hypothesis + where to look
  POST /api/export returns 500. Likely the new export handler
  (src/app/api/export/route.ts) doesn't await the stream / missing Content-Disposition.
  Check the handler and its DB query for the changed column.
```

- On **pass**: evidence + one-line verdict. On **fail**: evidence + a **runnable repro** (a Playwright `.spec.ts` written to `EVIDENCE_DIR`, hitting the ephemeral `SANDBOX_URL`, that reproduces the failure) + a **short fix suggestion** (root-cause hypothesis + the file/area to look at — 2-4 lines, not a patch).

---

## 3. Aggregator — collect and report

After all delegates return, write **`REVIEW.md`** into `EVIDENCE_DIR`:

```markdown
# Visual review — <repo> @ <short-sha> — <timestamp>
Base: <base ref>   Sandbox: <SANDBOX_URL>   Missions: <n>

| # | Mission | Verdict | Evidence | Notes |
|---|---------|---------|----------|-------|
| m1 | Export button produces a file | ⚠ FAIL | ERROR-export.png, network.json | POST /api/export → 500 |
| m2 | List still loads with export column | ✓ PASS | 05-list.png | |

## Findings
### ⚠ m1 — Export button throws 500
- **Evidence:** ERROR-export.png, network.json (req #12)
- **Repro:** `repro-m1.spec.ts`
- **Likely fix:** export handler doesn't set Content-Disposition / await the stream — see src/app/api/export/route.ts

**Verdict: ⚠ 1 of 2 missions failed.**
```

Then produce the **rich report** (full steps in `reference/reporting.md`): write `findings.json` to `EVIDENCE_DIR`, run `node "$SKILL_DIR/scripts/build-report.js" "$EVIDENCE_DIR"` to generate a self-contained `review.html` (screenshots inlined, a storyboard per mission), and — when the `Artifact` tool is available — publish it for a shareable link (favicon `🔎`). `REVIEW.md` stays for agents; `review.html` is the human view.

Then report inline: findings **ranked most-severe first**, with the key screenshot shown for UI failures, the repro path, and the fix hint. Keep it tight — the user wants the verdict and the proof, not a narration of every click. If you published an artifact, give them the link.

Finally `sandbox.sh down` (base image stays cached).

---

## Notes
- The planner is the agent running the skill — it runs at the session model, so launch the skill under a strong model (Opus) for good missions. Delegates are always spawned as `DELEGATE_MODEL`.
- Missions run **sequentially** with a `reset` between them — bounded machine load and bounded spend. Don't fan out in parallel (shared app + DB; they'd collide).
- This is v2's autonomous flow. If the user just wants one specific check, that's a brief with one obvious mission — same machinery.
