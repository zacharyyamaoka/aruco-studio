"""The evaluate() goldens came from REF (PLAN 3.3, D15): their maker refuses
to run where aruco_studio is importable; every file names REF's pinned
blobs it ran; the stand-ins are listed."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import ref_path  # noqa: E402


def test_the_maker_refuses_to_run_on_the_new_code(tmp_path):
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "make_evaluate_goldens.py"), "--child",
                        str(ref_path.REF), str(ROOT / "tools"), str(tmp_path)],
                       cwd=str(ROOT), env=env, capture_output=True, text=True)
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    assert "REFUSED" in p.stderr
    assert not list(tmp_path.iterdir())


def test_every_evaluate_golden_names_refs_code():
    for name in ("matrix", "legacy"):
        d = json.loads((ROOT / "goldens" / "evaluate" / f"{name}.json").read_text(encoding="utf-8"))
        assert d["ref_commit"] == ref_path.REF_COMMIT
        assert Path(d["maker"]).as_posix().endswith("ArucoMarkers/aruco_feature.py")
        assert "tests/aruco_trim_fixtures.py" in d["sha256"]
        assert "ArucoMarkers/aruco_feature.py" in d["sha256"]
        assert "CADExporter/bam_cad_core/aruco_label.py" in d["sha256"]
        assert all(len(v) == 64 for v in d["sha256"].values())
        assert "stand_ins" in d["args"]
