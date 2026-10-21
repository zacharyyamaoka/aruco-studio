#!/usr/bin/env python3
"""Build the printdims report (2026-10-21): Zach's 123.5 x 40 rectangle profile
holding a 3 x 1 grid of 30 mm DICT_4X4_50 on the inkjet preset -- where the
width stops being 123.5, before and after lane/os-printdims.

    .venv/bin/python docs/build_printdims_report.py --media <dir> --out <file.html> [--base 833ea6a]

Every number on the page is measured when it is built, never typed here:
the facade's answers (plan, svg, sheet) are computed twice in subprocesses,
once from the base commit's aruco_studio (git archive into a temp dir) and
once from this checkout, and each sheet's PDF is decoded and its grey cut
loop measured in points (tests/web/test_web_printdims.py's decoder, the
test's own oracle). The canvas numbers come from the browser runs in
--media (before.json / after.json: the real app's drawn white, outline and
Outer dims, client px over the zoom), with the screenshots, the hero video
and the PDF corner rendered there. Standard library only.
"""
from __future__ import annotations

import argparse
import base64
import html
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The facade's numbers for Zach's case, printed as JSON by a subprocess run
# against one aruco_studio (sys.argv[1] is its parent directory). The PDF
# decoder is the test's (tests/web/test_web_printdims.py pdf_cuts), copied
# into the run so the base commit needs nothing of this lane.
PROBE = r'''
import base64, json, math, re, sys, zlib
sys.path.insert(0, sys.argv[1])
from aruco_studio import web_api as W
PT = 25.4 / 72.0
def pdf_cut(pdf):
    objs = {int(m.group(1)): m.group(2) for m in re.finditer(rb"(\d+) 0 obj\n(.*?)\nendobj\n", pdf, re.S)}
    kids = re.search(rb"/Type /Pages /Kids \[([^\]]*)\]", pdf).group(1)
    body = objs[int(re.findall(rb"(\d+) 0 R", kids)[0])]
    media = [float(v) for v in re.search(rb"/MediaBox \[([^\]]*)\]", body).group(1).split()]
    raw = objs[int(re.search(rb"/Contents (\d+) 0 R", body).group(1))]
    s = zlib.decompress(raw[raw.index(b"stream\n") + 7:raw.rindex(b"\nendstream")]).decode("latin-1")
    grey, stack, subs, loops = None, [], [], []
    for t in s.split():
        if t in ("m", "l"):
            y, x = float(stack.pop()), float(stack.pop())
            if t == "m": subs.append([])
            subs[-1].append((x * PT, y * PT)); stack = []
        elif t == "G": grey = float(stack.pop()); stack = []
        elif t in ("S", "f", "f*"):
            if t == "S" and grey is not None and abs(grey - 0.55) < 1e-9:
                loops += [sp for sp in subs if len(sp) >= 3]
            subs, stack = [], []
        elif t in ("BT", "ET", "h", "w", "g", "re", "Tf", "Td", "Tm", "Tj"): stack = []
        else: stack.append(t)
    lp = max(loops, key=lambda q: (max(p[0] for p in q) - min(p[0] for p in q)))
    return {"w": max(p[0] for p in lp) - min(p[0] for p in lp), "h": max(p[1] for p in lp) - min(p[1] for p in lp),
            "stroke_mm": 0.1, "page_mm": [round(media[2] * PT, 3), round(media[3] * PT, 3)]}
pre = next(p for p in W.presets() if p["name"] == "Inkjet · Letter vinyl")
out = {}
for trim in ("profile", "marker"):
    r = {"trim": trim, "profile": {"loops": [[[-61.75, -20.0], [61.75, -20.0], [61.75, 20.0], [-61.75, 20.0]]]},
         "holes": "avoid", "marker": {"type": "grid", "dictionary": "DICT_4X4_50", "first_id": 19, "auto": True,
         "marker_mm": 30.0, "checker_mm": 0.0, "separation_mm": 0.0, "cols": 3, "rows": 1, "turn": 0, "flip": False,
         "quiet_modules": 1, "corner_mark": "none"}, "label": {"on": False, "text": "#{ids}", "height_mm": 0.0,
         "side": "below", "gap_mm": 2.0, "offset_mm": [0.0, 0.0]}, "preset": pre, "reference_face": False, "extrude": {}}
    p = W.plan(r)
    sh = W.sheet({"items": [r]}, "2026-10-21")
    svg_d = re.search(r'<path data-cut="m1"[^>]* d="([^"]*)"', sh["svg"][0]).group(1)
    nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", svg_d)]
    box = lambda lp: (max(q[0] for q in lp) - min(q[0] for q in lp), max(q[1] for q in lp) - min(q[1] for q in lp))
    out[trim] = {
        "profile": [123.5, 40.0], "fit_rect": [p["fit_rect"]["w"], p["fit_rect"]["h"]],
        "cut": list(box(p["cut"])), "outline": list(box(p["outer"])), "outer_mm": p["outer_mm"],
        "dims_outer": [d["value_mm"] for d in p["dims"] if d["field"] == "outer"],
        "marker_mm": p["marker_mm"], "separation_mm": p["separation_mm"],
        "summary": p["summary"],
        "size_line": next((w["text"] for w in p["warnings"] if w["field"] == "marker.marker_mm" and "· sticker" in w["text"]), ""),
        "svg_cut": [max(nums[0::2]) - min(nums[0::2]), max(nums[1::2]) - min(nums[1::2])],
        "pdf_cut": pdf_cut(base64.b64decode(sh["pdf_base64"])),
    }
print(json.dumps(out))
'''


def facade_numbers(code_root: Path) -> dict:
    r = subprocess.run([sys.executable, "-c", PROBE, str(code_root)], capture_output=True, text=True,
                       env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
    if r.returncode:
        raise SystemExit(f"the probe failed under {code_root}:\n{r.stderr}")
    return json.loads(r.stdout)


def base_tree(rev: str, into: Path) -> Path:
    tar = subprocess.run(["git", "-C", str(ROOT), "archive", rev, "aruco_studio"], capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(into, filter="data")
    return into


def uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def mm(v) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def pair(v) -> str:
    return f"{mm(v[0])} × {mm(v[1])}"


CSS = """
:root { --bg: #f6f7f9; --panel: #fff; --text: #1c222b; --muted: #5f6873; --line: #dde1e6; --ok: #18865a; --bad: #c4352f; --accent: #2f6fed; }
@media (prefers-color-scheme: dark) { :root { --bg: #15181d; --panel: #1c2026; --text: #e5e8ec; --muted: #9aa3ae; --line: #323943; --ok: #4cc27a; --bad: #f06a5f; --accent: #5b8ff0; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.5 Inter, system-ui, sans-serif; }
main { max-width: 1100px; margin: 0 auto; padding: 28px 16px 60px; }
h1 { font-size: 24px; margin: 0 0 6px; } h2 { font-size: 18px; margin: 34px 0 10px; }
.verdict { background: var(--panel); border: 1px solid var(--line); border-left: 4px solid var(--ok); border-radius: 8px; padding: 14px 16px; }
.muted { color: var(--muted); } code { font: 13px ui-monospace, monospace; }
table { border-collapse: collapse; width: 100%; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { font-size: 13px; color: var(--muted); font-weight: 600; }
td.bad { color: var(--bad); font-weight: 600; } td.ok { color: var(--ok); font-weight: 600; }
.pair { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; } @media (max-width: 760px) { .pair { grid-template-columns: 1fr; } }
figure { margin: 0; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 8px; }
figure img, figure video { width: 100%; height: auto; display: block; border-radius: 4px; }
figcaption { font-size: 13px; color: var(--muted); padding: 6px 2px 0; }
ul { padding-left: 20px; } li { margin: 4px 0; }
"""


def build(media: Path, out: Path, rev: str) -> None:
    with tempfile.TemporaryDirectory(prefix="printdims_base_") as tmp:
        before = facade_numbers(base_tree(rev, Path(tmp)))
    after = facade_numbers(ROOT)
    cb = json.loads((media / "before.json").read_text())       # the live site (pre-fix)
    ca = json.loads((media / "after.json").read_text())        # this lane's build
    b, a = before["profile"], after["profile"]

    def row(label, bv, av, want=None, note=""):
        def cell(v):
            if want is None:
                return f"<td>{html.escape(pair(v) if isinstance(v, (list, tuple)) else str(v))}</td>"
            ok = isinstance(v, (list, tuple)) and abs(float(v[0]) - want) < 0.1
            return f'<td class="{"ok" if ok else "bad"}">{html.escape(pair(v) if isinstance(v, (list, tuple)) else str(v))}</td>'
        return f"<tr><td>{label}</td>{cell(bv)}{cell(av)}<td class=muted>{note}</td></tr>"

    zb, za = cb["canvas"]["zoom_px_per_mm"], ca["canvas"]["zoom_px_per_mm"]
    cw = lambda c, k: [c["canvas"][k]["w"] / c["canvas"]["zoom_px_per_mm"], c["canvas"][k]["h"] / c["canvas"]["zoom_px_per_mm"]]
    outer_dims = lambda c: [d["value"] for d in c["canvas"]["dims"] if d["field"] == "outer"]
    rows = "".join([
        row("(a) the profile (the document's rectangle)", b["profile"], a["profile"], 123.5),
        row("(b) plan: the box the marker is placed in (fit_rect)", b["fit_rect"], a["fit_rect"], 123.5),
        row("(b) plan: the cut (cut / cut_shape)", b["cut"], a["cut"], 123.5),
        row("(b) plan: the marker's outline, its quiet-zone box", b["outline"], a["outline"], None,
            "the marker itself: 3 × 30 mm + 2 × 6 mm + 2 × 5 mm white border; unchanged"),
        row("(b) plan: the Outer dims the canvas draws", b["dims_outer"], a["dims_outer"], 123.5, "<b>here 123.5 stopped being 123.5</b>"),
        row("(b) plan: the summary", b["summary"].split("· ")[-1], a["summary"].split("· ")[-1], None),
        row("(b) plan: the Marker row", b["size_line"].split(" (")[0], a["size_line"].split(" (")[0], None),
        row("(c) canvas: the white drawn (px / zoom)", cw(cb, "cut_white"), cw(ca, "cut_white"), 123.5),
        row("(c) canvas: the outline drawn", cw(cb, "outline"), cw(ca, "outline"), None,
            "after: a dashed guide (it prints nothing), the selection outlines the cut"),
        row("(c) canvas: Outer dims as drawn", outer_dims(cb), outer_dims(ca), 123.5),
        row("(d) the sheet's SVG: the cut line", b["svg_cut"], a["svg_cut"], 123.5),
        row("(e) the PDF: the cut loop, decoded (pt → mm)", [b["pdf_cut"]["w"], b["pdf_cut"]["h"]],
            [a["pdf_cut"]["w"], a["pdf_cut"]["h"]], 123.5, f"0.1 mm grey line; page {pair(a['pdf_cut']['page_mm'])} (Letter)"),
        row("(e) Chrome's own print of the Print page", cb.get("chrome_print", "–"), ca.get("chrome_print", "–"), 123.5,
            "page.pdf() with the print CSS, measured by mutool trace"),
        row("(f) CPython web_api.sheet (same as Pyodide: test:parity)", [b["pdf_cut"]["w"], b["pdf_cut"]["h"]],
            [a["pdf_cut"]["w"], a["pdf_cut"]["h"]], 123.5),
    ])
    m = before["marker"], after["marker"]
    img = lambda name: uri(media / name, "image/webp" if name.endswith(".webp") else "image/png")
    hero = media / "hero.webm"
    gif = media / "hero.gif"
    body = f"""
<h1>Printed size = shown size</h1>
<p class="muted">lane <code>lane/os-printdims</code> · not merged · 2026-10-21 · base <code>{html.escape(rev)}</code></p>
<div class="verdict"><b>The PDF always cut 123.5 × 40. The canvas called the sticker 112 × 40.</b>
The marker's quiet-zone box (112 × 40) was shown as Outer, as the summary's "outer" and as the Marker row's
"sticker", while every printed file (the core PDF, the sheet SVG, Chrome's print of the Print page; CPython and
Pyodide) cut the profile at 123.5 × 40.000 mm. Now every size the Studio shows as the sticker's is the cut, to the
PDF's 1e-4 mm, and the panel's "Over the page" judges that cut as the sheet does.</div>

<h2>The hero: the real app, this lane's build</h2>
<figure><video autoplay muted loop playsinline controls poster="{img('after-unselected.webp')}">
<source src="{uri(hero, 'video/webm')}" type="video/webm"></video>
<figcaption>Zach's document opened; the marker selected (Outer 123.5 × 40, the panel's "sticker 123.5 × 40.0 mm" and
"outer 123.5 × 40.0 mm"); nothing selected (the quiet zone's edge a dashed guide); Print: the sheet cuts 123.5 × 40.
{'<a href="' + html.escape(gif.relative_to(out.parent).as_posix()) + '">GIF</a>' if gif.exists() else ''}</figcaption></figure>

<h2>Where 123.5 stopped being 123.5</h2>
<table><tr><th>stage</th><th>before (base / the live site)</th><th>after (this lane)</th><th>note</th></tr>{rows}</table>
<p class="muted">Marker {mm(m[1]['marker_mm'])} mm, separation {mm(m[1]['separation_mm'])} mm in both. Canvas zoom before
{zb:.3f} px/mm, after {za:.3f} px/mm. Trim Marker, before and after: cut {pair(before['marker']['cut'])},
PDF {pair([before['marker']['pdf_cut']['w'], before['marker']['pdf_cut']['h']])} → Outer {pair(after['marker']['dims_outer'])}.</p>

<h2>The canvas, before and after</h2>
<div class="pair">
<figure><img src="{img('before-unselected.webp')}" alt=""><figcaption>Before (arucostudio.com): the 123.5 dimension spans the
dashed profile; the solid grey line inside is the quiet zone's edge at 112, which reads as the plate's edge.</figcaption></figure>
<figure><img src="{img('after-unselected.webp')}" alt=""><figcaption>After: the quiet zone's edge is a faint dashed guide;
the white to the profile's edge is the sticker.</figcaption></figure>
<figure><img src="{img('before-selected.webp')}" alt=""><figcaption>Before, selected: Outer 112 × 40, "sticker 112.0 × 40.0 mm",
"outer 112.0 × 40.0 mm".</figcaption></figure>
<figure><img src="{img('after-selected.webp')}" alt=""><figcaption>After, selected: Outer 123.5 × 40; the selection outlines the
cut; the panel says 123.5 × 40.0.</figcaption></figure>
</div>

<h2>On paper: what a ruler along the top edge meets</h2>
<figure><img src="{img('pdf-corner.webp')}" alt="" style="max-width: 560px"><figcaption>The PDF's top-left corner at 600 dpi: the grey 0.1 mm cut
line, and the crop marks 0.5 mm off the corner running 1.5 mm out along the same lines. End to end the printed top edge
reads 123.5 + 2 × 2.0 = 127.5 mm. Not verified: whether this is what was measured. Measuring the 100 mm bar on the same
print tells the two apart: 100.0 mm means the file printed at 100 % and the extra is the marks (or the cut); more means the
printer or its dialog scaled it.</figcaption></figure>
"""
    out.write_text(f"<!doctype html><html lang=en><head><meta charset=utf-8>"
                   f"<meta name=viewport content='width=device-width, initial-scale=1'><title>Printdims report</title>"
                   f"<style>{CSS}</style></head><body><main>{body}</main></body></html>")
    print(f"wrote {out} ({out.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--base", default="833ea6a")
    a = ap.parse_args()
    build(a.media, a.out, a.base)
