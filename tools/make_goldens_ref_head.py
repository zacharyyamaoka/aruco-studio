"""Make goldens/ref_head/charuco_print.json from REF's OWN code at ref_path.REF_HEAD.

    .venv/Scripts/python tools/make_goldens_ref_head.py

N-1 (2026-10-17): the core was brought up to the add-in at REF_HEAD
(numbering 4c8810b, markers + print_sheet da6e622). This golden pins what
REF's core does there, so the Studio's port keeps doing it:

* REF's CADExporter/bam_cad_core is taken from the commit with `git archive`
  (never REF's working tree) into a temp directory;
* the work runs in a child `python -I -B` from that directory, REF's
  bam_cad_core first on sys.path; the child refuses (exit 2) when
  `aruco_studio` is importable or already imported;
* the scenario (tools/ref_head_scenario.py, stdlib only) is handed REF's
  modules; its sha256 is in the golden, so a changed scenario needs a new
  golden.

The file holds `ref_commit` (REF_HEAD), `maker` (REF's print_sheet.py, as a
path under REF), `made_by`, the REF files' sha256, the scenario's, the date.
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from datetime import date
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
OUT = ROOT / "goldens" / "ref_head" / "charuco_print.json"
SCENARIO = TOOLS / "ref_head_scenario.py"
FILES = ("CADExporter/bam_cad_core/markers.py", "CADExporter/bam_cad_core/print_sheet.py",
         "CADExporter/bam_cad_core/aruco_numbering.py", "CADExporter/bam_cad_core/aruco_label.py",
         "CADExporter/bam_cad_core/aruco_chamfer.py", "CADExporter/bam_cad_core/aruco_board.py",
         "CADExporter/bam_cad_core/aruco_dict.py", "CADExporter/bam_cad_core/fiducials.py")

CHILD = r"""
import importlib.util, json, sys
if importlib.util.find_spec("aruco_studio") is not None or "aruco_studio" in sys.modules:
    sys.exit(2)
sys.path.insert(0, sys.argv[1])
from bam_cad_core import markers as M, print_sheet as PS, aruco_label as AL
from bam_cad_core import aruco_chamfer as CH, aruco_numbering as N
spec = importlib.util.spec_from_file_location("ref_head_scenario", sys.argv[2])
sc = importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
print(json.dumps(sc.run(M, PS, AL, CH, N), sort_keys=True))
"""


def main():
    sys.path.insert(0, str(TOOLS))
    import ref_path
    commit = ref_path.git("rev-parse", ref_path.REF_HEAD).strip()
    tar = subprocess.run(["git", "-C", str(ref_path.REF), "archive", "--format=tar", commit,
                          "CADExporter/bam_cad_core"], capture_output=True, check=True).stdout
    with tempfile.TemporaryDirectory(prefix="aruco_ref_head_") as tmp:
        with tarfile.open(fileobj=io.BytesIO(tar)) as tf:
            tf.extractall(tmp)
        p = subprocess.run([sys.executable, "-I", "-B", "-X", "utf8", "-c", CHILD,
                            str(Path(tmp) / "CADExporter"), str(SCENARIO)],
                           cwd=tmp, capture_output=True)
    if p.returncode:
        raise SystemExit(f"child exit {p.returncode}: {p.stderr.decode('utf-8', 'replace')[-2000:]}")
    golden = json.loads(p.stdout.decode("utf-8").strip().splitlines()[-1])
    doc = {"ref_commit": ref_path.REF_HEAD, "ref_commit_full": commit,
           "maker": str(ref_path.REF / "CADExporter" / "bam_cad_core" / "print_sheet.py"),
           "made_by": "tools/make_goldens_ref_head.py (REF's bam_cad_core from git archive, "
                      "python -I, tools/ref_head_scenario.py)",
           "sha256": {f: hashlib.sha256(ref_path.show(f, commit)).hexdigest() for f in FILES},
           "scenario_sha256": hashlib.sha256(SCENARIO.read_bytes().replace(b"\r\n", b"\n"))
           .hexdigest(),
           "date": date.today().isoformat(), "golden": golden}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(golden)} answers from REF {commit[:12]}")


if __name__ == "__main__":
    main()
