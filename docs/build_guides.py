#!/usr/bin/env python3
"""Build the site's guides, https://arucostudio.com/guides/ (2026-10-21).

    .venv/bin/python docs/build_guides.py                  # run Verify on the board on the newest OpenCV
                                                           # installed, then every page
    .venv/bin/python docs/build_guides.py --opencv 4.11    # the same on another OpenCV (a version, or a Python)
    .venv/bin/python docs/build_guides.py --pages          # the pages only, from the last run (verify.json)

WHY one OpenCV (Zach, 2026-10-21: "Let's only run one, but you can choose,
and by default it should be the most recent one"; docs/peps/0003 decision 3):
OpenCVs draw the same view differently and disagree near the limits (on this
board 4.11 and 5.0 disagreed on 6 of the 28 markers: a label touching the
black lost 186 of 271 reads on 4.11, none on 5.0). Until then the page ran
both and kept the worse; now a run is one OpenCV's, the newest installed
unless --opencv says (aruco_studio/opencv_choice.py finds them: the repo's
.venv, .venv-cv411 beside it), and the page names it and says that others
can differ (OLD_FINDING). verify.json is keyed on it: --pages refuses a run
made on another OpenCV than the one asked for (the newest by default).
e2e/guides.spec.ts checks the browser's own sweep against a run on the
browser's OpenCV.

Writes (all under web/public/, which Vite copies into the static site as it is):

  examples/label-placement.arucostudio-web.json   the label placement test board: a Studio
                                                  document, opened by /?example=label-placement
  guides/index.html                               the Guides grid
  guides/label-placement/index.html               Label placement: Verify's results on that board
  guides/label-placement/verify.json              the run behind it (each marker's plan, its rules,
                                                  the check), read back by web/e2e/guides.spec.ts
  guides/label-placement/media/*.webp             the views a label lost, marked and bare
  guides/<decision>/index.html                    one short page per design decision

WHY generated (Zach, 2026-10-21): "the documentation is basically showing
the results of Verify". Every verdict on the label page is the core's own
output -- the plan's rule check (MarkerPlan.warnings) and Verify's label and
corner-mark check (aruco_studio/web_marks.py) -- never typed here; the
headline sentences are checked against them (HEADLINES) and the build
fails when a run disagrees. The decision pages' numbers are computed by the
same core (web_api, web_ids, core.presets) each build, so they move when the
code does.

The pages are standard library only. The Verify run imports the repo's core
with numpy and OpenCV (aruco_studio.web_marks) in the chosen OpenCV's Python
(this one when it is that, else that Python with this checkout's code), so
run it with the repo's .venv; --pages needs neither (it only asks the Pythons
here which OpenCV they have).
"""
from __future__ import annotations

import argparse
import copy
import datetime
import hashlib
import html
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aruco_studio import opencv_choice as OC             # noqa: E402  (standard library only)
from aruco_studio import web_api as W                    # noqa: E402  (standard library only)
from aruco_studio import web_ids as IDS                  # noqa: E402
from aruco_studio.core import presets as CP              # noqa: E402
from aruco_studio.core import rect_fill as RF            # noqa: E402

PUBLIC = ROOT / "web" / "public"
GUIDES = PUBLIC / "guides"
LP = GUIDES / "label-placement"
MEDIA = LP / "media"
RESULTS = LP / "verify.json"
BOARD_NAME = "label-placement"
BOARD = PUBLIC / "examples" / f"{BOARD_NAME}.arucostudio-web.json"
OPEN_BOARD = f"/?example={BOARD_NAME}"
BOARD_URL = f"/examples/{BOARD_NAME}.arucostudio-web.json"
ICON = PUBLIC / "icon.svg"
SITE = "https://arucostudio.com"
GITHUB = "https://github.com/zacharyyamaoka/aruco-studio"
SRC = f"{GITHUB}/blob/main"
# WHY a cap per page: the guides are read on phones; the label page carries
# 28 stickers drawn inline and a few small views
PAGE_BUDGET = 400 * 1024
# The finding the page links where it says other OpenCVs can differ: the last
# run with two (4.11 and 5.0, both kept, the worse governing), on GitHub at
# the commit that published it.
OLD_FINDING = {"commit": "078f361", "versions": ("4.11", "5.0"), "disagree": ("B5", "B7", "B8", "C4", "D4", "E4"),
               "url": f"{GITHUB}/blob/078f361/web/public/guides/label-placement/verify.json"}

INK = next(p for p in W.presets() if p["name"] == "Inkjet · Letter vinyl")
# the Studio's defaults for a new marker (web/src/model/doc.ts DEFAULT_MARKER / DEFAULT_LABEL)
MARKER0 = {"type": "single", "dictionary": "DICT_4X4_50", "first_id": 0, "auto": True, "marker_mm": 30,
           "checker_mm": 0, "separation_mm": 0, "cols": 1, "rows": 1, "turn": 0, "flip": False,
           "quiet_modules": 1, "corner_mark": "none"}
LABEL0 = {"on": False, "text": "#{ids}", "height_mm": 0, "side": "below", "gap_mm": 2, "offset_mm": [0, 0]}
LISTED = ("marker.type", "marker.dictionary", "marker.first_id", "marker.cols", "marker.rows", "marker.turn",
          "marker.flip", "marker.corner_mark", "label.on", "label.side", "label.gap_mm")

# ------------------------------------------------------------------ the board

SIDE = 30.0                       # a single's square: the 0.5 mm step makes its marker 22 mm
CELL = 22.0 / 6.0                 # that marker's cell (module): 3.67 mm
STICKER = 8 * CELL                # its sticker: 6 cells and a 1-cell quiet zone each side
BOARD_W, BOARD_H = 60.0, 48.0     # a 5 x 4 ChArUco board: 12 mm squares
GRID_SIDE = 60.0
ON_BLACK = {"on": True, "place": "on_marker", "surface": "black"}
ON_WHITE = {"on": True, "place": "on_marker", "surface": "white"}
OUTSIDE = {"on": True, "place": "outside"}
GRID = {"type": "grid", "cols": 2, "rows": 2}
CHARUCO = {"type": "charuco", "dictionary": "DICT_4X4_100", "cols": 5, "rows": 4}


@dataclass
class Case:
    key: str                      # its name on the board and in the guide ("B3")
    group: str
    title: str                    # what it varies, in a few words
    marker: dict = field(default_factory=dict)
    label: dict = field(default_factory=dict)
    size: tuple = (SIDE, SIDE)
    gap_cells: float | None = None  # outside: the label's gap from the quiet zone, in cells
    first_id: int = 0
    # filled by board():
    fid: str = ""
    rect: dict = field(default_factory=dict)
    req: dict = field(default_factory=dict)


GROUPS = {
    "ref": ("The bare marker", "No label and no corner mark: what every other marker is measured against."),
    "black": ("On the marker: the black border row",
              "Where a label goes when you turn it on: white letters knocked out of the marker's outer row of black "
              "cells, half a cell tall (Label › Place: On marker, Surface: Black)."),
    "white": ("On the marker: the quiet zone",
              "Black letters in the white ring round the marker (Surface: White)."),
    "outside": ("Outside the marker",
                "The label in its own band of the rectangle (Place: Outside), Gap away from the quiet zone; "
                "a negative Gap pushes the band over it."),
    "boards": ("Grids and ChArUco boards", "A grid's label goes in the border row of its edge marker nearest the "
               "middle; a ChArUco board's in a black square of its edge row."),
    "corner": ("Corner marks", "Corner mark › Black triangle (labels off). On a ChArUco board, whose top-left square "
               "is black, the Studio cuts that square's outer corner instead."),
}

CASES = [
    Case("A1", "ref", "No label, no corner mark"),
    Case("B1", "black", "Below", label=dict(ON_BLACK)),
    Case("B2", "black", "Above", label=dict(ON_BLACK, side="above")),
    Case("B3", "black", "Left", label=dict(ON_BLACK, side="left")),
    Case("B4", "black", "Right", label=dict(ON_BLACK, side="right")),
    Case("B5", "black", "Letters ¾ cell tall", label=dict(ON_BLACK, height_mm=round(0.75 * CELL, 6))),
    Case("B6", "black", "Letters a whole cell tall", label=dict(ON_BLACK, height_mm=round(CELL, 6))),
    Case("B7", "black", "Longer text: “#{ids} {dict}”", label=dict(ON_BLACK, text="#{ids} {dict}")),
    Case("B8", "black", "Text longer than the row: “#{ids} {dict} {type}”",
         label=dict(ON_BLACK, text="#{ids} {dict} {type}")),
    Case("B9", "black", "Moved up one cell, onto the data cells", label=dict(ON_BLACK, offset_mm=[0, round(CELL, 6)])),
    Case("C1", "white", "Below", label=dict(ON_WHITE)),
    Case("C2", "white", "Above", label=dict(ON_WHITE, side="above")),
    Case("C3", "white", "Left", label=dict(ON_WHITE, side="left")),
    Case("C4", "white", "Right", label=dict(ON_WHITE, side="right")),
    Case("D1", "outside", "Below, Gap 2 mm (the default)", label=dict(OUTSIDE), gap_cells=None),
    Case("D2", "outside", "Below, Gap 0: touching the quiet zone", label=dict(OUTSIDE), gap_cells=0.0),
    Case("D3", "outside", "Below, Gap −½ cell: half way into the quiet zone", label=dict(OUTSIDE), gap_cells=-0.5),
    Case("D4", "outside", "Below, Gap −1 cell: touching the black", label=dict(OUTSIDE), gap_cells=-1.0),
    Case("D5", "outside", "Above, Gap 2 mm", label=dict(OUTSIDE, side="above")),
    Case("D6", "outside", "Left, Gap 2 mm", label=dict(OUTSIDE, side="left")),
    Case("D7", "outside", "Right, Gap 2 mm", label=dict(OUTSIDE, side="right")),
    Case("E1", "boards", "Grid 2 × 2: in its border row", marker=dict(GRID), label=dict(ON_BLACK),
         size=(GRID_SIDE, GRID_SIDE)),
    Case("E2", "boards", "ChArUco 5 × 4: in a black square", marker=dict(CHARUCO), label=dict(ON_BLACK),
         size=(BOARD_W, BOARD_H)),
    Case("E3", "boards", "ChArUco 5 × 4: in a white square's margin", marker=dict(CHARUCO), label=dict(ON_WHITE),
         size=(BOARD_W, BOARD_H)),
    Case("E4", "boards", "ChArUco 5 × 4: moved toward a chessboard corner", marker=dict(CHARUCO),
         label=dict(ON_BLACK, offset_mm=[3.5, 3.5]), size=(BOARD_W, BOARD_H)),
    Case("F1", "corner", "Single: black triangle", marker={"corner_mark": "triangle"}),
    Case("F2", "corner", "Grid 2 × 2: black triangle", marker=dict(GRID, corner_mark="triangle"),
         size=(GRID_SIDE, GRID_SIDE)),
    Case("F3", "corner", "ChArUco 5 × 4: the black square's corner cut", marker=dict(CHARUCO, corner_mark="triangle"),
         size=(BOARD_W, BOARD_H)),
]
ROWS = [["A1", "B1", "B2", "B3", "B4"], ["B5", "B6", "B7", "B8", "B9"], ["C1", "C2", "C3", "C4"],
        ["D1", "D2", "D3", "D4"], ["D5", "D6", "D7"], ["E1", "E2", "E3", "E4"], ["F1", "F2", "F3"]]
GAP_X, GAP_Y = 12.0, 14.0
# WHY ids by hand: unique across the board, so "#12" names one marker. The
# singles and grids take DICT_4X4_50 in board order; a 5 x 4 ChArUco board
# prints 10 ids, more than 4X4_50 has left, so the boards take DICT_4X4_100
# (the same family: its first 50 are 4X4_50's) from 50 up, a block of ten
# each. They sit in the ledger as the auto ids a fresh board would keep.
CHARUCO_FIRST = {"E2": 50, "E3": 60, "E4": 70, "F3": 80}

# The headline: each sentence names the markers it speaks for and the
# verdicts they must have; build() stops when a run disagrees, so the prose
# can never drift from what Verify and the rules say.
HEADLINES = [
    ("Safe: the black border row, on any side, at the Studio's own size (half a cell) with a short id like #12.",
     ["B1", "B2", "B3", "B4"], {"safe"}),
    ("Safe: outside the quiet zone, on any side, with a Gap of 0 or more.",
     ["D1", "D2", "D5", "D6", "D7"], {"safe"}),
    ("Safe: a ChArUco label in its black square; a grid's in its border row.", ["E1", "E2"], {"safe"}),
    ("Safe: the black triangle corner mark, and ChArUco's cut corner.", ["F1", "F2", "F3"], {"safe"}),
    # WHY not B7 (2026-10-21, one OpenCV): a longer text that still fits the row is safe on 5.0 and by the rules;
    # only 4.11 lost reads there (the old finding), so it no longer stands under "not safe"
    ("Not safe: letters taller than half a cell, or a text longer than the border row.", ["B5", "B6", "B8"],
     {"marginal", "unsafe"}),
    ("Not safe: any ink in the quiet zone, the white ring round the marker.", ["C1", "C2", "C3", "C4", "D3", "D4", "E3"],
     {"marginal", "unsafe"}),
    ("Not safe: a ChArUco label near a chessboard corner.", ["E4"], {"marginal", "unsafe"}),
]


def rect_corners(r: dict) -> list:
    """web/src/model/geom.ts rectCorners, the same arithmetic (the profile the Studio sends)."""
    a = r["angle_deg"] * math.pi / 180.0
    c, s = math.cos(a), math.sin(a)
    hw, hh = r["w"] / 2.0, r["h"] / 2.0
    return [[r["cx"] + u * c - v * s, r["cy"] + u * s + v * c] for u, v in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]


def plan_request(doc: dict, f: dict) -> dict:
    """web/src/model/doc.ts planRequest for a feature on a plain rectangle (the board's only kind)."""
    shape = next(s for s in doc["shapes"] if s["id"] == f["profile"]["outer"])
    return {"trim": f["trim"], "profile": {"loops": [rect_corners(shape)]}, "holes": f["holes"],
            "marker": f["marker"], "label": f["label"], "preset": f["preset"], "reference_face": False,
            "extrude": f["extrude"]}


_BOX: list = []


def least_box() -> float:
    """The shortest box side the core still fits the 22 mm marker in (its sticker is 29.33 mm; the
    core keeps a hair more), found by bisection on the core itself, to 1 um."""
    if not _BOX:
        lo, hi = STICKER, SIDE
        assert W.plan(req_rect(SIDE, hi))["marker_mm"] == 22.0 and W.plan(req_rect(SIDE, lo))["marker_mm"] < 22.0
        while hi - lo > 1e-6:
            mid = (lo + hi) / 2.0
            lo, hi = (lo, mid) if W.plan(req_rect(SIDE, mid))["marker_mm"] == 22.0 else (mid, hi)
        _BOX.append(math.ceil(hi * 1e6) / 1e6)
    return _BOX[0]


def outside_size(case: Case) -> tuple:
    """The rectangle that leaves the marker's box just big enough for the 22 mm marker, so the label
    stands Gap from the quiet zone (the box centres the marker: any spare white would add half itself
    to the gap): that box + the core's band (core.rect_fill.fill, with the driven cap web_api._outside
    settles on, one cell) + the gap. where_of measures what it came to."""
    lab = case.label
    text = W.label_text(lab.get("text", LABEL0["text"]), "single", MARKER0["dictionary"], [case.first_id])
    side = lab.get("side", "below")
    fl = RF.fill(200.0, 200.0, text, font="sans", cap_mm=CELL, side=side, gap_mm=float(lab["gap_mm"]),
                 band_cap_mm=CELL, driven=True)
    u0, v0, u1, v1 = fl.band
    gap = float(lab["gap_mm"])
    if side in ("below", "above"):
        return SIDE, round(least_box() + (v1 - v0) + gap + 1e-6, 6)
    return round(least_box() + (u1 - u0) + gap + 1e-6, 6), SIDE


def board():
    """The test board as a Studio document (format arucostudio-web 4) and its cases, each with its request."""
    by_key = {c.key: c for c in CASES}
    assert [k for row in ROWS for k in row] == [c.key for c in CASES], "ROWS lists every case once, in board order"
    nxt = 0
    for c in CASES:
        if c.key in CHARUCO_FIRST:
            c.first_id = CHARUCO_FIRST[c.key]
        else:
            c.first_id = nxt
            n = {"single": 1, "grid": c.marker.get("cols", 1) * c.marker.get("rows", 1)}[c.marker.get("type", "single")]
            nxt += n
        if c.group == "outside":
            c.label = dict(c.label, gap_mm=LABEL0["gap_mm"] if c.gap_cells is None else round(c.gap_cells * CELL, 6))
            c.size = outside_size(c)
    shapes, features, ledger = [], [], {}
    top = 0.0
    for row in ROWS:
        left, tall = 0.0, 0.0
        for k in row:
            c = by_key[k]
            w, h = c.size
            c.fid = f"lp-{k}"
            c.rect = {"kind": "rect", "id": f"{c.fid}-r", "cx": round(left + w / 2.0, 6), "cy": round(top - h / 2.0, 6),
                      "w": w, "h": h, "angle_deg": 0}
            left += w + GAP_X
            tall = max(tall, h)
        top -= tall + GAP_Y
    for c in CASES:
        marker = dict(MARKER0, **c.marker, first_id=c.first_id)
        label = dict(LABEL0, **c.label)
        typed = [p for p in LISTED if p != "marker.first_id"
                 and (marker if p.startswith("marker.") else label)[p.split(".")[1]]
                 != (MARKER0 if p.startswith("marker.") else LABEL0)[p.split(".")[1]]]
        shapes.append(c.rect)
        features.append({"id": c.fid, "key": c.fid, "profile": {"outer": c.rect["id"], "holes": []}, "holes": "avoid",
                         "trim": "profile", "marker": marker, "label": label, "extrude": {},
                         "preset": copy.deepcopy(INK), "set": typed})
        ledger[c.fid] = c.first_id
    doc = {"format": "arucostudio-web", "version": 4, "name": "Label placement test board", "shapes": shapes,
           "dims": [], "features": features, "id_ledger": ledger, "default_preset": copy.deepcopy(INK)}
    for c, f in zip(CASES, features):
        c.req = plan_request(doc, f)
    return doc


def board_text(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


# ------------------------------------------------------------------ the run (numpy + OpenCV)

RULE_FIELDS = ("label.", "marker.corner_mark")


def rule_check(plan: dict) -> tuple:
    """The plan's own rule check: its warnings and errors on the label and the corner mark (what the
    Studio's panel shows). Any of them: "unsafe" (the rule's study measured a cost there)."""
    hits = [w["text"] for w in plan.get("warnings", [])
            if w["level"] in ("warn", "error") and w["field"].startswith(RULE_FIELDS)]
    return ("unsafe" if hits else "safe"), hits


def label_box(plan: dict):
    """The label's text block in the sketch frame (u0, v0, u1, v1): Helvetica's widths at the cap, the
    lines stacked as core.rect_fill stacks them, turned with the label."""
    lab = plan.get("label")
    if not lab or lab.get("font") != "sans":
        return None
    cap = float(lab["height_mm"])
    lines = lab["lines"]
    bw = max(W.text_width(t, cap) for t in lines)
    bh = len(lines) * cap + (len(lines) - 1) * RF.LINE_GAP * cap
    turned = abs(round(float(lab["angle_deg"])) % 180) == 90
    fw, fh = (bh, bw) if turned else (bw, bh)
    x, y = lab["at"]
    return (x - fw / 2.0, y - fh / 2.0, x + fw / 2.0, y + fh / 2.0)


def black_box(plan: dict):
    pts = [p for poly in plan["black"] for p in poly["outer"]]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))


def where_of(c: Case, plan: dict) -> dict:
    """Where the label is, from the plan: its cap in cells and, beside the marker, its distance from the black."""
    lab = c.req["label"]
    out = {"cap_cells": None, "from_black_cells": None}
    if not lab.get("on") or not plan.get("label"):
        return out
    cell = float(plan["cell_mm"])
    out["cap_cells"] = round(float(plan["label"]["height_mm"]) / cell, 3)
    tb = label_box(plan)
    if tb is not None and plan["marker_mm"] and c.req["marker"]["type"] == "single":
        bb = black_box(plan)
        dx = max(bb[0] - tb[2], tb[0] - bb[2], 0.0)
        dy = max(bb[1] - tb[3], tb[1] - bb[3], 0.0)
        inside = tb[0] >= bb[0] - 1e-6 and tb[2] <= bb[2] + 1e-6 and tb[1] >= bb[1] - 1e-6 and tb[3] <= bb[3] + 1e-6
        out["from_black_cells"] = None if inside else round(math.hypot(dx, dy) / cell, 3)
    return out


def bench_camera(plan: dict) -> dict:
    """The Verify dialog's bench camera (web/src/verify/bench.ts benchCamera): 16 px per cell head on,
    set back further when the outline would not fit 80 % of the sensor's short side."""
    w, h, hfov = 1280, 960, 60.0
    f = w / 2.0 / math.tan(math.radians(hfov) / 2.0)
    dist = max(plan["cell_mm"] * f / 16.0, max(plan["outer_mm"]) * f / (0.8 * min(w, h)))
    return {"distance_mm": dist, "resolution": [w, h], "hfov_deg": hfov}


def clean(tilt: float, camera: dict) -> dict:
    return {"camera": camera, "tilt_deg": float(tilt), "yaw_deg": 0.0, "blur_px": 0.0, "noise": 0.0, "glare": 0.0,
            "occlusion": 0.0, "seed": 0}


def bench_sweep(V, C, d: dict, scene, camera: dict):
    """Verify's own angle sweep (VerifyDialog: the bench camera, tilt 0-85 deg in 5 deg steps, a clean
    view, seed 0) -> the last tilt read in full counting up from 0 (None: not even head on)."""
    cam = C.Cam.of(camera)
    last = None
    for t in range(0, 90, 5):
        o = V._view(d, scene, cam, clean(t, camera), picture=False)
        if o["missing"] or o["wrong"]:
            break
        last = t
    return last


def browser_opencvs() -> list:
    """The OpenCVs the Studio's own Verify can load in the browser, newest first: the Pyodide lock's
    opencv-python (from Pyodide's CDN) and the wheels the site serves (web/public/opencv/), as
    cv2.__version__ ("4.11.0"). web/src/core/opencv.ts lists the same (its opencv.test.ts holds it to these)."""
    out = []
    for lock in (ROOT / "web" / "public" / "pyodide" / "pyodide-lock.json",
                 ROOT / "web" / "node_modules" / "pyodide" / "pyodide-lock.json"):
        if lock.exists():
            pkg = json.loads(lock.read_text())["packages"].get("opencv-python")
            if pkg:
                out.append(pkg["version"])
            break
    out += [w.name.split("-")[1] for w in sorted((PUBLIC / "opencv").glob("*.whl"))]
    return sorted({".".join(v.split(".")[:3]) for v in out}, key=OC.version_key, reverse=True)


def studio_opencv():
    """The OpenCV the Studio's own Verify runs in the browser by default: the newest it can load
    (web/src/core/opencv.ts), e.g. "4.11.0"; None when nothing says (no lock on disk)."""
    found = browser_opencvs()
    return found[0] if found else None


def same_opencv(a: str, b) -> bool:
    """cv2.__version__ "4.11.0" is opencv-python "4.11.0.86" (the wheel adds its own build number)."""
    return bool(b) and str(a).split(".")[:3] == str(b).split(".")[:3]


def run_sweeps(doc: dict) -> dict:
    """Verify's angle sweep of every marker on the board (as planned, label and all) under THIS Python's
    OpenCV: {feature id: the last tilt read in full, or None}, and the OpenCV. What web/e2e/guides.spec.ts
    holds the browser's own sweep to when the browser runs another OpenCV than the page's run."""
    import cv2
    from aruco_studio import web_verify as V
    from aruco_studio.verify import camera as C
    out = {}
    for c in CASES:
        req = V.placed(c.req)
        d = V._plan(req)
        out[c.fid] = bench_sweep(V, C, d, C.scene_of(d, V._label(req, d)), bench_camera(W.plan(c.req)))
    return {"opencv": cv2.__version__, "sweeps": out}


def run_detector(doc: dict) -> dict:
    """Verify on every marker of the board under THIS Python's OpenCV: the label and corner-mark check,
    the dialog's bench view and angle sweep and the head-on read limit (marked and bare), and the
    easiest view a label lost as two pictures. Progress on stderr."""
    import platform
    import cv2
    import numpy as np
    from aruco_studio import web_marks as M
    from aruco_studio import web_verify as V
    from aruco_studio.verify import camera as C
    tag = "cv" + "".join(cv2.__version__.split(".")[:3])
    MEDIA.mkdir(parents=True, exist_ok=True)
    for old in MEDIA.glob(f"*-{tag}-*.webp"):
        old.unlink()
    cam1080 = C.Cam.of({"distance_mm": 1000.0, "resolution": [1920, 1080], "hfov_deg": 70.0})
    out = {}
    t_all = time.time()
    for c in CASES:
        t0 = time.time()
        plan = W.plan(c.req)
        marks = M.check(c.req)
        req = V.placed(c.req)
        d = V._plan(req)
        lab = V._label(req, d)
        marked = C.scene_of(d, lab)
        bare = C.Scene(M.bare_plan(d), marked.bounds, marked.centre, marked.area, None)
        bench = bench_camera(plan)
        b_view = V._view(d, marked, C.Cam.of(bench), clean(0, bench), picture=False)
        sweep = {"marked": bench_sweep(V, C, d, marked, bench), "bare": bench_sweep(V, C, d, bare, bench)}
        limit = {"marked": round(V.max_distance(d, marked, cam1080), 1), "bare": round(V.max_distance(d, bare, cam1080), 1)}
        pictures = None
        if marks["reads_verdict"] != "safe" and marks["views_lost"]:
            # the easiest view it lost: the nearest, then the sharpest, then the least tilted
            v = min(marks["views_lost"], key=lambda x: (x["camera"]["distance_mm"], x["blur_px"], x["tilt_deg"]))
            cam = C.Cam.of(v["camera"])
            images = []
            for kind, scene in (("bare", bare), ("marked", marked)):
                sim = C.simulate(scene, cam, v)
                got = C.read(sim, d)
                want = list(d["ids"])
                missing = sorted(set(want) - set(i for i in got["ids"] if i in want))
                ok, buf = cv2.imencode(".webp", C.picture(sim, d, got, missing, 300), [cv2.IMWRITE_WEBP_QUALITY, 85])
                assert ok
                name = f"{c.key.lower()}-{tag}-{kind}.webp"
                (MEDIA / name).write_bytes(buf.tobytes())
                images.append({"kind": kind, "file": name, "missing": missing})
            pictures = {"view": {"px_per_cell": round(plan["cell_mm"] * cam.f_px / cam.distance_mm, 1),
                                 "blur_px": v["blur_px"], "tilt_deg": v["tilt_deg"], "seed": v["seed"],
                                 "conditions": v}, "images": images}
        keep = ("version", "views", "ids", "label", "corner_mark", "reads", "lost", "gained", "cost_pts", "p", "easy",
                "wrong", "reads_verdict", "verdict", "text", "map", "pose")
        out[c.key] = {"marks": {k: marks[k] for k in keep}, "bench_reads": bool(b_view["ok"]), "bench": bench,
                      "sweep_reads_to_deg": sweep, "limit_mm": limit, "pictures": pictures,
                      # a few views it lost, for the e2e to read in the browser's own Verify
                      "views_lost_sample": marks["views_lost"][:3]}
        print(f"  [{cv2.__version__}] {c.key} {marks['verdict']:8s} lost {marks['lost']:3d}/{marks['reads']['bare']:4d} "
              f"easy {marks['easy']['lost']:2d}/{marks['easy']['bare']:3d} pose {marks['pose']['verdict']:8s} "
              f"bench {'reads' if b_view['ok'] else 'MISSES'} sweep {sweep['bare']}/{sweep['marked']} "
              f"limit {limit['bare']:.0f}/{limit['marked']:.0f} {time.time() - t0:5.1f} s", file=sys.stderr, flush=True)
    return {"opencv": cv2.__version__, "numpy": np.__version__, "python": platform.python_version(),
            "seconds": round(time.time() - t_all), "cases": out}


def worst(*verdicts: str) -> str:
    return max(verdicts, key=("safe", "marginal", "unsafe").index)


def results_of(doc: dict, run: dict) -> dict:
    """The run behind the page: each marker's plan and rules (the core, standard library) and the ONE
    OpenCV's check; its verdict the worse of the two."""
    from aruco_studio import web_marks as M
    studio = studio_opencv()
    cases = []
    for n, c in enumerate(CASES, start=1):
        plan = W.plan(c.req)
        assert plan["ok"], (c.key, plan.get("warnings"))
        rule, hits = rule_check(plan)
        verify = run["cases"][c.key]
        cases.append({"key": c.key, "group": c.group, "title": c.title, "feature": c.fid, "number": n,
                      "plan": {"ids": plan["ids"], "cell_mm": plan["cell_mm"], "outer_mm": plan["outer_mm"],
                               "marker_mm": plan["marker_mm"], "summary": plan["summary"],
                               "label_cap_mm": None if not plan.get("label") else plan["label"]["height_mm"]},
                      "where": where_of(c, plan), "rules": {"verdict": rule, "hits": hits}, "verify": verify,
                      "verdict": worst(rule, verify["marks"]["verdict"])})
    return {"generated": datetime.date.today().isoformat(), "core_version": W.core_version(), "commit": commit(),
            "verify_version": M.VERSION, "grid": M.GRID,
            # the one OpenCV of this run (the page's and every verdict's), and the browser's
            "opencv": run["opencv"], "studio_opencv": studio,
            "detector": {"opencv": run["opencv"], "numpy": run["numpy"], "python": run["python"],
                         "seconds": run["seconds"], "studio": same_opencv(run["opencv"], studio)},
            "thresholds": {"marginal_pts": M.MARGINAL_PTS, "unsafe_pts": M.UNSAFE_PTS, "p_max": M.P_MAX,
                           "easy_px_per_cell": M.EASY_PX_PER_CELL, "easy_blur_px": M.EASY_BLUR_PX,
                           "easy_share": M.EASY_SHARE, "easy_min": M.EASY_MIN,
                           "pose_marginal": M.POSE_MARGINAL, "pose_unsafe": M.POSE_UNSAFE,
                           "pose_sharp_cells": M.POSE_SHARP_CELLS, "pose_min_views": M.POSE_MIN_VIEWS},
            "board": BOARD_URL, "board_sha256": hashlib.sha256(board_text(doc).encode()).hexdigest(),
            "cases": cases}


def commit() -> str:
    """The repo's commit (git describe), or "" outside a checkout."""
    import subprocess
    try:
        return subprocess.run(["git", "-C", str(ROOT), "describe", "--always", "--dirty"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


# The study numbers the page cites, and the core file each must still stand in (word for word): the
# page copies them from there, so a change in the core that drops one stops the build.
CITED = [("430,260 simulated photos", "core/label.py"), ("298,000 simulated", "core/chamfer.py"),
         ("`black_id_white` -0.3 pts, n.s.", "core/label.py"), ("-11 pts for a", "core/label.py"),
         ("up to -40 once a printer's dots spread", "core/label.py"), ("0.5 module -7.3", "core/label.py"),
         ("0.7\n# -1.5", "core/label.py"), ("n = 3000", "core/label.py"),
         ("closer than 0.3 square to", "core/label.py"), ("free (`tri_tl`", "core/chamfer.py"),
         ("never on a marker: corner 0 slides", "core/chamfer.py")]


def check_cited() -> None:
    bad = [(t, f) for t, f in CITED if t not in (ROOT / "aruco_studio" / f).read_text()]
    if bad:
        raise SystemExit("the page cites numbers the core no longer says:\n" + "\n".join(f"  {t!r} in {f}" for t, f in bad))


def check_sitemap() -> None:
    """Every guide is in web/public/sitemap.xml (kept by hand, beside the landing's two pages)."""
    text = (PUBLIC / "sitemap.xml").read_text()
    missing = [u for u in [f"{SITE}/guides/"] + [f"{SITE}/guides/{g.slug}/" for g in GUIDE_LIST] if f"<loc>{u}</loc>" not in text]
    if missing:
        raise SystemExit("add to web/public/sitemap.xml: " + ", ".join(missing))


def check_old_finding() -> None:
    """The page's OLD_FINDING is what that run says: the markers its two OpenCVs disagreed on (its
    verify.json, read from git at that commit). Said and skipped when the commit is not here."""
    import subprocess
    path = f"{OLD_FINDING['commit']}:web/public/guides/label-placement/verify.json"
    try:
        text = subprocess.run(["git", "-C", str(ROOT), "show", path], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        print(f"note: {OLD_FINDING['commit']} is not in this clone: the page's old finding is not re-checked", file=sys.stderr)
        return
    old = json.loads(text)
    got = tuple(c["key"] for c in old["cases"] if len({v["marks"]["verdict"] for v in c["verify"].values()}) > 1)
    versions = tuple(sorted(OC.short(d["opencv"]) for d in old["detectors"]))
    if got != OLD_FINDING["disagree"] or versions != tuple(sorted(OLD_FINDING["versions"])):
        raise SystemExit(f"OLD_FINDING cites {OLD_FINDING['disagree']} on OpenCV {OLD_FINDING['versions']}; "
                         f"that run says {got} on {versions}")


def check_headlines(results: dict) -> None:
    by = {r["key"]: r for r in results["cases"]}
    bad = [(text, k, by[k]["verdict"]) for text, keys, ok in HEADLINES for k in keys if by[k]["verdict"] not in ok]
    if bad:
        raise SystemExit("the headline disagrees with the run:\n" + "\n".join(f"  {k} is {v}: {t}" for t, k, v in bad))


# ------------------------------------------------------------------ the pages: shared

def esc(s) -> str:
    return html.escape(str(s), quote=True)


def num(v: float, nd: int = 2) -> str:
    """A number as the page prints it: no trailing zeros, a real minus sign."""
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".") if nd else f"{v:.0f}"
    return s.replace("-", "−") if s not in ("-0", "−0") else "0"


def sv(v: float, nd: int = 4) -> str:
    """A number for markup (an SVG attribute): plain ASCII, no trailing zeros."""
    s = f"{v:.{nd}f}"
    s = s.rstrip("0").rstrip(".") if "." in s else s
    return "0" if s in ("-0", "") else s


CSS = """
:root {
  --bg: #ffffff; --fg: #191c20; --muted: #5d6570; --line: #e4e7eb; --soft: #f6f7f9;
  --accent: #2f6fed; --accent-fg: #ffffff; --quote: #3a4049;
  --safe: #1a7f37; --safe-bg: #1a7f3714; --marginal: #9a6700; --marginal-bg: #bf870014;
  --unsafe: #cf222e; --unsafe-bg: #cf222e12;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #15171a; --fg: #e8eaed; --muted: #9aa2ad; --line: #2c3036; --soft: #1d2024;
    --accent: #5b8ff5; --accent-fg: #0d1117; --quote: #c9ced6;
    --safe: #4ac26b; --safe-bg: #4ac26b1a; --marginal: #d29922; --marginal-bg: #d299221a;
    --unsafe: #ff7b72; --unsafe-bg: #ff7b721a;
    color-scheme: dark;
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
a { color: var(--accent); }
img { max-width: 100%; height: auto; display: block; }
code { font: 0.9em ui-monospace, SFMono-Regular, Menlo, monospace; background: var(--soft); border: 1px solid var(--line);
  border-radius: 4px; padding: 0 4px; overflow-wrap: anywhere; }
kbd { font: 600 0.85em ui-monospace, SFMono-Regular, Menlo, monospace; border: 1px solid var(--line); border-bottom-width: 2px;
  border-radius: 4px; padding: 0 5px; background: var(--soft); }
.wrap { max-width: 1040px; margin: 0 auto; padding: 0 16px; }
nav.top { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 0; }
.brand { display: inline-flex; align-items: center; gap: 8px; font-weight: 650; color: var(--fg); text-decoration: none; }
.brand .logo { width: 24px; height: 24px; }
.links { display: flex; gap: 16px; align-items: center; font-size: 15px; }
.links a { color: var(--muted); text-decoration: none; }
.links a:hover, .links a[aria-current] { color: var(--fg); }
.links a.gh { display: inline-flex; color: var(--fg); }
.crumbs { font-size: 14px; color: var(--muted); margin: 10px 0 0; }
.crumbs a { color: var(--muted); }
article { max-width: 760px; }
article.wide { max-width: none; }
article.wide > :is(p, ul, ol, h2, h3, .lead, .ctas, .callout) { max-width: 760px; }
h1 { font-size: clamp(30px, 5vw, 44px); line-height: 1.15; letter-spacing: -0.02em; margin: 18px 0 12px; text-wrap: balance; }
h2 { font-size: clamp(22px, 3vw, 28px); letter-spacing: -0.01em; margin: 44px 0 10px; }
h3 { font-size: 18px; margin: 28px 0 6px; }
.lead { font-size: clamp(17px, 2.2vw, 19px); color: var(--muted); margin: 0 0 20px; }
.ctas { display: flex; gap: 12px; flex-wrap: wrap; margin: 18px 0 8px; }
.btn { display: inline-flex; align-items: center; gap: 8px; padding: 10px 18px; border-radius: 8px; font-weight: 600;
  text-decoration: none; border: 1px solid var(--line); color: var(--fg); background: var(--bg); }
.btn.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-fg); }
.btn:hover { filter: brightness(1.05); }
.muted { color: var(--muted); }
.small { font-size: 14px; }
ul.plain { padding-left: 20px; }
ul.plain li { margin: 4px 0; }
.callout { background: var(--soft); border: 1px solid var(--line); border-left: 4px solid var(--accent); border-radius: 8px;
  padding: 12px 16px; margin: 18px 0; }
.callout p { margin: 6px 0; }
blockquote { margin: 14px 0; padding-left: 12px; border-left: 3px solid var(--line); color: var(--quote); }
blockquote p { margin: 0; font-style: italic; }
blockquote cite { display: block; color: var(--muted); font-size: 13px; font-style: normal; margin-top: 4px; }
table.facts { border-collapse: collapse; width: 100%; max-width: 760px; font-size: 15px; margin: 12px 0; }
table.facts th, table.facts td { text-align: left; border-bottom: 1px solid var(--line); padding: 6px 8px 6px 0; vertical-align: top; }
table.facts th { color: var(--muted); font-weight: 600; font-size: 13px; }
.figs { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin: 16px 0; max-width: 760px; }
figure { margin: 0; }
figure .art { background: var(--soft); border: 1px solid var(--line); border-radius: 10px; padding: 12px; }
figure svg { display: block; width: 100%; height: auto; }
figcaption { color: var(--muted); font-size: 14px; margin-top: 6px; }
.cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin: 22px 0; }
.card { display: block; border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px; text-decoration: none; color: var(--fg); }
.card:hover { border-color: var(--accent); }
.card b { display: block; font-size: 17px; margin-bottom: 4px; }
.card span { color: var(--muted); font-size: 15px; }
.card.feature { grid-column: 1 / -1; border-left: 4px solid var(--accent); }
.related { border-top: 1px solid var(--line); margin-top: 48px; padding-top: 12px; }
.related ul { padding-left: 20px; }
footer { border-top: 1px solid var(--line); margin-top: 56px; padding: 24px 0 48px; color: var(--muted); font-size: 14px; }
footer p { margin: 6px 0; max-width: 760px; }
@media (max-width: 720px) {
  .cards { grid-template-columns: minmax(0, 1fr); }
  .links .hide-sm { display: none; }
}
"""

LP_CSS = """
.v { display: inline-block; font-size: 13px; font-weight: 700; border-radius: 99px; padding: 1px 10px; white-space: nowrap; }
.v-safe { color: var(--safe); background: var(--safe-bg); border: 1px solid color-mix(in srgb, var(--safe) 35%, transparent); }
.v-marginal { color: var(--marginal); background: var(--marginal-bg); border: 1px solid color-mix(in srgb, var(--marginal) 35%, transparent); }
.v-unsafe { color: var(--unsafe); background: var(--unsafe-bg); border: 1px solid color-mix(in srgb, var(--unsafe) 35%, transparent); }
.answer { list-style: none; padding: 0; margin: 12px 0; max-width: 760px; }
.answer li { display: flex; gap: 10px; align-items: baseline; margin: 8px 0; }
.answer li .v { flex: none; }
.overview { margin: 18px 0 8px; }
.overview .art { background: #8a9099; border: 0; }
.overview svg text { font: 600 3.4px ui-sans-serif, system-ui, sans-serif; fill: #ffffff; }
.group { margin-top: 36px; }
.group > p { max-width: 760px; margin: 0 0 8px; }
.mk { display: grid; grid-template-columns: 96px minmax(0, 1fr) auto; gap: 4px 16px; align-items: start;
  border-top: 1px solid var(--line); padding: 14px 0; }
.mk .thumb { grid-row: span 2; background: #8a9099; border-radius: 8px; padding: 6px; }
.mk .thumb svg { display: block; width: 100%; height: auto; }
.mk h3 { margin: 0; font-size: 16px; }
.mk h3 .key { color: var(--muted); font-weight: 700; margin-right: 6px; }
.mk .ids { color: var(--muted); font-weight: 400; font-size: 14px; margin-left: 6px; }
.mk .facts { grid-column: 2 / 4; font-size: 14.5px; }
.mk .facts p { margin: 3px 0; }
.mk .facts .lbl { color: var(--muted); font-weight: 600; margin-right: 6px; }
.mk .rule { color: var(--quote); }
.views { display: flex; flex-wrap: wrap; gap: 12px; margin: 8px 0 2px; }
.views figure { flex: 1 1 140px; max-width: 220px; }
.views img { border-radius: 6px; border: 1px solid var(--line); width: 100%; image-rendering: pixelated; }
.map { display: inline-block; margin: 6px 0 0; }
.map svg { width: 220px; max-width: 100%; height: auto; display: block; }
.map text { font: 9px ui-sans-serif, system-ui, sans-serif; fill: var(--muted); }
@media (max-width: 720px) {
  .mk { grid-template-columns: 72px minmax(0, 1fr); }
  .mk .verdict { grid-column: 2; grid-row: 2; }
  .mk .thumb { grid-row: span 2; }
  .mk .facts { grid-column: 1 / -1; }
}
"""


def gh_mark(px: int = 22) -> str:
    return (f'<svg viewBox="0 0 16 16" width="{px}" height="{px}" aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 '
            '3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 '
            '1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 '
            '.67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 '
            '3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>')


def shell(*, title: str, description: str, path: str, crumbs: list, body: str, css: str = "") -> str:
    """One guide page: the landing's look (docs/build_landing.py: its tokens, nav and footer, kept in
    step by hand), a breadcrumb, the article, Related, and the footer's provenance line."""
    icon = ICON.read_text().strip().replace("<svg ", '<svg class="logo" aria-hidden="true" ', 1)
    trail = " / ".join([f'<a href="{href}">{esc(name)}</a>' if href else esc(name) for name, href in crumbs])
    full = f"{title} · ArUco Studio guides" if path != "/guides/" else "Guides · ArUco Studio"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!-- Generated by docs/build_guides.py: edit the builder, not this file. -->
<title>{esc(full)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{SITE}{path}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta name="color-scheme" content="light dark">
<meta property="og:type" content="article">
<meta property="og:site_name" content="ArUco Studio">
<meta property="og:url" content="{SITE}{path}">
<meta property="og:title" content="{esc(full)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:image" content="{SITE}/og.png">
<meta name="twitter:card" content="summary_large_image">
<style>{CSS}{css}</style>
</head>
<body>
<div class="wrap">
<nav class="top" aria-label="Site">
  <a class="brand" href="/about/">{icon}<span>ArUco Studio</span></a>
  <span class="links"><a href="/guides/"{' aria-current="page"' if path == "/guides/" else ""}>Guides</a><a class="hide-sm" href="/about/">About</a><a href="/">Try Online</a><a class="gh" href="{GITHUB}" aria-label="GitHub" title="GitHub">{gh_mark()}</a></span>
</nav>
<p class="crumbs">{trail}</p>
<main>
{body}
</main>
<footer>
  <p>Every number on these pages is computed by ArUco Studio's own core, the same Python that runs in the Studio:
  <a href="{SRC}/docs/build_guides.py">docs/build_guides.py</a> runs it and writes the pages.</p>
  <p>ArUco Studio by Zach Yamaoka. Source on <a href="{GITHUB}">GitHub</a>; no licence chosen yet.
  <a href="/privacy/">Privacy Policy</a> &middot; <a href="/terms/">Terms of Use</a></p>
</footer>
</div>
</body>
</html>
"""


def quote(text: str, who: str) -> str:
    return f"<blockquote><p>“{esc(text)}”</p><cite>{esc(who)}</cite></blockquote>"


def related(current: str) -> str:
    items = "".join(f'<li><a href="/guides/{g.slug}/">{esc(g.title)}</a></li>' for g in GUIDE_LIST if g.slug != current)
    return f'<nav class="related" aria-label="Related guides"><h2 class="small muted">More guides</h2><ul>{items}</ul></nav>'


def svg_inner(svg: str):
    """(viewBox numbers, the inner markup) of the core's SVG (web_api.svg), its <title> dropped."""
    m = re.match(r'<svg [^>]*viewBox="([^"]+)"[^>]*>(.*)</svg>$', svg, re.S)
    assert m, svg[:120]
    vb = [float(v) for v in m.group(1).split()]
    return vb, re.sub(r"<title>.*?</title>", "", m.group(2), flags=re.S)


def sticker_svg(req: dict, label: str, cls: str = "") -> str:
    vb, inner = svg_inner(W.svg(req))
    return (f'<svg viewBox="{" ".join(sv(v, 4) for v in vb)}" role="img" aria-label="{esc(label)}"'
            f'{f" class={chr(34)}{cls}{chr(34)}" if cls else ""}>{inner}</svg>')


# ------------------------------------------------------------------ the label placement page

def verdict_badge(v: str) -> str:
    return f'<span class="v v-{v}">{ {"safe": "Safe", "marginal": "Marginal", "unsafe": "Not safe"}[v] }</span>'


def ids_text(ids: list) -> str:
    return f"#{ids[0]}" if len(ids) == 1 else f"#{ids[0]}–{ids[-1]}"


def where_text(c: Case, r: dict) -> str:
    lab = c.req["label"]
    w = r["where"]
    if not lab.get("on"):
        return "No label."
    bits = []
    place = "Outside" if lab.get("place") == "outside" else "On marker"
    surface = "" if lab.get("place") == "outside" else (", Surface " + ("White" if lab.get("surface") == "white" else "Black"))
    bits.append(f"{place}{surface}, side {lab.get('side', 'below').capitalize()}")
    if lab.get("place") == "outside":
        bits.append(f"Gap {num(float(lab['gap_mm']))} mm")
    if w["cap_cells"] is not None:
        bits.append(f"letters {num(r['plan']['label_cap_mm'])} mm tall ({num(w['cap_cells'])} cell)")
    if w["from_black_cells"] is not None:
        fb = w["from_black_cells"]
        bits.append("touching the black" if fb < 0.005 else f"{num(fb)} cell from the black")
    off = lab.get("offset_mm") or [0, 0]
    if any(abs(float(v)) > 1e-9 for v in off):
        bits.append(f"moved {num(float(off[0]))}, {num(float(off[1]))} mm")
    return " · ".join(bits) + "."


def map_svg(m: list, grid: dict) -> str:
    """The marks check's grid as a small table: rows px per cell (nearest at the top), columns blur; each
    cell the views read with the marks of those the bare marker read (red where the marks lost some)."""
    ppcs, blurs = grid["px_per_cell"], grid["blur_px"]
    cw, ch, lx, ty = 32, 15, 46, 14
    W_, H_ = lx + cw * len(blurs), ty + ch * len(ppcs) + 14
    out = [f'<svg viewBox="0 0 {W_} {H_}" role="img" aria-label="Reads with the label of the bare reads, by camera resolution and blur">']
    for j, b in enumerate(blurs):
        out.append(f'<text x="{lx + j * cw + cw / 2}" y="10" text-anchor="middle">{sv(b, 1)}</text>')
    out.append(f'<text x="{lx + cw * len(blurs) / 2}" y="{H_ - 2}" text-anchor="middle">blur, px</text>')
    for i, p in reversed(list(enumerate(ppcs))):
        y = ty + (len(ppcs) - 1 - i) * ch
        out.append(f'<text x="{lx - 4}" y="{y + 11}" text-anchor="end">{sv(p, 0)} px/cell</text>')
        for j in range(len(blurs)):
            marked, bare, n = m[i][j]
            lost = bare - marked
            fill = ("var(--unsafe)" if lost > 0 else "var(--safe)" if bare else "var(--line)")
            op = (0.25 + 0.75 * min(1.0, lost / max(1, bare))) if lost > 0 else (0.18 if bare else 0.6)
            out.append(f'<rect x="{lx + j * cw + 1}" y="{y + 1}" width="{cw - 2}" height="{ch - 2}" rx="2" fill="{fill}" '
                       f'fill-opacity="{op:.2f}"><title>{sv(p, 0)} px per cell, blur {sv(b, 1)} px: {marked} of the '
                       f'{bare} bare reads ({n} views)</title></rect>')
            if lost > 0:
                out.append(f'<text x="{lx + j * cw + cw / 2}" y="{y + 11}" text-anchor="middle" style="fill:var(--fg)">−{lost}</text>')
    out.append("</svg>")
    return "".join(out)


def det_name(opencv: str) -> str:
    """ "OpenCV 5.0" """
    return f"OpenCV {OC.short(opencv)}"


def verify_text(v: dict) -> str:
    """One detector's result for one marker, in words: the paired check, then what the dialog shows."""
    mk = v["marks"]
    sweep = v["sweep_reads_to_deg"]["marked"]
    dialog = ("The dialog's angle sweep: not even head on." if sweep is None
              else f"The dialog's angle sweep: to {sweep}°.")
    if not mk["label"] and not mk["corner_mark"]:
        got = (f"Reads in {mk['reads']['bare']} of the {mk['views']} views" if mk["ids"] == 1 else
               f"Reads {mk['reads']['bare']} of its {mk['ids']} ids × {mk['views']} views")
        return f"{got}: the baseline (the views run from easy to past reading). {dialog}"
    lost, gained, bare = mk["lost"], mk["gained"], mk["reads"]["bare"]
    s = f"Lost {'none' if lost == 0 else lost} of the bare marker's {bare} reads"
    if gained:
        s += f", gained {gained}"
    if lost - gained > 0:
        s += f" ({num(mk['cost_pts'], 1)} %)"
    if mk["easy"]["lost"]:
        s += f"; {mk['easy']['lost']} of them in sharp, well-resolved views"
    s += "."
    po = mk["pose"]
    if po["verdict"] != "safe":
        s += (f" Where the bare pose is sharp ({po['views']} views) the pose came out worse in {po['worse']} and "
              f"better in {po['better']}: {num(po['marked_mm'], 3)} mm mean error against {num(po['bare_mm'], 3)} mm bare.")
    return f"{s} {dialog}"


def group_cards(cases: list, results: dict, grid: dict) -> str:
    by = {r["key"]: r for r in results["cases"]}
    o = results["opencv"]
    per = len(grid["tilt_deg"]) * int(grid["seeds"])
    out = []
    for gid, (gtitle, gnote) in GROUPS.items():
        out.append(f'<section class="group" id="{gid}"><h3>{esc(gtitle)}</h3><p class="muted small">{esc(gnote)}</p>')
        for c in (c for c in cases if c.group == gid):
            r = by[c.key]
            rules = ("; ".join(esc(h) for h in r["rules"]["hits"]) + "." if r["rules"]["hits"]
                     else "No rule broken.")
            v = r["verify"]
            lines = (f'<p data-opencv="{esc(o)}"><span class="lbl">Verify · {esc(det_name(o))}</span>'
                     f'{esc(verify_text(v))} {verdict_badge(v["marks"]["verdict"])}</p>')
            extra = ""
            if v["pictures"]:
                pv = v["pictures"]["view"]
                figs = "".join(
                    f'<figure><img src="media/{im["file"]}" alt="{esc(c.key)} {im["kind"]} at {num(pv["px_per_cell"], 1)} px per cell" '
                    f'width="300"><figcaption>{"Bare" if im["kind"] == "bare" else "With the label"}: '
                    f'{"misses " + ", ".join(f"#{i}" for i in im["missing"]) if im["missing"] else "reads"}</figcaption></figure>'
                    for im in v["pictures"]["images"])
                extra += (f'<p class="small muted">A view it lost with {esc(det_name(o))}: '
                          f'{num(pv["px_per_cell"], 1)} px per cell, blur {num(pv["blur_px"], 1)} px, tilt '
                          f'{num(pv["tilt_deg"], 0)}°. Green: read; red: printed, not read.</p><div class="views">{figs}</div>'
                          f'<div class="map">{map_svg(v["marks"]["map"], grid)}</div><p class="small muted">Where it lost '
                          f'them: red cells, by px per cell (rows) and blur (columns), {per} views each.</p>')
            out.append(
                f'<div class="mk" id="{c.key.lower()}" data-key="{c.key}" data-verdict="{r["verdict"]}">'
                f'<div class="thumb">{thumb(c.key)}</div>'
                f'<h3><span class="key">{c.key}</span>{esc(c.title)}<span class="ids">{ids_text(r["plan"]["ids"])} · '
                f'ArUco Extrude {r["number"]}</span></h3>'
                f'<div class="verdict">{verdict_badge(r["verdict"])}</div>'
                f'<div class="facts"><p><span class="lbl">Where</span>{esc(where_text(c, r))}</p>'
                f'<p class="rule"><span class="lbl">The Studio\'s rules</span>{rules} {verdict_badge(r["rules"]["verdict"])}</p>'
                f'{lines}{extra}</div></div>')
        out.append("</section>")
    return "".join(out)


VIEWBOX: dict = {}


def symbols(cases: list) -> str:
    """Each marker drawn once, by the core (web_api.svg: the sticker as cut, with its label), as a
    <symbol> the overview and the rows both <use>."""
    out = ['<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>']
    for c in cases:
        vb, inner = svg_inner(W.svg(c.req))
        VIEWBOX[c.key] = " ".join(sv(v, 4) for v in vb)
        out.append(f'<symbol id="mk-{c.key}" viewBox="{VIEWBOX[c.key]}">{inner}</symbol>')
    out.append("</defs></svg>")
    return "".join(out)


def thumb(key: str) -> str:
    """One marker's symbol at its own aspect (a <use> of a <symbol> fills the x, y, width and height it is
    given: without them it is placed at 0, 0 at 100 % and shows a corner)."""
    w, h = (float(v) for v in VIEWBOX[key].split()[2:])
    return (f'<svg viewBox="0 0 {sv(w)} {sv(h)}" role="img" aria-label="Marker {key}">'
            f'<use href="#mk-{key}" x="0" y="0" width="{sv(w)}" height="{sv(h)}"/></svg>')


def overview(cases: list) -> str:
    """The board as the Studio's canvas lays it out, each sticker where its rectangle is, its key above."""
    items, xs, ys = [], [], []
    for c in cases:
        vb = [float(v) for v in VIEWBOX[c.key].split()]
        x, y = c.rect["cx"] + vb[0], -(c.rect["cy"]) + vb[1]
        items.append(f'<use href="#mk-{c.key}" x="{sv(x, 4)}" y="{sv(y, 4)}" width="{sv(vb[2], 4)}" height="{sv(vb[3], 4)}"/>'
                     f'<text x="{sv(x + 0.4, 3)}" y="{sv(y - 1.2, 3)}">{c.key}</text>')
        xs += [x, x + vb[2]]
        ys += [y - 5.0, y + vb[3]]
    pad = 3.0
    x0, y0, x1, y1 = min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad
    return (f'<figure class="overview"><div class="art"><svg viewBox="{sv(x0, 3)} {sv(y0, 3)} {sv(x1 - x0, 3)} {sv(y1 - y0, 3)}" '
            f'role="img" aria-label="The label placement test board">{"".join(items)}</svg></div>'
            f'<figcaption>The board as it opens in the Studio: 28 markers, each on its own rectangle, drawn here by the '
            f'Studio\'s core. The letters are the guide\'s names for them.</figcaption></figure>')


def link(k: str) -> str:
    return f'<a href="#{k.lower()}">{k}</a>'


def links(keys: list) -> str:
    """ "B5, B6 and D4" """
    out = [link(k) for k in keys]
    return "none" if not out else out[0] if len(out) == 1 else ", ".join(out[:-1]) + " and " + out[-1]


def label_page(cases: list, results: dict) -> str:
    syms = symbols(cases)                  # first: it fills VIEWBOX, which the overview and the rows read
    rs = results["cases"]
    grid = results["grid"]
    th = results["thresholds"]
    studio = results["studio_opencv"]
    o = results["opencv"]
    det = results["detector"]
    n_views = rs[0]["verify"]["marks"]["views"]
    answer = "".join(
        f'<li>{verdict_badge("safe" if ok == {"safe"} else "unsafe")}<span>{esc(text[text.index(":") + 2:])} '
        f'<span class="muted small">({links(keys)})</span></span></li>'
        for text, keys, ok in HEADLINES)
    flagged = [r["key"] for r in rs if r["verdict"] != "safe"]
    # what the dialog shows: its sweep failing head on, reading less far than bare, or like bare
    sw = {r["key"]: r["verify"]["sweep_reads_to_deg"] for r in rs}
    none = [k for k, v in sw.items() if v["marked"] is None and v["bare"] is not None]
    short = [k for k, v in sw.items() if v["marked"] is not None and v["bare"] is not None and v["marked"] < v["bare"]]
    like = [k for k in flagged if sw[k]["marked"] == sw[k]["bare"]]
    bits = []
    if none:
        bits.append(f"{links(none)} not reading even head on")
    if short:
        bits.append(" and ".join(f"{link(k)} reading only to {sw[k]['marked']}° (its bare marker to {sw[k]['bare']}°)"
                                 for k in short))
    shows = ("shows " + "; ".join(bits) + ". The other " if bits else "shows nothing: ")
    dialog = (f"Its sweep {shows}{len(like)} of the {len(flagged)} markers this page calls not safe or marginal sweep "
              f"exactly like their bare marker ({links(like)}).")
    any_found = [r["key"] for r in rs if r["verify"]["marks"]["verdict"] != "safe"]
    rules_say = [r["key"] for r in rs if r["rules"]["verdict"] != "safe"]
    only_rules = [k for k in rules_say if k not in any_found]
    run = f"OpenCV {esc(o)} (Python {esc(det['python'])}, numpy {esc(det['numpy'])}, {det['seconds']} s)"
    old_a, old_b = OLD_FINDING["versions"]
    others = (f'Other versions of OpenCV can read these markers differently near the limits: on this board OpenCV {old_a} '
              f'and {old_b} disagreed on {len(OLD_FINDING["disagree"])} of the {len(cases)} '
              f'({", ".join(OLD_FINDING["disagree"])}; <a href="{OLD_FINDING["url"]}">the run with both</a>, '
              f'which kept the worse).')
    # one OpenCV a run: the newest installed unless the build was told another (docs/peps/0003)
    which = (", the newest" if same_opencv(o, det.get("newest") or o)
             else f", as asked (the newest here was {esc(det_name(det['newest']))})")
    others_here = [v for v in browser_opencvs() if not same_opencv(v, studio)]
    offers = (f" (its OpenCV choice also offers {' and '.join(esc(OC.short(v)) for v in others_here)})" if others_here else "")
    if not studio:
        studio_note = ""
    elif same_opencv(o, studio):
        studio_note = f"The Studio's Verify runs this same OpenCV in your browser by default{offers}."
    else:
        studio_note = f"The Studio's Verify in your browser runs OpenCV {esc(OC.short(studio))} by default{offers}."
    body = f"""<article class="wide">
<h1>Where to put a label, and a corner mark</h1>
<p class="lead">Keep it short, in the black border row at the Studio's own size, or put it outside the white quiet
zone. Never in the quiet zone itself, and not near a ChArUco corner. Every verdict below is the Studio's own output on a
test board you can open.</p>
<div class="ctas"><a class="btn primary" href="{OPEN_BOARD}" data-cta="open-board">Open the board in the Studio</a>
<a class="btn" href="{BOARD_URL}" download>Download the board file</a></div>

<h2>The short answer</h2>
<ul class="answer">{answer}</ul>
<p class="small muted">Each line is checked against the run when this page is built: the build stops if a marker it names
gets another verdict.</p>

<h2>The board</h2>
<p>{len(cases)} markers, inkjet stickers on the Letter vinyl preset. Each varies one thing from the bare marker
{link("A1")}: where the label goes, how big it is, or the corner mark. The singles are DICT_4X4_50 markers, 22 mm on a
30 mm square; the ChArUco boards use DICT_4X4_100, so no two markers on the board print the same id. In the Studio each
is an ArUco Extrude, numbered in this order.</p>
{overview(cases)}

<h2>Every marker, and what the Studio says</h2>
<p>Each marker gets two verdicts. <b>The Studio's rules</b> are the warnings it shows in the ArUco Extrude
panel; they come from earlier, much larger studies (below). <b>Verify</b> is the Studio's simulated camera and OpenCV's
own detector, reading the marker {n_views} times with its label and {n_views} times without, here with
<b data-opencv="{esc(o)}">{esc(det_name(o))}</b>{which}. {studio_note}
{others} The verdict is the worse of the two.</p>
{group_cards(cases, results, grid)}

<h2>How Verify measured it</h2>
<p>The same marker, read twice through the same {n_views} views: as planned, and bare, with its label and corner mark
taken away. Both views share the camera, the crop, the blur and the grain, pixel for pixel, so a read the bare marker gets
and the labelled one does not is the label's doing. A read is one marker id in one view, so a grid or a ChArUco board
counts each of its markers. The views cover {num(grid["px_per_cell"][0], 0)} to {num(grid["px_per_cell"][-1], 0)} px per
cell on the sensor (from the edge of reading to Verify's bench), {num(grid["blur_px"][0], 1)} to
{num(grid["blur_px"][-1], 1)} px of blur, head on and tilted {num(grid["tilt_deg"][-1], 0)}°, grain
{num(grid["noise"], 2)}, {grid["seeds"]} seeds each.</p>
<ul class="plain">
<li><b>Safe</b>: it loses under {num(th["marginal_pts"], 0)} % of the bare marker's reads, or a sign test cannot
tell the loss from chance (p ≥ {num(th["p_max"], 2)}).</li>
<li><b>Marginal</b>: a real loss under {num(th["unsafe_pts"], 0)} %, or, where the bare pose is sharp, a mean pose
error {num(th["pose_marginal"] * 100, 0)} % or more worse.</li>
<li><b>Not safe</b>: a loss of {num(th["unsafe_pts"], 0)} % or more; or {num(th["easy_share"] * 100, 0)} % or more of
the reads in the easy views ({num(th["easy_px_per_cell"], 0)} px per cell or more, {num(th["easy_blur_px"], 0)} px of
blur or less, where a bare marker never fails), {th["easy_min"]} at least; or the pose
{num(th["pose_unsafe"] * 100, 0)} % worse.</li>
</ul>
<div class="callout"><p><b>Why not just Verify's dialog?</b> It shows one view at a time, a clean angle sweep and a
head-on read limit. {dialog} The dialog catches the worst places; the paired check measures the rest. It is
<a href="{SRC}/aruco_studio/web_marks.py">aruco_studio/web_marks.py</a>, version {results["verify_version"]}.</p></div>

<h2>What Verify cannot judge yet</h2>
<p>Verify found a cost for {len(any_found)} of these markers ({links(any_found)}); the rules flag {len(rules_say)}.
Where only the rules flag a marker ({links(only_rules)}), Verify saw no cost. Two things the
studies behind those rules measured, Verify does not draw, and one more it leaves out:</p>
<ul class="plain">
<li><b>Ink spread.</b> A printer's dots grow into the white round them, so ink in the quiet zone creeps toward the
marker's black; the studies measured up to −40 points once it did. Verify draws ink at its exact size.</li>
<li><b>Grey ink.</b> The studies' −11 points in the quiet ring were grey ids; Verify draws the label black, in
OpenCV's thin Hershey font stretched to the print's Helvetica widths.</li>
<li><b>What is round the sticker.</b> Verify draws white past the sticker's edge. On a dark part the quiet zone is all
the white there is, and black letters in it can join the black border to the dark background.</li>
</ul>
<p>So treat Verify's “no loss” in the quiet zone as no evidence it is safe on paper; the rule stays. The test Verify
cannot do is yours: Print the board, stick it where your markers will go, and read it with your camera.</p>

<h2>Where the rules come from</h2>
<p>The rules came out of the studies behind the ArUco Extrude add-in, in October 2026: 430,260 simulated photos for the
label, 298,000 for the corner mark, on OpenCV's detector. Their numbers are kept in the core, next to the rules they set:
<a href="{SRC}/aruco_studio/core/label.py">core/label.py</a> and <a href="{SRC}/aruco_studio/core/chamfer.py">core/chamfer.py</a>.</p>
<ul class="plain">
<li>White letters knocked out of the black border row cost nothing (−0.3 points, not significant) while they are at most
half a cell tall, keep a quarter cell of black above and below, and stay out of the corner cells.</li>
<li>Any ink in the 1-cell quiet ring costs: −11 points for a grey id, up to −40 once a printer's dots spread.</li>
<li>Black text on the white: 0.5 cell from the black cost −7.3 points, 0.7 cell −1.5 points, a whole cell or
more: nothing (3,000 paired trials). That is the quiet ring's own edge, so the quiet ring is the rule.</li>
<li>A ChArUco board's label fits in a black square for free; a bright mark nearer than 0.3 of a square to an inner
chessboard corner pulls that corner.</li>
<li>Corner marks: a black triangle in the quiet zone's corner, the white tile's corner cut, and a ChArUco board's
top-left black square's outer corner cut cost nothing. Cutting the marker's own black corner is never done: corner 0
slides along the cut.</li>
</ul>

<h2>Check it yourself</h2>
<ol>
<li><a href="{OPEN_BOARD}">Open the board in the Studio</a>.</li>
<li>Click a marker, then Verify (<kbd>K</kbd>). Drag Tilt and Blur; pick another marker from the list.</li>
<li>Click a marker to open its ArUco Extrude panel: the Label tab shows the rule warnings this page quotes.</li>
<li>Print it from the Studio (Print, at 100 %), stick it where your markers will go, and read it with your camera.</li>
</ol>
<p class="small muted">Built {esc(results["generated"])} from core {esc(results["core_version"])}
{f'(commit {esc(results["commit"])})' if results.get("commit") else ""}, with {run}.
The raw run: <a href="verify.json">verify.json</a>.</p>
{related("label-placement")}
</article>"""
    return shell(title="Where to put a label, and a corner mark",
                 description=("Which label placements and corner marks an ArUco marker's detector tolerates, measured by "
                              "ArUco Studio's Verify on a test board you can open and check yourself."),
                 path="/guides/label-placement/",
                 crumbs=[("Home", "/about/"), ("Guides", "/guides/"), ("Label placement", None)],
                 body=syms + body, css=LP_CSS)


# ------------------------------------------------------------------ the decision pages (computed each build)

def req_rect(w: float, h: float, marker=None, label=None, preset=None, extra=None) -> dict:
    loop = rect_corners({"cx": 0.0, "cy": 0.0, "w": w, "h": h, "angle_deg": 0})
    r = {"trim": "profile", "profile": {"loops": [loop]}, "holes": "avoid", "marker": dict(MARKER0, **(marker or {})),
         "label": dict(LABEL0, **(label or {})), "preset": preset or INK, "reference_face": False, "extrude": {}}
    r.update(extra or {})
    return r


def circle_loop(cx: float, cy: float, r: float, n: int = 96) -> list:
    """web/src/model/geom.ts circleLoop: n points, counter-clockwise from angle 0."""
    return [[cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)] for i in range(n)]


def plate_profile() -> dict:
    """The Plate example (web/src/sketch/examples.ts): 120 x 80 mm, two 20 mm holes."""
    outer = rect_corners({"cx": 60.0, "cy": 40.0, "w": 120.0, "h": 80.0, "angle_deg": 0})
    holes = [list(reversed(circle_loop(25.0, 55.0, 10.0))), list(reversed(circle_loop(95.0, 25.0, 10.0)))]
    return {"loops": [outer] + holes}


def figure(svg: str, caption: str) -> str:
    return f'<figure><div class="art">{svg}</div><figcaption>{caption}</figcaption></figure>'


def info_text(plan: dict, field_: str, pattern: str) -> str:
    for w in plan.get("warnings", []):
        if w["field"] == field_ and re.search(pattern, w["text"]):
            return w["text"]
    raise SystemExit(f"no {field_} note matching {pattern!r}: {[w['text'] for w in plan.get('warnings', [])]}")


def page_profile_first() -> str:
    prof = plate_profile()
    avoid = W.inscribe(prof, "avoid")
    ignore = W.inscribe(prof, "ignore")
    auto_req = {"trim": "profile", "profile": prof, "holes": "avoid", "marker": dict(MARKER0), "label": dict(LABEL0),
                "preset": INK, "reference_face": True, "extrude": {}}
    custom = rect_corners({"cx": 70.0, "cy": 57.0, "w": 30.0, "h": 30.0, "angle_deg": 0})
    custom_req = dict(auto_req, profile={"loops": [custom]}, reference_face=False)
    a_plan, c_plan = W.plan(auto_req), W.plan(custom_req)
    body = f"""<article>
<h1>Profile first</h1>
<p class="lead">You never draw the marker. You pick a profile, as you would for an extrude, and the Studio places the
marker in it.</p>
<h2>The rule</h2>
<ul class="plain">
<li><b>Click inside a closed shape</b> and press <kbd>A</kbd> (ArUco Extrude): the marker goes in the largest clear box
that fits in that profile. Its holes are avoided, or, with Holes: Ignore, treated as if they were not there.</li>
<li><b>Want it somewhere exact?</b> Draw a rectangle where it should go and double-click it: the rectangle alone is
the profile, and it is used exactly, angle and all.</li>
<li>The automatic box's edges snap inward to a 0.1 mm grid; a rectangle profile is never snapped.</li>
</ul>
<h2>On the Plate example</h2>
<p>The Plate is 120 × 80 mm with two Ø20 holes. Click its face and the core fits a
{num(avoid["w"], 1)} × {num(avoid["h"], 1)} mm box between the holes, centred at ({num(avoid["cx"], 1)},
{num(avoid["cy"], 1)}): a {num(a_plan["marker_mm"], 1)} mm marker. With Holes: Ignore the box is the whole
{num(ignore["w"], 0)} × {num(ignore["h"], 0)} mm face. A 30 mm square drawn at the top right is used as drawn:
a {num(c_plan["marker_mm"], 1)} mm marker, its sticker the square.</p>
<div class="figs">
{figure(sticker_svg(auto_req, "The Plate's face as the profile: the marker in the clear box between the holes"),
        f"Click the face: the box between the holes, {num(avoid['w'], 1)} × {num(avoid['h'], 1)} mm.")}
{figure(sticker_svg(custom_req, "A 30 mm square drawn on the plate, used as the profile"),
        "Draw a 30 mm square: the marker fills it exactly.")}
</div>
<h2>Why</h2>
<p>A marker belongs to a place on a part. Choosing the place by its profile is how every other CAD feature works, so
there is one happy path for the common case and one for the exact case, and nothing else to learn.</p>
{quote("I prefer Unix tool philosophy, just like simple things. With kind of known happy paths and I do like it behaving a bit more like an extrude", "Zach, 2026-10-20")}
<p class="small muted">In the code: <a href="{SRC}/aruco_studio/web_api.py">web_api.inscribe and fit_box</a>; the
contract's PlanRequest takes a profile, never a marker rectangle.</p>
{related("profile-first")}
</article>"""
    return shell(title="Profile first", path="/guides/profile-first/",
                 description="How ArUco Studio places a marker: pick a profile like an extrude; a rectangle profile places it exactly.",
                 crumbs=[("Home", "/about/"), ("Guides", "/guides/"), ("Profile first", None)], body=body)


def page_size_step() -> str:
    base = req_rect(30.0, 30.0)
    step05 = W.plan(base)
    dots = W.plan(dict(base, marker=dict(MARKER0, size_step={"of": "dots"})))
    tenth = W.plan(dict(base, marker=dict(MARKER0, size_step={"of": "mm", "mm": 0.1})))
    typed = W.plan(req_rect(30.0, 30.0, marker={"auto": False, "marker_mm": 21.37}))
    big = W.plan(req_rect(30.0, 30.0, marker={"auto": False, "marker_mm": 25.0}))
    dots_note = info_text(dots, "marker.marker_mm", r"dots at \d+ dpi")
    over = next(w["text"] for w in big.get("warnings", []) if w["level"] in ("warn", "error"))
    assert typed["marker_mm"] == 21.37 and big["marker_mm"] == 25.0 and big["overflow_mm"] > 0
    p3 = next(p for p in W.presets() if p["method"] == "print3d")
    line = 0.675
    lines = W.plan(req_rect(30.0, 30.0, preset=dict(p3, cell_step_mm=line, line_mm=line)))
    per_cell = lines["cell_mm"] / line
    assert abs(per_cell - round(per_cell)) < 1e-6, "a 3D profile's driven cell is whole lines"
    rows = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for a, b in (
        ("0.5 mm (the inkjet presets' default)", f"{num(step05['marker_mm'], 4)} mm"),
        ("0.1 mm", f"{num(tenth['marker_mm'], 4)} mm"),
        ("Whole printer dots (600 dpi)", f"{num(dots['marker_mm'], 4)} mm"),
        (f"A 3D printer profile, {num(line, 3)} mm lines", f"{num(lines['marker_mm'], 4)} mm: each cell "
                                                              f"{round(per_cell)} lines"),
    ))
    body = f"""<article>
<h1>Exact sizes, and the size step</h1>
<p class="lead">A size you type is the size you get. A size the Studio picks for you lands on a round step.</p>
<h2>The rule</h2>
<ul class="plain">
<li><b>Typed sizes are drawn as typed</b>, to the last digit, never rounded and never clamped. If one does not fit, it
is still drawn, and flagged.</li>
<li><b>Driven sizes</b> (the grey ones, filled in to fit the profile) round down to the marker's size step: 0.5 mm on
the inkjet presets, any step you set, or whole printer dots per cell, so every cell is exactly a whole number of dots. A
3D printer profile with a line width makes every cell a whole number of lines.</li>
<li>The step belongs to the preset, and a marker can override it.</li>
</ul>
<h2>In numbers</h2>
<p>A single 4 × 4 marker on a 30 mm square, its size driven:</p>
<table class="facts"><thead><tr><th>Size step</th><th>Marker</th></tr></thead><tbody>{rows}</tbody></table>
<p>The Marker row says how the size lands on the printer: “{esc(dots_note)}”</p>
<p>Type 21.37 mm on the same square and it is drawn at {num(typed['marker_mm'], 4)} mm: no step. Type 25 mm, which
with its quiet zone does not fit, and it is still drawn at {num(big['marker_mm'], 4)} mm, and the Studio says:
“{esc(over)}”</p>
<h2>Why</h2>
<p>Round numbers are easy to read, check with a ruler and type into CAD; exact numbers are what you asked for.</p>
{quote("we should by default recommend to the nearest like .5 mm", "Zach, 2026-10-20")}
{quote("we should always have complete control", "Zach, 2026-10-20")}
<p class="small muted">In the code: <a href="{SRC}/aruco_studio/core/autosize.py">core/autosize.py</a> (rules 2 and 3) and
web_api.cells_of; the contract's SizeStep.</p>
{related("size-step")}
</article>"""
    return shell(title="Exact sizes, and the size step", path="/guides/size-step/",
                 description="Typed marker sizes are exact; driven sizes round to 0.5 mm, a step you set, or whole printer dots.",
                 crumbs=[("Home", "/about/"), ("Guides", "/guides/"), ("Size step", None)], body=body)


def page_heights() -> str:
    d0 = CP.driven_heights(0, 0)
    d1 = CP.driven_heights(0.32, 0.2)
    p3 = next(p for p in W.presets() if p["method"] == "print3d")
    plan3 = W.plan(req_rect(30.0, 30.0, preset=p3))
    plan_ink = W.plan(req_rect(30.0, 30.0))
    ex3, exi = plan3["extrude"], plan_ink["extrude"]
    body = f"""<article>
<h1>Heights for 3D printing</h1>
<p class="lead">An inkjet sticker has one height, the paper. A 3D-printed marker has two: the white and the black, and the
black is measured from the white's outer face.</p>
<h2>The rule</h2>
<ul class="plain">
<li><b>Inkjet:</b> only the paper's thickness, filled in from the preset ({num(exi["paper_mm"], 2)} mm on the vinyl
presets).</li>
<li><b>3D print:</b> the white height and the black height. The black always starts at the white's outer face and goes
in: a white of W and a black of B put the black from W − B to W, flush with the face.</li>
<li><b>Driven heights</b> come from the preset's layers: whole layers printed face down, the first layer plus k layers,
the fewest that reach {num(CP.BLACK_PRINT_MM, 2)} mm of black and {num(CP.WHITE_PRINT_MM, 2)} mm of white. Without
layer heights, the old {num(d0["white_mm"], 1)} mm white and {num(d0["black_mm"], 1)} mm black.</li>
<li><b>Flip</b> is always there, on a face too: the face only picks which way the marker starts out.</li>
</ul>
<h2>In numbers</h2>
<table class="facts"><thead><tr><th>Preset</th><th>White</th><th>Black</th></tr></thead><tbody>
<tr><td>0.2 mm first layer, 0.32 mm layers</td><td>{num(d1["white_mm"], 2)} mm</td><td>{num(d1["black_mm"], 2)} mm, from
{num(d1["white_mm"] - d1["black_mm"], 2)} to {num(d1["white_mm"], 2)} mm</td></tr>
<tr><td>{esc(p3["name"])} (no layer heights)</td><td>{num(ex3["white_mm"], 2)} mm</td><td>{num(ex3["black_mm"], 2)} mm, from
{num(ex3["white_mm"] - ex3["black_mm"], 2)} to {num(ex3["white_mm"], 2)} mm</td></tr>
</tbody></table>
<h2>Why</h2>
<p>Measured from the white's face, the black's height means the same thing whatever the white is, and the face the
camera sees is always flat.</p>
{quote("for inkjet you just get to set paper thickness (but its autofilled from the preset); for 3D printer you get to set the white height and black height. black height is always measured from the outer face of the white", "Zach, 2026-10-20")}
<p class="small muted">In the code: <a href="{SRC}/aruco_studio/web_extrude.py">web_extrude.py</a> and
core.presets.driven_heights; the contract's ExtrudeParams.</p>
{related("heights")}
</article>"""
    return shell(title="Heights for 3D printing", path="/guides/heights/",
                 description="ArUco Studio's marker heights: paper thickness for inkjet; white and black heights for 3D print, the black from the white's face.",
                 crumbs=[("Home", "/about/"), ("Guides", "/guides/"), ("Heights", None)], body=body)


def page_trim() -> str:
    disc = {"loops": [circle_loop(0.0, 0.0, 45.0)] + [list(reversed(circle_loop(30 * math.cos(math.radians(a)),
                                                                                30 * math.sin(math.radians(a)), 5.0)))
                                                       for a in (90, 210, 330)]}
    prof = {"trim": "profile", "profile": disc, "holes": "avoid", "marker": dict(MARKER0), "label": dict(LABEL0),
            "preset": INK, "reference_face": True, "extrude": {}}
    mark = dict(prof, trim="marker")
    p_plan, m_plan = W.plan(prof), W.plan(mark)
    outside = W.plan(req_rect(40.0, 50.0, label=dict(OUTSIDE), extra={"trim": "marker"}))
    drop = next((w["text"] for w in outside.get("warnings", []) if w["field"] == "label.on"), "")
    xs = [p[0] for p in m_plan["cut"]]
    body = f"""<article>
<h1>Trim: profile or marker</h1>
<p class="lead">Trim says what the sticker is cut to: the whole profile, or just the marker and its quiet zone.</p>
<h2>The rule</h2>
<ul class="plain">
<li><b>Profile</b> (the default): the sticker is the profile's shape, its holes cut out, white wherever there is no
black.</li>
<li><b>Marker</b>: the sticker is the marker and its quiet zone, a rectangle, whatever the profile was.</li>
<li>There is no “trim to rectangle”: draw a rectangle profile and trim to Profile.</li>
<li>A label outside the marker does not survive Trim: Marker. The Studio says so: “{esc(drop)}”</li>
</ul>
<h2>On a disc</h2>
<p>A Ø90 mm disc with three Ø10 holes. Trimmed to Profile, the sticker is the disc. Trimmed to Marker, it is a
{num(max(xs) - min(xs), 1)} mm square: the {num(m_plan["marker_mm"], 1)} mm marker and its 1-cell quiet zone.</p>
<div class="figs">
{figure(sticker_svg(prof, "The disc, trimmed to its profile"), "Trim: Profile. The disc, holes and all.")}
{figure(sticker_svg(mark, "The same marker trimmed to the marker"), "Trim: Marker. Just the marker.")}
</div>
<h2>Why</h2>
{quote("there is no longer trim to rectangle. If you want trim to rectangle then just make your profile a rectangle and trim to profile!", "Zach, 2026-10-20")}
<p class="small muted">In the code: web_api.trim_of and cut_local (<a href="{SRC}/aruco_studio/web_api.py">web_api.py</a>);
the contract's Trim.</p>
{related("trim")}
</article>"""
    return shell(title="Trim: profile or marker", path="/guides/trim/",
                 description="What an ArUco Studio sticker is cut to: the whole profile, or the marker and its quiet zone.",
                 crumbs=[("Home", "/about/"), ("Guides", "/guides/"), ("Trim", None)], body=body)


def page_auto_id() -> str:
    def item(key, count=1, first=None, dictionary="DICT_4X4_50", kind="single"):
        return {"key": key, "type": kind, "dictionary": dictionary, "count": count, "first_id": first}

    a = IDS.assign_ids({"items": [item("m1"), item("m2"), item("m3")]})
    b = IDS.assign_ids({"items": [item("m1"), item("m2"), item("m3"), item("g1", 4, kind="grid")], "ledger": a["ledger"]})
    c = IDS.assign_ids({"items": [item("m1"), item("m2", first=10), item("m3"), item("g1", 4, kind="grid"), item("m4")],
                        "ledger": b["ledger"]})
    # the Studio's "Sticker sheet — many markers (Re-ID)" example (web/src/model/examples.ts STICKERS):
    # its kinds and the scattered ids the hash once gave it, in reading order
    sheet = [("s1", "single", 42), ("s2", "single", 25), ("s3", "grid", 33), ("s4", "single", 41),
             ("s5", "single", 37), ("s6", "charuco", 2), ("s7", "single", 17), ("s8", "grid", 43),
             ("s9", "single", 40), ("s10", "single", 1), ("s11", "single", 29), ("s12", "single", 30)]
    count = {"single": 1, "grid": 4, "charuco": 10}
    items = [item(k, count[t], kind=t) for k, t, _ in sheet]
    ledger = {k: f for k, _, f in sheet}
    re_id = IDS.assign_ids({"items": items, "ledger": ledger, "mode": "sequential", "start": 0, "fresh": True})
    again = IDS.assign_ids({"items": items, "ledger": re_id["ledger"], "mode": "sequential", "start": 0, "fresh": True})
    assert [x["ids"] for x in again["items"]] == [x["ids"] for x in re_id["items"]], "Re-ID is idempotent"
    clash = IDS.assign_ids({"items": [item("t1", first=5), item("t2", first=5)]})
    assert clash["warnings"], "two typed 5s are warned about"
    wrap = IDS.assign_ids({"items": [item("w1"), item("w2")], "ledger": {"w1": 49}})
    assert wrap["items"][1]["ids"] == [0] and wrap["warnings"], wrap
    by = {x["key"]: x for x in c["items"]}

    def rng(ids):
        return f"#{ids[0]}" if len(ids) == 1 else f"#{ids[0]}–{ids[-1]}"
    rows = "".join(f"<tr><td>{esc(t)}</td><td>{rng(list(range(f, f + count[t])))}</td><td>{rng(x['ids'])}</td></tr>"
                   for (k, t, f), x in zip(sheet, re_id["items"]))
    body = f"""<article>
<h1>Marker ids: next, and Re-ID</h1>
<p class="lead">You never have to pick an id. A new marker takes the next one free, a typed id always wins, and an id
once given never moves on its own.</p>
<h2>The rule</h2>
<ul class="plain">
<li><b>Next:</b> a new marker gets the first free block after the highest id in use in its dictionary family (4X4_50
and 4X4_1000 are one family: the first 50 are the same markers). A grid or a board gets one block, as many ids as it
prints.</li>
<li><b>Typed ids win.</b> Type one and it is kept, even when another marker has it; the Studio says:
“{esc(clash["warnings"][0]["text"])}”</li>
<li><b>Given ids stay.</b> Each marker's first id is kept in the file's ledger, so deleting or adding a marker never
renumbers the others. Past the end of a dictionary, numbering wraps to the lowest free block and says so: after #49 in
DICT_4X4_50 the next marker gets #{wrap["items"][1]["ids"][0]}, with “{esc(wrap["warnings"][0]["text"])}”</li>
<li><b>Re-ID</b> (Edit › Re-ID all markers) numbers the driven markers again in board order from a start you pick,
each grid or board one block. It is stateless: run it twice and nothing moves.</li>
</ul>
<h2>In numbers</h2>
<p>Three new markers get {rng(a["items"][0]["ids"])}, {rng(a["items"][1]["ids"])} and {rng(a["items"][2]["ids"])}; a
2 × 2 grid after them {rng(b["items"][3]["ids"])}. Type 10 on the second and the next new marker gets
{rng(by["m4"]["ids"])}, while the others keep theirs ({rng(by["m1"]["ids"])}, {rng(by["m3"]["ids"])},
{rng(by["g1"]["ids"])}).</p>
<p>The Sticker sheet example (File › Examples), whose ids are scattered, Re-ID'd from 0, in reading order:</p>
<table class="facts"><thead><tr><th>Marker</th><th>Before</th><th>After Re-ID</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Why</h2>
{quote("We don't want to have to worry about ensuring unique IDs.", "Zach, 2026-10-18")}
{quote("As I copy paste new single markers, how are the new IDs calculated? It seems like it would be simplest if they simply increment", "Zach, 2026-10-20")}
<p class="small muted">In the code: <a href="{SRC}/aruco_studio/core/autoid.py">core/autoid.py</a> (Next id, rule 3,
and Re-ID) through web_ids.assign_ids; the contract's IdRequest.</p>
{related("auto-id")}
</article>"""
    return shell(title="Marker ids: next, and Re-ID", path="/guides/auto-id/",
                 description="How ArUco Studio numbers markers: the next free id, typed ids win, given ids stay, Re-ID renumbers.",
                 crumbs=[("Home", "/about/"), ("Guides", "/guides/"), ("Marker ids", None)], body=body)


@dataclass(frozen=True)
class Guide:
    slug: str
    title: str
    takeaway: str


GUIDE_LIST = [
    Guide("label-placement", "Where to put a label, and a corner mark",
          "A short id on the black border row at the Studio's size, or outside the quiet zone; never in it. Measured "
          "by Verify on a test board you can open."),
    Guide("profile-first", "Profile first",
          "Pick a profile like an extrude; the marker goes in its largest clear box. Draw a rectangle to place it exactly."),
    Guide("size-step", "Exact sizes, and the size step",
          "Typed sizes are exact; driven ones round to 0.5 mm, a step you set, or whole printer dots."),
    Guide("heights", "Heights for 3D printing",
          "Inkjet has the paper; 3D print has a white and a black height, the black from the white's outer face."),
    Guide("trim", "Trim: profile or marker", "The sticker is cut to the whole profile, or just the marker and its quiet zone."),
    Guide("auto-id", "Marker ids: next, and Re-ID",
          "New markers take the next free id, typed ids win, given ids never move; Re-ID renumbers in board order."),
]
DECISIONS = {"profile-first": page_profile_first, "size-step": page_size_step, "heights": page_heights,
             "trim": page_trim, "auto-id": page_auto_id}


def index_page() -> str:
    first, rest = GUIDE_LIST[0], GUIDE_LIST[1:]
    cards = (f'<a class="card feature" href="/guides/{first.slug}/" data-guide="{first.slug}"><b>{esc(first.title)}</b>'
             f'<span>{esc(first.takeaway)}</span></a>'
             + "".join(f'<a class="card" href="/guides/{g.slug}/" data-guide="{g.slug}"><b>{esc(g.title)}</b>'
                       f'<span>{esc(g.takeaway)}</span></a>' for g in rest))
    body = f"""<article class="wide">
<h1>Guides</h1>
<p class="lead">Short notes on making markers that read, and on why the Studio works the way it does. Each number comes
from the Studio's own core.</p>
<div class="cards">{cards}</div>
</article>"""
    return shell(title="Guides", path="/guides/",
                 description="ArUco Studio guides: where to put a label, profile-first placement, size steps, 3D heights, trim and marker ids.",
                 crumbs=[("Home", "/about/"), ("Guides", None)], body=body)


# ------------------------------------------------------------------ main

def compact_json(data) -> str:
    """Indented JSON (a run diffs line by line) with each array of plain numbers on one line."""
    text = json.dumps(data, indent=1, ensure_ascii=False)
    return re.sub(r"\[\s+((?:-?[\d.eE+-]+,\s*)*-?[\d.eE+-]+)\s+\]",
                  lambda m: "[" + ", ".join(x.strip() for x in m.group(1).split(",")) + "]", text) + "\n"


def write(path: Path, text: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return len(text.encode())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pages", action="store_true", help="write the pages from the last run (verify.json): no Verify")
    ap.add_argument("--opencv", metavar="VERSION|PYTHON",
                    help="the one OpenCV Verify runs on: a version (5.0, 4.11) or a Python; default: the newest "
                         "installed (python -m aruco_studio.opencv_choice lists them). WHY one: docs/peps/0003")
    ap.add_argument("--detector-json", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--sweeps-json", action="store_true",
                    help="print only Verify's angle sweep of every marker on --opencv's OpenCV, as JSON (the e2e's oracle "
                         "for the browser's Verify); writes nothing")
    args = ap.parse_args()
    doc = board()
    if args.detector_json:                       # the run on this Python's OpenCV, as JSON on stdout (main's child)
        sys.stdout.write(json.dumps(run_detector(doc)))
        return 0
    if args.sweeps_json:
        choice = OC.choose(args.opencv)
        sys.stdout.write(json.dumps(run_sweeps(doc)) if OC.is_here(choice) else
                         OC.run_in(choice, [str(Path(__file__).resolve()), "--sweeps-json", "--opencv", choice["python"]]))
        return 0
    text = board_text(doc)
    write(BOARD, text)
    print(f"wrote {BOARD.relative_to(ROOT)} ({len(doc['features'])} markers)")
    try:
        choice = OC.choose(args.opencv)
    except ValueError as e:
        if not args.pages or args.opencv:
            raise SystemExit(str(e))
        choice = None                            # --pages with no OpenCV here: the run on disk, as it is
    if args.pages:
        results = json.loads(RESULTS.read_text())
        if results["board_sha256"] != hashlib.sha256(text.encode()).hexdigest():
            raise SystemExit("the board changed since verify.json was made: run without --pages")
        # WHY keyed on the OpenCV: the pages never show one OpenCV's run as another's
        if choice and not same_opencv(results.get("opencv", ""), choice["opencv"]):
            raise SystemExit(f"verify.json is OpenCV {results.get('opencv')}'s, the run asked for is "
                             f"{choice['opencv']}'s: run without --pages, or --pages --opencv {results.get('opencv')}")
        # the browser's OpenCV is the site's, not the run's: kept current (the e2e picks its oracle by it)
        studio = studio_opencv()
        if (results.get("studio_opencv"), results["detector"].get("studio")) != (studio, same_opencv(results["opencv"], studio)):
            results["studio_opencv"] = studio
            results["detector"]["studio"] = same_opencv(results["opencv"], studio)
            write(RESULTS, compact_json(results))
            print(f"wrote {RESULTS.relative_to(ROOT)}: the browser's OpenCV is now {studio}")
    else:
        print(f"running Verify on every marker with OpenCV {choice['opencv']} ({choice['python']}) ...")
        if OC.is_here(choice):
            run = run_detector(doc)
        else:
            run = json.loads(OC.run_in(choice, [str(Path(__file__).resolve()), "--detector-json"], live=True))
        assert same_opencv(run["opencv"], choice["opencv"]), (run["opencv"], choice)
        results = results_of(doc, run)
        results["detector"]["newest"] = OC.choose()["opencv"] if args.opencv else choice["opencv"]
        write(RESULTS, compact_json(results))
        print(f"wrote {RESULTS.relative_to(ROOT)}: OpenCV {run['opencv']}, {run['seconds']} s")
    check_headlines(results)
    check_old_finding()
    check_cited()
    check_sitemap()
    sizes = {}
    sizes["guides/label-placement/index.html"] = write(LP / "index.html", label_page(CASES, results))
    for slug, fn in DECISIONS.items():
        sizes[f"guides/{slug}/index.html"] = write(GUIDES / slug / "index.html", fn())
    sizes["guides/index.html"] = write(GUIDES / "index.html", index_page())
    used = {im["file"] for r in results["cases"] if r["verify"]["pictures"] for im in r["verify"]["pictures"]["images"]}
    for stale in MEDIA.glob("*.webp"):          # a picture the run does not name (another OpenCV's: names carry it)
        if stale.name not in used:
            stale.unlink()
    media = sum(p.stat().st_size for p in MEDIA.glob("*")) if MEDIA.exists() else 0
    for name, n in sizes.items():
        print(f"  {name:38s} {n / 1024:6.1f} KB")
    print(f"  {'guides/label-placement/media/':38s} {media / 1024:6.1f} KB")
    over = [n for n, s in sizes.items() if s > PAGE_BUDGET]
    if over:
        print(f"over the {PAGE_BUDGET // 1024} KB page budget: {over}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
