#!/usr/bin/env python3
"""Build the review report for the night of 2026-10-20 (aruco-studio main @ 9c9bd36, then @ 6560fa3).

    python3 docs/build_night_report.py [--src DIR] [--bench DIR] [--fusion DIR] [--work DIR] [--out FILE]

Writes reports/media/aruco-studio-night-2026-10-20.html: one self-contained
page, every image and both videos inlined as data URIs (no server, no
network). reports/media/ is gitignored; this script is the reviewed source.
It follows docs/build_online_studio_report.py and docs/build_v1_report.py.

The page has two parts. "Later tonight" (main @ LATER: cloud files, the
Figma layout, multi-select, the preset per marker, panel polish, sizes, ids,
the scale bar, the 3D underside, the startup waits, Fusion's speed) comes
first with its own verdict; "Earlier tonight" (main @ MAIN, the first version
of this report) follows unchanged in substance. One report per night: a
later pass extends this page rather than starting a second one.

The later part's stills (LATER_STILLS) come from the same scratchpad:
live-*.png (the live hosted-files server), lane-figma2/, lane-figma/,
lane-polish/, lane-under/ (before/ and after/ are the lane's probe views),
lane-startup/ and kpi/fusion-before-after.png. Its Fusion chart is drawn
from the add-in's own timings (--fusion, ~/.local/share/aruco_studio_bench/
fusion: fusion_golden_20261020.jsonl and fusion_reid_20261020.jsonl).

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
from decimal import ROUND_HALF_UP, Decimal
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
FUSION = Path.home() / ".local/share/aruco_studio_bench/fusion"
FFMPEG, FFPROBE = "/usr/bin/ffmpeg", "/usr/bin/ffprobe"

LATER = "6560fa3"                # the later work as reviewed: main after the os-under merge (21:37)
MAIN = "9c9bd36"                 # the earlier work as first reviewed (pushed); then only the landing recapture
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

# Later tonight. Same rules: real captures, crops at native pixels unless a
# scale is named. WHY the panel-only crops in L5 and L10: those lanes were shot
# before the Figma layout merged, so their top bar is the old one.
LATER_STILLS = [
    # the lead still and L2 · the Figma layout (lane-figma2: the lane build, headless)
    ("l_menu", "lane-figma2/logo-menu-file-1184-dark.png", "null", 82),
    ("l_pill_before", "lane-figma2/before-1184-dark.png", "crop=336:58:9:22", 90),
    ("l_pill_after", "lane-figma2/1184-dark.png", "crop=336:58:9:22", 90),
    ("l_dock_before", "lane-figma2/before-1184-dark.png", "crop=380:58:402:731", 90),
    ("l_dock_after", "lane-figma2/1184-dark.png", "crop=380:58:402:731", 90),
    ("l_dock_light", "lane-figma2/dock-2d-studio-light.png", "null", 90),
    ("l_dock_fusion", "lane-figma2/dock-3d-fusion-dark.png", "null", 90),
    ("l_home_out", "lane-figma2/home-signed-out-1184-dark.png", "crop=1184:640:0:0", 80),
    ("l_390_menu", "lane-figma2/390-menu-file.png", "null", 82),
    ("l_390_home", "lane-figma2/390-home.png", "null", 82),
    # L1 · cloud files
    ("l_docmenu", "live-docmenu.png", "crop=705:220:5:22", 88),
    ("l_signin", "live-signin.png", "crop=352:214:464:293", 88),
    ("l_home_in", "lane-figma2/home-signed-in-1280-light.png", "crop=1010:320:0:0", 86),
    ("l_quota", "lane-figma2/home-signed-in-1280-light.png", "crop=204:46:9:746", 92),
    # L3 · multi-select
    ("l_ms", "lane-figma2/multiselect-chip-1184-dark.png", "crop=400:570:400:130", 86),
    # L4 · the preset per marker (lane-figma, the first Figma lane)
    ("l_print", "lane-figma/g-print-two-groups.png", "crop=880:350:51:25", 86),
    # L5 · panel polish (panel only; shot before the 0.5 mm sizes too)
    ("l_make", "lane-polish/tab-inkjet-make.png", "crop=320:517:880:125", 88),
    ("l_marker", "lane-polish/c-marker-groups.png", "crop=320:563:880:125", 88),
    ("l_reset", "lane-polish/b-reset-inside.png", "null", 92),
    ("l_rotate", "lane-polish/d-rotate-mid-drag.png", "crop=370:345:530:120", 88),
    # L9 · the 3D underside: the lane's probe view from below, 50 degrees off
    # and far out, before / after the fix, enlarged 2x (the sticker is ~90 px)
    ("l_under_before", "lane-under/before/x-inkjet-50-8.png", "crop=300:130:460:305,scale=600:-1:flags=lanczos", 88),
    ("l_under_after", "lane-under/after/x-inkjet-50-8.png", "crop=300:130:460:305,scale=600:-1:flags=lanczos", 88),
    ("l_under_top", "lane-under/top-view-turn0.png", "crop=610:615:280:110,scale=305:-1:flags=lanczos", 86),
    # L10 · the startup waits (the panel's lower half)
    ("l_wait", "lane-startup/a-waiting.png", "crop=320:235:950:250", 88),
    ("l_fail", "lane-startup/d-core-error.png", "crop=320:262:950:250", 88),
    ("l_busy", "lane-startup/e-still-planning.png", "crop=320:245:950:250", 88),
    # L11 · speed: the Vibe Tracks drill-down after the Fusion rows joined
    ("l_vt", "kpi/fusion-before-after.png", "crop=666:500:614:220", 86),
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
    for name, rel, vf, q in STILLS + LATER_STILLS:
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


# ------------------------------------------------------------------ Fusion's timings

FUSION_CASES = [("single", "Single marker"), ("grid3x1", "Grid 3 × 1"), ("grid3x3", "Grid 3 × 3"),
                ("charuco5x4", "ChArUco 5 × 4"), ("charuco8x2", "ChArUco 8 × 2")]
FUSION_KINDS = [("face/sticker", "sticker on a face"), ("profile/sticker", "sticker on a profile"),
                ("face/3d", "3D print on a face")]


def fusion(fdir: Path) -> dict:
    """Fusion's OK time per golden case (the execute op's ms_total) with the
    add-in's speed-ups off (run "before") and on ("after"), same add-in
    commit, and the Re-ID rows -- straight from the add-in's bam_cad_perf/1 lines."""
    rows = [json.loads(line) for line in (fdir / "fusion_golden_20261020.jsonl").read_text().splitlines() if line.strip()]
    ok: dict = {}
    for r in rows:
        if r["op"] == "execute":
            run_ = r["tags"]["run"].split(":")[0]
            assert run_ not in ok.get(r["tags"]["case"], {}), r["tags"]  # one OK per case and run
            ok.setdefault(r["tags"]["case"], {})[run_] = r["ms_total"]
    reid = [json.loads(line) for line in (fdir / "fusion_reid_20261020.jsonl").read_text().splitlines() if line.strip()]
    rb = [r["ms_total"] for r in reid if r["tags"]["run"] == "before"]
    ra = [r["ms_total"] for r in reid if r["tags"]["run"] == "after"]
    face = [(label, ok[f"{c}/face/sticker"]["before"], ok[f"{c}/face/sticker"]["after"]) for c, label in FUSION_CASES]
    best = max(face, key=lambda x: x[1] / x[2])
    return {"ok": ok, "face": face, "best": best, "n": len(rows), "add_in": sorted({r["commit"] for r in rows}),
            "reid_before": rb, "reid_after": ra, "reid_commits": (reid[0]["commit"], reid[-1]["commit"])}


def secs(ms: float) -> str:
    """Two decimals under a second (834.6 ms is 0.83 s), three figures above
    (30.6 s, 7.4 s, 1.29 s). WHY Decimal: half-up on the logged value, as a
    person rounds it, never on a float's binary approximation."""
    if ms < 1000:
        return f"{Decimal(str(ms)).scaleb(-3).quantize(Decimal('0.01'), ROUND_HALF_UP)} s"
    return f"{ms / 1000:.3g} s"


def fusion_chart(rows: list, narrow: bool) -> str:
    """Before / after bars per layout: Fusion's OK time for a sticker on a face."""
    vmax, ticks = 35.0, (0, 10, 20, 30)
    if narrow:
        W, x0, x1, top, row_h, bh = 360, 8, 300, 40, 64, 13
    else:
        W, x0, x1, top, row_h, bh = 880, 150, 800, 40, 50, 14
    sx = lambda s: x0 + (x1 - x0) * s / vmax
    out = [f'<g class="c-legend"><rect x="{x0}" y="8" width="12" height="12" rx="2" class="s0"/>'
           f'<text x="{x0 + 18}" y="18.5">Before (speed-ups off)</text>'
           f'<rect x="{x0 + (170 if narrow else 190)}" y="8" width="12" height="12" rx="2" class="s1"/>'
           f'<text x="{x0 + (188 if narrow else 208)}" y="18.5">After</text></g>']
    y_end = top + row_h * len(rows)
    for t in ticks:
        out.append(f'<line class="c-grid" x1="{sx(t):.1f}" x2="{sx(t):.1f}" y1="{top - 4}" y2="{y_end}"/>'
                   f'<text class="c-tick" x="{sx(t):.1f}" y="{y_end + 16}" text-anchor="middle">{t}</text>')
    out.append(f'<text class="c-tick" x="{x1 + (0 if narrow else 30)}" y="{y_end + 16}" '
               f'text-anchor="{"end" if narrow else "start"}">{"" if narrow else "s"}</text>')
    for i, (label, before, after) in enumerate(rows):
        y = top + i * row_h
        if narrow:
            out.append(f'<text class="c-lab" x="{x0}" y="{y + 10}">{E(label)}</text>')
            yb = y + 16
        else:
            out.append(f'<text class="c-lab" x="{x0 - 12}" y="{y + bh + 7}" text-anchor="end">{E(label)}</text>')
            yb = y + 6
        for j, (ms, cls, kind) in enumerate(((before, "s0", "before, speed-ups off"), (after, "s1", "after"))):
            yy = yb + j * (bh + 3)
            tip = f"{label}, sticker on a face, {kind}: Fusion OK in {secs(ms)} ({ms:,.0f} ms)"
            out.append(f'<path class="c-bar {cls}" d="{bar(x0, yy, max(sx(ms / 1000) - x0, 2.0), bh)}" '
                       f'data-tip="{E(tip)}" tabindex="0" aria-label="{E(tip)}"/>'
                       f'<text class="c-val" x="{max(sx(ms / 1000), x0 + 2) + 6:.1f}" y="{yy + bh - 3}">{secs(ms)}</text>')
    H = y_end + 26
    label = ("Bar chart: Fusion's OK time for an ArUco sticker on a face, before and after the add-in's speed-ups. "
             + "; ".join(f"{lab} {secs(b)} to {secs(a)}" for lab, b, a in rows) + ".")
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
.chart .s1{fill:var(--s1)}.chart .s2{fill:var(--s2)}.chart .s0{fill:var(--faint)}
h2.part{font-size:27px;line-height:1.25;margin:64px 0 6px;padding-top:22px;border-top:3px solid var(--fg)}
h2.part.first{margin-top:30px}
h2.part .when{display:block;font-size:14px;font-weight:500;color:var(--muted);margin-top:4px;letter-spacing:0}
.ba{font-size:12px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin:0 0 4px}
.ba.after{color:var(--ok)}.ba.before{color:var(--bad)}
.stack figure{margin:0 0 10px}
.sizes td.n b{color:var(--ok)}
.side{display:grid;grid-template-columns:minmax(0,400px) 1fr;gap:22px;align-items:start}.side figure{margin:0}
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
 h2.part{font-size:23px}
 .pair,.three,.side{grid-template-columns:1fr}
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


def build(src: Path, bdir: Path, fdir: Path, out: Path, work: Path) -> Path:
    media = encode(src, work)
    b = bench(bdir)
    rows = chart_rows(b)
    fu = fusion(fdir)
    head = MAIN
    # WHY pinned: the earlier part is about main up to the landing recapture,
    # which is what the live site ran when it was written; main has moved on
    # since (the later part), so "now" must not leak into the earlier claims.
    early_main = LANDING_RECAPTURE
    pushed = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", early_main, "origin/main"]).returncode == 0
    # WHY: say exactly what main gained after the reviewed commit, from git, not from memory
    since = git("diff", "--name-only", MAIN, early_main).splitlines()
    since_other = sorted({f for f in since if not f.startswith(("web/public/about/", "web/e2e/landing", "docs/build_landing"))})
    now_main = git("rev-parse", "--short", "main")
    origin_main = git("rev-parse", "--short", "origin/main")
    later_n = int(git("rev-list", "--count", f"{early_main}..{LATER}"))
    later_merges = int(git("rev-list", "--count", "--merges", f"{early_main}..{LATER}"))
    later_time = git("show", "-s", "--format=%ci", LATER)[11:16]
    fb_label, fb_before, fb_after = fu["best"]
    rb, ra = fu["reid_before"], fu["reid_after"]
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
        "git": f'<code>git log main</code> in <code>/home/bam/aruco-studio</code>: the earlier work ends at <code>{MAIN}</code>, then the landing recapture <code>{early_main}</code>, which is {"on" if pushed else "NOT on"} <code>origin/main</code> (as last fetched); <code>git diff --name-only {MAIN} {early_main}</code>: {len(since)} files, the landing page (its page, media, tests and builder) and <code>{", ".join(since_other) or "nothing else"}</code>',
        # ---- later tonight
        "brief2": "this update's brief from the dispatcher session (2026-10-20, about 22:00): the state of main and of the deploy, and numbers the lanes reported that this report did not re-measure (each is named where it is used)",
        "git2": f'<code>git log main</code>: the later work is {later_n} commits ({later_merges} of them merges) from <code>{early_main}</code> to <code>{LATER}</code> ({later_time} PDT); <code>main</code> is {"still" if now_main == LATER else "now"} <code>{now_main}</code>; <code>origin/main</code> was <code>{origin_main}</code> when last fetched (the rest goes out with the deploy)',
        "hosted": commit("f83813e", "the hosted-files merge") + "; " + commit("7ab5e86") + "; " + commit("1346fe8"),
        "shf": '<code>/home/bam/simple-hosted-files</code>: <code>server/apps.json</code> gives <code>aruco-studio</code> <code>"free": {"filesPerApp": 100}</code>, and <code>server/src/plans.ts</code> keeps the free plan at 3 files per app for every other app',
        "shots_live": "<code>live-docmenu.png</code> and <code>live-signin.png</code> in this session's scratchpad: the Studio against the live hosted-files server, signed out, shot before the logo menu took File / Edit / Export",
        "figma2": commit("c7ad1ce", "the logo menu and Home") + "; merged in <code>22a0e17</code>",
        "figmav2": commit("00c5582", "the Figma layout (V2) and the preset per marker") + "; merged in <code>e79a800</code>",
        "proposals2": "<code>reports/media/studio-layout-proposals-2026-10-20.html</code>: the five page layouts; you picked V2, Figma",
        "shots_figma2": "headless Playwright captures of the os-figma2 lane build (<code>lane-figma2/</code>): <code>before-1184-dark.png</code> is the first Figma build, before this lane",
        "home_spec": "<code>web/e2e/figma-menu.spec.ts</code>, test c: the cloud's answers are stubbed in the test (the cloud is another repo's server), so the files and the account in that shot are test data",
        "multisel": commit("4c5944d", "multi-select under real input"),
        "real_input": "<code>web/scripts/real-input-check.mjs</code>: its own invisible display (Xvfb), a real Chrome window on it, and xdotool moving the real pointer",
        "shots_figma1": "headless Playwright capture from the first Figma lane (<code>lane-figma/g-print-two-groups.png</code>)",
        "polish": commit("8afd478", "the panel polish") + "; " + commit("fadf337", "the rotate manipulator") + "; " + commit("91a0e63", "label off"),
        "shots_polish": "headless Playwright captures of the os-polish lane (<code>lane-polish/</code>): shot before the Figma layout and the 0.5 mm sizes merged, so cropped to the panel",
        "round": commit("7e669e5", "inkjet sizes on 0.5 mm") + ": your 3 × 1 at 29.9718 / 6.0113 mm",
        "sizestep": commit("1ea2540", "contract barrier 11") + "; " + commit("be61a17", "the Size step"),
        "legacy": commit("5d304da", "legacy_presets()") + ": 144 sha256 digests taken at <code>03594f9</code>, 144/144 identical after the size step; with dots instead, 1/144 (the check can fail)",
        "nextid": commit("c92f4ed", "ids count up") + "; merged in <code>1062ecc</code>",
        "reid": commit("812829e", "Re-ID is stateless") + "; merged in <code>638c19c</code>",
        "scalebar": commit("bca680c", "contract barrier 12") + "; " + commit("e3bd70e") + "; " + commit("732cee7"),
        "under": commit("7a78a63", "the 3D underside") + "; merged in <code>6560fa3</code> (from-below pixel tests, mutation-checked)",
        "shots_under": "the os-under lane's probe captures (<code>lane-under/before/</code> on the old code, <code>lane-under/after/</code> with the fix) and its e2e top view; the e2e's from-below tests check this kind of view, straight up and 50° off, on the merged code",
        "startup": commit("39be11f", "the startup retries and waits") + "; merged in <code>ba746a2</code>; the words shortened since by " + "<code>00c5582</code>",
        "shots_startup": "headless Playwright captures of the os-startup lane (<code>lane-startup/</code>), shot before the Figma layout: the panel's lower half",
        "fusion_data": f'the Fusion add-in\'s own timings, <code>~/.local/share/aruco_studio_bench/fusion/</code>: <code>fusion_golden_20261020.jsonl</code> ({fu["n"]} lines, <code>bam_cad_perf/1</code>, add-in commit <code>{", ".join(fu["add_in"])}</code>, “before” = its speed-ups switched off, “after” = on) and <code>fusion_reid_20261020.jsonl</code> (add-in <code>{fu["reid_commits"][0]}</code> → <code>{fu["reid_commits"][1]}</code>); loaded into the bench by ' + commit("1092ffb"),
        "shots_vt2": "the Vibe Tracks drill-down after the Fusion rows joined the KPI (<code>kpi/fusion-before-after.png</code>)",
        "vtmerge": "<code>/home/bam/vibetracks</code>: <code>6ca26f2</code>, “Merge claude/aruco-studio-kpi”, 2026-10-20 16:47 PDT",
        "picks": vault("Settings/Memory/project_aruco_studio", "project_aruco_studio") + " (the late-night picks: V2 Figma, the preset per marker, 100 free files)",
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
        "vt": f'<code>/home/bam/vibetracks</code>, branch <code>{VT_BRANCH}</code> (not merged then; merged since as <code>6ca26f2</code>); ' + vault("Sources/Notes/PROJECT - Vibe Tracks", "PROJECT - Vibe Tracks"),
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

    def ba(before: str, after: str, alt_b: str, alt_a: str, cap: str) -> str:
        """Before over after in one figure, each labelled."""
        return (f'<figure><p class="ba before">Before</p>{img(media, before, alt_b)}'
                f'<p class="ba after" style="margin-top:10px">After</p>{img(media, after, alt_a)}'
                f'<figcaption>{cap}</figcaption></figure>')

    ratio = fb_before / fb_after
    max_after = max(v["after"] for v in fu["ok"].values())
    reid_txt = f"{rb[0] / 1000:.1f} s → {min(ra) / 1000:.1f}–{max(ra) / 1000:.1f} s"
    f_ok = lambda case: fu["ok"][case]
    ftab = "".join(
        f'<tr><td>{E(lab)}</td><td>{E(kind)}</td><td class="n">{secs(f_ok(f"{c}/{k}")["before"])}</td>'
        f'<td class="n">{secs(f_ok(f"{c}/{k}")["after"])}</td>'
        f'<td class="n">{f_ok(f"{c}/{k}")["before"] / f_ok(f"{c}/{k}")["after"]:.1f}×</td></tr>'
        for k, kind in FUSION_KINDS for c, lab in FUSION_CASES)

    # ---------------------------------------------------------------- later tonight
    later = f"""
<h2 class="part first" id="later">Later tonight<span class="when">aruco-studio <code>main</code> @ <code>{LATER}</code> · {later_n} commits after the earlier part</span></h2>

<div class="verdict"><b class="v">Your files can live in the cloud now, the Studio wears Figma's layout, and multi-select works with a real mouse. Fusion builds a {E(fb_label)} sticker in {secs(fb_after)} instead of {secs(fb_before)}.</b>
<p class="qual"><span class="pill ok">on main · deployed</span> All eleven items below are on <code>main</code> @ <code>{LATER}</code> and live on arucostudio.com: the final full test run passed 148, 0 failed {cite('git2', 'brief2')}. The hosted-files server, with ArUco Studio's 100 free files, is already deployed {cite('shf', 'brief2')}.
<br><span class="pill">needs you</span> One Google sign-in on arucostudio.com once it deploys. The last step needs your own account {cite('brief2')}.</p></div>

<ol class="toc">
<li><a href="#l1"><b>Cloud files.</b></a> The document pill is the file's title bar, and ArUco Studio gets 100 free files. Signed out, everything stays on this device.</li>
<li><a href="#l2"><b>Figma's layout, your pick (V2).</b></a> One logo menu; Download for CAD, Verify and Print top right; the tool dock at the bottom; a Home view.</li>
<li><a href="#l3"><b>Multi-select, root-caused.</b></a> Two bugs that only a real mouse showed. Both are fixed, with an “N selected” chip.</li>
<li><a href="#l4"><b>A preset per marker.</b></a> New markers take the last one picked, and Print groups by preset.</li>
<li><a href="#l5"><b>Panel polish.</b></a> Label off by default, ↺ inside the field, grouped rows with icons, and a rotate handle.</li>
<li><a href="#l6"><b>Sizes land on 0.5 mm.</b></a> Your 3 × 1 went from 29.9718 / 6.0113 to 30.0 / 6.0 mm. Old Fusion records stay exact.</li>
<li><a href="#l7"><b>Ids just count up.</b></a> Paste #5 three times and you get #6, #7 and #8.</li>
<li><a href="#l8"><b>Print: Scale bar.</b></a> Hide, First page (the default) or Every page.</li>
<li><a href="#l9"><b>3D underside.</b></a> The ink no longer shows through the paper from below.</li>
<li><a href="#l10"><b>No stuck “Loading…”.</b></a> Startup retries, and every wait says what it waits for.</li>
<li><a href="#l11"><b>Speed.</b></a> Fusion's OK: {E(fb_label)} {secs(fb_before)} → {secs(fb_after)}. Re-ID of 12 markers: {reid_txt}.</li>
</ol>

<figure class="hero">{img(media, "l_menu", "The Studio's new chrome in dark: the logo menu open on File, two rectangles selected with a 2 selected chip, the tool dock at the bottom")}
<figcaption><b>The new chrome, on the lane build.</b> The logo opens one menu: Back to files, then File / Edit / Export / View / Preferences / Help. Top right: Download for CAD, Verify, Print. At the bottom: the tool dock ending in 2D | 3D, and ? and GitHub in the corner. The two rectangles carry the new “2 selected” chip {cite('shots_figma2', 'figma2')}.</figcaption></figure>
<p class="note">This part has no hero video: recording one needs the app running, and the final test run has the machine. Every still is a real capture. Stills shot before the Figma layout merged are cropped to the panel, and their captions say so.</p>

<h2 id="l1">1 · Cloud files, by Simple Hosted Files</h2>
<p class="lead">Sign in and your files live online, on any device. Signed out, nothing changes: everything stays in this browser.</p>
{quote("the aruco files themselves are so small… persist and access them from anywhere", cite('picks'))}
<div class="media">{fig(media, "l_docmenu", "The document pill's menu, signed out: Sign in to save online, then Theme and Skin",
    f"<b>Signed out, against the live server.</b> The name's ⌄ offers “Sign in to save online”. This was shot before the logo menu took File / Edit / Export and moved Theme and Skin into Preferences (section 2) {cite('shots_live')}.", fit=True)}</div>
<div class="media pair">
{fig(media, "l_signin", "The sign-in dialog: Create a free account to save your files online, Sign in with Google",
     f"<b>Sign in opens this dialog</b> against the live server, with no errors. The Google step itself needs your account {cite('shots_live', 'brief2')}.")}
<figure style="max-width:{media['l_quota'][2]}px">{img(media, "l_quota", "Account line: 2 of 100 free files in ArUco Studio")}
<figcaption><b>The account line</b> counts your files against the 100 free ones {cite('home_spec')}.</figcaption></figure>
</div>
<div class="media">{fig(media, "l_home_in", "Home signed in: Recents with New file, Bracket stickers edited 5 min ago, Sheet for the arm edited yesterday; Trash 1",
    f"<b>Signed in, Home lists your files</b> with their times, a search, New and the Trash. The cloud's answers are stubbed in this e2e, so these files are test data {cite('home_spec', 'figma2')}.")}</div>
<ul class="built">
<li>The document pill is the file's title bar: rename the file, the file menu, History, Download, and an account line “N of 100 free files” {cite('hosted')}.</li>
<li>ArUco Studio gets 100 free files, a per-app override on the hosted-files server. Every other app keeps the free plan's three {cite('shf', 'picks')}.</li>
<li>Signed out, everything is local, and a draft of the open file is kept in this browser {cite('hosted')}.</li>
<li>It is the stock Simple Hosted Files kit: its core and React hooks are copied verbatim, and a check keeps the copy in sync. Only the look is the Studio's {cite('hosted')}.</li>
</ul>

<h2 id="l2">2 · Figma's layout <span class="pill">your pick: V2</span></h2>
<p class="lead">The canvas gets the whole window. File, Edit and Export live in one menu behind the logo, as in Figma, and nothing on screen talks about Python. You picked this layout, V2, from five {cite('proposals2', 'picks')}.</p>
{quote("Figma doesn't have the file edit export etc there... it's in a drop down when you press the icon", cite('figma2'))}
<div class="media pair">
{ba("l_pill_before", "l_pill_after", "Before: logo, File, Edit, Export, Plate", "After: logo with a chevron, then Plate",
    f"<b>Top left.</b> File / Edit / Export were inline; now the logo's ⌄ holds them. The before is the first Figma build, earlier tonight {cite('shots_figma2', 'figma2')}.")}
{ba("l_dock_before", "l_dock_after", "Before: the dock with a clipped 2D button", "After: the dock with 2D and 3D whole",
    f"<b>The dock.</b> The 2D | 3D switch was clipped by the kit's control track; now it fits {cite('shots_figma2', 'figma2')}.")}
</div>
<div class="media pair">
{fig(media, "l_dock_light", "The dock in the light Studio skin, 2D on", f"<b>2D</b>, light, Studio skin (2× close-up) {cite('shots_figma2')}.")}
{fig(media, "l_dock_fusion", "The dock in the dark Fusion 360 skin, 3D on", f"<b>3D</b>, dark, Fusion 360 skin {cite('shots_figma2')}.")}
</div>
<div class="media">{fig(media, "l_home_out", "Home signed out: Sign in to save online, On this device with Plate, and the examples",
    f"<b>Back to files opens Home.</b> Signed out: Sign in, your work on this device, and the examples {cite('shots_figma2', 'figma2')}.")}</div>
<div class="media pair">
{fig(media, "l_390_menu", "On a 390 px phone: the logo menu as one list with File, Edit, Export, View and Preferences groups",
     f"<b>At 390 px</b> the submenus become groups in one list {cite('shots_figma2', 'figma2')}.", fit=True)}
{fig(media, "l_390_home", "On a 390 px phone: Home signed out", f"<b>Home at 390 px</b> {cite('shots_figma2')}.", fit=True)}
</div>
<ul class="built">
<li><b>The logo menu:</b> Back to files, then File / Edit / Export / View / Preferences / Help. Theme and Skin moved into Preferences, and there are no inline menus {cite('figma2')}.</li>
<li><b>Top right:</b> Download for CAD, then Verify and Print. Their keys (K, S) are in the tooltips, not on badges {cite('figmav2')}.</li>
<li><b>Bottom:</b> the tool dock, ending in 2D | 3D. ? (the keys and the startup status) and GitHub sit in the corner {cite('figmav2')}.</li>
<li><b>No “Python ready” chip.</b> A wait shows in plain words, and only inside the panel or dialog that is waiting {cite('figmav2', 'picks')}.</li>
<li><b>Home</b> (“Back to files”): signed in, your files, search, New and the Trash; signed out, Sign in, this device and the examples. The browser's Back returns to Home {cite('figma2')}.</li>
<li><b>The audit:</b> 4 widths (1184, 1280, 1440, 390 px) × 2 themes × 4 skins, 32 states: 0 overflows and 0 overlaps. It goes red on the old dock CSS, so it can fail {cite('figma2', 'brief2')}.</li>
<li>Opening a file now starts a fresh undo history, so Ctrl+Z never brings the previous document back {cite('figmav2')}.</li>
</ul>
<p class="try"><b>Try it:</b> click the logo, hover File. Then Back to files.</p>

<h2 id="l3">3 · Multi-select: the root cause</h2>
<p class="lead">Right-drag and Shift+click failed for you, yet passed every headless test. A real mouse found two separate bugs, and both are fixed.</p>
{quote("multi select by right click drag doesn't work, or by shift click", cite('multisel'))}
<div class="media side">{fig(media, "l_ms", "Two rectangles selected by a right-drag: orange outlines, their shared bounds, and a 2 selected chip",
    f"<b>A right-drag around two rectangles:</b> both selected, their shared bounds drawn, and the “2 selected” chip {cite('shots_figma2', 'multisel')}.", fit=True)}
<ul class="built" style="margin-top:0">
<li><b>(a) A fast release lost the box.</b> The pointer handlers read the drag from the last screen update. When a real hand let go right after its last move, the release saw a box that had not moved, and selected nothing. Now the handlers read the live drag, and the release point closes the box. The old code lost 2 of 10 real flicks; the fix loses 0 of 25 {cite('multisel')}.</li>
<li><b>(b) Shift+click inside a rectangle picked its region</b> (the fill), not the shape. Now Shift, Ctrl or Cmd + click toggles the shape under any part of it {cite('multisel')}.</li>
<li>Also new: a left-drag on empty canvas draws a box, as in Figma, and Shift+drag adds to the selection. Two quick Shift+clicks are no longer a double-click {cite('multisel')}.</li>
</ul></div>
<p class="def"><b>Real input</b> here means the operating system's own pointer, moved by xdotool on an invisible display (Xvfb) with a real Chrome window. Headless tests send made-up events that always arrive in perfect order, which is why they passed {cite('real_input')}.</p>
<p class="try"><b>Try it:</b> draw two rectangles, then right-drag around both, or Shift+click inside each.</p>

<h2 id="l4">4 · A preset per marker <span class="pill">file v4</span></h2>
<p class="lead">Each marker keeps its own preset. A new marker takes the one you picked last, and Print makes one group per preset.</p>
{quote("it's applied on a per marker basis", cite('picks'))}
<div class="media">{fig(media, "l_print", "The Print dialog with two tabs, Inkjet A4 vinyl and Inkjet Letter vinyl, and a note that 1 marker is 3D printed",
    f"<b>Print with two inkjet presets:</b> one tab each. The 3D-printed marker is left off the paper, and the dialog says so. Shot on the first Figma lane {cite('shots_figma1', 'figmav2')}.")}</div>
<ul class="built">
<li>Edit › Presets… sets the preset new markers start with. The Make tab, the 3D view, Verify and Export PDF all read each marker's own {cite('figmav2')}.</li>
<li>Version 3 files open with every marker given the preset it used {cite('figmav2')}.</li>
</ul>

<h2 id="l5">5 · Panel polish, from your Fusion notes</h2>
<p class="lead">The panel reads like Fusion's now: titled groups with an icon on each row, the reset inside the field, and a handle to rotate a rectangle profile.</p>
<div class="media pair">
{fig(media, "l_make", "The Make tab grouped: Where, How, Heights, Outward side", f"<b>Make:</b> Where, How, Heights, Outward side {cite('shots_polish', 'polish')}.", fit=True)}
{fig(media, "l_marker", "The Marker tab grouped: Marker, Size with Suggest first, Orientation, Border", f"<b>Marker:</b> Marker, Size (Suggest first), Orientation, Border {cite('shots_polish', 'polish')}.", fit=True)}
</div>
<div class="media pair">
{fig(media, "l_rotate", "Mid-drag on the rotate handle: the rectangle profile at 45 degrees, with an angle box reading 45",
     f"<b>Rotate a rectangle profile</b> mid-drag, at 45°, with the box to type an angle into {cite('shots_polish', 'polish')}.", fit=True)}
<figure style="max-width:{media['l_reset'][2]}px">{img(media, "l_reset", "The Marker size field reading 20, with the reset arrow inside it before the unit")}
<figcaption><b>↺ inside the field</b>, before the unit {cite('shots_polish')}.</figcaption></figure>
</div>
<p class="note">Shot on the polish lane before the Figma layout and the 0.5 mm sizes merged, so the panel is cropped, and its sizes are still the old ones (37.3377 mm) {cite('shots_polish')}.</p>
<ul class="built">
<li>Label is off by default. The sticker-sheet example turns its labels on {cite('polish')}.</li>
<li>↺ sits inside a set field: before the unit, in a toggle's last cell, before a drop-down's chevron. Empty a field and it is driven again {cite('polish')}.</li>
<li>Suggest comes first in Size {cite('polish')}.</li>
<li>The rotate handle turns a rectangle profile about its centre in 15° snaps (Shift for free), or you type the angle. Each rotation is one undo step, and a click still turns 90° {cite('polish')}.</li>
</ul>

<h2 id="l6">6 · Sizes land on round numbers <span class="pill">barrier 11</span></h2>
<p class="lead">Inkjet sizes the Studio works out now land on 0.5 mm, so the numbers you carry into CAD are ones you would type.</p>
{quote("we should by default recommend to the nearest like .5 mm", cite('round'))}
<div class="tbl"><table class="sizes"><thead><tr><th>Your 3 × 1 grid, inkjet</th><th class="n">Before</th><th class="n">Now</th></tr></thead><tbody>
<tr><td>Marker</td><td class="n">29.9718 mm</td><td class="n"><b>30.0 mm</b></td></tr>
<tr><td>Gap between markers</td><td class="n">6.0113 mm</td><td class="n"><b>6.0 mm</b></td></tr>
</tbody></table></div>
<p class="def"><b>Driven</b> sizes are the ones the Studio works out, shown grey. A size you type is <b>set</b>: it is used exactly as typed and never rounded.</p>
<ul class="built">
<li><b>Size step</b> is a new setting on the preset: Whole printer dots (exact), 0.1, 0.5 or 1 mm. Inkjet presets default to 0.5 mm, and a single marker can override it on its Make tab {cite('sizestep')}.</li>
<li><b>Why 0.5 mm is safe:</b> a 600 dpi printer puts ink on a 0.042 mm grid, so a 0.5 mm size lands at most half a dot (0.021 mm) off. That is 0.08 % of a 28 mm marker, the same order as a printer's own scale error or smaller {cite('round', 'brief2')}.</li>
<li><b>Old Fusion records stay exact.</b> <code>legacy_presets()</code> keeps the old preset objects that old records point to: 144 of 144 answers are byte-identical to the code before the change {cite('legacy')}.</li>
<li>3D-print presets are unchanged {cite('round')}.</li>
</ul>

<h2 id="l7">7 · Ids just count up</h2>
<p class="lead">A new marker takes the next free id after the highest one in use. Paste #5 three times and you get #6, #7 and #8.</p>
<ul class="built">
<li>Existing ids never move. A pasted copy of a typed id gets the next one, so #30 pastes as #31 {cite('nextid')}.</li>
<li>The old hashed ids stay available as an explicit choice {cite('nextid')}.</li>
<li><b>ArUco Re-ID is stateless:</b> the same markers get the same ids whatever ran before, and running it twice changes nothing more. A 300-trial property test checks both, and it fails when the code is broken on purpose {cite('reid')}.</li>
</ul>
<p class="def">A <b>property test</b> runs many random cases (here 300) and checks that a rule holds in every one.</p>

<h2 id="l8">8 · Print: Scale bar <span class="pill">barrier 12</span></h2>
<p class="lead">The Print dialog has a Scale bar row: Hide, First page (the default) or Every page. A page without the bar gives its space to stickers.</p>
<ul class="built">
<li>One scale check per print job is enough, so by default only page 1 keeps the 50 mm bar. It is the ruler at the top of the page in section 4's still {cite('scalebar')}.</li>
<li>Every page gives the old output, byte for byte {cite('scalebar')}.</li>
<li>The e2e reads every preview page for the bar {cite('scalebar')}.</li>
</ul>
<p class="try"><b>Try it:</b> Print ({kbd('S')}), then the Scale bar row.</p>

<h2 id="l9">9 · 3D: the underside no longer shows the ink</h2>
<p class="lead">From below, the marker's pattern showed through the paper. Now the underside is plain, and the view from above is unchanged.</p>
{quote("the aruco markers shouldn't be showing on the underside", cite('under'))}
<div class="media pair">
{ba("l_under_before", "l_under_after", "Before: from below, the black marker pattern shows through the sticker", "After: from below, the sticker is plain grey",
    f"<b>From below</b>, 50° off and far out, enlarged 2×. The pattern showed through; now the paper's underside is plain {cite('shots_under', 'under')}.")}
{fig(media, "l_under_top", "From straight above: the black marker pattern on the white sticker",
     f"<b>From straight above</b>, as before: the pattern exactly where the plan has ink. This is the pixel test's view {cite('shots_under', 'pixel')}.", fit=True)}
</div>
<ul class="built">
<li><b>Cause 1, a depth trick.</b> The ink was nudged toward the camera with a depth offset so it would win against the paper. That also let it win from below, through 0.05 mm of paper {cite('under', 'brief2')}.</li>
<li><b>Cause 2, a fixed near plane.</b> At sub-millimetre thickness, seen from a sheet's distance, the depth buffer could no longer tell the ink from the paper {cite('under')}.</li>
<li><b>The fix:</b> every body is carved as its true solid, its pockets cut out, so nothing needs the offset. The near plane moves out to half the distance to the model, so depth stays sharp there {cite('under')}.</li>
<li>Pixel tests from below, straight up and 50° off, cover inkjet, 3D Both, flipped and on a face. They fail when the fix is taken out {cite('under')}.</li>
</ul>
<p class="def"><b>Near plane:</b> the closest distance the 3D camera draws. The depth buffer, which decides what is in front, is sharpest near it, so a near plane far too close leaves little sharpness at the model.</p>

<h2 id="l10">10 · No more stuck “Loading…”</h2>
<p class="lead">The core's startup calls now retry, and every wait says what it is waiting for, with a way out.</p>
<div class="media three">
{fig(media, "l_wait", "Panel: Preset reads Starting Python, footer Starting Python, first load takes a few seconds, 7 s", f"<b>Waiting</b>, with a seconds counter {cite('shots_startup')}.")}
{fig(media, "l_fail", "Panel: The Python core failed to start, could not download, with a Reload button", f"<b>Failed:</b> the reason, and Reload {cite('shots_startup')}.")}
{fig(media, "l_busy", "Panel: Still planning, the core is busy, with a Retry button", f"<b>Busy:</b> Still planning, with Retry {cite('shots_startup')}.")}
</div>
<p class="note">Shot on the startup lane before the Figma layout, which has shortened the words since: “Starting up… N s”, and “Couldn't start” with Reload and the technical reason behind Details {cite('startup', 'figmav2')}.</p>
<ul class="built">
<li>The core's first calls (its facts and the presets) retry 3 times, then show a lasting error with Retry {cite('startup')}.</li>
<li>Sheet, Verify, Re-ID and Presets wait the same way {cite('startup')}.</li>
</ul>

<h2 id="l11">11 · Speed: Fusion up to {ratio:.0f}× faster</h2>
<p class="lead">Fusion's time from OK to a finished feature fell from as much as {secs(fb_before)} to at most {secs(max_after)} on every golden case, and the geometry did not change.</p>
{fusion_chart(fu["face"], False)}{fusion_chart(fu["face"], True)}
<p class="note"><b>Fusion's OK time:</b> from pressing OK in the ArUco Extrude dialog to the finished bodies. Each pair is the same add-in build with its speed-ups switched off, then on. Hover a bar for the milliseconds {cite('fusion_data')}.</p>
<details><summary>The table: all 15 golden cases in Fusion (OK time)</summary><div class="tbl"><table><thead><tr><th>Case</th><th>Make</th><th class="n">Before</th><th class="n">After</th><th class="n">Faster</th></tr></thead><tbody>
{ftab}
</tbody></table></div></details>
<div class="media">{fig(media, "l_vt", "Vibe Tracks drill-down: CAD feature compute time p95 by host: cpython 85.1 ms, pyodide-node 155 ms, browser 154 ms, fusion 1,570 ms",
    f"<b>The compute-time KPI in Vibe Tracks</b>, p95 by host: CPython 85 ms, browser 154 ms, Fusion 1,570 ms, Fusion's slowest golden case after the speed-ups {cite('shots_vt2', 'vtmerge')}.", fit=True)}</div>
<ul class="built">
<li><b>Fusion OK</b>, sticker on a face: ChArUco 8 × 2 {secs(f_ok("charuco8x2/face/sticker")["before"])} → {secs(f_ok("charuco8x2/face/sticker")["after"])}; grid 3 × 3 {secs(f_ok("grid3x3/face/sticker")["before"])} → {secs(f_ok("grid3x3/face/sticker")["after"])}; grid 3 × 1 {secs(f_ok("grid3x1/face/sticker")["before"])} → {secs(f_ok("grid3x1/face/sticker")["after"])} {cite('fusion_data')}.</li>
<li><b>Same geometry:</b> 45 of 45 geometry fingerprints (hashes of the built bodies) match before and after {cite('brief2')}.</li>
<li><b>Re-ID of 12 markers:</b> {reid_txt}. What is left is Fusion's own cost of editing a part, about 214 ms each. Going further means redesigning the custom feature: question (b) below {cite('fusion_data', 'brief2')}.</li>
<li>The Vibe Tracks track from the earlier part is merged into Vibe Tracks' main (16:47), so the earlier part's question (a) is settled {cite('vtmerge')}.</li>
</ul>

<h2 id="later-decide">Later tonight: done, left, and what needs you</h2>
<h3>Done and proved</h3>
<ul class="built">
<li>Multi-select under a real mouse: the old code lost 2 of 10 flicks, the fix 0 of 25 {cite('multisel', 'real_input')}.</li>
<li>The layout audit: 32 states, 0 overflows and 0 overlaps, and red on the old dock CSS {cite('figma2')}.</li>
<li>Old Fusion records: 144 of 144 answers byte-identical through <code>legacy_presets()</code> {cite('legacy')}.</li>
<li>Re-ID: stateless and idempotent (running it twice changes nothing more) over a 300-trial property test, mutation-checked {cite('reid')}.</li>
<li>The 3D underside: from-below pixel tests, mutation-checked {cite('under')}.</li>
<li>Fusion's speed: the add-in's own timings, and 45 of 45 geometry fingerprints unchanged {cite('fusion_data', 'brief2')}.</li>
<li>Not in this report: the final full test run on <code>main</code>. It is still running {cite('brief2')}.</li>
</ul>
<h3>Left (next, not blocked)</h3>
<ul class="built">
<li>Editing a preset updates only the open marker, not every marker that uses it.</li>
<li>Editing several markers at once in the panel.</li>
<li>The README and design docs are still rectangle-first.</li>
</ul>
<h3>Needs you</h3>
<div class="packet">
<div class="q"><h4>(a) One Google sign-in on arucostudio.com</h4>
<p>Sign-in reaches its dialog against the live server with no errors. The last step needs your own Google account {cite('brief2')}.</p>
<p>If Google shows <code>redirect_uri_mismatch</code>, add these two to your Google OAuth client:</p>
<ul class="built">
<li>Authorized redirect URI: <code>https://simple-hosted-files.zach-yamaoka.workers.dev/api/auth/callback/google</code></li>
<li>Authorized JavaScript origin: <code>https://simple-hosted-files.zach-yamaoka.workers.dev</code></li>
</ul>
<p><b>Recommend:</b> do it once the deploy lands.</p>
<p class="dflt">If you say nothing: cloud files stay unproven end to end. Everything works signed out, as before.</p></div>
<div class="q"><h4>(b) Redesign the Fusion custom feature for a faster Re-ID?</h4>
<p>Re-ID of 12 markers takes {min(ra) / 1000:.1f}–{max(ra) / 1000:.1f} s now, and nearly all of it is Fusion editing each part (about 214 ms a part). Only a different custom-feature design can cut that {cite('fusion_data', 'brief2')}.</p>
<p><b>Recommend yes if you Re-ID often.</b> If you rarely do, it is not worth the rework.</p>
<p class="dflt">If you say nothing: no redesign, and Re-ID stays at about 4 s for 12 markers.</p></div>
<div class="q"><h4>(c) Selection box: Figma's or Fusion's?</h4>
<p>Figma's box selects anything it touches. Ours keeps Fusion's two kinds: left to right picks only what is fully inside, right to left anything it touches {cite('viewport', 'multisel')}.</p>
<p><b>Recommend keeping Fusion's</b>, since Fusion is where the markers end up.</p>
<p class="dflt">If you say nothing: it stays as it is.</p></div>
</div>
<h3>Deliberately not done</h3>
<ul class="built">
<li><b>“Deployed” is not claimed.</b> The deploy waits for the final test run.</li>
<li><b>No hero video for this part, and no fresh captures.</b> Both need the app running while the final test run has the machine. Stills shot before the Figma layout are cropped and labelled instead.</li>
<li><b>No audit:</b> audits run only when you ask.</li>
</ul>
"""

    body = f"""
<main>
<h1>ArUco Studio, the night of 20 Oct</h1>
<p class="meta">aruco-studio <code>main</code> @ <code>{LATER}</code> · built {DATE}, extended late that night · <a href="#later">Later tonight</a> first, then <a href="#earlier">Earlier tonight</a> · click any image to enlarge</p>
{later}
<h2 class="part" id="earlier">Earlier tonight<span class="when">aruco-studio <code>main</code> @ <code>{head}</code>, pushed and live on <a href="https://arucostudio.com">arucostudio.com</a> · the first version of this report</span></h2>

<div class="verdict"><b class="v">ArUco Extrude is profile-first again, its panel is Fusion's flat dialog, 3D heights can be seen and dragged, and the sketch has real tools. All of it is live.</b>
<p class="qual"><span class="pill ok">on main · deployed</span> All on <code>main</code> @ <code>{head}</code>, pushed. After it came only the landing page's retaken shots (<code>{early_main}</code>), and that is what the live site ran when this part was written {cite('git', 'live')}. Full e2e on merged main: <b>{E2E['passed']} passed, {E2E['skipped']} skipped</b> (the skips are the opt-in screenshot and video tests) {cite('brief')}.
<br><span class="pill ok">merged since</span> The compute-time KPI track was on a Vibetracks branch {cite('vt')}; it merged at 16:47 {cite('vtmerge')}. <span class="pill warn">not yet</span> A 0 height is refused, and paper outside 0.05–2 mm is clamped {cite('extrude_py')}.</p></div>

<ol class="toc">
<li><a href="#s1"><b>Profile-only, like an extrude.</b></a> Click a region and the core places the marker. Double-click a rectangle and you place it.</li>
<li><a href="#s2"><b>The panel is the V1 Command Dialog.</b></a> Three flat tabs, Make | Marker | Label, and nothing folded away.</li>
<li><a href="#s3"><b>3D heights.</b></a> They are driven from the preset's layers (0.52 / 1.80 mm on the Aruco profile), and a typed value is used exactly.</li>
<li><a href="#s4"><b>2D | 3D toggle (key 3).</b></a> Fusion's Extrude arrows sit on the model: drag them or type a value.</li>
<li><a href="#s5"><b>Sketch tools.</b></a> Dimension (D), value boxes while drawing, window and crossing selection, copy and paste, and A on many rectangles at once.</li>
<li><a href="#s6"><b>Compute time is a KPI.</b></a> The slowest case takes {b['now']:.0f} ms against a 100 ms line, and rectangles take ≤ {b['rect_max']:.0f} ms. The track was <i>not merged</i> then; it is now.</li>
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

<h2 id="s6">6 · Compute time is a KPI now <span class="pill ok">track merged since</span></h2>
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

<h2 id="decide">Earlier tonight: done, left, and what needs you</h2>
<h3>Done and proved</h3>
<ul class="built">
<li>Full e2e on merged main: <b>{E2E['passed']} passed, {E2E['skipped']} skipped</b>. The skips are the opt-in screenshot and video tests {cite('brief')}.</li>
<li>Live when this part was written: arucostudio.com served <code>{early_main}</code>, which is <code>{head}</code> plus the landing recapture {cite('live', 'git')}.</li>
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
<p class="dflt">If you say nothing: it stays on its branch, and the producer keeps writing its files.</p>
<p><span class="pill ok">settled since</span> It was merged into Vibe Tracks' main at 16:47 (<code>6ca26f2</code>) {cite('vtmerge')}.</p></div>
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
            f'<meta name="description" content="ArUco Studio, 20 Oct 2026 night. Later: cloud files, the Figma layout, multi-select, a preset per marker, panel polish, sizes, ids, the scale bar, the 3D underside, startup waits, Fusion speed. Earlier: profile-first, the V1 panel, 3D heights and toggle, sketch tools, the compute-time KPI, the landing page.">'
            f'<style>{CSS}</style></head><body>{body}<script>{JS}</script></body></html>')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--src", type=Path, default=SRC, help="the lane captures (lane-*/, kpi/)")
    ap.add_argument("--bench", type=Path, default=BENCH, help="the bench's kpi/ output")
    ap.add_argument("--fusion", type=Path, default=FUSION, help="the Fusion add-in's timings (bam_cad_perf/1)")
    ap.add_argument("--work", type=Path, default=WORK, help="the encoded media cache")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    out = build(a.src, a.bench, a.fusion, a.out, a.work)
    print(f"{out}  {out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
