"""One report per check: ids expected / read, the corner error against the
plan (px and mm), the PnP pose error, the PNG written (when asked)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2

from . import detect as _det
from . import pnp as _pnp
from .render import top_view


def verify_plan(plan, target: Optional[dict] = None, px_per_mm: float = 20.0, pose: bool = True,
                png: Optional[str] = None) -> dict:
    """The plan read back by OpenCV: frontal (ids, corners), and through a
    camera 25 deg off (the pose)."""
    d = plan.to_dict() if hasattr(plan, "to_dict") else plan
    if not d.get("ok"):
        return {"ok": False, "errors": list(d.get("errors") or []), "ids_expected": [],
                "ids_read": []}
    r = top_view(d, px_per_mm=px_per_mm, target=target)
    rep = _det.check(r, d)
    rep["px_per_mm"] = px_per_mm
    if png:
        Path(png).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(png), r.img)
        rep["png"] = str(png)
    if pose:
        pc = _pnp.pose_check(d, target=target)
        rep["pnp_err_mm"], rep["pnp_err_deg"] = pc["err_mm"], pc["err_deg"]
        rep["pnp"] = pc["info"]
        rep["ok"] = bool(rep["ok"] and pc["ok"])
    return rep


def verify_scene(scene, px_per_mm: float = 10.0, png: Optional[str] = None) -> dict:
    """A scene's sheet read back: every tag's markers found, each centre
    against where the scene puts it (mm), and no two tags overlapping."""
    from .scene_check import check_scene, scene_raster
    plans = scene.plans()
    r = scene_raster(scene, plans, px_per_mm=px_per_mm)
    rep = check_scene(r, scene, plans)
    rep["px_per_mm"] = px_per_mm
    rep["tags"] = {t.name: {"ok": plans[t.name].ok, "ids": plans[t.name].data["ids"]}
                   for t in scene.tags}
    # tags whose targets overlap on the canvas (scene/checks.py): the sheet
    # is not as planned even when every marker is still found (audit F13)
    from ..scene.checks import overlaps
    rep["overlaps"] = overlaps(scene)
    rep["markers_ok"] = rep["ok"]
    rep["ok"] = bool(rep["ok"]) and not rep["overlaps"]
    if png:
        Path(png).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(png), r.img)
        rep["png"] = str(png)
    return rep
