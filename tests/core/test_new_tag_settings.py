"""One home for a new tag's settings rule (audit C4).

`core.form.new_tag_settings` stamps the Origin rule and resolves Extrude
Auto; `core.form.mode_for` is the Auto rule on a plain value. The plan,
the Studio's new tag, the core's edit merge and the Fusion adapter call
them; no other file spells the rule again.
"""
import re
from pathlib import Path

from aruco_studio.core import form as F
from aruco_studio.core import origin as OR
from aruco_studio.core import settings as S

ROOT = Path(__file__).resolve().parents[2]


def test_new_tag_settings_stamps_origin_and_resolves_auto():
    s = dict(S.default_settings(), mode="auto")
    s.pop("origin_v", None)
    on_body = F.new_tag_settings(s, True)
    no_body = F.new_tag_settings(s, False)
    assert on_body["origin_v"] == OR.ORIGIN_RULE and no_body["origin_v"] == OR.ORIGIN_RULE
    assert on_body["mode"] == "black" and no_body["mode"] == "both"
    assert s["mode"] == "auto" and "origin_v" not in s            # a copy: the input is kept
    assert F.new_tag_settings(dict(s, mode="white"), True)["mode"] == "white"


def test_mode_for_is_resolve_mode():
    for mode in ("auto", "both", "black", "white"):
        for body in (True, False):
            assert F.mode_for(mode, body) == F.resolve_mode({"mode": mode}, body)["mode"]


def test_the_auto_rule_is_written_once():
    rx = re.compile(r'"black" if [^\n]*has_body[^\n]* else "both"')
    hits = []
    for p in (ROOT / "aruco_studio").rglob("*.py"):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if rx.search(line):
                hits.append(f"{p.relative_to(ROOT).as_posix()}:{i}")
    assert hits == ["aruco_studio/core/form.py:237"], hits


def test_the_adapter_stamps_no_rule_itself():
    src = (ROOT / "aruco_studio" / "adapters" / "fusion" / "feature.py").read_text(encoding="utf-8")
    assert "ORIGIN_RULE" not in src
    assert "new_tag_settings" in src
