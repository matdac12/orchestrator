# Driving the app + capturing evidence

After `sandbox.sh up` prints `SANDBOX_URL` and `EVIDENCE_DIR`, drive the running app with the **agent-browser** skill (invoke it; it's the preferred browser path). You are hitting the app on the host's published port — plain HTTP on `localhost`, so no container-networking or HTTPS-upgrade issues apply.

## Logging in (v5)

If the app gates pages behind auth, `up` prints the throwaway seeded creds
alongside `SANDBOX_URL`:

```
SANDBOX_URL=http://localhost:49han
TEST_USER=tester@sandbox.local
TEST_PASSWORD=sandbox-only-pw
LOGIN_PATH=/login
POST_LOGIN_PATH=/
```

Log in **through the app's real form** before the mission steps:

1. Navigate to `SANDBOX_URL + LOGIN_PATH`, screenshot `01-login.png`.
2. Fill `TEST_USER` / `TEST_PASSWORD`, screenshot `02-login-filled.png`, submit.
3. Wait for the post-login landing (`POST_LOGIN_PATH` if given, else any
   authed page), screenshot `03-authed.png`. Confirm you're actually in (URL
   changed off `LOGIN_PATH`, an authed element rendered).

Rules:
- Use **only** the seeded `TEST_USER`/`TEST_PASSWORD` — **never** real credentials,
  never creds from a `.env` or a password manager.
- If the login form is present but the seeded user is **rejected**, that's a
  **recipe/seed bug** (wrong password hash format, user not confirmed, seed didn't
  run) — not a product failure. Say so; don't report it as a broken login feature.
- Cookie won't stick / blank network tab → `Secure`-flag-over-HTTP or CORS; see
  `gotchas.md`. Also a recipe/sandbox issue, not the product.
- A useful adversarial check for an auth change: hit an authed route **before**
  logging in and confirm it redirects to `LOGIN_PATH` (proves the gate works).

## The loop, per step of the user's flow

For a brief like *"log in, open the outbound page, click the new Export button"*:

1. **Wait for readiness beyond the health check.** The health gate proves the server answers; a dev/first render can still lag. If the first navigation looks half-rendered, retry once.
2. **Navigate + act, screenshotting every meaningful step** into `EVIDENCE_DIR`, zero-padded and named:
   - `01-login.png` → fill the **seeded** test creds → `02-login-filled.png`
   - submit, wait for the post-login URL/element → `03-dashboard.png`
   - navigate to the target page → `04-outbound.png`
   - click the new control → `05-export-clicked.png` and one more after the result renders → `06-export-result.png`
3. **Capture failure signals, not just pixels.** After each step pull console messages and network activity. Write `console.log` and `network.json` into `EVIDENCE_DIR`. On any JS error or HTTP ≥ 400, also save `ERROR-<step>.png`. A screenshot shows *that* it broke; console/network show *why*.
4. **Assert per step:** element present? URL changed? expected text rendered? Record ✓ / ⚠ with a one-line reason.

## REPORT.md (write into EVIDENCE_DIR)

```markdown
# Visual test — <repo> @ <short-sha> — <timestamp>
Brief: "<the user's checklist, verbatim>"
Sandbox: <SANDBOX_URL>

| # | Step | Result | Evidence | Note |
|---|------|--------|----------|------|
| 1 | Load /login | ✓ | 01-login.png | |
| 2 | Log in (seed user) | ✓ | 03-dashboard.png | redirected to /dashboard |
| 3 | Open /outbound | ✓ | 04-outbound.png | |
| 4 | Click Export | ⚠ | ERROR-4.png, network.json | POST /api/export → 500 |

**Verdict:** ⚠ 1 issue — Export returns 500 (see network.json req #12).
```

Then report the verdict to the user inline and, for UI steps, show the key screenshot(s). Keep evidence per-run under `EVIDENCE_DIR` so runs form a visual history.

## Notes

- Use the **seeded** test user the recipe documents — never real credentials.
- If login fails with an empty network tab, suspect CORS or the cookie `Secure` flag over HTTP (see `gotchas.md`).
- Prefer role/text/testid locators over brittle CSS/XPath so the same flow survives small UI churn between commits.
- This is guided (you say what to check). Auto-deciding checks from the diff + delegating persona agents is the future v2 layer.
