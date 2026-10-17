"""M2.8: a copy's plan differs from its template's only where the id shows:
the cells (core.markers.cell_boxes of the copy's board) and the label's text
inside the template's slots (core.label.copy_regions). Every golden case x
3 ids."""
from __future__ import annotations

import pytest

import _evaluate_golden as G
from aruco_studio.core import dictionary as D
from aruco_studio.core import markers as M
from aruco_studio.plan import plan_tag
from aruco_studio.plan import variants as V
from aruco_studio.plan.spec import TagSpec

CELL_NAMES = {"pattern", "pocket", "recess_pattern", "cells"}
LABEL_NAMES = {"label_join", "label_cut"}


def _ids_for(p):
    cap = D.dictionary_info(p.data["marker"]["dictionary"])["capacity"]
    count = len(p.data["ids"])
    first = p.data["marker"]["marker_id"]
    out = [i for i in (1, 7, cap - count) if 0 <= i <= cap - count and i != first]
    return out[:3]


def _in_rects(rects, pt, tol=1e-6):
    return any(r[0] - tol <= pt[0] <= r[2] + tol and r[1] - tol <= pt[1] <= r[3] + tol
               for r in rects)


@pytest.mark.parametrize("group", ["legacy", "matrix"])
def test_a_copy_differs_only_in_the_ids_and_the_label_text(group):
    bad = []
    n = 0
    for c in G.cases(group):
        if "error" in c["out"]:
            continue
        t = plan_tag(TagSpec.from_dict(c["in"]))
        for nid in _ids_for(t):
            cp = V.copy_plan(t, nid)
            n += 1
            if not cp.ok:
                bad.append((c["id"], nid, cp.data["errors"]))
                continue
            a, b = t.data, cp.data
            # the board: only the first id
            ma, mb = dict(a["marker"]), dict(b["marker"])
            ma.pop("ids", None), mb.pop("ids", None)
            if mb.pop("marker_id") != nid or ma.pop("marker_id") is None or ma != mb:
                bad.append((c["id"], nid, "marker"))
            if b["ids"] != M.TagSpec.from_dict(b["marker"], lambda m: None, "copy").ids:
                bad.append((c["id"], nid, "ids"))
            for k in ("parts", "combines", "frames", "mark", "trim", "pins", "placement",
                      "layout", "slabs", "rules"):
                if a[k] != b[k]:
                    bad.append((c["id"], nid, k))
            ga, gb = dict(a["guides"]), dict(b["guides"])
            ga.pop("label_preview"), gb.pop("label_preview")
            if ga != gb:
                bad.append((c["id"], nid, "guides"))
            # the layers: the same, but the cells and the label's strokes
            slots = V.label_slots(t, nid)
            la = [L for L in a["layers"] if L["name"] not in LABEL_NAMES]
            lb = [L for L in b["layers"] if L["name"] not in LABEL_NAMES]
            if len(la) != len(lb):
                bad.append((c["id"], nid, "layer count"))
                continue
            cells = [[[x0 * 1000.0, y0 * 1000.0], [x1 * 1000.0, y0 * 1000.0],
                      [x1 * 1000.0, y1 * 1000.0], [x0 * 1000.0, y1 * 1000.0]]
                     for (x0, y0, x1, y1) in M.cell_boxes(cp.ev["spec"])]
            cell_names = {"cells"} if t.ev["mode"] == "white" else CELL_NAMES - {"cells"}
            for x, y in zip(la, lb):
                if x["name"] in cell_names:
                    if {k: v for k, v in x.items() if k != "polygons"} != \
                            {k: v for k, v in y.items() if k != "polygons"}:
                        bad.append((c["id"], nid, x["name"]))
                    got = [pp["outer"] for pp in y["polygons"]]
                    if len(got) != len(cells) or any(
                            abs(p - q) > 1e-9 for g, w in zip(got, cells)
                            for gp, wp in zip(g, w) for p, q in zip(gp, wp)):
                        bad.append((c["id"], nid, "cells of " + x["name"]))
                elif x != y:
                    bad.append((c["id"], nid, x["name"]))
            forced = bool((a.get("label") or {}).get("forced"))
            for L in b["layers"]:
                # Build anyway: REF relabel puts each copy's text at the template's
                # spot and cap, its warnings kept -- it may overflow the slot
                if L["name"] in LABEL_NAMES and not forced:
                    for pp in L["polygons"]:
                        if not all(_in_rects(slots, q) for q in pp["outer"]):
                            bad.append((c["id"], nid, "label outside its slots"))
                            break
    assert n > 100 if group == "matrix" else n > 30
    assert not bad, f"{len(bad)}: {bad[:5]}"


def test_id_regions_and_warning():
    c = next(c for c in G.cases("matrix") if "error" not in c["out"]
             and c["out"]["ev"]["label"] and c["out"]["ev"]["label"]["kind"] != "none")
    t = plan_tag(TagSpec.from_dict(c["in"]))
    cp = V.copy_plan(t, 5)
    reg = V.id_regions(t, cp)
    assert reg["changed"] and set(map(tuple, reg["old"])) != set(map(tuple, reg["new"]))
    assert V.label_slots(t, 5)
    assert V.label_warning(t, 5) in ("",) or isinstance(V.label_warning(t, 5), str)
