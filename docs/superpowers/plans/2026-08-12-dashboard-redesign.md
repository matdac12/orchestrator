# Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the `orch serve` dashboard around "what is everyone doing, and how much is left" — working agents with progress bars, a ready-to-merge strip, and a collapsed event feed.

**Architecture:** The client JS moves out of the Python string into `orch/dashboard.js`, served at `/dashboard.js`, which removes brace escaping and makes the JS syntax-checkable and unit-testable in node. `dashboard.py` keeps HTML and CSS, substituted with `str.replace` rather than `.format()` so CSS braces stay natural. All rendering stays client-side against the unchanged `/api/state`.

**Tech Stack:** Python 3.8+ stdlib (`http.server`, `unittest`), vanilla JS (no framework, no build step). Node is used only to syntax-check and unit-test the JS; every node-dependent test skips cleanly when node is absent.

**Spec:** `docs/superpowers/specs/2026-08-12-dashboard-redesign-design.md`

## Global Constraints

- **Standard library only** on the Python side. No npm, no bundler, no framework.
- **Python 3.8+ compatible.** No `match`, no `|` type unions.
- **`/api/state` and `get_state` do not change.** Anything reading that endpoint keeps working.
- **`orch serve` keeps its CLI surface** — same command, same port default, same project resolution.
- **Every user-controlled string is escaped** before reaching `innerHTML`: task title, branch, progress message, next step, event message, blocker reason, project name.
- **A progress bar is drawn only when both `step` and `step_total` are present.** No inferred percentages.
- **Working agents sort alphabetically and never reorder between polls.**
- **Node-dependent tests must `skipTest` when `shutil.which("node")` is None** — the suite stays green without node.
- **Style:** 4-space Python indent, ~79 columns; 2-space JS indent, semicolons, `const`/`let`.

## File Structure

| File | Responsibility |
|---|---|
| `orch/dashboard.py` | HTML skeleton + CSS. One substitution token, `{project}`. No JS. |
| `orch/dashboard.js` | All client logic: fetch, partition, render, escape, age. Node-loadable. |
| `orch/server.py` | Routes `/`, `/api/state`, and the new `/dashboard.js`. |
| `tests/dashboard_render_test.js` | Node harness asserting the pure JS functions. |
| `tests/test_server.py` | Python tests: routes, markers, JS syntax, and the node harness. |

---

### Task 1: Move the JS to its own file and serve it

Pure refactor — the page must look and behave exactly as it does today when this task ends. Doing the move first means every later task edits real JavaScript instead of an escaped Python string.

**Files:**
- Create: `orch/dashboard.js`
- Modify: `orch/dashboard.py`, `orch/server.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `server.DASHBOARD_JS` — `pathlib.Path` to `orch/dashboard.js`.
  - `server.render_dashboard_js() -> (str, str)` — body and content type, matching the shape of `render_index`.
  - `dashboard.PAGE` — now substituted with `str.replace`, not `.format()`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_server.py`, add `shutil` and `subprocess` to the imports at the top.

**First, fix an existing test that this task breaks.** `test_index_renders_waiting_and_health` asserts `DISCONNECTED` appears in the page, but that string is about to move into the JS. Replace it with:

```python
    def test_index_renders_waiting_and_health_containers(self):
        html, _ = server.render_index("demo")
        # The strings themselves now live in dashboard.js; the page only has
        # to provide the containers the script fills.
        self.assertIn('id="waiting"', html)
        self.assertIn('id="health"', html)
```

Then **replace the whole `DashboardProgressTest` class** (added by the progress feature — its `{{` assertion is about to become meaningless) with:

```python
class DashboardAssetTest(unittest.TestCase):
    def test_index_references_the_js_file(self):
        html, _ = server.render_index("demo")
        self.assertIn('src="/dashboard.js"', html)
        self.assertNotIn("function esc(", html)  # JS no longer inline

    def test_index_carries_the_project_without_formatting(self):
        html, _ = server.render_index("demo")
        self.assertIn('data-project="demo"', html)
        self.assertNotIn("{project}", html)

    def test_dashboard_js_is_served(self):
        body, ctype = server.render_dashboard_js()
        self.assertIn("javascript", ctype)
        self.assertIn("function esc(", body)

    def test_dashboard_js_has_valid_syntax(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("node not installed")
        out = subprocess.run([node, "--check", str(server.DASHBOARD_JS)],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_server.py -q`
Expected: FAIL — `AttributeError: module 'orch.server' has no attribute 'render_dashboard_js'`.

- [ ] **Step 3: Create `orch/dashboard.js` with today's behaviour**

This is the existing inline script, unescaped (`{{` → `{`), plus the node-compatibility guards at the bottom. Later tasks rewrite the render functions; this step only relocates them.

```javascript
const POLL_MS = 3000;
const PROJECT = typeof document !== 'undefined'
  ? document.body.dataset.project : '';

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'
  }[c]));
}

function setHealth(ok) {
  const h = document.getElementById('health');
  const t = new Date().toLocaleTimeString();
  h.className = ok ? 'ok' : 'down';
  h.textContent = ok ? ('connected ' + t) : ('DISCONNECTED since ' + t);
}

function progressLine(t) {
  const p = t && t.progress;
  if (!p) return '';
  const step = (p.step && p.step_total) ? ' ' + p.step + '/' + p.step_total : '';
  const msg = p.message ? ' · ' + esc(p.message) : '';
  const nxt = p.next_step
    ? '<br><span class=muted>next: ' + esc(p.next_step) + '</span>' : '';
  return '<br><span class=phase>' + esc(p.phase) + step + '</span>' + msg + nxt;
}

function render(s) {
  const w = s.waiting || [];
  document.getElementById('waiting').innerHTML = w.length
    ? '<div class=waiting>WAITING ON YOU: ' + w.map(x =>
        esc(x.agent) + (x.reason ? ' (' + esc(x.reason) + ')' : '')).join(', ')
      + '</div>'
    : '';
  document.getElementById('cols').innerHTML = s.agents.map(a => {
    const ct = a.current_task
      ? esc(a.current_task.title) : '<span class=muted>no task</span>';
    const br = a.current_task && a.current_task.branch
      ? ' <span class=muted>[' + esc(a.current_task.branch) + ']</span>' : '';
    return '<div class=agent><b>' + esc(a.agent) + '</b> ' +
      '<span class="badge ' + esc(a.status) + '">' + esc(a.status) +
      '</span><br>' + ct + br + progressLine(a.current_task) + '</div>';
  }).join('');
  document.getElementById('feed').innerHTML = s.events.map(e =>
    '<div class=ev><span class=muted>' + esc(e.created_at) + '</span> ' +
    '<b>' + esc(e.agent) + '</b>/' + esc(e.kind) + ': ' + esc(e.message) +
    '</div>').join('');
}

async function tick() {
  let s;
  try {
    const r = await fetch('/api/state?project=' + encodeURIComponent(PROJECT));
    s = await r.json();
    setHealth(true);
  } catch (e) {
    setHealth(false);
    return;
  }
  if (s.error) {
    document.getElementById('cols').innerHTML =
      '<div class=agent>' + esc(s.error) + '</div>';
    return;
  }
  render(s);
}

// Browser bootstrap. Guarded so `require()`ing this file in node for tests
// doesn't try to touch the DOM or start polling.
if (typeof document !== 'undefined') {
  tick();
  setInterval(tick, POLL_MS);
}

if (typeof module !== 'undefined') {
  module.exports = { esc, progressLine, render };
}
```

- [ ] **Step 4: Rewrite `orch/dashboard.py` as HTML + CSS only**

Replace the entire file. Note `{project}` stays a literal token — `render_index` substitutes it with `str.replace`, so CSS braces need no doubling.

```python
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
```

- [ ] **Step 5: Serve the file and switch the substitution**

In `orch/server.py`, add to the imports:

```python
import html
from pathlib import Path
```

Add below the existing imports:

```python
DASHBOARD_JS = Path(__file__).with_name("dashboard.js")
```

Replace `render_index` (`orch/server.py:22-23`) with:

```python
def render_index(project):
    # str.replace, not .format(): the page carries raw CSS, whose braces would
    # otherwise all need doubling. The project name is escaped because it lands
    # in both an attribute and the page text.
    body = PAGE.replace("{project}", html.escape(project, quote=True))
    return body, "text/html; charset=utf-8"


def render_dashboard_js():
    return (DASHBOARD_JS.read_text(encoding="utf-8"),
            "application/javascript; charset=utf-8")
```

In `do_GET`, add the route ahead of the 404 fallback:

```python
            elif parsed.path == "/dashboard.js":
                body, ctype = render_dashboard_js()
                self._send(body, ctype)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/test_server.py -q`
Expected: PASS.

- [ ] **Step 7: Look at it**

Run `python orch.py serve --project <a project with tasks>`, open http://127.0.0.1:8787/, confirm it renders exactly as before, and check the browser console is clean. Ctrl+C to stop.

- [ ] **Step 8: Commit**

```bash
git add orch/dashboard.py orch/dashboard.js orch/server.py tests/test_server.py
git commit -m "refactor(dashboard): move client JS to its own served file"
```

---

### Task 2: Pure helpers and the node test harness

Adds the logic the new layout needs — age formatting and the working/ready/idle partition — with real assertions, before any markup depends on them.

**Files:**
- Modify: `orch/dashboard.js`
- Create: `tests/dashboard_render_test.js`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `esc` from Task 1.
- Produces, all exported via `module.exports`:
  - `ago(iso) -> string` — `'5s ago'`, `'12m ago'`, `'2h ago'`, `'3d ago'`, `''` when unparseable. Mirrors `cli._age`.
  - `partition(state) -> {working: agent[], ready: task[], idle: string[]}` — `working` sorted by agent name, `ready` sorted oldest first.

- [ ] **Step 1: Write the failing node harness**

Create `tests/dashboard_render_test.js`:

```javascript
const assert = require('assert');
const path = require('path');
const d = require(path.join(__dirname, '..', 'orch', 'dashboard.js'));

const now = Date.now();
const iso = ms => new Date(now - ms).toISOString();

// esc neutralises markup wherever a title or message lands in innerHTML
assert.strictEqual(d.esc('<b>x</b>'), '&lt;b&gt;x&lt;/b&gt;');
assert.strictEqual(d.esc('a "q" & b'), 'a &quot;q&quot; &amp; b');
assert.strictEqual(d.esc(null), '');

// ago mirrors cli._age's thresholds so both surfaces read the same
assert.strictEqual(d.ago(iso(5 * 1000)), '5s ago');
assert.strictEqual(d.ago(iso(90 * 1000)), '1m ago');
assert.strictEqual(d.ago(iso(2 * 3600 * 1000)), '2h ago');
assert.strictEqual(d.ago(iso(3 * 86400 * 1000)), '3d ago');
assert.strictEqual(d.ago('not-a-date'), '');

// partition: a done task belongs to ready, never to working, and its agent
// is not idle either — it must appear exactly once on the page
const state = {
  agents: [
    {agent: 'C', status: 'executing',
     current_task: {id: 3, title: 'c', status: 'executing', progress: null}},
    {agent: 'A', status: 'discussing',
     current_task: {id: 1, title: 'a', status: 'discussing', progress: null}},
    {agent: 'D', status: 'done',
     current_task: {id: 4, title: 'd', status: 'done', progress: null}},
    {agent: 'F', status: 'idle', current_task: null}
  ],
  tasks: [
    {id: 3, agent: 'C', status: 'executing', title: 'c', updated_at: iso(0)},
    {id: 1, agent: 'A', status: 'discussing', title: 'a', updated_at: iso(0)},
    {id: 4, agent: 'D', status: 'done', title: 'd', branch: 'feat/d',
     updated_at: iso(60 * 1000)},
    {id: 5, agent: 'E', status: 'done', title: 'e', branch: 'feat/e',
     updated_at: iso(3600 * 1000)}
  ]
};
const p = d.partition(state);
assert.deepStrictEqual(p.working.map(a => a.agent), ['A', 'C'],
                       'working sorts alphabetically');
assert.deepStrictEqual(p.ready.map(t => t.agent), ['E', 'D'],
                       'ready sorts oldest first');
assert.deepStrictEqual(p.idle, ['F']);

console.log('dashboard.js behavioural checks passed');
```

- [ ] **Step 2: Add the pytest runner for it**

In `tests/test_server.py`, add to `DashboardAssetTest`:

```python
    def test_dashboard_js_behaviour(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("node not installed")
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "dashboard_render_test.js")
        out = subprocess.run([node, script], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
```

- [ ] **Step 3: Run to verify it fails**

Run: `python -m pytest tests/test_server.py -q`
Expected: FAIL — the node harness exits non-zero with `TypeError: d.ago is not a function`.

- [ ] **Step 4: Implement `ago` and `partition`**

In `orch/dashboard.js`, add after `esc`:

```javascript
const ACTIVE = ['queued', 'discussing', 'executing', 'blocked'];

function ago(iso) {
  // Mirrors cli._age. Stated plainly, with no staleness verdict attached:
  // 41m on awaiting_approval means the human hasn't answered, not that
  // anything is broken.
  const then = Date.parse(iso);
  if (isNaN(then)) return '';
  const secs = Math.max(Math.floor((Date.now() - then) / 1000), 0);
  if (secs < 60) return secs + 's ago';
  if (secs < 3600) return Math.floor(secs / 60) + 'm ago';
  if (secs < 86400) return Math.floor(secs / 3600) + 'h ago';
  return Math.floor(secs / 86400) + 'd ago';
}

function partition(state) {
  // get_state falls back to an agent's most recent task when it has no active
  // one, so an agent whose task is done arrives here looking like a working
  // agent with status 'done'. Splitting on the task's status rather than the
  // agent's is what keeps it from being listed twice.
  const working = state.agents
    .filter(a => ACTIVE.includes(a.status))
    .sort((a, b) => a.agent.localeCompare(b.agent));
  const ready = state.tasks
    .filter(t => t.status === 'done')
    .sort((a, b) => String(a.updated_at).localeCompare(String(b.updated_at)));
  const busy = new Set(working.map(a => a.agent));
  ready.forEach(t => busy.add(t.agent));
  const idle = state.agents
    .filter(a => !busy.has(a.agent))
    .map(a => a.agent)
    .sort();
  return {working: working, ready: ready, idle: idle};
}
```

Extend the exports at the bottom:

```javascript
if (typeof module !== 'undefined') {
  module.exports = { esc, ago, partition, progressLine, render };
}
```

- [ ] **Step 5: Run to verify it passes**

Run: `python -m pytest tests/test_server.py -q`
Expected: PASS. If node is installed you should also see the harness pass directly:
`node tests/dashboard_render_test.js` → `dashboard.js behavioural checks passed`.

- [ ] **Step 6: Commit**

```bash
git add orch/dashboard.js tests/dashboard_render_test.js tests/test_server.py
git commit -m "feat(dashboard): age helper and working/ready/idle partition"
```

---

### Task 3: The new page — skeleton, CSS, and the working section

**Files:**
- Modify: `orch/dashboard.py`, `orch/dashboard.js`
- Test: `tests/dashboard_render_test.js`, `tests/test_server.py`

**Interfaces:**
- Consumes: `esc`, `ago`, `partition` from Tasks 1-2.
- Produces:
  - `agentBlock(agent) -> string` — one working agent's HTML.
  - `progressBlock(task) -> string` — phase line, bar, message, next, age. Replaces `progressLine`.
  - Stable DOM container ids: `#counts`, `#waiting`, `#working`, `#ready`, `#readyhdr`, `#idle`, `#feed`, `#feedsummary`.

- [ ] **Step 1: Write the failing assertions**

Append to `tests/dashboard_render_test.js`, before the final `console.log`:

```javascript
// A bar is drawn only when the phase actually has a step count
const withSteps = d.progressBlock({progress: {
  phase: 'implementation', step: 3, step_total: 6,
  message: 'wiring the CLI', next_step: 'status output', updated_at: iso(0)}});
assert.ok(withSteps.includes('class=bar'), 'steps get a bar');
assert.ok(withSteps.includes('3/6'));
assert.ok(withSteps.includes('width:50%'), '3 of 6 is half');
assert.ok(withSteps.includes('next: status output'));

const noSteps = d.progressBlock({progress: {
  phase: 'planning', step: null, step_total: null,
  message: 'drafting', next_step: null, updated_at: iso(0)}});
assert.ok(!noSteps.includes('class=bar'), 'no steps, no bar');
assert.ok(noSteps.includes('planning'));

assert.strictEqual(d.progressBlock({progress: null}), '');
assert.strictEqual(d.progressBlock(null), '');

// Markup in a title must render as text
const block = d.agentBlock({
  agent: 'A', status: 'executing',
  current_task: {title: '<script>x</script>', branch: 'feat/a',
                 progress: null}});
assert.ok(!block.includes('<script>x'), 'title is escaped');
assert.ok(block.includes('&lt;script&gt;'));
assert.ok(block.includes('feat/a'));
```

In `tests/test_server.py`, add to `DashboardAssetTest`:

```python
    def test_index_has_the_new_sections(self):
        html, _ = server.render_index("demo")
        for marker in ('id="working"', 'id="ready"', 'id="counts"',
                       'id="idle"', 'id="feed"', "READY TO MERGE"):
            self.assertIn(marker, html)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_server.py -q`
Expected: FAIL — `d.progressBlock is not a function`, and the marker assertions fail.

- [ ] **Step 3: Rewrite `orch/dashboard.py`**

Replace the entire file:

```python
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
```

- [ ] **Step 4: Replace `progressLine` with `progressBlock` and add `agentBlock`**

In `orch/dashboard.js`, delete `progressLine` and add:

```javascript
function progressBlock(t) {
  const p = t && t.progress;
  if (!p) return '';
  const hasSteps = Boolean(p.step && p.step_total);
  // No bar without a step count. A bar for `planning` would have to invent a
  // percentage, and a bar that silently means nothing is worse than no bar.
  const pct = hasSteps ? Math.round((p.step / p.step_total) * 100) : 0;
  const bar = hasSteps
    ? '<div class=bar><div class=fill style="width:' + pct + '%"></div></div>' +
      '<span class=steps>' + p.step + '/' + p.step_total + '</span>'
    : '';
  const msg = p.message ? '<div class=msg>' + esc(p.message) + '</div>' : '';
  const nxt = p.next_step
    ? '<span>next: ' + esc(p.next_step) + '</span>' : '';
  return '<div class=prog><span class=phase>' + esc(p.phase) + '</span>' +
    bar + '</div>' + msg +
    '<div class=meta>' + nxt +
    '<span class=age>' + ago(p.updated_at) + '</span></div>';
}

function agentBlock(a) {
  const t = a.current_task;
  const title = t ? esc(t.title) : '<span class=muted>no task</span>';
  const branch = t && t.branch
    ? '<span class=branch>' + esc(t.branch) + '</span>' : '';
  return '<div class=agent><div class=head>' +
    '<b class=letter>' + esc(a.agent) + '</b>' +
    '<span class="badge ' + esc(a.status) + '">' + esc(a.status) + '</span>' +
    '<span class=title>' + title + '</span>' + branch + '</div>' +
    progressBlock(t) + '</div>';
}
```

- [ ] **Step 5: Rewrite `render` for the working section**

Replace `render` in `orch/dashboard.js` with:

```javascript
function setText(id, text) {
  document.getElementById(id).textContent = text;
}

function render(s) {
  const parts = partition(s);
  const w = s.waiting || [];
  document.getElementById('waiting').innerHTML = w.length
    ? '<div class=waiting>WAITING ON YOU: ' + w.map(x =>
        esc(x.agent) + (x.reason ? ' (' + esc(x.reason) + ')' : '')).join(', ')
      + '</div>'
    : '';
  document.getElementById('working').innerHTML =
    parts.working.length
      ? parts.working.map(agentBlock).join('')
      : '<div class=agent><span class=muted>no agent is working</span></div>';
  // The feed lives inside a <details> that is never re-created, so whether you
  // left it open survives every poll.
  document.getElementById('feed').innerHTML = s.events.map(e =>
    '<div class=ev><span class=muted>' + esc(e.created_at) + '</span> ' +
    '<b>' + esc(e.agent) + '</b>/' + esc(e.kind) + ': ' + esc(e.message) +
    '</div>').join('');
  setText('feedsummary', 'recent activity (' + s.events.length + ')');
}
```

And in `tick`, change the error branch's target from `cols` to `working`:

```javascript
  if (s.error) {
    document.getElementById('working').innerHTML =
      '<div class=agent>' + esc(s.error) + '</div>';
    return;
  }
```

Update the exports:

```javascript
if (typeof module !== 'undefined') {
  module.exports = { esc, ago, partition, progressBlock, agentBlock, render };
}
```

- [ ] **Step 6: Run to verify it passes**

Run: `python -m pytest tests/test_server.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add orch/dashboard.py orch/dashboard.js tests/dashboard_render_test.js tests/test_server.py
git commit -m "feat(dashboard): new layout with per-agent progress bars"
```

---

### Task 4: Ready-to-merge strip, idle line, header counts

**Files:**
- Modify: `orch/dashboard.js`
- Test: `tests/dashboard_render_test.js`

**Interfaces:**
- Consumes: `partition`, `ago`, `esc`.
- Produces: `mergeRow(task) -> string`; `render` now fills `#ready`, `#readyhdr`, `#idle`, `#counts`.

- [ ] **Step 1: Write the failing assertions**

Append to `tests/dashboard_render_test.js`, before the final `console.log`:

```javascript
// The merge strip shows branch, title and how long it has been sitting
const row = d.mergeRow({agent: 'D', branch: 'feat/d-api',
                        title: 'Notifications', updated_at: iso(12 * 60 * 1000)});
assert.ok(row.includes('feat/d-api'));
assert.ok(row.includes('Notifications'));
assert.ok(row.includes('12m ago'));

// A task reported done from main has no branch recorded; say so rather than
// rendering an empty gap
assert.ok(d.mergeRow({agent: 'D', branch: null, title: 'x',
                      updated_at: iso(0)}).includes('no branch'));
```

- [ ] **Step 2: Run to verify it fails**

Run: `node tests/dashboard_render_test.js`
Expected: FAIL — `d.mergeRow is not a function`.

- [ ] **Step 3: Add `mergeRow`**

In `orch/dashboard.js`, after `agentBlock`:

```javascript
function mergeRow(t) {
  const branch = t.branch
    ? esc(t.branch) : '<span class=muted>no branch</span>';
  return '<div class=merge>' +
    '<b class=letter>' + esc(t.agent) + '</b>' +
    '<span class=branch>' + branch + '</span>' +
    '<span class=title>' + esc(t.title) + '</span>' +
    '<span class=age>done ' + ago(t.updated_at) + '</span></div>';
}
```

- [ ] **Step 4: Fill the remaining sections in `render`**

In `orch/dashboard.js`, add to `render` immediately after the `working` assignment:

```javascript
  // Hide the header too when nothing is waiting — an empty "READY TO MERGE"
  // heading reads like a broken query.
  const hasReady = parts.ready.length > 0;
  document.getElementById('readyhdr').style.display = hasReady ? '' : 'none';
  document.getElementById('ready').innerHTML =
    parts.ready.map(mergeRow).join('');
  setText('idle', parts.idle.length ? 'idle: ' + parts.idle.join(', ') : '');
  setText('counts', parts.working.length + ' working · ' +
                    parts.ready.length + ' ready');
```

Add `mergeRow` to the exports.

- [ ] **Step 5: Run to verify it passes**

Run: `python -m pytest -q`
Expected: PASS — the whole suite.

- [ ] **Step 6: Commit**

```bash
git add orch/dashboard.js tests/dashboard_render_test.js
git commit -m "feat(dashboard): ready-to-merge strip, idle line, header counts"
```

---

### Task 5: Verify against real data and document

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Build a realistic project and look at it**

```bash
export ORCH_DB="$TEMP/orch-dash.db"
rm -f "$ORCH_DB"
python orch.py init dash
python orch.py task add --project dash --agent A --title "Progress reporting" --status executing --branch feat/a-progress
python orch.py task add --project dash --agent B --title "Login form" --status discussing
python orch.py task add --project dash --agent C --title "Search API" --status executing --branch feat/c-search
python orch.py task add --project dash --agent D --title "Notifications" --status done --branch feat/d-api
python orch.py task add --project dash --agent E --title "Search indexing" --status done --branch feat/e-search
python orch.py progress --project dash --agent A --phase implementation --step 3 --step-total 6 --msg "wiring the orch progress CLI" --next "status output"
python orch.py progress --project dash --agent B --phase awaiting_approval --msg "plan ready: docs/superpowers/plans/login.md" --next "human approval"
python orch.py progress --project dash --agent C --phase checkpoint --msg "codex review" --next "commit"
python orch.py serve --project dash
```

Open http://127.0.0.1:8787/ and check each acceptance criterion by eye:

1. A, B, C appear under WORKING in that order; D and E appear once each under READY TO MERGE and nowhere else.
2. Only A has a bar, at 50%. B and C show their phase with no bar.
3. Ages render, and the browser console is clean.
4. Expand "recent activity", wait through two polls, confirm it stays open.
5. Reload with the server stopped — the health indicator flips to DISCONNECTED.

- [ ] **Step 2: Check that a title with markup renders as text**

```bash
python orch.py task add --project dash --agent G --title "<img src=x onerror=alert(1)>" --status executing
```

Reload. The title must appear as literal text, with no alert and no broken layout. Then `rm -f "$ORCH_DB"`.

- [ ] **Step 3: Update the README**

In `README.md`, replace the `serve` row of the Commands table:

```markdown
| `serve [--port]` | on-demand web dashboard: working agents with phase and step progress, tasks waiting to merge, and a collapsed event feed (defaults to the only project if there is one) |
```

- [ ] **Step 4: Run the complete suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs(dashboard): describe what the dashboard shows"
```

---

## Verification checklist

Against the spec's acceptance criteria:

1. Five agents, each showing what they're doing and steps remaining — Tasks 3, 4; verified by eye in Task 5.
2. `done` tasks visible with age, exactly once — Task 2 (`partition`, tested), Task 4 (`mergeRow`).
3. Stable agent order — Task 2, asserted in the node harness.
4. No bar without a step count — Task 3, asserted in the node harness.
5. Markup renders as text — Task 3 assertion plus the live check in Task 5 Step 2.
6. JS syntax-checked by the suite — Task 1 (`node --check`), skipping cleanly without node.
