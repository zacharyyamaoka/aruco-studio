"""M8c.7: the slice checked against the plan (verify/slice_check.py, M8 note
5.7 steps 2-7), HEADLESS, on the plate and the forearm with the fixture
chain (the MK4 MMU3 0.6 user printer preset, `0.32mm SPEED @MK4IS 0.6 -
Aruco`, Prusament PLA @PGIS 0.6).

The console runs with --datadir pointing at a scratch folder that holds
copies of the needed presets with every private key stripped
(store.read_prusa_file); Zach's datadir is never read. Skipped, with the
reason, when prusa-slicer-console is not on the machine. The unit tests of
the oracle (G-code parsing, rasters) run everywhere.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest

from aruco_studio.core import beds as BD
from aruco_studio.core import label as L
from aruco_studio.core import presets as P
from aruco_studio.core import prusa as PR
from aruco_studio.plan import plan_tag
from aruco_studio.scene import design as DS
from aruco_studio.scene import print3d as P3
from aruco_studio.server import beds_io as BI
from aruco_studio.server import store as S
from aruco_studio.verify import slice_check as SC

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "prusaslicer_m8c"
EX = ROOT / "examples"
MK4_06 = "Original Prusa MK4 MMU3 0.6 nozzle - (Black, Clear, White)"
PRINT = "0.32mm SPEED @MK4IS 0.6 - Aruco"
CONSOLE = SC.find_console()
NEEDS = pytest.mark.skipif(CONSOLE is None, reason="prusa-slicer-console is not on this machine: "
                                                    "the slice check is skipped, not failed")
REPORTS = {}


# ------------------------------------------------------------------ the oracle alone

def test_parse_gcode_layers_tools_widths(tmp_path):
    g = tmp_path / "x.gcode"
    g.write_text("\n".join([
        ";LAYER_CHANGE", ";Z:0.2", ";HEIGHT:0.2", "T0", ";TYPE:External perimeter",
        ";WIDTH:0.68", "G1 X10 Y10", "G1 X20 Y10 E1.0", "G1 X20 Y20 E0.5",
        ";LAYER_CHANGE", ";Z:0.52", ";HEIGHT:0.32", "T1", ";TYPE:Solid infill", ";WIDTH:0.7",
        "G1 X10 Y10", "G1 X15 Y10 E0.2", ";TYPE:Wipe tower", "G1 X30 Y30 E1", ""]),
        encoding="utf-8")
    n, layers = SC.parse_gcode(str(g))
    assert n == 2 and [L["z"] for L in layers] == [0.2, 0.52]
    assert layers[0]["segs"][0] == (1, "External perimeter", 0.68, 10.0, 10.0, 20.0, 10.0)
    assert layers[1]["segs"] == [(2, "Solid infill", 0.7, 10.0, 10.0, 15.0, 10.0)]  # no tower
    assert SC.expected_layers(5.0, 0.32, 0.2) == 16
    assert SC.expected_layers(40.0, 0.32, 0.2) == 125


def test_grid_fill_capsule_and_iou():
    g = SC.Grid(0, 0, 10, 10, res=0.04)
    sq = g.polygons([[[(1, 1), (9, 1), (9, 9), (1, 9)], [(4, 4), (4, 6), (6, 6), (6, 4)]]])
    assert abs(sq.sum() * 0.04 ** 2 - (64 - 4)) < 0.2
    cap = g.empty()
    g.capsule(cap, 2, 5, 8, 5, 0.5)
    # within half a pixel all round (a tie on the edge is in): 14 mm of edge x 0.02 mm
    assert abs(cap.sum() * 0.04 ** 2 - (6 * 1.0 + math.pi * 0.25)) < 0.3
    assert SC.iou(sq, sq) == 1.0 and SC.iou(sq, np.zeros_like(sq)) == 0.0
    band = g.empty()
    g.band(band, 2, 4, 1, 3)
    assert abs(band.sum() * 0.04 ** 2 - 4.0) < 0.2


# ------------------------------------------------------------------ the slice

def _texts(sub):
    return {f.stem: f.read_text(encoding="utf-8") for f in sorted((FIX / sub).glob("*.ini"))}


@pytest.fixture(scope="module")
def chain():
    src = PR.sources_from_texts(_texts("print"), list(_texts("vendor").values()),
                                printer_texts=_texts("printer"),
                                physical_texts=_texts("physical_printer"),
                                ini_text=(FIX / "PrusaSlicer.ini").read_text(encoding="utf-8"))
    bundle, _ok = S.read_prusa_file(FIX / "vendor" / "PrusaResearch.ini", "vendor")
    pr = dict(PR.printer_of(MK4_06, src), physical="")
    fil = BI.filament_for(pr, src, bundle)
    prof = BI.chain_profile(src, MK4_06, PRINT, fil, bundle)
    pp = PR.pair_profile(PRINT, pr, src)
    presets = {n: p for n, p, _k in P.catalog_all(P.MemoryStore(), src)["items"]}
    # the scratch datadir's copies: the presets this chain needs, private keys stripped
    copies = {}
    for rel, kind in ((f"printer/{MK4_06}.ini", "printer"), (f"print/{PRINT}.ini", "print"),
                      ("vendor/PrusaResearch.ini", "vendor")):
        text, ok = S.read_prusa_file(FIX / rel, kind)
        assert ok
        copies[rel] = text
    return {"src": src, "profile": prof, "pp": pp, "presets": presets, "copies": copies,
            "filament": fil}


def sliced(name, chain, tmp_path, rule=None, **extra):
    """The example `name` with `extra` on its ArUco features, sliced and
    checked. `rule`: the label rule its tags are planned under (a new tag
    stores label.NEW_RULE; an older tag keeps its own)."""
    doc = json.loads((EX / f"{name}.arucostudio.json").read_text(encoding="utf-8"))
    for f in doc["features"]:
        if "aruco" in f:
            f.update(extra)
    sc, _issues = DS.compile(doc, chain["presets"])
    if rule is not None:
        for t in sc.tags:
            t.spec.settings["label"]["rule"] = rule
    plans = {t.name: plan_tag(t.spec) for t in sc.tags}
    ps, _sk = P3.parts(doc, sc, plans)
    prof = chain["profile"]
    st = BD.BedSettings(bed_w_mm=prof.bed_mm[0], bed_d_mm=prof.bed_mm[1],
                        bed_h_mm=prof.max_height_mm)
    lay = P3.layout(ps, st)
    proj = tmp_path / f"{name}.3mf"
    proj.write_bytes(P3.render(lay, BD.project_config_text(prof, st), name))
    run = SC.slice_project(CONSOLE, str(proj), str(tmp_path / "work"), chain["copies"])
    assert run["exit"] == 0 and run["gcode"], run["log"]
    for f in (tmp_path / "work" / "psdata").rglob("*.ini"):
        assert not any(PR.private_key(k) for k, _v in PR._kv_lines(f.read_text(encoding="utf-8")))
    rep = SC.check_send(lay, ps, sc, plans, run["gcode"], chain["pp"]["layer_mm"],
                        chain["pp"]["first_layer_mm"])
    rep["seconds"] = run["seconds"]
    REPORTS[name + ("" if not extra else " " + json.dumps(extra))
            + ("" if rule is None else f" rule {rule}")] = rep
    rep["plans"] = plans
    return rep


@NEEDS
def test_the_plate_slices_as_planned(chain, tmp_path):
    rep = sliced("plate_charuco", chain, tmp_path)
    assert rep["layers"]["ok"] and rep["layers"]["count"] == 16
    t = rep["tags"]["tag"]
    assert t["flat"] and t["heights"]["ok"]
    assert t["lines"]["ok"] and t["lines"]["parallel"] == 2       # 1.36 mm module, 0.68 lines
    assert t["ink"]["iou"] >= 0.9
    assert rep["footprint"]["ok"] and rep["ok"]


@pytest.fixture(scope="module")
def forearm(chain, tmp_path_factory):
    return sliced("forearm", chain, tmp_path_factory.mktemp("forearm"))


NAMED = {"label": "#id + name", "marker_ids": None}
LINE_MM = 0.68                                       # the fixture print's lines (the cell rule)
FLOOR = L.LINE_STROKE * LINE_MM                      # rule 5's thinnest cut stroke: 0.748 mm
AT_THE_LINE = {"label": {"on": True, "content": "id", "cap_mm": round(L.GLYPH_ROWS * FLOOR, 6)},
               "marker_ids": None}


@pytest.fixture(scope="module")
def forearm_named(chain, tmp_path_factory):
    """The forearm as M8c.7 sliced it, under label rule 4 (what a tag made
    before rule 5 stores): '#id + name' on every face and the list's shared
    ids, so the front and back carry the two-line label cut from the black
    at a 0.64 mm stroke, under the 0.68 mm line."""
    return sliced("forearm", chain, tmp_path_factory.mktemp("forearm_named"), rule=4, **NAMED)


@pytest.fixture(scope="module")
def forearm_at_the_line(chain, tmp_path_factory):
    """Label rule 5 (a new tag): the tightest label it builds cut from the
    black -- '#0-5' typed at 3.74 mm, so each stroke is exactly rule 5's
    floor, 1.1 lines of the cell rule's 0.68 mm, in the front and back
    ChArUco squares."""
    return sliced("forearm", chain, tmp_path_factory.mktemp("forearm_line"), **AT_THE_LINE)


@NEEDS
def test_the_forearm_slices_as_one_object_and_each_side_tag_passes(forearm):
    rep = forearm
    assert rep["layers"]["ok"]
    assert sorted(rep["tags"]) == ["tag.back", "tag.front", "tag.left", "tag.right"]
    for name, t in rep["tags"].items():
        assert not t["flat"], name
        assert t["heights"]["ok"], (name, t["heights"])
        assert t["ink"]["iou"] >= 0.9, (name, t["ink"])
    assert rep["footprint"]["ok"]


@NEEDS
def test_the_forearm_labels_print_their_pixels(forearm_at_the_line):
    """M8c.7's label bar, PASSED under label rule 5 (Q1's recommended
    default, 2026-10-17): a label cut out of the black strokes at least one
    line of the cell rule (1.1 lines: at exactly one line, 0.68-0.72 mm, the
    white prints but 10 of 85 one-pixel black counters drop out), so every
    font pixel prints -- even at the floor itself (was a strict xfail under
    rule 4: test_rule_4_is_unchanged_and_still_loses_pixels)."""
    rep = forearm_at_the_line
    for n in ("tag.back", "tag.front"):
        lab = rep["plans"][n].ev["label"]
        assert lab.settings.rule == L.NEW_RULE == 5 and lab.kind == "black", (n, lab.kind)
        assert abs(lab.stroke - FLOOR) < 1e-6, (n, lab.stroke)     # exactly the floor
    labelled = {n: t["label"] for n, t in rep["tags"].items() if t["label"].get("pixels")}
    assert sorted(labelled) == ["tag.back", "tag.front"]
    for name, lab in labelled.items():
        assert lab["mean_gap"] >= 0.85, (name, lab)      # the black around the text is there
    assert all(lab["ok"] for lab in labelled.values()), labelled


def test_rule_5_refuses_what_rule_4_built_under_one_line(chain):
    """No slicer: the forearm's '#id + name' (two lines in a 19 mm square)
    is built at a 0.64 mm stroke under rule 4 and refused under rule 5 (one
    message; never a label whose glyphs close up). A typed cap under the
    floor is refused too, saying so."""
    doc = json.loads((EX / "forearm.arucostudio.json").read_text(encoding="utf-8"))
    for f in doc["features"]:
        if "aruco" in f:
            f.update(NAMED)
    sc, _issues = DS.compile(doc, chain["presets"])
    front = next(t for t in sc.tags if t.name == "tag.front")
    assert front.spec.settings["label"]["rule"] == 5             # what a new tag stores
    new = plan_tag(front.spec).ev["label"]
    assert new.kind == "none" and "ChArUco square for '#0-5'" in new.reason, new.reason
    assert f"{L.GLYPH_ROWS * FLOOR:.1f} mm letters" in new.reason, new.reason
    spec4 = copy.deepcopy(front.spec)
    spec4.settings["label"]["rule"] = 4
    lab4 = plan_tag(spec4).ev["label"]
    assert lab4.kind == "black" and abs(lab4.stroke - 0.64) < 1e-6 and lab4.texts() == ["#0-5|FOR…"]
    typed = copy.deepcopy(front.spec)
    typed.settings["label"] = {**typed.settings["label"], "content": "id", "cap_mm": 3.2}
    lab = plan_tag(typed).ev["label"]
    assert lab.kind == "none" and "rule 5" in lab.reason, lab.reason


@NEEDS
def test_rule_4_is_unchanged_and_still_loses_pixels(forearm_named):
    """The M8c.7 finding, kept as it was found: a tag that stores label
    rule 4 is planned exactly as before (stroke 0.64 mm, '#0-5|FOR...'),
    and its slice still loses font pixels. Rule 5 is a new number, so no
    stored tag changes."""
    for n in ("tag.back", "tag.front"):
        lab = forearm_named["plans"][n].ev["label"]
        assert lab.settings.rule == 4 and abs(lab.stroke - 0.64) < 1e-6, (n, lab.stroke)
    labelled = {n: t["label"] for n, t in forearm_named["tags"].items()
                if t["label"].get("pixels")}
    assert sorted(labelled) == ["tag.back", "tag.front"]
    assert not all(lab["ok"] for lab in labelled.values()), labelled


@NEEDS
def test_negative_volumes_cut_nothing_of_the_black(chain, tmp_path):
    """New-body tiles with pins: each tag's socket is a negative volume; the
    black prints where the plan has it."""
    rep = sliced("plate_charuco", chain, tmp_path, mode="both", op="new")
    t = rep["tags"]["tag"]
    assert t["heights"]["ok"] and t["ink"]["iou"] >= 0.9, t
    assert rep["footprint"]["ok"]


def test_report(capsys):
    """The numbers for docs/status/M8c.md (printed with -s)."""
    short = {}
    for k, r in REPORTS.items():
        short[k] = {"layers": [r["layers"]["count"], r["layers"]["want"]], "s": r["seconds"],
                    "footprint": [r["footprint"]["outside"], r["footprint"]["in_margin"]],
                    "tags": {n: {"iou": t["ink"]["iou"], "z": [t["heights"]["first_mm"],
                                                               t["heights"]["last_mm"]],
                                 "want_z": t["heights"]["want_mm"],
                                 "lines": [t["lines"].get("parallel"), t["lines"].get("want")],
                                 "label": {k: t["label"].get(k) for k in (
                                     "pixels", "worst_ink", "worst_gap", "mean_ink", "mean_gap",
                                     "below", "ok")}}
                             for n, t in r["tags"].items()}}
    print("M8c.7 slice:", json.dumps(short))
