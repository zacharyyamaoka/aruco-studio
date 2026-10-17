"""Send to PrusaSlicer, the pure half (M8 note 5.5): a design's 3D parts as
PrusaSlicer volumes, laid on beds, as a 3MF project's bytes. Standard
library only; never opens a file (server/beds_io.py and server/prusa_api.py
write and open it).

| Function | Gives |
|---|---|
| `parts(doc, scene, plans)` | ([Part], skipped): one part per extruded body with every 3D tag on it (the forearm is ONE part with four tags); a 3D tag on a bare shape is a part of its own; stickers, hidden and unplanned tags are skipped with a reason |
| `Part.volumes` | the body's solid (white, extruder 1, `ModelPart`), then per tag, from `plan/mesh` in the tag's own frame placed by its 4x4 pose: the white it adds (extruder 1), the black (extruder 2), and what it removes from the body (`plan/mesh.removed`) as a `NegativeVolume` |
| `layout(parts, settings)` | the parts on beds (`core.beds.pack_rectangles`: footprints as modelled, never turned, the wipe tower's hole kept) |
| `render(lay, config_text, title)` | the 3MF bytes: each part ONE object, its volumes as triangle ranges with `volume_type` and `extruder` in Metadata/Slic3r_PE_model.config, the project config in Metadata/Slic3r_PE.config, the towers |
| `manifest(parts, skipped, lay)` | the JSON summary the route answers with |

PrusaSlicer does the 3D booleans: its parts are unioned per extruder (a
later part wins where two overlap: the black over the body), its negative
volumes subtracted. Our code is exact in 2D per slab in each tag's frame
(plan/region.py) and never does a 3D boolean: four tags on four faces have
four normals. A negative volume is the cut minus what the tag adds back
there, so it never overlaps a white or a black of its tag.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Tuple

from ..core import beds as _BD
from ..plan import mesh as _ME
from ..plan import region as _RG
from . import design as _DS
from .model import Scene, mat_mul

SCHEMA = "arucostudio.send/1"
WHITE, BLACK = 1, 2
STICKERS_ONLY = "nothing to slice: stickers print on paper"
NOTHING = "nothing to slice: the scene has no 3D tag"


@dataclass
class Volume:
    name: str
    kind: str                       # body / white / black / removed
    extruder: int
    positions: List[Tuple[float, float, float]]
    triangles: List[Tuple[int, int, int]]
    tag: Optional[str] = None

    @property
    def volume_type(self) -> str:
        return "NegativeVolume" if self.kind == "removed" else "ModelPart"


@dataclass
class Part:
    name: str
    body: Optional[str]             # the Extrude's id, None for a tag on a bare shape
    tags: List[str] = field(default_factory=list)
    volumes: List[Volume] = field(default_factory=list)

    def bbox(self, negative: bool = False):
        pts = [p for v in self.volumes if negative or v.kind != "removed" for p in v.positions]
        if not pts:
            return None
        return ([min(p[i] for p in pts) for i in range(3)],
                [max(p[i] for p in pts) for i in range(3)])


# ------------------------------------------------------------------ geometry

def _apply(M, p):
    x, y, z = p
    return (M[0] * x + M[1] * y + M[2] * z + M[3], M[4] * x + M[5] * y + M[6] * z + M[7],
            M[8] * x + M[9] * y + M[10] * z + M[11])


def _det3(M):
    return (M[0] * (M[5] * M[10] - M[6] * M[9]) - M[1] * (M[4] * M[10] - M[6] * M[8])
            + M[2] * (M[4] * M[9] - M[5] * M[8]))


def _placed(traps, z0, z1, M):
    pos, tri = _ME.prism(traps, z0, z1)
    pts = [_apply(M, p) for p in pos]
    tris = [tuple(t) for t in tri]
    if _det3(M) < 0:                                   # a mirror flips the winding
        tris = [(a, c, b) for a, b, c in tris]
    return pts, tris


def _merge(pieces):
    """Several closed prisms as one mesh (each keeps its own vertices)."""
    pos, tri = [], []
    for pts, tris in pieces:
        base = len(pos)
        pos += pts
        tri += [(a + base, b + base, c + base) for a, b, c in tris]
    return pos, tri


def body_volume(doc, fid: str, white: int = WHITE) -> Optional[Volume]:
    """An Extrude feature's solid: its shape's loops on the canvas (outer,
    then holes, even-odd) as a prism from z 0 to its height."""
    feat = next((f for f in doc.get("features") or [] if isinstance(f, dict)
                 and f.get("id") == fid and "extrude" in f), None)
    if feat is None:
        return None
    loops = next((s["loops"] for s in _DS.shapes_2d(doc) if s["shape"] == feat["extrude"]),
                 None)
    if not loops:
        return None
    h = float(feat["height"])
    traps = _RG.boolean([[loops]], lambda f: f[0])
    pos, tri = _ME.prism(traps, min(0.0, h), max(0.0, h))
    return Volume(f"{fid} body", "body", white, [tuple(p) for p in pos],
                  [tuple(t) for t in tri])


def tag_volumes(t, plan_d: dict, with_removed: bool = True, white: int = WHITE,
                black: int = BLACK) -> List[Volume]:
    """A tag's white, black and removed volumes, in the scene (mm): every
    slab's region (plan/mesh) placed by the tag's pose times the pattern's
    frame in its target."""
    M = mat_mul(t.pose_full, plan_d["frames"]["pattern_in_target"])
    whites, blacks = [], []
    for b in _ME.bodies(plan_d):
        if b["what"] == "body":
            continue
        piece = _placed(b["_traps"], b["z"][0], b["z"][1], M)
        (blacks if b["colour"] == "black" else whites).append(piece)
    out = []
    for kind, pieces, ext in (("white", whites, white), ("black", blacks, black)):
        if pieces:
            pos, tri = _merge(pieces)
            out.append(Volume(f"{t.name} {kind}", kind, ext, pos, tri, t.name))
    if with_removed:
        rem = [_placed(r["_traps"], r["z"][0], r["z"][1], M) for r in _ME.removed(plan_d)]
        if rem:
            pos, tri = _merge(rem)
            out.append(Volume(f"{t.name} removed", "removed", white, pos, tri, t.name))
    return out


# ------------------------------------------------------------------ the parts

def _body_of(t) -> Optional[str]:
    src = t.source or {}
    return src.get("body") or src.get("over")


def parts(doc, scene: Scene, plans: dict, white: int = WHITE,
          black: int = BLACK) -> Tuple[List[Part], List[dict]]:
    """([Part], [{tag, reason}]) of a compiled design (`plans`: {name:
    TagPlan}). A part per body with its tags, in the order of the bodies'
    first tags; a 3D tag on a bare shape alone."""
    out: Dict[str, Part] = {}
    order: List[str] = []
    skipped = []
    for t in scene.tags:
        p = plans.get(t.name)
        if t.hidden:
            skipped.append({"tag": t.name, "reason": "hidden"})
            continue
        if p is None or not p.ok:
            skipped.append({"tag": t.name, "reason": "not planned (see its errors)"})
            continue
        d = p.data
        if d.get("made_by") == "sticker":
            skipped.append({"tag": t.name, "reason": "a sticker: it prints on paper"})
            continue
        bid = _body_of(t)
        key = f"body:{bid}" if bid else f"tag:{t.name}"
        if key not in out:
            part = Part(bid or t.name, bid)
            if bid:
                bv = body_volume(doc, bid, white)
                if bv is not None:
                    part.volumes.append(bv)
            out[key] = part
            order.append(key)
        part = out[key]
        part.tags.append(t.name)
        part.volumes += tag_volumes(t, d, with_removed=bool(bid), white=white, black=black)
    return [out[k] for k in order if out[k].volumes], skipped


def nothing_reason(scene: Scene, plans: dict) -> str:
    """Why there is nothing to slice (the route's 400)."""
    ok = [t for t in scene.tags if not t.hidden and plans.get(t.name) is not None
          and plans[t.name].ok]
    if ok and all(plans[t.name].data.get("made_by") == "sticker" for t in ok):
        return STICKERS_ONLY
    return NOTHING


# ------------------------------------------------------------------ the beds

@dataclass
class Layout:
    settings: "_BD.BedSettings"
    parts: List[Part]
    placed: List[Tuple[int, int, float, float]]      # (part, bed, centre x, centre y)
    towers: List[Optional[tuple]]
    rejected: List[Tuple[str, str]]
    warnings: List[str]

    @property
    def bed_count(self) -> int:
        return len(self.towers)


def layout(ps: Sequence[Part], settings: Optional["_BD.BedSettings"] = None) -> Layout:
    """The parts on beds, as modelled (never turned or laid down: a side
    tag stays on its side), each dropped to z 0."""
    st = replace(settings or _BD.BedSettings(), allow_rotate=False, orientation="cad")
    items, owners, warns, rejected = [], [], [], []
    for i, p in enumerate(ps):
        lo, hi = p.bbox()
        h = hi[2] - lo[2]
        if st.bed_h_mm is not None and h > st.bed_h_mm + 1e-6:
            rejected.append((p.name, f"it stands {h:.1f} mm tall, above the "
                                     f"{st.bed_h_mm:.1f} mm print height"))
            continue
        items.append((hi[0] - lo[0], hi[1] - lo[1]))
        owners.append(i)
    slots, rej, towers = _BD.pack_rectangles(items, st, [ps[i].name for i in owners])
    placed = []
    for j, sl in enumerate(slots):
        if sl is None:
            rejected.append((ps[owners[j]].name, rej.get(j, "does not fit the bed")))
            continue
        placed.append((owners[j], sl.bed, sl.x + sl.w / 2.0, sl.y + sl.d / 2.0))
    for name, reason in rejected:
        warns.append(f"NOT PRINTED: {name} -- {reason}")
    return Layout(st, list(ps), placed, list(towers), rejected, warns)


def object_mesh(p: Part):
    """The part's volumes moved so its footprint's centre is at x, y 0 and
    its lowest point (colours, not negative volumes) at z 0."""
    lo, hi = p.bbox()
    dx, dy, dz = -(lo[0] + hi[0]) / 2.0, -(lo[1] + hi[1]) / 2.0, -lo[2]
    return [replace(v, positions=[(x + dx, y + dy, z + dz) for x, y, z in v.positions])
            for v in p.volumes]


# ------------------------------------------------------------------ the 3MF

def _f(v: float) -> str:
    return _BD._f(v)


def render(lay: Layout, config_text: Optional[str], title: str = "ArUco Studio") -> bytes:
    """The 3MF project: one object per placed part, one volume per Volume
    (a triangle range of the object's mesh) with its `volume_type` and
    extruder; bed k at PrusaSlicer 2.9's place; the wipe towers; the
    project config (`config_text`, None: none)."""
    st = lay.settings
    model = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
             'xmlns:slic3rpe="http://schemas.slic3r.org/3mf/2017/06">',
             ' <metadata name="slic3rpe:Version3mf">1</metadata>',
             ' <metadata name="Title">%s</metadata>' % _BD._xml_attr(title),
             ' <metadata name="Application">ArUco Studio (scene/print3d.py)</metadata>',
             ' <resources>']
    config = ['<?xml version="1.0" encoding="UTF-8"?>', '<config>']
    items = []
    for oid, (pi, bed, cx, cy) in enumerate(lay.placed, start=1):
        part = lay.parts[pi]
        vols = object_mesh(part)
        model.append('  <object id="%d" type="model">' % oid)
        model.append('   <mesh>')
        model.append('    <vertices>')
        for v in vols:
            for x, y, z in v.positions:
                model.append('     <vertex x="%s" y="%s" z="%s"/>' % (_f(x), _f(y), _f(z)))
        model.append('    </vertices>')
        model.append('    <triangles>')
        ranges, base, first = [], 0, 0
        for v in vols:
            for a, b, c in v.triangles:
                model.append('     <triangle v1="%d" v2="%d" v3="%d"/>'
                             % (a + base, b + base, c + base))
            ranges.append((first, first + len(v.triangles) - 1))
            first += len(v.triangles)
            base += len(v.positions)
        model.append('    </triangles>')
        model.append('   </mesh>')
        model.append('  </object>')
        config.append(' <object id="%d" instances_count="1">' % oid)
        config.append('  <metadata type="object" key="name" value="%s"/>'
                      % _BD._xml_attr(part.name))
        config.append('  <metadata type="object" key="extruder" value="%d"/>'
                      % st.tile_extruder)
        for v, (lo, hi) in zip(vols, ranges):
            config.append('  <volume firstid="%d" lastid="%d">' % (lo, hi))
            config.append('   <metadata type="volume" key="name" value="%s"/>'
                          % _BD._xml_attr(v.name))
            config.append('   <metadata type="volume" key="volume_type" value="%s"/>'
                          % v.volume_type)
            config.append('   <metadata type="volume" key="matrix" value="%s"/>'
                          % _BD._IDENTITY_4X4)
            config.append('   <metadata type="volume" key="extruder" value="%d"/>' % v.extruder)
            config.append('   <mesh edges_fixed="0" degenerate_facets="0" facets_removed="0" '
                          'facets_reversed="0" backwards_edges="0"/>')
            config.append('  </volume>')
        config.append(' </object>')
        ox, oy = _BD.bed_translation(bed, st.bed_w_mm, st.bed_d_mm)
        items.append('  <item objectid="%d" transform="%s" printable="1"/>'
                     % (oid, _BD._transform_3mf(0.0, cx + ox, cy + oy, 0.0)))
    model.append(' </resources>')
    model.append(' <build>')
    model += items
    model.append(' </build>')
    model.append('</model>')
    config.append('</config>')
    members = [("[Content_Types].xml", _BD._CONTENT_TYPES.encode("utf-8")),
               ("_rels/.rels", _BD._RELS.encode("utf-8")),
               ("3D/3dmodel.model", ("\n".join(model) + "\n").encode("utf-8"))]
    towers = [(b, t[0] + st.wipe_tower_brim_mm, t[1] + st.wipe_tower_brim_mm)
              for b, t in enumerate(lay.towers) if t is not None]
    if towers:
        members.append(("Metadata/Prusa_Slicer_wipe_tower_information.xml", (
            '<?xml version="1.0" encoding="utf-8"?>\n' + "".join(
                '<wipe_tower_information bed_idx="%d" position_x="%s" position_y="%s" '
                'rotation_deg="0"/>\n' % (b, _f(x), _f(y)) for b, x, y in towers)
        ).encode("utf-8")))
    if config_text:
        members.append(("Metadata/Slic3r_PE.config", config_text.encode("utf-8")))
    members.append(("Metadata/Slic3r_PE_model.config",
                    ("\n".join(config) + "\n").encode("utf-8")))
    return _BD._zip(members)


def volume_mm3(v: Volume) -> float:
    s = 0.0
    P = v.positions
    for a, b, c in v.triangles:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = P[a], P[b], P[c]
        s += (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx))
    return s / 6.0


def manifest(ps: Sequence[Part], skipped: Sequence[dict], lay: Optional[Layout] = None) -> dict:
    """The summary: per part its tags and volumes (name, kind, volume_type,
    extruder, triangles, mm3), the beds, what was skipped."""
    placed = {pi: (bed, cx, cy) for pi, bed, cx, cy in (lay.placed if lay else [])}
    out = []
    for i, p in enumerate(ps):
        lo, hi = p.bbox()
        bed = placed.get(i)
        out.append({"name": p.name, "body": p.body, "tags": list(p.tags),
                    "size_mm": [round(hi[k] - lo[k], 4) for k in range(3)],
                    "bed": None if bed is None else bed[0],
                    "at_mm": None if bed is None else [round(bed[1], 4), round(bed[2], 4)],
                    "volumes": [{"name": v.name, "kind": v.kind, "tag": v.tag,
                                 "volume_type": v.volume_type, "extruder": v.extruder,
                                 "triangles": len(v.triangles),
                                 "mm3": round(abs(volume_mm3(v)), 3)} for v in p.volumes]})
    return {"schema": SCHEMA, "parts": out, "skipped": list(skipped),
            "beds": lay.bed_count if lay else 0,
            "rejected": [{"part": n, "reason": r} for n, r in (lay.rejected if lay else [])]}

