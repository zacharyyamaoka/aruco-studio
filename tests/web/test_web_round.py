"""Cells rule 2 (autosize.ROUND_RULE, 2026-10-20 night): an inkjet preset's
driven sizes on 0.5 mm. Zach, on an inkjet 3 x 1 at 29.9718 / 6.0113 mm:
"Why is the auto suggested spacing here strange? I feel we should by
default recommend to the nearest like .5 mm or so? (in inkjet printing)".

- the inkjet built-ins are the marker in 0.5 mm steps (cell_step_mm 0,
  web_api._round_marker), which an inkjet reads as rule 2 (web_api.cells_of);
- the DRIVEN marker steps DOWN onto 0.5 mm (it still fits), the DRIVEN grid
  separation goes to the NEAREST 0.5 mm, up when that is under one module,
  the DRIVEN ChArUco checker is on 0.5 mm; everything is re-fitted, so a
  driven plan never overflows;
- SET values are drawn as typed, never rounded;
- the Marker row says what the dots do (web_api.dots_note);
- 3D presets plan byte for byte as before (pinned digests)."""
from __future__ import annotations

import hashlib
import json
import math
import random
import re

import pytest

from aruco_studio import web_api as W
from aruco_studio.core import autosize as A

from test_web_api import preset, req
from test_web_profile_first import disc, in_rect, profiled

INK = preset()
A4 = preset("Inkjet · A4 vinyl")
D3 = preset("Default")
D3_LINES = preset("Default", cell_step_mm=0.675)
STEP = 0.5
TOL = 1e-9
TYPES = {"single": {"type": "single"},
         "grid 2x2": {"type": "grid", "cols": 2, "rows": 2},
         "grid 3x1": {"type": "grid", "cols": 3, "rows": 1},
         "charuco 5x4": {"type": "charuco", "cols": 5, "rows": 4}}
N = 6                      # DICT_4X4_50: modules per marker side


def on_step(v: float) -> bool:
    return abs(v / STEP - round(v / STEP)) * STEP <= TOL


def shapes():
    """20 rectangles and 20 face profiles (no rect: the core fits the box),
    seeded: rotated rectangles, plates with holes, discs, L shapes."""
    rnd = random.Random(20261020)
    out = []
    for k in range(20):
        r = {"cx": rnd.uniform(-80, 80), "cy": rnd.uniform(-80, 80), "w": rnd.uniform(45, 220),
             "h": rnd.uniform(45, 160), "angle_deg": rnd.choice([0.0, rnd.uniform(-90, 90)])}
        out.append((f"rect {k}", "rect", r, rnd.random() < 0.5))
    for k in range(20):
        kind = k % 4
        cx, cy = rnd.uniform(-50, 50), rnd.uniform(-50, 50)
        if kind == 0:                              # a rectangle profile, turned
            w, h, a = rnd.uniform(50, 200), rnd.uniform(50, 150), math.radians(rnd.uniform(-80, 80))
            c, s = math.cos(a), math.sin(a)
            loop = [[cx + c * u - s * v, cy + s * u + c * v]
                    for u, v in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]
            prof = {"loops": [loop]}
        elif kind == 1:                            # a plate with two holes
            w, h, rad = rnd.uniform(140, 220), rnd.uniform(80, 140), rnd.uniform(5, 12)
            prof = {"loops": [[[cx - w / 2, cy - h / 2], [cx + w / 2, cy - h / 2], [cx + w / 2, cy + h / 2],
                               [cx - w / 2, cy + h / 2]],
                              disc(cx - w / 3, cy, rad), disc(cx + w / 3, cy, rad)]}
        elif kind == 2:                            # a disc (counter-clockwise)
            prof = {"loops": [disc(cx, cy, rnd.uniform(45, 90))[::-1]]}
        else:                                      # an L
            a, b, t = rnd.uniform(120, 200), rnd.uniform(120, 200), rnd.uniform(60, 90)
            prof = {"loops": [[[cx, cy], [cx + a, cy], [cx + a, cy + t], [cx + t, cy + t],
                               [cx + t, cy + b], [cx, cy + b]]]}
        out.append((f"profile {k}", "profile", prof, False))
    return out


SHAPES = shapes()


def request(shape, marker, pre=INK):
    _name, how, geo, face = shape
    if how == "rect":
        return req(marker, rect=geo, pre=pre, face=face)
    return profiled(geo, marker=marker, pre=pre)


def check_driven(p, kind):
    """Rule 2 on a driven plan: the marker, separation and checker on 0.5 mm,
    no overflow, the pattern inside fit_rect; never under the rule's floors."""
    assert p["ok"], p["summary"]
    L = p["marker_mm"]
    assert on_step(L), L
    assert p["overflow_mm"] == 0.0
    assert in_rect(p["fit_rect"], p["outer"]), (p["fit_rect"], p["outer_mm"])
    if kind.startswith("grid"):
        s = p["separation_mm"]
        assert on_step(s), s
        assert s >= L / N - TOL                  # never under one module
        assert abs(s - max(0.2 * L, L / N)) <= STEP / 2.0 + TOL or s - L / N < STEP
    if kind.startswith("charuco"):
        S = p["checker_mm"]
        assert on_step(S), S
        assert L <= S * N / (N + 2.0) + TOL      # a module of white round the marker


# ------------------------------------------------------------------ the rule

def test_the_inkjet_built_ins_are_rule_2_and_3d_is_not():
    for pre in (INK, A4):
        assert pre["cell_step_mm"] == 0.0 and pre["min_cell_mm"] == 1.0
        assert W.cells_of(pre) == {"rule": A.ROUND_RULE, "of": "marker", "mm": 0.5, "min_mm": 1.0}
    assert W.cells_of(D3) == {"rule": A.CELL_RULE, "of": "marker", "mm": 0.5, "min_mm": 2.0}
    assert W.cells_of(D3_LINES)["of"] == "cell" and W.cells_of(D3_LINES)["rule"] == A.CELL_RULE
    # a user's inkjet preset with dots keeps its dots
    assert W.cells_of(dict(INK, cell_step_mm=0.042333))["of"] == "cell"
    # rule 3 (A.DOTS_RULE, barrier 11): tests/web/test_web_sizestep.py
    assert (A.CELL_RULE, A.ROUND_RULE, A.CELL_RULES) == (1, 2, (1, 2, A.DOTS_RULE))


def test_only_the_cells_step_of_the_built_ins_changed():
    """presets(): the inkjet built-ins' cell_step_mm 0.042333 -> 0, nothing
    else (the digest main pinned, with that one field set back); barrier 11
    added their size_step, said and taken off here."""
    out = json.loads(W.call("presets", "{}"))
    for p in out["result"][1:]:
        assert p["cell_step_mm"] == 0.0
        p["cell_step_mm"] = 0.042333
        assert p.pop("size_step") == {"of": "mm", "mm": 0.5}
    text = json.dumps(out, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert hashlib.sha256(text.encode()).hexdigest() == \
        "dd7c0cf29534e61a5aa1f26c082b7d9b875ddf88254679680400e7734209496d"


def test_zachs_3x1_is_round():
    """The screenshot's board, 29.9718 / 6.0113 mm under the dots (a 112 x 40
    rectangle: 40 mm high holds a 30.0 mm marker and its two 5.0 mm borders
    exactly): 30.0 / 6.0 mm, suggested as "3×1 @ 30.0 mm"."""
    r = {"w": 112.0, "h": 40.0}
    p = W.plan(req(TYPES["grid 3x1"], rect=r))
    assert (p["marker_mm"], p["separation_mm"], p["overflow_mm"]) == (30.0, 6.0, 0.0)
    dots = W.plan(req(TYPES["grid 3x1"], rect=r, pre=preset(cell_step_mm=0.042333)))
    assert (dots["marker_mm"], dots["separation_mm"]) == (29.9718, 6.0113)
    assert W.suggest(req({"type": "grid"}, rect=r))[0]["label"] == "3×1 @ 30.0 mm"
    # wider than it is tall: the gap rounded to nearest lets the marker grow
    q = W.plan(req(TYPES["grid 3x1"], rect={"w": 120.0, "h": 45.0}))
    assert (q["marker_mm"], q["separation_mm"]) == (32.0, 6.5)


@pytest.mark.parametrize("kind", list(TYPES))
@pytest.mark.parametrize("shape", SHAPES, ids=[s[0] for s in SHAPES])
def test_driven_inkjet_values_are_on_half_millimetres(kind, shape):
    p = W.plan(request(shape, TYPES[kind]))
    check_driven(p, kind)
    assert any(w["field"] == "marker.marker_mm" and "dots" in w["text"] for w in p["warnings"])


@pytest.mark.parametrize("kind", list(TYPES))
@pytest.mark.parametrize("shape", SHAPES[:20], ids=[s[0] for s in SHAPES[:20]])
def test_the_driven_marker_is_the_largest_that_fits(kind, shape):
    """Re-fitted after rounding: half a millimetre more overflows (a grid
    with its gap still driven, so the rounded gap is what is re-fitted)."""
    p = W.plan(request(shape, TYPES[kind]))
    if kind == "single":
        # a single's sticker is never flush with the box: FILL_CLEARANCE_M a side
        short = min(p["fit_rect"]["w"], p["fit_rect"]["h"])
        tile = (p["marker_mm"] + STEP) * (1.0 + 2.0 / N)
        assert tile > short - 2000.0 * A.FILL_CLEARANCE_M, (tile, short)
        return
    if kind.startswith("charuco"):
        up = dict(TYPES[kind], checker_mm=p["checker_mm"] + STEP)          # set, Auto on
    else:
        up = dict(TYPES[kind], auto=False, marker_mm=p["marker_mm"] + STEP)
    assert W.plan(request(shape, up))["overflow_mm"] > 0.0


def test_the_separation_rounds_to_nearest_and_never_under_a_module():
    G = A._Grid(N, {"rule": 2, "of": "marker", "mm": 0.5, "min_mm": 1.0})
    for L_mm, want in ((29.5, 6.0), (32.0, 6.5), (24.0, 5.0), (31.0, 6.0), (13.0, 2.5),
                       (2.0, 0.5), (3.5, 1.0), (1.0, 0.5)):
        assert G.gap(L_mm / 1000.0, A.GAP_RATIO) * 1000.0 == pytest.approx(want, abs=1e-9), L_mm
    # 3.5 mm: 0.2 L = 0.7 -> nearest 0.5, under the 0.583 mm module -> up to 1.0
    legacy = A._Grid(N, {"rule": 1, "of": "marker", "mm": 0.5, "min_mm": 1.0})
    assert legacy.gap(0.0295, A.GAP_RATIO) == pytest.approx(0.0059, abs=1e-12)
    assert A.cells_of({"rule": 2, "of": "marker", "mm": 0.5, "min_mm": 1.0}) == ("marker", 0.0005, 0.001, 2)
    assert A.cells_of({"rule": 1, "of": "marker", "mm": 0.5, "min_mm": 1.0}) == ("marker", 0.0005, 0.001)


def test_rule_2_is_a_known_size_grid():
    p = W.plan(req(TYPES["grid 2x2"], rect={"w": 80.0, "h": 80.0}))
    assert not [w for w in p["warnings"] if "not a size grid" in w["text"] or w["level"] != "info"]


# ------------------------------------------------------------------ set values

def test_typed_values_are_exact():
    single = W.plan(req({"auto": False, "marker_mm": 29.97}, rect={"w": 60.0, "h": 60.0}))
    assert single["marker_mm"] == 29.97
    both = W.plan(req(dict(TYPES["grid 3x1"], auto=False, marker_mm=29.97, separation_mm=6.0113),
                      rect={"w": 120.0, "h": 45.0}))
    assert (both["marker_mm"], both["separation_mm"]) == (29.97, 6.0113)
    # the marker typed, the separation driven: the marker as typed, the gap rounded
    m = W.plan(req(dict(TYPES["grid 3x1"], auto=False, marker_mm=29.97), rect={"w": 120.0, "h": 45.0}))
    assert m["marker_mm"] == 29.97 and m["separation_mm"] == 6.0
    # a set separation with Auto on: as typed, the marker re-fitted to it on 0.5 mm
    s = W.plan(req(dict(TYPES["grid 3x1"], separation_mm=6.0113), rect={"w": 120.0, "h": 45.0}))
    assert s["separation_mm"] == 6.0113 and on_step(s["marker_mm"]) and s["overflow_mm"] == 0.0
    # a set checker with Auto on: as typed, the marker the largest it holds
    c = W.plan(req(dict(TYPES["charuco 5x4"], checker_mm=17.33), rect={"w": 93.0, "h": 71.0}))
    assert c["checker_mm"] == 17.33 and on_step(c["marker_mm"])
    t = W.plan(req(dict(TYPES["charuco 5x4"], auto=False, marker_mm=12.97, checker_mm=17.33),
                   rect={"w": 93.0, "h": 71.0}))
    assert (t["marker_mm"], t["checker_mm"]) == (12.97, 17.33)
    # a typed size that overflows is still drawn as typed and flagged
    big = W.plan(req({"auto": False, "marker_mm": 29.97}, rect={"w": 20.0, "h": 20.0}))
    assert big["marker_mm"] == 29.97 and big["overflow_mm"] > 0


# ------------------------------------------------------------------ the dots

def test_the_marker_row_says_what_the_dots_do():
    p = W.plan(req({}, rect={"w": 40.0, "h": 40.0}))
    assert p["marker_mm"] == 29.5
    note = [w for w in p["warnings"] if "dots" in w["text"]]
    assert note == [{"field": "marker.marker_mm", "level": "info",
                     "text": "29.5 mm → cell 4.92 mm (116.1 dots); the printer rounds by ≤ 0.02 mm"}]
    # in place of the core's cells line on the preset, never beside it
    assert not [w for w in p["warnings"] if w["field"] == "preset" and "steps" in w["text"]]
    typed = W.plan(req({"auto": False, "marker_mm": 29.97}, rect={"w": 40.0, "h": 40.0}))
    assert any(w["text"] == "29.97 mm → cell 5.00 mm (118.0 dots); the printer rounds by ≤ 0.02 mm"
               for w in typed["warnings"])
    for pre in (D3, D3_LINES, preset(cell_step_mm=0.042333)):
        assert not [w for w in W.plan(req({}, rect={"w": 40.0, "h": 40.0}, pre=pre))["warnings"]
                    if "printer rounds" in w["text"]]


# ------------------------------------------------------------------ suggestions

LABEL = {"single": r"^\d+\.\d mm$", "grid": r"^\d+×\d+ @ \d+\.\d mm$",
         "charuco": r"^\d+×\d+ @ \d+\.\d / \d+\.\d mm$"}


@pytest.mark.parametrize("kind", ["single", "grid", "charuco"])
def test_suggestions_are_round(kind):
    seen = 0
    for shape in SHAPES:
        for s in W.suggest(request(shape, {"type": kind})):
            seen += 1
            assert re.match(LABEL[kind], s["label"]), s["label"]
            assert on_step(s["params"]["marker_mm"]) and on_step(s["params"]["checker_mm"]), s
            # picked: the board it names, its driven gap round
            pick = dict(s["params"], type=kind, auto=False)
            if kind == "charuco":
                pick["auto"] = True
                pick.pop("marker_mm")
            p = W.plan(request(shape, pick))
            assert p["ok"] and p["overflow_mm"] == 0.0 and on_step(p["separation_mm"])
            assert (p["cols"], p["rows"]) == (s["params"]["cols"], s["params"]["rows"])
    assert seen >= 40


# ------------------------------------------------------------------ the mutation

def test_without_the_gap_rounding_the_check_fails(monkeypatch):
    """The ruler can fail: rule 2's gap rounding switched off, a driven
    grid's separation is off the 0.5 mm grid and check_driven says so."""
    shape = ("3x1", "rect", {"cx": 0.0, "cy": 0.0, "w": 120.0, "h": 45.0, "angle_deg": 0.0}, False)
    check_driven(W.plan(request(shape, TYPES["grid 3x1"])), "grid 3x1")
    init = A._Grid.__init__

    def no_round(self, n, cells=None):
        init(self, n, cells)
        self.round_gap = False
    monkeypatch.setattr(A._Grid, "__init__", no_round)
    p = W.plan(request(shape, TYPES["grid 3x1"]))
    with pytest.raises(AssertionError):
        check_driven(p, "grid 3x1")
    assert (p["marker_mm"], p["separation_mm"]) == (32.0, 6.4)


# ------------------------------------------------------------------ 3D unchanged

def d3_cases():
    out = []
    for pre_name, pre in (("default", D3), ("lines", D3_LINES)):
        for kind, m in TYPES.items():
            for r in ({"w": 60.0, "h": 40.0}, {"cx": 7.0, "cy": -3.0, "w": 106.0, "h": 40.0, "angle_deg": 20.0},
                      {"w": 93.0, "h": 71.0}):
                out.append((f"{pre_name} {kind} auto {r['w']:g}", "plan", req(m, rect=r, pre=pre)))
            out.append((f"{pre_name} {kind} typed", "plan",
                        req(dict(m, auto=False, marker_mm=12.97, checker_mm=17.33), rect={"w": 93.0, "h": 71.0},
                            pre=pre)))
        for kind in ("single", "grid", "charuco"):
            out.append((f"{pre_name} suggest {kind}", "suggest",
                        req({"type": kind}, rect={"w": 106.0, "h": 40.0}, pre=pre)))
    return out


def d3_digest():
    h = hashlib.sha256()
    for name, call, payload in d3_cases():
        h.update(name.encode())
        h.update(W.call(call, json.dumps(payload)).encode())
    return h.hexdigest()


def test_3d_presets_are_unchanged():
    """Every 3D case's call() JSON as main 03594f9 answered it (before rule 2)."""
    assert len(d3_cases()) == 38
    assert d3_digest() == D3_MAIN


D3_MAIN = "05055e124aea236e24ad06ee40e704f1f9ab27249a5c918f4040672ae8204d85"
