"""What prints is what the canvas says (Zach, 2026-10-21, arucostudio.com: a
123.5 x 40 rectangle profile holding a 3 x 1 grid of 30 mm DICT_4X4_50 on the
inkjet preset; "I am expecting 123.5 but it seems actually wider than that").

The oracle is the PDF itself: every sheet here is decoded (its FlateDecode
content streams, core/sheet.py _pdf_ops) and its cut line -- the grey stroked
loop -- measured in points, then millimetres. Two promises, over a sweep of
presets x marker types x profiles x trims x labels x turns:

1. Trim Profile: the printed cut is the profile, to 0.1 mm.
2. Either trim: every size the Studio shows as the sticker's outer size is the
   printed cut, to 0.1 mm -- the canvas's driven Outer dimensions (plan dims
   "outer"), the panel's summary ("outer W x H mm") and the Marker row's
   size line ("sticker W x H mm").

Before 2026-10-21 promise 2 failed whenever the marker did not fill its
profile: all three said the marker's quiet-zone box (112.0 x 40.0 here) while
the sheet cut the profile (123.5 x 40.0)."""
from __future__ import annotations

import base64
import copy
import math
import re
import zlib

import pytest

from aruco_studio import web_api as W
from aruco_studio.core import sheet as SH

from test_web_api import preset

TOL_MM = 0.1                 # Zach's tolerance for a printed size
WORDS_TOL_MM = 0.05 + 1e-9   # a size written with one decimal
PT_MM = 25.4 / 72.0
DATE = "2026-10-21"


# ------------------------------------------------------------------ the PDF

def pdf_cuts(pdf: bytes) -> list:
    """Every page's cut loops, decoded from the PDF bytes alone: [{"page",
    "page_mm": (w, h), "loops": [[(x, y) mm, ...], ...]}] per stroked cut
    path (grey core.sheet.CUT_GREY; a crop mark is a two-point line, not a
    loop). Pages in /Kids order."""
    objs = {int(m.group(1)): m.group(2)
            for m in re.finditer(rb"(\d+) 0 obj\n(.*?)\nendobj\n", pdf, re.S)}
    kids = re.search(rb"/Type /Pages /Kids \[([^\]]*)\]", pdf).group(1)
    out = []
    for page_no, ref in enumerate(re.findall(rb"(\d+) 0 R", kids), start=1):
        body = objs[int(ref)]
        media = [float(v) for v in re.search(rb"/MediaBox \[([^\]]*)\]", body).group(1).split()]
        raw = objs[int(re.search(rb"/Contents (\d+) 0 R", body).group(1))]
        start = raw.index(b"stream\n") + len(b"stream\n")
        stream = zlib.decompress(raw[start:raw.rindex(b"\nendstream")]).decode("latin-1")
        # the text's literal strings out first: a word in a label is no operator
        stream = re.sub(r"\((?:\\.|[^\\)])*\)", " ", stream)
        grey, stack, subs = None, [], []
        for tok in stream.split():
            if tok in ("m", "l"):
                y, x = float(stack.pop()), float(stack.pop())
                if tok == "m":
                    subs.append([])
                subs[-1].append((x * PT_MM, y * PT_MM))
                stack = []
            elif tok == "G":
                grey = float(stack.pop())
                stack = []
            elif tok in ("S", "f", "f*"):
                loops = [sp for sp in subs if len(sp) >= 3]
                if tok == "S" and grey is not None and abs(grey - SH.CUT_GREY) < 1e-9 and loops:
                    out.append({"page": page_no, "page_mm": (media[2] * PT_MM, media[3] * PT_MM),
                                "loops": loops})
                subs, stack = [], []
            elif tok in ("BT", "ET", "h", "w", "g", "re", "Tf", "Td", "Tm", "Tj"):
                stack = []
            else:
                stack.append(tok)
    return out


def size_of(loop):
    xs, ys = [p[0] for p in loop], [p[1] for p in loop]
    return max(xs) - min(xs), max(ys) - min(ys)


def perimeter(loop):
    return sum(math.dist(loop[k - 1], loop[k]) for k in range(len(loop)))


def printed(req: dict):
    """(the sheet, the printed cut's outer loop in mm, its w x h in the
    sticker's own frame -- the placement's 90 degree turn undone), or None
    when the sheet did not print the item."""
    sh = W.sheet({"items": [req]}, DATE)
    if len(sh["placements"]) != 1:
        return None
    cuts = pdf_cuts(base64.b64decode(sh["pdf_base64"]))
    assert len(cuts) == 1, "one sticker, one cut path"
    outer = max(cuts[0]["loops"], key=lambda lp: size_of(lp)[0] * size_of(lp)[1])
    w, h = size_of(outer)
    if sh["placements"][0]["rotation"] == 90:
        w, h = h, w
    return sh, outer, (w, h)


# ------------------------------------------------------------------ what the Studio says

def shown_outer(plan: dict):
    """The canvas's driven Outer W x H (web/src/sketch/Dims.tsx draws the
    plan's two "outer" dims): the one along the rectangle's x, then y."""
    rect = plan["fit_rect"]
    c, s = math.cos(math.radians(rect["angle_deg"])), math.sin(math.radians(rect["angle_deg"]))
    w = h = None
    for d in plan["dims"]:
        if d["field"] != "outer":
            continue
        du, dv = d["b"][0] - d["a"][0], d["b"][1] - d["a"][1]
        along_x = abs(c * du + s * dv) > abs(-s * du + c * dv)
        assert abs(math.hypot(du, dv) - d["value_mm"]) < 1e-6, "a dim is as long as its value"
        if along_x:
            w = d["value_mm"]
        else:
            h = d["value_mm"]
    return w, h


def summary_outer(plan: dict):
    m = re.search(r"· outer (\d+(?:\.\d+)?) × (\d+(?:\.\d+)?) mm$", plan["summary"])
    assert m, plan["summary"]
    return float(m.group(1)), float(m.group(2))


def size_line_sticker(plan: dict):
    """The Marker row's "sticker W × H mm" (core.form.size_line), or None."""
    for w in plan["warnings"]:
        m = re.search(r"· sticker (\d+(?:\.\d+)?)(?: × (\d+(?:\.\d+)?))? mm", w["text"])
        if m and w["field"] == "marker.marker_mm":
            a = float(m.group(1))
            return a, float(m.group(2)) if m.group(2) else a
    return None


def over_the_page(plan: dict) -> bool:
    """The panel's red page lint (CF-6): the sheet will not place it."""
    return any(w["level"] == "error" and w["text"].startswith("Over the page") for w in plan["warnings"])


def profile_size(req: dict, plan: dict):
    """The profile's outer loop measured in the frame the sticker is printed
    in (the box the core placed the marker in: its turn undone)."""
    a = -math.radians(plan["fit_rect"]["angle_deg"])
    c, s = math.cos(a), math.sin(a)
    lp = [(c * x - s * y, s * x + c * y) for x, y in req["profile"]["loops"][0]]
    return size_of(lp), perimeter(req["profile"]["loops"][0])


# ------------------------------------------------------------------ the requests

def rect_loop(w, h, cx=0.0, cy=0.0, deg=0.0):
    """A rectangle as the UI draws one (geom.rectCorners: counter-clockwise from (-w/2, -h/2))."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[cx + c * u - s * v, cy + s * u + c * v]
            for u, v in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]


def disc(cx, cy, r, n=72):
    return [[cx + r * math.cos(-2 * math.pi * k / n), cy + r * math.sin(-2 * math.pi * k / n)]
            for k in range(n)]


PROFILES = {
    "rect-123.5x40": {"loops": [rect_loop(123.5, 40.0)]},          # Zach's
    "rect-60x45": {"loops": [rect_loop(60.0, 45.0, 12.0, -7.0)]},
    "rect-70x40-turned-30": {"loops": [rect_loop(70.0, 40.0, -5.0, 3.0, 30.0)]},
    "face-plate-2-holes": {"loops": [rect_loop(120.0, 80.0), disc(-35.0, 0.0, 10.0),
                                     disc(35.0, 0.0, 10.0)]},
    "face-L": {"loops": [[[0.0, 0.0], [90.0, 0.0], [90.0, 30.0], [30.0, 30.0], [30.0, 70.0],
                          [0.0, 70.0]]]},
}
MARKERS = {
    "single": {"type": "single"},
    "single-typed-20": {"type": "single", "auto": False, "marker_mm": 20.0},
    "grid-3x1": {"type": "grid", "cols": 3, "rows": 1},
    "charuco-4x3": {"type": "charuco", "cols": 4, "rows": 3},
}
LABELS = {
    "off": {"on": False},
    "on-marker": {"on": True, "text": "#{ids}"},
    "outside": {"on": True, "text": "#{ids}", "place": "outside", "side": "below"},
}
PRESETS = {
    "letter": preset(),
    "a4": preset("Inkjet · A4 vinyl"),
    "custom-180x250": dict(preset(), id="my:custom", name="My custom paper", builtin=False,
                           page="Custom", page_mm=[180.0, 250.0]),
}


def request(profile, marker, label="off", trim="profile", turn=0, pre="letter"):
    m = {"type": "single", "dictionary": "DICT_4X4_50", "first_id": 0, "auto": True,
         "marker_mm": 30.0, "checker_mm": 0.0, "separation_mm": 0.0, "cols": 1, "rows": 1,
         "turn": turn, "flip": False, "quiet_modules": 1, "corner_mark": "none"}
    m.update(marker)
    lb = {"on": False, "text": "#{ids}", "height_mm": 0.0, "side": "below", "gap_mm": 2.0,
          "offset_mm": [0.0, 0.0]}
    lb.update(LABELS[label] if isinstance(label, str) else label)
    face = not profile.startswith(("rect", "lint"))
    return {"trim": trim, "profile": copy.deepcopy(PROFILES.get(profile) or LINT[profile]), "holes": "avoid",
            "marker": m, "label": lb, "preset": copy.deepcopy(PRESETS[pre]),
            "reference_face": face, "extrude": {}}


ZACH = dict(marker={"type": "grid", "cols": 3, "rows": 1, "first_id": 19})


# ------------------------------------------------------------------ Zach's sticker

def test_zachs_123_5_x_40_grid_prints_123_5_and_says_so():
    r = request("rect-123.5x40", ZACH["marker"])
    p = W.plan(r)
    assert p["ok"] and p["ids"] == [19, 20, 21]
    assert (p["marker_mm"], p["separation_mm"]) == (30.0, 6.0)
    # the marker's own outline (its quiet-zone box) is narrower than the profile
    assert p["outer_mm"] == [112.0, 40.0]
    sh, outer, (w, h) = printed(r)
    # the PDF cuts the profile: 123.5 x 40, at true size on a Letter page
    assert abs(w - 123.5) < TOL_MM and abs(h - 40.0) < TOL_MM
    assert base64.b64decode(sh["pdf_base64"]).count(b"/MediaBox [0 0 612 792]") == 1
    # and every size the Studio shows says the same
    assert shown_outer(p) == (123.5, 40.0)
    assert p["summary"].endswith("· outer 123.5 × 40.0 mm"), p["summary"]
    assert size_line_sticker(p) == (123.5, 40.0)


def test_zachs_grid_trimmed_to_the_marker_prints_and_says_112():
    r = request("rect-123.5x40", ZACH["marker"], trim="marker")
    p = W.plan(r)
    _sh, _outer, (w, h) = printed(r)
    assert abs(w - 112.0) < TOL_MM and abs(h - 40.0) < TOL_MM
    assert shown_outer(p) == (112.0, 40.0)
    assert p["summary"].endswith("· outer 112.0 × 40.0 mm")
    assert size_line_sticker(p) == (112.0, 40.0)


def test_a_rect_only_request_keeps_the_marker_outline_as_before():
    # the version boundary: Fusion and old callers send a rect and no profile
    # (barrier 9's legacy path), and their answers are pinned byte for byte
    # (tests/web/test_web_profile_first.py and the parity cases' pins), so
    # their Outer is still the marker's outline; the sheet cuts the rect
    r = request("rect-123.5x40", ZACH["marker"])
    del r["profile"]
    r["rect"] = {"cx": 0.0, "cy": 0.0, "w": 123.5, "h": 40.0, "angle_deg": 0.0}
    p = W.plan(r)
    assert shown_outer(p) == (112.0, 40.0)
    assert p["summary"].endswith("· outer 112.0 × 40.0 mm")
    _sh, _outer, (w, h) = printed(r)
    assert abs(w - 123.5) < TOL_MM and abs(h - 40.0) < TOL_MM


# ------------------------------------------------------------------ the family

CASES = [(pre, prof, mk) for pre in PRESETS for prof in PROFILES for mk in MARKERS]


@pytest.mark.parametrize("pre,prof,mk", CASES, ids=["-".join(c) for c in CASES])
def test_the_printed_cut_is_the_profile_and_the_outer_size_shown(pre, prof, mk):
    bad, measured = [], 0
    for trim in ("profile", "marker"):
        for label in LABELS:
            for turn in (0, 90):
                r = request(prof, MARKERS[mk], label, trim, turn, pre)
                p = W.plan(r)
                if not p["ok"]:
                    continue
                got = printed(r)
                case = f"{trim}/{label}/turn {turn}"
                if (got is None) != over_the_page(p):
                    bad.append(f"{case}: the panel's page lint says {over_the_page(p)}, the sheet "
                               f"{'refused' if got is None else 'placed'} it")
                if got is None:                    # too big for the page: refused, said
                    continue
                measured += 1
                sh, outer, (w, h) = got
                if trim == "profile":
                    (pw, ph), per = profile_size(r, p)
                    if abs(w - pw) > TOL_MM or abs(h - ph) > TOL_MM:
                        bad.append(f"{case}: printed {w:.3f} x {h:.3f}, profile {pw:.3f} x {ph:.3f}")
                    if abs(perimeter(outer) - per) > TOL_MM:
                        bad.append(f"{case}: printed perimeter {perimeter(outer):.3f}, profile {per:.3f}")
                sw, shh = shown_outer(p)
                if abs(sw - w) > TOL_MM or abs(shh - h) > TOL_MM:
                    bad.append(f"{case}: Outer dims {sw} x {shh}, printed {w:.3f} x {h:.3f}")
                ow, oh = summary_outer(p)
                if abs(ow - w) > WORDS_TOL_MM or abs(oh - h) > WORDS_TOL_MM:
                    bad.append(f"{case}: summary outer {ow} x {oh}, printed {w:.3f} x {h:.3f}")
                st = size_line_sticker(p)
                if st is not None and (abs(st[0] - w) > WORDS_TOL_MM or abs(st[1] - h) > WORDS_TOL_MM):
                    bad.append(f"{case}: size line sticker {st[0]} x {st[1]}, printed {w:.3f} x {h:.3f}")
                # the sheet's SVG cuts what the PDF cuts
                d = re.search(r'<path data-cut="m1"[^>]* d="([^"]*)"', sh["svg"][0]).group(1)
                nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", d)]
                sv = (max(nums[0::2]) - min(nums[0::2]), max(nums[1::2]) - min(nums[1::2]))
                if sh["placements"][0]["rotation"] == 90:
                    sv = sv[::-1]
                if abs(sv[0] - w) > 1e-3 or abs(sv[1] - h) > 1e-3:
                    bad.append(f"{case}: SVG cut {sv}, PDF cut {w:.4f} x {h:.4f}")
    assert measured >= 4, f"only {measured} printed: the sweep must print"
    assert not bad, "\n".join(bad)


# ------------------------------------------------------------------ the page lint

WIDE = [(190.0, 40.0), (230.0, 40.0), (260.0, 40.0), (200.0, 30.0)]
LINT = {f"lint-{w:g}x{h:g}": {"loops": [rect_loop(w, h)]} for w, h in WIDE}


@pytest.mark.parametrize("pre", ["letter", "a4", "custom-180x250"])
@pytest.mark.parametrize("trim", ["profile", "marker"])
@pytest.mark.parametrize("w,h", WIDE, ids=[f"{w:g}x{h:g}" for w, h in WIDE])
def test_the_page_lint_says_what_the_sheet_does(w, h, trim, pre):
    """The panel's "Over the page" (red) is said exactly when the sheet
    refuses the sticker, and "fits ... turned only" exactly when it turns it:
    both judge the sticker as it is cut, on the preset's paper as given."""
    r = request(f"lint-{w:g}x{h:g}", {"type": "single"}, trim=trim, pre=pre)
    p = W.plan(r)
    sh = W.sheet({"items": [r]}, DATE)
    placed = sh["placements"]
    assert over_the_page(p) == (not placed), p["warnings"]
    turned = any("turned only: the sheet turns it" in x["text"] for x in p["warnings"])
    assert turned == bool(placed and placed[0]["rotation"] == 90)
    assert not any("checked against Letter" in x["text"] for x in p["warnings"])


def test_a_typed_marker_over_a_small_profile_is_not_over_the_page():
    # the sheet cuts it to the 60 x 45 profile and prints it: the overflow is
    # the problem the panel shows (red on the marker's size), not the page
    r = request("rect-60x45", {"type": "single", "auto": False, "marker_mm": 200.0})
    p = W.plan(r)
    assert not over_the_page(p)
    assert any(x["field"] == "marker.marker_mm" and x["level"] == "error" for x in p["warnings"])
    assert printed(r)[2] == pytest.approx((60.0, 45.0), abs=TOL_MM)
    # trimmed to the marker, the 266.7 mm sticker is over the page, and refused
    m = request("rect-60x45", {"type": "single", "auto": False, "marker_mm": 200.0}, trim="marker")
    assert over_the_page(W.plan(m)) and printed(m) is None
