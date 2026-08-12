PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>orch — {project}</title>
<style>
 body{font:14px system-ui,sans-serif;margin:0;background:#0f1115;color:#e6e6e6}
 header{padding:12px 20px;background:#171a21;font-weight:600;
   display:flex;align-items:center;gap:12px}
 #counts{color:#8b949e;font-weight:400;font-size:12px}
 #health{margin-left:auto;font-weight:400;font-size:12px}
 .ok{color:#3fb950} .down{color:#f85149}
 h2{font-size:11px;letter-spacing:.08em;color:#8b949e;margin:20px 20px 8px}
 .agent{background:#171a21;border-radius:8px;padding:12px 14px;margin:0 20px 10px}
 .head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
 .letter{font-size:16px}
 .badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px}
 .queued{background:#444} .discussing{background:#1f6feb}
 .executing{background:#0e7490} .blocked{background:#b54708}
 .done{background:#238636} .merged{background:#8957e5}
 .title{flex:1;min-width:120px}
 .branch{color:#8b949e;font-size:12px}
 .prog{display:flex;align-items:center;gap:10px;margin-top:10px}
 .phase{color:#58a6ff;font-size:12px;min-width:130px}
 .bar{flex:1;max-width:320px;height:6px;background:#0b0d11;border-radius:3px;
   overflow:hidden}
 .fill{height:100%;background:#58a6ff}
 .steps{font-size:12px;color:#8b949e}
 .msg{margin-top:6px}
 .meta{display:flex;gap:10px;margin-top:4px;font-size:12px;color:#8b949e}
 .age{margin-left:auto}
 .merge{display:flex;align-items:center;gap:12px;background:#171a21;
   border-radius:8px;padding:8px 14px;margin:0 20px 6px;font-size:13px}
 .muted{color:#8b949e;font-size:12px}
 .waiting{margin:12px 20px 0;padding:10px 14px;border-radius:8px;
   background:#7a1f1f;color:#fff;font-weight:600}
 details{margin:20px}
 summary{cursor:pointer;color:#8b949e;font-size:12px}
 .ev{padding:6px 0;border-top:1px solid #222;font-size:13px}
 #idle{margin:0 20px;color:#8b949e;font-size:12px}
</style></head>
<body data-project="{project}">
<header>orch — {project}<span id="counts"></span><span id="health"></span></header>
<div id="waiting"></div>
<h2 id="workinghdr">WORKING</h2>
<div id="working"></div>
<h2 id="readyhdr">READY TO MERGE</h2>
<div id="ready"></div>
<div id="idle"></div>
<details id="feedwrap">
<summary id="feedsummary">recent activity</summary>
<div id="feed"></div>
</details>
<script src="/dashboard.js"></script>
</body></html>"""
