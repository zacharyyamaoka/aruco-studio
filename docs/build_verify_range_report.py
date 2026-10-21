"""The range strip's report (lane os-verifyrange, 2026-10-21): what was built, the
hero video and stills of the real app, the measured timing, the two-OpenCV
finding, how sure a range is, the camera library, the gates and what needs Zach.

    .venv/bin/python docs/build_verify_range_report.py --src reports/media/verify-range-2026-10-21-src

Reads <src>/evidence.json (the numbers measured this session), its stills and
hero.mp4 / hero.gif (docs/record_verify_range_hero.mjs), and the timing bench's
latest run (web/scripts/bench-verify-range.mjs, ~/.local/share/aruco_studio_bench/
verify_range/runs_table.jsonl). Writes /home/bam/aruco-studio/reports/media/
verify-range-2026-10-21.html (git-ignored: it inlines media). Standard library.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path("/home/bam/aruco-studio")
OUT = MAIN / "reports/media/verify-range-2026-10-21.html"
BENCH = Path.home() / ".local/share/aruco_studio_bench/verify_range"


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def m(mm) -> str:
    if mm is None:
        return "—"
    return f"{mm / 1000.0:.2f} m" if mm >= 1000.0 else f"{mm:.0f} mm"


def s(ms) -> str:
    return "—" if ms is None else f"{ms / 1000.0:.1f} s"


def data_uri(p: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")


def bench_rows() -> dict:
    """The bench's latest run: {host: {board: run}}."""
    f = BENCH / "runs_table.jsonl"
    rows = [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
    stamp = max(r["run_id"].split("-")[0] + "-" + r["run_id"].split("-")[1] for r in rows)
    out: dict = {}
    for r in rows:
        if r["run_id"].startswith(stamp):
            out.setdefault(r["facets"]["host"], {})[r["facets"]["board"]] = r
    return {"stamp": stamp, "hosts": out}


CSS = r"""
:root{--bg:#f6f7f9;--panel:#fff;--line:#e2e5ea;--text:#1c222b;--muted:#6b7480;--accent:#2f6fed;--ok:#18865a;--bad:#cf3b3b;--warn:#a8650e;
 --f:Inter,"Segoe UI",system-ui,-apple-system,sans-serif;--mono:ui-monospace,"Cascadia Mono",Consolas,monospace}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--panel:#1c2027;--line:#2c323b;--text:#e6e9ee;--muted:#98a1ad;--accent:#5b8ff0;--ok:#4cc27a;--bad:#f06a5f;--warn:#e3ac4b}}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 var(--f)}
main{max-width:1060px;margin:0 auto;padding:28px 16px 60px}
h1{font-size:26px;line-height:1.25;margin:0 0 6px} h2{font-size:18px;margin:34px 0 8px} h3{font-size:14px;margin:18px 0 6px}
.kick{font:600 11px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.verdict{font-size:16px;margin:10px 0 4px} .verdict b{color:var(--ok)}
.muted{color:var(--muted)} .ok{color:var(--ok)} .bad{color:var(--bad)} .warn{color:var(--warn)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:12px 0}
figure{margin:12px 0} figcaption{font-size:12.5px;color:var(--muted);margin-top:6px}
img,video{max-width:100%;height:auto;border-radius:6px;border:1px solid var(--line);display:block}
table{border-collapse:collapse;width:100%;font-size:13px} th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{font:600 10.5px/1.3 var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.tw{overflow-x:auto} code{font:12.5px var(--mono)} pre{font:12px/1.45 var(--mono);background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px 12px;overflow-x:auto}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px} @media (max-width:760px){.grid2{grid-template-columns:1fr}}
ul{padding-left:20px} li{margin:3px 0}
.pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:11.5px;border:1px solid var(--line)}
.pass{color:var(--ok);font-weight:600} .fail{color:var(--bad);font-weight:600}
"""


def build(src: Path) -> str:
    ev = json.loads((src / "evidence.json").read_text())
    b = bench_rows()
    H = b["hosts"]
    boards = ev["boards"]                          # [{id, name}]

    def run(host, bid):
        return H.get(host, {}).get(bid)

    # ---- the timing table (browser, CPython 5.0, CPython 4.11)
    trs = []
    tot = {h: 0.0 for h in H}
    for bd in boards:
        cells = []
        for h in ("browser", "cpython-cv411", "cpython"):
            r = run(h, bd["id"])
            if not r:
                cells.append("<td>—</td>")
                continue
            tot[h] += r["metrics"]["ms_sum"]
            d = r["detail"]
            cells.append(f'<td><b>{s(r["metrics"]["ms_sum"])}</b><br><span class="muted">{r["metrics"]["renders_sum"]} views · '
                         f'{m(d["near_mm"])}–{m(d["far_mm"])}</span></td>')
        trs.append(f'<tr><td>{esc(bd["name"])}</td>{"".join(cells)}<td class="muted">32 s</td></tr>')
    trs.append('<tr><td><b>The document (one worker, one after another)</b></td>'
               + "".join(f'<td><b>{s(tot.get(h))}</b></td>' for h in ("browser", "cpython-cv411", "cpython")) + '<td class="muted">128 s</td></tr>')
    load = (run("browser", boards[0]["id"]) or {}).get("detail", {}).get("opencv_load_ms")
    timing = f'''<div class="tw"><table><tr><th>Board (RealSense D435)</th><th>Browser · Pyodide worker · OpenCV 4.11</th>
      <th>CPython · OpenCV 4.11</th><th>CPython · OpenCV 5.0 (.venv)</th><th>Proposal's estimate</th></tr>{"".join(trs)}</table></div>
      <p class="muted">Bench run {esc(b["stamp"])} (<code>npm --prefix web run bench:verify-range</code>, load average {esc(ev["load"])} on 24 cores from
      peer lanes). OpenCV's first load in the browser ({s(load)}) is kept apart. Written as vt-kpi <code>verify_range_ms</code>,
      <code>verify_range_doc_ms</code> and <code>verify_range_ms_per_view</code> to <code>{esc(str(BENCH))}</code> (its own producer
      directory: bench-feature rewrites its catalog each run).</p>'''

    # ---- two OpenCVs
    tw = []
    for bd in boards:
        a, c = run("cpython-cv411", bd["id"]), run("cpython", bd["id"])
        br = run("browser", bd["id"])
        if not (a and c):
            continue
        same = (a["detail"]["near_mm"], a["detail"]["far_mm"], a["detail"]["band_mm"]) == (br["detail"]["near_mm"], br["detail"]["far_mm"], br["detail"]["band_mm"]) if br else None
        fa, fc = a["detail"]["far_mm"], c["detail"]["far_mm"]
        worse = "4.11" if (fa or -1) <= (fc or -1) else "5.0"
        tw.append(f'<tr><td>{esc(bd["name"])}</td><td>{m(a["detail"]["near_mm"])}–{m(fa)}</td><td>{m(c["detail"]["near_mm"])}–{m(fc)}</td>'
                  f'<td>{"identical" if same else ("differs" if same is False else "—")}</td><td>{worse}</td></tr>')
    sw = "".join(f'<tr><td>{esc(r["board"])}</td><td>{esc(r["d"])}</td><td>{esc(r["cv5img_cv5det"])}</td><td>{esc(r["cv4img_cv5det"])}</td>'
                 f'<td>{esc(r["cv5img_cv4det"])}</td><td>{esc(r["cv4img_cv4det"])}</td></tr>' for r in ev["swap"])
    steps = "".join(f'<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>' for k, v in ev["steps"].items())

    # ---- how sure
    cal = ev["calibration"]

    # ---- the library
    def links(c):
        return " ".join('<a href="%s">[%d]</a>' % (esc(x["url"]), i + 1) for i, x in enumerate(c["sources"]))

    def lib_row(c):
        derived = (" · derived: " + esc(c["derived"])) if c["derived"] else ""
        focus = m(c["focus_mm"]) if c["focus_mm"] else "—"
        star = "*" if c["derived"] else ""
        return (f'<tr><td><b>{esc(c["name"])}</b></td><td>{esc(c["stream"])}</td><td>{c["resolution"][0]}×{c["resolution"][1]}</td>'
                f'<td>{c["hfov_deg"]}°{star}</td><td>{focus}</td><td class="muted">{esc(c["note"])}{derived}</td><td>{links(c)}</td></tr>')

    lib = "".join(lib_row(c) for c in ev["library"])

    # ---- media
    vid = src / "hero.mp4"
    gif = src / "hero.gif"
    hero = ""
    if vid.exists():
        poster = data_uri(src / "strip-verdicts.webp", "image/webp") if (src / "strip-verdicts.webp").exists() else ""
        hero = (f'<figure><video controls muted loop autoplay playsinline poster="{poster}" width="960">'
                f'<source src="{data_uri(vid, "video/mp4")}" type="video/mp4">'
                + (f'<img src="{os.path.relpath(gif, OUT.parent)}" alt="the flow, as a GIF">' if gif.exists() else "")
                + f'</video><figcaption>{esc(ev["hero_caption"])}'
                + (f' · <a href="{os.path.relpath(gif, OUT.parent)}">GIF</a>' if gif.exists() else "") + '</figcaption></figure>')

    def still(name, cap):
        p = src / f"{name}.webp"
        if not p.exists():
            return ""
        return f'<figure><img src="{data_uri(p, "image/webp")}" alt="{esc(cap)}"><figcaption>{esc(cap)}</figcaption></figure>'

    gates = "".join(f'<tr><td>{esc(g["gate"])}</td><td class="{"ok" if g["ok"] else "bad"}"><b>{esc(g["result"])}</b></td><td class="muted">{esc(g.get("note", ""))}</td></tr>'
                    for g in ev["gates"])
    commits = "".join(f'<li><code>{esc(c["sha"])}</code> {esc(c["subject"])}</li>' for c in ev["commits"])
    files = "".join(f'<li><code>{esc(f)}</code></li>' for f in ev["files"])

    def lis(xs):
        return "".join(f"<li>{x}</li>" for x in xs)

    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Verify range strip</title><style>{CSS}</style></head><body><main>
<div class="kick">ArUco Studio · lane os-verifyrange · 2026-10-21</div>
<h1>Verify answers with a range now</h1>
<p class="verdict"><b>Pick a camera; every marker shows the distances it reads at, on one axis; a required distance, batch-set, turns each into PASS or FAIL with the fix.</b>
On <code>lane/os-verifyrange</code>, not merged. The browser runs OpenCV 4.11 and the repo's CPython 5.0, and they disagree by up to 2× near the limits (below).</p>
{hero}
<div class="grid2">{still("strip-verdicts", "The strip: two markers on the D435, a required 300 mm–2 m set on both at once; one PASS, one FAIL with its size fix")}
{still("camera-picker", "The camera library, searched: every row is the maker's own numbers, linked")}</div>
<div class="grid2">{still("strip-measuring", "While it measures: the selected marker first, a slice at a time; nothing else waits")}
{still("bench-at-far", "A band's far end opens the bench on that camera at that distance (the manual sweep stays)")}</div>

<h2>Measured timing</h2>
{timing}
<div class="card"><b>Never blocks.</b> {esc(ev["never_blocks"])}</div>

<h2>Two OpenCVs disagree, so the table says which one it used</h2>
<p>The browser's Verify runs <b>OpenCV 4.11.0</b> (Pyodide 314's); <code>requirements.txt</code> pins <b>5.0.0.93</b> for CPython. They draw the same
view differently, and near the limits that moves a range a lot. Their detectors agree. Swapping the pictures shows it is the rendering:</p>
<div class="tw"><table><tr><th>Board</th><th>Distance</th><th>5.0 picture · 5.0 detector</th><th>4.11 picture · 5.0 detector</th>
<th>5.0 picture · 4.11 detector</th><th>4.11 picture · 4.11 detector</th></tr>{sw}</table></div>
<p class="muted">24 cases each, the reads of every id. Step by step, with OpenCV 4.11 in CPython: {esc(ev["steps_note"])}</p>
<div class="tw"><table><tr><th>Step (same view)</th><th>CPython 4.11 vs Pyodide 4.11</th></tr>{steps}</table></div>
<h3>The golden document on both, the worse governs</h3>
<div class="tw"><table><tr><th>Board</th><th>OpenCV 4.11 (CPython)</th><th>OpenCV 5.0 (CPython)</th><th>4.11 CPython vs the browser</th><th>Worse</th></tr>{"".join(tw)}</table></div>
<p>{esc(ev["opencv_note"])}</p>

<h2>How sure a range is</h2>
<p>{esc(cal["note"])}</p>
<div class="tw"><table><tr><th></th><th>Board #19–21 on the D435 (CPython, OpenCV 5.0)</th></tr>
<tr><td>Dense oracle: {cal["oracle_cases"]} fresh cases × {cal["oracle_distances"]} distances ({cal["oracle_renders"]} renders)</td><td><b>{m(cal["truth_mm"])}</b></td></tr>
<tr><td>The engine over 12 seeds (48 cases a distance)</td><td>mean {m(cal["mean_mm"])}, sd {cal["sd_pct"]} %, bias {cal["bias_pct"]:+} %</td></tr>
<tr><td>Its 90 % interval covers the oracle</td><td>{cal["covered"]} of 12 seeds</td></tr>
<tr><td>The default seed (20261021) · the proposal's numpy draw</td><td>{m(cal["default_mm"])} · {m(cal["proposal_mm"])}</td></tr></table></div>

<h2>The camera library</h2>
<p>Each entry is the colour stream an ArUco pipeline reads, re-read from the maker's document on 2026-10-21. Corrections to the first lookup: {esc(ev["library_fixes"])}</p>
<div class="tw"><table><tr><th>Camera</th><th>Stream</th><th>Pixels</th><th>HFOV</th><th>Focus from</th><th>Note</th><th>Source</th></tr>{lib}</table></div>

<h2>For the guides lane and scripts</h2>
<pre>{esc(ev["api"])}</pre>

<h2>Gates</h2>
<div class="tw"><table><tr><th>Gate</th><th>Result</th><th>Note</th></tr>{gates}</table></div>

<h2>What is done, left, and yours</h2>
<h3>Done and proved</h3><ul>{lis(ev["done"])}</ul>
<h3>Left</h3><ul>{lis(ev["left"])}</ul>
<h3>Needs you</h3><ul>{lis(ev["needs"])}</ul>
<h3>Deliberately not done</h3><ul>{lis(ev["not_done"])}</ul>
<h3>Decisions to record at merge</h3><ul>{lis(ev["decisions"])}</ul>

<h2>Commits and files</h2><ul>{commits}</ul><details><summary>Files touched ({len(ev["files"])})</summary><ul>{files}</ul></details>
<p class="muted">Every number here was measured on this machine on 2026-10-21 by the code on the lane; the browser numbers are headless Chrome
driving the static build. Built by <code>docs/build_verify_range_report.py</code>.</p>
</main></body></html>'''


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", type=Path, default=MAIN / "reports/media/verify-range-2026-10-21-src")
    a = ap.parse_args()
    page = build(a.src)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
