"""M8c.3, M8c.4, M8c.6 (the route), M8c.8: PrusaSlicer over HTTP
(server/prusa_api.py), tested with FastAPI's TestClient (no port).

* GET /api/prusa/printers lists the fixture's five physical printers with
  their fitting prints; `current` marks the pair PrusaSlicer has selected;
* the Library's Printers collection has one card each; Select makes a
  preset with that printer's nozzle and that print's line and layers;
* the allow-list: a physical printer and the printer presets with every
  host key set to a marker: the marker is in no answer, no Library JSON,
  no 3MF, no log line;
* POST /api/scene/send/prusaslicer writes the project; `open: false` in
  every test (PrusaSlicer is never launched: the opener is replaced by one
  that fails the test); the sticker example answers 400 "nothing to slice";
* nothing is written under the PrusaSlicer folder.
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "prusaslicer_m8c"
EX = ROOT / "examples"
MARK = "MARKER-51d2-never-leaves"
MK4_04 = "Original Prusa MK4 MMU3 0.4 nozzle - (Black, Clear, White)"
MK4_06 = "Original Prusa MK4 MMU3 0.6 nozzle - (Black, Clear, White)"
HOST_KEYS = ("print_host", "printhost_apikey", "printhost_authorization_type", "printhost_cafile",
             "printhost_password", "printhost_port", "printhost_ssl_ignore_revoke",
             "printhost_user")


def folder_hash(d: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p for p in d.rglob("*") if p.is_file()):
        h.update(f.relative_to(d).as_posix().encode("utf-8") + b"\0" + f.read_bytes())
    return h.hexdigest()


def mark(d: Path) -> None:
    """Every host key of ontario and of the user printer presets set to the marker."""
    for f in [d / "physical_printer" / "ontario.ini"] + sorted((d / "printer").glob("*.ini")):
        kept = [ln for ln in f.read_text(encoding="utf-8").splitlines()
                if ln.split("=", 1)[0].strip() not in HOST_KEYS]
        f.write_text("\n".join(kept + [f"{k} = {MARK}-{k}" for k in HOST_KEYS]) + "\n",
                     encoding="utf-8")


@pytest.fixture()
def env(tmp_path, monkeypatch):
    ps = tmp_path / "PrusaSlicer"
    shutil.copytree(FIX, ps)
    monkeypatch.setenv("ARUCO_STUDIO_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ARUCO_STUDIO_SCENES", str(tmp_path / "scenes"))
    monkeypatch.setenv("BAM_ARUCO_PRUSASLICER_DIR", str(ps))
    from aruco_studio.scene import Scene
    from aruco_studio.server import app as A
    from aruco_studio.server import beds_io as BI
    from aruco_studio.server import design_api as DA
    from aruco_studio.server import prusa_api  # noqa: F401  (the include line, M8c)

    def never(*a, **k):
        raise AssertionError("PrusaSlicer must not be opened by a test")
    monkeypatch.setattr(BI, "open_in_prusaslicer", never)
    A.STATE["scene"] = Scene(name="untitled")
    c = TestClient(A.app)              # not `with`: the folder's watcher is not started here
    yield c, ps, tmp_path, DA
    DA.D.unbind()


def open_example(c, tmp_path, name):
    p = tmp_path / f"{name}.arucostudio.json"
    shutil.copy(EX / f"{name}.arucostudio.json", p)
    r = c.post("/api/design/open", json={"path": str(p)})
    assert r.status_code == 200, r.text
    return p


# ------------------------------------------------------------------ M8c.4

def test_printers_lists_the_five_with_their_fitting_prints(env):
    c, ps, _tmp, _DA = env
    before = folder_hash(ps)
    r = c.get("/api/prusa/printers").json()
    assert r["found"] and r["notes"] == []
    by = {e["name"]: e for e in r["printers"]}
    assert sorted(by) == ["Haribo", "Le Mis", "aburi", "kappa", "ontario"]
    assert [p["name"] for p in by["Haribo"]["prints"]] == ["0.32mm ERGO @COREONE 0.6"]
    assert len(by["aburi"]["prints"]) == 5
    assert by["kappa"]["printer"]["model"] == "MK3.5" and by["kappa"]["printer"]["nozzle_mm"] == 0.6
    assert r["current"] == {"physical": "ontario", "printer": MK4_04,
                            "print": "0.20mm SPEED @MK4IS 0.4"}
    assert [e["name"] for e in r["printers"] if e["current"]] == ["ontario"]
    cur = [p for p in by["ontario"]["prints"] if p.get("current")]
    assert [p["name"] for p in cur] == ["0.20mm SPEED @MK4IS 0.4"]
    for e in r["printers"]:
        assert set(e["printer"]) >= {"preset", "nozzle_mm", "model", "variant", "bed_mm"}
        assert "config" not in e["printer"]
        assert all(p["fits"] in ("yes", "maybe") for p in e["prints"])
    allp = c.get("/api/prusa/printers?system=1").json()
    n_sys = {e["name"]: len(e["prints"]) for e in allp["printers"]}
    assert n_sys["Haribo"] > 1
    assert folder_hash(ps) == before                   # read only


def test_the_library_has_one_printers_card_each_and_select_makes_the_pair(env):
    c, _ps, _tmp, _DA = env
    st = c.get("/api/library").json()
    cols = {x["id"]: x for x in st["collections"]}
    assert cols["printers"]["count"] == 5 and cols["printers"]["name"] == "Printers"
    assert cols["stickers"]["count"] == 2           # the two sticker built-ins (M6a)
    cards = [x for x in st["cards"] if x["kind"] == "printer"]
    assert sorted(x["name"] for x in cards) == ["Haribo", "Le Mis", "aburi", "kappa", "ontario"]
    on = next(x for x in cards if x["name"] == "ontario")
    assert on["current"] and on["default"] == "printer:ontario|0.20mm SPEED @MK4IS 0.4"
    assert [ch["current"] for ch in on["choices"]] == [True]
    ha = next(x for x in cards if x["name"] == "Haribo")
    choice = ha["choices"][0]
    r = c.post("/api/library/select", json={"id": choice["id"]})
    assert r.status_code == 200, r.text
    got = r.json()
    pr = got["preset"]["profile"]
    assert got["name"] == "Haribo · 0.32mm ERGO @COREONE 0.6"
    assert (pr["nozzle_mm"], pr["line_mm"], pr["layer_mm"], pr["first_layer_mm"]) == \
        (0.6, 0.68, 0.32, 0.2)
    assert pr["printer"] == {"physical": "Haribo", "preset": "Prusa CORE One 0.6 nozzle",
                             "model": "COREONE", "variant": "0.6"}
    assert got["preset"]["cells"]["of"] == "cell"      # every cell a whole number of lines
    mine = [x["name"] for x in c.get("/api/library").json()["cards"] if x["kind"] == "user"]
    assert mine == [got["name"]]                       # imported as yours
    r2 = c.post("/api/library/select", json={"id": "printer:ontario"}).json()   # the default
    assert r2["preset"]["profile"]["nozzle_mm"] == 0.4 and r2["preset"]["profile"]["line_mm"] == 0.45
    assert c.post("/api/library/select", json={"id": "printer:nobody"}).status_code == 404


# ------------------------------------------------------------------ M8c.6 (the route), M8c.8

def test_send_writes_the_project_and_never_opens_prusaslicer(env):
    c, ps, tmp, _DA = env
    before = folder_hash(ps)
    open_example(c, tmp, "forearm")
    r = c.post("/api/scene/send/prusaslicer",
               json={"printer": MK4_06, "print": "0.32mm SPEED @MK4IS 0.6 - Aruco", "open": False})
    assert r.status_code == 200, r.text
    a = r.json()
    assert Path(a["project"]).is_file() and a["opened"] is False
    assert a["printer"] == {"physical": None, "preset": MK4_06}
    assert a["filament"] == "Prusament PLA @PGIS 0.6" and a["beds"] == 1
    assert [p["name"] for p in a["parts"]] == ["forearm"]
    assert len(a["parts"][0]["volumes"]) == 5 and a["bed_mm"] == [250.0, 210.0]
    with zipfile.ZipFile(a["project"]) as z:
        assert "Metadata/Slic3r_PE.config" in z.namelist()
    assert not str(Path(a["project"])).startswith(str(ps))
    # a physical printer: its preset and its default print; the current one when selected
    r = c.post("/api/scene/send/prusaslicer", json={"printer": "ontario", "open": False}).json()
    assert r["printer"] == {"physical": "ontario", "preset": MK4_04}
    assert r["print"] == "0.20mm SPEED @MK4IS 0.4"
    with zipfile.ZipFile(r["project"]) as z:
        cfg = z.read("Metadata/Slic3r_PE.config").decode("utf-8")
    assert "; physical_printer_settings_id = ontario" in cfg
    r = c.post("/api/scene/send/prusaslicer", json={"open": False}).json()   # nothing chosen
    assert r["printer"]["physical"] == "ontario"
    assert c.post("/api/scene/send/prusaslicer",
                  json={"printer": "nobody", "open": False}).status_code == 404
    assert c.post("/api/scene/send/prusaslicer", json={"print": "nope", "open": False,
                                                       "printer": MK4_06}).status_code == 404
    assert folder_hash(ps) == before


def test_open_true_calls_the_opener_once(env, monkeypatch):
    c, _ps, tmp, _DA = env
    from aruco_studio.server import beds_io as BI
    calls = []
    monkeypatch.setattr(BI, "open_in_prusaslicer",
                        lambda path, single_instance=True: calls.append(path) or
                        {"opened": True, "command": ["prusa-slicer", path], "error": None})
    open_example(c, tmp, "plate_charuco")
    a = c.post("/api/scene/send/prusaslicer", json={"printer": MK4_06}).json()
    assert calls == [a["project"]] and a["opened"] is True


def test_stickers_answer_nothing_to_slice(env):
    c, _ps, tmp, _DA = env
    open_example(c, tmp, "sticker_sheet")
    r = c.post("/api/scene/send/prusaslicer", json={"open": False})
    assert r.status_code == 400
    assert r.json()["detail"] == "nothing to slice: stickers print on paper"


def test_no_folder_says_so(env, monkeypatch, tmp_path):
    c, _ps, tmp, _DA = env
    monkeypatch.setenv("BAM_ARUCO_PRUSASLICER_DIR", str(tmp_path / "nowhere"))
    monkeypatch.delenv("APPDATA", raising=False)
    r = c.get("/api/prusa/printers").json()
    assert r["found"] is False and r["notes"] == ["PrusaSlicer's folder not found"]
    open_example(c, tmp, "plate_charuco")
    a = c.post("/api/scene/send/prusaslicer", json={"open": False}).json()
    assert Path(a["project"]).is_file()
    assert any("carries no config" in w for w in a["warnings"])
    with zipfile.ZipFile(a["project"]) as z:
        assert "Metadata/Slic3r_PE.config" not in z.namelist()


# ------------------------------------------------------------------ M8c.3

def test_the_marker_is_nowhere(env, caplog):
    c, ps, tmp, _DA = env
    mark(ps)
    raw = (ps / "physical_printer" / "ontario.ini").read_text(encoding="utf-8")
    assert raw.count(MARK) == len(HOST_KEYS)
    caplog.set_level(logging.DEBUG)
    out = []
    out.append(c.get("/api/prusa/printers").text)
    out.append(c.get("/api/prusa/printers?system=1").text)
    out.append(c.get("/api/library").text)
    sel = c.post("/api/library/select", json={"id": "printer:ontario"})
    out.append(sel.text)
    out.append(c.get("/api/presets").text)
    out.append(c.get("/api/prusa/stale").text)
    open_example(c, tmp, "forearm")
    for body in ({"printer": "ontario", "open": False}, {"printer": MK4_06, "open": False}):
        r = c.post("/api/scene/send/prusaslicer", json=body)
        assert r.status_code == 200, r.text
        out.append(r.text)
        with zipfile.ZipFile(r.json()["project"]) as z:
            for n in z.namelist():
                out.append(z.read(n).decode("utf-8", errors="replace"))
    home = tmp / "home"
    for f in home.rglob("*"):
        if f.is_file():
            out.append(f.read_bytes().decode("utf-8", errors="replace"))
    out += [rec.getMessage() for rec in caplog.records]
    hits = [i for i, t in enumerate(out) if MARK in t]
    assert not hits, hits
    assert any("printhost" not in t for t in out)


def test_nothing_is_written_under_zachs_prusaslicer_folder():
    """The store refuses a write there (and under the folder the env points at)."""
    from aruco_studio.server import store as S
    appdata = os.environ.get("APPDATA")
    if appdata:
        with pytest.raises(S.StoreError):
            S.write_atomic(Path(appdata) / "PrusaSlicer" / "x.ini", "no")
    os.environ["BAM_ARUCO_PRUSASLICER_DIR"] = str(FIX)
    try:
        with pytest.raises(S.StoreError):
            S.write_atomic(FIX / "x.ini", "no")
    finally:
        del os.environ["BAM_ARUCO_PRUSASLICER_DIR"]
    assert not (FIX / "x.ini").exists()


def test_the_gui_and_its_single_instance_flag_are_found_but_not_run():
    """M8c.8: where the GUI is on this box (docs/status/M8c.md); the console's
    --help (headless, a scratch datadir) says whether --single-instance exists."""
    from aruco_studio.server import beds_io as BI
    from aruco_studio.verify import slice_check as SC
    gui = BI.find_prusaslicer_gui()
    con = SC.find_console()
    if gui is None or con is None:
        pytest.skip("PrusaSlicer is not installed on this machine")
    assert Path(gui).name.lower().startswith("prusa-slicer") and Path(gui).is_file()
    assert BI.single_instance_ok(con) is True
