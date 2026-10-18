#!/usr/bin/env python3
"""Build the review report for the online Studio (arucostudio.com, 2026-10-18).

    python3 docs/build_online_studio_report.py

Writes reports/media/online-studio-2026-10-18.html: one self-contained page,
every image and the hero video inlined as data URIs (no server, no network).
reports/media/ is gitignored; this script is the reviewed source.

Standard library only; it shells out to ffmpeg / ffprobe for the media and
(only for --label-renders) to git and Google Chrome.

Its raw inputs live in reports/media/online-studio-2026-10-18-src/ (gitignored):

  shots/*.png, shots/facts.json   the stills, from the LIVE site:
      (cd web && E2E_BASE_URL=https://arucostudio.com REPORT_SHOTS_DIR=<src>/shots \
          npx playwright test --project=e2e e2e/report.spec.ts)
  hero.webm                       the primary flow, from the LIVE site:
      (cd web && E2E_BASE_URL=https://arucostudio.com npx playwright test --project=hero)
      then copy web/test-results/hero/hero.webm (Playwright clears test-results/ each run)
  label-before.png, label-after.png
      the same plate request through web_api.sheet before (404467f) and after
      (HEAD) the WYSIWYG label fix: --label-renders makes them
  ref/*.png                       Zach's own reference screenshots, copied from
      ~/zach_brain/Sources/Images/ (pasted into PROJECT - Aruco Studio)
  suites.json                     the core / plan / scene counts, from
      `.venv/bin/python -m pytest tests/core -q -rf` (and plan, scene) on this box
  live-core.json                  the live core vs git: every file of
      https://arucostudio.com/py/aruco_studio.zip against `git show <stamp>:<path>`

Every number on the page is read from facts.json, a test log, git, or the
files named in its Source Index; the copy says which.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-10-18"
SRC = ROOT / "reports" / "media" / f"online-studio-{DATE}-src"
WORK = ROOT / "reports" / "media" / f"online-studio-{DATE}-build"
OUT = ROOT / "reports" / "media" / f"online-studio-{DATE}.html"
FFMPEG, FFPROBE = "/usr/bin/ffmpeg", "/usr/bin/ffprobe"
CHROME = "/usr/bin/google-chrome"

# The hero recording (33.7 s at 1280 x 800, 25 fps): keep the first 1.2 s
# (the chip says "Core loading..."), cut to 5.0 s (it turns "Python ready" at
# 5.8 s), keep to 32.2 s (2 s of the Print dialog), then play 1.45x.
# WHY: <= 20 s and watchable; the cut is said in the caption.
HERO_KEEP = [(0.0, 1.2), (5.0, 32.2)]
HERO_SPEED = 1.45
HERO_POSTER_T = 8.1      # seconds into the cut: the marker in the plate, panel open
HERO_CRF = 24


# ------------------------------------------------------------------ media

def run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"failed: {' '.join(cmd)}\n{r.stderr[-2000:]}")
    return r.stdout


def dims(path: Path) -> tuple[int, int]:
    out = run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=width,height", "-of", "csv=p=0", str(path)])
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


def webp(src: Path, dst: Path, vf: str, quality: int) -> Path:
    """One still as WebP through an ffmpeg filter chain (crop / scale)."""
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        run([FFMPEG, "-y", "-v", "error", "-i", str(src), "-vf", vf, "-c:v", "libwebp",
             "-quality", str(quality), "-compression_level", "6", "-frames:v", "1", str(dst)])
    return dst


def hero(src: Path, work: Path) -> tuple[Path, Path, float]:
    key = hashlib.sha1(f"{HERO_KEEP}|{HERO_SPEED}|{HERO_CRF}|{HERO_POSTER_T}".encode()).hexdigest()[:8]
    mp4, poster = work / f"hero-{key}.mp4", work / f"hero-poster-{key}.webp"
    if not mp4.exists() or mp4.stat().st_mtime < src.stat().st_mtime:
        parts = "".join(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[p{i}];" for i, (a, b) in enumerate(HERO_KEEP))
        joined = "".join(f"[p{i}]" for i in range(len(HERO_KEEP)))
        fc = (parts + f"{joined}concat=n={len(HERO_KEEP)}:v=1:a=0,setpts=PTS/{HERO_SPEED},fps=25,"
              "scale=960:-2:flags=lanczos,format=yuv420p[v]")
        run([FFMPEG, "-y", "-v", "error", "-i", str(src), "-filter_complex", fc, "-map", "[v]",
             "-c:v", "libx264", "-preset", "veryslow", "-crf", str(HERO_CRF), "-tune", "animation",
             "-movflags", "+faststart", "-an", str(mp4)])
    if not poster.exists() or poster.stat().st_mtime < mp4.stat().st_mtime:
        run([FFMPEG, "-y", "-v", "error", "-ss", str(HERO_POSTER_T), "-i", str(mp4), "-frames:v", "1",
             "-c:v", "libwebp", "-quality", "70", str(poster)])
    dur = float(run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)]))
    return mp4, poster, dur


# (name, source, ffmpeg filter, quality): every still and close-up on the page
STILLS = [
    # full screens at 1280 x 800 (shot at 2x): 1200 px wide
    ("plate", "shots/01-plate-inscribed.png", "scale=1200:-1:flags=lanczos", 80),
    ("typed", "shots/02-typed-overflow.png", "scale=1200:-1:flags=lanczos", 80),
    ("presets", "shots/04-presets.png", "crop=2180:1340:190:136,scale=1100:-1:flags=lanczos", 82),
    ("print", "shots/05-print.png", "crop=1760:1270:410:160,scale=1000:-1:flags=lanczos", 82),
    ("dark", "shots/06-dark.png", "scale=1200:-1:flags=lanczos", 80),
    ("drawn", "shots/08-drawn.png", "scale=1200:-1:flags=lanczos", 80),
    # the phone (390 x 844 at 2x)
    ("mobile", "shots/07-mobile.png", "scale=520:-1:flags=lanczos", 82),
    ("mobile_collapsed", "shots/07b-mobile-collapsed.png", "scale=520:-1:flags=lanczos", 82),
    # close-ups at 2x, kept sharp
    ("panel", "shots/01b-panel.png", "scale=480:-1:flags=lanczos", 90),
    ("panel_top", "shots/01b-panel.png", "crop=600:340:0:0,scale=480:-1:flags=lanczos", 90),
    ("panel_turn", "shots/01b-panel.png", "crop=600:180:0:756,scale=480:-1:flags=lanczos", 90),
    # WHY these crops: the sketch close-up is x 28..92 mm at 13.94 px/mm and the
    # print close-up 85 mm at 7.55 px/mm (its marker measured at px 123..404), so
    # both are cut to the same 64 mm-wide window: shown side by side at one scale.
    ("sketch_marker", "shots/01c-sketch-marker.png", "crop=892:779:0:253,scale=440:-1:flags=lanczos", 86),
    ("sketch_label", "shots/01c-sketch-marker.png", "crop=892:1099:0:253,scale=440:-1:flags=lanczos", 90),
    ("timeline", "shots/01d-timeline.png", "crop=1200:68:0:0", 90),
    ("holes_avoid", "shots/01e-holes-avoid.png", "scale=760:-1:flags=lanczos", 84),
    ("holes_ignore", "shots/01f-holes-ignore.png", "scale=760:-1:flags=lanczos", 84),
    ("row_issue", "shots/02b-marker-row-issue.png", "scale=596:-1", 90),
    ("grid_fields", "shots/03c-grid-fields.png", "scale=560:-1:flags=lanczos", 90),
    ("suggest", "shots/03b-suggest-list.png", "scale=560:-1:flags=lanczos", 90),
    ("print_label", "shots/05b-print-label.png", "crop=483:494:22:52,scale=440:-1:flags=lanczos", 90),
    ("scale_bar", "shots/05c-scale-bar.png", "scale=378:-1", 90),
    ("label_before", "label-before.png", "crop=480:560:0:0,scale=360:-1:flags=lanczos", 90),
    ("label_after", "label-after.png", "crop=480:560:0:0,scale=360:-1:flags=lanczos", 90),
    # Zach's references (his pasted screenshots)
    ("ref_panel", "ref/20261018123334.png", "scale=360:-1:flags=lanczos", 82),
    ("ref_presets", "ref/20261018123353.png", "scale=640:-1:flags=lanczos", 80),
    ("ref_suggest", "ref/20261018123031.png", "scale=399:-1", 88),
    ("ref_calib", "ref/20261018113419.png", "crop=880:166:0:560,scale=560:-1:flags=lanczos", 80),
    ("ref_timeline", "ref/20261018121133.png", "scale=180:-1:flags=neighbor", 90),
]


def encode(src: Path, work: Path) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    media = {}
    for name, rel, vf, q in STILLS:
        # WHY the key: a changed crop or quality must re-encode, not reuse the cache
        key = hashlib.sha1(f"{rel}|{vf}|{q}".encode()).hexdigest()[:8]
        p = webp(src / rel, work / f"{name}-{key}.webp", vf, q)
        media[name] = (p, "image/webp", *dims(p))
    mp4, poster, dur = hero(src / "hero.webm", work)
    media["hero"] = (mp4, "video/mp4", *dims(mp4))
    media["hero_poster"] = (poster, "image/webp", *dims(poster))
    media["_hero_s"] = dur
    return media


# ------------------------------------------------------------------ label renders

LABEL_REQ = """
import json, re, sys
sys.path.insert(0, sys.argv[1])
from aruco_studio import web_api as W
pre = next(x for x in W.presets() if x["name"] == "Inkjet · Letter vinyl")
r = {"rect": {"cx": 59.986795, "cy": 39.921875, "w": 49.964551, "h": 79.84375, "angle_deg": 0.0},
     "marker": {"type": "single", "dictionary": "DICT_4X4_50", "first_id": 0, "auto": True,
                "marker_mm": 0.0, "checker_mm": 0.0, "separation_mm": 0.0, "cols": 1, "rows": 1,
                "turn": 0, "flip": False, "quiet_modules": 1.0, "corner_mark": "none"},
     "label": {"on": True, "text": "", "height_mm": 0.0, "side": "below", "gap_mm": 2.0, "offset_mm": [0.0, 0.0]},
     "preset": pre, "reference_face": True}
plan = W.plan(r)
page = W.sheet({"items": [r], "cut_lines": True}, "2026-10-18")["svg"][0]
sizes = [float(f) for f, t in re.findall(r'<text[^>]*font-size="([\\d.]+)"[^>]*>([^<]*)</text>', page)
         if t == plan["label"]["text"]]
page = re.sub(r"<svg\\b[^>]*>", '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="640" '
              'viewBox="0 0 85 85" style="background:#fff">', page, count=1)
open(sys.argv[2], "w").write(page)
print(json.dumps({"sketch_cap_mm": plan["label"]["height_mm"], "printed_font_mm": sizes}))
"""


def label_renders(src: Path, before_rev: str = "404467f") -> dict:
    """The plate's sheet page before / after the WYSIWYG label fix (56a0d98),
    the top-left 85 x 85 mm rasterised by headless Chrome."""
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        old = tmp / "old"
        old.mkdir()
        tar = subprocess.run(["git", "-C", str(ROOT), "archive", before_rev, "aruco_studio"],
                             capture_output=True, check=True).stdout
        tarfile.open(fileobj=io.BytesIO(tar)).extractall(old, filter="data")
        for tag, root in (("before", old), ("after", ROOT)):
            svg = tmp / f"label-{tag}.svg"
            got = json.loads(run([sys.executable, "-c", LABEL_REQ, str(root), str(svg)]))
            run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={tmp / 'chrome'}",
                 f"--screenshot={src / f'label-{tag}.png'}", "--window-size=640,640", svg.as_uri()])
            out[tag] = {"rev": before_rev if tag == "before" else "HEAD", **got}
    (src / "label-renders.json").write_text(json.dumps(out, indent=2))
    return out


# ------------------------------------------------------------------ page parts

E = html.escape


def uri(media: dict, name: str) -> str:
    p, mime, *_ = media[name]
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")


def img(media: dict, name: str, alt: str, cls: str = "") -> str:
    _, _, w, h = media[name]
    c = f' class="{cls}"' if cls else ""
    return f'<img{c} src="{uri(media, name)}" width="{w}" height="{h}" alt="{E(alt)}" decoding="async" data-zoom>'


def fig(media: dict, name: str, alt: str, cap: str, cls: str = "") -> str:
    return f'<figure class="{cls}">{img(media, name, alt)}<figcaption>{cap}</figcaption></figure>'


def quote(text: str, where: str, ref: str) -> str:
    return f'<blockquote><p>{E(text)}</p><cite>you, <i>{E(where)}</i> {ref}</cite></blockquote>'


def git(*args: str) -> str:
    return run(["git", "-C", str(ROOT), *args]).strip()


# ------------------------------------------------------------------ the diagram

def diagram(narrow: bool) -> str:
    """The seam: UI -> frozen contract -> Pyodide worker -> the core, and
    inscribe() one step above plan(). Two layouts (wide / phone), same boxes;
    text wraps to the box (a character budget per line, measured by eye in
    the rendered page at 1280 and 390 px)."""
    layers = [
        ("ui", "The screen · web/src", "sketch viewport · ArUco Extrude panel · presets modal · Print"),
        ("contract", "web/src/core/contract.ts · frozen", "info · presets · inscribe · plan · suggest · svg · sheet"),
        ("worker", "Web Worker · Pyodide 314.0.7, self-hosted", "aruco_studio/web_api.py · call(name, json)"),
        ("core", "The core · aruco_studio core / plan / scene", "stdlib Python: the same package the Fusion add-in uses"),
    ]
    links = ["CoreApi: 7 calls, JSON in / out", "postMessage", "import"]
    pipe = [("Profile", "a face: its outline and its holes"), ("Rect", "cx, cy, w, h, angle (mm)"),
            ("MarkerPlan", "black, outline, Joint Origin, label, issues")]
    pipe_links = ["inscribe(profile, Avoid | Ignore)", "plan(rect, marker, label, preset)"]
    out = []
    if narrow:
        W, x0, bw, gap, tch, sch = 380, 16, 348, 44, 30, 40
        y = 40
        out.append(f'<text class="d-h" x="{x0}" y="22">The seam</text>')
        for i, (k, t_, s) in enumerate(layers):
            g, h = box(x0, y, bw, t_, s, k, tch, sch)
            out.append(g)
            if i < len(links):
                out.append(arrow(x0 + 26, y + h, y + h + gap, links[i]))
            y += h + gap
        y += 18 - gap + 26
        out.append(f'<text class="d-h" x="{x0}" y="{y}">Where inscribe sits</text>')
        y += 16
        for i, (t_, s) in enumerate(pipe):
            g, h = box(x0, y, bw, t_, s, "pipe", tch, sch)
            out.append(g)
            if i < len(pipe_links):
                out.append(arrow(x0 + 26, y + h, y + h + gap, pipe_links[i]))
            y += h + gap
        out.append(quote_svg(x0, y - gap + 26, ["“the input to this algorithim is always", "just a rectangle”"]))
        H = y - gap + 70
    else:
        W, x0, bw, gap, tch, sch = 960, 20, 520, 46, 56, 70
        y = 44
        out.append(f'<text class="d-h" x="{x0}" y="24">The seam</text>')
        for i, (k, t_, s) in enumerate(layers):
            g, h = box(x0, y, bw, t_, s, k, tch, sch)
            out.append(g)
            if i < len(links):
                out.append(arrow(x0 + bw / 2, y + h, y + h + gap, links[i]))
            y += h + gap
        H = y - gap + 20
        px, py, pw = 600, 44, 340
        out.append(f'<text class="d-h" x="{px}" y="24">Where inscribe sits</text>')
        for i, (t_, s) in enumerate(pipe):
            g, h = box(px, py, pw, t_, s, "pipe", 34, 44)
            out.append(g)
            if i < len(pipe_links):
                out.append(arrow(px + 26, py + h, py + h + 50, pipe_links[i]))
            py += h + 50
        out.append(quote_svg(px, py - 50 + 30, ["“the input to this algorithim is always just", "a rectangle”: inscribe is one step above"]))
        H = max(H, py - 50 + 64)
    label = ("Diagram: the screen calls the frozen contract, which posts JSON to a Pyodide worker running "
             "web_api.py on the core. A profile goes through inscribe to a rectangle; plan takes only the rectangle.")
    return (f'<svg class="diagram {"narrow" if narrow else "wide"}" viewBox="0 0 {W} {H:.0f}" role="img" '
            f'aria-label="{E(label)}">{"".join(out)}</svg>')


def wrap(text: str, n: int) -> list[str]:
    lines, cur = [], ""
    for w in text.split(" "):
        if cur and len(cur) + 1 + len(w) > n:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    return lines + ([cur] if cur else [])


def box(x, y, w, title, sub, kind, tch, sch) -> tuple[str, float]:
    tl, sl = wrap(title, tch), wrap(sub, sch)
    rows, yy = [], y + 26
    for line in tl:
        rows.append(f'<text class="d-t" x="{x + 14}" y="{yy}">{E(line)}</text>')
        yy += 21
    yy += 1
    for line in sl:
        rows.append(f'<text class="d-s" x="{x + 14}" y="{yy}">{E(line)}</text>')
        yy += 19
    h = yy - y - 3
    return (f'<g class="d-box d-{kind}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8"/>{"".join(rows)}</g>', h)


def arrow(x, y0, y1, label) -> str:
    return (f'<g class="d-link"><line x1="{x}" y1="{y0 + 3}" x2="{x}" y2="{y1 - 9}"/>'
            f'<path d="M{x - 5},{y1 - 11} L{x},{y1 - 3} L{x + 5},{y1 - 11} Z"/>'
            f'<text class="d-l" x="{x + 12}" y="{(y0 + y1) / 2 + 4}">{E(label)}</text></g>')


def quote_svg(x, y, lines) -> str:
    return "".join(f'<text class="d-q" x="{x}" y="{y + 20 * i}">{E(s)}</text>' for i, s in enumerate(lines))


# ------------------------------------------------------------------ the page

CSS = r"""
:root{--bg:#ffffff;--fg:#1f2328;--muted:#5f6670;--faint:#8a9099;--line:#e3e5e8;--panel:#f7f7f8;--chip:#eef0f2;
--accent:#2563eb;--accent-bg:#eef3fe;--ok:#1a7f37;--ok-bg:#eaf6ed;--warn:#9a6700;--warn-bg:#fdf6e3;--bad:#c62828;--bad-bg:#fdeeee;
--code:#f3f4f6;--shadow:0 1px 2px rgba(0,0,0,.05),0 4px 16px rgba(0,0,0,.05);color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#191a1c;--fg:#e6e7e9;--muted:#a3a8b0;--faint:#7c828b;
--line:#2e3034;--panel:#212226;--chip:#2a2c30;--accent:#7aa2ff;--accent-bg:#1f2a44;--ok:#6fd38b;--ok-bg:#1b2b20;--warn:#e3b341;
--warn-bg:#2d2616;--bad:#ff8a80;--bad-bg:#3a1f1f;--code:#25272b;--shadow:none;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#191a1c;--fg:#e6e7e9;--muted:#a3a8b0;--faint:#7c828b;--line:#2e3034;--panel:#212226;--chip:#2a2c30;
--accent:#7aa2ff;--accent-bg:#1f2a44;--ok:#6fd38b;--ok-bg:#1b2b20;--warn:#e3b341;--warn-bg:#2d2616;--bad:#ff8a80;--bad-bg:#3a1f1f;
--code:#25272b;--shadow:none;color-scheme:dark}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,"Noto Sans",
"Helvetica Neue",Arial,sans-serif;overflow-wrap:anywhere}
main{max-width:920px;margin:0 auto;padding:40px 24px 80px}
h1{font-size:30px;line-height:1.25;margin:0 0 6px;letter-spacing:-.01em}
h2{font-size:22px;line-height:1.3;margin:56px 0 14px;padding-top:18px;border-top:1px solid var(--line)}
h3{font-size:17px;margin:34px 0 10px}
p{margin:0 0 12px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
code{font:13.5px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--code);padding:1px 5px;border-radius:4px}
sup{font-size:11px;color:var(--faint);margin-left:1px}sup a{color:var(--faint)}
.meta{color:var(--muted);font-size:14px;margin-bottom:22px}
.verdict{border:1px solid var(--line);background:var(--panel);border-radius:10px;padding:16px 18px;margin:18px 0 26px}
.verdict b{font-size:18px;line-height:1.45;display:block;margin-bottom:6px}
.verdict .qual{color:var(--muted);font-size:15px}
.pill{display:inline-block;font-size:12.5px;font-weight:600;padding:1px 8px;border-radius:999px;background:var(--chip);color:var(--muted);margin-right:6px;white-space:nowrap}
.pill.ok{background:var(--ok-bg);color:var(--ok)}.pill.warn{background:var(--warn-bg);color:var(--warn)}.pill.bad{background:var(--bad-bg);color:var(--bad)}
figure{margin:0 0 14px}
figure img,video{display:block;width:100%;height:auto;border:1px solid var(--line);border-radius:8px;background:var(--panel)}
img[data-zoom]{cursor:zoom-in}
figcaption{font-size:13.5px;color:var(--muted);margin-top:6px;line-height:1.5}
.hero video{box-shadow:var(--shadow)}
.try{border:1px solid var(--accent);background:var(--accent-bg);border-radius:10px;padding:14px 18px;margin:16px 0 0}
.try ol{margin:6px 0 0;padding-left:22px}.try li{margin:2px 0}
.kbd{font:12.5px ui-monospace,monospace;border:1px solid var(--line);border-bottom-width:2px;border-radius:4px;padding:0 5px;background:var(--bg)}
.item{margin:0 0 30px;padding:0 0 26px;border-bottom:1px dashed var(--line)}
.item:last-child{border-bottom:0}
.item h3{margin-top:0}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}
.pair.r21{grid-template-columns:2fr 1fr}.pair.r12{grid-template-columns:1fr 2fr}.pair.r31{grid-template-columns:3fr 1fr}
.pair figure{margin:0}
.media{margin-bottom:12px}
.narrowimg{max-width:480px}
blockquote{margin:12px 0;padding:8px 14px;border-left:3px solid var(--line);color:var(--fg);background:var(--panel);border-radius:0 8px 8px 0}
blockquote p{margin:0 0 4px;font-style:italic}
blockquote cite{font-style:normal;font-size:12.5px;color:var(--faint)}
.built{margin:8px 0 0}.built li{margin:3px 0}
ul,ol{padding-left:22px}
.note{font-size:14px;color:var(--muted)}
.rough{border-left:3px solid var(--warn);background:var(--warn-bg);padding:8px 12px;border-radius:0 8px 8px 0;font-size:14.5px;margin:10px 0 0}
.tbl{width:100%;overflow-x:auto;margin:10px 0 16px}
table{border-collapse:collapse;width:100%;font-size:14.5px;line-height:1.45}
th,td{text-align:left;vertical-align:top;padding:8px 10px;border-bottom:1px solid var(--line)}
th{font-size:12.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600}
td.n{white-space:nowrap;font-variant-numeric:tabular-nums}
.score{font-variant-numeric:tabular-nums;white-space:nowrap}
.diagram{width:100%;height:auto;margin:6px 0 4px}
.diagram.narrow{display:none}
.d-box rect{fill:var(--panel);stroke:var(--line);stroke-width:1.5}
.d-contract rect{fill:var(--warn-bg);stroke:var(--warn)}
.d-core rect{fill:var(--ok-bg);stroke:var(--ok)}
.d-pipe rect{fill:var(--accent-bg);stroke:var(--accent)}
.d-t{font:600 16px ui-sans-serif,system-ui,sans-serif;fill:var(--fg)}
.d-s{font:13.5px ui-sans-serif,system-ui,sans-serif;fill:var(--muted)}
.d-h{font:600 13px ui-sans-serif,system-ui,sans-serif;fill:var(--faint);letter-spacing:.06em;text-transform:uppercase}
.d-l{font:13px ui-monospace,monospace;fill:var(--muted)}
.d-q{font:italic 13.5px ui-sans-serif,system-ui,sans-serif;fill:var(--muted)}
.d-link line{stroke:var(--faint);stroke-width:1.5}.d-link path{fill:var(--faint)}
.packet{counter-reset:q}
.q{border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:0 0 12px;background:var(--bg)}
.q h4{margin:0 0 6px;font-size:16px}
.q .rec,.q .def{font-size:14.5px;margin:4px 0 0}
.q .def{color:var(--muted)}
.q ol{margin:6px 0 0}
details{border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:10px 0;background:var(--panel)}
summary{cursor:pointer;font-size:14.5px;color:var(--muted)}
pre.diff{font:12.5px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;overflow-x:auto;margin:8px 0 0;padding:10px;background:var(--bg);border-radius:6px;border:1px solid var(--line)}
pre.diff .add{color:var(--ok)}pre.diff .del{color:var(--bad)}pre.diff .hunk{color:var(--accent)}
.sources{font-size:13.5px;color:var(--muted)}.sources li{margin:3px 0}
#zoom{position:fixed;inset:0;background:rgba(0,0,0,.82);display:none;align-items:center;justify-content:center;z-index:10;cursor:zoom-out;padding:16px}
#zoom img{max-width:100%;max-height:100%;border-radius:6px;background:#fff}
#zoom.on{display:flex}
@media (max-width:700px){
 main{padding:24px 16px 60px}
 h1{font-size:24px}
 h2{font-size:20px;margin-top:44px}
 .pair,.pair.r21,.pair.r12,.pair.r31{grid-template-columns:1fr}
 .diagram.wide{display:none}.diagram.narrow{display:block}
 table{font-size:13.5px}th,td{padding:7px 6px}
 table.stack thead{display:none}table.stack tr{display:block;border-bottom:1px solid var(--line);padding:10px 0}
 table.stack td{display:block;border:0;padding:3px 0}table.stack td:first-child{font-weight:600;font-size:15px}
 table.stack td:not(:first-child)::before{content:attr(data-label);display:block;font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--faint)}
 .hide-n{display:none}
}
"""

JS = r"""
(function(){var z=document.getElementById('zoom'),zi=z.querySelector('img');
document.addEventListener('click',function(e){var t=e.target;
if(t.matches&&t.matches('img[data-zoom]')){zi.src=t.src;zi.alt=t.alt;z.classList.add('on');}
else if(z.classList.contains('on')&&(t===z||t===zi)){z.classList.remove('on');zi.removeAttribute('src');}});
document.addEventListener('keydown',function(e){if(e.key==='Escape'){z.classList.remove('on');}});})();
"""


def diff_html(text: str) -> str:
    rows = []
    for line in text.splitlines():
        cls = "add" if line.startswith("+") and not line.startswith("+++") else \
              "del" if line.startswith("-") and not line.startswith("---") else \
              "hunk" if line.startswith("@@") else ""
        rows.append(f'<span class="{cls}">{E(line)}</span>' if cls else E(line))
    return '<pre class="diff">' + "\n".join(rows) + "</pre>"


def build(src: Path, out: Path, work: Path) -> Path:
    facts = json.loads((src / "shots" / "facts.json").read_text())
    labels = json.loads((src / "label-renders.json").read_text()) if (src / "label-renders.json").exists() else None
    media = encode(src, work)
    head = git("rev-parse", "--short", "HEAD")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    commits = git("log", "--format=%h\t%s", "5ea9599^..HEAD").splitlines()
    v1 = git("log", "--format=%h", "5ea9599^..2f5cf62").splitlines()
    diff_sheet = git("show", "56a0d98", "--format=", "-U2", "--", "aruco_studio/core/sheet.py")
    diff_settings = git("show", "37647aa", "--format=", "-U2", "--", "aruco_studio/core/settings.py")
    autosize = git("show", "--numstat", "--format=", "37647aa", "--", "aruco_studio/core/autosize.py").split()
    a_add, a_del = int(autosize[0]), int(autosize[1])

    LIVE_FILES = json.loads((src / "live-core.json").read_text())["same"]
    ins, ign, typed, pr = facts["inscribed_avoid"], facts["inscribed_ignore"], facts["typed"], facts["print"]
    ready = sorted(facts.get("core_ready_s_all") or facts["core_ready_s"])
    med = ready[len(ready) // 2]
    printed_cap = pr["printed_label_font_mm"][0] * 0.718     # core.sheet.CAP_EM
    sketch_cap = pr["sketch_label_cap_mm"]
    hero_s = media["_hero_s"]
    src_s = float(run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src / "hero.webm")]))
    mob = facts["mobile"]

    # Citations: a placeholder per source key now; numbered in order of first
    # appearance on the finished page (renumber() below), then the Source Index.
    def cite(*keys: str) -> str:
        for k in keys:
            assert k in SOURCES, k
        return "<sup>" + ",".join(f"\x00{k}\x00" for k in keys) + "</sup>"

    vault = "obsidian://open?vault=zach_brain&file=PROJECT%20-%20Aruco%20Studio"
    SOURCES = {
        "vault": f'<a href="{vault}">PROJECT - Aruco Studio</a> (your note; # Introduction, Mini CAD, Marker, Prior Art)',
        "spec": '<code>docs/design/online_studio_v1.md</code>: the v1 spec, flows and lanes',
        "contract": '<code>web/src/core/contract.ts</code>: the frozen UI ↔ core contract',
        "webapi": '<code>aruco_studio/web_api.py</code>: the facade the worker calls',
        "facts": '<code>web/e2e/report.spec.ts</code> on https://arucostudio.com, 2026-10-18: the stills and their measurements (<code>facts.json</code>)',
        "hero": '<code>web/e2e/hero.spec.ts</code> (project <code>hero</code>) on https://arucostudio.com, 2026-10-18',
        "c37647aa": 'commit <code>37647aa</code>: <code>settings.as_typed</code> and <code>numbers.separation</code>',
        "c56a0d98": 'commit <code>56a0d98</code>: the WYSIWYG label on the page; the inkjet default preset',
        "labels": 'the plate request through <code>web_api.sheet</code> at <code>404467f</code> (before) and HEAD (after), CPython; <code>--label-renders</code> in this script',
        "runs": 'test runs re-done for this report on <code>2f5cf62</code>, 2026-10-18 13:57–14:01: <code>pytest tests/web</code>, <code>npx vitest run</code>, <code>npm run test:parity</code>, and the live Playwright run (<code>E2E_BASE_URL=https://arucostudio.com</code>)',
        "build_session": 'the build session\'s own runs (commit messages <code>8827cfe</code>, <code>b204be5</code>); not re-run here',
        "live_zip": '<code>https://arucostudio.com/py/aruco_studio.zip</code>, fetched 2026-10-18: <code>_build.json</code> says <code>56a0d98</code>; every file compared with <code>git show 56a0d98:&lt;path&gt;</code>',
        "survey": '<a href="file:///home/bam/systemsketch/docs/tldraw-open-source-whiteboards-2026-08-31.html">your tldraw survey, 31 Aug 2026</a> (<code>systemsketch/docs/</code>)',
        "sspkg": '<code>/home/bam/systemsketch/package.json</code>: <code>"tldraw": "5.3.2"</code>',
        "pkg": '<code>web/package.json</code>: <code>pyodide 314.0.7</code>, <code>wrangler</code>; <code>web/wrangler.jsonc</code>',
        "worker": '<code>web/src/core/worker.ts</code>: <code>loadPyodide({ indexURL: "pyodide/" })</code>, served from the site',
        "seam": '<code>web/src/sketch/</code> and its importers (<code>grep</code>, 2026-10-18)',
        "tests_web": '<code>tests/web/test_web_api.py</code>',
        "suites": 'the core / plan / scene suites, re-run on this Linux box for this report (on <code>2f5cf62</code>), 2026-10-18 14:01–14:22 (<code>pytest tests/core|plan|scene -q -rf</code>)',
        "barrier": 'commit <code>ebc46a5</code> (14:21): the contract for the next wave (sheet mode / gap / cuts / fill, verify, readable, assign_ids)',
        "goldens": '<code>goldens/autosize.json</code>: made by <code>tools/make_goldens_from_ref.py</code> from <code>C:\\Users\\BAM\\…\\cad-exporter</code> (the Windows box)',
    }

    def media_pair(a: str, b: str, ratio: str = "") -> str:
        return f'<div class="pair {ratio}">{a}{b}</div>'

    # ---------------------------------------------------------------- 3. asked -> there
    items = []

    items.append(f"""
<div class="item"><h3>1 · A Fusion-style floating panel, a presets modal, neutral styling</h3>
<div class="media">{fig(media, "plate", "The plate example with the inscribed rectangle, the marker and the ArUco Extrude panel open",
    f"The ArUco Extrude panel floats top-right over the sketch (drag it by its title, collapse it with the chevron); the timeline runs along the bottom {cite('facts')}.")}</div>
<div class="media">{media_pair(
    fig(media, "panel", "The built ArUco Extrude panel, close up",
        f"Built: the panel, close up {cite('facts')}"),
    fig(media, "ref_panel", "Zach's reference: the earlier Edit ArUco Extrude panel in Fusion",
        "Your reference: the panel in Fusion (pasted in your note)"), "")}</div>
<div class="media">{media_pair(
    fig(media, "presets", "The presets modal: Recent, My presets, Built-in, cards, Filters and Info",
        f"Built: the presets modal is the kit's <code>LibraryShell</code>: Recent / My presets / Built-in, search, cards, Filters / Info, New · Duplicate · Edit · Delete · Import · Export {cite('facts')}"),
    fig(media, "ref_presets", "Zach's reference: the Aruco print presets modal in Fusion",
        "Your reference: the presets modal in Fusion"), "")}</div>
{quote("So we have the floating panel which is what you mainly use / and then we also have a floating modal for configuring presets etc", "UI (v1)", cite("vault"))}
{quote("Lets make these unstyled/neuralized style/shadcn in arucostudio so its easy to customize to feel natural in any other program..", "UI (v1)", cite("vault"))}
<ul class="built"><li>Every colour is a variable from the kit (<code>@bam/ui/tokens.css</code>), light and dark; no Fusion chrome is baked in, so a host restyles it by overriding the variables {cite('spec')}.</li>
<li>Built-ins: {", ".join(E(x) for x in facts["builtin_presets"])}. Your own presets live in the browser and export / import as JSON {cite('spec')}.</li></ul>
</div>""")

    items.append(f"""
<div class="item"><h3>2 · The marker rectangle is the entry point</h3>
<div class="media">{media_pair(
    fig(media, "holes_avoid", "Holes Avoid: the rectangle sits between the two holes",
        f"<b>Holes: Avoid.</b> Click inside the face, <span class='kbd'>A</span>: the core inscribes {ins['w']:.2f} × {ins['h']:.2f} mm between the holes {cite('facts')}. (The exact answer is 50 × 80 mm.)"),
    fig(media, "holes_ignore", "Holes Ignore: the rectangle covers the whole plate",
        f"<b>Holes: Ignore.</b> The same face: {ign['w']:.2f} × {ign['h']:.2f} mm, over the holes {cite('facts')}."), "")}</div>
<div class="media">{fig(media, "drawn", "A rectangle drawn with R on a blank sketch, the marker inside it, no profile, Flip shown",
    f"<b>Or draw one.</b> New sketch, <span class='kbd'>R</span>, drag a 60 × 40 mm rectangle, <span class='kbd'>A</span>: the panel says <i>Rectangle: 1 selected</i>, <i>Profile: None (optional)</i>, and Flip appears because there is no face {cite('facts')}.")}</div>
{quote("For me the key idea is that the marker is represented by a rectangle (4 perpendicular lines, opposite sides equal in length)", "Entry point (v2)", cite("vault"))}
{quote("Either you draw that rectangle and select its 4 edges, or if you select a non rectangular profile, the feature will automatically place a rectangle inside (either in a way where it ignores interior holes inside that profile, or avoids them)", "Entry point (v2)", cite("vault"))}
<ul class="built"><li>The inscribed rectangle is added to the sketch as an ordinary rectangle: move it, or pull one of its 8 handles, and the marker re-plans live (the drag is in the hero video) {cite('spec', 'hero')}.</li>
<li>The face is optional, the rectangle is not: <code>plan()</code> takes only a rectangle {cite('contract')}.</li></ul>
</div>""")

    items.append(f"""
<div class="item"><h3>3 · How it's made comes first</h3>
<div class="media narrowimg">{fig(media, "panel_top", "The top of the panel: Profile, Rectangle, Holes, then Preset and its notes, above the Marker and Label tabs",
    f"The Preset row sits above the Marker | Label tabs; its notes say what it does to the marker (cells in whole printer dots) {cite('facts')}.")}</div>
{quote("Actually the first thing you need to decide is how you are going to manufacture it, as that will impact what do you down stream.", "Manufacture", cite("vault"))}
<ul class="built"><li>A new document starts on <i>Inkjet · Letter vinyl</i>, after your 17 Oct pivot to inkjet on vinyl {cite('c56a0d98')}.</li>
<li>The preset chip in the top bar and the "…" button both open the presets modal {cite('spec')}.</li></ul>
</div>""")

    items.append(f"""
<div class="item"><h3>4 · The Marker fields, Separation (new) and Turn included</h3>
<div class="media">{media_pair(
    fig(media, "grid_fields", "Grid fields: Type, Dictionary, First ID with the range, Marker with Auto, Separation, Columns × Rows",
        f"A grid: Type, Dictionary, First ID with its range (#0–3), Marker + Auto, <b>Separation</b> (blank = the core's rule, shown greyed), Columns × Rows {cite('facts')}."),
    fig(media, "panel_turn", "The Turn row (0, 90, 180, 270) with its Joint Origin note, and Corner mark",
        f"Turn in 90° steps, with what it does to the Joint Origin written under it; Corner mark below {cite('facts')}."), "")}</div>
{quote("Type of marker - Single, Grid, Charuco · Dictionary · ID/or first ID of the range · Origin · Option to rotate · Marker Size · Checker Size (for Charuco) · Seperation (for grid) · Columns · Rows", "Marker › Choices (list joined)", cite("vault"))}
<ul class="built"><li>Checker shows only for ChArUco, Separation only for grids, Flip only when there is no reference face {cite('spec')}.</li>
<li>Separation is a new core field (<code>numbers.separation</code>): a typed gap goes all the way into OpenCV's board definition; 0 keeps today's rule {cite('c37647aa')}.</li></ul>
</div>""")

    items.append(f"""
<div class="item"><h3>5 · Manual always works: a typed size is drawn as typed and flagged red</h3>
<div class="media">{fig(media, "typed", "A 2 by 2 grid typed at 34 mm, drawn past the rectangle with a red outline; the Marker row is red with the message",
    f"Grid 2×2, Marker typed <b>{typed['marker_mm']:g} mm</b> in the {ins['w']:.2f} × {ins['h']:.2f} mm rectangle: the outline ({typed['outer_mm'][0]:.1f} × {typed['outer_mm'][1]:.1f} mm) is drawn in red past the orange rectangle, and nothing is refused {cite('facts')}.")}</div>
<div class="media">{media_pair(
    fig(media, "row_issue", "The Marker row in red with the overflow message under it",
        f"Close-up: the issue sits under its own row: <i>“{E(typed['issue'])}”</i> {cite('facts')}"),
    fig(media, "ref_calib", "Zach's reference: calib.io's red message 'The pattern exceeds the board dimensions'",
        "Your reference: calib.io's red linter (it lets you do it anyway)"), "")}</div>
{quote("You can always set these values to anything and it won't block you, it may just throw a warnign saying that its outside of the size of the rectangle!", "Marker", cite("vault"))}
<ul class="built"><li>Core change <code>settings.as_typed</code>: a typed size is laid out as typed and never clamped; the plan reports <code>overflow_mm</code> and an error on the Marker row, and stays <code>ok</code>. Opt-in: the Fusion add-in and old files still fit as before {cite('c37647aa')}.</li></ul>
<p class="rough"><b>Rough edge.</b> On the inkjet presets a typed size snaps down to whole printer dots per cell: {typed['marker_mm']:g} mm is drawn at {typed['drawn_marker_mm']:.2f} mm, and the row says so (“cell multiple: 34.0 mm → 33.782 mm”). A preset with no cell step draws exactly as typed {cite('tests_web')}.</p>
</div>""")

    sugg_rows = "".join(f"<li>{E(s)}</li>" for s in facts["suggestions"])
    items.append(f"""
<div class="item"><h3>6 · Suggestions with a short reason</h3>
<div class="media">{media_pair(
    fig(media, "suggest", "The Suggest list for the plate's rectangle: eight layouts, each with a reason",
        f"Built: eight layouts for the plate's rectangle (Grid). Picking one turns Auto off {cite('facts')}."),
    fig(media, "ref_suggest", "Zach's reference: the earlier Layout dropdown with largest marker, best fill, most markers",
        "Your reference: the earlier layout list in Fusion"), "")}</div>
{quote("it can just give me some options and perhaps short reason as to why its suggested.", "Suggestions and Auto Sizing", cite("vault"))}
<details><summary>The full reasons (the panel cuts them with “…”)</summary><ol class="note">{sugg_rows}</ol></details>
<p class="rough"><b>Rough edge.</b> The useful words come first (largest marker, best fill, most markers, fill %), but each reason then spells out the printer-dot arithmetic (“cells = 124 dots of 0.042333 mm”), so the line is cut. Shorter reasons are a small next step.</p>
</div>""")

    o = facts["plan_single"]["origin"]
    items.append(f"""
<div class="item"><h3>7 · The Joint Origin, Turn and Flip</h3>
<div class="media narrowimg">{fig(media, "sketch_marker", "Close-up of the marker in the sketch: the Joint Origin's x axis red and y axis green at the marker's centre, a turn arc above",
    f"The Joint Origin is drawn where the plan puts it: x red, y green, at the marker's centre ({o[3]:.2f}, {o[7]:.2f}) mm, z {o[11]:g} mm (the top of the 0.1 mm vinyl). The arc above is the turn; the Turn row (item 4) says what the frame is {cite('facts')}.")}</div>
{quote("I like the rotation to change which way is up or down.", "What is the entry point? (v1)", cite("vault"))}
{quote("if no reference frame then you get the option to manualy select flip for the upwards direction.", "What is the entry point? (v1)", cite("vault"))}
<ul class="built"><li><code>MarkerPlan.origin</code> is OpenCV's frame of the marker as built, a 4 × 4 in the sketch frame (mm); the UI only draws it {cite('contract')}.</li>
<li>With a face selected, Flip is hidden (the face sets Z); a drawn rectangle with no face shows Flip (item 2's still) {cite('spec', 'facts')}.</li></ul>
</div>""")

    lb = labels or {}
    before_cap = (lb.get("before", {}).get("printed_font_mm") or [0])[0] * 0.718
    items.append(f"""
<div class="item"><h3>8 · The label is sketch text, and now prints at the sketch's size</h3>
<div class="media">{media_pair(
    fig(media, "label_before", "Before the fix: the printed label is tiny under the marker",
        f"<b>Before</b> (<code>404467f</code>): the page printed its own 6 pt caption: cap height <b>{before_cap:.2f} mm</b> {cite('labels')}."),
    fig(media, "label_after", "After the fix: the printed label matches the sketch label's size",
        f"<b>After</b> (HEAD): cap height <b>{(lb.get('after', {}).get('printed_font_mm') or [0])[0] * 0.718:.2f} mm</b>, the sketch label's {cite('labels')}."), "")}</div>
<div class="media">{media_pair(
    fig(media, "sketch_label", "The label #0 under the rectangle in the sketch",
        f"In the sketch: <i>#0</i>, cap height {sketch_cap:.2f} mm, under the rectangle {cite('facts')}."),
    fig(media, "print_label", "The live Print page's corner: the marker, its cut line and the label",
        f"On the live Print page: font {pr['printed_label_font_mm'][0]:.2f} mm → cap height <b>{printed_cap:.2f} mm</b>, same as the sketch; it sits under the marker's outline, since the rectangle isn't printed (decision c) {cite('facts')}."), "")}</div>
<p class="note">The two close-ups above are cut to the same 64 mm-wide window, so they are at one scale.</p>
{quote("So whatevery sketch you do, that is the sketch in which the labels text will be auto added to, so you could potetially move it around custom if you want...", "What is the entry point? (v1)", cite("vault"))}
<ul class="built"><li>The label is plain text beside the rectangle, as a CAD text entity would be; drag it on the canvas to move it (it sets <code>label.offset_mm</code>) {cite('contract', 'spec')}.</li>
<li>Fix in <code>core/sheet.py</code>: <code>PrintItem.caption_cap_mm</code> / <code>caption_gap_mm</code>; the online Studio sets them from the sketch label, so the page's label is never shrunk or cut short. Absent = the old caption, so other callers are unchanged {cite('c56a0d98')}.</li></ul>
</div>""")

    items.append(f"""
<div class="item"><h3>9 · Sketch → ArUco Extrude → Joint Origin</h3>
<div class="media">{media_pair(
    fig(media, "timeline", "The timeline: Sketch, ArUco Extrude, Joint Origin",
        f"Built: the timeline at the bottom, Fusion-style icons; click selects, double-click re-opens the panel {cite('facts', 'spec')}."),
    fig(media, "ref_timeline", "Zach's reference: the three timeline icons in Fusion",
        "Your reference (Fusion's timeline, 2× size)"), "r31")}</div>
{quote("three features.. 2 the sketch (optionally geneated) hte joint origin auto generated.", "What is the entry point? (v1)", cite("vault"))}
</div>""")

    items.append(f"""
<div class="item"><h3>10 · Print at true scale, with a bar to measure</h3>
<div class="media">{fig(media, "print", "The Print dialog: the Letter vinyl page at actual size, the marker with its cut line and label, a 50 mm scale bar, Download SVG, Download PDF, Print",
    f"Export › Print…: the preset's page ({pr['page_mm'].replace('x', ' × ')} mm, Letter) at 100 %, with the cut line, the label and a 50 mm bar; Actual size / Fit; Download SVG, Download PDF, Print {cite('facts')}.")}</div>
<div class="media narrowimg">{fig(media, "scale_bar", "The 50 mm scale bar", f"The bar: measure it to check the print scale {cite('facts')}.")}</div>
{quote("Having to copy paste into canva, and resize to print", "Introduction: what it felt like before", cite("vault"))}
</div>""")

    items.append(f"""
<div class="item"><h3>Also: dark theme, and a phone</h3>
<div class="media">{fig(media, "dark", "The same screen in the dark theme", f"The theme button in the top bar switches every kit variable {cite('facts')}.")}</div>
<div class="media">{media_pair(
    fig(media, "mobile", "390 by 844: the panel docked to the bottom, covering the marker",
        f"390 × 844: the panel docks to the bottom ({mob['panel']['width']:.0f} px wide, {mob['panel']['height']:.0f} px tall); no horizontal scroll (measured) {cite('facts')}."),
    fig(media, "mobile_collapsed", "390 by 844 with the panel collapsed: the marker is visible",
        f"Collapsed (chevron): the marker shows {cite('facts')}."), "")}</div>
<p class="rough"><b>Rough edge.</b> On a phone the docked panel covers the marker until you collapse it: the view fits the whole screen, not the part above the panel.</p>
</div>""")

    # ---------------------------------------------------------------- 5. proof
    proof_rows = [
        ("tests/web (CPython)", "22 passed in 0.37 s", "runs"),
        ("Pyodide / CPython parity", "20 / 20 byte-identical JSON, the sheet's PDF included (Pyodide 318 ms, CPython 427 ms)", "runs"),
        ("vitest", "48 passed (4 files)", "runs"),
        ("Playwright, local build", "8 / 8 + the hero video", "build_session"),
        ("Playwright, live arucostudio.com", f"8 / 8 in 59.9 s (the build session saw 57 s); core ready in {ready[0]:g}–{ready[-1]:g} s, median {med:g} s, over {len(ready)} fresh loads", "runs"),
        ("Report stills, live", "8 / 8 (<code>report.spec.ts</code>)", "facts"),
        ("core / plan / scene", f"core {E(SUITES['core'])}; plan {E(SUITES['plan'])}; scene {E(SUITES['scene'])}: unchanged from the Linux baseline", "suites"),
    ]
    proof = "".join(f"<tr><td>{a}</td><td>{b} {cite(k)}</td></tr>" for a, b, k in proof_rows)
    commit_rows = "".join(f"<tr><td class='n'><code>{E(h)}</code></td><td>{E(s)}</td></tr>"
                          for h, s in (c.split("\t", 1) for c in commits))

    # ---------------------------------------------------------------- the page
    body = f"""
<main>
<h1>ArUco Studio, online</h1>
<div class="meta">Review · 18 Oct 2026 · branch <code>{E(branch)}</code> at <code>{E(head)}</code> · built by <code>docs/build_online_studio_report.py</code></div>

<div class="verdict"><b>arucostudio.com is live: the online Studio v1, the marker rectangle flow, with the same Python core the Fusion add-in uses running in your browser.</b>
<div class="qual"><span class="pill warn">not merged</span><span class="pill warn">not pushed</span> On branch <code>{E(branch)}</code>. The site was deployed from that branch: all {LIVE_FILES} files of its Python core are byte-identical to commit <code>56a0d98</code>, its build stamp {cite('live_zip')}. The branch has moved on since: <code>ebc46a5</code> (14:21) sets the contract for the next wave; the site doesn't have it.</div></div>

<h2 style="border:0;margin-top:20px;padding-top:0">See it</h2>
<figure class="hero"><video autoplay muted loop playsinline controls preload="auto" poster="{uri(media, 'hero_poster')}" width="{media['hero'][2]}" height="{media['hero'][3]}" aria-label="Hero video: the plate example, click the face, A, Grid, a suggestion, drag the rectangle, Print">
<source src="{uri(media, 'hero')}" type="video/mp4">Your browser can't play this video; the frame above is from it.</video>
<figcaption>The primary flow on the live site: Examples › Plate → click the face → <span class="kbd">A</span> → Grid → a suggestion → drag the rectangle → Print…. Recorded by Playwright in Chrome; {hero_s:.1f} s at {HERO_SPEED}× speed. Cut: {HERO_KEEP[1][0] - HERO_KEEP[0][1]:.1f} s of core loading (the chip goes “Core loading…” → “Python ready”) and the last {src_s - HERO_KEEP[-1][1]:.1f} s on the Print dialog {cite('hero')}.</figcaption></figure>
<div class="try"><b>Try it</b><ol>
<li>Open <a href="https://arucostudio.com">https://arucostudio.com</a> and wait for <i>Python ready</i> (about {med:g} s).</li>
<li>File › Examples… › <b>Plate</b>.</li>
<li>Click inside the face, between the holes.</li>
<li>Press <span class="kbd">A</span>. Then try Grid, pick a suggestion, drag the orange rectangle, or type a big Marker size.</li></ol></div>

<h2>What you asked → what's there</h2>
<p class="note">Your words are quoted from your note as written {cite('vault')}. Every still is from the live site today {cite('facts')}; click any image to enlarge it.</p>
{"".join(items)}

<h2>How it's built</h2>
{diagram(False)}{diagram(True)}
<p class="note">The diagram is v1 as deployed: 7 calls. Since then <code>ebc46a5</code> added <code>verify</code>, <code>readable</code> and <code>assign_ids</code> for the next wave {cite('barrier')}.</p>
<p class="note">The screen never computes marker geometry: it draws what <code>plan()</code> returns, in the sketch's millimetres {cite('spec')}. <code>inscribe(profile)</code> finds the largest clear rectangle in a face; <code>plan(rect)</code> only ever sees a rectangle, as you put it: “the input to this algorithim is always just a rectangle” and “Placing rectangles in a profile is actualyl a seperate step! one step above in the pipeline..” {cite('vault', 'contract')}. <b>Parity</b> here means the same call gives byte-for-byte the same JSON in Pyodide (Python compiled to WebAssembly, in the browser) and in CPython {cite('webapi')}.</p>
<h3>Stock parts</h3>
<div class="tbl"><table class="stack"><thead><tr><th>Element</th><th>Before</th><th>Off-the-shelf part</th><th>Behaviour that must survive</th></tr></thead><tbody>
<tr><td data-label="Element">Where the core runs</td><td data-label="Before">A FastAPI server on 127.0.0.1:5360 (<code>studio/</code>)</td><td data-label="Off-the-shelf part"><b>Pyodide 314.0.7</b> in a Web Worker, self-hosted under the site's <code>/pyodide/</code> {cite('pkg', 'worker')}</td><td data-label="Behaviour that must survive">Byte-identical JSON to CPython (20 / 20); the core stays stdlib-only</td></tr>
<tr><td data-label="Element">UI kit</td><td data-label="Before"><code>studio/packages/bam-ui</code></td><td data-label="Off-the-shelf part"><b><code>@bam/ui</code></b> reused as is: its tokens, field rows with per-row issues, and <code>LibraryShell</code> for the presets modal {cite('spec')}</td><td data-label="Behaviour that must survive">Each issue under its own row; light / dark; a host restyles it with variables</td></tr>
<tr><td data-label="Element">Hosting</td><td data-label="Before">Your machine only</td><td data-label="Off-the-shelf part">A <b>Cloudflare static-assets Worker</b>, deployed with <code>wrangler</code> to arucostudio.com + www {cite('pkg')}</td><td data-label="Behaviour that must survive">Static files only: no server code to run or keep alive</td></tr>
<tr><td data-label="Element">The canvas</td><td data-label="Before">A hand-rolled mini CAD with many tags and 3D (<code>studio/</code>)</td><td data-label="Off-the-shelf part">Stays <b>hand-rolled SVG</b> (<code>web/src/sketch/</code>); see the tldraw question below</td><td data-label="Behaviour that must survive">Exact mm; Fusion's edge vs inside picking; profiles with holes</td></tr>
<tr><td data-label="Element">The core</td><td data-label="Before"><code>aruco_studio</code> core / plan / scene</td><td data-label="Off-the-shelf part">Unchanged (the stock seam), plus two opt-in keys</td><td data-label="Behaviour that must survive">The Fusion add-in and old files plan exactly as before</td></tr>
</tbody></table></div>

<h2>Proof</h2>
<div class="tbl"><table><thead><tr><th>Check</th><th>Result</th></tr></thead><tbody>{proof}</tbody></table></div>
<p class="note">The core and plan failures were there before today and are the same before and after the core change {cite('c37647aa')}. All {SUITES['core_failed']} core failures are golden-file numbers that differ in the last digit: the largest relative difference is {E(SUITES['core_max_rel'])}, e.g. golden {E(SUITES['example'][0])} vs replay {E(SUITES['example'][1])} {cite('suites')}. The goldens were recorded on the Windows box and are replayed here with Linux's math library {cite('goldens')}. Plan's 2 are the same family: {E(SUITES['plan_failures'])} {cite('suites')}. A separate task is queued for them.</p>
<h3>The two core changes, both opt-in</h3>
<ul><li><code>settings.as_typed</code>: a typed size, count, checker or separation is laid out as typed, centred and never clamped; the plan adds <code>overflow_mm</code> and a red issue on the Marker row. Without the key, a tag fits exactly as before {cite('c37647aa')}.</li>
<li><code>numbers.separation</code>: a grid's gap in mm, all the way into OpenCV's board definition; absent or 0 keeps the gap rule {cite('c37647aa')}.</li></ul>
<details><summary><code>core/settings.py</code>: how separation is read (diff of <code>37647aa</code>)</summary>{diff_html(diff_settings)}</details>
<h3>The WYSIWYG label fix</h3>
<p>Before, the printed label was {before_cap:.2f} mm tall under a {sketch_cap:.2f} mm sketch label; now the page prints it at {printed_cap:.2f} mm, measured on the live Print page (item 8) {cite('labels', 'facts')}.</p>
<details><summary><code>core/sheet.py</code>: the diff of <code>56a0d98</code></summary>{diff_html(diff_sheet)}</details>
<details><summary>Commits on <code>{E(branch)}</code> since the scaffold ({len(commits)}; v1 is the {len(v1)} from <code>5ea9599</code> to <code>2f5cf62</code>)</summary><div class="tbl"><table><tbody>{commit_rows}</tbody></table></div></details>

<h2>The tldraw question</h2>
<p><b>Recommendation: don't adopt tldraw (or flatten-js) now.</b> The Python core already does the hard geometry (inscribe with holes, fitting, the lint), so the canvas only has to hold a few closed shapes, pick them the way Fusion does, and draw what the core returns. flatten-js would redo that geometry a second time in another language, which is exactly what the parity test exists to prevent.</p>
<div class="tbl"><table><thead><tr><th>Criterion (weight)</th><th>Hand-rolled SVG (built)</th><th>tldraw</th></tr></thead><tbody>
<tr><td>Exact mm and dimensions (5)</td><td>2 · mm grid, typed W × H, the outer dimension</td><td>0 · no units or dimension tool</td></tr>
<tr><td>Select closed regions with holes (5)</td><td>2 · edge = the rectangle, inside = the profile minus its holes (e2e test 8)</td><td>0 · no region concept: a line is a line</td></tr>
<tr><td>Free to ship on a public site (4)</td><td>2 · nothing to license</td><td>0 · needs a production licence key since SDK 4.0 {cite('survey')}</td></tr>
<tr><td>Still works in 10 years (4)</td><td>2 · no dependency</td><td>1 · majors move fast (SystemSketch is on 5.3.2) {cite('sspkg')}</td></tr>
<tr><td>Free ergonomics: undo, text editing, multi-select (2)</td><td>0 · ours to write; undo isn't there yet</td><td>2 · best in class</td></tr>
<tr><th>Weighted (of 40)</th><th class="score">36</th><th class="score">8</th></tr>
</tbody></table></div>
<p class="note">Scores: 0 = no, 1 = partly, 2 = yes, times the weight.</p>
<p><b>The door stays open.</b> The canvas is <code>web/src/sketch/</code>: <code>Viewport.tsx</code> draws, <code>model.ts</code> holds the shapes, profiles and picking. Outside that folder, only the store and the document use <code>model.ts</code>'s exports; the panel, the presets and Print never touch the canvas. A tldraw canvas would replace <code>Viewport.tsx</code> behind the same exports {cite('seam')}.</p>

<h2>Decisions for you</h2>
<p class="note">Each has my recommendation and what happens if you say nothing.</p>
<div class="packet">
<div class="q"><h4>(a) Push <code>{E(branch)}</code> to GitHub?</h4><p class="rec"><b>Recommend yes:</b> the source behind the live site is only on this machine (no remote branch has it as of the last fetch; <code>origin</code> has <code>main</code> only).</p><p class="def">If you say nothing: it stays local. The live site doesn't depend on it.</p></div>
<div class="q"><h4>(b) Merge into <code>main</code>?</h4><p class="rec"><b>Your call</b>: v1 is {len(v1)} commits (<code>5ea9599</code> → <code>2f5cf62</code>): it adds <code>web/</code> and two opt-in core keys, and leaves <code>studio/</code> untouched. The branch also carries this report and the next wave's contract (<code>ebc46a5</code>).</p><p class="def">If you say nothing: no merge.</p></div>
<div class="q"><h4>(c) The printed label: under the outline, or inside the sticker?</h4><p class="rec">Today the label prints under the marker's outline at the sketch's size and gap; the rectangle itself isn't printed (item 8). The alternative: print the whole rectangle as the sticker, with the label inside the cut. <b>Recommend keeping the outline</b>: it's the smallest sticker, and the label matches the sketch either way.</p><p class="def">If you say nothing: the outline.</p></div>
<div class="q"><h4>(d) What next, in this order?</h4><ol>
<li><b>A one-click “Get it for Fusion” download</b>, as the site's front door, after your “1 click downloads” {cite('vault')}. The add-in is in cad-exporter on the Windows box, so it starts there.</li>
<li><b>A 3D toggle</b> to see heights (“we also want a 3D viewer so you can see heights”) {cite('vault')}.</li>
<li><b>Undo.</b></li>
<li><b>Rotating rectangles in the UI</b> (the contract and core already take <code>angle_deg</code>; parity tests a 30° rectangle) {cite('contract')}.</li>
<li><b>DXF import of faces.</b></li>
<li><b>The camera verifier in the browser</b>: Pyodide ships OpenCV {cite('spec')}.</li></ol>
<p class="def">If you say nothing: I take them in this order, starting with (1).</p></div>
<div class="q"><h4>(e) Worth a /llm-judge?</h4><p class="rec"><code>core/autosize.py</code> changed {a_add + a_del} lines (+{a_add} −{a_del}) under the new opt-in key. What guards it: the 22 <code>tests/web</code> cases (several written for <code>as_typed</code> and separation) and the core suites, whose failures are the same before and after; no test under <code>tests/core</code> was added for it {cite('c37647aa', 'tests_web')}.</p><p class="def">If you say nothing: no audit (your rule).</p></div>
</div>
<h3>Left, not blocked: rough edges seen while shooting</h3>
<ul>
<li>On a phone, the docked panel covers the marker until it is collapsed (item “Also”).</li>
<li>When a marker overflows, the label stays under the rectangle, so it overlaps the red outline (item 5's still).</li>
<li>Numbers show up to 4 decimals in places: W 49.9646 / H 79.8438, Marker 37.3377, the red message, Separation “6.7733 (rule)”. Truthful, but noisy; a display rule is a small taste call.</li>
<li>Suggest reasons are cut with “…” (item 6).</li>
<li>The inscribed rectangle is {ins['w']:.2f} × {ins['h']:.2f} mm where 50 × 80 mm fits: within 0.2 mm.</li>
</ul>

<h2>Deliberately not done</h2>
<ul>
<li><b>No tldraw</b>: see above.</li>
<li><b>No 3D</b>: v1 is one sketch plane; 3D is next step 2.</li>
<li><b>The old <code>studio/</code> left untouched</b>: not deleted, not developed, until you decide {cite('spec')}.</li>
<li><b>No push, no merge.</b></li>
<li><b>No audit run</b>: audits are yours to ask for.</li>
</ul>

<h2>Source Index</h2>
<ol class="sources">\x00INDEX\x00</ol>
</main>
<div id="zoom" role="dialog" aria-label="Enlarged image"><img alt=""></div>
"""
    order: list[str] = []
    for k in re.findall(r"\x00([a-z0-9_]+)\x00", body):
        if k not in order:
            order.append(k)
    num = {k: i + 1 for i, k in enumerate(order)}
    body = re.sub(r"\x00([a-z0-9_]+)\x00", lambda m: f'<a href="#s{num[m.group(1)]}">{num[m.group(1)]}</a>', body)
    body = body.replace("\x00INDEX\x00", "".join(f'<li id="s{num[k]}">{SOURCES[k]}</li>' for k in order))
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>Online Studio review</title>'
            f'<meta name="description" content="arucostudio.com, the online ArUco Studio v1: what was built on 18 Oct 2026, the proof, and the decisions left.">'
            f'<style>{CSS}</style></head><body>{body}<script>{JS}</script></body></html>')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


# the core / plan / scene numbers: <src>/suites.json, written from a pytest run
# on this machine ({"core": "7,316 passed / ...", "plan": ..., "scene": ...,
# "core_failed": 79, "core_max_rel": "2.5 × 10⁻¹⁵", "example": [golden, replay]})
SUITES: dict = {}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--work", type=Path, default=WORK)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--label-renders", action="store_true", help="re-make label-before/after.png first")
    a = ap.parse_args()
    if a.label_renders or not (a.src / "label-renders.json").exists():
        print(json.dumps(label_renders(a.src), indent=2))
    SUITES.update(json.loads((a.src / "suites.json").read_text()))
    out = build(a.src, a.out, a.work)
    print(f"{out}  {out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
