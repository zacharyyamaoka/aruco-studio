"""The sheet's paper is the preset's (review finding #9, 2026-10-21): a
custom page size prints at that size, and a named page given landscape
(page_mm wider than tall) prints landscape; a built-in prints as before.
Before, both fell back to a named portrait page (custom: Letter) without a word."""
from __future__ import annotations

import re

from aruco_studio import web_api as W

from test_web_api import INK, req

_SIZE = re.compile(r'<svg[^>]* width="([\d.]+)mm" height="([\d.]+)mm"')


def page_mm(got):
    w, h = _SIZE.search(got["svg"][0]).groups()
    return float(w), float(h)


def sheet_of(pre):
    return W.sheet({"items": [req(pre=pre)], "cut_lines": True}, "2026-10-21")


def test_a_custom_page_prints_at_its_size():
    got = sheet_of(dict(INK, page="Custom", page_mm=[100.0, 100.0], margin_mm=5.0))
    assert page_mm(got) == (100.0, 100.0)
    assert got["pages"] == 1 and not [w for w in got["warnings"] if w["level"] == "error"]
    assert "not one the sheet prints" not in " ".join(w["text"] for w in got["warnings"])


def test_a_landscape_named_page_prints_landscape():
    assert page_mm(sheet_of(dict(INK, page="A4", page_mm=[297.0, 210.0]))) == (297.0, 210.0)
    assert page_mm(sheet_of(dict(INK, page="Custom", page_mm=[297.0, 210.0]))) == (297.0, 210.0)


def test_a_built_in_page_prints_as_it_did():
    before = sheet_of(INK)
    assert page_mm(before) == (215.9, 279.4)
    # no page_mm at all: the named page, portrait
    bare = dict(INK)
    bare.pop("page_mm")
    assert sheet_of(bare)["svg"] == before["svg"]


def test_the_plan_does_not_say_letter_for_a_custom_page():
    plan = W.plan(req(pre=dict(INK, page="Custom", page_mm=[100.0, 100.0])))
    text = " ".join(w["text"] for w in plan["warnings"])
    assert "not one the sheet prints" not in text
