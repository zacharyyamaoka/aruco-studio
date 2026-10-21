"""Profile first (contract barrier 9, Zach 2026-10-20 evening: "go back to just
profile ... behaving more like an extrude"): a PlanRequest with a profile and
no rect has its marker placed by the core -- the profile itself when it is a
rectangle (rotated too: the custom placement), else the largest clear box in
it (web_api.inscribe, holes "avoid" or "ignore") -- returned as
MarkerPlan.fit_rect. Trim is "profile" (default) or "marker"; "rectangle"
reads as "profile", said on "trim". A request with a rect plans exactly as
before (Fusion, old callers)."""
from __future__ import annotations

import base64
import hashlib
import json
import math

import pytest

from aruco_studio import web_api as W
from aruco_studio.core import autosize as A

from test_web_api import box, req

TOL = 1e-6
KEYS = ("cx", "cy", "w", "h", "angle_deg")


def disc(cx, cy, r, n=72):
    """A clockwise circle (a hole)."""
    return [[cx + r * math.cos(-2 * math.pi * k / n), cy + r * math.sin(-2 * math.pi * k / n)]
            for k in range(n)]


def corners(rect):
    """The rectangle's 4 corners, counter-clockwise from (-w/2, -h/2): the
    UI's geom.rectCorners."""
    c, s = math.cos(math.radians(rect["angle_deg"])), math.sin(math.radians(rect["angle_deg"]))
    out = []
    for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        u, v = u * rect["w"] / 2.0, v * rect["h"] / 2.0
        out.append([rect["cx"] + c * u - s * v, rect["cy"] + s * u + c * v])
    return out


PLATE = {"loops": [[[-60.0, -40.0], [60.0, -40.0], [60.0, 40.0], [-60.0, 40.0]],
                   disc(-35.0, 0.0, 10.0), disc(35.0, 0.0, 10.0)]}
TURNED = {"cx": 5.0, "cy": 3.0, "w": 30.0, "h": 20.0, "angle_deg": 30.0}


def profiled(profile=PLATE, holes=None, trim=None, marker=None, label=None, pre=None):
    """A profile-only request: no rect."""
    r = req(marker, label=label, pre=pre)
    del r["rect"]
    r["profile"] = profile
    if holes is not None:
        r["holes"] = holes
    if trim is not None:
        r["trim"] = trim
    return r


def issues(p, field, level):
    return [w for w in p["warnings"] if w["field"] == field and w["level"] == level]


def in_rect(rect, pts, tol=TOL):
    """Every sketch point inside the rect (its own frame)."""
    (lp,) = W.to_rect(rect, [pts])
    return all(abs(u) <= rect["w"] / 2.0 + tol and abs(v) <= rect["h"] / 2.0 + tol for u, v in lp)


def clear_in(rect, profile, holes):
    """The rect lies in the profile (outer loop only for holes "ignore"),
    touching allowed (autosize._rect_inside, exact)."""
    loops = profile["loops"][:1] if holes == "ignore" else profile["loops"]
    loops = [lp if (W._area2(lp) > 0) == (k == 0) else lp[::-1] for k, lp in enumerate(loops)]
    return A._rect_inside(W.to_rect(rect, loops), 0.0, 0.0, rect["w"], rect["h"], TOL)


# ------------------------------------------------------------------ the fit

def test_a_plate_with_holes_fits_a_clear_box():
    got = {}
    for holes in ("avoid", "ignore"):
        p = W.plan(profiled(holes=holes))
        assert p["ok"]
        fit = p["fit_rect"]
        assert fit == W.inscribe(PLATE, holes)     # inscribe's: exact rectangle fix, 0.1 mm snap
        assert clear_in(fit, PLATE, holes)
        assert all(abs(fit[k] * 10.0 - round(fit[k] * 10.0)) < 1e-6 for k in ("w", "h"))
        # the marker (its quiet-zone edge) and its black sit in the box
        assert in_rect(fit, p["outer"]) and p["overflow_mm"] == 0.0
        assert all(in_rect(fit, poly["outer"]) for poly in p["black"])
        got[holes] = fit
    assert not clear_in(got["ignore"], PLATE, "avoid")             # it runs over the holes
    assert got["ignore"]["w"] * got["ignore"]["h"] > got["avoid"]["w"] * got["avoid"]["h"]
    assert W.plan(profiled()) == W.plan(profiled(holes="avoid"))   # "avoid" is the default


def test_a_fitted_plan_is_the_rect_plan_in_that_box():
    """Planned exactly as the rect path plans: the same request with
    rect = fit_rect gives the same plan (label band, auto size, dims,
    overflow all measured against the box)."""
    for label in ({"on": False}, {"on": True, "text": "#{id}"},
                  {"on": True, "text": "#{id}", "place": "outside"}):
        for marker in (None, {"type": "grid", "cols": 3, "rows": 2},
                       {"auto": False, "marker_mm": 70.0}):
            r = profiled(label=label, marker=marker)
            p = W.plan(r)
            assert p == W.plan(dict(r, rect=p["fit_rect"]))
            assert W.svg(r) == W.svg(dict(r, rect=p["fit_rect"]))
    big = W.plan(profiled(marker={"auto": False, "marker_mm": 70.0}))
    assert big["overflow_mm"] > 0 and [w for w in big["warnings"] if w["level"] == "error"]


@pytest.mark.parametrize("rect", [TURNED, dict(TURNED, angle_deg=120.0), dict(TURNED, angle_deg=-170.0),
                                  {"cx": -4.0, "cy": 7.5, "w": 33.3, "h": 21.7, "angle_deg": 0.0},
                                  {"cx": 0.0, "cy": 0.0, "w": 25.0, "h": 40.0, "angle_deg": 90.0}],
                         ids=["30", "120", "-170", "0", "90"])
def test_a_rectangle_profile_is_used_exactly(rect):
    p = W.plan(profiled({"loops": [corners(rect)]}))
    assert p["ok"]
    assert [p["fit_rect"][k] for k in KEYS] == pytest.approx([rect[k] for k in KEYS], abs=TOL)
    assert in_rect(p["fit_rect"], p["outer"])
    # holes "ignore" is the same box: there are none
    assert W.plan(profiled({"loops": [corners(rect)]}, holes="ignore"))["fit_rect"] == p["fit_rect"]


def test_a_rectangle_profile_with_points_along_its_edges_is_still_the_rectangle():
    c = corners(TURNED)
    mid = lambda a, b, t: [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]
    # starting part way along its first edge, extra points on two edges, a repeated point
    loop = [mid(c[0], c[1], 0.25), c[1], mid(c[1], c[2], 0.5), c[2], c[3], c[3],
            mid(c[3], c[0], 0.3), c[0]]
    fit = W.plan(profiled({"loops": [loop]}))["fit_rect"]
    assert [fit[k] for k in KEYS] == pytest.approx([TURNED[k] for k in KEYS], abs=TOL)


def test_a_rectangle_with_a_hole_is_searched_unless_holes_are_ignored():
    rect = {"cx": 0.0, "cy": 0.0, "w": 120.0, "h": 80.0, "angle_deg": 0.0}
    prof = {"loops": [corners(rect), disc(35.0, 0.0, 10.0)]}
    avoid = W.plan(profiled(prof))["fit_rect"]
    assert clear_in(avoid, prof, "avoid") and avoid["w"] < 120.0
    assert W.plan(profiled(prof, holes="ignore"))["fit_rect"] == rect


@pytest.mark.parametrize("loop", [
    [[0.0, 0.0], [40.0, 0.0], [40.0, 30.0], [0.0, 31.0]],                 # not a right angle
    [[0.0, 0.0], [40.0, 0.0], [40.0, 20.0], [20.0, 20.0], [20.0, 40.0], [0.0, 40.0]],  # an L
], ids=["skewed", "L"])
def test_a_near_rectangle_is_searched_not_taken(loop):
    fit = W.plan(profiled({"loops": [loop]}))["fit_rect"]
    assert fit == W.inscribe({"loops": [loop]}, "avoid")
    assert clear_in(fit, {"loops": [loop]}, "avoid")


def test_a_rect_request_returns_its_rect():
    r = req(rect=TURNED)
    assert W.plan(r)["fit_rect"] == TURNED
    r = dict(req(rect=TURNED), profile=PLATE)       # a rect wins over the profile
    assert W.plan(r)["fit_rect"] == TURNED


# ------------------------------------------------------------------ nothing fits

@pytest.mark.parametrize("prof", [
    {"loops": [[[0.0, 0.0], [0.05, 0.0], [0.0, 0.05]]]},                    # too small
    {"loops": [[[0.0, 0.0], [40.0, 0.0], [20.0, 30.0]], [[20.0, 30.0], [40.0, 0.0], [0.0, 0.0]]]},  # all hole
    {"loops": [[[0.0, 0.0], [1.0, 1.0]]]},                                 # no loop
], ids=["tiny", "all-hole", "no-loop"])
def test_no_clear_box_is_refused_in_words(prof):
    r = profiled(prof)
    p = W.plan(r)
    assert p["ok"] is False and "fit_rect" not in p
    (e,) = issues(p, "tag", "error")
    assert e["text"].startswith("no clear box for the marker in the profile")
    assert p["summary"] == e["text"]
    assert "result" in json.loads(W.call("plan", json.dumps(r)))           # never raised
    assert W.suggest(r) == []
    assert "nothing to draw: no clear box" in json.loads(W.call("svg", json.dumps(r)))["error"]
    got = W.sheet({"items": [r, req()], "cut_lines": True}, "2026-10-20")
    assert [q["item"] for q in got["placements"]] == [1]
    assert any(w["text"].startswith("item 1 is not printed: no clear box") for w in got["warnings"])


# ------------------------------------------------------------------ the trim

def test_trim_profile_cuts_the_plates_loops():
    p = W.plan(profiled())
    cut = p["cut_shape"]
    assert cut["outer"] == PLATE["loops"][0] and p["cut"] == cut["outer"]
    assert cut["holes"] == [[[W._r(u), W._r(v)] for u, v in hl] for hl in PLATE["loops"][1:]]
    assert W.plan(profiled(trim="profile")) == p
    (paper,) = [L for L in p["layers"] if L["part"] == "sticker"]
    assert paper["polygons"] == [cut]
    assert not issues(p, "rect", "warn")          # a fitted box is inside: never "pokes out"


def test_trim_marker_cuts_the_quiet_zone():
    p = W.plan(profiled(trim="marker"))
    assert p["cut_shape"] == {"outer": p["outer"], "holes": []}
    assert (p["black"], p["outer"], p["fit_rect"]) == (lambda q: (q["black"], q["outer"], q["fit_rect"]))(
        W.plan(profiled()))


def test_a_rectangle_profile_trimmed_to_profile_is_the_rectangle():
    p = W.plan(profiled({"loops": [corners(TURNED)]}))
    assert p["cut_shape"]["holes"] == []
    assert p["cut"] == [[W._r(u), W._r(v)] for u, v in corners(TURNED)]


def test_trim_rectangle_reads_as_profile_said_on_trim():
    words = "trim to rectangle is now trim to profile; draw a rectangle profile"
    for r in (profiled(), dict(req(rect={"w": 40.0, "h": 40.0}), profile=PLATE),
              req(rect={"w": 40.0, "h": 40.0})):
        p = W.plan(dict(r, trim="profile"))
        q = W.plan(dict(r, trim="rectangle"))
        assert issues(q, "trim", "info") == [{"field": "trim", "level": "info", "text": words}]
        assert not issues(p, "trim", "info")
        assert dict(q, warnings=[w for w in q["warnings"] if w["field"] != "trim"]) == p
    # with a profile, "rectangle" no longer cuts to the rect: to the profile
    q = W.plan(dict(req(rect={"w": 40.0, "h": 40.0}), profile=PLATE, trim="rectangle"))
    assert len(q["cut_shape"]["holes"]) == 2


# ------------------------------------------------------------------ the other calls

def test_svg_sheet_suggest_and_readable_from_a_profile():
    for r in (profiled(label={"on": True, "text": "#{id}"}),
              profiled({"loops": [corners(TURNED)]}, marker={"type": "grid", "cols": 2, "rows": 1})):
        fit = W.plan(r)["fit_rect"]
        boxed = dict(r, rect=fit)
        assert W.svg(r) == W.svg(boxed) and W.svg(r).startswith("<svg")
        assert W.suggest(r) == W.suggest(boxed) and W.suggest(r)
        got = W.sheet({"items": [r], "cut_lines": True}, "2026-10-20")
        assert got == W.sheet({"items": [boxed], "cut_lines": True}, "2026-10-20")
        assert got["pages"] == 1 and len(got["placements"]) == 1
        assert base64.b64decode(got["pdf_base64"]).startswith(b"%PDF")
        assert not [w for w in got["warnings"] if w["level"] == "error"]
        from aruco_studio import web_verify as V
        cam = {"distance_mm": 300.0, "resolution": [1280, 720], "hfov_deg": 60.0}
        assert V.readable_analytic(r, cam) == V.readable_analytic(boxed, cam)
    assert W.sticker_parts(W.placed_in(profiled())[0])["cut"]["holes"]


def test_verify_from_a_profile():
    pytest.importorskip("cv2")
    from aruco_studio import web_verify as V
    view = {"camera": {"distance_mm": 250.0, "resolution": [1280, 720], "hfov_deg": 60.0},
            "tilt_deg": 0.0, "yaw_deg": 0.0, "blur_px": 0.0, "noise": 0.0, "glare": 0.0,
            "occlusion": 0.0, "seed": 1}
    r = profiled(label={"on": True, "text": "#{id}"})
    got = V.verify(r, view)
    assert got["ok"] and got["found"] == [0]
    assert got == V.verify(dict(r, rect=W.plan(r)["fit_rect"]), view)
    out = json.loads(W.call("readable", json.dumps({"req": r, "camera": view["camera"]})))
    assert out["result"]["max_distance_mm"] > 0
    bad = json.loads(W.call("verify", json.dumps({"req": profiled({"loops": [[[0, 0], [0.05, 0], [0, 0.05]]]}),
                                                   "view": view})))
    assert "nothing to verify: no clear box" in bad["error"]


# ------------------------------------------------------------------ rect requests are today's

def parity_cases():
    """web/scripts/parity.mjs's own cases (the rect-only facade, at main
    5164a79), built as that script builds them -- the inkjet presets with
    the whole 600 dpi dots they had then (cells rule 2, 2026-10-20 night,
    made them the marker in 0.5 mm steps: tests/web/test_web_round.py), so
    every pin below still says "byte for byte as before"."""
    d3, letter, a4 = json.loads(W.call("presets", "{}"))["result"]
    letter, a4 = dict(letter, cell_step_mm=0.042333), dict(a4, cell_step_mm=0.042333)
    for p in (letter, a4):
        p.pop("size_step", None)            # barrier 11: absent = derived from cell_step_mm

    def marker(**m):
        return dict({"type": "single", "dictionary": "DICT_4X4_50", "first_id": 0, "auto": True,
                     "marker_mm": 0, "checker_mm": 0, "separation_mm": 0, "cols": 1, "rows": 1,
                     "turn": 0, "flip": False, "quiet_modules": 1, "corner_mark": "none"}, **m)

    def rq(m=None, r=None, lb=None, preset=letter, face=False):
        return {"rect": dict({"cx": 0, "cy": 0, "w": 60, "h": 40, "angle_deg": 0}, **(r or {})),
                "marker": marker(**(m or {})),
                "label": dict({"on": False, "text": "", "height_mm": 0, "side": "below", "gap_mm": 2,
                               "offset_mm": [0, 0]}, **(lb or {})),
                "preset": preset, "reference_face": face}
    plate = {"loops": [[[-60, -40], [60, -40], [60, 40], [-60, 40]],
                       [[-35 + 10 * math.cos(-2 * math.pi * k / 72), 10 * math.sin(-2 * math.pi * k / 72)]
                        for k in range(72)],
                       [[35 + 10 * math.cos(-2 * math.pi * k / 72), 10 * math.sin(-2 * math.pi * k / 72)]
                        for k in range(72)]]}
    return [
        ("presets", "presets", {}),
        ("plan single auto", "plan", rq(None, {"w": 20, "h": 20})),
        ("plan overflow", "plan", rq({"auto": False, "marker_mm": 30}, {"w": 20, "h": 20})),
        ("plan grid 3x2 auto", "plan", rq({"type": "grid", "cols": 3, "rows": 2})),
        ("plan grid 2x1 manual", "plan", rq({"type": "grid", "cols": 2, "rows": 1, "auto": False,
                                             "marker_mm": 10, "separation_mm": 5})),
        ("plan grid turn 90", "plan", rq({"type": "grid", "cols": 3, "rows": 2, "auto": False,
                                          "marker_mm": 12, "turn": 90},
                                         {"cx": 15, "cy": -8, "angle_deg": 30})),
        ("plan charuco 5x4 auto", "plan", rq({"type": "charuco", "cols": 5, "rows": 4}, {"w": 80, "h": 60})),
        ("plan charuco 9 / 13", "plan", rq({"type": "charuco", "cols": 4, "rows": 3, "auto": False,
                                            "marker_mm": 9, "checker_mm": 13}, {"w": 80, "h": 60})),
        ("plan charuco 10 / 13 refused", "plan", rq({"type": "charuco", "cols": 4, "rows": 3, "auto": False,
                                                     "marker_mm": 10, "checker_mm": 13}, {"w": 80, "h": 60})),
        ("plan flip + corner + label", "plan", rq({"flip": True, "first_id": 7, "corner_mark": "triangle"},
                                                  {"w": 60, "h": 40, "angle_deg": 12.5},
                                                  {"on": True, "text": "#{id}\n{dict}", "side": "right"})),
        ("plan grid on a face, 3D", "plan", rq({"type": "grid", "cols": 2, "rows": 2}, {"w": 50, "h": 50},
                                               None, d3, True)),
        ("plan refused 100 markers", "plan", rq({"type": "grid", "cols": 10, "rows": 10},
                                                {"w": 200, "h": 200}, None, a4)),
        ("inscribe avoid", "inscribe", {"profile": plate, "holes": "avoid"}),
        ("inscribe ignore", "inscribe", {"profile": plate, "holes": "ignore"}),
        ("suggest grid", "suggest", rq({"type": "grid"})),
        ("suggest charuco, 3D lines", "suggest", rq({"type": "charuco"}, {"w": 80, "h": 60}, None,
                                                   dict(d3, cell_step_mm=0.675))),
        ("svg single with label", "svg", rq({"auto": False, "marker_mm": 15}, {"w": 20, "h": 20},
                                            {"on": True, "text": "#{id} {dict}"})),
        ("sheet letter, 3 items", "sheet", {"items": [
            rq(None, {"w": 20, "h": 20}, {"on": True, "text": "part {id}"}),
            rq({"type": "grid", "cols": 3, "rows": 2, "first_id": 10}),
            rq({"auto": False, "marker_mm": 300}, {"w": 300, "h": 300})],
            "cut_lines": True, "date": "2026-10-18"}),
        ("bad request", "plan", {}),
    ]


# sha256 of each case's call() JSON at main 5164a79 (before barrier 9's
# profile-first core), a plan's fit_rect left out: the one field it adds
TODAYS = {
    # cells rule 2 (2026-10-20 night): the inkjet built-ins cell_step_mm 0.042333 -> 0, nothing
    # else (dd7c0cf2... with that one field set back: tests/web/test_web_round.py); barrier 11
    # added their size_step {"of": "mm", "mm": 0.5}, nothing else (the same test takes it off)
    "presets": "2322da24a4ad861ed2374617f27bb49da3f7217493e7391a1e336970036a9428",
    "plan single auto": "22474e1daf30a3d03568720eb4fad64ba84254a8d8b9f8705e44c51e111e8c80",
    "plan overflow": "50c34ea6027f933690d200b86ef779fa003152541738de278219a55ffb1d8767",
    "plan grid 3x2 auto": "a6835d762498caa24db802a56cd79386370a48b87207a98a3c21b624fa28f4a9",
    "plan grid 2x1 manual": "cca9de79ae57891a181b7e1f273a73030279f877f6c955774c6d0da300d21add",
    "plan grid turn 90": "9b67a8425db5045e995435d02e4da5e8d389741a0ec16933e87c82bb8f8b6c99",
    "plan charuco 5x4 auto": "4ea6cbb5dc59ac47a86589c26486f6ccba10db29a1971dc931643f8b2cef3468",
    "plan charuco 9 / 13": "70f3091bd79ad42aff082561524a889c7dac825e50c62703deb628a00fa8e7bb",
    "plan charuco 10 / 13 refused": "3399dd2e2ecb823f3060315b6e6113db448228ae14c260629dd8833d422c8977",
    "plan flip + corner + label": "e704a527e5f8b3c690024a25a08c8d160c3fe9db4d21ae9ef9387aa2f0b00042",
    "plan grid on a face, 3D": "573fcc01d04a29404cfbc77192d3d80f6755ecd423d348e79a33a607e5ca4c6a",
    "plan refused 100 markers": "0a754321cd2aba05c63bde26569fa442b11a3fd4f69ab01c1b01452be52661d0",
    "inscribe avoid": "2872b929d055d95952d5f503de788e119cca0fe677322d876892bcdacff2045d",
    "inscribe ignore": "ff05193f6b0015b86548896b5f9e5ca00c4aa9dd122a7fcca1844220f3c1085c",
    "suggest grid": "6502143650f8ff288fd1fc62c564ee5eca7276a4bcf08ab1aa9761d6d9310915",
    "suggest charuco, 3D lines": "8a3128d3b753215543840bf9839ceaefc26a5394911ff53f0dabdb3034bca626",
    "svg single with label": "27f0e68bd705d93f1b50174eee1c65d898c58936fb63f55de2b4fc9d699a8eb4",
    "sheet letter, 3 items": "629e237732d3dec62b9addb1b696c6c0f7056442203f25c3ce7024e520051a91",
    "bad request": "8e6d901213f7b7338b700624b3727ea41595064d9871a074889a7cb3f6be97f3",
}


def test_rect_requests_are_byte_identical_to_before():
    got = {}
    for name, call, payload in parity_cases():
        out = json.loads(W.call(call, json.dumps(payload)))
        if isinstance(out.get("result"), dict):
            fit = out["result"].pop("fit_rect", None)
            if call == "plan" and out["result"]["ok"]:
                assert fit == {k: float(payload["rect"][k]) for k in KEYS}
        text = json.dumps(out, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        got[name] = hashlib.sha256(text.encode()).hexdigest()
    assert got == TODAYS
