"""Every golden says where it came from (PLAN M1.11, 3.3; D15).

Each file under goldens/ carries `ref_commit`, `maker` (a path under REF:
the REF file whose code made the numbers) and `sha256`; a non-JSON file is
listed with its sha256 in its folder's provenance.json. And a golden's
maker refuses to run on the new code: tools/make_goldens_from_ref.py exits
2 when aruco_studio is importable.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GOLDENS = ROOT / "goldens"
sys.path.insert(0, str(ROOT / "tools"))
import ref_path  # noqa: E402

FILES = sorted(p for p in GOLDENS.rglob("*") if p.is_file())


def test_there_are_goldens():
    names = {p.stem for p in GOLDENS.glob("*.json")}
    assert {"dictionary", "board", "origin", "slabs", "chamfer", "autosize", "label", "trim",
            "numbering", "restructure", "jo_maths", "presets", "prusa", "settings", "form",
            "preset_library"} <= names
    assert {p.name for p in (GOLDENS / "ref").glob("*.json")} == {
        "aruco_cells_legacy_golden.json", "aruco_label_rule1_golden.json",
        "aruco_trim_legacy_golden.json", "aruco_label_gim43_disc.json"}


@pytest.mark.parametrize("path", [p for p in FILES if p.suffix == ".json" and p.name != "provenance.json"],
                         ids=lambda p: p.relative_to(GOLDENS).as_posix())
def test_json_golden_has_provenance(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["ref_commit"] == ref_path.REF_COMMIT
    assert doc["maker"].startswith(str(ref_path.REF)), doc["maker"]
    assert doc.get("sha256"), "no sha256"
    assert doc["made_by"].startswith("tools/make_goldens_from_ref.py")
    if isinstance(doc["sha256"], dict):
        for rel, digest in doc["sha256"].items():
            assert len(digest) == 64 and not rel.startswith(("aruco_studio", "/")), rel


@pytest.mark.parametrize("path", [p for p in FILES if p.suffix != ".json"],
                         ids=lambda p: p.relative_to(GOLDENS).as_posix())
def test_other_files_are_in_a_manifest(path):
    man = json.loads((path.parents[len(path.relative_to(GOLDENS).parts) - 2] / "provenance.json")
                     .read_text(encoding="utf-8"))
    rel = path.relative_to(path.parents[len(path.relative_to(GOLDENS).parts) - 2]).as_posix()
    assert man["ref_commit"] == ref_path.REF_COMMIT and man["maker"].startswith(str(ref_path.REF))
    assert man["sha256"][rel] == hashlib.sha256(path.read_bytes()).hexdigest(), rel


@pytest.mark.skipif(not (ref_path.REF / ".git").exists(), reason="REF is not on this machine")
def test_copied_goldens_equal_refs_files_at_the_pinned_commit():
    for p in (GOLDENS / "ref").glob("*.json"):
        doc = json.loads(p.read_text(encoding="utf-8"))
        raw = ref_path.show(doc["source"])
        assert hashlib.sha256(raw).hexdigest() == doc["sha256"]
        assert json.loads(raw.decode("utf-8")) == doc["golden"], p.name


def test_the_maker_refuses_to_run_on_the_new_code(tmp_path):
    """--child with aruco_studio importable (ROOT on PYTHONPATH, no -I): exit 2."""
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "make_goldens_from_ref.py"), "--child",
                        str(ref_path.REF), str(ROOT / "tools"), str(tmp_path), "board"],
                       cwd=str(ROOT), env=env, capture_output=True, text=True)
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert "REFUSED" in p.stderr
    assert not list(tmp_path.iterdir())
