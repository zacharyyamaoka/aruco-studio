#!/usr/bin/env python3
"""Build the landing page, https://arucostudio.com/about/ (2026-10-20).

    python3 docs/build_landing.py            # the page only, from the media already in place
    python3 docs/build_landing.py --media    # re-encode the media from the raw captures first

Writes web/public/about/index.html (and, with --media, web/public/about/media/*).
Vite copies web/public/ into web/dist/ as it is, so the page is plain static
HTML: no JS, readable by any crawler. The Studio itself stays at /.

Standard library only; --media shells out to ffmpeg / ffprobe.

The raw captures live in reports/media/landing-src/ (gitignored), all from the
LIVE site:

  hero.webm, hero.marks.json   the primary flow:
      (cd web && E2E_BASE_URL=https://arucostudio.com HERO_OUT=<src>/hero.webm \
          npx playwright test --project=hero)
  shots/*.png, shots/facts.json   the stills:
      (cd web && E2E_BASE_URL=https://arucostudio.com REPORT_SHOTS_DIR=<src>/shots \
          npx playwright test --project=e2e e2e/report.spec.ts)
  shots/type-*.png, shots/trim-*.png, shots/heights-*.png, shots/landing-facts.json,
  canvas.webm, canvas.marks.json   single / grid / ChArUco and the two trims on
      the plate, the heights in 3D, and the marker-maker clip:
      (cd web && E2E_BASE_URL=https://arucostudio.com LANDING_SRC=<src> \
          npx playwright test --project=e2e e2e/landing-shots.spec.ts)
  fusion.mp4 or fusion.webm (optional)   a screen recording of the add-in in
      Fusion 360. --media speeds it up FUSION_SPEED times into a muted, looping
      media/fusion.mp4 with a poster; the page shows the "In Fusion 360" figure
      only while media/fusion.mp4 exists (no placeholder before that).

Every number in the copy is read from facts.json (the numbers used are kept
in web/public/about/media/facts.json, so the page rebuilds without the raw
captures) or the marks; every quote is
Zach's own text, word for word, from his project notes.
"""
from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reports" / "media" / "landing-src"
OUT_DIR = ROOT / "web" / "public" / "about"
MEDIA = OUT_DIR / "media"
ICON = ROOT / "web" / "public" / "icon.svg"
FFMPEG, FFPROBE = "/usr/bin/ffmpeg", "/usr/bin/ffprobe"

SITE = "https://arucostudio.com"
GITHUB = "https://github.com/zacharyyamaoka/aruco-studio"
RELEASES = f"{GITHUB}/releases"
TITLE = "ArUco Studio: a free ArUco and ChArUco marker generator for print and CAD"
DESCRIPTION = ("ArUco marker generator in your browser: pick a profile, get a printable, CAD-ready ArUco, "
               "grid or ChArUco board. Prints at true scale, verifies with OpenCV, Fusion 360 add-in coming.")
# WHY a 3 MB cap: the page is the site's front door and has to load fast on a phone.
BUDGET = 3 * 1024 * 1024

# The hero: two spans of the recording (seconds), from the marks. Span 1 is
# File > Examples > Plate, click the face, A, Grid (to 1 s past "grid");
# span 2 is Sheet with Fewest cuts | Fewest sheets (from the click on Sheet
# to just after the toggle). The cut skips the size and label edits between.
HERO_SPANS = [("core_ready", 0.5, "grid", 1.0), ("label", 1.1, "sheet_toggled", 0.4)]
HERO_POSTER_AT = ("grid", 0.6)   # the grid on the plate, the panel beside it
# The Fusion 360 recording plays this many times faster than it was recorded.
FUSION_SPEED = 4
# The marker maker: from the blank sketch to just after the paste, at 1x.
CANVAS_SPAN = ("start", 0.0, "end", 0.0)
CANVAS_POSTER_AT = ("end", -0.3)   # eight markers, eight ids
# WHY a crop (w, h, x, y in the 1280 x 800 recording): the blank sketch around
# the eight markers is most of the frame and shrinks them to nothing on a phone;
# the crop keeps the markers, the panel (it opens at the left edge) and the toolbar.
CANVAS_CROP = (1100, 600, 0, 200)

# out name -> (raw still, width px). Full-window shots are 2560 x 1600 (2x).
STILLS = {
    "inspect": ("01-inspect.png", 1280),
    "inspect-dark": ("12-dark.png", 1280),
    "type-single": ("type-single.png", 720),
    "type-grid": ("type-grid.png", 720),
    "type-charuco": ("type-charuco.png", 720),
    "driven": ("02c-rows-driven.png", 660),
    "set": ("02d-rows-set.png", 660),
    "autoid": ("06-two-markers.png", 1280),
    "trim-profile": ("trim-profile.png", 720),
    "trim-marker": ("trim-marker.png", 720),
    "heights-driven": ("heights-driven.png", 720),
    "heights-set": ("heights-set.png", 720),
    "sheet-sheets": ("09a-sheet-fewest-sheets.png", 1280),
    "sheet-cuts": ("09b-sheet-fewest-cuts.png", 1280),
    "print": ("10-sheet-plate.png", 1280),
    "verify": ("11-verify.png", 1280),
}


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def size_of(path: Path) -> tuple[int, int]:
    out = run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)])
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


def encode_media() -> None:
    MEDIA.mkdir(parents=True, exist_ok=True)
    marks = json.loads((SRC / "hero.marks.json").read_text())
    spans = [(marks[a] + da, marks[b] + db) for a, da, b, db in HERO_SPANS]
    parts = "".join(f"[0:v]trim={s:.2f}:{e:.2f},setpts=PTS-STARTPTS[v{i}];" for i, (s, e) in enumerate(spans))
    chain = "".join(f"[v{i}]" for i in range(len(spans)))
    graph = f"{parts}{chain}concat=n={len(spans)}:v=1:a=0,scale=960:-2:flags=lanczos,format=yuv420p[out]"
    run([FFMPEG, "-v", "error", "-y", "-i", str(SRC / "hero.webm"), "-filter_complex", graph, "-map", "[out]",
         "-c:v", "libx264", "-preset", "slow", "-crf", "22", "-r", "25", "-movflags", "+faststart", "-an", str(MEDIA / "hero.mp4")])
    at = marks[HERO_POSTER_AT[0]] + HERO_POSTER_AT[1]
    run([FFMPEG, "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", str(SRC / "hero.webm"), "-frames:v", "1",
         "-vf", "scale=960:-2:flags=lanczos", "-q:v", "4", str(MEDIA / "hero-poster.jpg")])
    for name, (raw, width) in STILLS.items():
        src = SRC / "shots" / raw
        w, _ = size_of(src)
        run([FFMPEG, "-v", "error", "-y", "-i", str(src), "-vf", f"scale={min(width, w)}:-2:flags=lanczos",
             "-c:v", "libwebp", "-quality", "86", "-compression_level", "6", str(MEDIA / f"{name}.webp")])
    # the numbers the copy quotes, kept beside the media so the page rebuilds without the raw captures
    facts = json.loads((SRC / "shots" / "facts.json").read_text())
    landing = json.loads((SRC / "shots" / "landing-facts.json").read_text())
    used = {"sheet": {k: facts["sheet"][k] for k in ("spaced40/fewest_sheets", "spaced40/fewest_cuts")},
            "verify": {"legend": facts["verify"]["legend"], "calc": {"text": facts["verify"]["calc"]["text"]}},
            "core_ready_s": facts["core_ready_s"],
            "tabs": landing["tabs"],
            "heights": {"preset": landing["heights"]["preset"],
                        **{k: landing["heights"]["extrude"][k] for k in ("white_mm", "black_mm")},
                        "set_black_mm": landing["heights_set"]["extrude"]["black_mm"]},
            "canvas": {"features": landing["canvas"]["features"], "ids": len(set(landing["canvas"]["ids"]))}}
    (MEDIA / "facts.json").write_text(json.dumps(used, indent=2, ensure_ascii=False) + "\n")
    encode_canvas()
    encode_fusion()


def encode_canvas() -> None:
    """The marker maker on a canvas: muted, looping, with its end state as the poster."""
    marks = json.loads((SRC / "canvas.marks.json").read_text())
    a, da, b, db = CANVAS_SPAN
    start, end = marks[a] + da, marks[b] + db
    crop = ":".join(map(str, CANVAS_CROP))
    run([FFMPEG, "-v", "error", "-y", "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(SRC / "canvas.webm"),
         "-vf", f"crop={crop},format=yuv420p", "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-r", "25",
         "-movflags", "+faststart", "-an", str(MEDIA / "canvas.mp4")])
    at = marks[CANVAS_POSTER_AT[0]] + CANVAS_POSTER_AT[1]
    run([FFMPEG, "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", str(SRC / "canvas.webm"), "-frames:v", "1",
         "-vf", f"crop={crop}", "-q:v", "4", str(MEDIA / "canvas-poster.jpg")])


def encode_fusion() -> None:
    """The add-in in Fusion 360, sped up, muted and looping, with a poster from its middle."""
    raw = next((p for p in (SRC / "fusion.mp4", SRC / "fusion.webm") if p.exists()), None)
    if raw is None:
        return
    out = MEDIA / "fusion.mp4"
    run([FFMPEG, "-v", "error", "-y", "-i", str(raw), "-vf", f"setpts=PTS/{FUSION_SPEED},scale=960:-2:flags=lanczos,format=yuv420p",
         "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-r", "25", "-movflags", "+faststart", "-an", str(out)])
    duration = float(run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)]).strip())
    run([FFMPEG, "-v", "error", "-y", "-ss", f"{duration / 2:.2f}", "-i", str(out), "-frames:v", "1",
         "-q:v", "4", str(MEDIA / "fusion-poster.jpg")])


# ---------------------------------------------------------------- the page

def esc(s: str) -> str:
    return html.escape(s, quote=True)


def img(name: str, alt: str, eager: bool = False) -> str:
    path = MEDIA / f"{name}.webp"
    w, h = size_of(path)
    return (f'<img src="/about/media/{name}.webp" width="{w}" height="{h}" alt="{esc(alt)}"'
            f'{"" if eager else " loading=\"lazy\""} decoding="async">')


def fig(name: str, alt: str, caption: str = "") -> str:
    cap = f"<figcaption>{caption}</figcaption>" if caption else ""
    return f'<figure class="shot">{img(name, alt)}{cap}</figure>'


def row(*figs: str) -> str:
    return f'<div class="row row-{len(figs)}">{"".join(figs)}</div>'


def quote(text: str) -> str:
    return f'<blockquote><p>“{esc(text)}”</p><cite>Zach Yamaoka, project notes</cite></blockquote>'


JSON_LD = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": "ArUco Studio",
    "url": f"{SITE}/",
    "description": "Pick a profile, get a printable, CAD-ready ArUco / ChArUco marker. Runs in your browser.",
    "applicationCategory": "DesignApplication",
    "operatingSystem": "Web",
    "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
    "image": f"{SITE}/og.png",
    "sameAs": [GITHUB],
}


def features(facts: dict) -> str:
    names = facts["tabs"]
    tabs = f"{len(names)} tabs: " + ", ".join(f"<em>{esc(t)}</em>" for t in names[:-1]) + f" and <em>{esc(names[-1])}</em>"
    h = facts["heights"]
    canvas = facts["canvas"]
    canvas_w, canvas_h = size_of(MEDIA / "canvas.mp4")
    sheet = facts["sheet"]
    few_sheets, few_cuts = sheet["spaced40/fewest_sheets"], sheet["spaced40/fewest_cuts"]
    plural = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"
    v = facts["verify"]
    return f"""
<section class="feature" id="profile">
  <h3>The profile</h3>
  <p>A marker starts from a profile, the way an extrude does. Click inside a face and press <kbd>A</kbd>
  (<em>ArUco Extrude</em>): the marker is placed for you in the largest clear spot, avoiding the holes or ignoring
  them. Want it somewhere exact? Draw a rectangle (<kbd>R</kbd>) and double-click it to pick its outer edges as the
  profile: the marker goes exactly there. The <em>ArUco Extrude</em> panel opens beside the marker, in {tabs}.</p>
  <figure class="shot"><picture><source srcset="/about/media/inspect-dark.webp" media="(prefers-color-scheme: dark)">{img("inspect", "The plate example: a single ArUco marker placed in the clear space between two holes, with the ArUco Extrude panel open beside it")}</picture>
  <figcaption>File › Examples › Plate: click between the holes, press A.</figcaption></figure>
</section>

<section class="feature" id="types">
  <h3>Single, Grid or ChArUco</h3>
  <p>One word switches the type. A grid lays out several markers with consecutive ids; a ChArUco board puts
  the markers in a checkerboard for camera calibration. Every OpenCV predefined dictionary is there, AprilTag included.</p>
  {row(fig("type-single", "A single ArUco marker on the plate", "Single"),
       fig("type-grid", "A 2 × 2 grid of ArUco markers on the plate", "Grid"),
       fig("type-charuco", "A ChArUco board on the plate", "ChArUco"))}
</section>

<section class="feature" id="driven">
  <h3>Driven or set: every value is real</h3>
  <p>No “Auto” switches. Each field shows the actual value: in grey when the core worked it out, in black once you
  type it. A typed value is kept until you press ↺, which hands it back to the core. A value that no longer fits
  turns red but never blocks you.</p>
  {row(fig("driven", "The panel rows with the marker size, separation and columns in grey: driven", "Driven: the core sized the grid to fill the profile."),
       fig("set", "The same rows after typing a 16 mm marker: the size is black, with a reset arrow", "Set: 16 mm typed; the note says how it lands on whole printer dots."))}
</section>

<section class="feature" id="auto-id">
  <h3>Auto id</h3>
  <p>Every marker gets its own id without you keeping a list. A stable key per marker is hashed to a preferred id, and
  the file keeps a ledger, so adding or removing other markers never moves an id already given out. Type an id to
  override it; a clash shows red under ID.</p>
  {fig("autoid", "Two markers on a blank sketch, each with its own id, the second one's panel open on the Marker tab")}
</section>

<section class="feature" id="canvas">
  <h3>A marker maker on a canvas</h3>
  <p>The sketch is a small sketcher of its own, so a batch of markers takes seconds. Type a rectangle's width and height
  while you draw it, place a driving dimension with <kbd>D</kbd>, right-drag a window round several, and press <kbd>A</kbd>
  once: one marker in each, each with its own id. <kbd>Ctrl</kbd>+<kbd>C</kbd> / <kbd>Ctrl</kbd>+<kbd>V</kbd> copies
  rectangles and markers together, and the copies get new ids.</p>
  <figure class="shot clip"><video src="/about/media/canvas.mp4" poster="/about/media/canvas-poster.jpg" width="{canvas_w}" height="{canvas_h}"
    autoplay muted loop playsinline controls preload="metadata"
    aria-label="Recording of the Studio: four rectangles typed while drawing, a dimension from the Y axis, a window round them, A, then copy and paste">
    <img src="/about/media/canvas-poster.jpg" alt="Eight ArUco markers on a blank sketch, each with its own id"></video>
  <figcaption>Recorded on arucostudio.com: four typed rectangles, <kbd>D</kbd> to line one up with the Y axis, a window,
  <kbd>A</kbd>, then copy and paste: {canvas['features']} markers, {canvas['ids']} ids.</figcaption></figure>
</section>

<section class="feature" id="trim">
  <h3>Trim</h3>
  <p>What the sticker is cut to: the profile (the whole face, holes cut out) or just the marker and its quiet zone.
  Everything inside the cut is white. For a rectangular sticker, draw a rectangle profile and trim to Profile.</p>
  {row(fig("trim-profile", "Trim Profile: the whole plate face is white", "Profile"),
       fig("trim-marker", "Trim Marker: only the marker and its quiet zone are white", "Marker"))}
</section>

<section class="feature" id="heights">
  <h3>Heights on the model</h3>
  <p>Press <kbd>3</kbd> (or the 2D | 3D toggle) to see the marker as solids. Each height has a drag arrow and a value box
  on the model, like an extrude in CAD. The black is measured from the white's outer face. Every height is driven from
  the preset's layers; drag or type to override any one, and ↺ hands it back.</p>
  {row(fig("heights-driven", "The 3D view of a tile with a marker: an arrow up out of the white with 2.00 mm, an arrow down into the black with 0.60 mm, both grey",
           f"Driven: the {esc(h['preset'])} 3D print preset gives white {h['white_mm']:.2f} mm, black {h['black_mm']:.2f} mm."),
       fig("heights-set", "The same tile with the black's box typed to 1.20 mm, with a reset arrow; the white still grey",
           f"Black typed to {h['set_black_mm']:.2f} mm; the white stays driven."))}
</section>

<section class="feature" id="layout">
  <h3>Auto layout: Fewest cuts or Fewest sheets</h3>
  <p>The Sheet packs every sticker onto the page for you. Every cut runs edge to edge, so scissors or a paper trimmer
  can follow it. <em>Tight</em> lets neighbours share cut lines; <em>Spaced</em> leaves a gap round each one. Then pick
  what matters: fewer straight cuts, or fewer pages.</p>
  {row(fig("sheet-sheets", "The Sheet with eight stickers on one page", f"Fewest sheets: {plural(few_sheets['pages'], 'page')}, {few_sheets['cuts']} straight cuts."),
       fig("sheet-cuts", "The same eight stickers over two pages with fewer cuts", f"Fewest cuts: {plural(few_cuts['pages'], 'page')}, {few_cuts['cuts']} straight cuts."))}
</section>

<section class="feature" id="print">
  <h3>Print at true scale</h3>
  <p>The page is drawn in real millimetres, with a 50 mm scale bar to check against a ruler. Print it, or download
  the page as PDF or SVG.</p>
  {fig("print", "The Sheet at actual size: the plate's sticker with its label, the 50 mm scale bar above")}
</section>

<section class="feature" id="verify">
  <h3>Verify with OpenCV, in the browser</h3>
  <p>OpenCV's own ArUco detector reads a simulated camera view of exactly what you will print. Drag tilt, yaw, blur,
  noise, glare and occlusion; an angle sweep runs for every marker, and a camera calculator turns distance,
  resolution and field of view into pixels per cell and a verdict.</p>
  {fig("verify", "Verify: OpenCV reads marker 35 at 50 degrees of tilt, with the angle sweep and the camera calculator",
       f"Measured on the live site: “{esc(v['legend'])}”; at 1500 mm with a 1920 px, 70° camera: “{esc(v['calc']['text'])}”.")}
</section>
"""


def page(facts: dict) -> str:
    icon = ICON.read_text().strip().replace("<svg ", '<svg class="logo" aria-hidden="true" ', 1)
    hero_w, hero_h = size_of(MEDIA / "hero.mp4")
    ready = facts.get("core_ready_s") or []
    ready_txt = f"{min(ready):.0f}–{max(ready):.0f} s" if ready else "a few seconds"
    qa = [
        ("How do I print at true scale?",
         "Print at 100 % (Scale: Default or Actual size). “Fit to page” changes the marker’s size. Every page carries "
         "a 50 mm scale bar: measure it with a ruler before you cut."),
        ("Which dictionary should I use?",
         "Start with the default, 4X4_50. Fewer bits means bigger cells for the same marker size, so a 4 × 4 marker reads "
         "from further away. Move to a bigger dictionary (4X4_100 up to 1000, or 5X5, 6X6, 7X7) only when you need more "
         "ids than it has. Every OpenCV predefined dictionary is listed with its id count, AprilTag 36h11 included."),
        ("Does anything leave my browser?",
         "No. There is no server: the Python core runs on your machine through Pyodide (WebAssembly). The network "
         "loads the Studio, Pyodide and the core from arucostudio.com, plus numpy and OpenCV (about 13 MB) from the "
         "jsDelivr CDN the first time you open Verify. Your design stays in the page until you Save it to a file; "
         "your own presets and camera settings are kept in this browser’s local storage."),
        ("Will a camera read it?",
         "Open Verify: OpenCV’s detector reads a simulated camera view of the marker exactly as planned, through tilt, "
         "blur, noise, glare and occlusion, and the camera calculator says how far away it should still read. "
         "It is a simulation, so a test with your real camera is still the last word."),
        ("Is it open source?",
         "The source is public on GitHub. A licence has not been chosen yet."),
        ("Can I use it in Fusion 360?",
         f"Not yet. The Fusion 360 add-in is being rebuilt on this same Python core; watch the "
         f"<a href=\"{RELEASES}\">GitHub Releases</a> page for it (see <a href=\"#download\">Download</a>). Until then, "
         "Try Online and export the marker as a true-size SVG or the page as a PDF."),
        ("What does it cost?",
         "Nothing. Try Online is a static website: no account, no sign-up."),
    ]
    qa_html = "\n".join(f'<div class="qa"><h3>{esc(q)}</h3><p>{a}</p></div>' for q, a in qa)
    principles = [
        ("Work at the level of intent",
         "Before, a marker meant sizing by hand, pasting into a drawing tool to print, and keeping id ranges straight yourself.",
         "now with AI you can basically build the tools that make this so much easier so you can work at the level of intent!"),
        ("A functional, CAD-free core",
         "One pure Python core plans every marker. The Studio, the Fusion add-in and the exports only draw what it says.",
         "Aruco Generate should be done where you CAD"),
        ("Auto builds on top of manual",
         "Suggestions and auto layout are a starting point. A typed value always wins, and a warning never blocks you.",
         "You should always get a manual fall back"),
        ("Good defaults",
         "Every field starts with a sensible value, shown in grey, so the first marker takes one click.",
         "cover like 80% of the use cases"),
        ("Simple, focused tools",
         "Markers, labels, layout, verify. Colour boards and the rest are out of scope.",
         "We don't do everything but we do a couple of things really well!"),
        ("WYSIWYG",
         "The label on the sketch is the label on the page is the label in CAD.",
         "What appears on the page should always match exactly what appears in the CAD."),
        ("Still works in 10 years",
         "No account, no server, no heavy framework under the sketch: a static site and a standard-library core (OpenCV only for Verify).",
         "this will still work in 10 years.. as long as there are still aruco markers."),
    ]
    principles_html = "\n".join(
        f'<div class="principle"><h3>{esc(t)}</h3><p>{esc(body)}</p>{quote(q)}</div>' for t, body, q in principles)
    ld = json.dumps(JSON_LD, indent=2, ensure_ascii=False)
    fusion = ""
    if (MEDIA / "fusion.mp4").exists():
        fw, fh = size_of(MEDIA / "fusion.mp4")
        fusion = f"""
  <figure class="hero-media fusion" id="in-fusion">
    <video src="/about/media/fusion.mp4" poster="/about/media/fusion-poster.jpg" width="{fw}" height="{fh}"
      autoplay muted loop playsinline controls preload="metadata"
      aria-label="Recording of the add-in in Fusion 360, sped up {FUSION_SPEED} times">
      <img src="/about/media/fusion-poster.jpg" alt="ArUco Studio's add-in in Fusion 360">
    </video>
    <figcaption>In Fusion 360, sped up {FUSION_SPEED}×.</figcaption>
  </figure>"""
    gh_mark = ('<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 '
               '3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 '
               '1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 '
               '.67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 '
               '3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>')
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!-- Generated by docs/build_landing.py: edit the builder, not this file. -->
<title>{esc(TITLE)}</title>
<meta name="description" content="{esc(DESCRIPTION)}">
<link rel="canonical" href="{SITE}/about/">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta name="color-scheme" content="light dark">
<meta property="og:type" content="website">
<meta property="og:site_name" content="ArUco Studio">
<meta property="og:url" content="{SITE}/about/">
<meta property="og:title" content="{esc(TITLE)}">
<meta property="og:description" content="{esc(DESCRIPTION)}">
<meta property="og:image" content="{SITE}/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(TITLE)}">
<meta name="twitter:description" content="{esc(DESCRIPTION)}">
<meta name="twitter:image" content="{SITE}/og.png">
<script type="application/ld+json">
{ld}
</script>
<style>
:root {{
  --bg: #ffffff; --fg: #191c20; --muted: #5d6570; --line: #e4e7eb; --soft: #f6f7f9;
  --accent: #2f6fed; --accent-fg: #ffffff; --quote: #3a4049;
  color-scheme: light;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #15171a; --fg: #e8eaed; --muted: #9aa2ad; --line: #2c3036; --soft: #1d2024;
    --accent: #5b8ff5; --accent-fg: #0d1117; --quote: #c9ced6;
    color-scheme: dark;
  }}
}}
* {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body {{ margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
a {{ color: var(--accent); }}
img, video {{ max-width: 100%; height: auto; display: block; }}
kbd {{ font: 600 0.85em ui-monospace, SFMono-Regular, Menlo, monospace; border: 1px solid var(--line); border-bottom-width: 2px;
  border-radius: 4px; padding: 0 5px; background: var(--soft); }}
.wrap {{ max-width: 1040px; margin: 0 auto; padding: 0 16px; }}
.text {{ max-width: 720px; }}
nav.top {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 0; }}
.brand {{ display: inline-flex; align-items: center; gap: 8px; font-weight: 650; color: var(--fg); text-decoration: none; }}
.brand .logo {{ width: 24px; height: 24px; }}
.links {{ display: flex; gap: 16px; align-items: center; font-size: 15px; }}
.links a {{ color: var(--muted); text-decoration: none; }}
.links a:hover {{ color: var(--fg); }}
.links a.gh {{ display: inline-flex; color: var(--fg); }}
header.hero {{ text-align: center; padding: 48px 0 28px; }}
header.hero .logo {{ width: 72px; height: 72px; margin: 0 auto 18px; display: block; }}
h1 {{ font-size: clamp(32px, 6vw, 52px); line-height: 1.1; letter-spacing: -0.02em; margin: 0 auto 14px; max-width: 780px; text-wrap: balance; }}
.sub {{ font-size: clamp(17px, 2.4vw, 20px); color: var(--muted); margin: 0 auto 26px; max-width: 640px; text-wrap: balance; }}
.ctas {{ display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }}
.btn {{ display: inline-flex; align-items: center; gap: 8px; padding: 10px 20px; border-radius: 8px; font-weight: 600;
  text-decoration: none; border: 1px solid var(--line); color: var(--fg); background: var(--bg); }}
.btn.primary {{ background: var(--accent); border-color: var(--accent); color: var(--accent-fg); }}
.btn:hover {{ filter: brightness(1.05); }}
.btn[disabled] {{ color: var(--muted); background: var(--soft); cursor: not-allowed; filter: none; font: inherit; font-weight: 600; }}
.note {{ color: var(--muted); font-size: 14px; margin-top: 14px; }}
.hero-media {{ margin: 32px auto 0; border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: var(--soft);
  box-shadow: 0 12px 40px rgba(0,0,0,0.08); }}
.hero-media video {{ width: 100%; }}
.hero-media.fusion {{ margin-top: 28px; }}
.hero-media.fusion figcaption {{ text-align: center; margin: 0; padding: 8px 0; border-top: 1px solid var(--line); }}
.hero-cap {{ color: var(--muted); font-size: 14px; text-align: center; margin: 10px 0 0; }}
main section.block {{ padding: 56px 0 8px; }}
h2 {{ font-size: clamp(24px, 3.4vw, 32px); letter-spacing: -0.01em; margin: 0 0 8px; }}
.lead {{ color: var(--muted); margin: 0 0 8px; }}
.feature {{ padding: 28px 0; border-top: 1px solid var(--line); }}
.feature:first-of-type {{ border-top: 0; }}
.feature h3, .principle h3, .qa h3 {{ font-size: 19px; margin: 0 0 6px; }}
.feature > p {{ max-width: 720px; margin: 0 0 16px; }}
figure.shot {{ margin: 0; }}
figure.shot img, figure.shot.clip video {{ border: 1px solid var(--line); border-radius: 10px; width: 100%; }}
figcaption {{ color: var(--muted); font-size: 14px; margin-top: 6px; }}
.row {{ display: grid; gap: 14px; }}
.row-2 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
.row-3 {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
.principles {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 18px; }}
.principle {{ background: var(--soft); border: 1px solid var(--line); border-radius: 10px; padding: 18px 20px; }}
.principle p {{ margin: 0 0 10px; }}
.principle.first {{ margin: 18px 0 22px; border-left: 4px solid var(--accent); }}
.principle.first h3 {{ font-size: 22px; }}
.principle.first p {{ max-width: 760px; margin: 0; }}
blockquote {{ margin: 0; padding-left: 12px; border-left: 3px solid var(--line); color: var(--quote); }}
blockquote p {{ margin: 0; font-style: italic; }}
blockquote cite {{ display: block; color: var(--muted); font-size: 13px; font-style: normal; margin-top: 4px; }}
.cad {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-top: 18px; }}
.cad div {{ border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px; }}
.cad b {{ display: block; }}
.card-actions {{ display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 14px; }}
.tag {{ display: inline-block; font-size: 12px; font-weight: 600; border-radius: 99px; padding: 1px 9px; margin-top: 6px;
  background: var(--soft); border: 1px solid var(--line); color: var(--muted); }}
.tag.live {{ color: #1a7f37; border-color: #1a7f3755; }}
.qa {{ padding: 18px 0; border-top: 1px solid var(--line); }}
.qa p {{ margin: 0; max-width: 720px; }}
footer {{ border-top: 1px solid var(--line); margin-top: 56px; padding: 28px 0 48px; color: var(--muted); font-size: 14px; }}
footer .ctas {{ justify-content: flex-start; margin-bottom: 16px; }}
@media (max-width: 720px) {{
  /* WHY the triptychs stay three across: the side-by-side comparison is the point */
  .row-2, .principles, .cad {{ grid-template-columns: minmax(0, 1fr); }}
  .row-3 {{ gap: 8px; }}
  header.hero {{ padding-top: 28px; }}
  .links .hide-sm {{ display: none; }}
}}
</style>
</head>
<body>
<div class="wrap">
<nav class="top" aria-label="Site">
  <a class="brand" href="/about/">{icon}<span>ArUco Studio</span></a>
  <span class="links"><a class="hide-sm" href="#philosophy">Philosophy</a><a class="hide-sm" href="#qa">Q&amp;A</a><a class="hide-sm" href="#download">Download</a><a href="/">Try Online</a><a class="gh" href="{GITHUB}" aria-label="GitHub" title="GitHub">{gh_mark.replace('width="16" height="16"', 'width="22" height="22"', 1)}</a></span>
</nav>

<header class="hero">
  {icon.replace('class="logo"', 'class="logo big"', 1)}
  <h1>ArUco markers at the level of intent</h1>
  <p class="sub">Pick a profile, get a printable, CAD-ready ArUco / ChArUco marker. Runs in your browser.</p>
  <div class="ctas">
    <a class="btn primary" href="#download" data-cta="download">Download</a>
    <a class="btn" href="/" data-cta="online">Try Online</a>
  </div>
  <p class="note">Free, no account. The Python core loaded in {ready_txt} in our tests.</p>
  <div class="hero-media">
    <video src="/about/media/hero.mp4" poster="/about/media/hero-poster.jpg" width="{hero_w}" height="{hero_h}"
      autoplay muted loop playsinline controls preload="metadata"
      aria-label="Recording of the Studio: open the plate example, click its face, press A, pick Grid, open the Sheet">
      <img src="/about/media/hero-poster.jpg" alt="The Studio with a grid of ArUco markers on the plate example">
    </video>
  </div>
  <p class="hero-cap">Recorded on arucostudio.com: Examples › Plate, click the face, <kbd>A</kbd>, Marker › Grid, then the Sheet's
  Fewest cuts | Fewest sheets. One cut skips a size and label edit.</p>{fusion}
</header>

<main>
<section class="block" id="what">
  <h2>What it does</h2>
  <p class="lead text">The marker tools of the CAD add-in, in your browser: pick a profile, ArUco Extrude, then print.</p>
  {features(facts)}
</section>

<section class="block" id="philosophy">
  <h2>Philosophy</h2>
  <div class="principle first" id="where-you-cad">
    <h3>Make markers where you CAD</h3>
    <p>A marker is tied to a physical place: the part it is stuck on, where on that part, and how that part sits in
    the rest of the assembly. So it belongs in the CAD model, next to the part, not in a separate generator whose
    output you copy across and line up by hand. That is why the core is CAD-free and the CAD add-ins are thin shells
    over it. Try Online runs the same core, to try it out and to print without CAD.</p>
  </div>
  <p class="lead text">The principles the Studio is built on, with the line each one comes from.</p>
  <div class="principles">
{principles_html}
  </div>
</section>

<section class="block" id="download">
  <h2>Download</h2>
  <p class="text">Install it in your CAD program, or use it online. Nothing to download yet: here is where each one stands.</p>
  <div class="cad">
    <div class="card" data-cad="fusion"><b>Fusion 360</b>The add-in is being rebuilt on this core.<br><span class="tag">In progress</span>
      <span class="card-actions"><button class="btn" type="button" disabled>Coming soon</button><a href="{RELEASES}">Watch for the release</a></span></div>
    <div class="card" data-cad="onshape"><b>Onshape</b>An Onshape version is planned.<br><span class="tag">Planned</span></div>
    <div class="card" data-cad="online"><b>Online</b>Profile, ArUco Extrude, Sheet, Verify. SVG and PDF export.<br><span class="tag live">Live</span>
      <span class="card-actions"><a class="btn primary" href="/">Try Online</a></span></div>
  </div>
</section>

<section class="block" id="qa">
  <h2>Q&amp;A</h2>
{qa_html}
</section>
</main>

<footer>
  <div class="ctas">
    <a class="btn primary" href="#download">Download</a>
    <a class="btn" href="/">Try Online</a>
  </div>
  ArUco Studio by Zach Yamaoka. Source on <a href="{GITHUB}">GitHub</a>; no licence chosen yet.
  <br><a href="/privacy/">Privacy Policy</a> &middot; <a href="/terms/">Terms of Use</a>
</footer>
</div>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--media", action="store_true", help="re-encode web/public/about/media/ from reports/media/landing-src/")
    args = ap.parse_args()
    if args.media:
        encode_media()
    facts = json.loads((MEDIA / "facts.json").read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "index.html"
    out.write_text(page(facts))
    total = sum(p.stat().st_size for p in OUT_DIR.rglob("*") if p.is_file())
    print(f"wrote {out.relative_to(ROOT)}; /about/ assets {total / 1024:.0f} KB in {sum(1 for p in OUT_DIR.rglob('*') if p.is_file())} files")
    for p in sorted(MEDIA.iterdir()):
        print(f"  {p.name:24s} {p.stat().st_size / 1024:7.0f} KB")
    if total > BUDGET:
        print(f"over the {BUDGET // 1024} KB budget", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
