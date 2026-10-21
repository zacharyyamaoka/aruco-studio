"""Builds the canvas-cleanup babble gallery: ten proposals for calming the
visual UI/UX of the online ArUco Studio (https://arucostudio.com), each drawn
over the SAME document captured from the live site.

Zach, 2026-10-21: "Please dispatch agent to make 10 proposals for how to
clean up the visual UI/UX of the online aruco studio. it feels a bit visually
busy..." -- his screenshot: 8 single markers and a ChArUco, every one with two
sketch dims, a red/green Joint Origin, a "#0 · 4X4_50 · 28.0 mm" info label, a
dashed profile box and a corner triangle, the turn arc on the focused one, the
ArUco Extrude panel on top.

The steps (each re-runnable; the captures are kept unless --recapture):

1. capture  a temporary web/.ui-cleanup-capture.cjs (playwright, channel
            "chrome", deleted afterwards) opens the live site headless, opens
            the documents below through File > Open from this computer, and
            per scene keeps: today's screenshot, the printed geometry alone
            (the sticker whites and the marker blacks, the corner marks with
            them) on a transparent page, the app's own chrome (top pills,
            toolbar) alone, the panel alone, and the canvas chrome as the live
            SVG markup (grid, ruler, profile edges, outlines, sketch dims,
            Joint Origins, info labels; the focused marker's dims, turn arc
            and handles) with the app's own .vp-svg CSS and token values.
2. gallery  every variant re-renders that live chrome over the captured
            printed geometry: the same SVG, its own CSS deciding what shows
            in which state, plus its own overlays (chips, list, popover).
            The babble skill's gallery.py builds the page; the images, the
            scenes' markup and one small script go in once (not per variant).
3. review   a temporary web/.ui-cleanup-review.cjs drives the built gallery
            at 1280 and 390: every story step of every card, live hover, the
            direct clicks; the renders are looked at before handing over.

Prototype boundary: the printed geometry, the chrome's geometry and styling,
the panel and the top chrome are the live site's own pixels and markup; which
chrome shows when, and the new overlays, are this mock's. Nothing in web/ is
changed.

Run:  python3 /home/bam/aruco-studio/docs/build_ui_cleanup_proposals.py [--recapture]
Out:  reports/media/studio-ui-cleanup-proposals-2026-10-21.html (gitignored),
      its captures and renders in reports/media/studio-ui-cleanup-proposals-2026-10-21-src/
"""
from __future__ import annotations

import argparse
import base64
import html
import io
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path("/home/bam/aruco-studio")
WEB = REPO / "web"
NAME = "studio-ui-cleanup-proposals-2026-10-21"
OUT = REPO / "reports" / "media" / f"{NAME}.html"
SRC = REPO / "reports" / "media" / f"{NAME}-src"
SHOTS = SRC / "shots"
RENDERS = SRC / "renders"
DOCS = SRC / "docs"
GALLERY = Path.home() / "zach_brain" / "Settings" / "Skills" / "babble" / "scripts" / "gallery.py"
LIVE = "https://arucostudio.com/"
E = html.escape

VIEW = (1440, 900)   # a common laptop window; the fit zoom is the app's own at this size
DPR = 2              # crisp when Focus shows a stage near 1:1


# ---------------------------------------------------------------- the documents
# Doc A is Zach's screenshot rebuilt: eight 37.48 mm rectangle profiles, each
# dimensioned (two driving sketch dims) and given a single 4X4_50 marker with
# the corner triangle, and a 50.8 x 200 rectangle with a 2 x 8 ChArUco (#8-15);
# View > Marker info on. Doc A-bad is the same with #5's marker typed to 36 mm
# (it no longer fits: the plan's overflow), for the exception state. Doc B is a
# 24-marker sheet for the "20+ markers" legibility test.

SQ = 37.48


def _rect(rid: str, cx: float, cy: float, w: float, h: float) -> dict:
    return {"kind": "rect", "id": rid, "cx": cx, "cy": cy, "w": w, "h": h, "angle_deg": 0}


def _dims(rid: str, w: float, h: float, off: float = 3.0, hoff: float | None = None) -> list[dict]:
    hoff = off if hoff is None else hoff
    return [{"id": f"dw-{rid}", "kind": "w", "shape": rid, "value": w, "at": [0, h / 2 + off]},
            {"id": f"dh-{rid}", "kind": "h", "shape": rid, "value": h, "at": [-(w / 2 + hoff), 0]}]


def _feature(k: int, typ: str = "single", cols: int = 1, rows: int = 1) -> dict:
    sets = ["marker.corner_mark"] + (["marker.type", "marker.cols", "marker.rows"] if typ != "single" else [])
    return {"id": f"f{k}", "key": f"f{k}", "profile": {"outer": f"r{k}", "holes": []}, "holes": "avoid", "trim": "profile",
            "marker": {"type": typ, "dictionary": "DICT_4X4_50", "first_id": k, "auto": True, "marker_mm": 30, "checker_mm": 0,
                       "separation_mm": 0, "cols": cols, "rows": rows, "turn": 0, "flip": False, "quiet_modules": 1,
                       "corner_mark": "triangle"},
            "label": {"on": False, "text": "#{ids}", "height_mm": 0, "side": "below", "gap_mm": 2, "offset_mm": [0, 0]},
            "extrude": {}, "preset": None, "set": sets}


def _doc(name: str, shapes: list, dims: list, feats: list) -> dict:
    return {"format": "arucostudio-web", "version": 4, "name": name, "shapes": shapes, "dims": dims, "features": feats,
            "id_ledger": {f["key"]: f["marker"]["first_id"] for f in feats}, "default_preset": None}


def documents() -> dict[str, dict]:
    shapes, dims, feats = [], [], []
    for k in range(8):
        row, col = divmod(k, 4)
        shapes.append(_rect(f"r{k}", col * 43.5, -row * 51.0, SQ, SQ))
        dims += _dims(f"r{k}", SQ, SQ)
        feats.append(_feature(k))
    shapes.append(_rect("r8", 206.0, -21.0, 50.8, 200.0))
    dims += _dims("r8", 50.8, 200.0, off=3.0, hoff=19.0)
    charuco = _feature(8, "charuco", 2, 8)
    feats.append(charuco)
    a = _doc("Marker set", shapes, dims, feats)
    bad = json.loads(json.dumps(a))
    f5 = bad["features"][5]
    f5["marker"].update(auto=False, marker_mm=36)       # isSet("marker.marker_mm") is auto == false
    shapes, dims, feats = [], [], []
    for k in range(24):
        row, col = divmod(k, 6)
        shapes.append(_rect(f"r{k}", col * 40.0, -row * 46.0, 30.0, 30.0))
        dims += _dims(f"r{k}", 30.0, 30.0)
        feats.append(_feature(k))
    b = _doc("Sticker sheet", shapes, dims, feats)
    return {"A": a, "Abad": bad, "B": b}


# ---------------------------------------------------------------- 1. capture
CAPTURE_JS = r"""
// Generated by docs/build_ui_cleanup_proposals.py -- the live site, headless. Deleted after the run.
const { chromium } = require("@playwright/test");
const fs = require("fs");
const CFG = %(cfg)s;
const [W, H] = CFG.view;

// the printed geometry alone: the sticker whites and the marker blacks (the corner mark is in the black)
const ONLY_PRINT = `body *{visibility:hidden!important}
  .vp-svg .whites,.vp-svg .whites *,.vp-svg [data-marker-black]{visibility:visible!important}
  html,body,#root,.app,.stage,.viewport{background:transparent!important}`;
// the app's own chrome alone: everything but the canvas and the panel
const ONLY_CHROME = `.viewport,[data-testid="extrude-panel"],.toast,.vp-hint{visibility:hidden!important}
  html,body,#root,.app,.stage{background:transparent!important}`;
// the panel alone, with its own shadow
const ONLY_PANEL = `body *{visibility:hidden!important}
  [data-testid="extrude-panel"],[data-testid="extrude-panel"] *{visibility:visible!important}
  html,body,#root,.app,.stage,.viewport{background:transparent!important}`;

async function boot(b) {
  const p = await b.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: CFG.dpr });
  // WHY: View > Marker info is a per-viewer setting (store.ts MARKER_INFO_KEY); Zach's screenshot has it on
  await p.addInitScript(() => { try { localStorage.setItem("arucoStudio.markerInfo", "1"); } catch {} });
  p.on("pageerror", (e) => console.error("pageerror", e.message));
  await p.goto(CFG.live);
  await p.getByTestId("viewport").waitFor();
  await p.waitForFunction(() => window.__aruco && window.__aruco.state().core.state === "ready", null, { timeout: 120000 });
  await p.evaluate(() => window.__aruco.idle(45000));
  return p;
}

async function openDoc(p, file) {
  await p.getByTestId("menu-main").click();
  await p.getByTestId("menu-file").hover();
  await p.waitForTimeout(250);
  const fc = p.waitForEvent("filechooser", { timeout: 15000 });
  await p.getByTestId("cmd-open").click();
  await (await fc).setFiles(file);
  await p.waitForTimeout(900);
  await p.evaluate(() => window.__aruco.idle(45000));
  await p.addStyleTag({ content: ".toast{display:none!important}" });
  await park(p);
}

async function park(p) { await p.mouse.move(W - 3, H / 2); await p.waitForTimeout(350); }

async function alpha(p, css, path) {
  const tag = await p.addStyleTag({ content: css });
  await p.waitForTimeout(200);
  await p.screenshot({ path, omitBackground: true });
  await tag.evaluate((e) => e.remove());
  await p.waitForTimeout(150);
}

// the canvas chrome as live markup, its boxes, the app's CSS for it and the token values it reads
const GEOM = () => {
  const svg = document.querySelector(".vp-svg");
  const vp = document.querySelector('[data-testid="viewport"]').getBoundingClientRect();
  const q = (s) => [...svg.querySelectorAll(s)];
  const one = (s) => svg.querySelector(s)?.outerHTML ?? null;
  const bb = (e) => { const b = e.getBBox(); return [b.x, b.y, b.x + b.width, b.y + b.height].map((v) => +v.toFixed(2)); };
  const css = [];
  for (const sh of document.styleSheets) {
    let rules; try { rules = sh.cssRules; } catch { continue; }
    for (const r of rules) if (r.selectorText && /\.vp-svg|cad-dim|sk-dims/.test(r.selectorText)) css.push(r.cssText);
  }
  const markup = svg.outerHTML;
  const names = [...new Set([...(css.join(" ") + markup).matchAll(/var\((--[\w-]+)/g)].map((m) => m[1]))];
  const cs = getComputedStyle(document.querySelector('[data-testid="viewport"]'));
  const vars = Object.fromEntries(names.map((n) => [n, cs.getPropertyValue(n).trim()]));
  const s = window.__aruco.state();
  const plans = Object.fromEntries(Object.entries(s.plans).map(([k, v]) => [k, {
    ids: v.ids, marker_mm: v.marker_mm, outer_mm: v.outer_mm, overflow_mm: v.overflow_mm, summary: v.summary,
    warnings: (v.warnings || []).map((w) => (typeof w === "string" ? w : w.message || JSON.stringify(w))) }]));
  return {
    vp: [vp.x, vp.y, vp.width, vp.height], camera: s.camera, sel: s.sel, panel: s.panel.open,
    font: getComputedStyle(svg).fontFamily, canvas: getComputedStyle(document.querySelector(".stage")).backgroundColor,
    defs: one("defs"), grid: one(".grid"), ruler: one(".ruler"),
    edges: q("[data-shape]").map((e) => ({ id: e.dataset.shape, html: e.outerHTML, bb: bb(e) })),
    outlines: q("[data-marker]").map((g) => ({ fid: g.dataset.marker, on: g.classList.contains("on"),
      html: g.querySelector(".outline").outerHTML, bb: bb(g.querySelector(".outline")) })),
    sdims: one('[data-testid="sketch-dims"]'),
    sdimBoxes: q("[data-sketch-dim]").map((e) => ({ id: e.dataset.sketchDim, bb: bb(e) })),
    triads: q(".triad").map((e) => ({ fid: e.dataset.feature, html: e.outerHTML, bb: bb(e),
      o: [+e.querySelector(".ax-o").getAttribute("cx"), +e.querySelector(".ax-o").getAttribute("cy")] })),
    infos: q('[data-testid="marker-info"]').map((e) => ({ fid: e.dataset.feature, html: e.outerHTML, text: e.textContent, bb: bb(e) })),
    fdims: one('[data-testid="dims"]'), fdimBoxes: q('[data-testid="dims"] [data-dim]').map((e) => ({ f: e.dataset.dim, bb: bb(e) })),
    arc: one('[data-testid="turn-arc"]'), handles: one(".handles"),
    css, vars, plans,
  };
};

const PANEL = () => {
  const pn = document.querySelector('[data-testid="extrude-panel"]');
  if (!pn) return null;
  const r = (e) => { const b = e.getBoundingClientRect(); return [b.x, b.y, b.width, b.height].map((v) => +v.toFixed(1)); };
  // the smallest element whose text contains t
  const smallest = (t) => {
    let best = null;
    for (const e of pn.querySelectorAll("*")) {
      if (!(e.textContent || "").includes(t)) continue;
      if (!best || best.contains(e)) best = e;
    }
    return best ? { text: best.textContent.trim(), box: r(best) } : null;
  };
  return {
    box: r(pn), head: r(pn.querySelector(".fpanel-head")), tabs: r(pn.querySelector('[role="tablist"]')),
    body: r(pn.querySelector(".tab-body")), foot: r(pn.querySelector(".fpanel-foot")),
    summary: r(pn.querySelector(".summary-line")), actions: r(pn.querySelector(".xp-actions")),
    groups: [...pn.querySelectorAll(".xp-group")].map((g) => ({ title: g.dataset.groupTitle, box: r(g) })),
    notes: [...pn.querySelectorAll(".hint-line, .kit-msg, [class*=msg], [class*=hint]")].map((e) => ({ cls: String(e.className), text: e.textContent.trim().slice(0, 120), box: r(e) })),
    corner: smallest("corner mark: a black"), mode: smallest("mode auto"),
  };
};

const rect = (p, s) => p.evaluate((sel) => {
  const e = document.querySelector(sel); if (!e) return null;
  const b = e.getBoundingClientRect(); return [b.x, b.y, b.width, b.height];
}, s);

(async () => {
  const b = await chromium.launch({ channel: "chrome" });
  const S = CFG.shots, facts = { view: CFG.view, dpr: CFG.dpr, scenes: {}, panels: {} };

  // ---- doc A: calm, then #3 being edited (Marker tab, then Label tab as in Zach's screenshot)
  let p = await boot(b);
  await openDoc(p, CFG.docs.A);
  facts.scenes.A = await p.evaluate(GEOM);
  await p.screenshot({ path: `${S}/today-A-calm.png` });
  await alpha(p, ONLY_PRINT, `${S}/print-A.png`);
  await alpha(p, ONLY_CHROME, `${S}/chrome-A-calm.png`);
  facts.chromeBoxes = { topbar: await rect(p, '[data-testid="doc-pill"]'), actions: await rect(p, '[data-testid="actions-pill"]'),
    toolbar: await rect(p, '[data-testid="toolbar"]'), corner: await rect(p, '[data-testid="corner"]') };
  const [cx, cy] = await p.evaluate(() => window.__aruco.toClient(130.5, 0));
  await p.mouse.click(cx, cy);
  await p.waitForTimeout(500);
  await p.evaluate(() => window.__aruco.idle(45000));
  await park(p);
  facts.scenes.Aedit = await p.evaluate(GEOM);
  facts.panels.marker = await p.evaluate(PANEL);
  await alpha(p, ONLY_PANEL, `${S}/panel-marker.png`);
  await alpha(p, ONLY_CHROME, `${S}/chrome-A-edit.png`);
  await p.screenshot({ path: `${S}/today-A-edit-marker.png` });
  await p.locator('[data-testid="extrude-panel"] [role=tab][data-tab="label"]').click();
  await p.waitForTimeout(400);
  await park(p);
  facts.panels.label = await p.evaluate(PANEL);
  await alpha(p, ONLY_PANEL, `${S}/panel-label.png`);
  await p.screenshot({ path: `${S}/today-A-edit.png` });
  // ---- A, zoomed in on the grid of eight (the near rung of a zoom ladder)
  await p.keyboard.press("Escape");
  await p.waitForTimeout(300);
  const [gx, gy] = await p.evaluate(() => window.__aruco.toClient(65.25, -25.5));
  await p.mouse.move(gx, gy);
  for (let i = 0; i < 3; i++) { await p.mouse.wheel(0, -240); await p.waitForTimeout(250); }
  await p.waitForTimeout(400);
  await park(p);
  facts.scenes.Anear = await p.evaluate(GEOM);
  await alpha(p, ONLY_PRINT, `${S}/print-Anear.png`);
  await p.screenshot({ path: `${S}/today-A-near.png` });
  await p.close();

  // ---- doc A-bad: #5 typed to 36 mm, no longer fits its profile
  p = await boot(b);
  await openDoc(p, CFG.docs.Abad);
  facts.scenes.Abad = await p.evaluate(GEOM);
  await alpha(p, ONLY_PRINT, `${S}/print-Abad.png`);
  await p.screenshot({ path: `${S}/today-Abad.png` });
  await p.close();

  // ---- doc B: 24 markers at fit, then zoomed out
  p = await boot(b);
  await openDoc(p, CFG.docs.B);
  facts.scenes.B = await p.evaluate(GEOM);
  await p.screenshot({ path: `${S}/today-B.png` });
  await alpha(p, ONLY_PRINT, `${S}/print-B.png`);
  await alpha(p, ONLY_CHROME, `${S}/chrome-B.png`);
  const [bx, by] = await p.evaluate(() => window.__aruco.toClient(100, -69));
  await p.mouse.move(bx, by);
  for (let i = 0; i < 4; i++) { await p.mouse.wheel(0, 240); await p.waitForTimeout(250); }
  await p.waitForTimeout(400);
  await park(p);
  facts.scenes.Bfar = await p.evaluate(GEOM);
  await alpha(p, ONLY_PRINT, `${S}/print-Bfar.png`);
  await p.screenshot({ path: `${S}/today-Bfar.png` });
  await p.close();

  await b.close();
  fs.writeFileSync(`${S}/capture.json`, JSON.stringify(facts, null, 1));
  console.log("captured", Object.keys(facts.scenes).join(" "), "| zoom A", facts.scenes.A.camera.zoom.toFixed(2),
    "near", facts.scenes.Anear.camera.zoom.toFixed(2), "B", facts.scenes.B.camera.zoom.toFixed(2), "Bfar", facts.scenes.Bfar.camera.zoom.toFixed(2));
})().catch((e) => { console.error(e); process.exit(1); });
"""


def run_temp_cjs(name: str, js: str, timeout: int) -> subprocess.CompletedProcess:
    """A temporary .cjs in web/ (so require("@playwright/test") resolves), run and always deleted."""
    path = WEB / f".ui-cleanup-{name}.cjs"
    path.write_text(js)
    try:
        return subprocess.run(["node", str(path)], cwd=WEB, check=True, timeout=timeout, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(e.stdout[-3000:], e.stderr[-3000:], sep="\n", file=sys.stderr)
        raise
    finally:
        path.unlink(missing_ok=True)


def capture(force: bool) -> dict:
    facts_file = SHOTS / "capture.json"
    if facts_file.exists() and not force:
        return json.loads(facts_file.read_text())
    SHOTS.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, doc in documents().items():
        path = DOCS / f"{key}.arucostudio-web.json"
        path.write_text(json.dumps(doc, indent=1))
        paths[key] = str(path)
    cfg = {"view": VIEW, "dpr": DPR, "live": LIVE, "shots": str(SHOTS), "docs": paths}
    r = run_temp_cjs("capture", CAPTURE_JS % {"cfg": json.dumps(cfg)}, 900)
    print(r.stdout.strip())
    if r.stderr.strip():
        print(r.stderr.strip(), file=sys.stderr)
    return json.loads(facts_file.read_text())


# ---------------------------------------------------------------- 2. the objective, fixed before any variant was drawn
# WHY these weights (inferred, revisable): Zach's complaint is noise, so the
# calm first screen leads; the chrome exists because editing needs it, so its
# reach is the counterweight; the Studio copies Fusion's dialog and Figma's
# layout (user_specs_by_reference_app); the sticker sheet ("lots of markers on
# a page, then re-id them", 2026-10-20) is the scale test; speed is a value.
REQUIREMENTS = [
    {"id": "fr1", "name": "A calm first screen: the 'is it OK' answer", "weight": 30,
     "why": "Zach: 'it feels a bit visually busy'. His calm-UI rule: the first screen is one calm answer, detail one step deeper.",
     "passCondition": "With nothing selected, doc A reads as markers on a page at a glance, and whether anything needs attention is clear without reading numbers.",
     "anchors": {"1": "Every marker still carries four or more chrome items (two dims, axes, info, a dashed box), as today.",
                 "3": "Clearly quieter, but numbers or axes still repeat on every marker.",
                 "5": "Only the printed markers plus at most one quiet cue each; a problem, if there were one, would stand out."}},
    {"id": "fr2", "name": "What editing needs is one step away", "weight": 25,
     "why": "The dims, the Joint Origin and the ids are on the canvas because editing uses them; hiding them must not cost a hunt.",
     "passCondition": "From the calm screen, any marker's size, axes and id are one hover or one click away, and the edited marker shows all of its own edit chrome.",
     "anchors": {"1": "Something is gone, or reaching it takes a menu plus a toggle.",
                 "3": "One step for the marker being edited; the others need a menu, a mode or a zoom.",
                 "5": "A hover for any marker, a click shows the full edit chrome, nothing lost."}},
    {"id": "fr3", "name": "Feels like the CAD it lives in (Fusion, Figma)", "weight": 15,
     "why": "Zero relearning: the panel is Fusion's feature dialog, the layout Figma's, and the add-ins live inside Fusion and Onshape.",
     "passCondition": "A Fusion or Figma user can predict when chrome appears without being told.",
     "anchors": {"1": "An invented rule no reference app uses.",
                 "3": "Familiar parts in a new combination.",
                 "5": "A named reference app's own convention, used directly."}},
    {"id": "fr4", "name": "Legible on a sheet of 20+ markers", "weight": 15,
     "why": "The sticker-sheet workflow: many markers on one page, then Re-ID; doc B is 24 markers at fit.",
     "passCondition": "On doc B every marker's id can be found at a glance and the sheet does not turn into a texture of repeated numbers.",
     "anchors": {"1": "The repeated chrome becomes a texture; ids hard to find.",
                 "3": "Readable, but either noisy or the ids are hidden until you point.",
                 "5": "Calm, and every id findable at a glance."}},
    {"id": "fr5", "name": "Small to build", "weight": 15,
     "why": "Speed: ship the tracer bullet. Scored as the inverse of the work in web/src (Viewport.tsx, Dims.tsx, SketchDims.tsx, styles.css, the store).",
     "passCondition": "An estimate of the files touched and the new concepts added, read from today's code.",
     "anchors": {"1": "A new subsystem: a list, a mode, a zoom ladder or persisted settings across many files.",
                 "3": "A few days: new state and conditionals in Viewport.tsx plus CSS.",
                 "5": "CSS and a few conditionals in Viewport.tsx and styles.css."}},
]
HARD_GATES = [
    {"id": "g1", "name": "Prints what it shows",
     "why": "Render stored properties truthfully: the sticker white, the marker black, the corner mark and the label are never hidden, recoloured or moved by a chrome change."},
    {"id": "g2", "name": "Nothing is lost",
     "why": "Every piece of today's canvas information (sketch dims, marker dims, Joint Origin, marker info, turn arc, handles) can still be shown."},
]
AXES = [
    {"name": "When chrome appears", "values": ["always (quieter)", "on hover / selection", "by mode", "by command and tab", "by zoom", "by toggle", "on exception"]},
    {"name": "Where per-marker facts live", "values": ["on every marker", "on the focused one", "in a list", "once, in a legend", "in one health chip"]},
    {"name": "Visual weight of what remains", "values": ["today's", "thin and grey", "monochrome + one accent", "none until asked"]},
]
STATES = ["calm", "hover", "edit", "editm", "editmode", "near", "far", "overlays", "overlays-on", "problem"]


# ---------------------------------------------------------------- the images, once each
def webp_uri(path: Path, lossless: bool = True, quality: int = 82, width: int | None = None) -> str:
    """Lossless WebP for the flat layers (lossy rings the white stickers);
    the two 'today' screenshots lossy and at 1x, they are reference only."""
    from PIL import Image
    im = Image.open(path)
    if width and im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    (im if im.mode == "RGBA" else im.convert("RGB")).save(buf, "WEBP", lossless=lossless, quality=quality if not lossless else 100, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


LAYERS = ["print-A", "print-Anear", "print-Abad", "print-B", "print-Bfar", "chrome-A-calm", "chrome-A-edit", "chrome-B",
          "panel-label", "panel-marker"]


def image_css() -> str:
    return ":root{" + "".join(f"--img-{n}:url({webp_uri(SHOTS / f'{n}.png')});" for n in LAYERS) + "}"


def _lucide(name: str) -> str:
    src = (WEB / "node_modules/lucide-react/dist/esm/icons" / f"{name}.mjs").read_text()
    alias = re.search(r"export \{ default \} from '\./([\w-]+)\.mjs'", src)
    if alias:
        return _lucide(alias.group(1))
    node = re.search(r"node:\s*\[(.*)\]\s*\};", src, re.S) or re.search(r"const __iconNode = \[(.*?)\];", src, re.S)
    els = []
    for tag, body in re.findall(r'\[\s*"(\w+)",\s*\{([^}]*)\}\s*\]', node.group(1)):
        kv = [(k, v) for k, v in re.findall(r'(\w+):\s*"([^"]*)"', body) if k != "key"]
        els.append(f"<{tag} " + " ".join(f'{k}="{v}"' for k, v in kv) + "/>")
    assert els, f"lucide {name}: no shapes parsed"
    return "".join(els)


ICONS = {n: _lucide(n) for n in ("eye", "layers", "circle-check", "triangle-alert", "info", "chevron-right", "chevron-down",
                                  "file-text", "pencil", "zoom-in", "zoom-out", "list", "x", "undo-2", "scan")}


def icon(name: str, size: float = 14, cls: str = "") -> str:
    return (f'<svg class="uc-i {cls}" viewBox="0 0 24 24" style="width:calc({size}*var(--u));height:calc({size}*var(--u))" fill="none" '
            f'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


# ---------------------------------------------------------------- 2a. the scenes: the live chrome, tagged per marker
STYLE_RE = re.compile(r"<style>(.*?)</style>", re.S)
INLINE_CSS: dict[str, None] = {}   # the app's own inline <style> blocks (Dims.tsx DIM_CSS, SketchDims CSS), kept once


def strip_styles(markup: str | None) -> str:
    if not markup:
        return ""
    for css in STYLE_RE.findall(markup):
        INLINE_CSS[css.strip()] = None
    return STYLE_RE.sub("", markup)


def scoped(css: str, scope: str) -> str:
    out = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        sels = ", ".join(f"{scope} {x.strip()}" for x in sel.split(","))
        out.append(f"{sels}{{{body}}}")
    return "\n".join(out)


def tag_k(markup: str, k: int, pin: bool, extra: str = "") -> str:
    """data-k on the element's opening tag; 'pin' (the pinned hover demo) and extra classes on its class list."""
    m = re.match(r"<(\w+)", markup)
    head = markup[: m.end()] + f' data-k="{k}"' + markup[m.end():]
    cls = (" pin" if pin else "") + (f" {extra}" if extra else "")
    if cls:
        head = re.sub(r'class="([^"]*)"', lambda c: f'class="{c.group(1)}{cls}"', head, count=1)
    return head


def kid(s: str) -> int:
    return int(re.search(r"(\d+)$", s).group(1))


def ids_text(plan: dict) -> str:
    ids = plan["ids"]
    return f"#{ids[0]}" if len(ids) == 1 else f"#{ids[0]}–{ids[-1]}"


def scene_markup(key: str, sc: dict, edit: dict | None, pin: int | None, clickable: bool, reps: set[int],
                 counts: dict[int, int], chrome: str, panels: dict | None, blockers: dict) -> str:
    """One scene's template: the canvas, the live grid, the printed geometry
    (an image), the live chrome tagged per marker, extras the variants may
    turn on, the app's chrome and panel (images), and the hotspots."""
    W, H = VIEW
    boxes = {kid(o["fid"]): o["bb"] for o in sc["outlines"]}
    info = {kid(i["fid"]): i["text"] for i in sc["infos"]}
    P = lambda k: pin is not None and k == pin  # noqa: E731
    z = sc["camera"]["zoom"]
    # the dot grid (a pattern at the live grid's own pitch and phase)
    xs = sorted({float(x) for x in re.findall(r'<line x1="([\d.\-]+)" x2="\1" y1="0" y2="900"', sc["grid"])})
    major = [float(x) for x in re.findall(r'<line x1="([\d.\-]+)" x2="\1" y1="0" y2="900" class="g major"', sc["grid"])]
    ys = sorted({float(y) for y in re.findall(r'<line y1="([\d.\-]+)" y2="\1" x1="0" x2="1440"', sc["grid"])})
    ymaj = [float(y) for y in re.findall(r'<line y1="([\d.\-]+)" y2="\1" x1="0" x2="1440" class="g major"', sc["grid"])]
    pitch = (xs[-1] - xs[0]) / (len(xs) - 1) if len(xs) > 1 else 20
    mp = pitch * 5
    ox, oy = (major[0] if major else 0) % mp, (ymaj[0] if ymaj else 0) % mp
    dots = "".join(f'<circle cx="{i * pitch:.2f}" cy="{j * pitch:.2f}" r="{1.25 if i == 0 and j == 0 else 0.75}"/>'
                   for i in range(5) for j in range(5))
    under = (f'<svg class="uc-layer vp-svg uc-under" viewBox="0 0 {W} {H}" preserveAspectRatio="none">'
             f'<defs><pattern id="dots-{key}" x="{ox:.2f}" y="{oy:.2f}" width="{mp:.2f}" height="{mp:.2f}" patternUnits="userSpaceOnUse">{dots}</pattern></defs>'
             f'<g class="L-grid">{sc["grid"]}</g><rect class="X X-dots" width="{W}" height="{H}" fill="url(#dots-{key})"/></svg>')

    edges = "".join(tag_k(e["html"], kid(e["id"]), P(kid(e["id"]))) for e in sc["edges"])
    outlines = "".join(f'<g class="marker{" pin" if P(kid(o["fid"])) else ""}" data-k="{kid(o["fid"])}">{o["html"]}</g>' for o in sc["outlines"])
    sd = strip_styles(sc["sdims"])
    sd = re.sub(r'<g class="cad-dim([^"]*)" data-sketch-dim="(d[wh]-r(\d+))"',
                lambda m: f'<g class="cad-dim{m.group(1)}{" pin" if P(int(m.group(3))) else ""}{" rep" if int(m.group(3)) in reps else ""}" '
                          f'data-k="{m.group(3)}" data-sketch-dim="{m.group(2)}"', sd)
    triads = "".join(tag_k(t["html"], kid(t["fid"]), P(kid(t["fid"]))) for t in sc["triads"])
    infos = "".join(tag_k(i["html"], kid(i["fid"]), P(kid(i["fid"]))) for i in sc["infos"])

    def pc(k: int) -> str:
        return " pin" if P(k) else ""
    xh, xt, xb, xf, xc = [], [], [], [], []
    for k, (x0, y0, x1, y1) in sorted(boxes.items()):
        cx = (x0 + x1) / 2
        xh.append(f'<rect class="xh{pc(k)}" data-k="{k}" x="{x0 - 2:.1f}" y="{y0 - 2:.1f}" width="{x1 - x0 + 4:.1f}" height="{y1 - y0 + 4:.1f}" rx="2"/>')
        xf.append(f'<rect class="xf{pc(k)}" data-k="{k}" x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}"/>')
        xt.append(f'<text class="xt{pc(k)}" data-k="{k}" x="{x0:.1f}" y="{y0 - 7:.1f}">{E(info.get(k, ""))}</text>')
        t = ids_text(sc["plans"][f"f{k}"])
        tw = 7.0 * len(t) + 10
        by = min(y1 + 14, H - 30)
        xb.append(f'<g class="xb{pc(k)}" data-k="{k}"><rect class="xb-c" x="{cx - tw / 2:.1f}" y="{by - 9:.1f}" width="{tw:.1f}" height="18" rx="9"/>'
                  f'<text class="xb-t" x="{cx:.1f}" y="{by:.1f}">{E(t)}</text></g>')
        leg = 2.8 * z
        xc.append(f'<circle class="xc{pc(k)}" data-k="{k}" cx="{x0 + leg * 0.36:.1f}" cy="{y0 + leg * 0.36:.1f}" r="{leg * 1.25:.1f}"/>')
    # one dimension per repeated size (V9): a count beside the representative's width value
    xn = []
    for k, n in counts.items():
        m = re.search(rf'data-sketch-dim="dw-r{k}".*?<rect class="chip" x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"', sd, re.S)
        if m and n > 1:
            x, y, w, h = map(float, m.groups())
            xn.append(f'<g class="xn"><rect x="{x + w + 4:.1f}" y="{y:.1f}" width="30" height="{h:.1f}" rx="7.5"/>'
                      f'<text x="{x + w + 19:.1f}" y="{y + h / 2:.1f}">×{n}</text></g>')

    edit_layer = ""
    if edit:
        e3 = [e for e in edit["edges"] if e["id"] == "r3"][0]
        o3 = [o for o in edit["outlines"] if o["fid"] == "f3"][0]
        edit_layer = (f'<g class="L-edit"><g class="E-edges">{e3["html"]}</g><g class="E-outline"><g class="marker on">{o3["html"]}</g></g>'
                      f'<g class="E-fdims">{strip_styles(edit["fdims"])}</g><g class="E-arc">{strip_styles(edit["arc"])}</g>'
                      f'<g class="E-handles">{strip_styles(edit["handles"])}</g></g>')
    over = (f'<svg class="uc-layer vp-svg uc-over" viewBox="0 0 {W} {H}" preserveAspectRatio="none">{sc["defs"]}'
            f'<g class="L-edges">{edges}</g><g class="L-outlines">{outlines}</g>'
            f'<g class="X X-face">{"".join(xf)}</g>'
            f'<g class="L-sdims">{sd}</g><g class="X X-count">{"".join(xn)}</g>'
            f'<g class="L-triads">{triads}</g><g class="L-infos">{infos}</g>'
            f'<g class="X X-corner">{"".join(xc)}</g><g class="X X-hover">{"".join(xh)}</g><g class="X X-tag">{"".join(xt)}</g>'
            f'<g class="X X-badge">{"".join(xb)}</g>{edit_layer}<g class="L-ruler">{sc["ruler"]}</g></svg>')

    def pct(x0, y0, w, h):
        return f"left:{x0 / W * 100:.3f}%;top:{y0 / H * 100:.3f}%;width:{w / W * 100:.3f}%;height:{h / H * 100:.3f}%"
    hots = []
    for k, (x0, y0, x1, y1) in sorted(boxes.items()):
        to = ' data-story-to="edit" title="Click: edit #3"' if clickable and k == 3 else ""
        hots.append(f'<div class="uc-hot{pc(k)}" data-k="{k}"{to} style="{pct(x0, max(y0, 0), x1 - x0, min(y1, H) - max(y0, 0))}"></div>')
    blocks = "".join(f'<div class="uc-block {name}" style="{pct(*b)}"></div>' for name, b in blockers.items() if b)
    imgs = f'<div class="uc-layer uc-img uc-print" style="background-image:var(--img-print-{key})"></div>'
    chrome_imgs = f'<div class="uc-layer uc-img uc-chrome-calm" style="background-image:var(--img-{chrome})"></div>'
    if panels:
        chrome_imgs += ('<div class="uc-layer uc-img uc-chrome-edit" style="background-image:var(--img-chrome-A-edit)"></div>'
                        '<div class="uc-layer uc-img uc-panel uc-panel-label" style="background-image:var(--img-panel-label)"></div>'
                        '<div class="uc-layer uc-img uc-panel uc-panel-marker" style="background-image:var(--img-panel-marker)"></div>')
    bg = '<div class="uc-bg" data-story-to="calm"></div>' if clickable else '<div class="uc-bg"></div>'
    return (f'<template id="uc-t-{key}"><div class="uc-layer uc-canvas"></div>{under}{imgs}{over}{chrome_imgs}'
            f'<div class="uc-layer uc-hots">{bg}{"".join(hots)}{blocks}</div></template>')


def templates(facts: dict) -> str:
    cb = facts["chromeBoxes"]
    pl, pm = facts["panels"]["label"]["box"], facts["panels"]["marker"]["box"]
    base = {"blk-top": cb["topbar"], "blk-act": cb["actions"], "blk-tool": cb["toolbar"], "blk-corner": cb["corner"]}
    a_blk = dict(base, **{"blk-panel-label": pl, "blk-panel-marker": pm})
    S = facts["scenes"]
    rects_a = {(r["w"], r["h"]) for r in documents()["A"]["shapes"]}
    assert rects_a == {(SQ, SQ), (50.8, 200.0)}
    out = [
        scene_markup("A", S["A"], S["Aedit"], 5, True, {0, 8}, {0: 8}, "chrome-A-calm", {"label": 1}, a_blk),
        scene_markup("Anear", S["Anear"], None, 5, True, set(), {}, "chrome-A-calm", None, base),
        scene_markup("Abad", S["Abad"], None, 5, True, set(), {}, "chrome-A-calm", None, base),
        scene_markup("B", S["B"], None, None, False, {0}, {0: 24}, "chrome-B", None, base),
        scene_markup("Bfar", S["Bfar"], None, None, False, set(), {}, "chrome-B", None, base),
    ]
    return "\n".join(out)


# ---------------------------------------------------------------- 2b. shared CSS
def GS(*states: str) -> str:
    """The generic 'in this state' selector: a hero in a prototype at that story state, or an exhibit fixed to it."""
    return ".uc-hero:is(" + ", ".join(f'.prototype[data-story-state="{s}"] .uc-hero, .uc-hero[data-fixed="{s}"]' for s in states) + ")"


def VS(v: str):
    def S(*states: str) -> str:
        return f".uc-hero.{v}:is(" + ", ".join(f'.prototype[data-story-state="{s}"] .uc-hero, .uc-hero[data-fixed="{s}"]' for s in states) + ")"
    return f".uc-hero.{v}", S


def base_css(facts: dict) -> str:
    A = facts["scenes"]["A"]
    tokens = "".join(f"{k}:{v};" for k, v in A["vars"].items())
    css = [f".uc-hero{{{tokens}position:relative;width:100%;container-type:inline-size;--u:calc(100cqw / {VIEW[0]});"
           "font-family:var(--font);color:var(--text);line-height:1.3;text-align:left}",
           ".uc-stage{position:relative;width:100%;aspect-ratio:1440 / 900;overflow:hidden;background:var(--canvas)}",
           ".uc-layer{position:absolute;inset:0}",
           ".prototype .uc-stage svg.uc-layer, .media-surface .uc-stage svg.uc-layer{width:100%;height:100%;max-width:none;display:block}",
           ".uc-stage svg *{pointer-events:none!important}",
           ".uc-img{background-size:100% 100%;background-repeat:no-repeat;pointer-events:none}",
           ".uc-canvas{background:var(--canvas)}",
           ".uc-hots>*{position:absolute}.uc-bg{inset:0}.uc-hot[data-story-to]{cursor:pointer}.uc-block{cursor:default}",
           ".uc-abs{position:absolute;box-sizing:border-box}",
           ".prototype .uc-hero :is(.uc-abs, .uc-hot).story-target{position:absolute}",
           ".prototype .uc-hero .uc-hot.story-target{outline-offset:4px}",
           ".X,.L-edit,.uc-chrome-edit,.uc-panel,.blk-panel-label,.blk-panel-marker{display:none}",
           # the extras' own look
           ".uc-stage .xh{fill:none;stroke:var(--accent);stroke-width:1.5}",
           ".uc-stage pattern circle{fill:rgba(25,35,50,.30)}",
           ".uc-stage .xf{fill:color-mix(in srgb,var(--accent) 10%,transparent);stroke:var(--accent);stroke-width:1}",
           ".uc-stage .xt{fill:var(--accent);font:600 11px var(--font)}",
           ".uc-stage .xb-c{fill:var(--panel);stroke:var(--line);stroke-width:1}",
           ".uc-stage .xb-t{fill:var(--text);font:600 10.5px var(--font);text-anchor:middle;dominant-baseline:central}",
           ".uc-stage .xc{fill:none;stroke:var(--accent);stroke-width:1.6}",
           ".uc-stage .xn rect{fill:var(--panel);stroke:var(--line)}.uc-stage .xn text{fill:var(--text);font:600 10.5px var(--font);text-anchor:middle;dominant-baseline:central}",
           # the selected state, as today (variants override with their own, more specific, rules)
           f"{GS('edit', 'editm')} .L-edit{{display:inline}}",
           f"{GS('edit', 'editm')} :is(.L-sdims .cad-dim, .L-edges>path, .L-outlines>.marker)[data-k=\"3\"]{{display:none}}",
           f"{GS('edit', 'editm')} .uc-chrome-calm{{display:none}}",
           f"{GS('edit', 'editm')} .uc-chrome-edit{{display:block}}",
           f"{GS('edit')} :is(.uc-panel-label,.blk-panel-label){{display:block}}",
           f"{GS('editm')} :is(.uc-panel-marker,.blk-panel-marker){{display:block}}",
           # the overlays' look: the app's pills (kit tokens)
           ".uc-pill{background:var(--panel);border:1px solid var(--line);border-radius:calc(12*var(--u));"
           "box-shadow:0 1px 2px rgba(16,24,40,.05),0 6px 20px rgba(16,24,40,.07);font-size:calc(12.5*var(--u))}",
           ".uc-seg{display:flex;gap:calc(2*var(--u));padding:calc(4*var(--u))}",
           ".uc-seg>button{all:unset;display:flex;align-items:center;gap:calc(6*var(--u));padding:calc(6*var(--u)) calc(12*var(--u));"
           "border-radius:calc(8*var(--u));color:var(--muted);font-weight:600;cursor:pointer;font-size:calc(12.5*var(--u))}",
           ".uc-seg>button:hover{background:var(--panel-2)}",
           ".uc-seg>button.on{background:var(--accent);color:#fff}",
           ".uc-cap{font-size:calc(10.5*var(--u));color:var(--muted);font-weight:600;letter-spacing:.04em;text-transform:uppercase}",
           ".uc-i{flex:none;display:inline-block;vertical-align:middle}",
           ]
    for s in STATES:
        css.append(f'.prototype[data-story-state="{s}"] .uc-stage[data-on]:not([data-on~="{s}"]),'
                   f'.uc-hero[data-fixed="{s}"] .uc-stage[data-on]:not([data-on~="{s}"]){{display:none}}')
    app = scoped("\n".join(INLINE_CSS), ".uc-stage")
    # WHY every rule, cursor and pointer-events too: dropping a rule for its cursor dropped its fill
    # (.turn-hit, .turn-knob, .handle); the stage's own rule turns SVG pointer events off
    vp = "\n".join(A["css"])
    return "\n".join(css) + "\n" + vp + "\n" + app


QUIET_DIMS = """
{H} .L-sdims .cad-dim line{{stroke:{c};stroke-width:.6}}
{H} .L-sdims .cad-dim path.arw{{fill:{c};transform-box:fill-box;transform-origin:center;transform:scale(.75)}}
{H} .L-sdims .cad-dim .chip{{fill:var(--canvas);stroke:none}}
{H} .L-sdims .cad-dim text{{fill:{t};font-weight:400;font-size:9.5px}}
"""
CANVAS_OFF = "{H} :is(.L-edges>path, .L-sdims .cad-dim, .L-triads>.triad, .L-infos>text){{display:none}}"


def reveal(H: str, S, layer: str, pinned: bool = True) -> str:
    """A hidden-by-default extras layer whose pointed-at marker shows (live hover, and the pinned demo state)."""
    pin = f", {S('hover')} {layer}>.pin" if pinned else ""
    return f"{H} {layer}{{display:inline}}{H} {layer}>*{{display:none}}{H} {layer}>.is-hot{pin}{{display:inline}}"


# ---------------------------------------------------------------- 2c. the ten variants
def ov(x: float, y: float, inner: str, cls: str = "", w: float | None = None, h: float | None = None, attrs: str = "") -> str:
    st = f"left:calc({x}*var(--u));top:calc({y}*var(--u));" + (f"width:calc({w}*var(--u));" if w else "") + (f"height:calc({h}*var(--u));" if h else "")
    return f'<div class="uc-abs {cls}" style="{st}" {attrs}>{inner}</div>'


def stage(scene: str, overlays: str = "", on: str | None = None) -> str:
    return f'<div class="uc-stage" data-scene="{scene}"{f" data-on={chr(34)}{on}{chr(34)}" if on else ""}>{overlays}</div>'


HINT = ('<div class="uc-hint"><b>Live</b> point at any marker <span>·</span> click #3 to edit it <span>·</span> '
        'click empty canvas to deselect <span>·</span> Back / Next step through the states</div>')


def hero(v: str, stages: str, extra: str = "") -> str:
    return f'<div class="uc-hero {v}"{extra}>{stages}{HINT}</div>'


def exhibit(v: str, overlays: str = "") -> str:
    return f'<div class="uc-hero {v}" data-fixed="calm">{stage("B", overlays)}</div>'


def variants(facts: dict) -> list[dict]:
    S_ = facts["scenes"]
    A, B, Abad = S_["A"], S_["B"], S_["Abad"]
    bb = {kid(o["fid"]): o["bb"] for o in A["outlines"]}
    plansA = A["plans"]
    warn5 = [w for w in Abad["plans"]["f5"]["warnings"] if '"level":"error"' in w]
    warn5 = json.loads(warn5[0])["text"] if warn5 else "does not fit its profile"
    pl = facts["panels"]["label"]
    pm = facts["panels"]["marker"]
    out = []

    def tabs_hots(panel: dict, here: str) -> str:
        x, y, w, h = panel["tabs"]
        tw = w / 3
        hs = []
        for i, (name, to) in enumerate([("Marker", "editm"), ("Label", "edit")]):
            if to == here:
                continue
            hs.append(ov(x + i * tw, y, "", "v4tab", tw, h, f'data-story-to="{to}" role="button" title="{name} tab"'))
        return "".join(hs)

    # ---------- V1
    H, S = VS("v1")
    out.append(dict(
        id="v1", name="Turn it down", accent="#e05a3f",
        thesis="Keep every layer of today and fix the three loudest: axes and the dashed profile box only on the marker you point at or edit; dims and info labels thin and grey.",
        css=f"""{H} .L-grid .g{{stroke-opacity:.55}}
{QUIET_DIMS.format(H=H, c="#a9b1ba", t="#87909a")}
{H} :is(.L-triads>.triad, .L-edges>path){{display:none}}
{H} :is(.L-triads, .L-edges)>.is-hot, {S('hover')} :is(.L-triads, .L-edges)>.pin, {S('edit')} .L-triads>[data-k="3"]{{display:inline}}
{H} .L-infos>text{{font-size:9px!important;fill:#a0a8b1!important}}""",
        preview=hero("v1", stage("A")), media=exhibit("v1"),
        steps=[("edit", "Zach's moment, turned down", "#3 open on the Label tab. Every marker keeps its two dims and its info label, thinner and grey; only #3 keeps its axes, arc and handles.", '.uc-hot[data-k="3"]'),
               ("calm", "Nothing selected", "Esc. The dims stay on all nine, but no red/green axes and no dashed boxes: the markers read first.", None),
               ("hover", "Point at #5", "Its Joint Origin and its dashed profile box come back while you point. Point at any marker yourself: the same.", '.uc-hot[data-k="5"]')],
        decisions=[("What changes", "Three CSS-level fixes; no new state, no new control."), ("Axes", "Only on the hovered or edited marker."),
                   ("Dims", "Still on every profile, 0.6 px grey, no white chip box, 9.5 px.")],
        bestWhen="The busy feeling is mostly weight and colour, and Zach wants every number still visible without pointing.",
        losesWhen="The sheet grows: 24 markers still carry 48 dims and 24 info lines, just quieter.",
        keep=["Axes only on hover / edit", "Dashed profile box only on hover", "Thin grey sketch dims"]))

    # ---------- V2
    H, S = VS("v2")
    out.append(dict(
        id="v2", name="Selection is the chrome", accent="#2f7f74",
        thesis="Figma's rule: nothing is drawn on a marker until you point at it (an outline and its name) or select it (its dims, axes, arc).",
        css=f"""{H} .L-grid .g{{stroke-opacity:.6}}
{CANVAS_OFF.format(H=H)}
{reveal(H, S, ".X-hover")}{reveal(H, S, ".X-tag")}
{S('edit')} :is(.L-triads, .L-infos)>[data-k="3"]{{display:inline}}
{S('edit')} :is(.X-hover, .X-tag)>[data-k="3"]{{display:none}}""",
        preview=hero("v2", stage("A")), media=exhibit("v2"),
        steps=[("edit", "Zach's moment, selection only", "#3 open: its dims, axes, arc, handles and info, exactly as today. The other eight show only what prints.", '.uc-hot[data-k="3"]'),
               ("calm", "Nothing selected", "Esc. Nine markers on a page, no chrome at all.", None),
               ("hover", "Point at #5", "A blue outline and its name, as Figma's hover. Point at any marker yourself; click #3 to select it.", '.uc-hot[data-k="5"]')],
        decisions=[("Rest state", "Printed geometry and the sticker's own edge only."), ("Hover", "Accent outline + the info line as a name tag."),
                   ("Select", "Today's full edit chrome on that one marker; sketch dims of others hidden.")],
        bestWhen="Zach mostly looks at the sheet and edits one marker at a time; Figma is the model he expects on a canvas.",
        losesWhen="He wants to compare sizes across markers at a glance: every number needs a point or a click.",
        keep=["Hover outline + name tag", "Sketch dims only on the selection", "Calm rest state"]))

    # ---------- V3
    H, S = VS("v3")
    sw = ov(608, 34, f'<div class="uc-seg">'
            f'<button type="button" data-story-to="calm" class="sw-doc">{icon("file-text", 14)}Document</button>'
            f'<button type="button" data-story-to="editmode" class="sw-edit">{icon("pencil", 14)}Edit</button></div>', "uc-pill v3sw")
    out.append(dict(
        id="v3", name="Document | Edit", accent="#7667c6",
        thesis="Two explicit modes: Document shows the page as it prints, no grid and no chrome; Edit shows everything today shows. A click on a marker enters Edit.",
        css=f"""{S('calm')} :is(.L-grid, .L-ruler, .L-edges, .L-sdims, .L-triads, .L-infos){{display:none}}
{S('calm')} .uc-canvas{{background:#f3f4f6}}
{S('calm')} .uc-print{{filter:drop-shadow(0 1px 1.2px rgba(16,24,40,.18)) drop-shadow(0 4px 10px rgba(16,24,40,.07))}}
{S('calm')} .L-outlines .outline{{stroke:transparent}}
{H} .v3sw button.on, {S('calm')} .v3sw .sw-doc, {S('editmode', 'edit')} .v3sw .sw-edit{{background:var(--accent);color:#fff}}""",
        preview=hero("v3", stage("A", sw)), media=exhibit("v3", sw.replace('data-story-to="calm"', "").replace('data-story-to="editmode"', "")),
        steps=[("edit", "Zach's moment, in Edit", "#3 open. Edit mode is today's canvas, unchanged: every dim, axis, info label and dashed box.", '.uc-hot[data-k="3"]'),
               ("editmode", "Esc: still in Edit", "Nothing selected, but the mode stays Edit, so the chrome stays.", ".v3sw .sw-edit"),
               ("calm", "Document", "The switch at the top. The page as it prints: stickers on paper, no grid, no rulers, no chrome. Click #3 to go straight back to Edit.", ".v3sw .sw-doc")],
        decisions=[("Model", "A view mode, like a print preview, beside the doc name."), ("Edit mode", "Today's chrome, untouched."),
                   ("Entering Edit", "The switch, or a click on any marker.")],
        bestWhen="The calm view is for showing or checking the sheet, and editing is a separate, deliberate session.",
        losesWhen="Editing is most of the time: then the busy canvas is still the one Zach lives in.",
        keep=["The Document view (paper, no grid)", "A Document | Edit switch", "Click a marker to enter Edit"]))

    # ---------- V4
    H, S = VS("v4")
    x, y, w, h = pl["box"]
    cy0, cy1 = pl["corner"]["box"][1] + 0.5, pl["corner"]["box"][1] + pl["corner"]["box"][3] + 0.5
    my0, my1 = pl["mode"]["box"][1] - 3, pl["mode"]["box"][1] + pl["mode"]["box"][3] + 2
    W_, H_ = VIEW
    row_h = 24
    d1 = cy1 - cy0
    d2 = d1 + (my1 - my0) - row_h

    def slice_(y0: float, y1: float, dy: float, cls: str) -> str:
        return (f'<div class="uc-layer uc-img v4slice {cls}" style="background-image:var(--img-panel-label);'
                f'clip-path:inset({y0 / H_ * 100:.3f}% 0 {(H_ - y1) / H_ * 100:.3f}% 0);transform:translateY(-{dy / H_ * 100:.3f}%)"></div>')
    # WHY a white backing: a clip edge and a translate can round apart by a device pixel, and the ChArUco under the panel showed through
    patch = (ov(x + 1, y + 1, "", "v4slice v4back", w - 2, h - d2 - 2)
             + slice_(0, cy0, 0, "s1") + slice_(cy1, my0, d1, "s2") + slice_(my1, H_, d2, "s3")
             + ov(x + 1, my0 - d1, f'{icon("info", 13)}<span>2 notes</span><span class="v4n-t">corner mark · mode auto</span>{icon("chevron-right", 13)}',
                  "v4notes", w - 2, row_h))
    corner_callout = ov(bb[3][0] - 2, bb[3][1] - 30, '◤ Corner mark · triangle · 2.80 mm legs', "v4callout")
    out.append(dict(
        id="v4", name="The command decides", accent="#b7791f",
        thesis="Fusion's rule: with no command running only the markers show; the open ArUco Extrude draws only what its current tab edits, and its notes fold into one row.",
        css=f"""{CANVAS_OFF.format(H=H)}
{reveal(H, S, ".X-face")}
{S('edit')} .L-edit :is(.E-fdims, .E-arc){{display:none}}
{S('edit')} .X-corner{{display:inline}}{S('edit')} .X-corner>*{{display:none}}{S('edit')} .X-corner>[data-k="3"]{{display:inline}}
{S('editm')} .L-triads>[data-k="3"]{{display:inline}}
{H} .v4slice, {H} .v4notes, {H} .v4callout{{display:none}}
{S('edit')} .uc-panel-label{{display:none}}{S('edit')} :is(.v4slice, .v4callout){{display:block}}{S('edit')} .v4notes{{display:flex}}
{H} .v4notes{{align-items:center;gap:calc(6*var(--u));padding:0 calc(10*var(--u));background:var(--panel);color:var(--muted);font-size:calc(11*var(--u));
  border-top:1px solid var(--line);border-bottom:1px solid var(--line);cursor:default}}
{H} .v4notes .v4n-t{{flex:1;opacity:.75}}
{H} .v4callout{{font-size:calc(10.5*var(--u));color:var(--accent);font-weight:600;white-space:nowrap}}
{H} .v4back{{background:var(--panel)}}
{H} .v4tab{{cursor:pointer;border-radius:calc(4*var(--u))}}{H} .v4tab:hover{{background:color-mix(in srgb,var(--accent) 8%,transparent)}}
{H} .v4tab-m{{display:none}}{S('edit')} .v4tab-m{{display:block}}{H} .v4tab-l{{display:none}}{S('editm')} .v4tab-l{{display:block}}""",
        preview=hero("v4", stage("A", patch + corner_callout
                                  + tabs_hots(pl, "edit").replace('class="uc-abs v4tab"', 'class="uc-abs v4tab v4tab-m"')
                                  + tabs_hots(pm, "editm").replace('class="uc-abs v4tab"', 'class="uc-abs v4tab v4tab-l"'))),
        media=exhibit("v4"),
        steps=[("edit", "Zach's moment, Label tab", "The Label tab edits the label and the corner mark, so the canvas rings #3's corner mark and shows nothing else; no size dims, no arc. The panel's two notes fold into one row.", '.uc-hot[data-k="3"]'),
               ("editm", "Marker tab", "Click the Marker tab in the panel: now the size dims, the turn arc and the Joint Origin appear, because this tab edits them.", ".v4tab-l"),
               ("calm", "No command", "Esc. No command running: only the markers, as Fusion shows bodies outside a sketch.", None),
               ("hover", "Point at #5", "Fusion's pre-highlight: the face tints before you click. Point at any marker yourself.", '.uc-hot[data-k="5"]')],
        decisions=[("Rule", "The chrome is the active command's: none, or the current tab's fields."),
                   ("Label tab", "Corner-mark ring; no size dims."), ("Marker tab", "Marker and outer dims, turn arc, Joint Origin."),
                   ("Panel notes", "Folded into one '2 notes' row under the fields.")],
        bestWhen="Zach thinks in Fusion: a command owns the viewport while it runs, and the tab says what is being edited.",
        losesWhen="He wants a marker's size while on the Label tab, or at rest without opening the command.",
        keep=["Chrome follows the panel's tab", "Fusion pre-highlight on hover", "Panel notes folded into one row"]))

    # ---------- V5
    H, S = VS("v5")
    zA, zN, zF = A["camera"]["zoom"], S_["Anear"]["camera"]["zoom"], S_["Bfar"]["camera"]["zoom"]
    lad = ov(12, 834, f'<div class="uc-seg"><span class="uc-cap v5cap">Detail by zoom</span>'
             f'<button type="button" data-story-to="far" class="z-far">{icon("zoom-out", 13)}Far · ids</button>'
             f'<button type="button" data-story-to="calm" class="z-fit">Fit · ids, hover</button>'
             f'<button type="button" data-story-to="near" class="z-near">{icon("zoom-in", 13)}Near · everything</button></div>', "uc-pill v5lad")
    out.append(dict(
        id="v5", name="Zoom ladder", accent="#3f6fa8",
        thesis="Semantic zoom, as maps do: far away each marker is just its id; at fit an id under each and the full line on hover; zoomed in, the dims and axes come back.",
        css=f"""{CANVAS_OFF.format(H=H)}
{H} .X-badge{{display:inline}}
{reveal(H, S, ".X-tag", pinned=False)}
{S('near')} :is(.L-edges>path, .L-sdims .cad-dim, .L-triads>.triad, .L-infos>text){{display:inline}}
{S('near')} .X-badge, {S('near')} .X-tag{{display:none}}
{S('far')} .L-grid .g{{stroke-opacity:.5}}
{S('far')} .X-badge .xb-t{{font-size:12.5px;font-weight:700}}
{S('edit')} .X-badge>[data-k="3"]{{display:none}}{S('edit')} :is(.L-triads, .L-infos)>[data-k="3"]{{display:inline}}
{H} .v5cap{{align-self:center;padding:0 calc(6*var(--u))}}
{S('far')} .v5lad .z-far, {S('calm', 'edit')} .v5lad .z-fit, {S('near')} .v5lad .z-near{{background:var(--accent);color:#fff}}""",
        preview=hero("v5", stage("A", lad, "edit calm hover") + stage("Anear", lad, "near") + stage("Bfar", lad, "far")),
        media=exhibit("v5", lad.replace("data-story-to=", "data-x=")),
        steps=[("edit", "Zach's moment, at fit", f"At fit ({zA:.2f} px/mm) each marker shows only its id; #3, being edited, shows all of its chrome.", '.uc-hot[data-k="3"]'),
               ("calm", "Nothing selected, at fit", "Nine ids. Point at a marker for its full info line.", ".v5lad .z-fit"),
               ("near", "Zoom in", f"At {zN:.2f} px/mm there is room: every marker in view gets its dims, axes, info and profile box back.", ".v5lad .z-near"),
               ("far", "Zoom out (24 markers)", f"At {zF:.2f} px/mm only ids remain, larger. The rung buttons are the live control.", ".v5lad .z-far")],
        decisions=[("Rungs", f"far < 3 px/mm: ids; fit: ids + hover; > 5 px/mm: everything (live zooms {zF:.1f}, {zA:.1f}, {zN:.1f})."),
                   ("Edited marker", "Always full chrome, at any zoom."), ("Control", "Ordinary zoom; the rung indicator is optional.")],
        bestWhen="Zach zooms a lot anyway and wants the canvas to stay right at every zoom, like a map.",
        losesWhen="At fit he wants sizes without zooming in; and the thresholds need tuning per screen.",
        keep=["Id badge under each marker", "Full chrome only when zoomed in", "Hover shows the full info line"]))

    # ---------- V6
    H, S = VS("v6")

    def mlist(scene: dict, edit_click: bool, pin: int | None, max_rows: int = 24) -> str:
        rows = []
        feats = sorted(scene["plans"].items(), key=lambda kv: kid(kv[0]))
        for fid, p in feats[:max_rows]:
            k = kid(fid)
            typ = p["summary"].split(" ")[0]
            to = ' data-story-to="edit"' if edit_click and k == 3 else ""
            rows.append(f'<div class="uc-hot v6row{" pin" if pin == k else ""}" data-k="{k}"{to}><b>{E(ids_text(p))}</b>'
                        f'<span>{E(typ)}</span><i>{p["marker_mm"]:.1f} mm</i></div>')
        if len(feats) > max_rows:
            rows.append(f'<div class="v6more">+ {len(feats) - max_rows} more</div>')
        return ov(12, 90, f'<div class="v6h">{icon("list", 13)}<b>Markers</b><span>{len(feats)} · 4X4_50</span></div>' + "".join(rows), "uc-pill v6list", 196)
    out.append(dict(
        id="v6", name="Marker list", accent="#a94f78",
        thesis="Move the per-marker facts off the canvas into a Figma-style layers list: the canvas shows markers, the list shows ids, types and sizes, and hovering either highlights both.",
        css=f"""{CANVAS_OFF.format(H=H)}
{reveal(H, S, ".X-hover")}
{S('edit')} .L-triads>[data-k="3"]{{display:inline}}
{H} .v6list{{padding:calc(6*var(--u)) 0;font-size:calc(11.5*var(--u))}}
{H} .v6h{{display:flex;align-items:center;gap:calc(6*var(--u));padding:calc(4*var(--u)) calc(12*var(--u)) calc(8*var(--u));border-bottom:1px solid var(--line);margin-bottom:calc(4*var(--u))}}
{H} .v6h span{{margin-left:auto;color:var(--muted);font-size:calc(10.5*var(--u))}}
{H} .v6row{{position:relative!important;display:flex;gap:calc(8*var(--u));align-items:baseline;padding:calc(4*var(--u)) calc(12*var(--u));cursor:default}}
{H} .v6row b{{min-width:calc(40*var(--u))}}{H} .v6row span{{color:var(--muted);flex:1}}{H} .v6row i{{font-style:normal;color:var(--muted);font-variant-numeric:tabular-nums}}
{H} .v6row[data-story-to]{{cursor:pointer}}{H} .v6row.story-target{{outline-offset:-2px;box-shadow:none;animation:none}}
{H} .v6more{{padding:calc(4*var(--u)) calc(12*var(--u));color:var(--muted)}}
{H} .v6row.is-hot, {S('hover')} .v6row.pin{{background:var(--accent-soft)}}
{S('edit')} .v6row[data-k="3"]{{background:var(--accent);color:#fff}}{S('edit')} .v6row[data-k="3"] :is(span,i){{color:#fff}}""",
        preview=hero("v6", stage("A", mlist(A, True, 5))), media=exhibit("v6", mlist(B, False, None, 16)),
        steps=[("edit", "Zach's moment, with a list", "#3 open: its row is selected and it alone carries chrome on the canvas. Every id, type and size sits in the list at the left.", '.v6row[data-k="3"]'),
               ("calm", "Nothing selected", "Markers on the canvas, facts in the list.", ".v6list"),
               ("hover", "Point at row #5", "The row and the marker light up together; hover any row or any marker yourself, click row #3 to edit it.", '.v6row[data-k="5"]')],
        decisions=[("Where facts live", "A list panel, top-left under the doc pill (Figma's layers)."), ("Canvas", "Markers only; hover links canvas and list."),
                   ("Selection", "The row and the marker, both.")],
        bestWhen="Sheets get long and Zach wants to scan, sort or Re-ID by id; the list is also a natural home for warnings.",
        losesWhen="The screen is small (the list costs ~200 px) or the document has two or three markers.",
        keep=["Markers list with id, type, size", "Hover links list and canvas", "Canvas free of text"]))

    # ---------- V7
    H, S = VS("v7")
    out.append(dict(
        id="v7", name="Ink and one accent", accent="#4f7d3a",
        thesis="Keep all of the information, lose the colour: grey hairline chrome on a dot grid, red/green axes only on the edited marker, and one blue for whatever is selected.",
        css=f"""{H} .L-grid{{display:none}}{H} .X-dots{{display:inline}}
{H} .L-edges>path{{display:none}}
{QUIET_DIMS.format(H=H, c="#b9c0c8", t="#8f98a2")}
{H} .L-triads line{{stroke:#bcc3cb!important;stroke-width:1.2px}}
{H} .L-triads .ax-o{{stroke:#a0a8b1;r:2.4px}}
{H} .L-infos>text{{fill:#a3abb4!important}}
{H} .L-ruler text{{fill:#a3abb4}}{H} .L-ruler .ruler-bg{{opacity:.55}}
{reveal(H, S, ".X-hover")}
{S('edit')} :is(.E-edges .edge, .E-outline .outline){{stroke:var(--accent)!important}}
{S('edit')} .E-handles .handle{{stroke:var(--accent)}}
{S('edit')} .E-fdims line{{stroke:var(--accent)}}{S('edit')} .E-fdims path.arw{{fill:var(--accent)}}{S('edit')} .E-fdims text{{fill:var(--accent)}}
{S('edit')} .L-triads>[data-k="3"] .ax-x{{stroke:#e5484d!important;stroke-width:2.2px}}{S('edit')} .L-triads>[data-k="3"] .ax-y{{stroke:#2f9e5a!important;stroke-width:2.2px}}
{S('edit')} .L-triads>[data-k="3"] .ax-o{{stroke:var(--text);r:3.5px}}""",
        preview=hero("v7", stage("A")), media=exhibit("v7"),
        steps=[("edit", "Zach's moment, one accent", "Every marker keeps its dims, axes and info in light grey on a dot grid; #3 is the only colour: blue selection and dims, its own red/green axes.", '.uc-hot[data-k="3"]'),
               ("calm", "Nothing selected", "All the information, no colour at all. The markers are the darkest thing on screen.", None),
               ("hover", "Point at #5", "Blue outline: colour means 'this one'. Point at any marker yourself.", '.uc-hot[data-k="5"]')],
        decisions=[("Colour", "One accent (the app's blue) for selection and hover; the orange pick colour is dropped."),
                   ("Grid", "Dots at the live grid's pitch."), ("Axes", "Grey at rest, red/green only when editing.")],
        bestWhen="Zach wants every number visible all the time and the noise is mostly colour and line weight.",
        losesWhen="The count is the problem, not the colour: 24 markers still carry 120 chrome items.",
        keep=["Dot grid", "Grey axes at rest, colour on the edited one", "One accent for selection"]))

    # ---------- V8
    H, S = VS("v8")
    tb = facts["chromeBoxes"]["toolbar"]
    btn = ov(tb[0] + tb[2] + 10, tb[1], f'<button type="button" class="v8btn" data-story-to="overlays">{icon("layers", 15)}<span>Overlays</span>{icon("chevron-down", 12)}</button>',
             "uc-pill v8wrap", None, tb[3])
    items = [("grid", "Grid"), ("rulers", "Rulers"), ("edges", "Profile edges"), ("sdims", "Sketch dimensions"),
             ("triads", "Joint Origins"), ("infos", "Marker info")]
    pop = ov(tb[0] + tb[2] + 10, tb[1] - 268,
             f'<div class="v8ph"><b>Overlays</b><button type="button" class="v8x" data-story-to="calm" aria-label="Close">{icon("x", 13)}</button></div>'
             + "".join(f'<label class="v8it"><input type="checkbox" data-ov="{k}"><span>{E(t)}</span></label>' for k, t in items)
             + '<div class="v8f">The edited marker always shows its own dims, arc and handles.</div>', "uc-pill v8pop", 230)
    ovcss = "".join(f"{H}.ov-{k} .{layer}{{display:inline}}" for k, layer in
                    [("grid", "L-grid"), ("rulers", "L-ruler"), ("edges", "L-edges"), ("sdims", "L-sdims"), ("triads", "L-triads"), ("infos", "L-infos")])
    out.append(dict(
        id="v8", name="Overlays menu", accent="#9a5b34",
        thesis="Blender's viewport overlays, very minimal: the canvas shows only the markers; grid, rulers, dims, axes and info are each one toggle in a single Overlays menu.",
        css=f"""{H} :is(.L-grid, .L-ruler, .L-edges, .L-sdims, .L-triads, .L-infos){{display:none}}
{ovcss}
{H} .v8wrap{{display:flex;align-items:center;padding:0 calc(4*var(--u))}}
{H} .v8btn{{all:unset;display:flex;align-items:center;gap:calc(6*var(--u));padding:calc(8*var(--u)) calc(10*var(--u));border-radius:calc(8*var(--u));
  font-weight:600;font-size:calc(12.5*var(--u));color:var(--text);cursor:pointer}}
{H} .v8btn:hover, {S('overlays', 'overlays-on')} .v8btn{{background:var(--accent-soft);color:var(--accent)}}
{H} .v8pop{{display:none;padding:calc(8*var(--u)) 0}}{S('overlays', 'overlays-on')} .v8pop{{display:block}}
{H} .v8ph{{display:flex;align-items:center;padding:calc(2*var(--u)) calc(12*var(--u)) calc(6*var(--u))}}{H} .v8ph b{{flex:1;font-size:calc(12*var(--u))}}
{H} .v8x{{all:unset;cursor:pointer;color:var(--muted);display:flex}}
{H} .v8it{{display:flex;align-items:center;gap:calc(8*var(--u));padding:calc(5*var(--u)) calc(12*var(--u));cursor:pointer;font-size:calc(12*var(--u))}}
{H} .v8it:hover{{background:var(--panel-2)}}{H} .v8it input{{margin:0;width:calc(14*var(--u));height:calc(14*var(--u));accent-color:var(--accent)}}
{H} .v8f{{margin-top:calc(4*var(--u));padding:calc(6*var(--u)) calc(12*var(--u)) 0;border-top:1px solid var(--line);color:var(--muted);font-size:calc(10.5*var(--u))}}""",
        preview=hero("v8", stage("A", btn + pop), ' data-ovsync="1"'), media=exhibit("v8", btn.replace('data-story-to="overlays"', "")),
        steps=[("edit", "Zach's moment, overlays off", "Every overlay is off: no grid, rulers, dims, axes or info. #3, being edited, still gets its own dims, arc and handles.", '.uc-hot[data-k="3"]'),
               ("calm", "Nothing selected", "The most minimal canvas: only what prints, on a plain background.", None),
               ("overlays", "Open Overlays", "One menu beside the toolbar holds every layer. Tick any box yourself: it turns on live.", ".v8btn"),
               ("overlays-on", "Dims and info on", "Sketch dimensions and Marker info ticked: they appear on every marker, the rest stay off.", ".v8pop")],
        decisions=[("Default", "All overlays off (persisted per viewer, as Marker info is today)."), ("Control", "One Overlays menu beside the toolbar."),
                   ("Edited marker", "Its own edit chrome ignores the toggles.")],
        bestWhen="Different moments want different layers and Zach is happy to set them once and leave them.",
        losesWhen="The right layers depend on the task: toggles become a chore, and a newcomer never finds the dims.",
        keep=["One Overlays menu", "Off-by-default rest state", "Edit chrome independent of toggles"]))

    # ---------- V9
    H, S = VS("v9")

    def legend(text: str) -> str:
        return ov(12, 834, f'<div class="v9lg">{icon("info", 14)}{text}</div>', "uc-pill v9wrap", None, 52)
    lgA = legend("<b>8 ×</b> Single · 4X4_50 · 28.0 mm<span>·</span><b>1 ×</b> ChArUco 2×8 · 18.5 mm")
    lgB = legend(f"<b>24 ×</b> Single · 4X4_50 · {B['plans']['f0']['marker_mm']:.1f} mm")
    out.append(dict(
        id="v9", name="Say it once", accent="#5361a8",
        thesis="Repeated facts are shown once: one dimension pair for the eight equal squares (×8), a short id per marker, and the shared dictionary and size in one legend.",
        css=f"""{H} .L-sdims .cad-dim{{display:none}}{H} .L-sdims .cad-dim.rep, {H} .L-sdims .cad-dim.is-hot, {S('hover')} .L-sdims .cad-dim.pin{{display:inline}}
{H} .X-count{{display:inline}}
{H} .L-infos>text{{display:none}}{H} .L-infos>.is-hot, {S('hover')} .L-infos>.pin, {S('edit')} .L-infos>[data-k="3"]{{display:inline}}
{H} .X-badge{{display:inline}}{H} .X-badge .xb-c{{display:none}}{H} .X-badge .xb-t{{fill:var(--muted);font-weight:600;font-size:10px}}
{H} .X-badge>.is-hot, {S('hover')} .X-badge>.pin, {S('edit')} .X-badge>[data-k="3"]{{display:none}}
{H} .L-triads :is(.ax-x, .ax-y){{display:none}}{H} .L-triads .ax-o{{r:2.2px;stroke:var(--muted)}}
{H} .L-triads>.is-hot :is(.ax-x, .ax-y), {S('hover')} .L-triads>.pin :is(.ax-x, .ax-y), {S('edit')} .L-triads>[data-k="3"] :is(.ax-x, .ax-y){{display:inline}}
{S('edit')} .L-triads>[data-k="3"] .ax-o{{r:3.5px;stroke:var(--text)}}
{H} .L-edges>path{{display:none}}{H} .L-edges>.is-hot, {S('hover')} .L-edges>.pin{{display:inline}}
{H} .v9wrap{{display:flex;align-items:center;padding:0 calc(14*var(--u))}}
{H} .v9lg{{display:flex;align-items:center;gap:calc(7*var(--u));font-size:calc(12*var(--u));color:var(--muted);white-space:nowrap}}
{H} .v9lg b{{color:var(--text)}}""",
        preview=hero("v9", stage("A", lgA)), media=exhibit("v9", lgB),
        steps=[("edit", "Zach's moment, said once", "The eight equal squares carry one dimension pair (×8) on #0; each marker a short id; the shared 4X4_50 and 28 mm sit in the legend. #3 has its full edit chrome.", '.uc-hot[data-k="3"]'),
               ("calm", "Nothing selected", "Two dimension pairs instead of eighteen; origins are dots.", ".v9wrap"),
               ("hover", "Point at #5", "Its own dims, axes, profile box and full info line come back. Point at any marker yourself.", '.uc-hot[data-k="5"]')],
        decisions=[("Grouping", "Profiles with an equal size share one dimension, with a count."), ("Ids", "A short '#5' under each marker; the full line on hover."),
                   ("Legend", "Shared dictionary and sizes, bottom-left."), ("Axes", "Origin dot at rest; the triad on hover or edit.")],
        bestWhen="Sheets repeat the same sticker many times, which is exactly the sticker-sheet workflow.",
        losesWhen="Every profile is different: then 'once' is 'every time' and it degrades to today, quieter.",
        keep=["One dim per equal size (×N)", "Short id under each marker", "Shared-facts legend"]))

    # ---------- V10
    H, S = VS("v10")

    def chip(inner: str, cls: str) -> str:
        return ov(560, 34, inner, f"uc-pill v10chip {cls}", 320, 44)
    okA = chip(f'{icon("circle-check", 16, "ok")}<span><b>9 markers</b> · ids 0–15 · all fit</span>', "v10ok")
    badA = chip(f'{icon("triangle-alert", 16, "warn")}<span><b>#5 doesn\'t fit</b> its profile</span>'
                f'<button type="button" data-story-to="calm" class="v10undo">{icon("undo-2", 13)}Undo</button>', "v10bad")
    b5 = {kid(o["fid"]): o["bb"] for o in Abad["outlines"]}[5]
    callout = ov(b5[0], b5[3] + 22, E(warn5), "v10call", b5[2] - b5[0] + 110)
    okB = chip(f'{icon("circle-check", 16, "ok")}<span><b>24 markers</b> · ids 0–23 · all fit</span>', "v10ok")
    out.append(dict(
        id="v10", name="Exceptions only", accent="#357c91",
        thesis="The canvas answers 'is it OK' in one chip; chrome appears on a marker only when it needs you or you select it.",
        css=f"""{CANVAS_OFF.format(H=H)}
{reveal(H, S, ".X-tag", pinned=False)}
{S('edit')} :is(.L-triads, .L-infos)>[data-k="3"]{{display:inline}}
{S('problem')} :is(.L-sdims .cad-dim, .L-infos>text)[data-k="5"]{{display:inline}}
{H} .v10chip{{display:flex;align-items:center;justify-content:center;gap:calc(8*var(--u));font-size:calc(12.5*var(--u));padding:0 calc(10*var(--u))}}
{H} .v10chip .ok{{color:#2f9e5a}}{H} .v10chip .warn{{color:#c2410c}}
{H} .v10bad{{border-color:#f0b27a;background:#fff7ed}}
{H} .v10undo{{all:unset;display:flex;align-items:center;gap:calc(4*var(--u));margin-left:calc(6*var(--u));padding:calc(4*var(--u)) calc(8*var(--u));
  border-radius:calc(6*var(--u));color:#c2410c;font-weight:600;cursor:pointer}}{H} .v10undo:hover{{background:#ffedd5}}
{H} .v10call{{font-size:calc(10.5*var(--u));color:var(--bad);font-weight:600;line-height:1.35}}""",
        preview=hero("v10", stage("A", okA, "edit calm hover") + stage("Abad", badA + callout, "problem")), media=exhibit("v10", okB),
        steps=[("edit", "Zach's moment, exceptions only", "#3 open with its full chrome; the other eight are only what prints, and one chip says the sheet is fine.", '.uc-hot[data-k="3"]'),
               ("calm", "Nothing selected", "One calm answer: 9 markers, ids 0–15, all fit. Point at a marker for its info line.", ".v10chip"),
               ("problem", "#5 typed to 36 mm", "Captured live: #5 no longer fits. The chip turns amber and only #5 shows chrome: its red outline, its dims, the core's own warning. Undo returns to the sheet that fits.", ".v10undo")],
        decisions=[("Rest state", "Markers plus one health chip (count, id range, fit)."), ("Exceptions", "A marker that needs you shows its chrome and the core's warning."),
                   ("Selection", "Today's full edit chrome on the selected one.")],
        bestWhen="Most sheets are fine most of the time, and Zach wants problems to find him rather than scanning numbers.",
        losesWhen="He wants sizes at a glance; and a warning that is not an error (an info) still needs a home.",
        keep=["Health chip at the top", "Chrome only on markers that need you", "The core's warning on the canvas"]))
    return out


# ---------------------------------------------------------------- 2d. the one script: fill the stages, live hover, the overlay toggles
STAGE_JS = r"""
(function () {
  // every .uc-stage[data-scene] gets its scene's live chrome (a <template>, once in the page)
  const fill = () => document.querySelectorAll('.uc-stage[data-scene]:not([data-filled])').forEach((st) => {
    const t = document.getElementById('uc-t-' + st.dataset.scene);
    if (!t) return;
    st.prepend(t.content.cloneNode(true));
    st.dataset.filled = '1';
  });
  fill();
  new MutationObserver(fill).observe(document.body, { childList: true, subtree: true });
  // live hover: pointing at a marker (or its list row) marks every element of that marker in this hero
  const hot = (h, on) => {
    const hero = h.closest('.uc-hero');
    if (!hero) return;
    hero.querySelectorAll('[data-k="' + h.dataset.k + '"]').forEach((e) => e.classList.toggle('is-hot', on));
  };
  document.addEventListener('mouseover', (e) => { const h = e.target.closest && e.target.closest('.uc-hot'); if (h) hot(h, true); });
  document.addEventListener('mouseout', (e) => {
    const h = e.target.closest && e.target.closest('.uc-hot');
    if (h && !(e.relatedTarget && h.contains(e.relatedTarget))) hot(h, false);
  });
  // V8's overlay toggles: a ticked box shows its layer; the walkthrough's steps set them
  const OV = { 'overlays-on': ['sdims', 'infos'] };
  const sync = (hero, state) => hero.querySelectorAll('[data-ov]').forEach((c) => {
    c.checked = (OV[state] || []).includes(c.dataset.ov);
    hero.classList.toggle('ov-' + c.dataset.ov, c.checked);
  });
  document.addEventListener('change', (e) => {
    const c = e.target.closest && e.target.closest('[data-ov]');
    if (c) c.closest('.uc-hero').classList.toggle('ov-' + c.dataset.ov, c.checked);
  });
  new MutationObserver((ms) => ms.forEach((m) => {
    const hero = m.target.querySelector && m.target.querySelector(':scope > .uc-hero[data-ovsync]');
    if (hero) sync(hero, m.target.dataset.storyState);
  })).observe(document.body, { attributes: true, attributeFilter: ['data-story-state'], subtree: true });
})();
"""


# ---------------------------------------------------------------- 2e. the AI prune: scores after all ten were built and driven
# Counts are measured in the built gallery by the review (visible chrome items on the canvas); fr5 is an estimate read from
# today's web/src (Viewport.tsx already has `hover`, `sel`, `panel.tab`, `camera.zoom`, `markerInfo` and the plans' overflow).
def scores(measure: dict) -> dict[str, dict[str, tuple[int, str, str]]]:
    t = measure.get("today", {"A": "?", "B": "?"})

    def m(v: str, k: str):
        return measure.get(v, {}).get(k, "?")
    return {
        "v1": {"fr1": (3, f"{m('v1', 'A_calm')} chrome items at rest (today {t['A']}): the axes and dashed boxes are gone, but two grey dims and an info line still repeat on all nine.", "high"),
               "fr2": (5, "Dims and info never leave; a hover brings a marker's axes and profile box; a click is today's edit chrome. Nothing moves further away.", "high"),
               "fr3": (4, "Today's Studio convention, quieter; Fusion also keeps sketch dims on while a sketch is shown.", "medium"),
               "fr4": (3, f"{m('v1', 'B_calm')} items on the 24-marker sheet (today {t['B']}): ids are readable in the info lines but 48 grey dims still make a texture.", "high"),
               "fr5": (5, "styles.css for weights and colours, two conditionals in Viewport.tsx (triads and marker-rect edges only for the hovered or focused feature).", "medium")},
        "v2": {"fr1": (5, f"{m('v2', 'A_calm')} chrome items at rest: only what prints and the sticker's edge; an overflow still draws its red outline, so a problem would stand out.", "high"),
               "fr2": (4, "A hover gives any marker's outline, id, dictionary and size; its dims and axes take one click (which also opens its panel).", "medium"),
               "fr3": (5, "Figma's own model: hover outline and layer name, everything else on selection.", "high"),
               "fr4": (3, f"{m('v2', 'B_calm')} items on the sheet: very calm, but no id is readable until you point, which hurts the Re-ID sheet.", "high"),
               "fr5": (4, "Conditionals in Viewport.tsx (sketch dims, triads, info only for the selection; dimhide already does half), one hover outline and tag element.", "medium")},
        "v3": {"fr1": (4, "Document mode has 0 chrome items and a paper look; but Esc after an edit leaves you in Edit, today's 45.", "medium"),
               "fr2": (4, "One step: the switch, or a click on any marker, and everything today shows is back.", "medium"),
               "fr3": (4, "Fusion's own split: sketch dims show while you edit the sketch, not on the model; a print preview is familiar everywhere.", "medium"),
               "fr4": (3, "Document mode is calm but shows no ids; Edit mode is today's 120 items.", "high"),
               "fr5": (3, "A view mode in the store, a switch in TopBar.tsx, a canvas style for Document, and every layer gated on it.", "medium")},
        "v4": {"fr1": (5, f"{m('v4', 'A_calm')} chrome items with no command running; an overflow's red outline still shows.", "high"),
               "fr2": (2, f"A size needs the command open on the right tab: the Label tab shows {m('v4', 'A_edit')} items and no size; hover only tints the face.", "medium"),
               "fr3": (5, "Fusion's convention exactly: a command owns its manipulators, the dialog's tab says what is being edited, pre-highlight on hover.", "high"),
               "fr4": (3, "Calm, but no ids on the sheet unless a command shows them.", "high"),
               "fr5": (3, "Viewport.tsx reads panel.tab (already in the store) to pick the chrome; a corner-mark ring; ExtrudePanel.tsx folds its notes.", "medium")},
        "v5": {"fr1": (4, f"{m('v5', 'A_calm')} short id badges at fit, one quiet cue per marker; nothing else.", "high"),
               "fr2": (3, "Hover gives the info line; dims and axes need a zoom in; the edited marker always has its chrome.", "medium"),
               "fr3": (2, "Semantic zoom is a maps convention; neither Fusion nor Figma hides dims by zoom level.", "medium"),
               "fr4": (5, f"{m('v5', 'B_calm')} id badges on the 24-marker sheet: every id findable, nothing else; far out the badges get bigger.", "high"),
               "fr5": (4, "Thresholds on camera.zoom (already in the store) in Viewport.tsx and one badge element; the thresholds need tuning per screen size.", "medium")},
        "v6": {"fr1": (4, f"{m('v6', 'A_calm')} chrome items on the canvas, but a permanent list of nine rows sits beside it.", "medium"),
               "fr2": (4, "Ids, types and sizes for every marker need zero steps (the list); hover links list and canvas; dims and axes take a click.", "medium"),
               "fr3": (4, "Figma's layers panel and Fusion's browser: a familiar home for per-object facts.", "medium"),
               "fr4": (4, "The list holds all 24 ids (16 shown, then '+ 8 more'), but finding which marker is #17 needs a hover.", "medium"),
               "fr5": (2, "A new panel component: rows, hover and selection sync both ways, scrolling, collapse, phone layout.", "medium")},
        "v7": {"fr1": (3, f"{m('v7', 'A_calm')} chrome items at rest, all grey on a dot grid: no colour, but more marks than V1.", "high"),
               "fr2": (5, "Everything stays visible; colour marks the selection.", "high"),
               "fr3": (3, "Figma's chrome is monochrome with one blue; Fusion keeps coloured axes, here they are grey until edited.", "medium"),
               "fr4": (2, f"{m('v7', 'B_calm')} grey items on the 24-marker sheet: the axes cross every marker's black, a texture.", "high"),
               "fr5": (5, "CSS only (colours, line weights, a dot-grid pattern) plus the pick colour set to the accent.", "medium")},
        "v8": {"fr1": (5, f"{m('v8', 'A_calm')} chrome items and no grid: the most minimal canvas; an overflow's red outline still shows.", "high"),
               "fr2": (2, "Every layer is a menu plus a toggle away (then it stays on); the edited marker still shows its own chrome.", "high"),
               "fr3": (3, "Blender's overlays; Fusion has per-object visibility and display settings, but not one menu like this.", "medium"),
               "fr4": (3, "Calm, but no ids until Marker info is ticked; then it is today's 24 info lines.", "high"),
               "fr5": (3, "A menu with six persisted per-viewer toggles (Marker info's pattern, store.ts) and each layer gated on one.", "medium")},
        "v9": {"fr1": (4, f"{m('v9', 'A_calm')} chrome items at rest: two dimension pairs with a count, a short id and an origin dot per marker.", "high"),
               "fr2": (5, "A hover gives that marker its own dims, axes, box and full info line; a click is the edit chrome; shared facts sit in the legend.", "high"),
               "fr3": (2, "Counting equal values ('×8') and a legend are not a CAD convention; Fusion would draw an Equal constraint instead.", "medium"),
               "fr4": (5, f"{m('v9', 'B_calm')} items on the 24-marker sheet: one dimension pair '×24', a short id under every marker, one legend line.", "high"),
               "fr5": (3, "Group profiles by equal size, pick a representative, draw the count; id badges; a legend; hover reveals in Viewport.tsx.", "medium")},
        "v10": {"fr1": (5, f"{m('v10', 'A_calm')} chrome items plus one chip that literally answers 'is it OK': 9 markers, ids 0–15, all fit.", "high"),
                "fr2": (4, "Problems come to you with their chrome and the core's warning; any marker's info is a hover away; dims and axes a click.", "medium"),
                "fr3": (3, "A design-rule or problems indicator, not a canvas convention; selection behaves as in Figma.", "medium"),
                "fr4": (3, "The chip states 24 markers, ids 0–23, all fit; per-marker ids appear only on hover.", "high"),
                "fr5": (4, "The data exists (plan overflow_mm and error warnings); a chip, hide-unless-selected-or-bad conditionals, a hover tag.", "medium")},
    }


GATE_EVIDENCE = {
    "g1": "The printed geometry is one live capture under every state; only chrome layers change{x}.",
    "g2": "{y}",
}
GATE_NOTES = {
    "v1": ("", "Every layer still draws; axes and boxes on hover or edit."),
    "v2": ("", "Selecting a marker shows all of its chrome; sketch dims as today's dimhide rule."),
    "v3": (" (Document mode adds a paper shadow under the stickers, outside the print)", "Edit mode is today's canvas, untouched."),
    "v4": (" (the hover tint is a transient 10 % overlay, like Fusion's pre-highlight)", "Each tab shows what it edits; sketch dims with the Dimension tool, as Fusion (not drawn here: low confidence)."),
    "v5": ("", "Zoomed in, every layer returns; the edited marker always has its chrome."),
    "v6": ("", "The list carries ids and sizes; selection shows the rest."),
    "v7": ("", "Every layer still draws, in grey."),
    "v8": ("", "Every layer is a toggle; the edited marker keeps its own chrome."),
    "v9": ("", "Hover restores any marker's own dims, axes, box and info."),
    "v10": ("", "Selection shows all; a marker that needs you shows its chrome."),
}


def gates() -> dict[str, dict[str, tuple[bool, str]]]:
    return {v: {"g1": (True, GATE_EVIDENCE["g1"].format(x=x)), "g2": (True, y)} for v, (x, y) in GATE_NOTES.items()}


NAMES = {}


def judgment(sc: dict) -> dict[str, str]:
    """The recommendation and its hinge, computed from the frozen weights and the scores (never typed)."""
    w0 = {r["id"]: r["weight"] for r in REQUIREMENTS}
    tot = lambda v, w: sum(w[k] * sc[v][k][0] / 5 for k in w)  # noqa: E731
    rank = sorted(sc, key=lambda v: tot(v, w0), reverse=True)
    top, second = rank[0], rank[1]
    gap = tot(top, w0) - tot(second, w0)
    co = [v for v in rank[1:] if tot(top, w0) - tot(v, w0) <= 3]
    lead = (f"{NAMES[top]} (V{top[1:]}) leads at {tot(top, w0):.0f}/100, "
            + (f"within 3 points of {', '.join(f'{NAMES[v]} (V{v[1:]}, {tot(v, w0):.0f})' for v in co)}: treat them as co-leaders. " if co else
               f"{gap:.0f} ahead of {NAMES[second]} (V{second[1:]}, {tot(second, w0):.0f}). "))
    # WHY an assert: the sentence below is written about V2; a rescoring that changes the winner must rewrite it
    assert top == "v2", f"the recommendation text describes V2, but {top} now leads"
    both = [v for v in sc if sc[v]["fr1"][0] == 5 and sc[v]["fr3"][0] == 5]
    assert sorted(both) == ["v2", "v4"], both
    why = (lead + "With V4 it is one of two that score 5 on both the calm first screen and CAD familiarity, and it beats V4 on reach: "
           "at rest the canvas is only what prints, a hover gives any marker its outline, id and size, and a click gives today's full edit chrome "
           "on that one marker, which is Figma's rule exactly (V4's hover gives nothing, and its Label tab hides the sizes). "
           "Its weak spot is the 24-marker sheet: no id is readable until you point.")
    # the hinge: the smallest move of weight from CAD familiarity (fr3) to the 24-marker test (fr4) that changes the winner
    flip = None
    for k in range(1, w0["fr3"]):
        w = dict(w0, fr3=w0["fr3"] - k, fr4=w0["fr4"] + k)
        best = max(sc, key=lambda v: tot(v, w))
        if best != top:
            flip = (k, best, tot(best, w), tot(top, w))
            break
    if flip:
        k, best, tb, tt = flip
        sp = {k_: v_ for k_, v_ in sc[top].items()}
        sp["fr1"], sp["fr4"] = (4, "", ""), (5, "", "")
        splice = sum(w0[k_] * sp[k_][0] / 5 for k_ in w0)
        hinge = (f"Ids on the sheet against CAD familiarity. Move {k} points of weight from 'feels like the CAD it lives in' to 'legible on a sheet of 20+ markers' "
                 f"and {NAMES[best]} (V{best[1:]}) overtakes, {tb:.0f} to {tt:.0f}. If the Re-ID sticker sheet is the main job, that shift is right. "
                 f"The cheaper answer is a splice: V2's rest and hover rules plus V9's short grey id under each marker. Scored the same way "
                 f"(calm 4 instead of 5, the sheet 5 instead of 3, the rest as V2) it totals {splice:.0f} under the frozen weights, and it no longer depends on this weight.")
    else:
        hinge = "No move of weight from CAD familiarity to the 24-marker test changes the winner."
    return {"why": why, "hinge": hinge}


def today_section(facts: dict, measure: dict) -> str:
    a = webp_uri(SHOTS / "today-A-edit.png", lossless=False, quality=80, width=1440)
    b = webp_uri(SHOTS / "today-B.png", lossless=False, quality=80, width=1440)
    t = measure.get("today", {})
    ca, cb = t.get("A", "?"), t.get("B", "?")
    return f"""<section class="uc-today" aria-labelledby="today-heading">
  <div class="eyebrow">The starting point · live, arucostudio.com, {VIEW[0]} × {VIEW[1]}</div>
  <h2 id="today-heading">Today</h2>
  <p>Zach's screenshot rebuilt on the live site: eight dimensioned 37.48 mm profiles with single markers, a 50.8 × 200 ChArUco, corner marks on,
  View › Marker info on, #3 open on the Label tab. Left alone, the canvas draws <b>{ca}</b> chrome items for nine markers (two sketch dims, a Joint Origin,
  an info label and a dashed profile box each) and <b>{cb}</b> for the 24-marker sheet. Every variant below re-renders exactly this chrome, from the live
  page's own SVG, over the same printed geometry.</p>
  <div class="uc-today-grid">
    <figure><img src="{a}" alt="Today: Zach's document on the live site, #3 open on the Label tab"><figcaption>Doc A · #3 being edited (Zach's moment)</figcaption></figure>
    <figure><img src="{b}" alt="Today: a 24-marker sticker sheet on the live site"><figcaption>Doc B · 24 markers at fit, nothing selected</figcaption></figure>
  </div>
</section>"""


GALLERY_CSS = """
.uc-today{margin:26px 0 30px}
.uc-today h2{margin:6px 0 8px;font:500 30px/1.1 var(--serif)}
.uc-today p{max-width:1000px;margin:0 0 14px;color:#494641;font-size:15px;line-height:1.5}
.uc-today-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.uc-today figure{margin:0;border:1px solid var(--line);border-radius:5px;overflow:hidden;background:#fff}
.uc-today img{display:block;width:100%;height:auto}
.uc-today figcaption{padding:8px 10px;font-size:12.5px;color:var(--muted)}
@media (max-width:760px){.uc-today-grid{grid-template-columns:1fr}}
/* the stage fills its card at the stage's own aspect, never taller than the frame */
.prototype:has(> .uc-hero){width:100%;min-height:0;min-width:0}
.variant-grid:not(.focus-layout) .prototype-frame:has(.uc-hero){min-height:0}
.variant-grid:not(.focus-layout) .prototype > .uc-hero{width:min(100%, calc((340px - 84px) * 1.6));margin:0 auto}
.variant-grid.focus-layout .prototype > .uc-hero{width:min(100%, calc((min(90vh, 1400px) - 84px) * 1.6));margin:0 auto}
.prototype-frame:fullscreen .prototype > .uc-hero{width:min(100%, calc((100vh - 48px) * 1.6));margin:0 auto}
.media-surface:has(> .uc-hero){min-height:0}
.variant-grid.focus-layout .media-surface > .uc-hero{width:min(100%, calc((min(70vh, 820px) - 6px) * 1.6));margin:0 auto}
.variant-grid:not(.focus-layout) .media-surface > .uc-hero{width:min(100%, calc((340px - 84px) * 1.6));margin:0 auto}
.uc-hint{margin:8px 2px 2px;font:12px/1.4 var(--sans, system-ui);color:#6b665e}
.uc-hint b{font:700 10px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:#7667c6;margin-right:6px}
.uc-hint span{opacity:.5;margin:0 4px}
"""


def spec_for(facts: dict, measure: dict, built: list[dict]) -> dict:
    NAMES.update({v["id"]: v["name"] for v in built})
    SC, GR = scores(measure), gates()
    JUDGMENT = judgment(SC)
    variants_ = []
    for v in built:
        vid = v["id"]
        m = measure.get(vid, {})
        proof = [f"Re-rendered from the live page's SVG over the live print capture; every story step and the direct clicks driven headless (docs/build_ui_cleanup_proposals.py review)."]
        if m:
            proof.append(f"Canvas chrome items drawn (measured in the built gallery): doc A at rest {m.get('A_calm', '?')}, "
                         f"while editing #3 {m.get('A_edit', '?')}; doc B at rest {m.get('B_calm', '?')}. Today: "
                         f"{measure['today']['A']} / {measure['today']['B']}.")
        sc = SC[vid]
        gr = GR[vid]
        variants_.append({
            "id": vid, "name": v["name"], "thesis": v["thesis"], "accent": v["accent"],
            "bestWhen": v["bestWhen"], "losesWhen": v["losesWhen"],
            "decisions": [{"label": a, "value": b} for a, b in v["decisions"]],
            "keepParts": v["keep"], "proof": proof,
            "previewLabel": "live chrome · hover or click the markers",
            "story": {"title": "Walk through it", "steps": [
                {"label": lab, "caption": cap, "state": st, **({"target": tg} if tg else {})} for st, lab, cap, tg in v["steps"]]},
            "scores": {k: {"score": s, "evidence": ev, "confidence": c} for k, (s, ev, c) in sc.items()},
            "gateResults": {k: {"pass": p, "evidence": ev} for k, (p, ev) in gr.items()},
            "preview": v["preview"],
            "media": [{"label": "24 markers, nothing selected",
                       "caption": "Doc B (a 24-marker sheet, captured live at fit) under this variant's rest-state rules: the 20+ legibility test. Hover works here too.",
                       "html": v["media"]}],
        })
    totals = {v["id"]: sum(r["weight"] * v["scores"][r["id"]]["score"] / 5 for r in REQUIREMENTS) for v in variants_}
    elig = {v["id"]: all(x["pass"] for x in v["gateResults"].values()) for v in variants_}
    rank = sorted(totals, key=lambda i: (elig[i], totals[i]), reverse=True)
    return {
        "schemaVersion": 3, "count": len(variants_),
        "title": "Ten ways to calm the Studio canvas",
        "kicker": "Babble & prune · /babble 10 · ArUco Studio · 2026-10-21",
        "brief": ("Zach: “it feels a bit visually busy.” Ten different rules for what the online Studio draws on top of the markers: "
                  "the sketch dims, the red/green Joint Origins, the marker info labels, the dashed profile boxes, the turn arc and the panel. "
                  "Every variant shows the same live document; the printed geometry never changes."),
        "defaultId": rank[0], "defaultWhy": JUDGMENT.get("why", "Provisional."), "decisionHinge": JUDGMENT.get("hinge", "Provisional."),
        "invariants": ["Doc A (Zach's screenshot rebuilt) and doc B (24 markers), opened on the live site at 1440 × 900; the same camera in every variant.",
                       "The printed geometry is a capture and never changes (gate 1).",
                       "The chrome is the live page's own SVG markup, CSS and tokens (Studio skin, light); a variant only decides what shows, when, and how loud.",
                       "The panel and the top chrome are the live page's pixels."],
        "boundary": ("The markers, the chrome's geometry and styling, the panel and the top chrome are captured from arucostudio.com; which chrome shows "
                     "in which state, and the new overlays (chips, list, legend, menus), are a mock. Hover and the marked clicks are live; nothing in web/ is changed."),
        "axes": AXES, "requirements": REQUIREMENTS, "hardGates": HARD_GATES, "variants": variants_,
        "checks": ["Ten variants on one document", "Criteria and gates fixed before drawing", "Live chrome re-rendered, never redrawn by hand",
                   "Every step and the direct clicks driven headless", "Pick, shortlist, reject, splice export"],
    }


def write_gallery(facts: dict, measure: dict, built: list[dict]) -> dict:
    INLINE_CSS.clear()
    tpl = templates(facts)          # fills INLINE_CSS
    css = [image_css(), base_css(facts)] + [v["css"] for v in built]
    spec = spec_for(facts, measure, built)
    (SRC / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    if OUT.exists():
        OUT.unlink()
    subprocess.run([sys.executable, str(GALLERY), "build", "--spec", str(SRC / "spec.json"), "--output", str(OUT), "--strict"], check=True)
    doc = OUT.read_text()
    doc = doc.replace("</head>", f'<style id="uc-css">{chr(10).join(css)}\n{GALLERY_CSS}</style>\n</head>', 1)
    anchor = '<section class="objective-contract"'
    assert anchor in doc
    doc = doc.replace(anchor, today_section(facts, measure) + "\n    " + anchor, 1)
    doc = doc.replace("</body>", f'<div hidden id="uc-templates">{tpl}</div>\n<script id="uc-js">{STAGE_JS}</script>\n</body>', 1)
    OUT.write_text(doc)
    subprocess.run([sys.executable, str(GALLERY), "check", "--input", str(OUT), "--strict"], check=True)
    return spec


# ---------------------------------------------------------------- 3. review: drive the built gallery headless
REVIEW_JS = r"""
// Generated by docs/build_ui_cleanup_proposals.py -- the built gallery, driven headless. Deleted after the run.
const { chromium } = require("@playwright/test");
const fs = require("fs");
const CFG = %(cfg)s;
const CHROME = '.L-sdims .cad-dim, .L-triads>.triad, .L-edges>path, .L-infos>text, .X-hover>*, .X-tag>*, .X-badge>*, .X-face>*, .X-corner>*, .X-count>*, .E-fdims .cad-dim, .E-arc, .E-handles';
(async () => {
  const b = await chromium.launch({ channel: "chrome" });
  const errors = [], log = { cards: {} };
  const open = async (w, h) => {
    const p = await b.newPage({ viewport: { width: w, height: h } });
    p.on("pageerror", (e) => errors.push(e.message));
    p.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    await p.goto("file://" + CFG.out);
    await p.waitForTimeout(600);
    return p;
  };
  const count = (card, which) => card.evaluate((c, [sel, which]) => {
    const st = which === 'exhibit' ? c.querySelector('.media-surface .uc-stage') :
      [...c.querySelectorAll('.prototype .uc-stage')].find((s) => s.checkVisibility());
    if (!st) return -1;
    const shown = (e) => { for (let x = e; x && x !== st; x = x.parentElement) { const cs = getComputedStyle(x); if (cs.display === 'none' || cs.visibility === 'hidden') return false; } return true; };
    return [...st.querySelectorAll(sel)].filter(shown).length;
  }, [CHROME, which]);
  const p = await open(1280, 800);
  await p.addStyleTag({ content: "#decision-dock{visibility:hidden!important}" });
  const clickC = async (loc) => { await loc.evaluate((e) => e.scrollIntoView({ block: "center" })); await p.waitForTimeout(80); await loc.click(); };
  await p.screenshot({ path: `${CFG.renders}/top-1280.png` });
  await p.locator("#variant-grid").scrollIntoViewIfNeeded();
  await p.waitForTimeout(200);
  await p.screenshot({ path: `${CFG.renders}/grid-1280.png` });
  // today, measured on a stage with no rules: a fresh page with a bare hero
  log.today = await p.evaluate((sel) => {
    const res = {};
    for (const sc of ['A', 'B']) {
      const h = document.createElement('div'); h.className = 'uc-hero'; h.style.width = '600px';
      h.innerHTML = `<div class="uc-stage" data-scene="${sc}"></div>`; document.body.appendChild(h);
      const st = h.querySelector('.uc-stage'); st.prepend(document.getElementById('uc-t-' + sc).content.cloneNode(true));
      const shown = (e) => { for (let x = e; x && x !== st; x = x.parentElement) { const cs = getComputedStyle(x); if (cs.display === 'none' || cs.visibility === 'hidden') return false; } return true; };
      res[sc] = [...st.querySelectorAll(sel)].filter(shown).length; h.remove();
    }
    return res;
  }, CHROME);
  for (const id of CFG.ids) {
    const card = p.locator(`#card-${id}`);
    await p.locator('[data-layout="grid"]').click(); await p.waitForTimeout(100);
    await card.locator("[data-grid-focus-target]").click(); await p.waitForTimeout(250);
    const frame = card.locator(".prototype-frame");
    await frame.scrollIntoViewIfNeeded();
    const proto = card.locator(".prototype");
    const n = await card.locator('[data-story-action="jump"]').count();
    const rec = { steps: [], counts: {} };
    for (let i = 0; i < n; i++) {
      await card.locator(`[data-story-action="jump"][data-story-index="${i}"]`).click(); await p.waitForTimeout(160);
      const state = await proto.getAttribute("data-story-state");
      rec.steps.push(state);
      rec.counts[state] = await count(card, 'hero');
      await frame.screenshot({ path: `${CFG.renders}/${id}-${i + 1}-${state}.png` });
    }
    // direct manipulation: from calm, point at #6 (live hover), click #3 (edit), click the canvas (calm)
    const calmIdx = (await card.evaluate((c) => [...c.querySelectorAll('[data-story-index]')].length)) && rec.steps.indexOf('calm');
    await card.locator(`[data-story-action="jump"][data-story-index="${calmIdx}"]`).click(); await p.waitForTimeout(150);
    const h6 = card.locator('.prototype .uc-stage:visible .uc-hot[data-k="6"]').first();
    await h6.hover(); await p.waitForTimeout(150);
    rec.hoverHot = await card.evaluate((c) => c.querySelectorAll('.prototype .is-hot').length);
    rec.hoverCount = await count(card, 'hero');
    await frame.screenshot({ path: `${CFG.renders}/${id}-hover6.png` });
    await card.locator('.prototype .uc-stage:visible .uc-hot[data-k="3"]').first().click(); await p.waitForTimeout(150);
    rec.click3 = await proto.getAttribute("data-story-state");
    rec.click3caption = await card.locator("[data-story-label]").textContent();
    await p.mouse.move(5, 5);
    const bgBox = await card.locator('.prototype .uc-stage:visible').first().boundingBox();
    await p.mouse.click(bgBox.x + bgBox.width * 0.42, bgBox.y + bgBox.height * 0.18); await p.waitForTimeout(150);
    rec.clickBg = await proto.getAttribute("data-story-state");
    // exhibit
    const ex = card.locator(".media-exhibit").first();
    await ex.scrollIntoViewIfNeeded();
    rec.counts.B_calm = await count(card, 'exhibit');
    await ex.screenshot({ path: `${CFG.renders}/${id}-exhibit.png` });
    log.cards[id] = rec;
  }
  // V8: tick a box directly, V4: click the Marker tab, V3: the switch, V10: Undo, V5: a rung
  const direct = {};
  const jump = async (id, state) => {
    const card = p.locator(`#card-${id}`);
    await p.locator('[data-layout="grid"]').click(); await p.waitForTimeout(100);
    await card.locator("[data-grid-focus-target]").click(); await p.waitForTimeout(200);
    await card.locator(".prototype-frame").scrollIntoViewIfNeeded();
    const idx = log.cards[id].steps.indexOf(state);
    await card.locator(`[data-story-action="jump"][data-story-index="${idx}"]`).click(); await p.waitForTimeout(150);
    return card;
  };
  let c = await jump('v8', 'overlays');
  await c.locator('.v8pop input[data-ov="triads"]').evaluate((e) => e.scrollIntoView({ block: 'center' })); await c.locator('.v8pop input[data-ov="triads"]').check(); await p.waitForTimeout(120);
  direct.v8 = await count(c, 'hero');
  await c.locator('.prototype-frame').screenshot({ path: `${CFG.renders}/v8-direct-triads.png` });
  c = await jump('v4', 'edit');
  await clickC(c.locator('.v4tab-m')); await p.waitForTimeout(150);
  direct.v4 = await c.locator('.prototype').getAttribute('data-story-state');
  c = await jump('v3', 'calm');
  await clickC(c.locator('.v3sw .sw-edit').first()); await p.waitForTimeout(150);
  direct.v3 = await c.locator('.prototype').getAttribute('data-story-state');
  c = await jump('v10', 'problem');
  await clickC(c.locator('.v10undo')); await p.waitForTimeout(150);
  direct.v10 = await c.locator('.prototype').getAttribute('data-story-state');
  c = await jump('v5', 'calm');
  await clickC(c.locator('.prototype .z-far').first()); await p.waitForTimeout(150);
  direct.v5 = await c.locator('.prototype').getAttribute('data-story-state');
  c = await jump('v6', 'calm');
  await c.locator('.prototype .v6row[data-k="7"]').hover(); await p.waitForTimeout(120);
  direct.v6hover = await c.evaluate((x) => x.querySelectorAll('.prototype .X-hover .is-hot').length);
  log.direct = direct;
  await p.locator("#ai-prune").scrollIntoViewIfNeeded(); await p.waitForTimeout(150);
  await p.screenshot({ path: `${CFG.renders}/prune-1280.png` });
  await p.close();
  const m = await open(390, 844);
  await m.addStyleTag({ content: "#decision-dock{visibility:hidden!important}" });
  await m.screenshot({ path: `${CFG.renders}/top-390.png` });
  await m.locator("#variant-grid").scrollIntoViewIfNeeded(); await m.waitForTimeout(200);
  await m.screenshot({ path: `${CFG.renders}/grid-390.png` });
  log.phoneHscroll = await m.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  await m.locator(`#card-v2 .prototype-frame`).scrollIntoViewIfNeeded();
  await m.locator(`#card-v2 .prototype-frame`).screenshot({ path: `${CFG.renders}/card-390.png` });
  await m.close();
  await b.close();
  console.log(JSON.stringify({ errors, log }));
})().catch((e) => { console.error(e); process.exit(1); });
"""


def review(ids: list[str]) -> dict:
    RENDERS.mkdir(parents=True, exist_ok=True)
    cfg = {"out": str(OUT), "renders": str(RENDERS), "ids": ids}
    r = run_temp_cjs("review", REVIEW_JS % {"cfg": json.dumps(cfg)}, 900)
    return json.loads(r.stdout.strip().splitlines()[-1])


def measure_from(rv: dict) -> dict:
    out = {"today": rv["log"]["today"]}
    for vid, rec in rv["log"]["cards"].items():
        c = rec["counts"]
        out[vid] = {"A_calm": c.get("calm"), "A_edit": c.get("edit"), "B_calm": c.get("B_calm")}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--recapture", action="store_true", help="capture the live site again")
    ap.add_argument("--capture-only", action="store_true")
    ap.add_argument("--no-review", action="store_true")
    args = ap.parse_args()
    facts = capture(args.recapture)
    if args.capture_only:
        return 0
    built = variants(facts)
    assert len(built) == 10 and len({v["id"] for v in built}) == 10
    mfile = SRC / "measure.json"
    measure = json.loads(mfile.read_text()) if mfile.exists() else {}
    spec = write_gallery(facts, measure, built)
    print(f"gallery: {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")
    if args.no_review:
        return 0
    rv = review([v["id"] for v in built])
    new = measure_from(rv)
    mfile.write_text(json.dumps(new, indent=1))
    (SRC / "review.json").write_text(json.dumps(rv, indent=1))
    if new != measure:      # the evidence cites the counts: rebuild once with the measured numbers
        write_gallery(facts, new, built)
        print(f"rebuilt with measured counts: {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")
    print("review:", json.dumps({"errors": rv["errors"], "direct": rv["log"]["direct"], "phoneHscroll": rv["log"]["phoneHscroll"],
                                 "cards": {k: {kk: vv for kk, vv in r.items() if kk != "click3caption"} for k, r in rv["log"]["cards"].items()}}, indent=1))
    if rv["errors"]:
        raise SystemExit("the gallery logged errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
