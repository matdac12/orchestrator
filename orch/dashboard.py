PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>orch — {project}</title>
<style>
 body{font:14px system-ui,sans-serif;margin:0;background:#0f1115;color:#e6e6e6}
 header{padding:12px 20px;background:#171a21;font-weight:600}
 .cols{display:flex;gap:12px;padding:16px;flex-wrap:wrap}
 .agent{flex:1;min-width:200px;background:#171a21;border-radius:8px;padding:12px}
 .badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px}
 .queued{background:#444} .discussing{background:#1f6feb}
 .executing{background:#0e7490} .blocked{background:#b54708}
 .done{background:#238636} .merged{background:#8957e5}
 .idle{background:#333}
 .feed{padding:0 16px 24px} .ev{padding:6px 0;border-top:1px solid #222}
 .muted{color:#8b949e;font-size:12px}
 .phase{color:#58a6ff;font-size:12px}
 .waiting{margin:12px 16px 0;padding:10px 14px;border-radius:8px;
   background:#7a1f1f;color:#fff;font-weight:600}
 #health{float:right;font-weight:400;font-size:12px}
 .ok{color:#3fb950} .down{color:#f85149}
</style></head>
<body data-project="{project}">
<header>orch — {project}<span id="health"></span></header>
<div id="waiting"></div>
<div id="cols" class="cols"></div>
<div class="feed"><h3>events</h3><div id="feed"></div></div>
<script src="/dashboard.js"></script>
</body></html>"""
