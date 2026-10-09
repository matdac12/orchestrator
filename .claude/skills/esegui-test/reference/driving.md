# Driving the app (delegate playbook)

Delegates drive the sandbox with the host's **native browser tools** (`preview_*` in T3 Code). They are plain MCP tools, so there is no extra skill to load. If the session has no `preview_*` tools, fall back to the `agent-browser` skill with the same rules.

The app is on the host's published port, plain HTTP on `localhost` (no HTTPS-upgrade trap).

## Delegate prompt (fill and send, one per mission)

```
You are a QA agent. Run ONE mission against a sandbox and report what you actually see.
Mission: <id, title, steps, expected>
SANDBOX_URL: <url>        EVIDENCE_DIR: <dir>
Login (omit if no auth): TEST_USER=<..> TEST_PASSWORD=<..> LOGIN_PATH=<..> POST_LOGIN_PATH=<..>
Rules: use only these creds; push adversarially (bad input, empty state, double-click, the boundary); do not edit code.
Browser: open your own tab with preview_open(url, reuseExistingTab=false, open=false) and pass its tabId on every call.
Playbook: <path to this file>. Return the finding YAML from reviewing.md (verdict, summary, evidence; on fail also repro + fix).
```

## Tool recipe

- **See:** `preview_snapshot` (no `save`) returns `visibleText`, `accessibilityTree` with `[ref=...]` handles, plus `consoleEntries`, `networkEntries` (url, method, status, failed) and an `actionTimeline`. That one call covers reading the page, console and network. Text only, cheap.
- **Act:** `preview_click` / `preview_type` with `locator='aria-ref=<ref>'` or a role/text selector (`role=textbox[name='Email']`, `role=button[name='Log in']`). Refs expire after navigation or a new snapshot. `preview_wait_for` (text, selector or `urlIncludes`) instead of sleeping; if it times out, take a snapshot before concluding failure (the page may be fine).
- **Evidence screenshot:** `preview_snapshot(save=true)` returns **only** `url` + `screenshotPath` (no tree), so it is a separate call. Copy the file into `EVIDENCE_DIR` as `<mission>-NN-<what>.png` with `cp`. Shoot every meaningful step and every failure (`ERROR-<step>.png`).
- **Console/network evidence:** take the plain snapshot after the action; write failing entries (status >= 400, `failed: true`, console errors) to `network.json` / `console.log` in `EVIDENCE_DIR`. For request/response bodies, wrap `fetch` via `preview_evaluate` before acting.
- **Entries accumulate** across navigations in a tab (and carry earlier origins), so judge only entries newer than your action (compare `timestamp`).
- **Finish:** close your tab when done (`t3_preview_close` if available).

## Logging in

If creds were given: open `SANDBOX_URL + LOGIN_PATH`, fill `TEST_USER`/`TEST_PASSWORD`, submit through the **real form**, then confirm you left `LOGIN_PATH` and an authed element rendered (screenshot each stage). Never use real credentials.

- Form present but seeded user **rejected** → recipe/seed bug. Say so; don't report a broken login.
- Good auth-change check: hit an authed route before logging in and confirm it redirects to `LOGIN_PATH`.

## Per step

Act → wait for the expected state → snapshot → judge ✓/⚠ against `expected` with a one-line reason. Prefer role/text locators so flows survive small UI churn.

If a browser call fails (tab can't open, host unavailable), report the exact error as a blocker, not a product verdict, and do not guess. Do not cite commit hashes in `fix` unless you ran `git log` yourself.

Return one finding and stop. The planner aggregates.
