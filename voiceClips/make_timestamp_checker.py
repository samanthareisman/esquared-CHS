#!/usr/bin/env python3
"""
make_timestamp_checker.py
Writes timestamp_checker.html next to this script. Open it in a browser (double-click) to
audition every clip that has a word-timestamp json: words light up as the audio plays, using
the same times the task uses. Click a word to hear from just before its timestamp. The offset
slider shows what a global shift would do (it does not change any file).
Run again after regenerating timestamps.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
clips = []
for sub in ("fixedVars", "dynamicVars"):
    d = HERE / "audio" / sub
    for j in sorted(d.glob("*.json")):
        if j.name == "manifest.json" or j.stem.endswith("-cues"):
            continue
        mp3 = j.with_suffix(".mp3")
        if not mp3.exists():
            continue
        data = json.loads(j.read_text())
        if not data:
            continue
        cues_p = j.with_name(j.stem + "-cues.json")
        cues = json.loads(cues_p.read_text()) if cues_p.exists() else {}
        clips.append({"name": j.stem, "src": f"audio/{sub}/{mp3.name}", "words": data, "cues": cues})

html = """<!doctype html><meta charset="utf-8"><title>Timestamp checker</title>
<style>
body{font-family:Arial,sans-serif;margin:24px;max-width:900px}
select,button{font-size:16px;margin:4px 0}
#words{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}
.w{padding:10px 16px;border:2px solid #ccc;border-radius:10px;cursor:pointer;font-size:20px}
.w small{display:block;font-size:12px;color:#777}
.w.on{border-color:#f5a623;background:#fff6e0}
.cue{padding:6px 12px;border:2px solid #ccc;border-radius:8px;margin:4px 0}
.cue.on{border-color:#c00;background:#fee}
#t{font-variant-numeric:tabular-nums;font-size:22px}
</style>
<h2>Timestamp checker</h2>
<button id="prev">&larr; Prev</button> <select id="sel" size="1"></select> <button id="next">Next &rarr;</button>
<label><input type="checkbox" id="auto" checked> autoplay on change</label> <span id="pos"></span><br>
<audio id="a" controls style="width:100%"></audio>
<div>Time: <span id="t">0.00</span>s &nbsp; Offset (s): <input id="off" type="range" min="-0.5" max="0.5" step="0.05" value="0">
<span id="offv">0.00</span> (positive = highlight later)</div>
<div id="words"></div><div id="cues"></div>
<script>
const CLIPS = __DATA__;
const sel = document.getElementById('sel'), a = document.getElementById('a');
const wordsDiv = document.getElementById('words'), cuesDiv = document.getElementById('cues');
const off = document.getElementById('off');
CLIPS.forEach((c, i) => sel.add(new Option(c.name, i)));
let cur = null;
function load() {
  cur = CLIPS[sel.value]; a.src = cur.src;
  document.getElementById('pos').textContent = (+sel.value + 1) + ' / ' + CLIPS.length;
  wordsDiv.innerHTML = ''; cuesDiv.innerHTML = '';
  Object.entries(cur.words).sort((x, y) => x[1] - y[1]).forEach(([w, t]) => {
    const d = document.createElement('div'); d.className = 'w'; d.dataset.t = t;
    d.innerHTML = w + '<small>' + t.toFixed(2) + 's</small>';
    d.onclick = () => { a.currentTime = Math.max(0, t - 0.3); a.play(); };
    wordsDiv.appendChild(d);
  });
  Object.entries(cur.cues).forEach(([n, c]) => {
    const d = document.createElement('div'); d.className = 'cue'; d.dataset.s = c.start; d.dataset.e = c.end;
    d.textContent = n + '  ' + c.start.toFixed(2) + ' - ' + c.end.toFixed(2) + 's';
    d.onclick = () => { a.currentTime = Math.max(0, c.start - 0.3); a.play(); };
    cuesDiv.appendChild(d);
  });
}
function go(d) {
  const n = CLIPS.length; sel.value = (+sel.value + d + n) % n; load();
  if (document.getElementById('auto').checked) { a.currentTime = 0; a.play(); }
}
sel.onchange = () => go(0);
document.getElementById('next').onclick = () => go(1);
document.getElementById('prev').onclick = () => go(-1);
document.addEventListener('keydown', e => {
  if (e.key === 'ArrowRight') go(1);
  else if (e.key === 'ArrowLeft') go(-1);
  else if (e.key === ' ' && e.target === document.body) { e.preventDefault(); a.paused ? a.play() : a.pause(); }
});
off.oninput = () => document.getElementById('offv').textContent = (+off.value).toFixed(2);
(function tick() {
  const t = a.currentTime - (+off.value);
  document.getElementById('t').textContent = a.currentTime.toFixed(2);
  const ws = [...wordsDiv.children];
  let curW = null;
  ws.forEach(d => { if (t >= +d.dataset.t) curW = d; });
  ws.forEach(d => d.classList.toggle('on', d === curW));
  [...cuesDiv.children].forEach(d => d.classList.toggle('on', t >= +d.dataset.s && t < +d.dataset.e));
  requestAnimationFrame(tick);
})();
load();
</script>"""
out = HERE / "timestamp_checker.html"
out.write_text(html.replace("__DATA__", json.dumps(clips)))
print(f"{len(clips)} clips -> {out}")
