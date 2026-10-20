#!/usr/bin/env python3
"""Build the review report for the night of 2026-10-20 (aruco-studio main @ 9c9bd36).

    python3 docs/build_night_report.py [--src DIR] [--bench DIR] [--work DIR] [--out FILE]

Writes reports/media/aruco-studio-night-2026-10-20.html: one self-contained
page, every image and both videos inlined as data URIs (no server, no
network). reports/media/ is gitignored; this script is the reviewed source.
It follows docs/build_online_studio_report.py and docs/build_v1_report.py.

Standard library only; it shells out to ffmpeg / ffprobe for the media and
to git (read-only) for commit subjects.

Its raw inputs (--src) are the captures each lane made tonight with headless
Playwright, kept in that session's scratchpad (ephemeral: copy the folder to
reports/media/aruco-studio-night-2026-10-20-src/ to rebuild later):

  lane-sketchx/   marker-maker.webm (the hero), the sketch-tool stills
  lane-view3d/    view3d-drag-type.webm, the 3D stills
  lane-panelv1/   the panel's tabs on the real core, sbs-*.png (proposal | built)
  lane-profui/    profile-a / b / c
  kpi/            the Vibe Tracks track screenshot

The compute-time chart is drawn from the bench's own output (--bench,
~/.local/share/aruco_studio_bench/kpi: kpi_series.jsonl, runs_table.jsonl),
pinned to the run at BENCH_T.

Several lanes were shot before the new panel merged, so their stills show the
old panel: those are cropped to the canvas (the crops below say so).
Every number on the page is read from the bench files, git, or the source
named in its Source Index; the copy says which.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote as urlquote

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-10-20"
NAME = f"aruco-studio-night-{DATE}"
SCRATCH = Path("/tmp/claude-1000/-home-bam-zach-brain--claude-worktrees-quirky-hodgkin-6cfeae/"
               "473097fc-b055-4240-85ae-5ee356761d0e/scratchpad")
SRC = SCRATCH
WORK = SCRATCH / "report" / "build"
OUT = ROOT / "reports" / "media" / f"{NAME}.html"
BENCH = Path.home() / ".local/share/aruco_studio_bench/kpi"
FFMPEG, FFPROBE = "/usr/bin/ffmpeg", "/usr/bin/ffprobe"

MAIN = "9c9bd36"                 # tonight's work as reviewed (pushed); main has since gained only the landing recapture
LIVE_STAMP = '{"version":"0.1.0","git":"0f22b1e"}'   # https://arucostudio.com/py/aruco_studio.zip, fetched 2026-10-20 ~15:25 PDT
LANDING_RECAPTURE = "0f22b1e"    # merged 15:17: the landing's retaken shots, its tests and the 404 text
E2E = {"passed": 98, "skipped": 19}                 # the dispatcher's full e2e run on merged main (not re-run here)
BENCH_T = "2026-10-20T21:39:05Z"                    # the second bench run (the KPI's latest point)
BENCH_T0 = "2026-10-20T21:31:19Z"                   # the first
VT_BRANCH = "claude/aruco-studio-kpi"

# The hero: marker-maker.webm is 12.6 s. Keep 1.8 .. 11.0 s: the first 1.8 s is
# the plate example loading, the last 1.6 s is the finished canvas standing
# still. Real speed. WHY: <= 20 s, every second shows a step.
HERO = ("lane-sketchx/marker-maker.webm", 1.8, 11.0, None, 8.6)
# The 3D clip: 11.68 s, keep 0 .. 9.3 s (the end is still), cropped to the
# model and its arrows at native pixels (the canvas around it is empty grid).
V3D = ("lane-view3d/view3d-drag-type.webm", 0.0, 9.3, "crop=760:380:340:150", 8.8)
CRF = 24

# (name, source, ffmpeg filter, WebP quality). Sources are 1280 x 800 at 1x,
# so crops stay at native pixels.
OLD_PANEL = "crop=650:625:190:95"   # WHY: these lanes were shot before the panel merged: canvas only
STILLS = [
    # 1 · profile-only
    ("p_face", "lane-profui/profile-a-plate-face.png", OLD_PANEL, 86),
    ("p_rect", "lane-profui/profile-b-rectangle.png", OLD_PANEL, 86),
    ("trim_profile", "lane-profui/profile-c-trim-profile.png", OLD_PANEL, 86),
    ("trim_marker", "lane-profui/profile-c-trim-marker.png", OLD_PANEL, 86),
    # 2 · the panel (merged layout, real core)
    ("sbs_make", "lane-panelv1/sbs-make.png", "null", 86),
    ("tab_make", "lane-panelv1/panel-inkjet-make.png", "crop=322:452:879:125", 88),
    ("tab_marker", "lane-panelv1/panel-inkjet-marker.png", "crop=322:472:879:125", 88),
    ("tab_label", "lane-panelv1/panel-inkjet-label.png", "crop=322:517:879:125", 88),
    ("presets", "lane-panelv1/panel-presets.png", "crop=1082:400:99:69,scale=920:-1:flags=lanczos", 86),
    # 3 · heights (the 3D shots predate the panel merge: model only)
    ("h_panel", "lane-panelv1/panel-print3d-make.png", "crop=322:148:879:372", 90),
    ("h_driven", "lane-view3d/3d-print-driven.png", "crop=520:300:455:195", 88),
    ("h_set", "lane-view3d/3d-print-both-set.png", "crop=520:300:455:195", 88),
    ("h_face_black", "lane-view3d/face-black-only.png", "crop=780:500:90:140", 86),
    # 4 · the toggle
    ("t_inkjet", "lane-view3d/inkjet.png", "crop=560:300:440:205", 86),
    ("t_top", "lane-view3d/top-view-label.png", "crop=594:672:284:68,scale=340:-1:flags=lanczos", 86),
    # 5 · sketch tools
    ("s_toolbar", "lane-sketchx/dim-w-placed.png", "crop=842:40:219:748", 92),
    ("s_boxes", "lane-sketchx/draw-value-boxes.png", "crop=340:190:470:315", 90),
    ("s_dims", "lane-sketchx/dims-on-rectangle.png", "crop=400:280:620:290", 90),
    ("s_window", "lane-sketchx/select-window.png", "crop=550:210:350:315", 88),
    ("s_crossing", "lane-sketchx/select-crossing.png", "crop=550:210:350:315", 88),
    ("s_multi", "lane-sketchx/multi-move.png", "crop=510:160:480:330", 88),
    ("s_multi_toast", "lane-sketchx/multi-move.png", "crop=262:36:510:705", 90),
    # 6 · the KPI
    ("k_track", "kpi/aruco-studio-track-1280x800.png", "crop=960:600:300:0", 88),
]


# ------------------------------------------------------------------ media

def run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"failed: {' '.join(map(str, cmd))}\n{r.stderr[-2000:]}")
    return r.stdout


def dims(path: Path) -> tuple[int, int]:
    out = run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=width,height", "-of", "csv=p=0", str(path)])
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


def duration(path: Path) -> float:
    return float(run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]))


def fresh(dst: Path, src: Path) -> bool:
    return dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime


def webp(src: Path, dst: Path, vf: str, quality: int) -> Path:
    if not fresh(dst, src):
        run([FFMPEG, "-y", "-v", "error", "-i", str(src), "-vf", vf, "-c:v", "libwebp",
             "-quality", str(quality), "-compression_level", "6", "-frames:v", "1", str(dst)])
    return dst


def clip(src: Path, work: Path, name: str, a: float, b: float, crop: str | None, poster_t: float):
    """One real recording, cut to [a, b] s at real speed, H.264 for every
    browser, and a poster frame (the still a browser shows before it plays)."""
    key = hashlib.sha1(f"{a}|{b}|{crop}|{CRF}|{poster_t}".encode()).hexdigest()[:8]
    mp4, poster = work / f"{name}-{key}.mp4", work / f"{name}-poster-{key}.webp"
    vf = ",".join(x for x in (crop, "fps=25", "format=yuv420p") if x)
    if not fresh(mp4, src):
        run([FFMPEG, "-y", "-v", "error", "-ss", str(a), "-to", str(b), "-i", str(src), "-vf", vf,
             "-c:v", "libx264", "-preset", "veryslow", "-crf", str(CRF), "-tune", "animation",
             "-movflags", "+faststart", "-an", str(mp4)])
    if not fresh(poster, mp4):
        run([FFMPEG, "-y", "-v", "error", "-ss", str(poster_t), "-i", str(mp4), "-frames:v", "1",
             "-c:v", "libwebp", "-quality", "80", str(poster)])
    return mp4, poster


def encode(src: Path, work: Path) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    media: dict = {}
    for name, rel, vf, q in STILLS:
        # WHY the key: a changed crop or quality must re-encode, not reuse the cache
        key = hashlib.sha1(f"{rel}|{vf}|{q}".encode()).hexdigest()[:8]
        p = webp(src / rel, work / f"{name}-{key}.webp", vf, q)
        media[name] = (p, "image/webp", *dims(p))
    for name, (rel, a, b, crop, pt) in (("hero", HERO), ("v3d", V3D)):
        mp4, poster = clip(src / rel, work, name, a, b, crop, pt)
        media[name] = (mp4, "video/mp4", *dims(mp4))
        media[f"{name}_poster"] = (poster, "image/webp", *dims(poster))
        media[f"_{name}_s"] = duration(mp4)
        media[f"_{name}_src_s"] = duration(src / rel)
    return media


# ------------------------------------------------------------------ the bench

LAYOUTS = [("single", "1x1", "Single marker"), ("grid", "3x1", "Grid 3 × 1"), ("grid", "3x3", "Grid 3 × 3"),
           ("charuco", "5x4", "ChArUco 5 × 4"), ("charuco", "8x2", "ChArUco 8 × 2")]
HOSTS = [("cpython", "CPython"), ("pyodide-node", "Pyodide in Node"), ("browser", "Browser")]


def bench(bdir: Path) -> dict:
    """The warm p95 of every golden case at BENCH_T, the whole-bench points of
    both runs, and each host's startup, straight from the producer's files."""
    pts = [json.loads(line) for line in (bdir / "kpi_series.jsonl").read_text().splitlines() if line.strip()]
    runs = [json.loads(line) for line in (bdir / "runs_table.jsonl").read_text().splitlines() if line.strip()]
    whole = {p["t"]: p for p in pts if "slice" not in p and p["kpi"] == "feature_compute_ms"}
    whole50 = {p["t"]: p for p in pts if "slice" not in p and p["kpi"] == "feature_compute_ms_p50"}
    cases: dict = {}
    for p in pts:
        s = p.get("slice")
        if not s or p["t"] != BENCH_T or p["kpi"] != "feature_compute_ms" or s.get("phase") != "warm":
            continue
        k = (s["marker_type"], s["layout"], s["profile_kind"], s["method"], s["call"])
        cases.setdefault(k, {})[s["host"]] = p["value"]
    stamp = BENCH_T.replace("-", "").replace(":", "").replace("T", "-")[:15]
    startup = {}
    for h, _ in HOSTS:
        xs = [r["metrics"]["startup_ms_sum"] / r["metrics"]["startups"] for r in runs
              if r["run_id"].startswith(stamp) and r["facets"]["host"] == h and r["metrics"].get("startups")]
        startup[h] = statistics.median(xs) if xs else None
    rect_max = max(v for k, hv in cases.items() if k[2] == "rectangle" for v in hv.values())
    n_runs = sum(1 for r in runs if r["run_id"].startswith(stamp))
    slowest = whole[BENCH_T]["labels"]["slowest"]
    m = re.match(r".*-(\w+)-(\d+x\d+)-(\w+)-(\w+)-(\w+)$", slowest)
    return {"cases": cases, "now": whole[BENCH_T]["value"], "then": whole[BENCH_T0]["value"],
            "p50": whole50[BENCH_T]["value"], "now_sha": whole[BENCH_T]["source"]["code_sha"],
            "slowest": m.groups() if m else None, "startup": startup, "rect_max": rect_max, "n_runs": n_runs}


def chart_rows(b: dict) -> list:
    """Per layout: the browser's warm p95 on a face and on a rectangle, the
    slower of the inkjet and 3D-print presets (what you would wait for)."""
    rows = []
    for mt, lay, label in LAYOUTS:
        row = [label]
        for kind in ("face", "rectangle"):
            vals = {m: b["cases"][(mt, lay, kind, m, "plan")]["browser"] for m in ("inkjet", "print3d")}
            row.append((max(vals.values()), vals))
        rows.append(row)
    return rows


def bar(x0, y, w, h, r=3.0) -> str:
    """A bar with its data end rounded and its baseline end square."""
    r = min(r, h / 2, max(w, 0.01))
    return (f"M{x0:.1f},{y:.1f} h{w - r:.1f} a{r},{r} 0 0 1 {r},{r} v{h - 2 * r:.1f} "
            f"a{r},{r} 0 0 1 -{r},{r} h-{w - r:.1f} z")


def chart(rows: list, narrow: bool) -> str:
    vmax, ticks = 160.0, (0, 50, 100, 150)
    if narrow:
        W, x0, x1, top, row_h, bh = 360, 8, 300, 58, 64, 13
    else:
        W, x0, x1, top, row_h, bh = 880, 150, 800, 58, 50, 14
    sx = lambda v: x0 + (x1 - x0) * v / vmax
    out = [f'<g class="c-legend"><rect x="{x0}" y="8" width="12" height="12" rx="2" class="s1"/>'
           f'<text x="{x0 + 18}" y="18.5">A face with holes</text>'
           f'<rect x="{x0 + (150 if narrow else 170)}" y="8" width="12" height="12" rx="2" class="s2"/>'
           f'<text x="{x0 + (168 if narrow else 188)}" y="18.5">A rectangle</text></g>']
    y_end = top + row_h * len(rows)
    for t in ticks:
        out.append(f'<line class="c-grid" x1="{sx(t):.1f}" x2="{sx(t):.1f}" y1="{top - 8}" y2="{y_end}"/>'
                   f'<text class="c-tick" x="{sx(t):.1f}" y="{y_end + 16}" text-anchor="middle">{t}</text>')
    out.append(f'<text class="c-tick" x="{x1 + (0 if narrow else 30)}" y="{y_end + 16}" '
               f'text-anchor="{"end" if narrow else "start"}">{"" if narrow else "ms"}</text>')
    ref = sx(100)
    out.append(f'<line class="c-ref" x1="{ref:.1f}" x2="{ref:.1f}" y1="{top - 22}" y2="{y_end}"/>'
               f'<text class="c-reft" x="{ref + 5:.1f}" y="{top - 14}">100 ms: feels instant{"" if narrow else " (suggested)"}</text>')
    for i, (label, face, rect) in enumerate(rows):
        y = top + i * row_h
        if narrow:
            out.append(f'<text class="c-lab" x="{x0}" y="{y + 4}">{E(label)}</text>')
            yb = y + 10
        else:
            out.append(f'<text class="c-lab" x="{x0 - 12}" y="{y + bh + 3}" text-anchor="end">{E(label)}</text>')
            yb = y + 2
        for j, ((v, per), cls, kind) in enumerate(((face, "s1", "on a face with holes"), (rect, "s2", "on a rectangle"))):
            yy = yb + j * (bh + 3)
            tip = (f"{label} {kind}: {v:.0f} ms (browser, warm p95). "
                   f"Inkjet {per['inkjet']:.1f} ms · 3D print {per['print3d']:.1f} ms")
            out.append(f'<path class="c-bar {cls}" d="{bar(x0, yy, sx(v) - x0, bh)}" data-tip="{E(tip)}" '
                       f'tabindex="0" aria-label="{E(tip)}"/>'
                       f'<text class="c-val" x="{sx(v) + 6:.1f}" y="{yy + bh - 3}">{v:.0f}</text>')
    H = y_end + 26
    label = ("Bar chart: the browser's warm 95th-percentile compute time per golden case. On a face with holes "
             "each layout takes 112 to 151 ms; on a rectangle 8 to 35 ms. A line marks 100 ms.")
    return (f'<svg class="chart {"narrow" if narrow else "wide"}" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="{E(label)}">{"".join(out)}</svg>')


# ------------------------------------------------------------------ page parts

E = html.escape


def uri(media: dict, name: str) -> str:
    p, mime, *_ = media[name]
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")


def img(media: dict, name: str, alt: str) -> str:
    _, _, w, h = media[name]
    return (f'<img src="{uri(media, name)}" width="{w}" height="{h}" alt="{E(alt)}" decoding="async" '
            f'data-zoom style="max-width:{w}px">')


def fig(media: dict, name: str, alt: str, cap: str, cls: str = "", fit: bool = False) -> str:
    """fit: the figure is as wide as its image, so the caption wraps under it."""
    style = f' style="max-width:{media[name][2]}px"' if fit else ""
    return f'<figure class="{cls}"{style}>{img(media, name, alt)}<figcaption>{cap}</figcaption></figure>'


def video(media: dict, name: str, label: str) -> str:
    _, _, w, h = media[name]
    return (f'<video autoplay muted loop playsinline controls preload="auto" width="{w}" height="{h}" '
            f'style="max-width:{w}px" poster="{uri(media, name + "_poster")}" aria-label="{E(label)}">'
            f'<source src="{uri(media, name)}" type="video/mp4"></video>')


def quote(text: str, ref: str) -> str:
    return f'<blockquote><p>“{E(text)}”</p><cite>you {ref}</cite></blockquote>'


def git(*args: str) -> str:
    return run(["git", "-C", str(ROOT), *args]).strip()


def vault(path: str, label: str) -> str:
    return f'<a href="obsidian://open?vault=zach_brain&amp;file={urlquote(path)}">{E(label)}</a>'


def kbd(k: str) -> str:
    return f'<span class="kbd">{E(k)}</span>'


# ------------------------------------------------------------------ the page

CSS = r"""
:root{--bg:#ffffff;--fg:#1f2328;--muted:#5f6670;--faint:#8a9099;--line:#e3e5e8;--panel:#f7f7f8;--chip:#eef0f2;
--accent:#2563eb;--accent-bg:#eef3fe;--ok:#1a7f37;--ok-bg:#eaf6ed;--warn:#9a6700;--warn-bg:#fdf6e3;--bad:#c62828;--bad-bg:#fdeeee;
--code:#f3f4f6;--s1:#2a78d6;--s2:#eb6834;--shadow:0 1px 2px rgba(0,0,0,.05),0 4px 16px rgba(0,0,0,.05);color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#191a1c;--fg:#e6e7e9;--muted:#a3a8b0;--faint:#7c828b;
--line:#2e3034;--panel:#212226;--chip:#2a2c30;--accent:#7aa2ff;--accent-bg:#1f2a44;--ok:#6fd38b;--ok-bg:#1b2b20;--warn:#e3b341;
--warn-bg:#2d2616;--bad:#ff8a80;--bad-bg:#3a1f1f;--code:#25272b;--s1:#3987e5;--s2:#d95926;--shadow:none;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#191a1c;--fg:#e6e7e9;--muted:#a3a8b0;--faint:#7c828b;--line:#2e3034;--panel:#212226;--chip:#2a2c30;
--accent:#7aa2ff;--accent-bg:#1f2a44;--ok:#6fd38b;--ok-bg:#1b2b20;--warn:#e3b341;--warn-bg:#2d2616;--bad:#ff8a80;--bad-bg:#3a1f1f;
--code:#25272b;--s1:#3987e5;--s2:#d95926;--shadow:none;color-scheme:dark}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,"Noto Sans",
"Helvetica Neue",Arial,sans-serif;overflow-wrap:anywhere}
main{max-width:920px;margin:0 auto;padding:40px 24px 80px}
h1{font-size:30px;line-height:1.25;margin:0 0 6px;letter-spacing:-.01em}
h2{font-size:22px;line-height:1.3;margin:56px 0 10px;padding-top:18px;border-top:1px solid var(--line)}
h2 .tag{font-size:12.5px;font-weight:600;vertical-align:middle;margin-left:8px}
h3{font-size:17px;margin:30px 0 10px}
p{margin:0 0 12px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
code{font:13.5px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--code);padding:1px 5px;border-radius:4px}
sup{font-size:11px;color:var(--faint);margin-left:1px}sup a{color:var(--faint)}
.meta{color:var(--muted);font-size:14px;margin-bottom:22px}
.verdict{border:1px solid var(--line);background:var(--panel);border-radius:10px;padding:16px 18px;margin:18px 0 22px}
.verdict b.v{font-size:18px;line-height:1.45;display:block;margin-bottom:8px}
.verdict .qual{color:var(--muted);font-size:15px;margin:0}
.pill{display:inline-block;font-size:12.5px;font-weight:600;padding:1px 8px;border-radius:999px;background:var(--chip);color:var(--muted);white-space:nowrap}
.pill.ok{background:var(--ok-bg);color:var(--ok)}.pill.warn{background:var(--warn-bg);color:var(--warn)}
.toc{margin:0 0 24px;padding-left:22px}.toc li{margin:4px 0}.toc li::marker{color:var(--faint)}
.lead{font-size:17px;margin:0 0 14px}
figure{margin:0 0 14px}
figure img,video{display:block;width:100%;height:auto;border:1px solid var(--line);border-radius:8px;background:var(--panel)}
img[data-zoom]{cursor:zoom-in}
figcaption{font-size:13.5px;color:var(--muted);margin-top:6px;line-height:1.5}
.hero video{box-shadow:var(--shadow)}
.media{margin-bottom:12px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}
.pair figure{margin:0}
.three{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;align-items:start}
.three figure{margin:0}
.built{margin:10px 0 0;padding-left:22px}.built li{margin:4px 0}
.try{border:1px solid var(--accent);background:var(--accent-bg);border-radius:10px;padding:10px 16px;margin:14px 0 0;font-size:15px}
.kbd{font:12.5px ui-monospace,monospace;border:1px solid var(--line);border-bottom-width:2px;border-radius:4px;padding:0 5px;background:var(--bg);white-space:nowrap}
blockquote{margin:12px 0;padding:8px 14px;border-left:3px solid var(--line);background:var(--panel);border-radius:0 8px 8px 0}
blockquote p{margin:0 0 4px;font-style:italic}
blockquote cite{font-style:normal;font-size:12.5px;color:var(--faint)}
.note{font-size:14px;color:var(--muted)}
.def{font-size:14px;color:var(--muted);border-left:3px solid var(--line);padding:2px 10px;margin:10px 0}
.tbl{width:100%;overflow-x:auto;margin:10px 0 6px}
table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.45}
th,td{text-align:left;vertical-align:top;padding:6px 10px;border-bottom:1px solid var(--line)}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600}
td.n,th.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
details{border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:10px 0;background:var(--panel)}
summary{cursor:pointer;font-size:14.5px;color:var(--muted)}
.chart{width:100%;height:auto;margin:4px 0 2px;overflow:visible}
.chart.narrow{display:none}
.chart text{font:13px ui-sans-serif,system-ui,sans-serif;fill:var(--muted)}
.chart .c-lab{fill:var(--fg);font-size:13.5px;paint-order:stroke;stroke:var(--bg);stroke-width:4px;stroke-linejoin:round}
.chart .c-val{fill:var(--fg);font-variant-numeric:tabular-nums;font-size:12.5px}
.chart .c-legend text{fill:var(--fg)}
.chart .c-grid{stroke:var(--line);stroke-width:1}
.chart .c-ref{stroke:var(--faint);stroke-width:1.5;stroke-dasharray:4 4}
.chart .c-reft{font-size:12.5px}
.chart .s1{fill:var(--s1)}.chart .s2{fill:var(--s2)}
.chart .c-bar{cursor:default;outline:none}
.chart .c-bar:hover,.chart .c-bar:focus{stroke:var(--fg);stroke-width:1.5}
#tip{position:fixed;z-index:11;pointer-events:none;background:var(--fg);color:var(--bg);font-size:13px;line-height:1.4;padding:6px 9px;
border-radius:6px;max-width:300px;display:none}
.packet .q{border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:0 0 12px;background:var(--bg)}
.q h4{margin:0 0 6px;font-size:16px}
.q p{font-size:14.5px;margin:4px 0 0}.q .dflt{color:var(--muted)}
.sources{font-size:13.5px;color:var(--muted)}.sources li{margin:3px 0}
#zoom{position:fixed;inset:0;background:rgba(0,0,0,.82);display:none;align-items:center;justify-content:center;z-index:10;cursor:zoom-out;padding:16px}
#zoom img{max-width:100%;max-height:100%;border-radius:6px;background:#fff}
#zoom.on{display:flex}
@media (max-width:700px){
 main{padding:24px 16px 60px}
 h1{font-size:24px}
 h2{font-size:20px;margin-top:44px}
 .pair,.three{grid-template-columns:1fr}
 .chart.wide{display:none}.chart.narrow{display:block}
 table{font-size:13px}th,td{padding:5px 6px}
}
"""

JS = r"""
(function(){var z=document.getElementById('zoom'),zi=z.querySelector('img');
document.addEventListener('click',function(e){var t=e.target;
if(t.matches&&t.matches('img[data-zoom]')){zi.src=t.src;zi.alt=t.alt;z.classList.add('on');}
else if(z.classList.contains('on')&&(t===z||t===zi)){z.classList.remove('on');zi.removeAttribute('src');}});
document.addEventListener('keydown',function(e){if(e.key==='Escape'){z.classList.remove('on');}});
var tip=document.getElementById('tip');
function show(el,x,y){tip.textContent=el.getAttribute('data-tip');tip.style.display='block';
var w=tip.offsetWidth,h=tip.offsetHeight,vw=window.innerWidth;
tip.style.left=Math.max(8,Math.min(vw-w-8,x+12))+'px';tip.style.top=Math.max(8,y-h-12)+'px';}
document.querySelectorAll('.c-bar').forEach(function(b){
b.addEventListener('mousemove',function(e){show(b,e.clientX,e.clientY);});
b.addEventListener('mouseleave',function(){tip.style.display='none';});
b.addEventListener('focus',function(){var r=b.getBoundingClientRect();show(b,r.right,r.top);});
b.addEventListener('blur',function(){tip.style.display='none';});});})();
"""


def build(src: Path, bdir: Path, out: Path, work: Path) -> Path:
    media = encode(src, work)
    b = bench(bdir)
    rows = chart_rows(b)
    head = MAIN
    now_main = git("rev-parse", "--short", "main")
    pushed = git("rev-parse", "main") == git("rev-parse", "origin/main")
    # WHY: say exactly what main gained after the reviewed commit, from git, not from memory
    since = [f for f in git("diff", "--name-only", MAIN, now_main).splitlines()] if now_main != MAIN else []
    since_other = sorted({f for f in since if not f.startswith(("web/public/about/", "web/e2e/landing", "docs/build_landing"))})
    subj = lambda h: git("show", "-s", "--format=%s", h)
    st = b["startup"]
    slow_mt, slow_lay, slow_kind, slow_method, _ = b["slowest"]
    slow_name = {"charuco": "ChArUco", "grid": "Grid", "single": "Single"}[slow_mt] + " " + slow_lay.replace("x", " × ")
    face_lo = min(r[1][0] for r in rows)
    rect_hi = max(r[2][0] for r in rows)

    # Citations: a placeholder per source key now, numbered in order of first
    # appearance on the finished page, then the Source Index.
    def cite(*keys: str) -> str:
        for k in keys:
            assert k in SOURCES, k
        return "<sup>" + ",".join(f"\x00{k}\x00" for k in keys) + "</sup>"

    def commit(h: str, what: str = "") -> str:
        return f'commit <code>{h}</code>{": " + what if what else ""} (“{E(subj(h)[:150])}{"…" if len(subj(h)) > 150 else ""}”)'

    lanes = "tonight's headless Playwright captures from the lane"
    SOURCES = {
        "brief": "tonight's dispatcher session (the brief for this report): the full e2e run on merged main, the open items and the questions for you. The e2e run was not repeated for this report",
        "live": f'<code>https://arucostudio.com/py/aruco_studio.zip</code>, fetched 2026-10-20 by this report\'s session: its <code>_build.json</code> is <code>{E(LIVE_STAMP)}</code>',
        "git": f'<code>git log main</code> in <code>/home/bam/aruco-studio</code>: tonight\'s work ends at <code>{MAIN}</code>; <code>main</code> is now <code>{now_main}</code>, {"level with" if pushed else "NOT level with"} <code>origin/main</code> (as last fetched); <code>git diff --name-only {MAIN} {now_main}</code>: {len(since)} files, the landing page (its page, media, tests and builder) and <code>{", ".join(since_other) or "nothing else"}</code>',
        "daily": vault("Sources/Daily Notes/Daily Note - Oct 20 2026", "Daily Note - Oct 20 2026") + ", # Simplify Aruco Studio (your voice note)",
        "project": vault("PROJECT - Aruco Studio", "PROJECT - Aruco Studio") + ": your earlier “keep this tight and focused”, linked to Unix design principles",
        "unix": vault("World Model/Chunks & Concepts/C - Unix Design Principles", "C - Unix Design Principles"),
        "dispatch": vault("World Model/Chunks & Concepts/C - Agent Dispatch Discipline (Serialize on Contracts, Not on Fear)",
                          "C - Agent Dispatch Discipline (Serialize on Contracts, Not on Fear)") + ": what a barrier is",
        "kpimem": vault("Settings/Memory/feedback_cad_feature_compute_time_kpi", "feedback_cad_feature_compute_time_kpi") + " (your words, 20 Oct night)",
        "b9": commit("5164a79", "contract barrier 9"),
        "profcore": commit("bb83df6", "the profile-first core"),
        "profui": commit("6fde285", "the profile-first UI"),
        "b10": commit("bef3fe6", "contract barrier 10"),
        "core3d": commit("a71d2a4", "the heights through the core"),
        "presets_py": '<code>aruco_studio/core/presets.py</code>, <code>driven_heights</code> (its docstring works the Aruco profile through); the built-in Default has <code>layer_mm</code> 0',
        "extrude_py": '<code>aruco_studio/web_extrude.py</code> (docstring: set values used exactly, the core refuses a colour with no height) and <code>aruco_studio/core/make.py</code> (<code>THICKNESS_MM = (0.05, 2.0)</code>, clamped with a warn)',
        "panelv1": commit("de89c9c", "the V1 Command Dialog") + "; its e2e, " + commit("4f20809"),
        "view3d": commit("a2bb41f", "the 2D | 3D toggle"),
        "pixel": commit("86ab903", "the top-view pixel test"),
        "view3dwhy": '<code>web/src/view3d/View3D.tsx</code>: the WHY comment quoting you',
        "sketchx": commit("ca01e4b", "the sketch tools"),
        "viewport": '<code>web/src/sketch/Viewport.tsx</code>: its header (right-button drag = selection box; a drag on a selected shape moves every selected one)',
        "survey": '<code>docs/design/sketch_tools_survey.md</code> (2026-10-17): about 40 projects checked; tldraw has no constraints and needs a licence key in production; planegcs (LGPL-2.1, FreeCAD\'s solver as WebAssembly) for later',
        "bench_code": '<code>web/scripts/bench-feature.mjs</code> (<code>npm run bench:feature</code>), ' + commit("35adf96") + "; " + commit(MAIN),
        "bench_data": f'the bench\'s own output, <code>~/.local/share/aruco_studio_bench/kpi/</code>: <code>kpi_series.jsonl</code> and <code>runs_table.jsonl</code>, the runs at {BENCH_T0[11:16]} and {BENCH_T[11:16]} UTC, 2026-10-20 ({b["n_runs"]} case runs in the second, each 1 cold + 30 warm calls)',
        "vt": f'<code>/home/bam/vibetracks</code>, branch <code>{VT_BRANCH}</code> (not merged); ' + vault("Sources/Notes/PROJECT - Vibe Tracks", "PROJECT - Vibe Tracks"),
        "landing": commit("fc2eae3", "the landing page") + ", merged in " + "<code>1d9a90f</code>",
        "recapture": commit(LANDING_RECAPTURE, "the landing recapture") + "; both section titles found on https://arucostudio.com/about/ when this report was built",
        "proposals": '<code>reports/media/panel-proposals-2026-10-20.html</code> (the panel proposals; V1 is the Command Dialog) and <code>3d-proposals-2026-10-20.html</code>',
        "shots_prof": f"{lanes} <code>os-profui</code> (<code>lane-profui/</code>): shot before the panel merged, so cropped to the canvas",
        "shots_panel": f"{lanes} <code>os-panelv1</code> (<code>lane-panelv1/</code>): the real core, the merged panel; <code>sbs-*.png</code> put the proposal and the build side by side",
        "shots_3d": f"{lanes} <code>os-view3d</code> (<code>lane-view3d/</code>): stills and <code>view3d-drag-type.webm</code>; shot before the panel merged, so cropped to the model",
        "shots_sketch": f"{lanes} <code>os-sketchx</code> (<code>lane-sketchx/</code>): stills and <code>marker-maker.webm</code>",
        "shots_kpi": "the Vibe Tracks app on the KPI branch, headless, after the second bench run (<code>kpi/aruco-studio-track-1280x800.png</code>)",
    }

    hero_s, hero_src = media["_hero_s"], media["_hero_src_s"]
    v3d_s = media["_v3d_s"]
    cut0, cut1 = HERO[1], HERO[2]

    body = f"""
<main>
<h1>ArUco Studio, the night of 20 Oct</h1>
<p class="meta">aruco-studio <code>main</code> @ <code>{head}</code>, pushed and live on <a href="https://arucostudio.com">arucostudio.com</a> · built {DATE} · click any image to enlarge</p>

<div class="verdict"><b class="v">ArUco Extrude is profile-first again, its panel is Fusion's flat dialog, 3D heights can be seen and dragged, and the sketch has real tools. All of it is live.</b>
<p class="qual"><span class="pill ok">on main · deployed</span> All on <code>main</code> @ <code>{head}</code>, pushed. Since then <code>main</code> has gained only the landing page's retaken shots (<code>{now_main}</code>), and that is what the live site runs {cite('git', 'live')}. Full e2e on merged main: <b>{E2E['passed']} passed, {E2E['skipped']} skipped</b> (the skips are the opt-in screenshot and video tests) {cite('brief')}.
<br><span class="pill warn">not merged</span> The compute-time KPI track is on a Vibetracks branch {cite('vt')}. <span class="pill warn">not yet</span> A 0 height is refused, and paper outside 0.05–2 mm is clamped {cite('extrude_py')}.</p></div>

<ol class="toc">
<li><a href="#s1"><b>Profile-only, like an extrude.</b></a> Click a region and the core places the marker. Double-click a rectangle and you place it.</li>
<li><a href="#s2"><b>The panel is the V1 Command Dialog.</b></a> Three flat tabs, Make | Marker | Label, and nothing folded away.</li>
<li><a href="#s3"><b>3D heights.</b></a> They are driven from the preset's layers (0.52 / 1.80 mm on the Aruco profile), and a typed value is used exactly.</li>
<li><a href="#s4"><b>2D | 3D toggle (key 3).</b></a> Fusion's Extrude arrows sit on the model: drag them or type a value.</li>
<li><a href="#s5"><b>Sketch tools.</b></a> Dimension (D), value boxes while drawing, window and crossing selection, copy and paste, and A on many rectangles at once.</li>
<li><a href="#s6"><b>Compute time is a KPI.</b></a> The slowest case takes {b['now']:.0f} ms against a 100 ms line, and rectangles take ≤ {b['rect_max']:.0f} ms. The track is <i>not merged</i>.</li>
<li><a href="#s7"><b>Landing page.</b></a> Download and Try Online buttons, and “Make markers where you CAD” leads.</li>
</ol>

<figure class="hero">{video(media, "hero", "The marker maker: draw four rectangles with typed sizes, select them, A, copy and paste")}
<figcaption><b>The marker maker, recorded live at real speed.</b>
<ol class="built" style="margin-top:4px">
<li>0–1 s: File → New.</li>
<li>1–4 s: <span class="kbd">R</span>, then type 20 and 15 into the value boxes, for each of four rectangles.</li>
<li>4.3 s: drag a selection window over them with the right button.</li>
<li>5 s: <span class="kbd">A</span> makes four markers, each with its own id.</li>
<li>6–8 s: Ctrl+C, Ctrl+V, and drag the copy aside.</li>
</ol>
This is {hero_s:.1f} s of a {hero_src:.1f} s take: the first {cut0:.1f} s (the example loading) and the last {hero_src - cut1:.1f} s (a still canvas) are cut. The take was recorded on the sketch-tools lane before the new panel merged, so the panel that flashes at 5 s is the old layout; section 2 shows the new one {cite('shots_sketch')}.</figcaption></figure>
<p class="note">Every still is a real capture from tonight's lanes. Where a lane was shot before the new panel merged, the still is cropped to the canvas.</p>

<h2 id="s1">1 · Profile-only, like an extrude <span class="pill">barrier 9</span></h2>
<p class="lead">There is one input again, a profile. Click a region and the core finds the place; double-click a rectangle and the place is yours.</p>
{quote("I prefer Unix tool philosophy, just like simple things. With kind of known happy paths and I do like it behaving a bit more like an extrude", cite('daily', 'project', 'unix'))}
<div class="media pair">
{fig(media, "p_face", "The plate face clicked: the marker sits in a dashed box between the two holes",
     f"<b>Click a region, then A.</b> The core puts the marker in the largest clear box, drawn dashed, here clear of both holes {cite('shots_prof', 'profcore')}.")}
{fig(media, "p_rect", "A 35 by 45 mm rectangle double-clicked: the marker sits inside its outline",
     f"<b>Double-click a rectangle.</b> Its outer edges become the profile, and the marker fills it. Drag the rectangle and the marker follows {cite('shots_prof', 'profui')}.")}
</div>
<div class="media pair">
{fig(media, "trim_profile", "Trim Profile: the whole plate is white", f"<b>Trim: Profile.</b> The sticker is the whole profile {cite('shots_prof')}.")}
{fig(media, "trim_marker", "Trim Marker: only the marker's square is white, the plate around it grey", f"<b>Trim: Marker.</b> The sticker is cut to the marker {cite('shots_prof')}.")}
</div>
<ul class="built">
<li>Trim is now Profile | Marker. Trim to rectangle is gone: to get it, draw a rectangle profile instead {cite('b9')}.</li>
<li>Old (v2) files still open: their rectangle becomes the profile {cite('profui')}.</li>
<li>Rectangle requests plan exactly as before (the core's pinned digests did not change) {cite('profcore')}.</li>
</ul>
<p class="def"><b>Barrier</b> here means a change to the shared UI ↔ core contract that lands alone, before the lanes that build on it. Tonight had two, 9 and 10 {cite('dispatch')}.</p>
<p class="try"><b>Try it:</b> Examples → Plate, click the plate, {kbd('A')}. Then draw a rectangle ({kbd('R')}), double-click it and press {kbd('A')}.</p>

<h2 id="s2">2 · The panel is the V1 Command Dialog</h2>
<p class="lead">This is Fusion's flat feature dialog: three tabs, nothing above them but the title, and no Advanced fold.</p>
<div class="media">{fig(media, "sbs_make", "Left the V1 proposal panel, right the built ArUco Extrude panel on the Make tab",
    f"<b>Left: the V1 proposal you picked</b>, drawn before profile-only, so it still has a Rectangle row and Trim to rectangle {cite('proposals')}. <b>Right: as built</b>, on the 3D Default preset {cite('shots_panel')}.", fit=True)}</div>
<div class="media three">
{fig(media, "tab_make", "The Make tab on the inkjet preset", f"<b>Make</b> (inkjet). Profile and Holes, Preset, Trim, Paper thickness, Flip {cite('shots_panel')}.")}
{fig(media, "tab_marker", "The Marker tab", f"<b>Marker.</b> Flat: Quiet zone and Key sit in the open {cite('shots_panel')}.")}
{fig(media, "tab_label", "The Label tab with Corner mark at its foot", f"<b>Label.</b> Place and Surface are new, and Corner mark moved here {cite('shots_panel', 'panelv1')}.")}
</div>
<div class="media">{fig(media, "presets", "The presets dialog: Inkjet and 3D print groups, with an Info pane",
    f"<b>The presets dialog lists presets by method:</b> Inkjet, then 3D print {cite('shots_panel', 'panelv1')}.")}</div>
<ul class="built">
<li>Make runs top to bottom: Profile (+ Holes), Preset, Trim, the method's heights, then Flip. Flip is on every profile and says which side faces out {cite('panelv1')}.</li>
<li>Inkjet shows Paper thickness. 3D shows Extrude Black | White | Both, White height and Black height “from the white's outer face” {cite('panelv1')}.</li>
<li>A new feature opens on Make. A feature you reopen keeps the tab you left it on {cite('panelv1')}.</li>
</ul>
<p class="try"><b>Try it:</b> click any marker. The panel opens beside it on Make.</p>

<h2 id="s3">3 · 3D heights, driven by the preset <span class="pill">barrier 10</span></h2>
<p class="lead">Leave a height alone and it comes from the preset's layers, shown grey. Type one and it is used exactly.</p>
<div class="media pair">
{fig(media, "h_driven", "3D model with arrows: white 2.00 mm and black 0.60 mm, both grey",
     f"<b>Driven:</b> 2.00 / 0.60 mm in grey. The Default preset has no layer heights, so it falls back to 0.6 / 2.0 {cite('shots_3d', 'core3d')}.")}
{fig(media, "h_set", "3D model with arrows: white 3.00 mm and black 1.20 mm, each with a reset mark",
     f"<b>Set:</b> 3.00 / 1.20 mm, in normal ink with ↺ to go back to driven {cite('shots_3d')}.")}
</div>
<div class="media pair">
{fig(media, "h_panel", "The Make tab's heights: Extrude Black, White height 2, Black height 0.6 from the white's outer face, Flip",
     f"<b>The same numbers in the Make tab</b>, grey because they are driven {cite('shots_panel')}.")}
{fig(media, "h_face_black", "Black only on a plate face: the black pattern goes 0.60 mm into the face beside a hole",
     f"<b>Black only on a face:</b> the part's own plastic is the white, and the black goes 0.60 mm into the face {cite('shots_3d', 'core3d')}.")}
</div>
<ul class="built">
<li><b>The rule:</b> each height is the first layer plus whole layers, the fewest that reach 0.5 mm for black and 1.8 mm for white. The Aruco profile has a 0.2 mm first layer and 0.32 mm layers: 0.2 + 1 × 0.32 = <b>0.52</b> and 0.2 + 5 × 0.32 = <b>1.80</b>. A preset with no layers, like Default, keeps the old 0.6 / 2.0 {cite('core3d', 'presets_py')}.</li>
<li>Black height is measured from the white's outer face, and Flip now applies on a face too {cite('b10', 'core3d')}.</li>
<li>Nothing old moved: requests without heights give byte-identical answers on all 121 parity cases {cite('core3d')}.</li>
</ul>
<p class="try"><b>Try it:</b> pick the 3D Default preset, then type a White height on Make. Click ↺ to go back.</p>

<h2 id="s4">4 · 2D | 3D toggle (key 3)</h2>
<p class="lead">Press {kbd('3')} to see every feature's planned layers as solids, with Fusion's Extrude arrows on the one you are editing.</p>
{quote("Show the extrusion dimensions directly on it! … Important though is to have the option to drag and also put in a custom value.", cite('view3dwhy'))}
<figure style="max-width:{media['v3d'][2]}px">{video(media, "v3d", "Dragging the white and black arrows in 3D, then typing 2.4 into the white's box")}
<figcaption><b>Drag, then type ({v3d_s:.1f} s, real speed, cropped to the model)</b> {cite('shots_3d', 'view3d')}.
<ol class="built" style="margin-top:4px">
<li>1–4 s: drag the white arrow from 2.00 to 5.25 mm. It snaps to whole layers.</li>
<li>5–6 s: drag the black arrow from 0.60 to 2.15 mm.</li>
<li>7–8 s: type 2.4 into the white's box, and it lands on exactly 2.40.</li>
</ol></figcaption></figure>
<div class="media pair">
{fig(media, "t_inkjet", "3D view of an inkjet marker: a 0.10 mm paper layer, the 2D 3D chip at top left",
     f"<b>Inkjet in 3D:</b> the paper is a single 0.10 mm layer, so it gets one arrow {cite('shots_3d')}.")}
{fig(media, "t_top", "The 3D view from straight above: marker 27 and its label, read the right way round",
     f"<b>The pixel test's view.</b> From straight above, the 3D view must be dark exactly where the plan has ink. Put a mirror in and the test fails {cite('shots_3d', 'pixel')}.")}
</div>
<ul class="built">
<li>The 2D | 3D chip sits at the canvas's top left, and {kbd('3')} flips it. The view is ported from the old Studio's three.js View3D and drawn at true scale {cite('view3d')}.</li>
<li>A drag is one undo step. In the value box, Enter commits and Esc cancels {cite('view3d', 'view3dwhy')}.</li>
</ul>
<p class="try"><b>Try it:</b> Examples → Custom placement, click the marker, press {kbd('3')}, then drag an arrow.</p>

<h2 id="s5">5 · Sketch tools</h2>
<p class="lead">This is what makes it “an ArUco marker maker on a canvas” (your words tonight) {cite('brief')}.</p>
<div class="media">{fig(media, "s_toolbar", "The toolbar: Select, Rectangle, Circle, Dimension (active), ArUco Extrude, Sheet, Verify, Fit",
    f"<b>Dimension (D) is a new tool</b> in the toolbar {cite('shots_sketch')}.")}</div>
<div class="media pair">
{fig(media, "s_boxes", "Drawing a rectangle: value boxes 30 and 20 on its edges",
     f"<b>Value boxes while you draw</b>, as in Fusion: type W, Tab, H, Enter. The old W × H corner box is gone {cite('shots_sketch', 'sketchx')}.")}
{fig(media, "s_dims", "A 40 by 25 mm rectangle with dimensions 40, 25 and 15 from the origin",
     f"<b>D: driving dimensions.</b> Type a value and the shape moves to it, and it stays locked there {cite('shots_sketch', 'sketchx')}.")}
</div>
<div class="media pair">
{fig(media, "s_window", "A solid blue window box over two rectangles: only those two selected",
     f"<b>Right-drag left → right: window.</b> It picks only shapes fully inside {cite('shots_sketch', 'viewport')}.")}
{fig(media, "s_crossing", "A dashed green crossing box touching three rectangles: all three selected",
     f"<b>Right-drag right → left: crossing.</b> It picks anything the box touches {cite('shots_sketch', 'viewport')}.")}
</div>
<div class="media"><figure style="max-width:{media['s_multi'][2]}px">{img(media, "s_multi", "Three markers, one in each rectangle, ids 2, 33 and 40")}
<div style="margin-top:6px;max-width:{media['s_multi_toast'][2]}px">{img(media, "s_multi_toast", "The toast: 3 ArUco Extrudes, one in each rectangle.")}</div>
<figcaption><b>A on several rectangles:</b> one marker each, each with its own id (#2, #33, #40). Below is the toast from the same capture {cite('shots_sketch')}.</figcaption></figure></div>
<ul class="built">
<li>Move or nudge many shapes at once, and Ctrl+C / X / V copies shapes together with their markers {cite('sketchx')}.</li>
<li><b>Hand-rolled for now.</b> The 17 Oct survey found tldraw has no dimension or constraint tool and needs a production licence key. Planegcs, FreeCAD's solver, is the stock part to use once lines and arcs need real constraints {cite('survey')}.</li>
</ul>
<p class="try"><b>Try it:</b> {kbd('R')}, type <code>30</code> Tab <code>20</code> Enter. Then {kbd('D')}, click an edge and type a value.</p>

<h2 id="s6">6 · Compute time is a KPI now <span class="pill warn">track not merged</span></h2>
<p class="lead">Faces are the slow case: {face_lo:.0f}–{b['now']:.0f} ms in the browser. Rectangles take {rect_hi:.0f} ms at most there, and ≤ {b['rect_max']:.0f} ms on every host.</p>
{quote("time to compute the feature in CAD. It's really frustrating when it takes a while... so performance matters.", cite('kpimem'))}
{chart(rows, False)}{chart(rows, True)}
<p class="note">Each bar is the browser's <b>warm p95</b>, the time 19 of 20 calls beat once the core is loaded. Each case uses the slower of its inkjet and 3D-print presets. Hover a bar for both {cite('bench_data')}.</p>
<details><summary>The table: every golden plan case on every host (warm p95, ms)</summary><div class="tbl"><table><thead><tr><th>Case</th><th>Profile</th><th>Preset</th>{"".join(f'<th class="n">{E(n)}</th>' for _, n in HOSTS)}</tr></thead><tbody>
{"".join(f'<tr><td>{E(lab)}</td><td>{"face" if kind == "face" else "rectangle"}</td><td>{"inkjet" if m == "inkjet" else "3D print"}</td>' + "".join(f'<td class="n">{b["cases"][(mt, lay, kind, m, "plan")][h]:.1f}</td>' for h, _ in HOSTS) + "</tr>" for mt, lay, lab in LAYOUTS for kind in ("face", "rectangle") for m in ("inkjet", "print3d"))}
</tbody></table></div></details>
<div class="media">{fig(media, "k_track", "The ArUco Studio track in Vibe Tracks: CAD feature compute time p95 151 ms, median 130 ms",
    f"<b>The new Vibe Tracks track:</b> p95 {b['now']:.0f} ms and median {b['p50']:.0f} ms, computed from the producer's runs and never typed in {cite('shots_kpi', 'vt')}.")}</div>
<ul class="built">
<li><b>The producer:</b> <code>npm run bench:feature</code> times the core's plan and svg calls on CPython, Pyodide in Node and the browser's worker. Golden cases: single, grid 3 × 1 and 3 × 3, ChArUco 5 × 4 and 8 × 2, each on a face and on a rectangle, inkjet and 3D {cite('bench_code')}.</li>
<li><b>Headline:</b> {b['now']:.0f} ms on the slowest case ({slow_name} on a face with holes, {"3D print" if slow_method == "print3d" else "inkjet"}), against a suggested 100 ms line. The first run read {b['then']:.0f} ms {cite('bench_data')}.</li>
<li><b>Startup:</b> loading Pyodide takes {st['browser'] / 1000:.1f} s in the browser and {st['pyodide-node'] / 1000:.1f} s in Node (medians); CPython takes {st['cpython']:.0f} ms {cite('bench_data')}.</li>
<li>The Fusion add-in is being instrumented, and its timings will join the same chart {cite('bench_code', 'brief')}.</li>
</ul>

<h2 id="s7">7 · Landing page</h2>
<p class="lead">It is live at <a href="https://arucostudio.com/about/">arucostudio.com/about/</a>. It is linked rather than pictured here: its own shots were retaken on the live site and merged while this report was built ({LANDING_RECAPTURE}) {cite('git')}.</p>
<ul class="built">
<li>The Download and Try Online buttons sit up top, the GitHub mark is in the top bar, and a #download section has one honest card per CAD program {cite('landing')}.</li>
<li>“Make markers where you CAD” leads the philosophy, and the copy is profile-first {cite('landing')}.</li>
<li>The recapture added two sections, “Heights on the model” and “A marker maker on a canvas”. Both are live now {cite('recapture')}.</li>
</ul>

<h2 id="decide">Done, left, and what needs you</h2>
<h3>Done and proved</h3>
<ul class="built">
<li>Full e2e on merged main: <b>{E2E['passed']} passed, {E2E['skipped']} skipped</b>. The skips are the opt-in screenshot and video tests {cite('brief')}.</li>
<li>Live: arucostudio.com serves <code>{now_main}</code>, which is <code>{head}</code> plus the landing recapture {cite('live', 'git')}.</li>
<li>Old work still behaves the same. Rectangle requests keep their pinned digests {cite('profcore')}. Requests without heights are byte-identical on all 121 parity cases {cite('core3d')}.</li>
<li>The 3D view is checked against the plan by a top-view pixel test that fails when a mirror is put in {cite('pixel')}.</li>
<li>The KPI numbers come from two bench runs written by the producer itself {cite('bench_data')}.</li>
</ul>
<h3>Left (next, not blocked)</h3>
<ul class="built">
<li>Editing several markers at once in the panel.</li>
<li>The README and design docs still say rectangle-first.</li>
<li>“Always honour set values” is not met for heights yet: a 0 height is refused, and paper outside 0.05–2 mm is clamped with a warning {cite('extrude_py')}.</li>
<li>Only one feature per profile.</li>
</ul>
<h3>Needs you</h3>
<div class="packet">
<div class="q"><h4>(a) Merge the Vibetracks KPI branch <code>{VT_BRANCH}</code>?</h4>
<p><b>Recommend yes.</b> It is the only place the compute-time numbers show as a track, and the Fusion timings will land on the same chart {cite('vt')}.</p>
<p class="dflt">If you say nothing: it stays on its branch, and the producer keeps writing its files.</p></div>
<div class="q"><h4>(b) Unblock the Fusion agent</h4>
<p>It is waiting for you on two things:</p>
<ul class="built">
<li>Close the ArUco Extrude dialog left open in Fusion.</li>
<li>Grant computer use, so it can record the CAD video for the landing page's Fusion slot.</li>
</ul>
<p><b>Recommend both</b> next time you are at the Windows box {cite('brief')}.</p>
<p class="dflt">If you say nothing: it keeps waiting, and the landing page's Fusion slot stays empty (it shows all or nothing) {cite('landing')}.</p></div>
<div class="q"><h4>(c) Google Search Console verification</h4>
<p>Unchanged: it needs your Google sign-in {cite('brief')}.</p>
<p class="dflt">If you say nothing: the site stays unverified there. Search engines can still crawl it.</p></div>
</div>
<h3>Deliberately not done</h3>
<ul class="built">
<li><b>No audit:</b> audits run only when you ask.</li>
<li><b>Editing several markers at once:</b> out of scope tonight.</li>
<li><b>In this report:</b> no landing stills (link only; the page carries its own fresh shots), and no Vibe Tracks drill-down (it was shot before the second run, so its 185 ms is stale).</li>
</ul>

<h2>Source Index</h2>
<ol class="sources">\x00INDEX\x00</ol>
</main>
<div id="zoom" role="dialog" aria-label="Enlarged image"><img alt=""></div>
<div id="tip" role="tooltip"></div>
"""
    order: list[str] = []
    for k in re.findall(r"\x00([a-z0-9_]+)\x00", body):
        if k not in order:
            order.append(k)
    missing = set(SOURCES) - set(order)
    assert not missing, f"sources never cited: {missing}"
    num = {k: i + 1 for i, k in enumerate(order)}
    body = re.sub(r"\x00([a-z0-9_]+)\x00", lambda m: f'<a href="#src{num[m.group(1)]}">{num[m.group(1)]}</a>', body)
    body = body.replace("\x00INDEX\x00", "".join(f'<li id="src{num[k]}">{SOURCES[k]}</li>' for k in order))
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>ArUco Studio night review</title>'
            f'<meta name="description" content="ArUco Studio, 20 Oct 2026 night: profile-first, the V1 panel, 3D heights and toggle, sketch tools, the compute-time KPI, the landing page.">'
            f'<style>{CSS}</style></head><body>{body}<script>{JS}</script></body></html>')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--src", type=Path, default=SRC, help="the lane captures (lane-*/, kpi/)")
    ap.add_argument("--bench", type=Path, default=BENCH, help="the bench's kpi/ output")
    ap.add_argument("--work", type=Path, default=WORK, help="the encoded media cache")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    out = build(a.src, a.bench, a.out, a.work)
    print(f"{out}  {out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
