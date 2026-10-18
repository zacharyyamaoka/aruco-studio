"""The online Studio's facade (aruco_studio/web_api.py) under CPython: every
CoreApi call, and the two core changes it needs (docs/design/online_studio_v1.md,
"Lane core"): a typed size drawn as typed and flagged red (`settings.as_typed`),
and a grid's separation as a field (`numbers.separation`). The same calls run
in Pyodide in web/scripts/parity.mjs, byte for byte."""
from __future__ import annotations

import base64
import copy
import json
import math
import re

import pytest

from aruco_studio import __version__
from aruco_studio import web_api as W
from aruco_studio.core import dictionary as D
from aruco_studio.core import make as MK
from aruco_studio.core import presets as P
from aruco_studio.plan import TagSpec, Target, plan_tag


def preset(name="Inkjet · Letter vinyl", **kw):
    p = copy.deepcopy(next(x for x in W.presets() if x["name"] == name))
    p.update(kw)
    return p


INK = preset()
INK_NO_SNAP = preset(cell_step_mm=0.0)          # typed sizes exactly as typed


def req(marker=None, rect=None, label=None, pre=None, face=False):
    m = {"type": "single", "dictionary": "DICT_4X4_50", "first_id": 0, "auto": True,
         "marker_mm": 0.0, "checker_mm": 0.0, "separation_mm": 0.0, "cols": 1, "rows": 1,
         "turn": 0, "flip": False, "quiet_modules": 1.0, "corner_mark": "none"}
    m.update(marker or {})
    lb = {"on": False, "text": "", "height_mm": 0.0, "side": "below", "gap_mm": 2.0,
          "offset_mm": [0.0, 0.0]}
    lb.update(label or {})
    return {"rect": dict({"cx": 0.0, "cy": 0.0, "w": 20.0, "h": 20.0, "angle_deg": 0.0},
                         **(rect or {})),
            "marker": m, "label": lb, "preset": pre or INK, "reference_face": face}


def box(loops):
    xs = [p[0] for lp in loops for p in lp]
    ys = [p[1] for lp in loops for p in lp]
    return min(xs), min(ys), max(xs), max(ys)


def black_box(plan):
    return box([poly["outer"] for poly in plan["black"]])


def errors(plan, field):
    return [w for w in plan["warnings"] if w["field"] == field and w["level"] == "error"]


# ------------------------------------------------------------------ info, presets

def test_info_lists_every_dictionary():
    got = W.info()
    assert got["core_version"].startswith(__version__)
    assert [d["name"] for d in got["dictionaries"]] == list(D.DICTIONARY_NAMES)
    d = next(d for d in got["dictionaries"] if d["name"] == "DICT_4X4_50")
    assert (d["capacity"], d["bits"]) == (50, 4)
    assert got["python"] and got["pyodide"] == ""


def test_presets_map_back_onto_the_core():
    got = W.presets()
    assert [p["id"] for p in got] == ["builtin:default", "builtin:inkjet-letter-vinyl",
                                      "builtin:inkjet-a4-vinyl"]
    assert all(p["builtin"] for p in got)
    d3, letter, a4 = got
    assert d3["method"] == "print3d" and d3["cell_step_mm"] == 0.0 and d3["min_cell_mm"] == 2.0
    assert (letter["method"], letter["page"], letter["page_mm"]) == ("inkjet", "Letter", [215.9, 279.4])
    assert (a4["page"], a4["page_mm"]) == ("A4", [210.0, 297.0])
    # the flat preset back onto the core: the make and the cells the core's preset gives
    for flat, core in ((letter, P.vinyl_preset("letter")), (a4, P.vinyl_preset("a4")),
                       (d3, P.default_preset())):
        kind = "sticker" if flat["method"] == "inkjet" else "print3d"
        assert W.make_of(flat, []) == MK.new_make(kind, core["profile"])
        want = P.cell_setting(core)
        if want["of"] == "marker":
            assert W.cells_of(flat) == want
        else:
            assert W.cells_of(flat) == dict(want, mm=round(flat["cell_step_mm"], 6))


# ------------------------------------------------------------------ core change A

def test_a_typed_size_is_drawn_as_typed_and_flagged():
    """30 mm single in a 20 x 20 rectangle: drawn at 30 mm, never clamped.
    overflow_mm is the OUTLINE's (the quiet-zone edge, contract.ts): with the
    default 1-module quiet zone the outline is 40 mm, so 10 mm a side; the
    black marker itself pokes 5 mm past each edge."""
    p = W.plan(req({"auto": False, "marker_mm": 30.0}, pre=INK_NO_SNAP))
    assert p["ok"] and p["marker_mm"] == 30.0 and not p["auto"]
    assert p["outer_mm"] == [40.0, 40.0] and p["outer_mm"][0] >= 30.0
    assert p["overflow_mm"] == pytest.approx((40.0 - 20.0) / 2.0, abs=1e-6)
    x0, y0, x1, y1 = black_box(p)
    assert (x1 - x0, y1 - y0) == (pytest.approx(30.0, abs=1e-6), pytest.approx(30.0, abs=1e-6))
    assert x1 - 10.0 == pytest.approx(5.0, abs=1e-6)       # the black: 5 mm past the edge
    red = errors(p, "marker.marker_mm")
    assert len(red) == 1 and "20.0 mm wider and 20.0 mm taller than the 20 × 20 mm rectangle" \
        in red[0]["text"]


def test_a_fitting_or_auto_size_has_no_overflow():
    for m in ({"auto": False, "marker_mm": 12.0}, {"auto": True}):
        p = W.plan(req(m, pre=INK_NO_SNAP))
        assert p["ok"] and p["overflow_mm"] == 0.0 and not errors(p, "marker.marker_mm")
    p = W.plan(req({"auto": False, "marker_mm": 12.0}, pre=INK_NO_SNAP))
    assert p["marker_mm"] == 12.0


def test_as_typed_is_opt_in():
    """Without settings.as_typed the core clamps a typed size, as before."""
    s = {"layout": "single", "origin_v": 2, "make": MK.new_make("sticker", None)}
    t = Target(kind="free", w_mm=20.0, h_mm=20.0, has_body=False)
    old = plan_tag(TagSpec(settings=s, numbers={"size": 30.0}, target=t)).data
    assert old["ok"] and old["layout"]["marker_mm"] < 20.0 and "overflow_mm" not in old
    new = plan_tag(TagSpec(settings=dict(s, as_typed=True), numbers={"size": 30.0}, target=t)).data
    assert new["layout"]["marker_mm"] == 30.0 and new["overflow_mm"] == [10.0, 10.0]


def test_typed_counts_are_kept_and_auto_fills_them():
    m = {"type": "grid", "cols": 3, "rows": 2}
    auto = W.plan(req(dict(m, auto=True), rect={"w": 60.0, "h": 40.0}))
    assert auto["ok"] and (auto["cols"], auto["rows"]) == (3, 2) and auto["overflow_mm"] == 0.0
    assert auto["outer_mm"][0] <= 60.0 and auto["outer_mm"][1] <= 40.0
    assert max(auto["outer_mm"][0] / 60.0, auto["outer_mm"][1] / 40.0) > 0.97   # it fills
    typed = W.plan(req(dict(m, auto=False, marker_mm=12.0), rect={"w": 60.0, "h": 40.0},
                       pre=INK_NO_SNAP))
    assert (typed["cols"], typed["rows"], typed["marker_mm"]) == (3, 2, 12.0)
    assert not [w for w in typed["warnings"] if w["field"] == "marker.cols"]
    many = W.plan(req(dict(m, auto=False, marker_mm=12.0, cols=6, rows=4),
                      rect={"w": 60.0, "h": 40.0}, pre=INK_NO_SNAP))
    assert (many["cols"], many["rows"]) == (6, 4) and many["overflow_mm"] > 0
    assert errors(many, "marker.marker_mm")


# ------------------------------------------------------------------ core change B

def _gaps(p):
    """The gaps between the markers' black squares along x (each marker's
    black border is one polygon's outer loop, the marker's own square)."""
    spans = sorted({(round(b[0], 6), round(b[2], 6)) for b in
                    (box([poly["outer"]]) for poly in p["black"])
                    if abs((b[2] - b[0]) - p["marker_mm"]) < 1e-6})
    return [round(spans[i + 1][0] - spans[i][1], 6) for i in range(len(spans) - 1)]


def test_separation_is_a_field():
    m = {"type": "grid", "cols": 2, "rows": 1, "auto": False, "marker_mm": 10.0,
         "separation_mm": 5.0}
    p = W.plan(req(m, rect={"w": 60.0, "h": 40.0}, pre=INK_NO_SNAP))
    assert p["ok"] and p["separation_mm"] == 5.0
    assert _gaps(p) == [5.0]
    d, _i = W._plan(req(m, rect={"w": 60.0, "h": 40.0}, pre=INK_NO_SNAP))
    assert d["marker"]["separation_m"] == 0.005                # OpenCV's board definition
    # 0 = the rule (max(0.2 L, L / n)): 2.0 mm at 10 mm
    rule = W.plan(req(dict(m, separation_mm=0.0), rect={"w": 60.0, "h": 40.0}, pre=INK_NO_SNAP))
    assert _gaps(rule) == [2.0]
    # Auto honours it too
    auto = W.plan(req(dict(m, auto=True), rect={"w": 60.0, "h": 40.0}, pre=INK_NO_SNAP))
    assert auto["separation_mm"] == 5.0 and _gaps(auto) == [5.0]


def test_separation_reaches_the_opencv_board():
    from aruco_studio.core import board as B
    d, _i = W._plan(req({"type": "grid", "cols": 2, "rows": 2, "auto": False, "marker_mm": 10.0,
                         "separation_mm": 4.0}, rect={"w": 60.0, "h": 40.0}, pre=INK_NO_SNAP))
    mk = d["marker"]
    spec = B.BoardSpec(layout="grid", dictionary=mk["dictionary"], first_id=0,
                       marker_length_m=mk["marker_length_m"], rows=mk["rows"], cols=mk["cols"],
                       separation_m=mk["separation_m"])
    assert B.extent_m(spec)[0] == pytest.approx(0.024, abs=1e-12)     # 2 x 10 + 4


def test_a_negative_separation_is_refused_on_its_row():
    p = W.plan(req({"type": "grid", "cols": 2, "rows": 1, "auto": False, "marker_mm": 10.0,
                    "separation_mm": -1.0}, rect={"w": 60.0, "h": 40.0}))
    assert p["ok"]                       # 0 or less = the rule; the facade sends only > 0
    s = {"layout": "grid", "force": [2, 1]}
    t = Target(kind="free", w_mm=60.0, h_mm=40.0, has_body=False)
    bad = plan_tag(TagSpec(settings=s, numbers={"size": 10.0, "separation": -1.0}, target=t)).data
    assert not bad["ok"] and bad["warnings"][0]["field"] == "numbers.separation"


# ------------------------------------------------------------------ placement

def test_the_plan_is_placed_by_the_rectangle():
    a = W.plan(req({"type": "grid", "cols": 3, "rows": 2}, rect={"w": 60.0, "h": 40.0}))
    b = W.plan(req({"type": "grid", "cols": 3, "rows": 2},
                   rect={"cx": 100.0, "cy": -50.0, "w": 60.0, "h": 40.0, "angle_deg": 90.0}))
    ax0, ay0, ax1, ay1 = box([a["outer"]])
    bx0, by0, bx1, by1 = box([b["outer"]])
    assert (ax1 - ax0, ay1 - ay0) == (pytest.approx(by1 - by0), pytest.approx(bx1 - bx0))
    assert ((bx0 + bx1) / 2.0, (by0 + by1) / 2.0) == (pytest.approx(100.0), pytest.approx(-50.0))
    assert b["origin"][3] != a["origin"][3]


def test_turn_90_swaps_the_outline_axes():
    m = {"type": "grid", "cols": 3, "rows": 2, "auto": False, "marker_mm": 12.0}
    r0 = W.plan(req(m, rect={"w": 60.0, "h": 40.0}, pre=INK_NO_SNAP))
    r90 = W.plan(req(dict(m, turn=90), rect={"w": 60.0, "h": 40.0}, pre=INK_NO_SNAP))
    assert r0["outer_mm"] == list(reversed(r90["outer_mm"])) and r0["outer_mm"][0] > r0["outer_mm"][1]
    # the footprint on the sketch stays: the turn is on the marker's own footprint
    assert box([r0["outer"]]) == pytest.approx(box([r90["outer"]]), abs=1e-6)
    # OpenCV's x axis turned a quarter
    assert (r90["origin"][0], r90["origin"][4]) != (r0["origin"][0], r0["origin"][4])


def test_flip_mirrors_and_a_reference_face_ignores_it():
    m = {"auto": False, "marker_mm": 15.0, "first_id": 7}
    a = W.plan(req(m, pre=INK_NO_SNAP))
    f = W.plan(req(dict(m, flip=True), pre=INK_NO_SNAP))
    mirrored = sorted(tuple(sorted((x, -y) for x, y in poly["outer"])) for poly in a["black"])
    assert sorted(tuple(sorted(map(tuple, poly["outer"]))) for poly in f["black"]) == \
        pytest.approx(mirrored)
    assert f["origin"][10] == -a["origin"][10]               # z flipped
    for poly in f["black"]:                                   # still CCW outers, CW holes
        assert W._area2(poly["outer"]) > 0 and all(W._area2(h) < 0 for h in poly["holes"])
    face = W.plan(req(dict(m, flip=True), pre=INK_NO_SNAP, face=True))
    assert face["black"] == W.plan(req(m, pre=INK_NO_SNAP, face=True))["black"]
    assert any(w["field"] == "marker.flip" and w["level"] == "info" for w in face["warnings"])


def test_every_type_plans():
    for t in ("single", "grid", "charuco"):
        p = W.plan(req({"type": t, "cols": 4, "rows": 3}, rect={"w": 80.0, "h": 60.0}))
        assert p["ok"] and p["black"] and len(p["origin"]) == 16, (t, p["warnings"])
        assert p["summary"].startswith({"single": "Single", "grid": "Grid 4×3",
                                        "charuco": "ChArUco 4×3"}[t])
        assert (p["checker_mm"] > 0) == (t == "charuco")
    p3d = W.plan(req({"type": "grid", "cols": 2, "rows": 2}, rect={"w": 60.0, "h": 60.0},
                     pre=preset("Default")))
    assert p3d["ok"] and p3d["black"]


def test_a_refusal_comes_back_as_a_plan():
    p = W.plan(req({"type": "grid", "cols": 10, "rows": 10, "first_id": 0},
                   rect={"w": 200.0, "h": 200.0}))
    assert not p["ok"] and p["black"] == [] and p["warnings"]
    assert any(w["level"] == "error" for w in p["warnings"])


# ------------------------------------------------------------------ the label

def test_label_text_and_default_spot():
    p = W.plan(req({"type": "grid", "cols": 3, "rows": 2, "first_id": 4},
                   rect={"cx": 10.0, "cy": 20.0, "w": 60.0, "h": 40.0},
                   label={"on": True, "text": "{type} {dict} {ids} ({first}..{last}) #{id}",
                          "gap_mm": 2.0}))
    lab = p["label"]
    assert lab["text"] == "Grid 4X4_50 4-9 (4..9) #4"
    cap = 40.0 * 0.12
    assert lab["height_mm"] == pytest.approx(cap)
    assert lab["at"] == [pytest.approx(10.0), pytest.approx(20.0 - 20.0 - 2.0 - cap / 2.0)]
    moved = W.plan(req({"type": "single"}, label={"on": True, "side": "above", "height_mm": 3.0,
                                                  "offset_mm": [1.0, -1.0]}))["label"]
    assert moved["text"] == "#0" and moved["height_mm"] == 3.0
    assert moved["at"] == [pytest.approx(1.0), pytest.approx(10.0 + 2.0 + 1.5 - 1.0)]
    assert W.plan(req())["label"] is None


# ------------------------------------------------------------------ inscribe, suggest

def _disc(cx, cy, r, n=72, cw=True):
    pts = [[cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)]
           for k in range(n)]
    return pts[::-1] if cw else pts


def test_inscribe_keeps_off_the_holes():
    plate = [[-60.0, -40.0], [60.0, -40.0], [60.0, 40.0], [-60.0, 40.0]]
    holes = [(-35.0, 0.0), (35.0, 0.0)]
    prof = {"loops": [plate] + [_disc(x, y, 10.0) for x, y in holes]}
    r = W.inscribe(prof, "avoid")
    assert r is not None and r["angle_deg"] == 0.0
    x0, x1 = r["cx"] - r["w"] / 2.0, r["cx"] + r["w"] / 2.0
    y0, y1 = r["cy"] - r["h"] / 2.0, r["cy"] + r["h"] / 2.0
    for hx, hy in holes:                         # the nearest point of the rect to the centre
        nx, ny = min(max(hx, x0), x1), min(max(hy, y0), y1)
        assert math.hypot(nx - hx, ny - hy) >= 10.0 * math.cos(math.pi / 72) - 1e-3
    assert x0 >= -60.0 - 1e-6 and x1 <= 60.0 + 1e-6 and y0 >= -40.0 - 1e-6 and y1 <= 40.0 + 1e-6
    ig = W.inscribe(prof, "ignore")
    assert ig["w"] * ig["h"] > r["w"] * r["h"]
    assert ig["w"] == pytest.approx(120.0, abs=0.1) and ig["h"] == pytest.approx(80.0, abs=0.1)
    assert W.inscribe({"loops": []}, "avoid") is None


def test_suggestions_carry_reasons():
    for t, rect in (("single", {"w": 30.0, "h": 30.0}), ("grid", {"w": 60.0, "h": 40.0}),
                    ("charuco", {"w": 80.0, "h": 60.0})):
        got = W.suggest(req({"type": t, "cols": 2, "rows": 2}, rect=rect))
        assert got, t
        assert all(s["label"] and s["reason"] for s in got)
        assert set(got[0]["params"]) == {"cols", "rows", "marker_mm", "checker_mm", "separation_mm"}
        assert "largest marker" in got[0]["reason"]
        assert any("cells = " in s["reason"] and "dots of 0.042333 mm" in s["reason"] for s in got)
    # 3D: lines, not dots
    g3 = W.suggest(req({"type": "grid"}, rect={"w": 60.0, "h": 40.0},
                       pre=preset("Default", cell_step_mm=0.675)))
    for s in g3:                                  # the words say what the cell is
        k = int(re.search(r"cells = (\d+) lines? of 0\.675 mm", s["reason"]).group(1))
        assert s["params"]["marker_mm"] / 6.0 == pytest.approx(k * 0.675, abs=1e-6)
    # picking one gives that board, at that size
    s = W.suggest(req({"type": "grid"}, rect={"w": 60.0, "h": 40.0}))[2]
    p = W.plan(req(dict({"type": "grid", "auto": False}, **s["params"]), rect={"w": 60.0, "h": 40.0}))
    assert (p["cols"], p["rows"], p["marker_mm"], p["overflow_mm"]) == \
        (s["params"]["cols"], s["params"]["rows"], s["params"]["marker_mm"], 0.0)


# ------------------------------------------------------------------ svg, sheet

def test_svg_is_true_size_with_its_label():
    out = W.svg(req({"auto": False, "marker_mm": 15.0}, pre=INK_NO_SNAP,
                    label={"on": True, "text": "#{id} {dict}"}))
    assert out.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="') and 'mm" height="' in out
    assert ">#0 4X4_50</text>" in out and out.endswith("</svg>")
    plain = W.svg(req({"auto": False, "marker_mm": 15.0}, pre=INK_NO_SNAP))
    assert 'width="20mm" height="20mm"' in plain             # 15 + 2 x 2.5 quiet zone


def test_sheet_letter_gives_pages_and_a_pdf():
    items = [req({"first_id": i}, label={"on": True, "text": "part {id}"}) for i in range(3)]
    items.append(req({"type": "grid", "cols": 3, "rows": 2, "first_id": 10},
                     rect={"w": 60.0, "h": 40.0}))
    got = W.sheet({"items": items, "cut_lines": True}, "2026-10-18")
    assert got["pages"] >= 1 and len(got["svg"]) == got["pages"]
    assert all(s.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="215.9mm" '
                            'height="279.4mm"') for s in got["svg"])
    assert ">part 1</text>" in got["svg"][0] and "data-cut=" in got["svg"][0]
    assert base64.b64decode(got["pdf_base64"]).startswith(b"%PDF")
    assert not [w for w in got["warnings"] if w["level"] == "error"]
    no_cut = W.sheet({"items": items[:1], "cut_lines": False}, "2026-10-18")
    assert "data-cut=" not in no_cut["svg"][0]


def test_sheet_flags_a_marker_bigger_than_the_page():
    big = req({"auto": False, "marker_mm": 300.0}, rect={"w": 300.0, "h": 300.0})
    got = W.sheet({"items": [big], "cut_lines": True}, "2026-10-18")
    red = [w for w in got["warnings"] if w["field"] == "preset" and w["level"] == "error"]
    assert any("not printed" in w["text"] for w in red)
    p = W.plan(big)
    assert any(w["field"] == "preset" and w["text"].startswith("Over the page")
               for w in p["warnings"])


# ------------------------------------------------------------------ call

def test_call_never_raises():
    assert "error" in json.loads(W.call("nope", "{}"))
    assert "error" in json.loads(W.call("plan", "{not json"))
    assert "error" in json.loads(W.call("plan", "{}"))
    r = req({"type": "grid", "cols": 2, "rows": 2}, rect={"w": 50.0, "h": 50.0})
    got = json.loads(W.call("plan", json.dumps(r)))
    assert got == {"result": json.loads(json.dumps(W.plan(r)))}
    assert json.loads(W.call("inscribe", json.dumps({"profile": {"loops": []}, "holes": "avoid"}))) \
        == {"result": None}
    assert len(json.loads(W.call("presets", "{}"))["result"]) == 3


def test_sheet_prints_the_label_at_the_sketch_labels_size():
    # WYSIWYG (Zach, 2026-10-16: "if you have a label on the page it needs to
    # be in CAD"): the page's label has the cap height plan() gives the sketch.
    r = req(marker={"type": "grid", "cols": 2, "rows": 2},
            label={"on": True, "text": "", "height_mm": 0, "side": "below", "gap_mm": 2.0})
    cap = W.plan(r)["label"]["height_mm"]
    page = W.sheet({"items": [r], "cut_lines": True}, "2026-10-18")["svg"][0]
    sizes = [float(f) for f, t in re.findall(r'<text[^>]*font-size="([\d.]+)"[^>]*>([^<]*)</text>', page)
             if t == W.plan(r)["label"]["text"]]
    assert sizes, "the label is on the page"
    assert sizes[0] * W.CAP_EM == pytest.approx(cap, abs=1e-3)
