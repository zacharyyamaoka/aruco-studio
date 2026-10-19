#!/usr/bin/env python3
"""Build the review report for ArUco Studio V1 (the second round, 2026-10-18).

    python3 docs/build_v1_report.py [--renders] [--bench] [--suites-logs DIR]

Writes reports/media/aruco-studio-v1-2026-10-18.html: one self-contained
page, every image and the hero video inlined as data URIs (no server, no
network). reports/media/ is gitignored; this script is the reviewed source.
It follows docs/build_online_studio_report.py (the first round's report).

Standard library only; it shells out to ffmpeg / ffprobe for the media, and
(only for --renders / --bench) to git, the repo's .venv python and Google
Chrome (headless).

Its raw inputs live in reports/media/aruco-studio-v1-2026-10-18-src/ (gitignored):

  shots/*.png, shots/facts.json   the stills, from the LIVE site:
      (cd web && E2E_BASE_URL=https://arucostudio.com REPORT_SHOTS_DIR=<src>/shots \
          REPORT_PREVIEW_URL=http://127.0.0.1:5383 npx playwright test --project=e2e e2e/report.spec.ts)
      shots/sheet-request-plate.json is the Sheet dialog's own request for
      the plate (test 10); --renders replays it through CPython
  hero.webm, hero.marks.json      the V1 primary flow, from the LIVE site:
      (cd web && E2E_BASE_URL=https://arucostudio.com HERO_OUT=<src>/hero.webm \
          npx playwright test --project=hero)
  renders/                        --renders: the same requests through
      web_api at two commits (git archive, CPython): the sticker before / after
      73884a2, the inkjet lint before / after 7f84feb, Verify's view of a
      two-line label at 12f9f35
  bench-pack.json                 --bench: core.pack over the 200 seeded sets
      of tests/core/test_pack.py, both objectives, tight and spaced
  suites.json                     --suites-logs DIR: the counts parsed from
      the test logs (pytest, vitest, parity, Playwright) of the runs on a
      clean `git archive 12f9f35` (logs kept in <src>/logs)
  live-core.json                  every file of https://arucostudio.com/py/aruco_studio.zip
      against `git show <its _build.json stamp>:<path>`
  ref/*.png                       Zach's reference screenshots (~/zach_brain/Sources/Images)
  proposals/*.png                 two prototypes from ui-proposals-2026-10-18-src/shots

Every number on the page is read from facts.json, a log, git, or a file
named in its Source Index; the copy says which.
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
NAME = f"aruco-studio-v1-{DATE}"
SRC = ROOT / "reports" / "media" / f"{NAME}-src"
WORK = ROOT / "reports" / "media" / f"{NAME}-build"
OUT = ROOT / "reports" / "media" / f"{NAME}.html"
FFMPEG, FFPROBE = "/usr/bin/ffmpeg", "/usr/bin/ffprobe"
CHROME = "/usr/bin/google-chrome"
VENV_PY = ROOT / ".venv" / "bin" / "python"

MAIN = "12f9f35"          # main as reviewed (pushed); the live site is c2cf9b1 + this e2e-only commit
LIVE = "c2cf9b1"

HERO_SPEED = 1.6          # WHY: <= 20 s and still watchable (typing reads at 1.6x)
HERO_CRF = 26
HERO_W = 960


# ------------------------------------------------------------------ media

def run(cmd: list[str], **kw) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"failed: {' '.join(map(str, cmd))}\n{r.stderr[-2000:]}")
    return r.stdout


def dims(path: Path) -> tuple[int, int]:
    out = run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=width,height", "-of", "csv=p=0", str(path)])
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


def webp(src: Path, dst: Path, vf: str, quality: int, ss: float | None = None) -> Path:
    """One still as WebP through an ffmpeg filter chain (crop / scale); `ss`
    takes a frame from a video."""
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        pre = ["-ss", f"{ss:.2f}"] if ss is not None else []
        run([FFMPEG, "-y", "-v", "error", *pre, "-i", str(src), "-vf", vf, "-c:v", "libwebp",
             "-quality", str(quality), "-compression_level", "6", "-frames:v", "1", str(dst)])
    return dst


def hero_cut(marks: dict) -> list[tuple[float, float]]:
    """The kept spans of the raw recording (seconds), from the spec's marks:
    a glimpse of "Core loading...", then from the core being ready to the
    first "Loading OpenCV (13 MB)..." frames, then from the first verify
    image to just after the Tilt drag. WHY: the waits are network, not the
    flow; the caption says what was cut."""
    return [(0.6, 1.3),
            (marks["core_ready"] - 0.1, marks["verify_open"] + 0.6),
            (marks["verify_image"] - 0.2, marks["tilt_done"] + 0.8)]


def out_time(keep: list[tuple[float, float]], t: float) -> float:
    """A raw time -> its time in the cut, sped-up video."""
    acc = 0.0
    for a, b in keep:
        if t <= b:
            return (acc + max(0.0, t - a)) / HERO_SPEED
        acc += b - a
    return acc / HERO_SPEED


def hero(src: Path, work: Path, marks: dict) -> tuple[Path, Path, float, list]:
    keep = hero_cut(marks)
    poster_t = out_time(keep, marks["dim_set"] + 0.4)
    key = hashlib.sha1(f"{keep}|{HERO_SPEED}|{HERO_CRF}|{HERO_W}|{poster_t:.2f}".encode()).hexdigest()[:8]
    mp4, poster = work / f"hero-{key}.mp4", work / f"hero-poster-{key}.webp"
    if not mp4.exists() or mp4.stat().st_mtime < src.stat().st_mtime:
        parts = "".join(f"[0:v]trim={a:.2f}:{b:.2f},setpts=PTS-STARTPTS[p{i}];" for i, (a, b) in enumerate(keep))
        joined = "".join(f"[p{i}]" for i in range(len(keep)))
        fc = (parts + f"{joined}concat=n={len(keep)}:v=1:a=0,setpts=PTS/{HERO_SPEED},fps=25,"
              f"scale={HERO_W}:-2:flags=lanczos,format=yuv420p[v]")
        run([FFMPEG, "-y", "-v", "error", "-i", str(src), "-filter_complex", fc, "-map", "[v]",
             "-c:v", "libx264", "-profile:v", "high", "-preset", "veryslow", "-crf", str(HERO_CRF),
             "-tune", "animation", "-movflags", "+faststart", "-an", str(mp4)])
    if not poster.exists() or poster.stat().st_mtime < mp4.stat().st_mtime:
        run([FFMPEG, "-y", "-v", "error", "-ss", f"{poster_t:.2f}", "-i", str(mp4), "-frames:v", "1",
             "-c:v", "libwebp", "-quality", "70", str(poster)])
    dur = float(run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)]))
    return mp4, poster, dur, keep


# (name, source, ffmpeg filter, quality): every still and close-up on the page.
# Full screens are 2560 x 1600 (1280 x 800 at 2x); close-ups are 2x.
FULL = "scale=1100:-1:flags=lanczos"
# the Sheet dialog's page (at 1280 x 800: x 271..709, y 102..710)
SHEET = "crop=876:1216:543:205,scale=300:-1:flags=lanczos"
STILLS = [
    ("inspect", "shots/01-inspect.png", FULL, 74),
    ("two", "shots/06-two-markers.png", FULL, 72),
    ("verify", "shots/11-verify.png", "crop=2360:1502:100:49,scale=1100:-1:flags=lanczos", 74),
    ("presets", "shots/07b-presets-mine.png", "crop=2180:760:190:136,scale=1000:-1:flags=lanczos", 76),
    ("dark", "shots/12-dark.png", FULL, 70),
    ("mobile", "shots/13-mobile.png", "scale=390:-1:flags=lanczos", 80),
    ("sheets", "shots/09a-sheet-fewest-sheets.png", SHEET, 80),
    ("cuts", "shots/09b-sheet-fewest-cuts.png", SHEET, 80),
    ("tight", "shots/09e-sheet-tight.png", SHEET, 80),
    ("chip", "shots/15-preview.png", "crop=1100:100:1440:1500,scale=550:-1:flags=lanczos", 90),
    # close-ups (2x), kept sharp
    ("panel", "shots/01b-panel.png", "scale=330:-1:flags=lanczos", 88),
    ("toolbar", "shots/01c-toolbar.png", "scale=676:-1:flags=lanczos", 90),
    ("mark", "shots/01d-topbar-left.png", "scale=236:-1:flags=lanczos", 92),
    ("dims_driven", "shots/02-dims-driven.png", "scale=380:-1:flags=lanczos", 86),
    ("dims_set", "shots/02b-dims-set.png", "scale=380:-1:flags=lanczos", 86),
    ("rows_driven", "shots/02c-rows-driven.png", "crop=iw:ih-20:0:10,scale=440:-1:flags=lanczos", 90),
    ("rows_set", "shots/02d-rows-set.png", "crop=iw:ih-20:0:10,scale=440:-1:flags=lanczos", 90),
    ("label_tab", "shots/03-label-tab.png", "scale=440:-1:flags=lanczos", 90),
    ("label_inkjet", "shots/03b-label-inkjet.png", "scale=360:-1:flags=lanczos", 86),
    ("label_pixel", "shots/03c-label-pixel.png", "scale=360:-1:flags=lanczos", 86),
    ("charuco_corner", "shots/04a-charuco-corner.png", "scale=360:-1:flags=lanczos", 86),
    ("charuco_square", "shots/04b-charuco-square.png", "scale=360:-1:flags=lanczos", 86),
    ("origin_rows", "shots/04c-origin-rows.png", "crop=iw:ih-20:0:10,scale=440:-1:flags=lanczos", 90),
    ("suggest", "shots/05-suggest-open.png", "scale=400:-1:flags=lanczos", 88),
    ("id_driven", "shots/06a-id-driven.png", "crop=iw:ih-20:0:10,scale=440:-1:flags=lanczos", 90),
    ("id_clash", "shots/06b-id-clash.png", "crop=iw:ih-20:0:10,scale=440:-1:flags=lanczos", 90),
    ("id_key", "shots/06c-key.png", "crop=iw:ih-20:0:10,scale=413:-1:flags=lanczos", 90),
    ("cad", "shots/08-cad-menu.png", "scale=464:-1:flags=lanczos", 90),
    ("sweep", "shots/11b-sweep.png", "scale=420:-1:flags=lanczos", 90),
    ("calc", "shots/11c-calc.png", "scale=452:-1:flags=lanczos", 90),
    ("sticker", "shots/10b-sticker.png", "crop=500:792:20:0,scale=220:-1:flags=lanczos", 88),
    ("preset_row", "shots/14-preset-row.png", "scale=440:-1:flags=lanczos", 90),
    ("sheet_side", "shots/09d-sheet-side.png", "crop=600:570:0:0,scale=300:-1:flags=lanczos", 90),
    # CPython renders (--renders)
    ("sticker_before", "renders/sticker-before.png", "scale=300:-1:flags=lanczos", 88),
    ("sticker_after", "renders/sticker-after.png", "scale=300:-1:flags=lanczos", 88),
    ("verify_ml_cpython", "renders/verify-multiline.png", "crop=488:420:0:20,scale=300:-1:flags=lanczos", 88),
    # the two prototypes Zach picked from
    ("proto_v1", "proposals/s-v1-select-light.png", "scale=560:-1:flags=lanczos", 76),
    ("proto_v2", "proposals/s-v2-set-light.png", "scale=560:-1:flags=lanczos", 76),
    # Zach's references (his pasted screenshots)
    ("ref_toolbar", "ref/20261018142350.png", "scale=300:-1:flags=lanczos", 86),
    ("ref_timeline", "ref/20261018142402.png", "scale=300:-1:flags=lanczos", 86),
    ("ref_label", "ref/20261018142755.png", "scale=440:-1:flags=lanczos", 80),
    ("ref_suggest", "ref/20261018142917.png", "scale=300:-1:flags=lanczos", 86),
    ("ref_offset", "ref/20261018162421.png", "scale=159:-1", 90),
    ("ref_sweep", "ref/20261018162558.png", "scale=480:-1:flags=lanczos", 76),
]


def encode(src: Path, work: Path) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    media = {}
    for name, rel, vf, q in STILLS:
        # WHY the key: a changed crop or quality must re-encode, not reuse the cache
        key = hashlib.sha1(f"{rel}|{vf}|{q}".encode()).hexdigest()[:8]
        p = webp(src / rel, work / f"{name}-{key}.webp", vf, q)
        media[name] = (p, "image/webp", *dims(p))
    marks = json.loads((src / "hero.marks.json").read_text())
    mp4, poster, dur, keep = hero(src / "hero.webm", work, marks)
    media["hero"] = (mp4, "video/mp4", *dims(mp4))
    media["hero_poster"] = (poster, "image/webp", *dims(poster))
    media["_hero"] = {"s": dur, "keep": keep, "marks": marks}
    # the live Verify bench drawing the two-line label (a frame of the raw recording)
    vf = "crop=810:640:64:70,scale=360:-1:flags=lanczos"
    key = hashlib.sha1(f"verify-ml|{vf}|{marks['verify_image']}".encode()).hexdigest()[:8]
    p = webp(src / "hero.webm", work / f"verify_ml_live-{key}.webp", vf, 86, ss=marks["verify_image"] + 1.2)
    media["verify_ml_live"] = (p, "image/webp", *dims(p))
    og = ROOT / "web" / "public" / "og.png"
    p = webp(og, work / "og.webp", "scale=600:-1:flags=lanczos", 80)
    media["og"] = (p, "image/webp", *dims(p))
    return media


# ------------------------------------------------------------------ CPython renders

def archive(rev: str, dest: Path) -> Path:
    tar = subprocess.run(["git", "-C", str(ROOT), "archive", rev, "aruco_studio"], capture_output=True, check=True).stdout
    tarfile.open(fileobj=io.BytesIO(tar)).extractall(dest, filter="data")
    return dest


STICKER_REQ = r"""
import json, re, sys
sys.path.insert(0, sys.argv[1])
from aruco_studio import web_api as W
req = json.load(open(sys.argv[2]))
it = req["items"][0]
plan = W.plan(it)
page = W.sheet(req, "2026-10-18")["svg"][0]
texts = [(float(x), float(y), float(f), t) for x, y, f, t in
         re.findall(r'<text x="([\d.]+)" y="([\d.]+)"[^>]*font-size="([\d.]+)"[^>]*>([^<]*)</text>', page)
         if t == plan["label"]["text"]]
cut = re.findall(r'data-cut="[^"]*"[^>]*d="M([\d.]+) ([\d.]+) L([\d.]+) ([\d.]+) L([\d.]+) ([\d.]+)', page)[0]
r, lab = it["rect"], plan["label"]
page = re.sub(r"<svg\b[^>]*>", '<svg xmlns="http://www.w3.org/2000/svg" width="560" height="800" '
              'viewBox="0 0 70 100" style="background:#fff">', page, count=1)
open(sys.argv[3], "w").write(page)
print(json.dumps({
    "cut_mm": [float(c) for c in cut], "label_text": lab["text"], "label_font_mm": texts[0][2] if texts else None,
    "label_baseline_page_y": texts[0][1] if texts else None,
    # the plan's label centre (sketch, y up) less half its cap height = its baseline
    "plan_baseline_above_rect_bottom_mm": round(lab["at"][1] - lab["height_mm"] / 2 - (r["cy"] - r["h"] / 2), 4),
    "plan_label_at": lab["at"], "cap_mm": lab["height_mm"], "outer_mm": plan.get("outer_mm")}))
"""

LINT_REQ = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from aruco_studio import web_api as W
base = json.load(open(sys.argv[2]))["items"][0]
# tests/web/test_web_api.py test_an_inkjet_marker_is_not_linted_for_an_fdm_nozzle's request, on the plate's inkjet preset
r = dict(base, rect={"cx": 0, "cy": 0, "w": 90, "h": 40, "angle_deg": 0},
         marker=dict(base["marker"], type="grid", cols=5, rows=4, auto=False, marker_mm=5.8, first_id=0))
p = W.plan(r)
print(json.dumps({"preset": r["preset"]["name"], "warnings": [w["text"] for w in p["warnings"]]}))
"""

VERIFY_REQ = r"""
import base64, json, sys
sys.path.insert(0, sys.argv[1])
import cv2
from aruco_studio import web_verify as V
req = json.load(open(sys.argv[2]))["items"][0]
req = dict(req, label=dict(req["label"], text="PLATE\n#{ids}"))
view = {"camera": {"resolution": [1280, 960], "distance_mm": 400, "hfov_deg": 60},
        "tilt_deg": 0, "yaw_deg": 0, "blur_px": 0, "noise": 0, "glare": 0, "occlusion": 0, "seed": 0}
out = V.verify(req, view)
open(sys.argv[3], "wb").write(base64.b64decode(out["image_png_base64"]))
print(json.dumps({"opencv": cv2.__version__, "found": out["found"], "ok": out["ok"]}))
"""


def chrome_png(svg: Path, png: Path, size: tuple[int, int], tmp: Path) -> None:
    run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={tmp / 'chrome'}",
         f"--screenshot={png}", f"--window-size={size[0]},{size[1]}", svg.as_uri()])


def renders(src: Path) -> dict:
    """The plate's sticker before (73884a2^) and after (MAIN) the label fix,
    the inkjet lint before (7f84feb^) and after (MAIN), and Verify's view of
    a two-line label (MAIN, CPython's OpenCV): the Sheet dialog's own request."""
    out_dir = src / "renders"
    out_dir.mkdir(parents=True, exist_ok=True)
    req = src / "shots" / "sheet-request-plate.json"
    out: dict = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        trees = {}
        for rev in ("73884a2^", "7f84feb^", MAIN):
            trees[rev] = archive(rev, tmp / rev.replace("^", "-parent"))
        for tag, rev in (("before", "73884a2^"), ("after", MAIN)):
            svg = tmp / f"sticker-{tag}.svg"
            got = json.loads(run([str(VENV_PY), "-c", STICKER_REQ, str(trees[rev]), str(req), str(svg)]))
            chrome_png(svg, out_dir / f"sticker-{tag}.png", (560, 800), tmp)
            out[f"sticker_{tag}"] = {"rev": rev, **got}
        for tag, rev in (("before", "7f84feb^"), ("after", MAIN)):
            out[f"lint_{tag}"] = {"rev": rev, **json.loads(run([str(VENV_PY), "-c", LINT_REQ, str(trees[rev]), str(req)]))}
        out["verify_multiline"] = {"rev": MAIN, **json.loads(run(
            [str(VENV_PY), "-c", VERIFY_REQ, str(trees[MAIN]), str(req), str(out_dir / "verify-multiline.png")]))}
    (out_dir / "renders.json").write_text(json.dumps(out, indent=2))
    return out


# ------------------------------------------------------------------ the packer benchmark

BENCH = r"""
import json, statistics, sys, multiprocessing as mp
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[1] + "/tests/core")
import test_pack as T

def one(seed):
    page, its = T.random_set(seed)
    row = {"seed": seed, "n": len(its), "page": page}
    for mode in ("tight", "spaced"):
        s = T.lay(its, mode, page)
        c = T.lay(its, mode, page, objective="fewest_cuts")
        sh = T.lay(its, mode, page, packer="shelf")
        row[mode] = {"sheets": [s.page_count, s.cuts()], "cuts": [c.page_count, c.cuts()],
                     "shelf": [sh.page_count, T.page_cuts(sh)], "sheets_fill": s.fill(), "shelf_fill": sh.fill()}
    return row

if __name__ == "__main__":
    with mp.Pool(12) as p:
        rows = p.map(one, range(200))
    out = {}
    for mode in ("tight", "spaced"):
        r = [x[mode] for x in rows]
        med = lambda k, i: statistics.median(x[k][i] for x in r)
        out[mode] = {
            "fewest_sheets": {"median_pages": med("sheets", 0), "median_cuts": med("sheets", 1), "pages_sum": sum(x["sheets"][0] for x in r)},
            "fewest_cuts": {"median_pages": med("cuts", 0), "median_cuts": med("cuts", 1), "pages_sum": sum(x["cuts"][0] for x in r)},
            "shelf": {"median_pages": med("shelf", 0), "median_cuts": med("shelf", 1), "pages_sum": sum(x["shelf"][0] for x in r)},
            "cuts_fewer": sum(1 for x in r if x["cuts"][1] < x["sheets"][1]),
            "cuts_more_pages": sum(1 for x in r if x["cuts"][0] > x["sheets"][0]),
            "mean_fill_guillotine": statistics.mean(x["sheets_fill"] for x in r),
            "mean_fill_shelf": statistics.mean(x["shelf_fill"] for x in r),
        }
    json.dump({"sets": 200, "summary": out, "rows": rows}, open(sys.argv[2], "w"), indent=1)
"""


def bench(src: Path) -> None:
    """core.pack on the 200 seeded sets of tests/core/test_pack.py (its own
    random_set / lay), at MAIN: both objectives, tight and spaced, and the
    old shelf packer as the baseline."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        tar = subprocess.run(["git", "-C", str(ROOT), "archive", MAIN, "aruco_studio", "tests"],
                             capture_output=True, check=True).stdout
        tarfile.open(fileobj=io.BytesIO(tar)).extractall(tmp, filter="data")
        run([str(VENV_PY), "-c", BENCH, str(tmp), str(src / "bench-pack.json")], cwd=tmp,
            env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})


# ------------------------------------------------------------------ the test logs

def suites_from_logs(logs: Path) -> dict:
    """The summary line of each log -> counts (pytest, vitest, parity, Playwright)."""
    def text(name: str) -> str:
        p = logs / name
        return p.read_text(errors="replace") if p.exists() else ""

    def pytest(name: str) -> dict:
        t = text(name)
        line = [s for s in t.splitlines() if re.search(r"\d+ passed", s) and " in " in s]
        got = {k: int(v) for v, k in re.findall(r"(\d+) (passed|failed|skipped)", line[-1])} if line else {}
        took = re.search(r" in ([\d.]+)s", line[-1]).group(1) if line else ""
        fails = sorted({re.sub(r"\[.*", "", s.split()[1]) for s in t.splitlines() if s.startswith("FAILED ")})
        return {**got, "seconds": float(took) if took else None, "failed_tests": fails,
                "failed_ids": [s.split()[1].split(" - ")[0] for s in t.splitlines() if s.startswith("FAILED ")]}

    def pw(name: str) -> dict:
        t = text(name)
        got = {k: int(v) for v, k in re.findall(r"^\s+(\d+) (passed|failed|skipped|flaky)", t, re.M)}
        took = re.search(r"\d+ passed \(([^)]+)\)", t)
        return {**got, "took": took.group(1) if took else None}

    par = re.search(r"parity: (\d+) / (\d+) byte-identical \(Pyodide (\d+) ms, CPython (\d+) ms", text("parity.log"))
    vt = re.search(r"Tests\s+(\d+) passed \((\d+)\)", text("vitest.log"))
    vf = re.search(r"Test Files\s+(\d+) passed", text("vitest.log"))
    return {
        "rev": MAIN, "web": pytest("py-web.log"), "scene": pytest("py-scene.log"), "verify": pytest("py-verify.log"),
        "core": pytest("py-core.log"), "plan": pytest("py-plan.log"),
        "vitest": {"passed": int(vt.group(1)) if vt else None, "files": int(vf.group(1)) if vf else None},
        "parity": {"same": int(par.group(1)), "of": int(par.group(2)), "pyodide_ms": int(par.group(3)),
                   "cpython_ms": int(par.group(4))} if par else None,
        "e2e_local": pw("e2e-local.log"), "e2e_live": pw("e2e-live.log"), "e2e_live2": pw("e2e-live2.log"),
        "report_live": pw("report-run.log"), "hero_live": pw("hero-run.log"),
        "e2e_rerun": pw("e2e-features-a.log"),
    }


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
    c = f' class="{cls}"' if cls else ""
    return f'<figure{c}>{img(media, name, alt)}<figcaption>{cap}</figcaption></figure>'


def quote(text: str, where: str, ref: str) -> str:
    return f'<blockquote><p>{E(text)}</p><cite>you, <i>{E(where)}</i> {ref}</cite></blockquote>'


def git(*args: str) -> str:
    return run(["git", "-C", str(ROOT), *args]).strip()


def diff_html(text: str) -> str:
    rows = []
    for line in text.splitlines():
        cls = "add" if line.startswith("+") and not line.startswith("+++") else \
              "del" if line.startswith("-") and not line.startswith("---") else \
              "hunk" if line.startswith("@@") else ""
        rows.append(f'<span class="{cls}">{E(line)}</span>' if cls else E(line))
    return '<pre class="diff">' + "\n".join(rows) + "</pre>"


# ------------------------------------------------------------------ the diagram

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


def diagram(narrow: bool, ncalls: int) -> str:
    """The seam at MAIN: UI -> frozen contract -> Pyodide worker -> the core,
    and inscribe() one step above plan(), sheet() over every plan. Two
    layouts (wide / phone), same boxes; a character budget per line,
    checked by eye in the rendered page at 1280 and 390 px."""
    layers = [
        ("ui", "The screen · web/src", "sketch + typed dimensions · ArUco Extrude panel · presets · Sheet · Verify"),
        ("contract", "web/src/core/contract.ts · frozen between barriers",
         "info · presets · inscribe · plan · suggest · svg · sheet · verify · readable · assign_ids"),
        ("worker", "Web Worker · Pyodide 314.0.7, self-hosted",
         "web_api.py · web_ids.py · web_verify.py (numpy + OpenCV 4.11 fetched on the first verify)"),
        ("core", "The core · aruco_studio core / plan / scene / verify",
         "stdlib Python (pack, autoid, rect_fill, sheet …): the package the Fusion add-in uses"),
    ]
    links = [f"CoreApi: {ncalls} calls, JSON in / out", "postMessage", "import"]
    pipe = [("Profile", "a face: its outline and its holes"), ("Rect", "cx, cy, w, h, angle (mm)"),
            ("MarkerPlan", "black, outline, label inside, dims, issues"), ("Sheet", "pages, straight cuts, fill")]
    pipe_links = ["inscribe(profile, Avoid | Ignore)", "plan(rect, marker, label, preset)", "sheet(every plan) → core.pack"]
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
        out.append(f'<text class="d-h" x="{x0}" y="{y}">Where inscribe and sheet sit</text>')
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
        W, x0, bw, gap, tch, sch = 960, 20, 520, 46, 56, 66
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
        out.append(f'<text class="d-h" x="{px}" y="24">Where inscribe and sheet sit</text>')
        for i, (t_, s) in enumerate(pipe):
            g, h = box(px, py, pw, t_, s, "pipe", 34, 40)
            out.append(g)
            if i < len(pipe_links):
                out.append(arrow(px + 26, py + h, py + h + 44, pipe_links[i]))
            py += h + 44
        out.append(quote_svg(px, py - 44 + 30, ["“the input to this algorithim is always just", "a rectangle”: inscribe is one step above"]))
        H = max(H, py - 44 + 64)
    label = ("Diagram: the screen calls the frozen contract, which posts JSON to a Pyodide worker running "
             "web_api.py on the core. A profile goes through inscribe to a rectangle; plan takes only the "
             "rectangle; sheet packs every plan onto pages.")
    return (f'<svg class="diagram {"narrow" if narrow else "wide"}" viewBox="0 0 {W} {H:.0f}" role="img" '
            f'aria-label="{E(label)}">{"".join(out)}</svg>')


def logo_tiles(icon: str, icon2d: str) -> str:
    """The cube at 128 / 64 / 32 / 16 px on a light and a dark tile, and the
    flat 2D spare at 64 / 32 / 16: the files as shipped (web/public)."""
    def inline(svg: str, px: int) -> str:
        return svg.replace("<svg ", f'<svg width="{px}" height="{px}" aria-hidden="true" ', 1)
    sizes = (128, 64, 32, 16)
    cube = "".join(f'<span class="lt">{inline(icon, s)}<i>{s}</i></span>' for s in sizes)
    flat = "".join(f'<span class="lt">{inline(icon2d, s)}<i>{s}</i></span>' for s in (64, 32, 16))
    # WHY the 2D spare on light only: the file is black-only; recolouring it
    # for a dark tile would show something that was not shipped
    return (f'<div class="logos"><div class="lrow light">{cube}</div><div class="lrow dark">{cube}</div></div>'
            f'<div class="logos"><div class="lrow light">{flat}<span class="lt cap">2D spare (black only)</span></div></div>')


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
h4{font-size:15px;margin:22px 0 8px}
p{margin:0 0 12px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
code{font:13.5px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--code);padding:1px 5px;border-radius:4px}
sup{font-size:11px;color:var(--faint);margin-left:1px}sup a{color:var(--faint)}
.meta{color:var(--muted);font-size:14px;margin-bottom:22px}
.verdict{border:1px solid var(--line);background:var(--panel);border-radius:10px;padding:16px 18px;margin:18px 0 26px}
.verdict b.v{font-size:18px;line-height:1.45;display:block;margin-bottom:8px}
.verdict .qual{color:var(--muted);font-size:15px}
.verdict ul{margin:8px 0 0;font-size:15px;color:var(--muted)}
.pill{display:inline-block;font-size:12.5px;font-weight:600;padding:1px 8px;border-radius:999px;background:var(--chip);color:var(--muted);margin-right:6px;white-space:nowrap}
.pill.ok{background:var(--ok-bg);color:var(--ok)}.pill.warn{background:var(--warn-bg);color:var(--warn)}.pill.bad{background:var(--bad-bg);color:var(--bad)}
figure{margin:0 0 14px}
figure img,video{display:block;max-width:100%;height:auto;border:1px solid var(--line);border-radius:8px;background:var(--panel)}
figure.wide img{width:100%}
img[data-zoom]{cursor:zoom-in}
figcaption{font-size:13.5px;color:var(--muted);margin-top:6px;line-height:1.5}
.hero video{width:100%;box-shadow:var(--shadow)}
.try{border:1px solid var(--accent);background:var(--accent-bg);border-radius:10px;padding:14px 18px;margin:16px 0 0}
.try ol{margin:6px 0 0;padding-left:22px}.try li{margin:2px 0}
.kbd{font:12.5px ui-monospace,monospace;border:1px solid var(--line);border-bottom-width:2px;border-radius:4px;padding:0 5px;background:var(--bg)}
.item{margin:0 0 30px;padding:0 0 26px;border-bottom:1px dashed var(--line)}
.item:last-child{border-bottom:0}
.item h3{margin-top:0}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}
.pair.r21{grid-template-columns:2fr 1fr}.pair.r12{grid-template-columns:1fr 2fr}.pair.three{grid-template-columns:1fr 1fr 1fr}
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
.bug{border-left:3px solid var(--bad);background:var(--bad-bg);padding:8px 12px;border-radius:0 8px 8px 0;font-size:14.5px;margin:10px 0 0}
.tbl{width:100%;overflow-x:auto;margin:10px 0 16px}
table{border-collapse:collapse;width:100%;font-size:14.5px;line-height:1.45}
th,td{text-align:left;vertical-align:top;padding:8px 10px;border-bottom:1px solid var(--line)}
th{font-size:12.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600}
td.n,th.n{white-space:nowrap;font-variant-numeric:tabular-nums;text-align:right}
td.h{white-space:nowrap}
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
.waves{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:10px 0 14px}
.wave{border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:var(--panel);font-size:14px}
.wave h4{margin:0 0 4px;font-size:14px}
.wave .b{color:var(--warn);font-size:12.5px;margin-bottom:6px}
.wave ul{margin:4px 0 0;padding-left:18px}.wave li{margin:2px 0}
.wave .m{color:var(--muted);font-size:12.5px;margin-top:6px}
.q{border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:0 0 12px;background:var(--bg)}
.q h4{margin:0 0 6px;font-size:16px}
.q .rec,.q .def{font-size:14.5px;margin:4px 0 0}
.q .def{color:var(--muted)}
.q ol{margin:6px 0 0}
details{border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:10px 0;background:var(--panel)}
summary{cursor:pointer;font-size:14.5px;color:var(--muted)}
pre.diff{font:12.5px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;overflow-x:auto;margin:8px 0 0;padding:10px;background:var(--bg);border-radius:6px;border:1px solid var(--line);white-space:pre}
pre.diff .add{color:var(--ok)}pre.diff .del{color:var(--bad)}pre.diff .hunk{color:var(--accent)}
.logos{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 10px}
.lrow{display:flex;align-items:flex-end;gap:14px;padding:12px 14px;border-radius:10px;border:1px solid var(--line)}
.lrow.light{background:#f4f5f7}.lrow.dark{background:#1d1f23;border-color:#2e3034}
.lt{display:flex;flex-direction:column;align-items:center;gap:4px}
.lt i{font:11px ui-monospace,monospace;font-style:normal;color:#8a9099}
.lt.cap{font-size:12px;color:#8a9099;align-self:center}
.sources{font-size:13.5px;color:var(--muted)}.sources li{margin:3px 0}
#zoom{position:fixed;inset:0;background:rgba(0,0,0,.82);display:none;align-items:center;justify-content:center;z-index:10;cursor:zoom-out;padding:16px}
#zoom img{max-width:100%;max-height:100%;border-radius:6px;background:#fff}
#zoom.on{display:flex}
@media (max-width:700px){
 main{padding:24px 16px 60px}
 h1{font-size:24px}
 h2{font-size:20px;margin-top:44px}
 .pair,.pair.r21,.pair.r12,.pair.three{grid-template-columns:1fr}
 .waves{grid-template-columns:1fr}
 .diagram.wide{display:none}.diagram.narrow{display:block}
 table{font-size:13.5px}th,td{padding:7px 6px}
 table.stack thead{display:none}table.stack tr{display:block;border-bottom:1px solid var(--line);padding:10px 0}
 table.stack td{display:block;border:0;padding:3px 0;text-align:left}table.stack td:first-child{font-weight:600;font-size:15px}
 table.stack td:not(:first-child)::before{content:attr(data-label);display:block;font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--faint)}
}
"""

JS = r"""
(function(){var z=document.getElementById('zoom'),zi=z.querySelector('img');
document.addEventListener('click',function(e){var t=e.target;
if(t.matches&&t.matches('img[data-zoom]')){zi.src=t.src;zi.alt=t.alt;z.classList.add('on');}
else if(z.classList.contains('on')&&(t===z||t===zi)){z.classList.remove('on');zi.removeAttribute('src');}});
document.addEventListener('keydown',function(e){if(e.key==='Escape'){z.classList.remove('on');}});})();
"""


def build(src: Path, out: Path, work: Path) -> Path:
    facts = json.loads((src / "shots" / "facts.json").read_text())
    rend = json.loads((src / "renders" / "renders.json").read_text())
    bp = json.loads((src / "bench-pack.json").read_text())["summary"]
    su = json.loads((src / "suites.json").read_text())
    live = json.loads((src / "live-core.json").read_text())
    media = encode(src, work)
    hero_s, keep, marks = media["_hero"]["s"], media["_hero"]["keep"], media["_hero"]["marks"]
    raw_s = float(run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src / "hero.webm")]))
    head = git("rev-parse", "--short", "HEAD")
    contract = git("show", f"{MAIN}:web/src/core/contract.ts")
    api = re.search(r"export interface CoreApi \{(.*?)\n\}", contract, re.S).group(1)
    ncalls = len(re.findall(r"^\s+(\w+)\(", api, re.M))
    icon = git("show", f"{MAIN}:web/public/icon.svg")
    icon2d = git("show", f"{MAIN}:web/public/icon-2d.svg")
    d_flaky = git("show", MAIN, "--format=", "-U1", "--", "web/e2e/features.spec.ts")
    d_stable = git("show", "a497385", "--format=", "-U0", "--", "stable-preview.json")
    d_dims = git("show", "0b93cd8", "--format=", "-U1", "--", "web/e2e/dims.spec.ts")
    d_lint = git("show", "7f84feb", "--format=", "-U1", "--", "aruco_studio/plan/plan.py")
    stat_fix = git("show", "--stat", "--format=", "73884a2")
    merge_tree = git("merge-tree", "--write-tree", "b1864d5^1", "b1864d5^2").splitlines()[0]
    logo_tree = git("rev-parse", "b1864d5^{tree}")
    fsck = subprocess.run(["git", "-C", str(ROOT), "fsck", "--no-dangling"], capture_output=True, text=True)
    repair_dir = Path.home() / ".local/state/aruco-studio-git-repair-2026-10-18/.git/objects"
    kept = sorted(p.parent.name + p.name for p in repair_dir.rglob("*") if p.is_file()) if repair_dir.exists() else []
    kept_empty = sum(1 for p in repair_dir.rglob("*") if p.is_file() and p.stat().st_size == 0) if repair_dir.exists() else 0
    kept_now = [o for o in kept if subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", o]).returncode == 0]
    origin_main = git("rev-parse", "--short", "origin/main")
    since = git("log", "--format=%h\t%s", f"{MAIN}..HEAD").splitlines()
    merges = git("log", "--merges", "--format=%h", f"{MAIN}..HEAD").splitlines()
    head_merge = f"<code>{merges[0]}</code>" if merges else "not yet"

    # Citations: a placeholder per source key now; numbered in order of first
    # appearance on the finished page, then the Source Index.
    def cite(*keys: str) -> str:
        for k in keys:
            assert k in SOURCES, k
        return "<sup>" + ",".join(f"\x00{k}\x00" for k in keys) + "</sup>"

    vault = "obsidian://open?vault=zach_brain&file=PROJECT%20-%20Aruco%20Studio"
    SOURCES = {
        "vault": f'<a href="{vault}">PROJECT - Aruco Studio</a> (your note: # Oct 18 2026, ## Auto layout, ## Verify Accuracy, ## Auto id, #### Mini CAD, ### Good defaults)',
        "facts": '<code>web/e2e/report.spec.ts</code> on https://arucostudio.com, 2026-10-18 18:22–18:23 (test 6 re-shot 18:37): 15 / 15, the stills and their measurements (<code>facts.json</code>)',
        "hero": f'<code>web/e2e/hero.spec.ts</code> (project <code>hero</code>) on https://arucostudio.com, 2026-10-18 18:26: {raw_s:.1f} s raw, step times in <code>hero.marks.json</code>',
        "live_zip": f'<code>https://arucostudio.com/py/aruco_studio.zip</code>, fetched 2026-10-18 18:28: <code>_build.json</code> says <code>{live["stamp"]}</code>; each file compared with <code>git show {live["stamp"]}:&lt;path&gt;</code>',
        "git": f'<code>git log</code> / <code>git show</code> in <code>/home/bam/aruco-studio</code>; <code>origin/main</code> = <code>{origin_main}</code> at the last fetch',
        "pack": '<code>aruco_studio/core/pack.py</code>: the guillotine packer, its prior art and objectives (docstring)',
        "testpack": '<code>tests/core/test_pack.py</code>: the 200 seeded random sets, the validity oracle, the objective test',
        "bench": f'this report\'s re-run of the benchmark (<code>--bench</code>): <code>core.pack</code> on those 200 sets at <code>{MAIN}</code>, 2026-10-18 18:23',
        "sheetspec": '<code>web/e2e/sheet.spec.ts</code>: the eight-sticker document, each objective\'s numbers checked against CPython\'s <code>web_api.sheet</code>',
        "webverify": '<code>aruco_studio/web_verify.py</code>: <code>verify</code>, <code>readable</code> and the measured thresholds (<code>FIELD_SHARE</code>, the WHY comment)',
        "verifyspec": '<code>web/e2e/verify.spec.ts</code>: the dialog, Tilt re-rendering while dragged, the sweep, the calculator against <code>core.readable</code>',
        "pyodide": '<code>web/node_modules/pyodide/pyodide-lock.json</code>: <code>opencv-python 4.11.0.86</code>; the repo\'s <code>.venv</code>: <code>cv2 5.0.0</code>',
        "autoid": '<code>aruco_studio/core/autoid.py</code>: the key, sha256, the ledger, typed ids, the 62 % birthday figure (docstring)',
        "renders": f'this report\'s CPython replays (<code>--renders</code>) of the Sheet dialog\'s own plate request at <code>73884a2^</code>, <code>7f84feb^</code> and <code>{MAIN}</code> (<code>git archive</code>)',
        "c73884a2": 'commit <code>73884a2</code>: "Integrate layout + plan2": the whole rectangle is the sticker, the label keeps white from the cut line',
        "c7f84feb": 'commit <code>7f84feb</code>: a sticker is not linted for an FDM nozzle',
        "ca497385": 'commit <code>a497385</code>: keep <code>aruco_studio/verify</code> in the Stable snapshot',
        "c0b93cd8": 'commit <code>0b93cd8</code>: the dims e2e reads the plan\'s auto id',
        "c12f9f35": f'commit <code>{MAIN}</code>: the features e2e types an id that differs from the auto id',
        "ced5e15e": 'commit <code>ed5e15e</code> (18:17): contract barrier 4, "the Fusion adapter\'s N-6 asks", its message',
        "barriers": 'commits <code>ebc46a5</code> (14:21), <code>56235bd</code> (14:43), <code>184f107</code> (16:39): the contract barriers; lane bases from <code>git merge-base</code> of each merge\'s parents',
        "logo": 'commit <code>facc33e</code> (the logo lane) and <code>reports/media/logo-v18-picks-2026-10-18.html</code>: the eight top faces and the decodability check',
        "live_head": '<code>curl https://arucostudio.com/</code>, 18:28: <code>&lt;link rel="icon" href="/favicon.svg"&gt;</code> and <code>og:image</code> = <code>/og.png</code> (1200 × 630)',
        "sps": '<code>stable-preview.json</code> (ports 5382 / 5383) and <code>~/.local/share/applications/aruco-studio.desktop</code> (its three right-click actions)',
        "gallery": '<a href="ui-proposals-2026-10-18.html">ui-proposals-2026-10-18.html</a>: the five clickable proposals (same folder as this page)',
        "contract": f'<code>web/src/core/contract.ts</code> at <code>{MAIN}</code>: <code>CoreApi</code>, {ncalls} calls',
        "runs_head": '<code>tests/web</code>, vitest, <code>npm run test:parity</code> and the local Playwright e2e on a clean <code>git archive</code> of <code>main</code> at its newer head, 2026-10-18 18:42–18:48 (logs in <code>{NAME}-src/logs-head/</code>)'.replace("{NAME}", NAME),
        "runs": f'test runs re-done for this report on a clean <code>git archive {MAIN}</code>, 2026-10-18 18:18–18:40 (logs kept in <code>{NAME}-src/logs/</code>)',
        "repair": '<code>~/.local/state/aruco-studio-git-repair-2026-10-18/.git/objects/</code> (the kept objects), <code>git fsck --no-dangling</code> and <code>git merge-tree --write-tree</code>, re-run 2026-10-18',
        "design": '<code>docs/design/online_studio_v1.md</code>: the v1 spec, "Many features, driven vs set, no timeline"',
    }

    def pair(a: str, b: str, ratio: str = "") -> str:
        return f'<div class="pair {ratio}">{a}{b}</div>'

    F = facts
    ins, dm, lab, lpx, ch = F["inspect"], F["dims"], F["label"], F["label_pixel"], F["charuco"]
    aid, sh, st, vf, mob = F["autoid"], F["sheet"], F["sticker"], F["verify"], F["mobile"]
    ready = sorted(F["core_ready_s"])
    dm_b = {d["field"]: d for d in dm["before"]}
    dm_a = {d["field"]: d for d in dm["after"]}
    sa, sb = rend["sticker_after"], rend["sticker_before"]
    lint_b = [w for w in rend["lint_before"]["warnings"] if "nozzle" in w]
    lint_a = [w for w in rend["lint_after"]["warnings"] if "nozzle" in w]
    cellmin = [w for w in rend["lint_after"]["warnings"] if w.startswith("cell minimum")]
    ap = F.get("autoid_panel")
    o0 = [float(v) for v in ch["origin_corner"].split(",")]
    o1 = [float(v) for v in ch["origin_square"].split(",")]
    moved = ((o1[0] - o0[0]) ** 2 + (o1[1] - o0[1]) ** 2) ** 0.5
    T, S_ = bp["tight"], bp["spaced"]
    hd = su.get("head")
    head_note = ((f". On <code>{E(hd['rev'])}</code> the local e2e gave {hd['e2e_local'].get('passed')} passed and "
                  f"{hd['e2e_local'].get('failed', 0)} failed, an intermittent one that passed {hd['e2e_rerun'].get('passed')} times on re-run (Proof): "
                  f"worth one look before you promote") if hd and hd['e2e_local'].get('failed') else
                 (f"; on <code>{E(hd['rev'])}</code> the local e2e passed too" if hd else f"; it has not been re-run on <code>{head}</code>"))

    items = []

    # ---------------------------------------------------------------- auto layout
    items.append(f"""
<div class="item" id="layout"><h3>1 · Auto layout: Tight | Spaced, and Optimize: Fewest cuts | Fewest sheets</h3>
<div class="media"><div class="pair three">
    {fig(media, "sheets", "The Sheet dialog's page, eight stickers, Spaced with a 40 mm gap, Fewest sheets: all on one page",
        f"<b>Fewest sheets</b>: {sh['spaced40/fewest_sheets']['pages']} page, {sh['spaced40/fewest_sheets']['cuts']} straight cuts {cite('facts')}.")}
    {fig(media, "cuts", "The same eight stickers, Fewest cuts: page 1 of 2",
        f"<b>Fewest cuts</b>: {sh['spaced40/fewest_cuts']['pages']} pages (page 1 shown), {sh['spaced40/fewest_cuts']['cuts']} cuts {cite('facts')}.")}
    {fig(media, "sheet_side", "The Sheet dialog's side: Layout Tight | Spaced, Gap 40 mm, Optimize Fewest cuts | Fewest sheets, and 2 pages, 17 straight cuts, 10 % fill",
        f"The controls and the core's numbers, Fewest cuts {cite('facts')}.")}</div></div>
<p class="note">Eight stickers (3 × 40×25, 3 × 40×30, 2 × 35×35 mm) on Letter, Spaced with a 40 mm gap: a wide gap is where the two objectives part ways. At the default 4 mm gap both give {sh['spaced/fewest_sheets']['pages']} page and {sh['spaced/fewest_sheets']['cuts']} cuts; Tight gives {sh['tight/fewest_sheets']['cuts']} {cite('facts')}. The dialog's numbers are the core's: <code>sheet.spec.ts</code> checks each against CPython on the same request {cite('sheetspec')}.</p>
{quote("I see two ways for auto layout - 1 could be like as compact as possible, the other is as few straight cuts as possible", "## Auto layout", cite("vault"))}
{quote("for the layouts there are two things to optimize for btw on is fewest cut lines. one is most compact (fewest number of sheets)", "#### My feedback on aruco studio proposals", cite("vault"))}
<ul class="built">
<li><b>Guillotine packing</b> (<code>core/pack.py</code>): every sticker sits in the corner of a free rectangle and the rest is split by one straight line, so every cut runs edge to edge of the piece it is in, as a paper trimmer or scissors can do. Tight shares cut lines; Spaced is the same packer with every sticker grown by the gap {cite('pack')}.</li>
<li>Ported, not invented: Jylänki 2010, "A Thousand Ways to Pack the Bin" (the GUILLOTINE family and its choice and split rules); rectpack 0.2.2's <code>guillotine.py</code> (its free-rectangle merge is left out, because it breaks guillotine cuts); Gilmore &amp; Gomory 1965 for the cut rule. Many sort × choice × split variants are tried and the best kept {cite('pack')}.</li>
<li>Odd-shaped profiles are packed by their bounding box for now; true nesting (SVGnest / Deepnest style) is not built {cite('pack')}.</li></ul>
<h4>The benchmark: 200 random sheets</h4>
<div class="tbl"><table class="stack"><thead><tr><th>Mode · Optimize</th><th class="n">Median pages</th><th class="n">Median cuts</th><th class="n">Pages, all 200</th></tr></thead><tbody>
<tr><td>Tight · Fewest sheets</td><td class="n" data-label="Median pages">{T['fewest_sheets']['median_pages']:g}</td><td class="n" data-label="Median cuts">{T['fewest_sheets']['median_cuts']:g}</td><td class="n" data-label="Pages, all 200">{T['fewest_sheets']['pages_sum']}</td></tr>
<tr><td>Tight · Fewest cuts</td><td class="n" data-label="Median pages">{T['fewest_cuts']['median_pages']:g}</td><td class="n" data-label="Median cuts">{T['fewest_cuts']['median_cuts']:g}</td><td class="n" data-label="Pages, all 200">{T['fewest_cuts']['pages_sum']}</td></tr>
<tr><td>Spaced · Fewest sheets</td><td class="n" data-label="Median pages">{S_['fewest_sheets']['median_pages']:g}</td><td class="n" data-label="Median cuts">{S_['fewest_sheets']['median_cuts']:g}</td><td class="n" data-label="Pages, all 200">{S_['fewest_sheets']['pages_sum']}</td></tr>
<tr><td>Spaced · Fewest cuts</td><td class="n" data-label="Median pages">{S_['fewest_cuts']['median_pages']:g}</td><td class="n" data-label="Median cuts">{S_['fewest_cuts']['median_cuts']:g}</td><td class="n" data-label="Pages, all 200">{S_['fewest_cuts']['pages_sum']}</td></tr>
<tr><td>Spaced · the old shelf packer</td><td class="n" data-label="Median pages">{S_['shelf']['median_pages']:g}</td><td class="n" data-label="Median cuts">{S_['shelf']['median_cuts']:g}</td><td class="n" data-label="Pages, all 200">{S_['shelf']['pages_sum']}</td></tr>
</tbody></table></div>
<p class="note">Each set is 1–40 stickers of 10–120 mm on Letter or A4, seeded, from <code>tests/core/test_pack.py</code> {cite('testpack')}. Re-measured for this report: Fewest cuts makes fewer cuts on <b>{S_['cuts_fewer']}</b> of the 200 spaced sets and takes a page more on {S_['cuts_more_pages']}; tight, the two never differ ({T['cuts_fewer']} sets) {cite('bench')}. The test's own validity checker (plain geometry, sharing no code with the packer) passes every layout {cite('testpack')}. Mean paper fill, spaced: {S_['mean_fill_guillotine'] * 100:.0f} % against the shelves' {S_['mean_fill_shelf'] * 100:.0f} % {cite('bench')}.</p>
</div>""")

    # ---------------------------------------------------------------- verify
    items.append(f"""
<div class="item" id="verify"><h3>2 · Verify accuracy: OpenCV in the browser, Tilt as your manual sweep</h3>
<div class="media">{fig(media, "verify", "The Verify dialog: the simulated camera view of marker #23 at 50 degrees tilt, read by OpenCV; sliders, the angle sweep and the camera calculator",
    f"The plate's marker at Tilt 50°: OpenCV's own ArUco detector reads it (green outline, its id, the pose axes). Right: the sliders, the automatic sweep (“reads to {vf['reads_to_deg']}°”) and the camera calculator {cite('facts')}.", "wide")}</div>
<div class="media">{pair(
    fig(media, "sweep", "The angle sweep: one line per marker, 18 tilts from 0 to 85 degrees",
        f"<b>Automatic</b>: per marker, 18 tilts 0–85°. {E(vf['legend'])} {cite('facts', 'verifyspec')}."),
    fig(media, "calc", "The camera calculator: 1500 mm, 1920 px, 70 degrees: good, 5.7 px per cell, limit about 3.5 m",
        f"<b>Calculator</b>: 1500 mm, 1920 px, 70°: {E(vf['calc']['text'] or '')} {cite('facts')}."))}</div>
<div class="media">{pair(
    fig(media, "ref_sweep", "Zach's reference: the V1 prototype's Verify with the sweep he liked", "Your reference: the prototype's sweep you liked"),
    "<div></div>")}</div>
{quote("This website does it even better.. It tests at different angles, etc.. we 100% want to add this.", "## Verify Accuracy", cite("vault"))}
{quote("I like how I scan sweap the verify marker my self... Of course it should autoamtically calculate it my self but its nice being able to look at it my self..", "#### My feedback on aruco studio proposals", cite("vault"))}
<ul class="built">
<li>OpenCV runs in your browser: Pyodide's <code>opencv-python 4.11.0.86</code> and numpy, fetched only on the first Verify (“Loading OpenCV (13 MB)…”). On the live site the first image came {vf['first_image_ms'] / 1000:.1f} s after opening and the sweep finished at {vf['sweep_done_ms'] / 1000:.1f} s, in this run {cite('facts', 'pyodide')}.</li>
<li><b>Tilt is the manual sweep</b>: it re-renders while you drag it (the e2e test counts at least 3 renders during one drag); clicking or hovering a sweep column sets Tilt there too {cite('verifyspec')}.</li>
<li><b>The calculator's thresholds are measured, not guessed</b>: <code>readable</code> finds the farthest distance the simulator still reads head on, then calls it “good” within 0.55 of that limit. 0.55 comes from a field view (tilt 45°, blur 1 px, grain) over 4 cameras × 5 markers, where the share that still read every id ran 0.57–0.85 {cite('webverify')}.</li></ul>
<div class="bug"><b>Bug found while recording.</b> Verify draws a two-line label as one line. In the browser (OpenCV 4.11) the line break prints as “?”: <i>PLATE?#36—39</i>. In CPython (OpenCV 5.0) the second line is cut off. The marker still reads; only the label is wrong, and the parity test does not cover Verify's pictures. Not fixed {cite('hero', 'renders', 'pyodide')}.
<div class="pair" style="margin-top:8px">{fig(media, "verify_ml_live", "The live Verify bench: the label drawn as PLATE?#36-39 on one line", "Live, in the hero recording")}{fig(media, "verify_ml_cpython", "CPython at 12f9f35: PLATE on one line, the second line cut off", f"CPython, <code>{MAIN}</code>")}</div></div>
</div>""")

    # ---------------------------------------------------------------- auto id
    items.append(f"""
<div class="item" id="autoid"><h3>3 · Auto id: a stable key, hashed, kept in a ledger in the file</h3>
<div class="media">{pair(
    fig(media, "id_driven", "The ID row driven: 40, grey", f"Driven: the auto id (#{aid['ids'][1]}), grey {cite('facts')}."),
    fig(media, "id_clash", "The ID row set to 3, which the other marker has: red, with the message", f"Typed #{aid['ids'][0]}, the other marker's id: red, “{E(aid['clash'])}” {cite('facts')}."))}</div>
<div class="media narrowimg">{fig(media, "id_key", "Advanced: the feature's key", f"The key under Advanced (<code>{E(aid['key2'])}</code>): what gets hashed {cite('facts')}.")}</div>
{quote("with stable ids, so you rebuild constiently... you just pass in something that dosen't change for that marker, and then internall we hash it..", "## Auto id", cite("vault"))}
{quote("By default the id if you are in an assembly should just automatically start at a unique ID, and if you want to manually override you can do that", "## Auto id", cite("vault"))}
<ul class="built">
<li>Each marker has a <b>key</b> that never changes. sha256 of the key (with the dictionary) picks its preferred first id; a grid gets one contiguous block {cite('autoid')}.</li>
<li><b>Why a ledger and not the hash alone</b>: in DICT_4X4_50, 10 keys share a preferred id 62 % of the time, so which one moves on would depend on who else is in the document. The ledger, saved in the file, pins every id once given out: adding or removing other markers never moves it {cite('autoid')}. Two markers on the live site got #{aid['ids'][0]} and #{aid['ids'][1]}; the ledger read <code>{E(json.dumps(aid['ledger']))}</code> {cite('facts')}.</li>
<li><b>A typed id always wins</b>; two that overlap both keep their numbers and both show red {cite('autoid', 'facts')}.</li></ul>
</div>""")

    # ---------------------------------------------------------------- the UX feedback
    ux = []
    ux.append(f"""
<h4 id="inspect">No timeline: click the marker to inspect it</h4>
<div class="media">{fig(media, "inspect", "The plate's marker clicked: the ArUco Extrude panel open beside it, no timeline; the toolbar at the bottom centre",
    f"Click the marker: its panel opens beside it ({ins['gap_px']:g} px to its {ins['side']}, not over it); click empty canvas to close it. No timeline {cite('facts')}.", "wide")}</div>
<div class="media">{pair(fig(media, "ref_timeline", "Zach's reference: the Sketch / ArUco Extrude / Joint Origin timeline", "Before: the timeline you called too CAD-specific"), "<div></div>")}</div>
{quote("in this case lets just a more WYSISYG . where by just clicking the marker on the screen is what brings up the relevant inspector window etc...", "# Oct 18 2026", cite("vault"))}""")
    ux.append(f"""
<h4>The toolbar at the bottom centre</h4>
<div class="media">{fig(media, "toolbar", "The toolbar: Select, Rectangle, Circle, ArUco, Sheet, Verify, Fit, with their keys",
    f"Words beside the icons and their keys. Its centre is {ins['toolbar_centre_off_px']:g} px from the viewport's, {ins['toolbar_bottom_gap_px']:g} px above its bottom {cite('facts')}.")}</div>
<div class="media">{pair(fig(media, "ref_toolbar", "Zach's reference: the old off-centre toolbar", "Before: off centre"), "<div></div>")}</div>
{quote("The off center tool bar shoiuld be center at top of bottom", "# Oct 18 2026", cite("vault"))}""")
    ux.append(f"""
<h4 id="label-inside">The label inside the rectangle, with white kept from the cut line</h4>
<div class="media">{pair(
    fig(media, "sticker_before", "Before: the sheet cut only the marker's outline, and the label printed below it, outside the sticker",
        f"<b>Before</b> (<code>73884a2^</code>): the page cut only the marker ({sb['cut_mm'][2] - sb['cut_mm'][0]:.2f} mm square) and printed the label outside it; in the plan its baseline sat {sb['plan_baseline_above_rect_bottom_mm']:.2f} mm from the rectangle's edge, ON the cut {cite('renders')}."),
    fig(media, "sticker_after", "After: the whole rectangle is the sticker; the label is inside it with white below",
        f"<b>After</b> (<code>{MAIN}</code>): the whole {sa['cut_mm'][2] - sa['cut_mm'][0]:.1f} × {sa['cut_mm'][1] - sa['cut_mm'][5]:.1f} mm rectangle is cut; the baseline sits <b>{sa['plan_baseline_above_rect_bottom_mm']:.2f} mm</b> above the cut, so the “p” keeps its tail {cite('renders')}."))}</div>
<div class="media">{pair(
    fig(media, "sticker", "The live Sheet page: the plate sticker with 'plate #35' inside its cut line", f"The same on the live Sheet page {cite('facts')}."),
    fig(media, "ref_label", "Zach's reference: the label outside the marker rectangle", "Before: your screenshot, the label outside the rectangle"))}</div>
{quote("THe label should go inside of the marker rectangle", "# Oct 18 2026", cite("vault"))}""")
    ux.append(f"""
<h4>3D print labels in a pixel font; inkjet labels in normal text</h4>
<div class="media">{pair(
    fig(media, "label_inkjet", "Inkjet: PLATE / #28 in normal sans text inside the rectangle", f"Inkjet · Letter vinyl: sans {cite('facts')}."),
    fig(media, "label_pixel", "3D print (Default preset): the same label as blocky pixel ink", f"3D print (preset “{E(lpx['preset'])}”): font <code>{E(lpx['font'])}</code>, {lpx['polygons']} polygons of ink {cite('facts')}."))}</div>
{quote("If 3D printign the label text should be very blocky and suitable for 3D printing", "# Oct 18 2026", cite("vault"))}""")
    ux.append(f"""
<h4>Multi-line labels, typed X / Y offsets, no offset dimension</h4>
<div class="media">{pair(
    fig(media, "label_tab", "The Label tab: On, Text with two lines, Side, Offset X 3 set, Offset Y 0, Height, Gap",
        f"Two lines (<code>PLATE</code> / <code>#{{ids}}</code> → “{E(' / '.join(lab['lines']))}”), Offset X typed 3: the label moved {lab['dx_mm']:g} mm; ↺ puts it back {cite('facts')}."),
    fig(media, "ref_offset", "Zach's reference: the offset readout he did not want", "Before: the offset readout you didn't want"), "r21")}</div>
<p class="note">No offset dimension is drawn: {lab['offset_dim']} on the canvas, and no “offset” text in the sketch {cite('facts')}.</p>
{quote("I don't like how you show the offset value here for the text. its enough to just see the location of the text.", "#### My feedback on aruco studio proposals", cite("vault"))}""")
    ux.append(f"""
<h4>The ChArUco origin in a square</h4>
<div class="media">{pair(
    fig(media, "charuco_corner", "ChArUco 5x4: the Joint Origin at the board corner", "Board corner (driven)."),
    fig(media, "charuco_square", "ChArUco 5x4: the Joint Origin in square column 1, row 1", f"Square [1, 1]: the origin moved {moved:.2f} mm, 1.5 checkers ({ch['checker_mm']:.2f} mm) along each axis {cite('facts')}."))}</div>
<div class="media narrowimg">{fig(media, "origin_rows", "The Origin row: Board corner | Square, Column 1, Row 1", "The rows.")}</div>
{quote("For charuo markers we should support an origin that is inside one of the squares btw", "# Oct 18 2026", cite("vault"))}""")
    ux.append(f"""
<h4>Suggestions in a dropdown</h4>
<div class="media">{pair(
    fig(media, "suggest", "The Suggest dropdown open: eight layouts, each with its whole reason",
        f"One row ({F['suggest_trigger_h']:g} px tall) until opened; each option shows its whole reason {cite('facts')}."),
    fig(media, "ref_suggest", "Zach's reference: the old list of suggestions", "Before: the list you wanted compact"))}</div>
{quote("Suggestions should be in adrop down menu to be more compact:", "# Oct 18 2026", cite("vault"))}""")
    ux.append(f"""
<h4>The presets modal: Info on the right, editable</h4>
<div class="media">{fig(media, "presets", "The presets modal: filters in the left bar, a copied preset selected, its Info on the right with editable fields",
    f"Search and filter chips in the left bar; a click shows the preset's Info on the right. Built-ins are read-only with Duplicate to edit; this copy's margin was typed to {E(F['preset_copy']['margin_mm'])} mm and is kept in this browser {cite('facts')}.", "wide")}</div>
{quote("as I click different ones it should show the info screen...", "# Oct 18 2026", cite("vault"))}""")
    ux.append(f"""
<h4>Download for CAD (placeholders)</h4>
<div class="media narrowimg">{fig(media, "cad", "The Download for CAD menu: Fusion 360 and Onshape, both coming soon", "Both items are disabled: “coming soon” {cite}.".replace("{cite}", cite('facts')))}</div>
{quote("Aruco studio should have easily accesibly a Download for CAD button... wher eyou can then download for fusion360, onshape (place holder for now)", "# Oct 18 2026", cite("vault"))}""")
    ux.append(f"""
<h4>The inkjet “0.4 mm nozzle” lint, fixed</h4>
<div class="media narrowimg">{fig(media, "preset_row", "The Preset row on Inkjet Letter vinyl: its notes, no nozzle", f"Live, the plate on Inkjet · Letter vinyl: no “nozzle” anywhere in the panel {cite('facts')}.")}</div>
<p>The same grid (5 × 4 at 5.8 mm) through the core before and after: <b>before</b> it said “{E(lint_b[0] if lint_b else '')}”; <b>after</b>, {'no nozzle note' if not lint_a else E(lint_a[0])}, and the inkjet's own rule stays: “{E(cellmin[0] if cellmin else '')}” {cite('renders', 'c7f84feb')}.</p>
{quote("preset is inject but its giving me alinter warning for 3d printing...", "# Oct 18 2026", cite("vault"))}""")
    ux.append(f"""
<h4>Also: several markers on one board, dark theme, a phone</h4>
<div class="media">{fig(media, "two", "Two markers drawn on a blank sketch with ids 3 and 40; the second's panel open",
    f"Two markers, each its own feature with its own id (#{aid['ids'][0]}, #{aid['ids'][1]}) {cite('facts')}.", "wide")}</div>""" + (f"""
<p class="rough"><b>Rough edge.</b> A marker near the right edge: the panel stays inside the viewport and covers the right {ap['rect_covered_px']:g} px of that marker's rectangle, {ap['marker_covered_px']:g} px of its white border and {ap['black_covered_px']:g} px of its black. The view does not pan to make room {cite('facts')}.</p>""" if ap and ap.get("rect_covered_px", 0) > 0 else "") + f"""
<div class="media">{pair(
    fig(media, "dark", "The plate with its panel open in the dark theme", f"Dark {cite('facts')}."),
    fig(media, "mobile", "390 by 844: the panel docked at the bottom, the toolbar above it, the marker fitted above both",
        f"390 × 844: the panel docks at the bottom ({mob['panel']['height']:.0f} px of 844), the toolbar above it; no sideways scroll {cite('facts')}."), "r21")}</div>""")
    items.append(f"""
<div class="item" id="ux"><h3>4 · Your UX feedback, item by item</h3>{''.join(ux)}</div>""")

    # ---------------------------------------------------------------- driven vs set
    items.append(f"""
<div class="item" id="driven"><h3>5 · Driven vs set: grey vs solid, ↺, no Auto switches</h3>
<div class="media">{pair(
    fig(media, "dims_driven", "Grid 2x2 on the plate: every dimension grey (driven) except the rectangle's W and H",
        f"<b>Driven</b>: the marker ({E(dm_b['marker.marker_mm']['text'])}), the gap ({E(dm_b['marker.separation_mm']['text'])}) and the outer size are grey; the rectangle's own W and H ({E(dm_b['rect.w']['text'])}, {E(dm_b['rect.h']['text'])}) are solid {cite('facts')}."),
    fig(media, "dims_set", "After typing 16 into the marker dimension: 16 solid, the others grey and re-planned",
        f"<b>Typed</b> {dm['typed_mm']:g} into the marker's dimension on the sketch: it turns solid and the rest re-plan ({E(dm_a['marker.separation_mm']['text'])} gap) {cite('facts')}."))}</div>
<div class="media">{pair(
    fig(media, "rows_driven", "The panel rows, driven: Marker 19.5578 grey", "The panel before: Marker grey."),
    fig(media, "rows_set", "The panel rows, set: Marker 16 solid with a reset arrow; the cell-grid note under it",
        f"After: Marker 16, solid, with ↺ {cite('facts')}."))}</div>
<p class="note">Truthful, not rounded: “16” is drawn at {dm['plan_marker_mm']:.4f} mm, the nearest whole number of printer dots per cell on this preset; the row says so (“cell multiple: 16.0 mm → 15.748 mm”) {cite('facts')}. Grey and solid are the theme's muted and text colours: <code>{E(dm_b['marker.marker_mm']['fill'])}</code> vs <code>{E(dm_a['marker.marker_mm']['fill'])}</code> in light {cite('facts')}. The Auto switch is gone: {dm['auto_switch']} on the panel {cite('facts')}.</p>
{quote("instead of showing like auto, just show the actual value but make it kinda like grey outed that indicates that its like being driven as supposet to having been set.", "### Good defaults", cite("vault"))}
{quote("and then just like fusion the can be in like an automod where they are being driven or if you set them then they turn kinda white... thats now a set dimensions,e tc.", "# Oct 18 2026", cite("vault"))}
</div>""")

    # ---------------------------------------------------------------- proposals
    items.append(f"""
<div class="item" id="proposals"><h3>6 · The five UI proposals → your pick: V1 core + V2 dimensions, no V4</h3>
<div class="media">{pair(
    fig(media, "proto_v1", "The V1 Click-to-inspect prototype", "V1 Click-to-inspect (prototype): the core you kept."),
    fig(media, "proto_v2", "The V2 Sketch-native prototype with typed dimensions", "V2 Sketch-native (prototype): its typed dimensions came along."))}</div>
<p>All five are still clickable in <a href="ui-proposals-2026-10-18.html">the proposals gallery</a> {cite('gallery')}. The built V1 is item 4's first still.</p>
{quote("yes 100% lets keep your v1 click to isnpect as the core. we want it read to drop into a cad program", "#### My feedback on aruco studio proposals", cite("vault"))}
{quote("Yes I agree we can support the v2 dimensions type in the sketch with v1", "#### My feedback on aruco studio proposals", cite("vault"))}
{quote("I don't find v4 useful though no need to support that.", "#### My feedback on aruco studio proposals", cite("vault"))}
</div>""")

    # ---------------------------------------------------------------- logo
    items.append(f"""
<div class="item" id="logo"><h3>7 · The logo: V18 Extrude Cube</h3>
<div class="media">{logo_tiles(icon, icon2d)}</div>
<p class="note">The files as shipped (<code>web/public/icon.svg</code>, <code>icon-2d.svg</code>), drawn here at 128 / 64 / 32 / 16 px on a light and a dark background; the 2D spare is black only, so it is shown on light.</p>
<div class="media">{pair(
    fig(media, "og", "The 1200 by 630 social card", f"The social card (<code>og.png</code>, 1200 × 630), live as <code>og:image</code> {cite('live_head')}."),
    fig(media, "mark", "The top-bar mark: the cube and 'ArUco Studio'", f"The top-bar mark, live {cite('facts')}."), "r21")}</div>
<ul class="built">
<li>The corner is a <b>45° cut</b>, not the square notch; the top face is the <b>“window”</b> pattern. The other 7 top faces are in <a href="logo-v18-picks-2026-10-18.html">the V18 picks page</a> {cite('logo')}.</li>
<li><b>It never decodes as a real ArUco marker</b>: OpenCV 5's detector over all 22 predefined ArUco / AprilTag dictionaries, normal and inverted, found 0 decodes in 276 renders of the cube and 276 of the 2D icon (sizes, 20° / 45° turns, perspective, blur). A real DICT_4X4_50 marker as the control was caught. One caveat the check states: hits on DICT_ARUCO_ORIGINAL ids 0 / 1023 are not counted, since a plain book icon decodes to those {cite('logo')}.</li>
<li>Used as the dock icon, the favicon, the top-bar mark and the social card; the flat 2D icon is the spare {cite('logo', 'live_head')}.</li></ul>
</div>""")

    # ---------------------------------------------------------------- stable / preview
    items.append(f"""
<div class="item" id="sps"><h3>8 · Stable / Preview, and the dock icon</h3>
<div class="media">{fig(media, "chip", "The Preview chip: Preview, main, ed5e15e, Stable is behind, Make Stable",
    f"Your local Preview (http://127.0.0.1:5383) at 18:23: the chip says Preview · main · ed5e15e · Stable is behind · Make Stable {cite('facts')}.")}</div>
<ul class="built">
<li><b>Stable</b> is the pinned build on <code>http://127.0.0.1:5382</code>; <b>Preview</b> is <code>main</code> live, with hot reload, on <code>http://127.0.0.1:5383</code>. The app adds one data file, <code>stable-preview.json</code>, and no code {cite('sps')}.</li>
<li>The dock's “ArUco Studio” opens Stable; right-click for <i>Open Preview (live — what agents are changing)</i>, <i>Make Preview Stable</i> and <i>Roll Stable Back</i> {cite('sps')}.</li></ul>
<p class="rough"><b>Rough edge.</b> At 1280 × 800 the Preview chip sits over the toolbar's Fit button (the still above) {cite('facts')}. The chip is the shared switcher's, so the fix belongs there or in the toolbar's spacing.</p>
{quote("Its great to the remote deployed one but please server this app locally and install the stable preview switcher", "# Oct 18 2026", cite("vault"))}
</div>""")

    # ---------------------------------------------------------------- fusion
    items.append(f"""
<div class="item" id="fusion"><h3>9 · The Fusion plugin</h3>
<p>The request went to the Windows session over Remote Control, which has no reply channel, so this session could not see an answer. <b>Update while this report was built:</b> commit <code>ed5e15e</code> (18:17) is contract barrier 4, “the Fusion adapter's N-6 asks”, and its message says they were “Requested by the Windows session that put the Fusion add-in on web_api” (cad-exporter <code>claude/aruco-fusion-plugin-0e9bcb</code> @ <code>a1dc10b</code>). The lane that builds them, <code>lane/os-cadfacade</code>, merged into <code>main</code> at 18:40 ({head_merge}) {cite('ced5e15e', 'git')}. I could not open that cad-exporter branch from Linux, so whether the add-in runs in Fusion is still unknown to me.</p>
</div>""")

    # ---------------------------------------------------------------- dispatch
    waves = f"""
<div class="waves">
<div class="wave"><h4>Barrier 1 · <code>ebc46a5</code> 14:21</h4><div class="b">sheet mode / gap / cuts / fill, verify, readable, assign_ids</div>
<ul><li><code>os-ids</code> → auto id</li><li><code>os-layout</code> → core.pack</li><li><code>os-verify</code> → web_verify</li><li><code>os-doc</code> → many features, driven vs set, no timeline</li></ul>
<div class="m">merged 14:38 (ids) and 16:14</div></div>
<div class="wave"><h4>Barrier 2 · <code>56235bd</code> 14:43</h4><div class="b">your 14:30 review: label inside, pixel font, multi-line, origin square, dims, the cut line</div>
<ul><li><code>os-plan2</code> → the label inside the rectangle</li><li><code>os-presets</code> → Info on the right</li><li><code>os-sps</code> → Stable / Preview</li></ul>
<div class="m">merged 16:14; the merged tree's tests found the sticker bug: fixed in <code>73884a2</code> 16:22</div></div>
<div class="wave"><h4>Barrier 3 · <code>184f107</code> 16:39</h4><div class="b">your V1 pick: Optimize objective, the Verify mount point</div>
<ul><li><code>os-verifyui</code> → the Verify dialog</li><li><code>os-v1panel</code> → click-to-inspect</li><li><code>os-dims</code> → typed dimensions</li><li><code>os-sheet</code> → the Sheet dialog (+ a follow-up)</li><li><code>os-logo</code> (cut from <code>0fa102d</code>) → the logo</li></ul>
<div class="m">merged 16:54–17:55</div></div>
</div>"""

    # ---------------------------------------------------------------- proof
    s = su
    def pyrow(k: str) -> str:
        return pyrow_of(s[k])

    def pyrow_of(d: dict) -> str:
        bits = [f"{d.get('passed', 0):,} passed"]
        if d.get("skipped"):
            bits.append(f"{d['skipped']} skipped")
        if d.get("failed"):
            bits.append(f"{d['failed']} failed")
        return " / ".join(bits) + (f" ({d['seconds']:.0f} s)" if d.get("seconds") else "")
    core_f = s["core"]["failed_tests"]
    proof_rows = [
        ("tests/web (CPython)", pyrow("web"), "runs"),
        ("core", pyrow("core") + ": the Linux baseline", "runs"),
        ("plan", pyrow("plan") + ": the Linux baseline", "runs"),
        ("scene", pyrow("scene"), "runs"),
        ("verify", pyrow("verify"), "runs"),
        ("vitest", f"{s['vitest']['passed']} passed ({s['vitest']['files']} files)", "runs"),
        ("Pyodide ↔ CPython parity", f"{s['parity']['same']} / {s['parity']['of']} byte-identical (Pyodide {s['parity']['pyodide_ms']} ms, CPython {s['parity']['cpython_ms']} ms)", "runs"),
        ("Playwright e2e, local build", f"{s['e2e_local'].get('passed')} passed, {s['e2e_local'].get('skipped', 0)} skipped (the report stills) in {s['e2e_local'].get('took')}", "runs"),
        ("Playwright e2e, live arucostudio.com", f"{s['e2e_live'].get('passed')} passed, {s['e2e_live'].get('failed', 0)} failed in {s['e2e_live'].get('took')}" + (f"; again: {s['e2e_live2'].get('passed')} passed, {s['e2e_live2'].get('failed', 0)} failed" if s.get('e2e_live2', {}).get('passed') else ""), "runs"),
        ("Report stills + hero, live", f"{s['report_live'].get('passed')} / {s['report_live'].get('passed', 0) + s['report_live'].get('failed', 0)} and {s['hero_live'].get('passed')} / 1", "facts"),
        ("The live core", f"all {live['same']} files of the live zip byte-identical to <code>{live['stamp']}</code> ({live['diff']} differ, {live['missing']} missing)", "live_zip"),
    ]
    hd = s.get("head")
    if hd:
        proof_rows.append((f"<code>main</code> at <code>{E(hd['rev'])}</code> (18:40, moved during this report)",
            f"tests/web {pyrow_of(hd['web'])}; vitest {hd['vitest']['passed']}; parity {hd['parity']['same']} / {hd['parity']['of']}; "
            f"e2e local {hd['e2e_local'].get('passed')} passed, <b>{hd['e2e_local'].get('failed', 0)} failed</b>, {hd['e2e_local'].get('skipped', 0)} skipped"
            + (f" (<code>features.spec.ts</code> a: one marker's black drawn 0 px wide; it passed {hd['e2e_rerun'].get('passed')} / {hd['e2e_rerun'].get('passed', 0) + hd['e2e_rerun'].get('failed', 0)} on re-run; not root-caused)" if hd['e2e_local'].get('failed') and hd.get('e2e_rerun', {}).get('passed') else ""), "runs_head"))
    proof = "".join(f"<tr><td>{a}</td><td>{b} {cite(k)}</td></tr>" for a, b, k in proof_rows)

    # ---------------------------------------------------------------- the page
    body = f"""
<main>
<h1>ArUco Studio V1</h1>
<div class="meta">Review, round two · 18 Oct 2026 · <code>main</code> at <code>{MAIN}</code> · built by <code>docs/build_v1_report.py</code></div>

<div class="verdict"><b class="v">ArUco Studio V1 is live and on main: click-to-inspect, dimensions you type on the sketch, auto layout, verify, auto id, and the new logo.</b>
<div class="qual"><span class="pill ok">on main</span><span class="pill ok">pushed</span><span class="pill warn">Stable not promoted</span> The site runs commit <code>{LIVE}</code>: all {live['same']} files of its Python core are byte-identical to it {cite('live_zip')}. The one commit after it, <code>{MAIN}</code>, only changes an e2e test {cite('git')}. Making Preview Stable is your call.</div>
<ul>
<li>Found while recording this report: Verify draws a two-line label on one line (a “?” for the break), and the panel can cover a marker at the right edge. Neither is fixed (<a href="#verify">2</a>, <a href="#ux">4</a>).</li>
<li><code>main</code> moved on while this report was built: {len(since)} commit{'s' if len(since) != 1 else ''} after <code>{MAIN}</code>, now at <code>{head}</code> (<code>origin/main</code>: <code>{origin_main}</code>). They are the Fusion adapter's contract asks and their lane (<a href="#fusion">9</a>), then newer work such as “only dimensions you control”. The live site has none of them; Preview has all. Everything below is of <code>{MAIN}</code>{f'; on <code>{E(su["head"]["rev"])}</code> (main at 18:40) I re-ran the quick checks and the local e2e (<a href="#proof">Proof</a>)' if su.get("head") else ''}.
<details><summary>The {len(since)} newer commits</summary><div class="tbl"><table><tbody>{''.join(f"<tr><td class='h'><code>{E(c.split(chr(9))[0])}</code></td><td>{E(c.split(chr(9), 1)[1])}</td></tr>" for c in since)}</tbody></table></div></details></li></ul></div>

<h2 style="border:0;margin-top:20px;padding-top:0">See it</h2>
<figure class="hero"><video autoplay muted loop playsinline controls preload="auto" poster="{uri(media, 'hero_poster')}" width="{media['hero'][2]}" height="{media['hero'][3]}" aria-label="Hero video: the plate, click the face, A, the panel beside the marker, Grid, the marker size typed on the sketch, the Label tab, Sheet's Optimize toggle, Verify's Tilt dragged">
<source src="{uri(media, 'hero')}" type="video/mp4">Your browser can't play this video; the frame above is from it.</video>
<figcaption>The live site: Examples › Plate → click the face, <span class="kbd">A</span> (the panel opens beside the marker) → Grid → type 16 into the marker's dimension (grey → solid) → Label: two lines, Offset X 3 → Sheet: Fewest cuts, Fewest sheets → Verify: drag Tilt. Recorded by Playwright in Chrome; {hero_s:.1f} s at {HERO_SPEED:g}× of {raw_s:.1f} s. Cut: the core loading ({keep[1][0] - keep[0][1]:.1f} s) and OpenCV loading ({keep[2][0] - keep[1][1]:.1f} s) {cite('hero')}.</figcaption></figure>
<div class="try"><b>Try it</b> on <a href="https://arucostudio.com">https://arucostudio.com</a>, or your local Preview at <a href="http://127.0.0.1:5383">http://127.0.0.1:5383</a> (Stable, older, on <a href="http://127.0.0.1:5382">:5382</a>).<ol>
<li>Wait for <i>Python ready</i> ({ready[0]:g}–{ready[-1]:g} s over {len(ready)} fresh loads today {cite('facts')}).</li>
<li>File › Examples… › <b>Plate</b>; click inside the face; press <span class="kbd">A</span>.</li>
<li>Click Grid, then click the marker's grey dimension and type a size.</li>
<li><span class="kbd">S</span> opens Sheet, <span class="kbd">K</span> opens Verify.</li></ol></div>

<h2>What you asked → what's there</h2>
<p class="note">Your words are quoted from your note as written {cite('vault')}. Every app still is from the live site today, 1280 × 800 at 2× {cite('facts')}; click any image to enlarge it.</p>
{"".join(items)}

<h2>How it's built</h2>
{diagram(False, ncalls)}{diagram(True, ncalls)}
<p class="note">The screen never computes marker geometry: it draws what the core returns, in the sketch's millimetres {cite('design')}. <code>plan()</code> only ever sees a rectangle; <code>inscribe(profile)</code> is the step above it, and <code>sheet()</code> packs every plan with <code>core.pack</code> {cite('contract')}. You put it as “Placing rectangles in a profile is actualyl a seperate step! one step above in the pipeline..” {cite('vault')}. <b>Parity</b> means the same call gives byte-for-byte the same JSON in Pyodide (Python compiled to WebAssembly, in the browser) and in CPython.</p>
<h3>How the lanes were dispatched</h3>
<p>Each lane was one agent in its own git worktree, cut from a <b>contract barrier</b>: a commit that freezes the UI ↔ core contract before the lanes that depend on it start, so two lanes can't each be right and together wrong. Three barriers this round; each lane merged back into <code>main</code>, and the tests ran on the merged tree before the next step {cite('barriers', 'git')}.</p>
{waves}

<h2 id="proof">Proof</h2>
<p class="note">Re-measured for this report on a clean <code>git archive {MAIN}</code> (no working-tree changes), 2026-10-18 {cite('runs')}.</p>
<div class="tbl"><table><thead><tr><th>Check</th><th>Result</th></tr></thead><tbody>{proof}</tbody></table></div>
<p class="note">The {s['core'].get('failed', 0)} core and {s['plan'].get('failed', 0)} plan failures are the Linux baseline, the same 79 and 2 the first report measured: golden numbers recorded on the Windows box that differ here in the last digit, in {len(core_f)} golden tests ({', '.join('<code>' + E(t.split('::')[-1]) + '</code>' for t in core_f)}); plan's are a stored Windows path and one mesh digest, <code>fuzz:57</code> {cite('runs')}. A separate task is queued for them.</p>
<h3>The flaky driven-vs-set test, root-caused</h3>
<p>Each new feature gets a random key, which hashes to its auto id. The test typed “3” into First ID to make it set; when the key happened to hash to 3, typing the value the field already showed was no edit, so the row stayed driven and the test failed. It now types an id one past the auto id {cite('c12f9f35')}.</p>
<details><summary><code>web/e2e/features.spec.ts</code>: the diff of <code>{MAIN}</code></summary>{diff_html(d_flaky)}</details>

<h2>Cross-lane bugs the merged-tree tests caught</h2>
<p>Each lane was green alone. These showed up only when the lanes met on <code>main</code>:</p>
<ol>
<li><b>The sheet printed only the marker's outline, and the label sat ON the cut line.</b> The layout lane cut each sticker at the marker; the label lane had put the label inside the rectangle with its baseline on the rectangle's edge, so a knife on that line cuts the descenders (“part” loses its “p”). Fixed in <code>73884a2</code>: the whole rectangle is the sticker, and the label band keeps white from the cut plus room for descenders {cite('c73884a2', 'renders')}. The before / after is in item 4.</li>
<li><b>Stable's snapshot excluded <code>verify/</code></b>, which the browser core now packs for Verify, so the first “Make Preview Stable” failed (ENOENT). Fixed by dropping it from the exclude list {cite('ca497385')}.
<details><summary><code>stable-preview.json</code>: the diff of <code>a497385</code></summary>{diff_html(d_stable)}</details></li>
<li><b>The dims e2e expected the label “#0”</b>; once auto id landed, an untouched marker gets its hashed id instead. The test now reads the plan's id. This is a test edited in a fix, so here is the whole change {cite('c0b93cd8')}:
<details><summary><code>web/e2e/dims.spec.ts</code>: the diff of <code>0b93cd8</code></summary>{diff_html(d_dims)}</details></li>
</ol>
<details><summary>The files <code>73884a2</code> changed</summary><pre class="diff">{E(stat_fix)}</pre></details>
<details><summary><code>plan/plan.py</code>: the nozzle lint fix (<code>7f84feb</code>)</summary>{diff_html(d_lint)}</details>

<h2>The repo repair</h2>
<p>The build session crashed in the middle of a commit, leaving 11 empty git objects and some working files zeroed. It was repaired without losing anything:</p>
<ul>
<li>The logo merge was rebuilt from the intact lane branch with <code>git merge-tree</code>. Check, re-run today: the merge <code>b1864d5</code>'s tree is <code>{logo_tree[:7]}</code>, exactly what <code>git merge-tree --write-tree</code> builds from its two parents (<code>{merge_tree[:7]}</code>){'; it was one of the 11 empty objects' if logo_tree in kept else ''} {cite('repair')}.</li>
<li>The zeroed files were restored from git. Today no tracked file is empty except <code>aruco_studio/server/__init__.py</code>, which is empty in git too.</li>
<li>The empty objects are kept in <code>~/.local/state/aruco-studio-git-repair-2026-10-18/</code>: {len(kept)} files, {kept_empty} of them 0 bytes. {len(kept_now)} of those ids exist whole in the repo again; the other {len(kept) - len(kept_now)} are referenced by nothing {cite('repair')}.</li>
<li><code>git fsck --no-dangling</code>: {'clean' if fsck.returncode == 0 and not fsck.stdout.strip() else E(fsck.stdout.strip()[:200])} (exit {fsck.returncode}) {cite('repair')}.</li>
<li>GitHub was never affected: the crash was local, and <code>origin/main</code> is <code>{origin_main}</code> {cite('git')}.</li></ul>

<h2>Decisions for you</h2>
<p class="note">Each has my recommendation and what happens if you say nothing.</p>
<div class="q"><h4>(a) Make Preview Stable?</h4><p class="rec"><b>Recommend yes</b>: Preview is <code>main</code> (<code>{head}</code> as this page was built): everything above, plus the newer commits in the verdict. The e2e suite passed on <code>{MAIN}</code> locally and twice live{head_note}. Right-click the dock icon › <i>Make Preview Stable</i>; <i>Roll Stable Back</i> undoes it.</p><p class="def">If you say nothing: Stable stays where it is.</p></div>
<div class="q"><h4>(b) The logo's top face: “window”, or one of the other 7?</h4><p class="rec"><b>Recommend “window”</b>: its whole inside is one white window, so the top face still reads at 32 and 16 px, where the other seven's single bits are gone (the picks page's reasoning) {cite('logo')}. The others are on <a href="logo-v18-picks-2026-10-18.html">the picks page</a>; each has a “Pick #N” line to copy back to me.</p><p class="def">If you say nothing: window.</p></div>
<div class="q"><h4>(c) What next, in this order?</h4><ol>
<li><b>The Fusion add-in on this core</b>: now moving (item 9); its contract asks are barrier 4.</li>
<li><b>A one-click CAD download</b> in Download for CAD, once the add-in is packaged {cite('vault')}.</li>
<li><b>A 3D view for heights</b> (“we also want a 3D viewer so you can see heights”) {cite('vault')}.</li>
<li><b>DXF import of faces.</b></li>
<li><b>Undo.</b></li>
<li><b>True nesting</b> for odd-shaped profiles (today they pack by their bounding box) {cite('pack')}.</li></ol>
<p class="rec">Plus three small fixes from this report: Verify's two-line label, the panel covering a marker at the right edge, and the Preview chip over Fit.</p>
<p class="def">If you say nothing: this order, after the small fixes.</p></div>
<div class="q"><h4>(d) The {s['core'].get('failed', 0) + s['plan'].get('failed', 0)} golden failures on Linux</h4><p class="rec">A separate task is queued; they predate today and are last-digit float noise against Windows-made goldens.</p><p class="def">If you say nothing: the queued task handles them.</p></div>
<div class="q"><h4>(e) Worth a /llm-judge?</h4><p class="rec"><code>core/pack.py</code> decides what you cut, and <code>web_verify.py</code>'s thresholds decide what the calculator tells people about their camera. Both are tested ({cite('testpack', 'webverify')}), but no second model has read them.</p><p class="def">If you say nothing: no audit (your rule).</p></div>

<h2>Deliberately not done</h2>
<ul>
<li><b>No tldraw</b>: the sketch stays hand-rolled SVG, behind one seam.</li>
<li><b>No 3D view</b>: next step 3.</li>
<li><b>No audit run</b>: audits are yours to ask for.</li>
<li><b>No Stable promote</b>: decision (a).</li>
<li><b>The old <code>studio/</code> left untouched.</b></li>
<li><b>The bugs found today are reported, not fixed</b>: this pass was the report.</li>
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
            f'<title>ArUco Studio V1</title>'
            f'<meta name="description" content="ArUco Studio V1, round two of 18 Oct 2026: what was built, the proof, the bugs found, and the decisions left.">'
            f'<link rel="icon" href="data:image/svg+xml;base64,{base64.b64encode(icon.encode()).decode()}">'
            f'<style>{CSS}</style></head><body>{body}<script>{JS}</script></body></html>')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--work", type=Path, default=WORK)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--renders", action="store_true", help="re-make the CPython before / after renders first")
    ap.add_argument("--bench", action="store_true", help="re-run the 200-set packer benchmark first")
    ap.add_argument("--suites-logs", type=Path, help="parse the test logs in this folder into suites.json first")
    ap.add_argument("--head-logs", nargs=2, metavar=("DIR", "REV"), help="also parse the quick checks run on main at REV (it moved during the report)")
    a = ap.parse_args()
    if a.renders or not (a.src / "renders" / "renders.json").exists():
        print(json.dumps(renders(a.src), indent=2)[:3000])
    if a.bench or not (a.src / "bench-pack.json").exists():
        bench(a.src)
    if a.suites_logs:
        su = suites_from_logs(a.suites_logs)
        if a.head_logs:
            su["head"] = {**suites_from_logs(Path(a.head_logs[0])), "rev": a.head_logs[1]}
        (a.src / "suites.json").write_text(json.dumps(su, indent=2))
    out = build(a.src, a.out, a.work)
    print(f"{out}  {out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
