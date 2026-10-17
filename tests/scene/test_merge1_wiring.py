"""Merge 1 (M6a + M8a): the wiring between the two lanes.

- The design file's preset names reach the sticker printers (M6a's
  catalog_all), so the sticker example's tags plan as stickers.
- plan/newtag.new_spec stamps `make` from its preset, as /api/new does.
- app.py serves M6a's sheet routes (the include line).
"""
from __future__ import annotations

import json
from pathlib import Path

from aruco_studio.core import presets as _P
from aruco_studio.plan import newtag as _NEW
from aruco_studio.scene import design as _DS
from aruco_studio.server.design_api import resolver

ROOT = Path(__file__).resolve().parents[2]
TARGET = {"kind": "face", "w_mm": 40.0, "h_mm": 40.0, "loops_mm": [], "has_body": False}


def test_new_spec_takes_make_from_a_sticker_preset():
    sp = _NEW.new_spec("single", TARGET, _P.sticker_builtins()[0])
    assert sp["settings"]["make"]["by"] == "sticker"
    assert sp["settings"]["mode"] == "both" and sp["settings"]["pin"] == "none"


def test_new_spec_3d_is_as_before():
    a = _NEW.new_spec("single", TARGET, None)
    b = _NEW.new_spec("single", TARGET, _P.default_preset())
    assert a["settings"]["make"] == b["settings"]["make"] == {"rule": 1, "by": "print3d"}


def test_resolver_finds_the_sticker_printers():
    get = resolver()
    for p in _P.sticker_builtins():
        assert get(p["name"]) is not None


def test_sticker_example_plans_as_stickers():
    doc = json.loads((ROOT / "examples" / "sticker_sheet.arucostudio.json").read_text(encoding="utf-8"))
    sc, issues = _DS.compile(doc, resolver())
    assert not [i for i in issues if i.level == "error"], issues
    assert not [i for i in issues if "no preset" in i.text], issues
    plans = sc.plans()
    assert len(plans) == 4
    for name, p in plans.items():
        assert p.data.get("made_by") == "sticker", name


def test_app_serves_the_sheet_routes():
    from aruco_studio.server.app import app
    paths = {getattr(r, "path", "") for r in app.router.routes}
    assert {"/api/scene/sheet.svg", "/api/scene/print.pdf", "/api/scene/export/print",
            "/api/scene/verify/sheet"} <= paths
