"""M8c.6: Send to PrusaSlicer's project (scene/print3d.py), read back WITHOUT
our code (zipfile + ElementTree, as REF's tools/verify_print_beds.py).

The three example files: the forearm is ONE object (its body and four
tags' volumes), the plate its body and one tag's, the sticker sheet
nothing ("stickers print on paper"). The examples' preset prints the
black inset into the body (Extrude Auto -> black only), so their tags have
a black volume and no white or negative one; the same files with New-body
tiles (`"mode": "both", "op": "new"`) give the white, the black and the
negative volume (the pins' sockets) of every tag: 1 + 4 x 3 on the forearm.
"""
from __future__ import annotations

import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

import pytest

from aruco_studio.core import beds as BD
from aruco_studio.core import presets as P
from aruco_studio.core import prusa as PR
from aruco_studio.plan import plan_tag
from aruco_studio.scene import design as DS
from aruco_studio.scene import print3d as P3

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "prusaslicer_m8c"
EX = ROOT / "examples"
MK4_06 = "Original Prusa MK4 MMU3 0.6 nozzle - (Black, Clear, White)"
PRINT = "0.32mm SPEED @MK4IS 0.6 - Aruco"
FIL = "Prusament PLA @PGIS 0.6"
NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}


def _texts(sub):
    return {f.stem: f.read_text(encoding="utf-8") for f in sorted((FIX / sub).glob("*.ini"))}


@pytest.fixture(scope="module")
def src():
    return PR.sources_from_texts(_texts("print"), list(_texts("vendor").values()),
                                 printer_texts=_texts("printer"),
                                 physical_texts=_texts("physical_printer"),
                                 ini_text=(FIX / "PrusaSlicer.ini").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def presets(src):
    cat = P.catalog_all(P.MemoryStore(), src)
    return {n: p for n, p, _k in cat["items"]}


def compiled(name, presets, **extra):
    doc = json.loads((EX / f"{name}.arucostudio.json").read_text(encoding="utf-8"))
    for f in doc["features"]:
        if "aruco" in f:
            f.update(extra)
    sc, issues = DS.compile(doc, presets)
    assert not [i for i in issues if i.level == "error"], issues
    plans = {t.name: plan_tag(t.spec) for t in sc.tags}
    return doc, sc, plans


def profile_of(src):
    """The fixture chain (MK4 MMU3 0.6, the Aruco print), resolved by core.prusa."""
    pcfg, _c, _k = PR.resolve_printer(MK4_06, src)
    rcfg, _r = PR.resolve(PRINT, src)
    fils = PR.parse_bundle((FIX / "vendor" / "PrusaResearch.ini").read_text(encoding="utf-8"),
                           kinds=("filament",))["filament"]
    fcfg = PR._system(FIL, [fils], {FIL})
    values = {}
    for cfg in (pcfg, rcfg, fcfg):
        values.update({k: v for k, v in cfg.items() if k not in BD._META_KEYS})
    return BD.PrusaProfile(MK4_06, PRINT, FIL, "Prusa Research 2.5.11", values, "",
                           filaments=[FIL], physical_printer="")


def project(doc, sc, plans, src):
    ps, skipped = P3.parts(doc, sc, plans)
    prof = profile_of(src)
    st = BD.BedSettings(bed_w_mm=prof.bed_mm[0], bed_d_mm=prof.bed_mm[1],
                        bed_h_mm=prof.max_height_mm)
    lay = P3.layout(ps, st)
    return ps, skipped, lay, P3.render(lay, BD.project_config_text(prof, st), "test")


# ------------------------------------------------------------------ reading it back

def read_back(data: bytes):
    """[{name, volumes: [{name, type, extruder, tris: [(a, b, c)]}]}], the
    config {key: value}, the wipe towers -- with the standard library only."""
    z = zipfile.ZipFile(io.BytesIO(data))
    model = ET.fromstring(z.read("3D/3dmodel.model"))
    meshes = {}
    for obj in model.find("m:resources", NS).findall("m:object", NS):
        m = obj.find("m:mesh", NS)
        verts = [tuple(float(v.get(a)) for a in "xyz")
                 for v in m.find("m:vertices", NS).findall("m:vertex", NS)]
        tris = [tuple(int(t.get(k)) for k in ("v1", "v2", "v3"))
                for t in m.find("m:triangles", NS).findall("m:triangle", NS)]
        meshes[obj.get("id")] = (verts, tris)
    items = {it.get("objectid"): [float(x) for x in it.get("transform").split()]
             for it in model.find("m:build", NS).findall("m:item", NS)}
    cfg = ET.fromstring(z.read("Metadata/Slic3r_PE_model.config"))
    objs = []
    for o in cfg.findall("object"):
        verts, tris = meshes[o.get("id")]
        name = {m.get("key"): m.get("value") for m in o.findall("metadata")}["name"]
        vols = []
        for v in o.findall("volume"):
            md = {m.get("key"): m.get("value") for m in v.findall("metadata")}
            lo, hi = int(v.get("firstid")), int(v.get("lastid"))
            vols.append({"name": md["name"], "type": md["volume_type"],
                         "extruder": int(md["extruder"]), "tris": tris[lo:hi + 1],
                         "verts": verts})
        objs.append({"name": name, "volumes": vols, "transform": items[o.get("id")]})
    conf = {}
    for line in z.read("Metadata/Slic3r_PE.config").decode("utf-8").splitlines():
        m = re.match(r"^; (\S+) = (.*)$", line)
        if m:
            conf[m.group(1)] = m.group(2).rstrip()
    towers = (z.read("Metadata/Prusa_Slicer_wipe_tower_information.xml").decode("utf-8")
              if "Metadata/Prusa_Slicer_wipe_tower_information.xml" in z.namelist() else "")
    return objs, conf, towers


def closed_two_manifold(tris) -> bool:
    """Every directed edge once and its reverse once: closed, two-manifold,
    consistently wound."""
    directed = Counter((a, b) for t in tris for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])))
    return bool(tris) and all(n == 1 and directed.get((b, a)) == 1
                              for (a, b), n in directed.items())


def signed_volume(verts, tris) -> float:
    s = 0.0
    for a, b, c in tris:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = verts[a], verts[b], verts[c]
        s += ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
    return s / 6.0


def independent_chain():
    """The chosen printer's chain read here with a parser of our own: the
    user printer preset over its system parents, the print over its
    parents, the filament; later parents win, own keys last."""
    def ini(path):
        out = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            k, sep, v = line.partition("=")
            if sep and not line.lstrip().startswith(("#", ";")):
                out[k.strip()] = v.strip()
        return out
    secs, cur = {}, None
    for line in (FIX / "vendor" / "PrusaResearch.ini").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\[(.+)\]$", line.strip())
        if m:
            cur = secs.setdefault(m.group(1), {})
            continue
        k, sep, v = line.partition("=")
        if cur is not None and sep and not line.lstrip().startswith(("#", ";")):
            cur[k.strip()] = v.strip()

    def chain(kind, name):
        own = secs[f"{kind}:{name}"]
        out = {}
        for p in [x.strip().strip('"') for x in own.get("inherits", "").split(";") if x.strip()]:
            out.update(chain(kind, p))
        out.update(own)
        return out
    pr_own = ini(FIX / "printer" / f"{MK4_06}.ini")
    printer = chain("printer", pr_own["inherits"])
    printer.update(pr_own)
    pt_own = ini(FIX / "print" / f"{PRINT}.ini")
    prn = chain("print", pt_own["inherits"])
    prn.update(pt_own)
    out = {}
    for cfg in (printer, prn, chain("filament", FIL)):
        out.update(cfg)
    meta = {"inherits", "compatible_printers", "compatible_printers_condition", "compatible_prints",
            "compatible_prints_condition", "renamed_from", "alias", "instantiation"}
    return {k: v for k, v in out.items() if k not in meta
            and not k.startswith(("print_host", "printhost_", "octoprint_"))}   # never read


# ------------------------------------------------------------------ M8c.6

def test_the_forearm_is_one_object_with_its_four_tags(src, presets):
    doc, sc, plans = compiled("forearm", presets)
    ps, skipped, lay, data = project(doc, sc, plans, src)
    assert not skipped and len(ps) == 1 and ps[0].tags == ["tag.front", "tag.right", "tag.back",
                                                            "tag.left"]
    objs, conf, towers = read_back(data)
    assert len(objs) == 1 and objs[0]["name"] == "forearm"
    vols = objs[0]["volumes"]
    assert [v["name"] for v in vols] == ["forearm body"] + [f"tag.{f} black" for f in
                                                            ("front", "right", "back", "left")]
    _check_volumes(vols)
    assert towers                       # the MMU's wipe tower kept clear of the part


def test_new_body_tiles_give_white_black_and_negative_volumes(src, presets):
    doc, sc, plans = compiled("forearm", presets, mode="both", op="new")
    ps, _sk, lay, data = project(doc, sc, plans, src)
    objs, _conf, _t = read_back(data)
    assert len(objs) == 1
    vols = objs[0]["volumes"]
    assert len(vols) == 1 + 4 * 3
    want = ["forearm body"] + [f"tag.{f} {k}" for f in ("front", "right", "back", "left")
                               for k in ("white", "black", "removed")]
    assert [v["name"] for v in vols] == want
    _check_volumes(vols)
    neg = [v for v in vols if v["type"] == "NegativeVolume"]
    assert len(neg) == 4 and all(v["name"].endswith("removed") for v in neg)


def _check_volumes(vols):
    for v in vols:
        assert closed_two_manifold(v["tris"]), v["name"]
        assert signed_volume(v["verts"], v["tris"]) > 0, v["name"]      # outward normals
        kind = v["name"].rsplit(" ", 1)[1]
        assert v["type"] == ("NegativeVolume" if kind == "removed" else "ModelPart"), v["name"]
        assert v["extruder"] == (2 if kind == "black" else 1), v["name"]


def test_the_config_is_the_chosen_printers_chain_and_its_bed(src, presets):
    doc, sc, plans = compiled("plate_charuco", presets)
    _ps, _sk, lay, data = project(doc, sc, plans, src)
    _objs, conf, _t = read_back(data)
    want = independent_chain()
    set_by_project = {"extruder_colour", "filament_colour", "print_settings_id",
                      "printer_settings_id", "filament_settings_id"}
    differ = sorted(k for k in want if k not in set_by_project
                    and conf.get(k) != want[k].replace("\r", ""))
    assert not differ, differ[:10]
    assert set(conf) - set(want) <= set_by_project
    assert conf["printer_settings_id"] == MK4_06 and conf["print_settings_id"] == PRINT
    assert conf["bed_shape"] == want["bed_shape"] == "0x0,250x0,250x210,0x210"
    assert lay.settings.bed_w_mm == 250 and lay.settings.bed_d_mm == 210
    ec = conf["extruder_colour"].split(";")
    assert ec[0].strip('"') == "#FFFFFF" and ec[1].strip('"') == "#000000"
    assert not any(k.startswith(("print_host", "printhost_", "octoprint_")) for k in conf)


def test_the_plate_is_its_body_and_one_tags_volumes(src, presets):
    doc, sc, plans = compiled("plate_charuco", presets)
    ps, _sk, lay, data = project(doc, sc, plans, src)
    objs, _conf, _t = read_back(data)
    assert [o["name"] for o in objs] == ["body"]
    assert [v["name"] for v in objs[0]["volumes"]] == ["body body", "tag black"]
    _check_volumes(objs[0]["volumes"])
    body = objs[0]["volumes"][0]
    # the Ø18 hole is in the body: 80 x 50 x 5 less a circle stroked at 0.05 mm
    # (a stroked hole is a little smaller than the circle: under 12 mm³ here)
    vol = signed_volume(body["verts"], body["tris"])
    full = 80 * 50 * 5 - 3.14159265 * 9 * 9 * 5
    assert full < vol < full + 12
    man = P3.manifest(ps, [], lay)
    assert man["parts"][0]["size_mm"] == [80.0, 50.0, 5.0] and man["beds"] == 1


def test_stickers_have_nothing_to_slice(src, presets):
    doc, sc, plans = compiled("sticker_sheet", presets)
    ps, skipped = P3.parts(doc, sc, plans)
    assert ps == [] and len(skipped) == 4
    assert all(s["reason"] == "a sticker: it prints on paper" for s in skipped)
    assert P3.nothing_reason(sc, plans) == "nothing to slice: stickers print on paper"


def test_a_tag_on_a_bare_shape_is_a_part_of_its_own(src, presets):
    doc = json.loads((EX / "sticker_sheet.arucostudio.json").read_text(encoding="utf-8"))
    doc["preset"] = PRINT                # the same file under a 3D preset
    sc, _i = DS.compile(doc, presets)
    plans = {t.name: plan_tag(t.spec) for t in sc.tags}
    ps, skipped = P3.parts(doc, sc, plans)
    assert [p.name for p in ps] == [t.name for t in sc.tags if plans[t.name].ok]
    assert all(p.body is None and len(p.tags) == 1 for p in ps)
    assert all(v.kind != "removed" for p in ps for v in p.volumes)   # no body: nothing to cut
    lay = P3.layout(ps, BD.BedSettings())
    assert len(lay.placed) == len(ps)
