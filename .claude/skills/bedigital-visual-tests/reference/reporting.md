# Reporting — the rich HTML report

After the aggregator has all findings (see `reviewing.md` §3), it produces **three** outputs:

1. **`REVIEW.md`** — the agent-facing summary (unchanged; the orchestrator/`work` agent parses it to decide merge-or-fix).
2. **`review.html`** — a self-contained, human-facing visual report (screenshots inlined, a storyboard per mission, repros + fixes). Always written to `EVIDENCE_DIR`.
3. **A published Artifact** — when the `Artifact` tool is available, `review.html` is published to a shareable claude.ai URL. When it isn't (autonomous/headless run), just report the local path.

`trace.zip` per failed mission stays alongside for deep-dive (linked, not embedded).

## Step 1 — write `findings.json`

Write the collected findings to `EVIDENCE_DIR/findings.json`. Schema:

```json
{
  "repo": "visual-test-demo",
  "sha": "<short sha>",
  "base": "<base ref>",
  "sandbox_url": "http://localhost:<ephemeral>",
  "timestamp": "2026-07-07 12:26",
  "missions": [
    {
      "id": "m1",
      "title": "Export button produces a file",
      "rationale": "PR adds the Export control to /outbound.",
      "verdict": "pass",            // pass | fail  (fail | warn | ⚠ also count as fail)
      "summary": "One-line observation.",
      "steps": ["m1-01-outbound.png", "m1-02-export.png"],  // ordered screenshots → storyboard
      "repro": "repro-m1.spec.ts",  // fail only; a file in EVIDENCE_DIR
      "fix": "Root-cause hypothesis + where to look."       // fail only
    }
  ]
}
```

- `steps` are the ordered screenshot filenames (already in `EVIDENCE_DIR`) the delegate captured — they become the mission's storyboard.
- `repro` / `fix` are only meaningful on failures; omit or null on pass.

## Step 2 — build the HTML

```bash
node "$SKILL_DIR/scripts/build-report.js" "$EVIDENCE_DIR"
```

`build-report.js` (Node built-ins only — Node is in the base image, no npm install) reads `findings.json`, **base64-inlines every referenced screenshot as a `data:` URI**, inlines each repro file as a code block, and writes `EVIDENCE_DIR/review.html`. The output is inline `<style>` + markup + `<script>` with **no `<html>/<head>/<body>`** — so the same file opens locally in a browser AND is exactly what the Artifact tool wraps at publish time. The design (cool-slate neutrals, semantic pass/fail, per-mission cards, auto-advancing storyboard with pause/scrub, theme-aware) lives in the template; you don't hand-write HTML.

## Step 3 — publish (when possible)

If the **`Artifact`** tool is available, publish the file:
- `file_path` = the `review.html` you just wrote
- `favicon` = `🔎` (keep it stable across runs)
- `description` = the verdict in one line (e.g. "Visual review — 1 of 3 missions failed")

Return the artifact URL to the user. **The report is already designed** (built per the `artifact-design` fundamentals), so you do NOT need to reload `artifact-design` or restyle — just publish the file as-is.

If the `Artifact` tool is **not** available (autonomous/headless), skip publishing and report the local path (`EVIDENCE_DIR/review.html`) — it's fully self-contained and opens in any browser.

## Notes
- **Sensitive content:** `review.html` embeds screenshots and can surface network/DB data from the sandbox — treat it as potentially sensitive. Artifacts are **private by default** (only the user chooses to share one), so never auto-share or post the link anywhere public; the human decides who sees it.
- Everything is inlined; no external assets (the Artifact CSP forbids them). That's why screenshots are `data:` URIs, not `<img src="file.png">`.
- **Deferred (clean follow-ons):** a downloadable animated `.gif` of the storyboard (stitch the step PNGs with ffmpeg), and true `.webm` motion capture of the live session. Neither is built yet; the inline slideshow covers the "storyboard" need without an encoder dependency.
