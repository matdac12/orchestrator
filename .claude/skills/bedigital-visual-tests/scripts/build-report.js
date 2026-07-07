#!/usr/bin/env node
// build-report.js — assemble a self-contained visual-review report from a run's
// findings + evidence. Node built-ins only (no npm deps); Node ships in the base
// image, so this runs anywhere the sandbox does.
//
//   node build-report.js <EVIDENCE_DIR>
//
// Reads <EVIDENCE_DIR>/findings.json (schema in reference/reporting.md), inlines
// every referenced screenshot as a data: URI, and writes <EVIDENCE_DIR>/review.html.
//
// The output has inline <style> + markup + <script> and NO <html>/<head>/<body>
// wrapper — so the same file opens locally in a browser AND is exactly what the
// Artifact tool wraps at publish time (its CSP forbids external assets, hence the
// inlined images).

const fs = require("fs");
const path = require("path");

const dir = process.argv[2];
if (!dir) {
  console.error("usage: build-report.js <EVIDENCE_DIR>");
  process.exit(2);
}
const findingsPath = path.join(dir, "findings.json");
if (!fs.existsSync(findingsPath)) {
  console.error(`ERROR: no findings.json in ${dir}`);
  process.exit(1);
}
const data = JSON.parse(fs.readFileSync(findingsPath, "utf8"));
const missions = Array.isArray(data.missions) ? data.missions : [];

const esc = (s) =>
  String(s == null ? "" : s).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]),
  );

const MIME = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
};
// Containment: findings.json is untrusted input (and review.html may be
// published as a shareable Artifact), so a `../` in a `steps`/`repro` path must
// NOT let us inline arbitrary local files. Resolve against EVIDENCE_DIR and
// refuse anything that escapes it. e.g. "../etc/passwd" -> null (skipped).
const root = path.resolve(dir);
function safeResolve(file) {
  const p = path.resolve(dir, String(file));
  if (p !== root && !p.startsWith(root + path.sep)) return null; // escapes EVIDENCE_DIR
  return p;
}
function dataUri(file) {
  const p = safeResolve(file);
  if (!p || !fs.existsSync(p)) return null;
  const mime = MIME[path.extname(String(file)).toLowerCase()] || "application/octet-stream";
  return `data:${mime};base64,${fs.readFileSync(p).toString("base64")}`;
}
function readText(file) {
  const p = safeResolve(file);
  return p && fs.existsSync(p) ? fs.readFileSync(p, "utf8") : null;
}

const norm = (v) => String(v || "").toLowerCase();
const isFail = (m) => ["fail", "failed", "warn", "⚠"].includes(norm(m.verdict));
const failed = missions.filter(isFail).length;
const passed = missions.length - failed;
const overall =
  failed === 0
    ? { cls: "ok", text: `All ${missions.length} missions passed` }
    : { cls: "bad", text: `${failed} of ${missions.length} mission${missions.length === 1 ? "" : "s"} failed` };

function storyboard(m, idx) {
  const frames = (m.steps || [])
    .map((f) => ({ f, uri: dataUri(f) }))
    .filter((x) => x.uri);
  if (!frames.length) return "";
  const imgs = frames
    .map(
      (x, i) =>
        `<img class="frame${i === 0 ? " on" : ""}" src="${x.uri}" alt="${esc(x.f)}" loading="lazy">`,
    )
    .join("");
  const dots = frames
    .map((_, i) => `<button class="dot${i === 0 ? " on" : ""}" data-i="${i}" aria-label="Step ${i + 1}"></button>`)
    .join("");
  const caption = frames.length > 1 ? `Step 1 / ${frames.length}` : esc(frames[0].f);
  return `<figure class="story" data-sb="${idx}">
    <div class="stage">${imgs}</div>
    <figcaption class="sbbar">
      <span class="sbcap" data-cap>${esc(caption)}</span>
      ${frames.length > 1 ? `<span class="dots">${dots}</span><button class="play" data-play aria-label="Pause">❚❚</button>` : ""}
    </figcaption>
  </figure>`;
}

function card(m, i) {
  const bad = isFail(m);
  const repro = m.repro ? readText(m.repro) : null;
  return `<article class="card ${bad ? "bad" : "ok"}">
    <header class="chead">
      <span class="mid">${esc(m.id || "m" + (i + 1))}</span>
      <h2>${esc(m.title || "Mission")}</h2>
      <span class="pill ${bad ? "bad" : "ok"}">${bad ? "FAIL" : "PASS"}</span>
    </header>
    ${m.rationale ? `<p class="why">${esc(m.rationale)}</p>` : ""}
    ${storyboard(m, i)}
    ${m.summary ? `<p class="summary">${esc(m.summary)}</p>` : ""}
    ${
      bad && m.fix
        ? `<div class="fix"><span class="eyebrow">Likely fix</span><p>${esc(m.fix)}</p></div>`
        : ""
    }
    ${
      bad && repro
        ? `<details class="repro"><summary>Runnable repro${m.repro ? ` — ${esc(m.repro)}` : ""}</summary><pre><code>${esc(repro)}</code></pre></details>`
        : ""
    }
  </article>`;
}

const meta = [
  data.repo && `repo ${esc(data.repo)}`,
  data.sha && `@ ${esc(data.sha)}`,
  data.base && `base ${esc(data.base)}`,
  data.sandbox_url && `sandbox ${esc(data.sandbox_url)}`,
  data.timestamp && esc(data.timestamp),
]
  .filter(Boolean)
  .join("  ·  ");

const html = `<style>
  * { box-sizing: border-box; }
  :root {
    --bg:#f6f7f9; --surface:#ffffff; --sunk:#f0f2f6; --ink:#1b1f27; --muted:#5a6370;
    --line:#e4e7ec; --accent:#3b5bdb; --ok:#16a34a; --bad:#d97706;
    --radius:14px; --maxw:62rem;
    --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    --mono: ui-monospace, "SF Mono", "Cascadia Code", "JetBrains Mono", Consolas, monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0e1116; --surface:#161a21; --sunk:#11151b; --ink:#e6eaf0; --muted:#98a2b1;
            --line:#232935; --accent:#7c8cff; --ok:#34d399; --bad:#fbbf24; }
  }
  :root[data-theme="light"] { --bg:#f6f7f9; --surface:#ffffff; --sunk:#f0f2f6; --ink:#1b1f27; --muted:#5a6370; --line:#e4e7ec; --accent:#3b5bdb; --ok:#16a34a; --bad:#d97706; }
  :root[data-theme="dark"]  { --bg:#0e1116; --surface:#161a21; --sunk:#11151b; --ink:#e6eaf0; --muted:#98a2b1; --line:#232935; --accent:#7c8cff; --ok:#34d399; --bad:#fbbf24; }

  body { margin:0; background:var(--bg); color:var(--ink); font-family:var(--sans);
         line-height:1.55; -webkit-font-smoothing:antialiased; }
  .wrap { max-width:var(--maxw); margin:0 auto; padding:2.5rem 1.25rem 4rem; }
  .eyebrow { font-size:.7rem; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); font-weight:600; }

  .banner { display:flex; flex-wrap:wrap; align-items:baseline; gap:.5rem 1rem;
            border-left:4px solid var(--accent); padding:.25rem 0 .25rem 1rem; margin-bottom:.5rem; }
  .banner.ok  { border-color:var(--ok); }
  .banner.bad { border-color:var(--bad); }
  .banner h1 { font-size:1.6rem; margin:0; font-weight:700; letter-spacing:-.01em; text-wrap:balance; }
  .banner .count { font-variant-numeric:tabular-nums; }
  .metaline { font-family:var(--mono); font-size:.78rem; color:var(--muted);
              font-variant-numeric:tabular-nums; margin:0 0 2rem; word-break:break-word; }

  .cards { display:flex; flex-direction:column; gap:1.25rem; }
  .card { position:relative; background:var(--surface); border:1px solid var(--line);
          border-radius:var(--radius); padding:1.25rem 1.35rem; overflow:hidden; }
  .card::before { content:""; position:absolute; inset:0 auto 0 0; width:4px; background:var(--ok); }
  .card.bad::before { background:var(--bad); }

  .chead { display:flex; align-items:center; gap:.75rem; flex-wrap:wrap; }
  .chead h2 { font-size:1.12rem; margin:0; font-weight:650; flex:1 1 auto; letter-spacing:-.01em; }
  .mid { font-family:var(--mono); font-size:.72rem; color:var(--muted); background:var(--sunk);
         border:1px solid var(--line); border-radius:6px; padding:.1rem .4rem; }
  .pill { font-size:.7rem; font-weight:700; letter-spacing:.08em; padding:.2rem .5rem; border-radius:999px;
          color:#fff; background:var(--ok); }
  .pill.bad { background:var(--bad); }
  .why { color:var(--muted); margin:.5rem 0 0; font-size:.92rem; }
  .summary { margin:.9rem 0 0; }

  .story { margin:1rem 0 0; border:1px solid var(--line); border-radius:10px; overflow:hidden; background:var(--sunk); }
  .stage { position:relative; aspect-ratio:16/9; background:var(--sunk); }
  .frame { position:absolute; inset:0; width:100%; height:100%; object-fit:contain; object-position:center;
           opacity:0; transition:opacity .35s ease; }
  .frame.on { opacity:1; }
  .sbbar { display:flex; align-items:center; gap:.6rem; padding:.45rem .7rem; border-top:1px solid var(--line);
           background:var(--surface); }
  .sbcap { font-family:var(--mono); font-size:.72rem; color:var(--muted); flex:1 1 auto;
           font-variant-numeric:tabular-nums; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .dots { display:flex; gap:.3rem; }
  .dot { width:.5rem; height:.5rem; border-radius:999px; border:0; padding:0; background:var(--line); cursor:pointer; }
  .dot.on { background:var(--accent); }
  .play { border:1px solid var(--line); background:var(--surface); color:var(--muted); border-radius:6px;
          font-size:.6rem; line-height:1; padding:.25rem .35rem; cursor:pointer; }

  .fix { margin:1rem 0 0; padding:.8rem .95rem; background:var(--sunk); border:1px solid var(--line);
         border-radius:10px; }
  .fix p { margin:.3rem 0 0; }
  .repro { margin:.85rem 0 0; }
  .repro summary { cursor:pointer; font-size:.82rem; color:var(--accent); font-weight:600; }
  .repro pre { margin:.6rem 0 0; padding:.9rem; background:var(--sunk); border:1px solid var(--line);
               border-radius:10px; overflow-x:auto; }
  .repro code { font-family:var(--mono); font-size:.78rem; line-height:1.5; }

  a, .repro summary:focus-visible, .dot:focus-visible, .play:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
  @media (prefers-reduced-motion: reduce) { .frame { transition:none; } }
</style>

<div class="wrap">
  <div class="banner ${overall.cls}">
    <span class="eyebrow">Visual review</span>
    <h1>${esc(overall.text)}</h1>
    <span class="count eyebrow">${passed} passed · ${failed} failed</span>
  </div>
  <p class="metaline">${meta || "bedigital-visual-tests"}</p>
  <div class="cards">
    ${missions.map(card).join("\n")}
  </div>
</div>

<script>
(function () {
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.querySelectorAll(".story").forEach(function (sb) {
    var frames = [].slice.call(sb.querySelectorAll(".frame"));
    if (frames.length < 2) return;
    var dots = [].slice.call(sb.querySelectorAll(".dot"));
    var cap = sb.querySelector("[data-cap]");
    var playBtn = sb.querySelector("[data-play]");
    var i = 0, timer = null, playing = !reduce;
    function show(n) {
      i = (n + frames.length) % frames.length;
      frames.forEach(function (f, k) { f.classList.toggle("on", k === i); });
      dots.forEach(function (d, k) { d.classList.toggle("on", k === i); });
      if (cap) cap.textContent = "Step " + (i + 1) + " / " + frames.length;
    }
    function tick() { show(i + 1); }
    function start() { if (timer) return; timer = setInterval(tick, 1800); playing = true; if (playBtn) playBtn.textContent = "❚❚"; }
    function stop() { clearInterval(timer); timer = null; playing = false; if (playBtn) playBtn.textContent = "▶"; }
    dots.forEach(function (d) { d.addEventListener("click", function () { stop(); show(+d.dataset.i); }); });
    if (playBtn) playBtn.addEventListener("click", function () { playing ? stop() : start(); });
    sb.addEventListener("mouseenter", function () { if (playing) clearInterval(timer), (timer = null); });
    sb.addEventListener("mouseleave", function () { if (playing && !timer) timer = setInterval(tick, 1800); });
    show(0);
    if (playing) start();
  });
})();
</script>`;

fs.writeFileSync(path.join(dir, "review.html"), html);
console.log(`review.html written to ${path.join(dir, "review.html")} (${missions.length} missions, ${failed} failed)`);
