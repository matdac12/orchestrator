const POLL_MS = 3000;
const PROJECT = typeof document !== 'undefined'
  ? document.body.dataset.project : '';

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'
  }[c]));
}

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

function setHealth(ok) {
  const h = document.getElementById('health');
  const t = new Date().toLocaleTimeString();
  h.className = ok ? 'ok' : 'down';
  h.textContent = ok ? ('connected ' + t) : ('DISCONNECTED since ' + t);
}

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
    document.getElementById('working').innerHTML =
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
  module.exports = { esc, ago, partition, progressBlock, agentBlock, render };
}
