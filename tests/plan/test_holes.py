"""M6a.3: Holes: avoid / ignore (`settings.holes`; absent = avoid).

* `avoid` is today's plan byte for byte: the 824 evaluate() goldens replay
  with `holes` absent (tests/plan/test_golden_evaluate.py) AND with
  `holes: avoid` (here), and plan_tag gives the same JSON either way;
* `ignore` fits on the outer loop only: on every palette face with holes the
  marker is at least avoid's, and bigger where a hole was in the way;
* a marker crossing a hole under `ignore` carries a `warn` on settings.holes;
* junk reads as avoid with a `warn`.
"""
from __future__ import annotations

import copy

import pytest

import _evaluate_golden as G
from aruco_studio.core import faces as FA
from aruco_studio.plan import plan_tag
from aruco_studio.plan import target as T
from aruco_studio.plan.spec import TagSpec

CASES = G.cases("legacy") + G.cases("matrix")
CHUNKS = 16


def _strict_replay(case, s):
    got, _ev = G.run_ref_inputs(dict(case, s=s))
    want = case["out"]
    if "settled" in got:                       # settle() hands the stored key back
        assert got["settled"]["settings"].pop("holes") == "avoid"
    if "error" in want or "error" in got:
        return "" if want.get("error") == got.get("error") else "error differs"
    return G.diff(G.norm(got), {k: want[k] for k in got})


@pytest.mark.parametrize("chunk", range(CHUNKS))
def test_holes_avoid_replays_the_evaluate_goldens(chunk):
    """REF's exact evaluate() inputs with "holes": "avoid" added: every
    output as REF recorded it (824 cases over the chunks)."""
    bad = []
    for c in CASES[chunk::CHUNKS]:
        d = _strict_replay(c, dict(c["s"], holes="avoid"))
        if d:
            bad.append((c["id"], d))
    assert not bad, bad[:3]


def test_the_goldens_are_all_here():
    assert len(CASES) == 824


@pytest.mark.parametrize("chunk", range(CHUNKS))
def test_holes_avoid_is_the_same_plan(chunk):
    bad = []
    for c in CASES[chunk::CHUNKS]:
        spec = TagSpec.from_dict(c["in"])
        a = plan_tag(spec).to_json()
        sp = copy.deepcopy(spec)
        sp.settings["holes"] = "avoid"
        if plan_tag(sp).to_json() != a:
            bad.append(c["id"])
    assert not bad, bad[:5]


HOLED = [f["key"] for f in FA.PALETTE if f["holes"]]


def _plan(key, holes=None, layout="single", **kw):
    s = {"layout": layout, "mode": "both", "op": "new", **kw}
    if holes is not None:
        s["holes"] = holes
    return plan_tag({"settings": s, "target": T.from_face(key).to_dict()})


def test_the_palette_faces_with_holes():
    assert HOLED == ["disc4", "plate_hole", "ring"]


@pytest.mark.parametrize("key", HOLED)
@pytest.mark.parametrize("layout", ["single", "charuco"])
def test_ignore_gives_a_marker_at_least_avoids(key, layout):
    a, i = _plan(key, "avoid", layout), _plan(key, "ignore", layout)
    assert i.ok, i.data["errors"]
    if not a.ok:                               # nothing fits between the holes: ignore fits
        return
    am, im = a.data["layout"]["marker_mm"], i.data["layout"]["marker_mm"]
    if layout == "charuco":
        am, im = (a.data["layout"]["square_mm"] * a.data["layout"]["cols"]
                  * a.data["layout"]["rows"], i.data["layout"]["square_mm"]
                  * i.data["layout"]["cols"] * i.data["layout"]["rows"])
    assert im >= am - 1e-9, (key, layout, am, im)


def test_ignore_grows_the_marker_over_the_plate_hole():
    a, i = _plan("plate_hole", "avoid"), _plan("plate_hole", "ignore")
    assert i.data["layout"]["marker_mm"] > a.data["layout"]["marker_mm"] + 5.0
    assert i.data["guides"]["target_ignored"] and not a.data["guides"]["target_ignored"]
    w = [x for x in i.data["warnings"] if x["field"] == "settings.holes"]
    assert w and w[0]["level"] == "warn" and "covers 1 hole" in w[0]["text"], w
    assert not [x for x in a.data["warnings"] if x["field"] == "settings.holes"]


def test_a_sticker_crossing_a_hole_warns_per_hole():
    i = _plan("plate_hole", "ignore", make={"rule": 1, "by": "sticker"})
    w = [x for x in i.data["warnings"] if x["field"] == "settings.holes"]
    assert w and w[0]["level"] == "warn"
    assert w[0]["text"].startswith("the marker crosses hole 1: cut the hole out after sticking")


def test_ignore_reads_the_outer_loop_for_the_label_white():
    """A label on the white may sit over a hole under ignore (the region is
    the outer loop), never under avoid."""
    lab = {"on": True, "rule": 3, "place": "white", "content": "name", "nozzle_mm": 0.4}
    a = _plan("ring", "avoid", label=lab)
    i = _plan("ring", "ignore", label=lab)
    assert a.ok and i.ok


def test_junk_reads_as_avoid_with_a_warn():
    j, a = _plan("plate_hole", "maybe"), _plan("plate_hole", "avoid")
    w = [x for x in j.data["warnings"] if x["field"] == "settings.holes"]
    assert w and w[0]["level"] == "warn" and "read as avoid" in w[0]["text"]
    jd, ad = j.to_dict(), a.to_dict()
    jd.pop("warnings")
    ad.pop("warnings")
    assert jd == ad


def test_the_trim_still_reads_every_loop():
    """Trim excess refuses to cut through a hole under ignore as under avoid."""
    t = {"rule": 1, "axes": "both", "margin_mm": 0.0}
    for h in ("avoid", "ignore"):
        p = plan_tag({"settings": {"layout": "single", "mode": "both", "op": "join", "holes": h,
                                   "trim": t},
                      "target": T.from_face("plate_hole", 3.0).to_dict()})
        assert p.ok
        assert p.data["trim"] is not None and "holes" in p.data["trim"]
