"""M2b.4 and M2b.7's scene check.

* the mesh (plan/mesh.py's triangles, painted top-down, highest last) reads
  the same ids as the layers' pixel CSG (verify/render), every golden case;
* a 12-tag scene sheet at 10 px / mm reads every id, each marker's centre
  within 0.1 mm of where the scene puts it.
"""
from __future__ import annotations

import math

import cv2
import numpy as np
import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plan"))
import _evaluate_golden as G  # noqa: E402

from aruco_studio.plan import mesh as ME  # noqa: E402
from aruco_studio.plan import plan_tag  # noqa: E402
from aruco_studio.plan import target as T  # noqa: E402
from aruco_studio.plan.spec import TagSpec  # noqa: E402
from aruco_studio.scene import Scene, renumber  # noqa: E402
from aruco_studio.verify import detect as D  # noqa: E402
from aruco_studio.verify.render import SHIFT, Raster, top_view  # noqa: E402
from aruco_studio.verify.report import verify_scene  # noqa: E402

GREY = {"white": 255, "black": 0, "body": 255}
CHUNKS = 8


def mesh_raster(plan, like: Raster) -> np.ndarray:
    """The mesh's upward faces, painted in z order, on `like`'s grid."""
    d = plan.data
    H, W = like.img.shape
    ss = 2
    s = like.px_per_mm * ss
    white_mode = any(L["part"] == "pattern" and L["colour"] == "white" for L in d["layers"])
    bg = 0 if white_mode else 255
    body = 0 if white_mode else 255
    img = np.full((H * ss, W * ss), bg, np.uint8)
    faces = []
    for m in ME.mesh(plan):
        P = m["positions"]
        I = m["indices"]
        for k in range(0, len(I), 3):
            a, b, c = (P[3 * I[k + j]:3 * I[k + j] + 3] for j in range(3))
            nz = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if nz > 1e-12 and abs(a[2] - m["z"][1]) < 1e-9:      # a top face
                faces.append((m["z"][1], m["colour"], (a, b, c)))
    faces.sort(key=lambda f: f[0])
    for z, colour, tri in faces:
        pts = np.array([[((p[0] - like.u0) * s - 0.5), ((like.v1 - p[1]) * s - 0.5)]
                        for p in tri]) * (1 << SHIFT)
        g = body if colour == "body" else GREY[colour]
        cv2.fillPoly(img, [np.round(pts).astype(np.int32)], int(g), lineType=cv2.LINE_8,
                     shift=SHIFT)
    return np.round(img.astype(np.float32).reshape(H, ss, W, ss).mean(axis=(1, 3))).astype(np.uint8)


def _read(img, plan):
    return D.detect(img, plan.data)["ids"]


@pytest.mark.parametrize("chunk", range(CHUNKS))
def test_the_mesh_reads_as_the_layers_do(chunk):
    cases = [c for c in G.cases("legacy") + G.cases("matrix") if "error" not in c["out"]]
    bad = []
    n = 0
    for c in cases[chunk::CHUNKS]:
        p = plan_tag(TagSpec.from_dict(c["in"]))
        r = top_view(p, px_per_mm=12.0, ss=2)
        ids = set(p.data["ids"])
        want = [i for i in _read(r.img, p) if i in ids]
        got = [i for i in _read(mesh_raster(p, r), p) if i in ids]
        n += 1
        # the plan's own ids, every one, in both. (A plain ArucoDetector can
        # also "find" a marker in a ChArUco label's text -- docs/status/M2.md,
        # findings -- so ids that are not the plan's are not compared.)
        if got != want or set(want) != ids:
            bad.append((c["id"], sorted(ids), want, got))
    assert n > 50
    assert not bad, bad[:5]


def test_a_twelve_tag_scene_reads_every_id_where_it_was_put():
    sc = Scene(name="twelve")
    k = 0
    for layout, area in (("single", (40, 40)), ("grid", (90, 60)), ("charuco", (90, 70))):
        for j in range(4):
            sc.add(TagSpec(settings={"layout": layout, "mode": "both", "op": "new"},
                           target=T.box(*area, 0)),
                   x_mm=110 * j, y_mm=100 * k, rotation_deg=[0, 30, 90, 200][j])
        k += 1
    renumber(sc)
    rep = verify_scene(sc, px_per_mm=10.0)
    assert len(sc.tags) == 12
    assert rep["ok"] and rep["found"] == rep["markers"] > 12, rep["missing"]
    assert rep["worst_err_mm"] < 0.1, rep["worst_err_mm"]
