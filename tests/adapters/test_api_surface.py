"""The adapter's Fusion protocol, and that nothing imports adsk for real
(PLAN M4.8).

* `import aruco_studio.adapters.fusion` with no adsk in sys.modules raises
  RuntimeError naming fake_adsk.install(); the host-neutral recipe imports
  without adsk and loads none;
* no module outside aruco_studio/adapters/fusion imports adsk;
* every `adsk.core.X` / `adsk.fusion.X` the adapter names is in
  api.SURFACE, and the stand-in has each of them;
* every Fusion-style (camelCase) attribute the adapter calls is listed in
  api.METHODS, and the stand-in's source defines each listed name.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import fake_adsk as FK
from aruco_studio.adapters.fusion import api

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "aruco_studio"
FUSION = PKG / "adapters" / "fusion"
FAKE = Path(FK.__file__)


def _run(code):
    return subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), capture_output=True,
                          text=True)


def test_the_package_refuses_without_adsk():
    p = _run("import sys\nassert 'adsk' not in sys.modules\n"
             "try:\n    import aruco_studio.adapters.fusion\n"
             "except RuntimeError as e:\n    print('RAISED', e)\n")
    assert p.returncode == 0, p.stderr
    assert p.stdout.startswith("RAISED") and "fake_adsk.install()" in p.stdout


def test_the_recipe_needs_no_adsk():
    p = _run("import sys\nimport aruco_studio.adapters.recipe\n"
             "print(','.join(k for k in sys.modules if k.split('.')[0] == 'adsk'"
             " or k.startswith('aruco_studio.adapters.fusion')))\n")
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == ""


def test_only_the_fusion_adapter_imports_adsk():
    hits = []
    for f in PKG.rglob("*.py"):
        if FUSION in f.parents:
            continue
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            hits += [f"{f.relative_to(ROOT)}:{node.lineno}" for n in names
                     if n.split(".")[0] == "adsk"]
    assert not hits, hits


def _adapter_source():
    return {f.name: f.read_text(encoding="utf-8") for f in sorted(FUSION.glob("*.py"))}


def test_every_adsk_name_is_in_the_surface_and_the_stand_in():
    used = set()
    for text in _adapter_source().values():
        used |= set(re.findall(r"\badsk\.(?:core|fusion)\.[A-Z]\w*", text))
    missing = sorted(used - api.SURFACE)
    assert not missing, missing
    absent = []
    for name in sorted(api.SURFACE):
        _adsk, mod, cls = name.split(".")
        if not hasattr(sys.modules[f"adsk.{mod}"], cls):
            absent.append(name)
    assert not absent, absent


def test_every_fusion_attribute_is_in_the_protocol():
    listed = {m for ms in api.METHODS.values() for m in ms}
    used = set()
    for name, text in _adapter_source().items():
        if name == "api.py":
            text = text.split("METHODS = {", 1)[0] + text.split("\n}\n", 1)[-1]
        used |= set(re.findall(r"\.([a-z]+[A-Z][A-Za-z0-9]*)\b", text))
    assert not sorted(used - listed), sorted(used - listed)
    fake = FAKE.read_text(encoding="utf-8")
    absent = sorted(m for m in listed if not re.search(rf"\b{re.escape(m)}\b", fake))
    assert not absent, absent
