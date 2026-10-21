"""The size step (contract barrier 11, Zach 2026-10-20 night): what DRIVEN
sizes round to -- "maybe that's a preset you then put in the vinyl printer
preset... how many significant figures you want... that helps us cover all
bases".

- `marker.size_step` wins over `preset.size_step`, which wins over the old
  derivation from `cell_step_mm` (web_api.size_step_of);
- "dots": whole printer dots per cell, the cell step 25.4 / dpi exactly
  (autosize.DOTS_RULE, rule 3), the Marker note "27.94 mm = 6 cells × 110
  dots at 600 dpi, exact";
- "mm": cells rule 2 on any step (0.1 / 0.5 / 1): the driven marker,
  separation and checker on it;
- "line": the 3D line snap, as before;
- typed sizes are never rounded, under any step;
- a request without size_step is byte for byte what main 1ea2540 answered,
  and the built-ins' explicit {mm: 0.5} answers the same."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from aruco_studio import web_api as W
from aruco_studio.core import autosize as A

from test_web_api import preset, req
from test_web_profile_first import parity_cases
from test_web_round import SHAPES, TYPES, D3, D3_LINES, d3_cases, request

INK = preset()
A4 = preset("Inkjet · A4 vinyl")
DOTS = {"of": "dots"}
TOL = 1e-9
N = 6                      # DICT_4X4_50: modules per marker side
QUANTUM_MM = W.DOT_TOL_MM  # the core keeps lengths to 0.1 um (autosize._r7): half of it


def mm_step(mm):
    return {"of": "mm", "mm": mm}


def on(v, step, tol=TOL):
    return abs(v / step - round(v / step)) * step <= tol


def stepped(pre, step):
    """`pre` with its own size step `step` (a user's preset)."""
    return dict(pre, size_step=step)


def plan_with(shape, kind, pre=INK, marker_step=None, **m):
    mk = dict(TYPES[kind], **m)
    if marker_step is not None:
        mk["size_step"] = marker_step
    return W.plan(request(shape, mk, pre=pre))


def check_dots(p, kind, dpi, n=N, exact=True):
    """Whole printer dots per cell: cell / (25.4 / dpi) an integer (within
    1e-9 when n cells of whole dots are a whole 0.1 um, else within the
    core's length quantum); separation and checker on whole dots; nothing
    overflows; the Marker note says it is exact."""
    assert p["ok"], p["summary"]
    assert p["overflow_mm"] == 0.0
    dot = 25.4 / dpi
    k = p["marker_mm"] / n / dot
    assert k >= 1 and abs(k - round(k)) <= (TOL if exact else QUANTUM_MM / n / dot), (p["marker_mm"], k)
    if kind.startswith("grid"):
        assert on(p["separation_mm"], dot, QUANTUM_MM), p["separation_mm"]
    if kind.startswith("charuco"):
        assert on(p["checker_mm"], dot, QUANTUM_MM), p["checker_mm"]
    note = [w["text"] for w in p["warnings"] if w["field"] == "marker.marker_mm" and "dots at" in w["text"]]
    assert note and note[0].endswith(f"{n} cells × {round(k)} dots at {dpi} dpi, exact"), p["warnings"]


def check_mm(p, kind, step):
    """Rule 2 on `step`: the driven marker, separation and checker on it."""
    assert p["ok"], p["summary"]
    assert p["overflow_mm"] == 0.0
    assert on(p["marker_mm"], step), p["marker_mm"]
    if kind.startswith("grid"):
        assert on(p["separation_mm"], step), p["separation_mm"]
        assert p["separation_mm"] >= p["marker_mm"] / N - TOL
    if kind.startswith("charuco"):
        assert on(p["checker_mm"], step), p["checker_mm"]
        assert p["marker_mm"] <= p["checker_mm"] * N / (N + 2.0) + TOL


# ------------------------------------------------------------------ the resolver

def test_the_inkjet_built_ins_say_half_a_millimetre():
    out = W.presets()
    assert [p.get("size_step") for p in out] == [None, mm_step(0.5), mm_step(0.5)]
    # and it is what they derived before: rule 2 on 0.5 mm
    for p in out[1:]:
        assert W.cells_for({"preset": p, "marker": {}}) == W.cells_of({k: v for k, v in p.items() if k != "size_step"})


def test_the_step_resolves_marker_then_preset_then_cell_step():
    pre = stepped(INK, DOTS)
    assert W.size_step_of({"preset": pre, "marker": {"size_step": mm_step(1)}}) == mm_step(1)
    assert W.size_step_of({"preset": pre, "marker": {"size_step": None}}) == DOTS
    assert W.size_step_of({"preset": pre, "marker": {}}) == DOTS
    assert W.size_step_of({"preset": preset(cell_step_mm=0.042333), "marker": {}}) is None
    assert W.cells_for({"preset": pre, "marker": {}}) == {"rule": A.DOTS_RULE, "of": "cell", "mm": 25.4 / 600,
                                                          "min_mm": 1.0}
    for mm in (0.1, 0.5, 1):
        assert W.cells_for({"preset": pre, "marker": {"size_step": mm_step(mm)}}) == \
            {"rule": A.ROUND_RULE, "of": "marker", "mm": float(mm), "min_mm": 1.0}
    # "line": the old derivation, whatever it was
    for p in (INK, preset(cell_step_mm=0.042333), D3, D3_LINES):
        base = {k: v for k, v in p.items() if k != "size_step"}
        assert W.cells_for({"preset": p, "marker": {"size_step": {"of": "line"}}}) == W.cells_of(base)
    assert A.cells_of(W.cells_for({"preset": pre, "marker": {}})) == ("cell", 25.4 / 600 / 1000.0, 0.001, 3)


def test_a_step_that_cannot_be_used_is_said_and_the_next_one_used():
    r = {"w": 40.0, "h": 40.0}
    for bad in ({"of": "inches"}, mm_step(0), mm_step(50), mm_step("1"), "dots"):
        p = W.plan(req({"size_step": bad}, rect=r))
        said = [w for w in p["warnings"] if w["field"] == "marker.size_step"]
        assert len(said) == 1 and said[0]["level"] == "warn" and "preset's is used" in said[0]["text"], p["warnings"]
        assert p["marker_mm"] == 29.5                           # the preset's 0.5 mm
    p = W.plan(req({}, rect=r, pre=stepped(D3, DOTS)))           # dots on a 3D printer: no dpi
    assert any(w["field"] == "preset" and "dpi" in w["text"] for w in p["warnings"])
    assert p["marker_mm"] == W.plan(req({}, rect=r, pre=D3))["marker_mm"]


# ------------------------------------------------------------------ dots

@pytest.mark.parametrize("kind", list(TYPES))
@pytest.mark.parametrize("shape", SHAPES[::2], ids=[s[0] for s in SHAPES[::2]])
def test_dots_give_whole_dots_per_cell(kind, shape):
    check_dots(plan_with(shape, kind, pre=stepped(INK, DOTS)), kind, 600)


@pytest.mark.parametrize("dpi", [300, 1200, 720])
@pytest.mark.parametrize("kind", list(TYPES))
@pytest.mark.parametrize("shape", SHAPES[::8], ids=[s[0] for s in SHAPES[::8]])
def test_dots_at_other_resolutions(dpi, kind, shape):
    """720 dpi: 6 cells of whole dots are not a whole 0.1 um (25.4 / 720 x
    6 = 0.21167 mm), so the cell is whole dots to the core's quantum."""
    p = plan_with(shape, kind, pre=stepped(dict(A4, dpi=dpi), DOTS))
    check_dots(p, kind, dpi, exact=dpi != 720)


def test_dots_on_a_5x5_dictionary():
    for shape in SHAPES[:6]:
        p = plan_with(shape, "grid 2x2", pre=stepped(INK, DOTS), dictionary="DICT_5X5_50")
        check_dots(p, "grid 2x2", 600, n=7, exact=False)


def test_zachs_marker_is_dot_exact():
    """The Fusion panel's 27.9398 mm (6 cells x 110 dots under the rounded
    0.042333 mm dot) is 27.94 mm exactly under 25.4 / 600."""
    p = W.plan(req({"size_step": DOTS}, rect={"w": 37.3, "h": 37.3}))
    assert p["marker_mm"] == 27.94
    assert {"field": "marker.marker_mm", "level": "info",
            "text": "27.94 mm = 6 cells × 110 dots at 600 dpi, exact"} in p["warnings"]
    # in place of the core's cells line on the preset, never beside it
    assert not [w for w in p["warnings"] if w["field"] == "preset" and w["text"].startswith("cells ")]
    old = W.plan(req({}, rect={"w": 37.3, "h": 37.3}, pre=preset(cell_step_mm=0.042333)))
    assert old["marker_mm"] == 27.9398


# ------------------------------------------------------------------ mm

@pytest.mark.parametrize("mm", [0.1, 0.5, 1.0])
@pytest.mark.parametrize("kind", list(TYPES))
@pytest.mark.parametrize("shape", SHAPES[::4], ids=[s[0] for s in SHAPES[::4]])
def test_mm_steps_give_multiples(mm, kind, shape):
    p = plan_with(shape, kind, pre=stepped(INK, mm_step(mm)))
    check_mm(p, kind, mm)
    assert any("printer rounds by" in w["text"] for w in p["warnings"] if w["field"] == "marker.marker_mm")


def test_the_mm_note_is_todays_wording():
    p = W.plan(req({"size_step": mm_step(1)}, rect={"w": 40.0, "h": 40.0}))
    assert p["marker_mm"] == 29.0
    assert {"field": "marker.marker_mm", "level": "info",
            "text": "29.0 mm → cell 4.83 mm (114.2 dots); the printer rounds by ≤ 0.02 mm"} in p["warnings"]


# ------------------------------------------------------------------ the override

def check_override():
    """A marker's step wins over its preset's, both ways round."""
    for shape in SHAPES[:8]:
        for kind in ("grid 3x1", "charuco 5x4"):
            check_mm(plan_with(shape, kind, pre=stepped(INK, DOTS), marker_step=mm_step(1.0)), kind, 1.0)
            check_dots(plan_with(shape, kind, pre=stepped(INK, mm_step(1.0)), marker_step=DOTS), kind, 600)
            check_dots(plan_with(shape, kind, pre=stepped(INK, DOTS), marker_step=None), kind, 600)


def test_the_marker_step_wins_over_the_preset():
    check_override()


def test_without_the_marker_override_the_check_fails(monkeypatch):
    """The ruler can fail: size_step_of reading the preset only."""
    real = W.size_step_of

    def preset_only(r, issues=None):
        return real(dict(r, marker={k: v for k, v in (r.get("marker") or {}).items() if k != "size_step"}), issues)
    monkeypatch.setattr(W, "size_step_of", preset_only)
    with pytest.raises(AssertionError):
        check_override()


# ------------------------------------------------------------------ typed sizes

@pytest.mark.parametrize("step", [DOTS, mm_step(0.1), mm_step(0.5), mm_step(1.0)], ids=["dots", "0.1", "0.5", "1"])
def test_typed_sizes_are_exact(step):
    r = {"w": 120.0, "h": 45.0}
    grid = TYPES["grid 3x1"]
    single = W.plan(req({"auto": False, "marker_mm": 29.97, "size_step": step}, rect={"w": 60.0, "h": 60.0}))
    assert single["marker_mm"] == 29.97
    both = W.plan(req(dict(grid, auto=False, marker_mm=29.97, separation_mm=6.0113, size_step=step), rect=r))
    assert (both["marker_mm"], both["separation_mm"]) == (29.97, 6.0113)
    s = W.plan(req(dict(grid, separation_mm=6.0113, size_step=step), rect=r))
    assert s["separation_mm"] == 6.0113 and s["overflow_mm"] == 0.0
    board = {"w": 93.0, "h": 71.0}
    c = W.plan(req(dict(TYPES["charuco 5x4"], checker_mm=17.33, size_step=step), rect=board))
    assert c["ok"] and c["checker_mm"] == 17.33 and c["marker_mm"] <= 17.33 * N / (N + 2.0)
    t = W.plan(req(dict(TYPES["charuco 5x4"], auto=False, marker_mm=12.97, checker_mm=17.33, size_step=step),
                   rect=board))
    assert t["ok"] and (t["marker_mm"], t["checker_mm"]) == (12.97, 17.33)
    lone = W.plan(req(dict(TYPES["charuco 5x4"], auto=False, marker_mm=12.97, size_step=step), rect=board))
    assert lone["ok"] and lone["marker_mm"] == 12.97 and lone["checker_mm"] >= 12.97 * (N + 2.0) / N - TOL
    big = W.plan(req({"auto": False, "marker_mm": 29.97, "size_step": step}, rect={"w": 20.0, "h": 20.0}))
    assert big["marker_mm"] == 29.97 and big["overflow_mm"] > 0
    if step == DOTS:
        # the partner of a typed size is on the dots
        k = c["marker_mm"] / N / (25.4 / 600)
        assert abs(k - round(k)) <= TOL and any(w["text"].endswith(", exact") for w in c["warnings"])
        assert on(lone["checker_mm"], 25.4 / 600, QUANTUM_MM)
        # a typed size off the dots says what the printer does, not "exact"
        assert any(w["text"] == "29.97 mm → cell 5.00 mm (118.0 dots); the printer rounds by ≤ 0.02 mm"
                   for w in single["warnings"])


def test_the_cell_step_dots_still_snap_a_typed_size():
    """Rule 1 (a preset's cell_step_mm) is unchanged: it snaps a typed size,
    which rule 3 does not -- the same check fails there."""
    p = W.plan(req({"auto": False, "marker_mm": 29.97}, rect={"w": 60.0, "h": 60.0},
                   pre=preset(cell_step_mm=round(25.4 / 600, 6))))
    assert p["marker_mm"] == 29.7178


# ------------------------------------------------------------------ unchanged

def flavours():
    """parity_cases() as test_web_profile_first builds them (the dots presets
    the pins there are taken under), and the same cases on today's inkjet
    built-ins: every request without a size_step."""
    dots = parity_cases()
    d3, letter, a4 = W.presets()
    today = []
    swap = {}
    for p in (letter, a4):
        q = copy.deepcopy(p)
        q.pop("size_step", None)
        swap[json.dumps(dict(q, cell_step_mm=0.042333), sort_keys=True)] = q
    for name, call, payload in dots:
        text = json.dumps(payload, sort_keys=True)
        for k, q in swap.items():
            text = text.replace(k, json.dumps(q, sort_keys=True))
        today.append((f"today: {name}", call, json.loads(text)))
    return dots + today


def digests(cases):
    out = {}
    for name, call, payload in cases:
        if call == "presets":
            continue                                       # it says the new field (test_web_round)
        out[name] = hashlib.sha256(W.call(call, json.dumps(payload)).encode()).hexdigest()
    return out


def test_without_a_size_step_every_answer_is_main_byte_for_byte():
    cases = flavours()
    assert len(cases) == 38
    for name, _call, payload in cases:
        assert "size_step" not in json.dumps(payload), name
    assert hashlib.sha256(json.dumps(digests(cases), sort_keys=True).encode()).hexdigest() == MAIN_1EA2540


def test_the_built_ins_explicit_half_millimetre_answers_the_same():
    """Today's cases with the built-ins as presets() gives them (size_step
    {mm: 0.5} said) answer what they answered with it derived."""
    d3, letter, a4 = W.presets()
    plain = [c for c in flavours() if c[0].startswith("today: ")]
    said = []
    for name, call, payload in plain:
        text = json.dumps(payload, sort_keys=True)
        for p in (letter, a4):
            q = {k: v for k, v in p.items() if k != "size_step"}
            text = text.replace(json.dumps(q, sort_keys=True), json.dumps(p, sort_keys=True))
        said.append((name, call, json.loads(text)))
    assert sum("size_step" in json.dumps(c[2]) for c in said) == 13      # every inkjet case
    assert digests(said) == digests(plain)


def test_3d_is_unchanged_and_its_line_is_the_line():
    """test_web_round's 38 3D cases (pinned there), and the same with
    size_step {of: line} on the preset and on the marker: identical."""
    base = d3_cases()
    lined = []
    for name, call, payload in base:
        q = copy.deepcopy(payload)
        q["preset"]["size_step"] = {"of": "line"}
        q["marker"]["size_step"] = {"of": "line"}
        lined.append((name, call, q))
    assert digests(lined) == digests(base)


# sha256 of digests(flavours()) at main 1ea2540 (contract barrier 11, before this lane)
MAIN_1EA2540 = "d246b4a6b06d585f7f99c028ada96ba0629ce0fa069f4f050b864e37f2c7f33c"
