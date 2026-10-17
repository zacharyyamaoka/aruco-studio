"""The target: the face or sketch area a tag is made on, as plain numbers
(ARCHITECTURE 5.1).

An adapter fills it from what it clicked: Fusion from a BRepFace or a
Profile (REF `face_frame` + `keep_x`, `profile_rect`, the face's loops, the
body under it), the Studio from its target editor. The plan never sees an
entity.

The frame is the BASE frame REF's evaluate() works in: origin on the face /
sketch plane, u = the target's x (after REF's keep_x / x_sketch / z_sign /
the legacy rotate_deg), v = z x u, z = the side the tag stands on. Every
length is mm in that frame.

| Field | Meaning |
|---|---|
| `kind` | "face" (a face of a body), "profile" (a sketch area), "free" (a sketch area with nothing under it) |
| `w_mm`, `h_mm` | the box the target spans along u / v |
| `loops_mm` | the outline: the outer loop first, then the holes; [] = the box itself |
| `has_body` | a body under the target (the slabs' Join / pocket / recess) |
| `z_sign` | which way the normal points against the host (carried for the adapter) |
| `x_ref` | a face tag's x as it was made, [u, v] (REF x_ref: after the fit it wins over a flip); null for a profile |
| `body_mm` | the body under it, boxed in the base frame: {u0, v0, u1, v1, z0, z1} (z along the normal, 0 at the face); `measured` false = its volumes could not be measured (the trim then refuses); `depth` = the plate's thickness when it is not z1 - z0 |
| `body_loops_mm` | the body's footprint when it is a prism of the outline (the Studio's targets); null = the body box |
| `face_loops_mm` | a sketch area: the loops of the face UNDER it (the trim measures that face); null = no face under it. A face target always measures its own loops |
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ..core import faces as _faces

KINDS = ("face", "profile", "free")
Pt = Tuple[float, float]


class SpecTypeError(TypeError):
    """A wrong TYPE in a request: a string where a number goes, a missing
    required key. `path` is the key path (ARCHITECTURE 5.6)."""

    def __init__(self, path: str, message: str):
        super().__init__(f"{path}: {message}")
        self.path = path
        self.message = message


def _num(d, key, path, default=None, required=False):
    if key not in d or d[key] is None:
        if required:
            raise SpecTypeError(f"{path}.{key}", "required")
        return default
    v = d[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise SpecTypeError(f"{path}.{key}", f"a number, not {type(v).__name__}")
    return float(v)


def _loops(v, path) -> List[List[Pt]]:
    if v is None:
        return []
    if not isinstance(v, (list, tuple)):
        raise SpecTypeError(path, "a list of loops")
    out = []
    for i, lp in enumerate(v):
        if not isinstance(lp, (list, tuple)):
            raise SpecTypeError(f"{path}[{i}]", "a loop: a list of [u, v] points")
        pts = []
        for j, p in enumerate(lp):
            if (not isinstance(p, (list, tuple)) or len(p) != 2
                    or any(isinstance(c, bool) or not isinstance(c, (int, float)) for c in p)):
                raise SpecTypeError(f"{path}[{i}][{j}]", "a point: [u, v] numbers")
            pts.append((float(p[0]), float(p[1])))
        out.append(pts)
    return out


@dataclass
class Target:
    kind: str = "face"
    w_mm: float = 40.0
    h_mm: float = 40.0
    loops_mm: List[List[Pt]] = field(default_factory=list)
    has_body: bool = True
    z_sign: int = 1
    x_ref: Optional[Tuple[float, float]] = None
    body_mm: Optional[Dict[str, float]] = None
    body_loops_mm: Optional[List[List[Pt]]] = None
    face_loops_mm: Optional[List[List[Pt]]] = None
    name: str = ""

    # ------------------------------------------------------------ reading

    @property
    def is_profile(self) -> bool:
        """REF's `isinstance(target, adsk.fusion.Profile)`: a sketch area
        (with or without a body under it)."""
        return self.kind != "face"

    def box_loop_mm(self) -> List[Pt]:
        """The box, counter-clockwise from its bottom-left corner."""
        w, h = self.w_mm, self.h_mm
        return [(-w / 2.0, -h / 2.0), (w / 2.0, -h / 2.0), (w / 2.0, h / 2.0), (-w / 2.0, h / 2.0)]

    def outline_mm(self) -> List[List[Pt]]:
        """The loops, or the box when there are none."""
        return [list(lp) for lp in self.loops_mm] if self.loops_mm else [self.box_loop_mm()]

    def loops_m(self) -> List[List[Pt]]:
        """The loops in METRES (what REF's `_face_loops_m` / `_profile_loops_m`
        give evaluate()): mm / 1000; the box as REF's fixtures write it."""
        if self.loops_mm:
            return [[(u / 1000.0, v / 1000.0) for (u, v) in lp] for lp in self.loops_mm]
        w, h = self.w_mm, self.h_mm
        return [[(-w / 2000, -h / 2000), (w / 2000, -h / 2000), (w / 2000, h / 2000),
                 (-w / 2000, h / 2000)]]

    def trim_face_loops_mm(self) -> Optional[List[List[Pt]]]:
        """The loops the trim measures (mm, base frame): a face's own, a
        sketch area's face under it (None: no face there)."""
        if self.is_profile:
            return [list(lp) for lp in self.face_loops_mm] if self.face_loops_mm else None
        return self.outline_mm()

    # ------------------------------------------------------------ JSON

    def to_dict(self) -> dict:
        r = lambda lps: [[[float(u), float(v)] for (u, v) in lp] for lp in lps]
        d = {"kind": self.kind, "w_mm": float(self.w_mm), "h_mm": float(self.h_mm),
             "loops_mm": r(self.loops_mm), "has_body": bool(self.has_body),
             "z_sign": int(self.z_sign),
             "x_ref": [float(c) for c in self.x_ref] if self.x_ref is not None else None,
             "body_mm": dict(self.body_mm) if self.body_mm is not None else None,
             "body_loops_mm": r(self.body_loops_mm) if self.body_loops_mm is not None else None,
             "face_loops_mm": r(self.face_loops_mm) if self.face_loops_mm is not None else None}
        if self.name:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, d, path: str = "target") -> "Target":
        """Types are checked here (SpecTypeError names the key path); values
        are checked by plan.spec.check."""
        if not isinstance(d, dict):
            raise SpecTypeError(path, "an object")
        kind = d.get("kind", "face")
        if not isinstance(kind, str):
            raise SpecTypeError(f"{path}.kind", "a string")
        hb = d.get("has_body", kind != "free")
        if not isinstance(hb, bool):
            raise SpecTypeError(f"{path}.has_body", "true or false")
        zs = d.get("z_sign", 1)
        if isinstance(zs, bool) or not isinstance(zs, (int, float)):
            raise SpecTypeError(f"{path}.z_sign", "1 or -1")
        xr = d.get("x_ref")
        if xr is not None:
            if (not isinstance(xr, (list, tuple)) or len(xr) != 2
                    or any(isinstance(c, bool) or not isinstance(c, (int, float)) for c in xr)):
                raise SpecTypeError(f"{path}.x_ref", "[u, v] or null")
            xr = (float(xr[0]), float(xr[1]))
        body = d.get("body_mm")
        if body is not None:
            if not isinstance(body, dict):
                raise SpecTypeError(f"{path}.body_mm", "an object or null")
            b = {}
            for k in ("u0", "v0", "u1", "v1", "z0", "z1"):
                b[k] = _num(body, k, f"{path}.body_mm", required=True)
            if "depth" in body and body["depth"] is not None:
                b["depth"] = _num(body, "depth", f"{path}.body_mm")
            m = body.get("measured", True)
            if not isinstance(m, bool):
                raise SpecTypeError(f"{path}.body_mm.measured", "true or false")
            b["measured"] = m
            body = b
        name = d.get("name", "")
        if not isinstance(name, str):
            raise SpecTypeError(f"{path}.name", "a string")
        bl = d.get("body_loops_mm")
        fl = d.get("face_loops_mm")
        return cls(kind=kind, w_mm=_num(d, "w_mm", path, required=True),
                   h_mm=_num(d, "h_mm", path, required=True),
                   loops_mm=_loops(d.get("loops_mm"), f"{path}.loops_mm"),
                   has_body=hb, z_sign=int(zs), x_ref=xr, body_mm=body,
                   body_loops_mm=_loops(bl, f"{path}.body_loops_mm") if bl is not None else None,
                   face_loops_mm=_loops(fl, f"{path}.face_loops_mm") if fl is not None else None,
                   name=name)


# ------------------------------------------------------------ makers

def _area2(pts: Sequence[Pt]) -> float:
    return sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))


def _ccw(pts, ccw=True):
    pts = [(float(u), float(v)) for u, v in pts]
    if (_area2(pts) > 0) != ccw:
        pts.reverse()
    return pts


def _box_of(loops):
    us = [p[0] for p in loops[0]]
    vs = [p[1] for p in loops[0]]
    return min(us), min(vs), max(us), max(vs)


def with_thickness(t: "Target", thickness_mm: float) -> "Target":
    """The target as the top face of a prism `thickness_mm` deep (the
    Studio's stand-in for a plate): the body under it is the outline
    extruded down, so pockets, recesses, pins and the trim all plan."""
    if thickness_mm and thickness_mm > 0:
        u0, v0, u1, v1 = _box_of(t.outline_mm())
        t.body_mm = {"u0": u0, "v0": v0, "u1": u1, "v1": v1, "z0": -float(thickness_mm),
                     "z1": 0.0, "measured": True}
        t.body_loops_mm = t.outline_mm()
        t.has_body = True
    else:
        t.body_mm = None
        t.body_loops_mm = None
        t.has_body = False
    return t


def box(w_mm: float, h_mm: float, thickness_mm: float = 0.0, kind: str = "face") -> Target:
    """A w x h rectangle centred on the origin."""
    t = Target(kind=kind, w_mm=float(w_mm), h_mm=float(h_mm), loops_mm=[], has_body=False)
    return with_thickness(t, thickness_mm)


def circle_pts(cx: float, cy: float, r: float, n: int = 64, cw: bool = False) -> List[Pt]:
    pts = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n))
           for k in range(n)]
    return pts[::-1] if cw else pts


def disc(r_mm: float, holes: Sequence[Tuple[float, float, float]] = (), thickness_mm: float = 0.0,
         n: int = 96) -> Target:
    """A disc of radius r (mm) with round holes (cx, cy, r)."""
    loops = [circle_pts(0.0, 0.0, r_mm, n)] + [circle_pts(cx, cy, r, 48, cw=True)
                                                for cx, cy, r in holes]
    t = Target(kind="face", w_mm=2.0 * r_mm, h_mm=2.0 * r_mm, loops_mm=loops, has_body=False)
    return with_thickness(t, thickness_mm)


def from_loops(loops: Sequence[Sequence[Pt]], thickness_mm: float = 0.0, kind: str = "face",
               centre: bool = True, name: str = "") -> Target:
    """Any outline (the outer loop first, then holes), centred on its box."""
    lps = [_ccw(loops[0])] + [_ccw(h, ccw=False) for h in loops[1:]]
    u0, v0, u1, v1 = _box_of(lps)
    if centre:
        cu, cv = (u0 + u1) / 2.0, (v0 + v1) / 2.0
        lps = [[(u - cu, v - cv) for u, v in lp] for lp in lps]
    t = Target(kind=kind, w_mm=u1 - u0, h_mm=v1 - v0, loops_mm=lps, has_body=False, name=name)
    return with_thickness(t, thickness_mm)


def from_face(key: str, thickness_mm: float = 0.0) -> Target:
    """One of the palette's faces (core.faces: a box, a disc and REF's ten
    autosize-gallery faces, tessellated as Fusion strokes an edge)."""
    for f in _faces.PALETTE:
        if f["key"] == key:
            return from_loops(_faces.loops_mm(f), thickness_mm, name=f["title"])
    raise KeyError(key)


def palette(thickness_mm: float = 3.0) -> List[dict]:
    """The target palette the Studio offers (GET /api/targets)."""
    out = []
    for f in _faces.PALETTE:
        t = from_face(f["key"], thickness_mm)
        out.append({"key": f["key"], "title": f["title"], "target": t.to_dict()})
    return out


def prism_volumes(t: Target) -> Optional[Dict[str, float]]:
    """A Studio target's volumes (mm3): the body (its footprint x depth) and
    the part of it under the face (the face's area x depth). Exact for a
    prism; None when there is no body."""
    if t.body_mm is None:
        return None
    b = t.body_mm
    depth = b.get("depth", b["z1"] - b["z0"])
    loops = t.body_loops_mm or [[(b["u0"], b["v0"]), (b["u1"], b["v0"]), (b["u1"], b["v1"]),
                                 (b["u0"], b["v1"])]]
    body = abs(_area2(loops[0])) / 2.0 - sum(abs(_area2(h)) / 2.0 for h in loops[1:])
    face = t.trim_face_loops_mm() or loops
    under = abs(_area2(face[0])) / 2.0 - sum(abs(_area2(h)) / 2.0 for h in face[1:])
    return {"body": body * depth, "under_face": under * depth}
