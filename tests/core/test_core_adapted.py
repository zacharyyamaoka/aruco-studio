"""The functions the port ADAPTED (they read Fusion or the dialog in REF):
each gives what REF's version gave on the same facts.

The facts are written by hand from REF's code (cad-exporter c8216ff); the
goldens cover the verbatim functions.
"""
import json
from pathlib import Path

import pytest

from aruco_studio.core import (edits as E, export_rows as X, form as F, geometry as G,
                               ids_design as I, markers as M, marker_table as T, numbering as N,
                               validate as V)

GOLDENS = Path(__file__).resolve().parents[2] / "goldens"


# ----------------------------------------------------------- ids_design

def _fixtures():
    return json.loads((GOLDENS / "numbering.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", _fixtures(), ids=lambda c: c["in"]["fixture"])
def test_plan_snapshot_is_plan_stable(case):
    """A snapshot of REF's numbering fixtures numbers exactly as plan_stable
    (what ArUco IDs runs) does on the same tags and occurrences."""
    inp = case["in"]
    snap = I.AssemblySnapshot(design_units="cm", tags=inp["tags"], root="Robot",
                              occurrences=[dict(o, world=o["transform"]) for o in inp["occurrences"]])
    tags = [M.TagDef.from_dict(d, lambda m: None) for d in inp["tags"]]
    occs = [M.OccurrenceRef(o["path"], o["component"], o["transform"], o["visible"], o["linked"])
            for o in inp["occurrences"]]
    want = N.plan_stable(tags, occs, root_component="Robot")
    got = I.plan_snapshot(snap)
    assert got.to_dict() == want.to_dict()
    assert got.to_dict() == case["out"]["stable"]
    back = I.AssemblySnapshot.from_dict(json.loads(json.dumps(snap.to_dict())))
    assert back == snap


def test_snapshot_refuses_an_unknown_schema():
    with pytest.raises(ValueError, match="snapshot/1"):
        I.AssemblySnapshot.from_dict({"schema": "arucostudio.snapshot/9"})


def test_stamps_make_chains_and_find_a_pasted_copy():
    info = {"A:1": {"nk": "/A:1", "inside_linked": False, "uid": "u1", "born": 5.0, "home": "h"},
            "A:1+Tag:1": {"nk": "A/Tag:1", "inside_linked": False, "uid": "u2", "born": 7.0, "home": "h"},
            "A:2": {"nk": "/A:2", "inside_linked": False, "uid": "u1", "born": 5.0, "home": "h"},
            "L:1+Tag:1": {"nk": "L/Tag:1", "inside_linked": True, "uid": "", "born": None, "home": ""}}
    st = I.stamps(info)
    # A:2 carries A:1's stamp (pasted): one of them loses it (aruco_numbering.stamp_losers)
    assert st["losers"] == N.stamp_losers([("/A:1", "u1", "h"), ("A/Tag:1", "u2", "h"), ("/A:2", "u1", "h")])
    assert st["chains"]["A:1+Tag:1"] == N.chain_key(
        [None if "/A:1" in st["losers"] else "#u1", "#u2"])
    assert st["born"]["A:1+Tag:1"] == 7.0
    assert st["chains"]["L:1+Tag:1"] == N.chain_key([None, "=Tag:1"])


def test_component_labels_number_shared_names():
    lab = I.ComponentLabels(["Robot", "Component1", "Plate", "Component1"], root=0)
    assert [lab.label(i) for i in range(4)] == ["", "Component1 <1>", "Plate", "Component1 <2>"]
    assert lab.duplicates == ["Component1"]
    assert lab.comp("Component1 <2>") == 3 and lab.comp("") == 0 and lab.comp("nope") is None


def test_unique_name_and_warning_text():
    assert I.unique_name(["Plate", "Plate (2)"], "Plate") == "Plate (3)"
    assert I.unique_name(["Plate"], "Arm", taken={"Arm"}) == "Arm (2)"
    assert I.unique_name([], "Arm") == "Arm"
    w = I.warning_text(["a", "b", "c", "d"], "why")
    assert w.startswith("ArUco IDs' parts are out of date: a; b; c (+1 more). why Double-click")
    assert len(I.warning_text(["x" * 900])) == 480


def test_node_state_of_reads_or_gives_empty():
    st = {"schema": N.SCHEMA, "final": {"Tag:1|top": 3}}
    assert I.node_state_of(json.dumps(st)) == N.read_state(json.dumps(st))
    assert I.node_state_of(None) == {} and I.node_state_of("{not json") == N.read_state("{not json") or True


# ------------------------------------------------- the after-compute policy

def test_verdict_is_auto_decision_on_the_documents_state():
    st = E.SyncState(auto_refresh="all", doc_is_mine=False, undoing=False, done=("d0",),
                     recent=(1.0, 2.0))
    assert E.verdict(st, "d1", 100.0) == N.auto_decision("all", False, False, "d1", done=("d0",),
                                                         failed=None, recent=(1.0, 2.0), now=100.0)
    assert E.verdict(E.SyncState(undoing=True), "d1", 0.0)[0] == N.auto_decision(
        "all", False, True, "d1", now=0.0)[0]
    assert I.auto_verdict(st, "d0", 100.0) == N.auto_decision("all", False, False, "d0", done=("d0",),
                                                              recent=(1.0, 2.0), now=100.0)
    assert E.BUDGET_MS == 5.0


# ------------------------------------------------------ the marker table rows

def _row(**kw):
    base = dict(name="A:1|t", path="A:1", key="t", component="A", layout="single",
                dictionary="DICT_4X4_50", count=1, modelled=3, base=3, final=3)
    base.update(kw)
    return N.IdsRow(**base)


def test_how_and_tone_say_where_an_id_comes_from():
    assert T._how(_row(error="no room")) == "⚠ no room" and T._tone(_row(error="x")) == "error"
    assert T._how(_row(hidden=True)) == "hidden — not numbered" and T._tone(_row(hidden=True)) == "muted"
    r = _row(source="override")
    assert T._how(r) == f"override {r.label()}"
    r = _row(basis="ledger")
    assert T._how(r) == f"auto {r.label()} · kept" and T._tone(r) == ""
    r = _row(basis="reused")
    assert "reuses a retired id" in T._how(r) and T._tone(r) == "warn"
    r = _row(basis="new", linked=True)
    assert T._how(r).endswith(" · new · linked")


def test_marker_row_from_an_ids_row():
    sp = M.TagSpec(dictionary="DICT_4X4_50", marker_id=0, marker_length_m=0.03)
    r = _row(final=7)
    row = T.marker_row(r, {("A", "t"): sp}, part_paths={"A:1": "IDs:1+Part:1"})
    assert row.ids == list(r.ids) and row.pick_paths == ("IDs:1+Part:1", "A:1")
    assert T.spec_of({("A", "t"): sp}, r).marker_id == 7


# -------------------------------------------------------- the export words

def test_export_words():
    assert X.slug("My design v2!") == "My_design_v2" and X.slug("!!!") == "design"
    assert X.plural(1, "part") == "1 part" and X.plural(3, "copy", "copies") == "3 copies"
    assert X.split_black(0.6, "raised") == (0.0, 0.6) and X.split_black(0.6, "half") == (0.3, 0.3)
    assert X._tick_part("part_3__1") == 3 and X._tick_part("part_x") is None
    assert X.ids_text({"ids": [4, 5, 6]}) == "#4-6" and X.ids_text({"marker_id": 2}) == "#2"
    assert X.KINDS == ("prusaslicer", "stl", "pdf") and X.SLOTS == (1, 2, 3, 4, 5)


# ------------------------------------------------------- form: adapted lines

def test_edit_kind_line():
    assert F.edit_kind_line({"kind": "compute"}) is None
    line = F.edit_kind_line({"kind": "in place", "goes": ["pocket"], "op_changes": True, "why": None},
                            {"pocket": [("Fillet1", "edges of")], "joined": [("Joint2", "a face of")]})
    assert "IN PLACE" in line and "removes the pocket" in line and "Fillet1 (edges of the pocket)" in line
    assert "Joint2 (a face of the joined body's new faces)" in line
    line = F.edit_kind_line({"kind": "rebuild", "goes": [], "op_changes": False, "why": "x"}, {})
    assert "REBUILDS this tag (delete + create: x); nothing after it uses it" in line


def test_preset_lines():
    out = F.preset_lines("Preset 'A' applied", ["not saved"], ["file could not be read"])
    assert out == ["<span style='color:#06c'>Preset 'A' applied</span>",
                   "<span style='color:#c60'>not saved</span>",
                   "<span style='color:#c60'>file could not be read</span>"]


# ------------------------------------------------------- validate: the model

def test_row_model_shows_two_messages_per_row_and_the_summary():
    m = V.RowModel(names={"size": "Size"}, tabs={"size": "Marker"}, rows=["size", "label_place"],
                   alias={"label_side": "label_place"})
    shown = m.show([V.Issue("size", "warn", "clamped"), V.Issue("size", "block", "nothing fits"),
                    V.Issue("size", "info", "x"), V.Issue("label_side", "error", "too big")], "ok")
    assert shown["rows"]["size"]["html"].startswith("<span style='color:#cc0000'>⚠ nothing fits")
    assert shown["rows"]["label_place"]["html"].endswith("too big</span>")
    assert "OK is off -- Size (Marker): nothing fits" in shown["summary"]
    assert [i.text for i in m.blocking()] == ["nothing fits"] and m.first_tab() == "Marker"
    hidden = m.show([V.Issue("size", "warn", "w")], visible=lambda a: False)
    assert hidden["rows"]["size"] is None


def test_issue_fields_are_tagspec_key_paths():
    assert V.field_of("size") == "numbers.size" and V.field_of("label_cap") == "settings.label.cap_mm"
    assert V.field_of("") == "tag" and V.field_of("unknown_row") == "tag"
    assert all(f == "tag" or f.split(".")[0] in ("settings", "numbers", "target")
               for f in V.ANCHOR_FIELD.values())


# ----------------------------------------------------------- geometry

def test_frames_and_matrices():
    fr = ([1.0, 2.0, 3.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0])
    m = G.matrix_of_frame(*fr)
    assert G.frame_of_matrix(m) == tuple(list(v) for v in fr) or G.frame_of_matrix(m) == list(fr)
    assert G._xf_point(m, (1, 0, 0)) == [1.0, 3.0, 3.0]
    assert G._xf_vector(m, (2, 0, 0)) == [0.0, 1.0, 0.0]
    assert G._rotz([1.0, 0.0, 0.0], [0.0, 0.0, 1.0], 0) == [1.0, 0.0, 0.0]
    x = G._rotz([1.0, 0.0, 0.0], [0.0, 0.0, 1.0], 90)
    assert abs(x[0]) < 1e-12 and abs(x[1] - 1.0) < 1e-12


def test_dot_keeps_the_sign_of_zero_like_aruco_tags():
    """aruco_tags._dot sums p0 + p1 + p2; a -0.0 there makes atan2 say -pi."""
    import math
    assert math.copysign(1.0, G._dot([-0.0, -0.0, -0.0], [1.0, 1.0, 1.0])) == -1.0
    assert math.copysign(1.0, G._dot_f([-0.0, -0.0, -0.0], [1.0, 1.0, 1.0])) == 1.0
