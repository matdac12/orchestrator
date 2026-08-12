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

console.log('dashboard.js behavioural checks passed');
