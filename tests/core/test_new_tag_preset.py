"""The new-tag preset (2026-10-17, CF-13: Zach prints tags only by inkjet on
vinyl): core.presets.NEW_TAG_PRESET and new_tag_preset() are the one home
of the rule "a brand-new tag that names no preset is an 'Inkjet · Letter
vinyl' sticker". The Fusion add-in vendors this module (stdlib only)."""
from __future__ import annotations

import ast
import sys

from aruco_studio.core import form as F
from aruco_studio.core import presets as P


def test_the_constant_names_the_vinyl_letter_builtin():
    assert P.NEW_TAG_PRESET == "Inkjet · Letter vinyl"
    assert P.NEW_TAG_PRESET == P.vinyl_preset("letter")["name"]
    assert P.NEW_TAG_PRESET != P.DEFAULT and not P.is_legacy(P.NEW_TAG_PRESET)


def test_new_tag_preset_is_the_vinyl_letter_preset_as_a_fresh_copy():
    p = P.new_tag_preset()
    assert p == P.vinyl_preset("letter") and p["name"] == P.NEW_TAG_PRESET
    pr = p["profile"]
    assert P.kind_of(p) == "sticker" and pr["make_rule"] == 2
    assert (pr["page"], pr["dpi"], pr["stock_mm"]) == ("letter", 600, P.VINYL_STOCK_MM)
    assert P.normalise(p) == p
    p["profile"]["page"] = "a4"
    p["tag"]["mode"] = "black"
    q = P.new_tag_preset()
    assert q["profile"]["page"] == "letter" and q["tag"]["mode"] == "both"


def test_it_is_a_builtin_of_the_studio_catalog():
    cat = P.catalog_all(P.MemoryStore())
    got, kind = P.find(cat, P.NEW_TAG_PRESET)
    assert kind == "builtin" and got == P.new_tag_preset()
    # Default stays the 3D built-in it was
    d, dk = P.find(cat, P.DEFAULT)
    assert dk == "builtin" and P.kind_of(d) == "print3d" and d == P.default_preset()


def test_a_new_tag_under_it_is_a_rule_2_vinyl_sticker():
    s = F.new_tag_settings({"layout": "single", "mode": "auto", "op": "join", "pin": "triangle",
                            "trim": "outline"}, True, preset=P.new_tag_preset())
    mk = s["make"]
    assert mk["by"] == "sticker" and mk["rule"] == 2
    assert mk["page"] == "letter" and mk["thickness_mm"] == P.VINYL_STOCK_MM
    assert (s["mode"], s["op"], s["pin"], s["grow"]) == ("both", "new", "none", False)
    assert "trim" not in s


def test_presets_imports_only_the_stdlib_and_its_package():
    tree = ast.parse(open(P.__file__, encoding="utf-8").read())
    absolute = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            absolute |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            absolute.add((node.module or "").split(".")[0])
    absolute.discard("__future__")
    assert absolute <= set(sys.stdlib_module_names), absolute - set(sys.stdlib_module_names)
