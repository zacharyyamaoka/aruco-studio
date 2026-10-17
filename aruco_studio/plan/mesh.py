"""A plan's solids, exactly: per slab of z, the 2D boolean of its layers
(plan/region.py), the parts combined as `combines` says -- then as
triangles for the 3D view and an STL. Standard library only.

| Function | Gives |
|---|---|
| `bodies(plan)` | [{what, colour, z, polygons}]: the white tile and pins (`white`), the pattern (`black`, or `white` in White only), the body under it (`body`), one per run of slabs that is the same |
| `top(plan)` | {colour: polygons}: what is seen from above, the colour of the highest material over each point (the vector top view: the SVG export) |
| `mesh(plan)` | [{what, colour, z, positions, indices}] per body: watertight prisms (every edge in two triangles) |
| `stl(plan)` | binary STL of every body (or of one `what`) |

All in the pattern frame, mm. The assembly is REF's create(): the tile
joined to the body (Join) or new, the pins joined to the tile, the pocket
cut from the tile and (Join) the body, the pattern its own body, the recess
cut from the body (and the joined tile), the trim intersected with it.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Optional, Sequence, Tuple

from . import region as RG

GREY = {"white": "white", "black": "black", "body": "body"}


def _d(plan):
    return plan.to_dict() if hasattr(plan, "to_dict") else plan


class _Model:
    """The plan's steps as boolean groups, and what a column of material
    looks like for given flags (which groups contain the point)."""

    def __init__(self, d):
        self.d = d
        self.layers = d["layers"]
        self.groups = [[[p["outer"]] + list(p.get("holes", [])) for p in L["polygons"]]
                       for L in self.layers]
        body = d.get("body")
        self.body = None
        if body:
            self.body = len(self.groups)
            # the body's loops are one even-odd polygon (outer and holes)
            self.groups.append([body["loops"]])
            self.body_z = tuple(body["z"])
        zs = {z for L in self.layers for z in L["z"]}
        if self.body is not None:
            zs |= set(self.body_z)
        zs = sorted(zs)
        self.slabs = [(a, b) for a, b in zip(zs, zs[1:]) if b - a > 1e-9]
        self.comb = {c["part"]: c for c in d["combines"]}
        self.joined = self.comb.get("tile", {}).get("op") == "join"
        self.pattern_colour = ("white" if any(L["part"] == "pattern" and L["colour"] == "white"
                                              for L in self.layers) else "black")
        # per slab: the layers that cut through it
        self.active = []
        for a, b in self.slabs:
            zm = (a + b) / 2.0
            self.active.append([i for i, L in enumerate(self.layers)
                                if L["z"][0] < zm < L["z"][1]])

    def materials(self, k, f):
        """(body, white, pattern) at slab k for flags f."""
        parts = {}
        solids = {}
        for i in self.active[k]:
            L = self.layers[i]
            key = (L["part"], L["solid"])
            cur = solids.get(key, False)
            solids[key] = (cur or f[i]) if L["step"] == "add" else (cur and not f[i])
        for (part, _s), v in solids.items():
            parts[part] = parts.get(part, False) or v
        a, b = self.slabs[k]
        zm = (a + b) / 2.0
        B = (self.body is not None and f[self.body] and self.body_z[0] < zm < self.body_z[1])
        W = P = False
        for part in self.d["parts"]:
            r = parts.get(part)
            if r is None:
                continue
            if part in ("tile", "pin"):
                W = W or r
            elif part == "pocket":
                W = W and not r
                if self.comb.get("pocket", {}).get("into") == "body":
                    B = B and not r
            elif part == "pattern":
                P = P or r
            elif part == "recess":
                B = B and not r
                if self.joined:
                    W = W and not r
            elif part == "trim":
                B = B and r
                if self.joined:
                    W = W and r
        return B, W, P

    def top(self, f):
        """The colour seen from above for flags f, or None."""
        for k in range(len(self.slabs) - 1, -1, -1):
            B, W, P = self.materials(k, f)
            if P:
                return self.pattern_colour
            if W:
                return "white"
            if B:
                return "body"
        return None


def bodies(plan) -> List[dict]:
    d = _d(plan)
    m = _Model(d)
    out = []
    prev = {}
    for k, (a, b) in enumerate(m.slabs):
        sig = tuple(m.active[k]) + (("body",) if m.body is not None and
                                     m.body_z[0] < (a + b) / 2.0 < m.body_z[1] else ())
        for what, idx in (("body", 0), ("white", 1), ("pattern", 2)):
            if prev.get(what, (None,))[0] == sig:
                prev[what][1]["z"][1] = b             # the same region: one taller prism
                continue
            idxs = list(m.active[k]) + ([m.body] if m.body is not None else [])
            n = len(m.groups)

            def expr(fs, k=k, idx=idx, idxs=idxs, n=n):
                f = [False] * n
                for j, i in enumerate(idxs):
                    f[i] = fs[j]
                return m.materials(k, f)[idx]
            traps = RG.boolean([m.groups[i] for i in idxs], expr)
            if not traps:
                prev[what] = (sig, {"z": [a, b]})
                continue
            colour = {"body": "body", "white": "white", "pattern": m.pattern_colour}[what]
            rec = {"what": what, "colour": colour, "z": [a, b], "polygons": RG.polygons(traps),
                   "_traps": traps}
            out.append(rec)
            prev[what] = (sig, rec)
    return out


def top(plan) -> Dict[str, list]:
    """{colour: polygons} of the top view."""
    d = _d(plan)
    m = _Model(d)
    out = {}
    for c in ("body", "white", "black"):
        traps = RG.boolean(m.groups, lambda f, c=c: m.top(f) == c)
        if traps:
            out[c] = RG.polygons(traps)
    return out


def prism(traps, z0, z1):
    """(positions [[x, y, z]], triangles [[i, j, k]]) of a region (its
    trapezoids, plan/region.py) extruded z0..z1: top, bottom and walls,
    outward normals. Each connected piece is its own closed shell (pieces
    that touch at a corner do not share vertices), so every edge is in
    exactly two triangles."""
    pos: List[Tuple[float, float, float]] = []
    tris = []
    for comp in RG.components(traps):
        index: Dict[Tuple[float, float, float], int] = {}

        def v(p, z):
            key = (p[0], p[1], z)
            i = index.get(key)
            if i is None:
                i = index[key] = len(pos)
                pos.append(key)
            return i
        edges, ys_at = RG.boundary(comp)
        for c, a, b in RG.faces(comp, ys_at):
            tris.append((v(c, z1), v(a, z1), v(b, z1)))          # top: CCW seen from +z
            tris.append((v(c, z0), v(b, z0), v(a, z0)))          # bottom
        for a, b in edges:
            # the region on the left of a -> b: the wall faces right (outward)
            tris.append((v(a, z0), v(b, z0), v(b, z1)))
            tris.append((v(a, z0), v(b, z1), v(a, z1)))
    pos, tris = _split_pinches(pos, tris)
    return [list(p) for p in pos], [list(t) for t in tris]


def _split_pinches(pos, tris):
    """A vertex where the solid only touches itself (two cells meeting at a
    corner): one copy per fan of triangles around it, so every edge is in
    exactly two triangles."""
    from collections import defaultdict
    inc = defaultdict(list)
    for t, tri in enumerate(tris):
        for v in tri:
            inc[v].append(t)
    tris = [list(t) for t in tris]
    pos = list(pos)
    for v, ts in inc.items():
        if len(ts) < 3:
            continue
        # triangles around v connected through an edge (v, w)
        by_w = defaultdict(list)
        for t in ts:
            for w in tris[t]:
                if w != v:
                    by_w[w].append(t)
        parent = {t: t for t in ts}

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for w, tt in by_w.items():
            if len(tt) == 2:
                a, b = find(tt[0]), find(tt[1])
                if a != b:
                    parent[a] = b
        fans = defaultdict(list)
        for t in ts:
            fans[find(t)].append(t)
        if len(fans) < 2:
            continue
        for k, (_root, fan) in enumerate(sorted(fans.items())):
            if k == 0:
                continue
            nv = len(pos)
            pos.append(pos[v])
            for t in fan:
                tris[t] = [nv if x == v else x for x in tris[t]]
    return pos, tris


def _public(b):
    return {k: v for k, v in b.items() if not k.startswith("_")}


def mesh(plan, what: Optional[Sequence[str]] = None) -> List[dict]:
    out = []
    for b in bodies(plan):
        if what and b["what"] not in what:
            continue
        pos, tri = prism(b["_traps"], b["z"][0], b["z"][1])
        out.append({"what": b["what"], "colour": b["colour"], "z": b["z"],
                    "positions": [round(c, 6) + 0.0 for p in pos for c in p],
                    "indices": [i for t in tri for i in t]})
    return out


def stl(plan, what: Optional[Sequence[str]] = None, name: str = "arucostudio") -> bytes:
    """Binary STL (mm) of the plan's bodies."""
    tris = []
    for b in bodies(plan):
        if what and b["what"] not in what:
            continue
        pos, tri = prism(b["_traps"], b["z"][0], b["z"][1])
        tris += [(pos[i], pos[j], pos[k]) for i, j, k in tri]
    head = name.encode("ascii", "replace")[:80].ljust(80, b" ")
    out = [head, struct.pack("<I", len(tris))]
    for a, b, c in tris:
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        ln = (nx * nx + ny * ny + nz * nz) ** 0.5 or 1.0
        out.append(struct.pack("<12fH", nx / ln, ny / ln, nz / ln, *a, *b, *c, 0))
    return b"".join(out)


def volume(positions, indices) -> float:
    """The signed volume of a closed mesh (divergence theorem)."""
    p = [positions[i:i + 3] for i in range(0, len(positions), 3)]
    v = 0.0
    for t in range(0, len(indices), 3):
        a, b, c = p[indices[t]], p[indices[t + 1]], p[indices[t + 2]]
        v += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
              + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
    return v
