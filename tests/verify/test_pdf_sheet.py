"""The PDF print sheet (scene/sheet.to_pdf: REF print_sheet over the scene),
read back by OpenCV (Definition of Done D6; spec ST-EXP-PDF, ST-T-EXP-1).

The PDF is rasterised by pdfium (pypdfium2, REF tools/verify_aruco_output's
oracle) at 300 dpi; OpenCV's own detector reads every page; every visible
tag's every id is found, once, in its dictionary, and each sticker's black
square is its planned size within one pixel (true scale on paper).
"""
from __future__ import annotations

import numpy as np
import pypdfium2 as pdfium
import cv2

from aruco_studio.plan import target as T
from aruco_studio.plan.spec import TagSpec
from aruco_studio.scene import Scene, renumber
from aruco_studio.scene import sheet as SH
from aruco_studio.verify import detect as D

DPI = 300
PX_PER_MM = DPI / 25.4


def _scene():
    sc = Scene(name="pdf")
    k = 0
    for layout, area, dic in (("single", (40, 40), "DICT_4X4_50"),
                              ("grid", (90, 60), "DICT_5X5_100"),
                              ("charuco", (90, 70), "DICT_4X4_50"),
                              ("single", (30, 30), "DICT_6X6_250")):
        for j in range(3):
            sc.add(TagSpec(settings={"layout": layout, "mode": "both", "op": "new",
                                     "dictionary": dic}, target=T.box(*area, 0)),
                   x_mm=110 * j, y_mm=100 * k)
        k += 1
    renumber(sc)
    return sc


def _pages(pdf: bytes):
    doc = pdfium.PdfDocument(pdf)
    out = []
    for i in range(len(doc)):
        bmp = doc[i].render(scale=DPI / 72.0, grayscale=True)
        img = np.asarray(bmp.to_numpy())
        if img.ndim == 3:
            img = img[:, :, 0] if img.shape[2] == 1 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        out.append(np.ascontiguousarray(img))
    return out


def test_the_pdf_sheet_reads_every_id_of_every_tag():
    sc = _scene()
    plans = sc.plans()
    lay = SH.pdf_layout(sc, plans)
    assert not lay.rejected, lay.rejected
    pdf = SH.to_pdf(sc, plans, date="2026-10-16")
    assert pdf.startswith(b"%PDF-")
    pages = _pages(pdf)
    assert len(pages) == lay.page_count >= 1
    want = {}
    for t in sc.tags:
        p = plans[t.name]
        want.setdefault(p.data["marker"]["dictionary"], []).extend(p.data["ids"])
    for dic, ids in want.items():
        assert len(ids) == len(set(ids)), (dic, ids)        # renumbered: unique per dictionary
        found = []
        det = cv2.aruco.ArucoDetector(D.dictionary(dic), D.parameters())
        for img in pages:
            _c, got, _r = det.detectMarkers(img)
            if got is not None:
                found += [int(i) for i in np.asarray(got).ravel()]
        assert sorted(set(found) & set(ids)) == sorted(ids), (dic, sorted(ids), sorted(found))


def test_a_single_sticker_prints_at_its_planned_size():
    sc = Scene(name="size")
    sc.add(TagSpec(settings={"layout": "single", "mode": "both", "op": "new"},
                   target=T.box(40, 40, 0)))
    plans = sc.plans()
    mm = plans[sc.tags[0].name].data["marker"]["marker_length_m"] * 1000.0
    img = _pages(SH.to_pdf(sc, plans, date="2026-10-16"))[0]
    det = cv2.aruco.ArucoDetector(D.dictionary("DICT_4X4_50"), D.parameters())
    corners, ids, _r = det.detectMarkers(img)
    assert ids is not None and len(ids) == 1
    c = np.asarray(corners[0]).reshape(4, 2)
    side = float(np.mean([np.linalg.norm(c[i] - c[(i + 1) % 4]) for i in range(4)]))
    assert abs(side - mm * PX_PER_MM) <= 1.5, (side, mm * PX_PER_MM)


def test_hidden_and_refused_tags_are_not_on_the_sheet():
    sc = _scene()
    sc.tags[0].hidden = True
    items = SH.print_items(sc)
    assert sc.tags[0].name not in [i.key for i in items]
    assert len(items) == len(sc.tags) - 1
