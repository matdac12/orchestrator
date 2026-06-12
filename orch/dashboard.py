PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>orch — {project}</title>
<style>
 body{{font:14px system-ui,sans-serif;margin:0;background:#0f1115;color:#e6e6e6}}
 header{{padding:12px 20px;background:#171a21;font-weight:600}}
 .cols{{display:flex;gap:12px;padding:16px;flex-wrap:wrap}}
 .agent{{flex:1;min-width:200px;background:#171a21;border-radius:8px;padding:12px}}
 .badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px}}
 .queued{{background:#444}} .discussing{{background:#1f6feb}}
 .executing{{background:#0e7490}} .blocked{{background:#b54708}}
 .done{{background:#238636}} .merged{{background:#8957e5}}
 .idle{{background:#333}}
 .feed{{padding:0 16px 24px}} .ev{{padding:6px 0;border-top:1px solid #222}}
 .muted{{color:#8b949e;font-size:12px}}
</style></head><body>
<header>orch — {project}</header>
<div id="cols" class="cols"></div>
<div class="feed"><h3>events</h3><div id="feed"></div></div>
<script>
function esc(v){{
  return String(v).replace(/[&<>"']/g, c => ({{
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
}}
async function tick(){{
  const r = await fetch('/api/state?project={project_qs}');
  const s = await r.json();
  if(s.error){{document.getElementById('cols').innerHTML =
    '<div class=agent>'+esc(s.error)+'</div>';return;}}
  document.getElementById('cols').innerHTML = s.agents.map(a=>{{
    const ct = a.current_task ? esc(a.current_task.title) : '<span class=muted>no task</span>';
    const br = a.current_task && a.current_task.branch ?
      ' <span class=muted>['+esc(a.current_task.branch)+']</span>' : '';
    return '<div class=agent><b>'+esc(a.agent)+'</b> '+
      '<span class="badge '+esc(a.status)+'">'+esc(a.status)+'</span><br>'+ct+br+'</div>';
  }}).join('');
  document.getElementById('feed').innerHTML = s.events.map(e=>
    '<div class=ev><span class=muted>'+esc(e.created_at)+'</span> '+
    '<b>'+esc(e.agent)+'</b>/'+esc(e.kind)+': '+esc(e.message)+'</div>').join('');
}}
tick(); setInterval(tick, 3000);
</script></body></html>"""
