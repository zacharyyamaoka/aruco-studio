"""The N-1 golden scenario: what REF's core does since c8216ff (4c8810b, da6e622),
run on whichever core's modules it is handed.

tools/make_goldens_ref_head.py hands it REF's own bam_cad_core at
ref_path.REF_HEAD (a child process, `python -I`, REF's files only) and writes
the answers to goldens/ref_head/charuco_print.json; tests/core/
test_golden_ref_head.py hands it aruco_studio.core and compares. The inputs are
REF's tests/test_charuco_print.py fixture (the boards as the export builds
them: a calibration board, the arm's 8 x 2 strip, a labelled board with a
cut corner, a 3D-made legacy board with a white label strip, an oversize
board, a single marker twice) plus the e2e-style records numbering digests.

stdlib only; no file is read or written here.
"""
from __future__ import annotations

import dataclasses
import hashlib


def _plain(v):
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return {f.name: _plain(getattr(v, f.name)) for f in dataclasses.fields(v)}
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, (bytes, bytearray)):
        return {"sha256": hashlib.sha256(bytes(v)).hexdigest(), "n": len(v)}
    return v


# REF's PrintItem fields: the Studio's extra ones (cut_mm, ink_mm, caption,
# made_by, name, ids; SheetSettings.mode) are not REF's and stay out
PRINT_ITEM_FIELDS = ("key", "dictionary", "marker_id", "marker_length_m", "quiet_modules",
                     "label_lines", "layout", "rows", "cols", "separation_m", "square_length_m",
                     "legacy", "top_label", "marks", "ink", "outline_mm")


def _item(i):
    return {k: _plain(getattr(i, k)) for k in PRINT_ITEM_FIELDS}


def run(M, PS, AL, CH, N):
    """-> {name: answer}: every answer JSON-able."""
    CALIB = M.TagSpec(dictionary="DICT_4X4_50", marker_id=0, layout="charuco", cols=5, rows=7,
                      square_length_m=0.030, marker_length_m=0.022, quiet_modules=0.0)
    STRIP = M.TagSpec(dictionary="DICT_4X4_50", marker_id=20, layout="charuco", cols=8, rows=2,
                      square_length_m=0.025, marker_length_m=0.0185, quiet_modules=0.0)
    LABELLED = M.TagSpec(dictionary="DICT_5X5_100", marker_id=40, layout="charuco", cols=5,
                         rows=4, square_length_m=0.020, marker_length_m=0.015, quiet_modules=0.5)
    MADE3D = M.TagSpec(dictionary="DICT_4X4_50", marker_id=10, layout="charuco", cols=4, rows=4,
                       square_length_m=0.020, marker_length_m=0.015, quiet_modules=1.0,
                       grow_m=0.0002, raise_m=0.0006, depth_m=0.0, legacy=True)
    BIG = M.TagSpec(dictionary="DICT_5X5_100", marker_id=60, layout="charuco", cols=7, rows=10,
                    square_length_m=0.030, marker_length_m=0.022, quiet_modules=0.0)
    SINGLE = M.TagSpec(dictionary="DICT_4X4_50", marker_id=3, marker_length_m=0.030)
    tags = [M.TagDef(key="board", component="Calib Board", spec=CALIB),
            M.TagDef(key="charuco", component="Aruco Marker", spec=STRIP),
            M.TagDef(key="lab", component="Labelled Board", spec=LABELLED),
            M.TagDef(key="made3d", component="Printed Board", spec=MADE3D),
            M.TagDef(key="big", component="Big Board", spec=BIG),
            M.TagDef(key="front", component="Plate", spec=SINGLE)]
    occs = [M.OccurrenceRef("Calib Board:1", "Calib Board"),
            M.OccurrenceRef("One Dof Arm:1", "One Dof Arm"),
            M.OccurrenceRef("One Dof Arm:1+Aruco Marker:1", "Aruco Marker"),
            M.OccurrenceRef("Labelled Board:1", "Labelled Board"),
            M.OccurrenceRef("Printed Board:1", "Printed Board"),
            M.OccurrenceRef("Big Board:1", "Big Board"),
            M.OccurrenceRef("Plate:1", "Plate"), M.OccurrenceRef("Plate:2", "Plate")]
    res = M.resolve(tags, [], occs, "Root", "cm")
    lab_label = AL.plan_label(
        LABELLED, AL.LabelSettings.from_dict({"on": True, "content": "id", "place": "black",
                                              "row": "square"}),
        mode="both", op="new", name="Labelled Board", key="lab")
    lab_mark = CH.mark_for_spec(LABELLED, "both", "new", want="cut").to_dict()
    m3d_label = AL.plan_label(
        MADE3D, AL.LabelSettings.from_dict({"on": True, "content": "id", "place": "white",
                                            "side": "below"}),
        mode="both", op="new", name="Printed Board", key="made3d", grow=True)
    m3d_mark = CH.mark_for_spec(MADE3D, "both", "new", want="cut").to_dict()
    ink = {"Labelled Board:1|lab": M.cad_print_ink(LABELLED, lab_label.to_dict(), lab_mark),
           "Printed Board:1|made3d": M.cad_print_ink(MADE3D, m3d_label, m3d_mark)}
    out = {"cad_print_ink": _plain(ink),
           "cad_print_ink_bare": _plain(M.cad_print_ink(CALIB)),
           "charuco_label_line": [M.charuco_label_line(s) for s in
                                  (CALIB, STRIP, LABELLED, MADE3D, BIG)]}
    items = M.print_items(res, cad_ink=ink)
    out["print_items"] = [_item(i) for i in items]
    out["print_items_only"] = [_item(i) for i in M.print_items(
        res, only=["Calib Board:1", "Plate:2"], cad_ink=ink)]
    for page, land in (("letter", False), ("letter", True), ("a4", False), ("a3", True)):
        out[f"sheet_check_{page}_{int(land)}"] = _plain(M.sheet_check(
            res, page=page, landscape=land, cad_ink=ink))
        lay = M.sheet_layout(res, page=page, landscape=land, cad_ink=ink)
        out[f"layout_summary_{page}_{int(land)}"] = _plain(PS.layout_summary(lay))
        out[f"pdf_{page}_{int(land)}"] = _plain(PS.render_layout_pdf(lay, date="2026-10-17"))
        out[f"pdf_dialog_{page}_{int(land)}"] = _plain(PS.render_layout_pdf(
            lay, date="2026-10-17", print_dialog=True))
    files = M.sidecar_files(res, design_name="Golden", exported_at="2026-10-17T00:00:00",
                            only=["Calib Board:1", "Labelled Board:1", "Printed Board:1"],
                            cad_ink=ink)
    # the sheet PDF in sidecar_files carries TODAY's date (render_layout_pdf's
    # default): it is pinned above with a fixed date, so it is left out here
    out["sidecar_files"] = {k: hashlib.sha256(v).hexdigest() for k, v in sorted(files.items())
                            if not k.endswith(".pdf")}
    out["sidecar_pdfs"] = sorted(k for k in files if k.endswith(".pdf"))
    settings = PS.SheetSettings()
    out["fit_pages"] = {i.key: _plain(PS.fit_pages(i, settings)) for i in items}
    out["sticker_box_mm"] = {i.key: _plain(PS.sticker_box_mm(i)) for i in items}
    sq = [(-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)]
    ell = [(0.0, 0.0), (8.0, 0.0), (8.0, 3.0), (3.0, 3.0), (3.0, 8.0), (0.0, 8.0)]
    out["offset_polygon"] = {f"{n} {d}": _plain(PS.offset_polygon(p, d))
                             for n, p in (("square", sq), ("ell", ell)) for d in (0.05, 0.5, 2.0)}
    recs = [t.to_dict() for t in tags]
    jit = [dict(r) for r in recs]
    for r in jit:
        r["origin"] = [v + 4e-8 for v in (r.get("origin") or [0.0, 0.0, 0.0])]
    out["record_digest"] = N.record_digest(recs)
    out["record_digest_r"] = N.record_digest_r(recs)
    out["record_digest_jitter"] = N.record_digest(jit)
    out["record_digest_r_jitter"] = N.record_digest_r(jit)
    x = {"records": N.record_digest(recs), "records_r": N.record_digest_r(recs)}
    y = {"records": N.record_digest(jit), "records_r": N.record_digest_r(jit)}
    out["records_same"] = [N.records_same(x, y), N.records_same(x, {"records": "z"}),
                           N.records_same({"records_eval_r": y["records_r"]}, y),
                           N.records_same(None, None)]
    return out
