"""The design document (`arucostudio.scene/2`, docs/FILE_FORMAT.md): sketches
of shapes, Extrude and ArUco Extrude features, the ids. Standard library
only; never opens a file (server/ reads and writes them).

| Function | Does |
|---|---|
| `compile(doc, presets)` | -> `(Scene, [Issue])`: today's Scene (scene/model.py), so the plan, the numbering, the sheet and the exports run unchanged. An Issue's `field` is its JSON path (`features[1].aruco`) |
| `doc_from_scene(scene)` | a Scene as a design document: each tag a sketch at its place holding one shape (its target's loops; a box target writes `rect`), an Extrude when the target had a body, an ArUco Extrude with the exact `settings` / `numbers` (the `/1` migration and the old routes' new tags) |
| `write_back(doc, scene, presets)` | a Scene changed through the Scene API (add, delete, rename, move, edit, renumber, overrides) written back into the document: changed features get exact `settings` / `numbers` and lose their sugar; a multi-face list stays one feature while its faces agree and splits when one differs |
| `add_tag`, `delete_tag`, `rename_tag`, `move_tag` | the single edits `write_back` is made of |
| `shapes_2d(doc)` | every shape's loops on the canvas (mm), for drawings |
| `freeze(doc, presets)` | the presets a sugar feature names, copied into `frozen_presets` (once; unused ones dropped): sugar expands against the copy, so a changed PrusaSlicer profile never changes a typed tag by itself (the server calls it on open and on every write) |

`presets` is a function name -> a preset dict (or None), or a dict; the
compile never reads a file. Sugar on an ArUco Extrude expands through
`plan/newtag.new_spec` (what today's dialog stores for a fresh tag), so a
typed file gets exactly what a Fusion dialog or POST /api/new would store.
"""
from __future__ import annotations

import copy
import math
import re
from typing import Callable, Dict, List, Optional, Tuple, Union

from ..core import form as _F
from ..plan import newtag as _NEW
from ..plan import shapes as _SH
from ..plan.spec import Issue, TagSpec
from ..plan.target import SpecTypeError, Target
from .model import NAME_BAD, Scene, SceneTag, mat_mul, pose_of

SCHEMA = "arucostudio.scene/2"

TOP_KEYS = ("schema", "name", "units", "preset", "sheet", "sketches", "features", "overrides",
            "ledger", "presets_used", "frozen_presets", "note")
FROZEN = "frozen_presets"          # {preset name: the preset as the sugar was first expanded with}
SKETCH_KEYS = ("id", "at", "rot", "shapes", "name", "note")
SHAPE_KEYS = ("id", "at", "rot", "name", "holes", "note") + _SH.KINDS
EXTRUDE_KEYS = ("id", "extrude", "height", "name", "note")
# an ArUco Extrude: the sugar (typed by a person or an AI; replaced by the
# exact dicts on the Studio's first write of the feature) ...
SUGAR = ("preset", "layout", "dictionary", "first_id", "size", "square", "cols", "rows", "turn",
         "mark", "pins", "holes", "perimeter", "mode", "op", "label")
SUGAR_SETTINGS = ("layout", "dictionary", "cols", "rows", "turn", "mark", "pins", "holes",
                  "perimeter", "mode", "op", "label", "size", "square")
SUGAR_NUMBERS = ("size", "square")
# ... and what is kept exactly
EXACT = ("id", "aruco", "settings", "numbers", "name", "key", "target", "over", "uid", "locked",
         "hidden", "marker_ids", "note")
LABEL_WORDS = {"#id": "id", "#id + name": "id_name", "name": "name", "Name": "name",
               "Dictionary #id": "dict_id", "dictionary #id": "dict_id"}
ID_BAD = re.compile(r"[.\s+|]")

Presets = Union[None, Dict[str, dict], Callable[[str], Optional[dict]]]
Xf = Tuple[float, float, float]          # a 2D placement: x, y (mm), rotation (deg, CCW)
IDENT: Xf = (0.0, 0.0, 0.0)


class DesignError(ValueError):
    pass


# ------------------------------------------------------------ 2D placements

def compose(a: Xf, b: Xf) -> Xf:
    """a after b: b's frame placed in a's."""
    if b == IDENT or (not b[0] and not b[1] and not b[2]):
        return a
    if a == IDENT or (not a[0] and not a[1] and not a[2]):
        return b
    c, s = _SH._cos_sin(a[2])
    return (a[0] + c * b[0] - s * b[1], a[1] + s * b[0] + c * b[1], a[2] + b[2])


def invert(a: Xf) -> Xf:
    c, s = _SH._cos_sin(-a[2])
    return (-(c * a[0] - s * a[1]), -(s * a[0] + c * a[1]), -a[2])


def xf_matrix(a: Xf) -> List[float]:
    return pose_of(a[0], a[1], a[2])


def _clean(v: float) -> float:
    """A computed coordinate without float dust (1e-9 mm)."""
    r = round(v, 9)
    return 0.0 if r == 0 else (float(round(r)) if abs(r - round(r)) < 1e-9 else r)


# ------------------------------------------------------------ reading the doc

def _presets_fn(presets: Presets) -> Callable[[str], Optional[dict]]:
    if presets is None:
        return lambda name: None
    if callable(presets):
        return presets
    return lambda name: presets.get(name)


def _frozen_first(doc, resolve, issues=None):
    """name -> the file's frozen copy of that preset, else `resolve(name)`."""
    fr = doc.get(FROZEN)
    if fr is None:
        return resolve
    if not isinstance(fr, dict):
        if issues is not None:
            issues.append(Issue(FROZEN, "error", "frozen_presets: {preset name: a preset}"))
        return resolve
    bad = [k for k, v in fr.items() if not isinstance(v, dict)]
    if bad and issues is not None:
        issues.append(Issue(f"{FROZEN}.{bad[0]}", "error",
                            "a frozen preset is an object (the preset's JSON)"))

    def get(name):
        v = fr.get(name)
        return v if isinstance(v, dict) else resolve(name)
    return get


def is_sugar(f) -> bool:
    """An ArUco Extrude still expanded from its sugar (no exact settings or numbers)."""
    return isinstance(f, dict) and "aruco" in f and (f.get("settings") is None
                                                       or f.get("numbers") is None)


def sugar_presets(doc) -> List[str]:
    """The preset names the sugar features expand with (a feature's, else the file's)."""
    out: List[str] = []
    for f in doc.get("features") or []:
        if is_sugar(f):
            name = f.get("preset", doc.get("preset"))
            if isinstance(name, str) and name not in out:
                out.append(name)
    return out


def freeze(doc, presets: Presets = None) -> bool:
    """Copy each preset a sugar feature names into `doc["frozen_presets"]`
    (in place), unless it is there already, and drop the copies no sugar
    feature names any more. A name the catalog does not know is left out
    (the compile's warn says "Default used"). -> True when `doc` changed.

    Why: sugar expands against a preset; without the copy a changed
    PrusaSlicer profile would change a typed tag at its next compile, with
    no word. With it, the tag keeps what it was made with and the "Apply?"
    info (server/prusa_watch.stale) offers the new profile."""
    fr = doc.get(FROZEN)
    if fr is not None and not isinstance(fr, dict):
        return False                                # the compile reports it
    fr = dict(fr or {})
    resolve = _presets_fn(presets)
    want = sugar_presets(doc)
    changed = False
    for name in want:
        if isinstance(fr.get(name), dict):
            continue
        p = resolve(name)
        if isinstance(p, dict):
            fr[name] = copy.deepcopy(p)
            changed = True
    for name in [k for k in fr if k not in want]:
        del fr[name]
        changed = True
    if fr:
        if doc.get(FROZEN) != fr:
            doc[FROZEN] = fr
    elif FROZEN in doc:
        del doc[FROZEN]
        changed = True
    return changed


def _xf_of(d, path, issues) -> Xf:
    at = d.get("at")
    x = y = 0.0
    if at is not None:
        try:
            x, y = _SH._pt(at, f"{path}.at")
        except _SH.ShapeError as exc:
            issues.append(Issue(exc.path, "error", exc.message))
    rot = d.get("rot")
    r = 0.0
    if rot is not None:
        if isinstance(rot, bool) or not isinstance(rot, (int, float)) or not math.isfinite(rot):
            issues.append(Issue(f"{path}.rot", "error", f"degrees, not {rot!r}"))
        else:
            r = float(rot)
    return (x, y, r)


def _unknown(d, known, path, issues):
    for k in d:
        if k not in known:
            issues.append(Issue(f"{path}.{k}" if path else k, "info",
                                f"{k!r} is not a key ArUco Studio reads: kept as it is"))


def _id_ok(v) -> bool:
    return isinstance(v, str) and bool(v) and not ID_BAD.search(v)


def all_ids(doc) -> Dict[str, str]:
    """Every id in the document -> what it is (sketch, shape, body, tag)."""
    out = {}
    for sk in doc.get("sketches") or []:
        if isinstance(sk, dict):
            if isinstance(sk.get("id"), str):
                out[sk["id"]] = "sketch"
            for sh in sk.get("shapes") or []:
                if isinstance(sh, dict) and isinstance(sh.get("id"), str):
                    out[sh["id"]] = "shape"
    for f in doc.get("features") or []:
        if isinstance(f, dict) and isinstance(f.get("id"), str):
            out[f["id"]] = "body" if "extrude" in f else "tag"
    return out


class _Shape:
    def __init__(self, sid, shape, path, si, sj, xf):
        self.id, self.shape, self.path, self.si, self.sj, self.xf = sid, shape, path, si, sj, xf
        self.ok = True


def _refs(f) -> List[str]:
    a = f.get("aruco")
    if isinstance(a, str):
        return [a]
    if isinstance(a, list):
        return [r for r in a if isinstance(r, str)]
    return []


def _label_of(v, path, issues) -> Optional[dict]:
    if v is None or v is False or v == "":
        return {"on": False}
    if v is True:
        return {"on": True}
    if isinstance(v, str):
        if v in LABEL_WORDS:
            return {"on": True, "content": LABEL_WORDS[v]}
        return {"on": True, "content": "custom", "text": v}
    if isinstance(v, dict):
        return dict(v)
    issues.append(Issue(path, "error", "a label: \"#id\", \"#id + name\", \"name\", your "
                                       "text, or an object of label settings"))
    return None


def _sugar(f, s, n, has_body, fp, issues):
    """The typed sugar keys into settings `s` / numbers `n` (in place)."""
    def num(k, positive=False, whole=False):
        v = f[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            issues.append(Issue(f"{fp}.{k}", "error", f"a number, not {v!r}"))
            return None
        if whole and float(v) != int(v):
            issues.append(Issue(f"{fp}.{k}", "error", f"a whole number, not {v!r}"))
            return None
        if positive and v < 1:
            issues.append(Issue(f"{fp}.{k}", "error", f"1 or more, not {v!r}"))
            return None
        return v
    if s is not None:
        for k, key in (("dictionary", "dictionary"), ("mark", "corner_mark"), ("pins", "pin"),
                       ("holes", "holes"), ("op", "op")):
            if k in f:
                s[key] = copy.deepcopy(f[k])
        if "turn" in f:
            v = num("turn")
            if v is not None:
                s["turn"] = v
        if "mode" in f:
            s["mode"] = _F.mode_for(f["mode"], has_body)
        if "cols" in f or "rows" in f:
            if "cols" in f and "rows" in f:
                c, r = num("cols", True, True), num("rows", True, True)
                if c is not None and r is not None:
                    s["force"] = [int(c), int(r)]
            else:
                issues.append(Issue(f"{fp}.{'rows' if 'cols' in f else 'cols'}", "error",
                                    "cols and rows go together"))
        if "label" in f:
            lab = _label_of(f["label"], f"{fp}.label", issues)
            if lab is not None:
                s["label"] = dict(s.get("label") or {}, **lab)
        if "perimeter" in f:
            v = f["perimeter"]
            if v not in ("marker", "profile"):
                issues.append(Issue(f"{fp}.perimeter", "error",
                                    f"perimeter: \"marker\" or \"profile\", not {v!r}"))
            elif has_body:
                s["trim"] = "both" if v == "profile" else "off"    # a 3D tag's Perimeter IS Trim
            else:
                s["make"] = dict(s.get("make") or {}, perimeter=v)
    if n is not None:
        for k in SUGAR_NUMBERS:
            if k in f:
                v = num(k)
                if v is not None:
                    n[k] = float(v)
                    if v > 0 and s is not None:
                        s["size_auto"] = False


def _tag_spec(f, fp, target: Target, tag_name: str, k: int, single: bool, doc_preset,
              resolve, overrides, issues) -> Optional[TagSpec]:
    exact_s, exact_n = f.get("settings"), f.get("numbers")
    for key, v in (("settings", exact_s), ("numbers", exact_n)):
        if v is not None and not isinstance(v, dict):
            issues.append(Issue(f"{fp}.{key}", "error", "an object"))
            return None
    has_body = bool(target.has_body)
    if exact_s is None or exact_n is None:
        layout = f.get("layout", (exact_s or {}).get("layout", "single"))
        pname = f.get("preset", doc_preset)
        preset = None
        if pname is not None:
            if not isinstance(pname, str):
                issues.append(Issue(f"{fp}.preset", "error", "a preset's name"))
            else:
                preset = resolve(pname)
                if preset is None and k == 0:
                    issues.append(Issue(f"{fp}.preset" if "preset" in f else "preset", "warn",
                                        f"no preset {pname!r} here: Default used"))
        try:
            base = _NEW.new_spec(layout, target.to_dict(), preset, marker_id=0,
                                 name=f.get("name", "") if isinstance(f.get("name", ""), str)
                                 else "", key="")
        except ValueError as exc:
            issues.append(Issue(f"{fp}.layout", "error", str(exc)))
            return None
        s = base["settings"] if exact_s is None else None
        n = base["numbers"] if exact_n is None else None
        _sugar(f, s, n, has_body, fp, issues)
    else:
        s = n = None
    if exact_s is not None:
        s = copy.deepcopy(exact_s)
        if k == 0:
            for key in SUGAR_SETTINGS:
                if key in f and key not in SUGAR_NUMBERS:
                    issues.append(Issue(f"{fp}.{key}", "info",
                                        f"{key!r} not used: `settings` holds the exact settings"))
    if exact_n is not None:
        n = dict(exact_n)
    mids = f.get("marker_ids")
    if mids is not None:
        if (not isinstance(mids, list) or single or len(mids) != len(_refs(f))
                or any(isinstance(m, bool) or not isinstance(m, int) for m in mids)):
            if k == 0:
                issues.append(Issue(f"{fp}.marker_ids", "error",
                                    "one whole number per face of the list"))
        else:
            n["marker_id"] = int(mids[k])
    fid = f.get("first_id")
    if fid is not None:
        bad = object()
        if single:
            v = bad if isinstance(fid, list) else fid
        else:
            v = fid[k] if isinstance(fid, list) and k < len(fid) else bad
        if v is bad:
            if k == 0:
                issues.append(Issue(f"{fp}.first_id", "error",
                                    "a whole number (on a list: a list of them, one per face)"))
        elif v is not None:
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                issues.append(Issue(f"{fp}.first_id", "error",
                                    f"a first id is a whole number, 0 or more, not {v!r}"))
            else:
                overrides[tag_name] = int(v)
                n["marker_id"] = int(v)
    name = f.get("name", "")
    key = f["key"] if "key" in f else tag_name
    d = {"schema": "arucostudio.tagspec/1", "settings": s, "numbers": n,
         "target": target.to_dict(), "name": name, "key": key}
    try:
        return TagSpec.from_dict(d)
    except SpecTypeError as exc:
        issues.append(Issue(f"{fp}.{exc.path}" if exc.path else fp, "error", exc.message))
        return None


def compile(doc, presets: Presets = None) -> Tuple[Scene, List[Issue]]:
    """The design document -> (today's Scene, [Issue]). Never raises on a
    bad feature: it is an `error` on its path and the rest compiles."""
    if not isinstance(doc, dict):
        raise DesignError("a design document is a JSON object")
    issues: List[Issue] = []
    resolve = _frozen_first(doc, _presets_fn(presets), issues)
    _unknown(doc, TOP_KEYS, "", issues)
    ov = doc.get("overrides") or {}
    if not isinstance(ov, dict) or not all(isinstance(v, int) and not isinstance(v, bool)
                                           for v in ov.values()):
        issues.append(Issue("overrides", "error", "overrides: {tag name: first id}"))
        ov = {}
    sc = Scene(name=str(doc.get("name") or "scene"), ledger=copy.deepcopy(doc.get("ledger")),
               overrides=dict(ov))
    seen: Dict[str, str] = {}

    def claim(i, path):
        if not _id_ok(i):
            issues.append(Issue(f"{path}.id", "error",
                                f"an id: a short string without dots or spaces, not {i!r}"))
            return False
        if i in seen:
            issues.append(Issue(f"{path}.id", "error", f"the id {i!r} is taken by {seen[i]}"))
            return False
        seen[i] = path
        return True

    shapes: Dict[str, _Shape] = {}
    sketches = doc.get("sketches") or []
    if not isinstance(sketches, list):
        issues.append(Issue("sketches", "error", "a list of sketches"))
        sketches = []
    for i, sk in enumerate(sketches):
        p = f"sketches[{i}]"
        if not isinstance(sk, dict):
            issues.append(Issue(p, "error", "a sketch: {id, at, rot, shapes}"))
            continue
        _unknown(sk, SKETCH_KEYS, p, issues)
        claim(sk.get("id"), p)
        sxf = _xf_of(sk, p, issues)
        shs = sk.get("shapes") or []
        if not isinstance(shs, list):
            issues.append(Issue(f"{p}.shapes", "error", "a list of shapes"))
            continue
        for j, sh in enumerate(shs):
            sp = f"{p}.shapes[{j}]"
            if not isinstance(sh, dict):
                issues.append(Issue(sp, "error", "a shape: one of " + ", ".join(_SH.KINDS)))
                continue
            _unknown(sh, SHAPE_KEYS, sp, issues)
            sid = sh.get("id")
            rec = _Shape(sid, sh, sp, i, j, compose(sxf, _xf_of(sh, sp, issues)))
            try:
                _SH.stroke(sh)
            except _SH.ShapeError as exc:
                issues.append(Issue(f"{sp}.{exc.path}" if exc.path else sp, "error", exc.message))
                rec.ok = False
            for k, h in enumerate(sh.get("holes") or [] if isinstance(sh.get("holes"), list)
                                  else []):
                if isinstance(h, dict):
                    _unknown(h, SHAPE_KEYS, f"{sp}.holes[{k}]", issues)
            if sid is not None and claim(sid, sp):
                shapes[sid] = rec

    bodies: Dict[str, Tuple[_Shape, float, str]] = {}
    feats = doc.get("features") or []
    if not isinstance(feats, list):
        issues.append(Issue("features", "error", "a list of features"))
        feats = []
    names: Dict[str, str] = {}
    used_presets: List[str] = []
    doc_preset = doc.get("preset")
    if isinstance(doc_preset, str):
        used_presets.append(doc_preset)
    for i, f in enumerate(feats):
        fp = f"features[{i}]"
        if not isinstance(f, dict):
            issues.append(Issue(fp, "error", "a feature: an Extrude or an ArUco Extrude"))
            continue
        if "extrude" in f:
            _unknown(f, EXTRUDE_KEYS, fp, issues)
            if not claim(f.get("id"), fp):
                continue
            src = f.get("extrude")
            rec = shapes.get(src) if isinstance(src, str) else None
            if rec is None:
                issues.append(Issue(f"{fp}.extrude", "error", f"no shape {src!r} to extrude"))
                continue
            h = f.get("height")
            if isinstance(h, bool) or not isinstance(h, (int, float)) or not h \
                    or not math.isfinite(h):
                issues.append(Issue(f"{fp}.height", "error",
                                    f"a height in mm other than 0, not {h!r}"))
                continue
            if rec.ok:
                bodies[f["id"]] = (rec, float(h), fp)
            continue
        if "aruco" not in f:
            issues.append(Issue(fp, "error", "an unknown feature: an Extrude has \"extrude\", "
                                             "an ArUco Extrude \"aruco\""))
            continue
        _unknown(f, EXACT + SUGAR, fp, issues)
        fid = f.get("id")
        if not isinstance(fid, str) or not fid or NAME_BAD.search(fid) or re.search(r"\s", fid):
            issues.append(Issue(f"{fp}.id", "error", f"a tag's id: a string without spaces, "
                                                     f"+ or |, not {fid!r}"))
            continue
        if fid in seen:
            issues.append(Issue(f"{fp}.id", "error", f"the id {fid!r} is taken by {seen[fid]}"))
            continue
        seen[fid] = fp
        a = f["aruco"]
        single = isinstance(a, str)
        refs = [a] if single else a
        if not isinstance(refs, list) or not refs or not all(isinstance(r, str) for r in refs):
            issues.append(Issue(f"{fp}.aruco", "error",
                                "a shape's id, \"<body>.<face>\", or a list of them"))
            continue
        if isinstance(f.get("preset"), str) and f["preset"] not in used_presets:
            used_presets.append(f["preset"])
        for k, ref in enumerate(refs):
            rp = f"{fp}.aruco" + ("" if single else f"[{k}]")
            got = _resolve(ref, rp, f, fp, shapes, bodies, issues)
            if got is None:
                continue
            target, shape_rec, net, frame, src = got
            label = ref.split(".")[-1]
            tname = fid if single else f"{fid}.{label}"
            if tname in names:
                issues.append(Issue(rp, "error", f"two tags named {tname!r} "
                                                 f"({names[tname]} and {rp})"))
                continue
            spec = _tag_spec(f, fp, target, tname, k, single, doc_preset, resolve,
                             sc.overrides, issues)
            if spec is None:
                continue
            names[tname] = rp
            canvas = compose(shape_rec.xf, net)
            uid = f.get("uid")
            uid = (str(uid) if uid else fid) if single else f"{uid or fid}.{label}"
            t = SceneTag(name=tname, spec=spec, x_mm=canvas[0], y_mm=canvas[1],
                         rotation_deg=canvas[2], locked=bool(f.get("locked", False)),
                         hidden=bool(f.get("hidden", False)), uid=uid)
            p3 = mat_mul(xf_matrix(shape_rec.xf), frame)
            if p3 != t.pose:
                t.pose_3d = [_clean(v) for v in p3]
            src.update(feature=i, entry=None if single else k, ref=ref, shape=shape_rec.id,
                       sketch=(sketches[shape_rec.si] or {}).get("id"), local=list(net))
            if src.get("hinge"):
                xf = shape_rec.xf
                src["hinge_xy"] = [list(q) for q in _SH.place(src["hinge"], (xf[0], xf[1]),
                                                               xf[2])]
            t.source = src
            sc.tags.append(t)
    for n in list(sc.overrides):
        if n not in names:
            issues.append(Issue(f"overrides.{n}", "info",
                                f"an override for {n!r}, which is not a tag here: kept"))
    pu = doc.get("presets_used")
    sc.presets_used = list(pu) if isinstance(pu, list) else used_presets
    out, seen_issue = [], set()
    for x in issues:                              # a file-level message once
        if (x.field, x.text) not in seen_issue:
            seen_issue.add((x.field, x.text))
            out.append(x)
    return sc, out


def _resolve(ref, rp, f, fp, shapes, bodies, issues):
    """(Target, shape record, the 2D net placement, the 3D frame, source) of one reference."""
    over = f.get("over")
    if "." in ref:
        bid, face = ref.split(".", 1)
        if bid not in bodies:
            if bid in shapes:
                msg = f"{bid!r} is a shape, not a body: extrude it, or put the tag on the shape"
            else:
                msg = f"no body {bid!r}: a body is an Extrude's id"
            issues.append(Issue(rp, "error", msg))
            return None
        rec, h, _bp = bodies[bid]
        try:
            ft = _SH.face_target(rec.shape, h, face)
        except _SH.ShapeError as exc:
            issues.append(Issue(rp, "error", f"{ref}: {exc.message}"))
            return None
        target, net, frame = ft.target, ft.net, ft.frame
        src = {"body": bid, "face": ft.face, "normal": list(ft.normal),
               "hinge": [list(p) for p in ft.hinge] if ft.hinge else None}
    else:
        if ref not in shapes:
            msg = (f"{ref!r} is a body: name its face ({ref}.top)" if ref in bodies
                   else f"no shape {ref!r}")
            issues.append(Issue(rp, "error", msg))
            return None
        rec = shapes[ref]
        if not rec.ok:
            issues.append(Issue(rp, "error", f"the shape {ref!r} has an error (above)"))
            return None
        target = _SH.bare_target(rec.shape)
        net, frame = IDENT, pose_of(0.0, 0.0, 0.0)
        src = {"body": None, "face": None, "normal": [0.0, 0.0, 1.0], "hinge": None}
        if over is not None:
            got = _over(rec, over, f"{fp}.over", bodies, issues)
            if got is None:
                return None
            target, frame = got
            src["over"] = over
    if f.get("target") is not None:
        try:
            target = Target.from_dict(f["target"])
        except SpecTypeError as exc:
            issues.append(Issue(f"{fp}.{exc.path}", "error", exc.message))
            return None
    return target, rec, net, frame, src


def _over(rec, over, path, bodies, issues):
    """A sketch area over a body (Fusion's profile case): kind "profile",
    the body under it, the body's top face measured by the trim."""
    if not isinstance(over, str) or over not in bodies:
        issues.append(Issue(path, "error", f"no body {over!r} under the shape"))
        return None
    brec, h, _bp = bodies[over]
    th = abs(h)
    rel = compose(invert(rec.xf), brec.xf)          # the body's shape frame in this shape's
    body_loops = [_SH.place(lp, (rel[0], rel[1]), rel[2]) for lp in _SH.stroke(brec.shape)]
    t = _SH.bare_target(rec.shape)
    us = [x for x, _y in body_loops[0]]
    vs = [y for _x, y in body_loops[0]]
    t.kind = "profile"
    t.has_body = True
    t.body_mm = {"u0": min(us), "v0": min(vs), "u1": max(us), "v1": max(vs), "z0": -th, "z1": 0.0,
                 "measured": True}
    t.body_loops_mm = body_loops
    t.face_loops_mm = body_loops
    frame = pose_of(0.0, 0.0, 0.0)
    frame[11] = max(0.0, h)
    return t, frame


def shapes_2d(doc) -> List[dict]:
    """[{sketch, shape, path, loops}] every shape that strokes, its loops in
    canvas mm (outer counter-clockwise, then its holes)."""
    out = []
    issues: List[Issue] = []
    for i, sk in enumerate(doc.get("sketches") or []):
        if not isinstance(sk, dict):
            continue
        sxf = _xf_of(sk, f"sketches[{i}]", issues)
        for j, sh in enumerate(sk.get("shapes") or []):
            if not isinstance(sh, dict):
                continue
            try:
                loops = _SH.stroke(sh)
            except _SH.ShapeError:
                continue
            xf = compose(sxf, _xf_of(sh, "", issues))
            out.append({"sketch": sk.get("id"), "shape": sh.get("id"),
                        "path": f"sketches[{i}].shapes[{j}]",
                        "loops": [_SH.place(lp, (xf[0], xf[1]), xf[2]) for lp in loops]})
    return out


# ------------------------------------------------------------ a tag as parts

def _unique(base: str, taken) -> str:
    base = ID_BAD.sub("_", base) or "x"
    if base not in taken:
        return base
    k = 2
    while f"{base}{k}" in taken:
        k += 1
    return f"{base}{k}"


def _num_out(v: float):
    """A float written as it is (JSON keeps it exactly)."""
    return float(v)


def tag_parts(spec: TagSpec, name: str, x: float, y: float, rot: float, taken: set) -> \
        Tuple[dict, Optional[dict], dict]:
    """(sketch, extrude or None, ArUco Extrude) for one tag: a sketch at its
    place holding one shape (a box target writes `rect`, else its `loops`),
    an Extrude when its target is the top of a prism, and the feature with
    the exact settings / numbers. When the shape cannot say the target (a
    sketch profile, a flipped or measured face, ...) the feature carries the
    exact `target` too, so the tag plans byte for byte as before."""
    t = spec.target
    skid = _unique(f"{name}_sketch", taken)
    taken.add(skid)
    sid = _unique(f"{name}_shape", taken)
    taken.add(sid)
    if t.loops_mm:
        shape = {"id": sid, "loops": [[[_num_out(u), _num_out(v)] for u, v in lp]
                                      for lp in t.loops_mm]}
    else:
        shape = {"id": sid, "rect": [_num_out(t.w_mm), _num_out(t.h_mm)]}
    if t.name:
        shape["name"] = t.name
    extrude = None
    ref = sid
    want = t.to_dict()
    got = None
    try:
        b = t.body_mm or {}
        depth = (b.get("z1", 0.0) - b.get("z0", 0.0)) if b else 0.0
        if t.has_body and b and depth > 0 and t.kind == "face":
            bid = _unique(f"{name}_body", taken)
            got = _SH.face_target(shape, -depth, "top").target.to_dict()
            if got == want:
                taken.add(bid)
                # extruded downwards: the tag's face stays at z 0, as the target editor's was
                extrude = {"id": bid, "extrude": sid, "height": -_num_out(depth)}
                ref = f"{bid}.top"
        if extrude is None:
            got = _SH.bare_target(shape).to_dict()
    except _SH.ShapeError:
        got = None
    feat = {"id": name, "aruco": ref, "settings": copy.deepcopy(spec.settings),
            "numbers": dict(spec.numbers)}
    if got != want:
        feat["target"] = want
    if spec.name:
        feat["name"] = spec.name
    if spec.key != name:
        feat["key"] = spec.key
    sk = {"id": skid}
    if x or y:
        sk["at"] = [_num_out(x), _num_out(y)]
    if rot:
        sk["rot"] = _num_out(rot)
    sk["shapes"] = [shape]
    return sk, extrude, feat


def doc_from_scene(scene: Scene) -> dict:
    """A Scene as a design document (the `/1` migration; dumps of a Scene)."""
    doc = {"schema": SCHEMA, "name": scene.name, "sketches": [], "features": []}
    for t in scene.tags:
        add_tag(doc, t.spec, t.x_mm, t.y_mm, t.rotation_deg, name=t.name, locked=t.locked,
                hidden=t.hidden, uid=t.uid, exact=True)
    if scene.overrides:
        doc["overrides"] = dict(scene.overrides)
    if scene.ledger is not None:
        doc["ledger"] = copy.deepcopy(scene.ledger)
    if scene.presets_used:
        doc["presets_used"] = list(scene.presets_used)
    return doc


def add_tag(doc, spec: TagSpec, x: float = 0.0, y: float = 0.0, rot: float = 0.0,
            name: str = "tag1", locked: bool = False, hidden: bool = False,
            uid: Optional[str] = None, index: Optional[int] = None, exact: bool = False) -> str:
    """A tag as new parts at the end of the document (or at feature `index`).
    Its key is its name when it has none (as Scene.add), unless `exact`."""
    if not spec.key and not exact:
        spec = copy.deepcopy(spec)
        spec.key = name
    taken = set(all_ids(doc))
    sk, ex, feat = tag_parts(spec, name, x, y, rot, taken)
    if uid and uid != name:
        feat["uid"] = uid
    if locked:
        feat["locked"] = True
    if hidden:
        feat["hidden"] = True
    doc.setdefault("sketches", []).append(sk)
    fs = doc.setdefault("features", [])
    new = ([ex] if ex else []) + [feat]
    if index is None or index >= len(fs):
        fs.extend(new)
    else:
        fs[index:index] = new
    return name


# ------------------------------------------------------------ edits

def _tag_index(doc, presets) -> Dict[str, SceneTag]:
    sc, _ = compile(doc, presets)
    return {t.name: t for t in sc.tags}


def _referenced(doc) -> Tuple[Dict[str, int], Dict[str, int]]:
    """How many features reference each shape and each body."""
    shapes: Dict[str, int] = {}
    bodies: Dict[str, int] = {}
    for f in doc.get("features") or []:
        if not isinstance(f, dict):
            continue
        if "extrude" in f and isinstance(f.get("extrude"), str):
            shapes[f["extrude"]] = shapes.get(f["extrude"], 0) + 1
        for r in _refs(f):
            if "." in r:
                b = r.split(".", 1)[0]
                bodies[b] = bodies.get(b, 0) + 1
            else:
                shapes[r] = shapes.get(r, 0) + 1
        if isinstance(f.get("over"), str):
            bodies[f["over"]] = bodies.get(f["over"], 0) + 1
    return shapes, bodies


def _gc(doc, refs: List[str]) -> None:
    """After a tag left: the bodies and shapes it alone used go too (a tag
    of the old Studio owns its target), and a sketch left empty."""
    shapes_ref, bodies_ref = _referenced(doc)
    gone_shapes = set()
    for r in refs:
        if "." in r:
            b = r.split(".", 1)[0]
            if bodies_ref.get(b, 0) == 0:
                for f in list(doc.get("features") or []):
                    if isinstance(f, dict) and f.get("id") == b and "extrude" in f:
                        doc["features"].remove(f)
                        gone_shapes.add(f.get("extrude"))
        else:
            gone_shapes.add(r)
    shapes_ref, _ = _referenced(doc)
    for sk in list(doc.get("sketches") or []):
        if not isinstance(sk, dict):
            continue
        shs = sk.get("shapes") or []
        keep = [s for s in shs if not (isinstance(s, dict) and s.get("id") in gone_shapes
                                       and shapes_ref.get(s.get("id"), 0) == 0)]
        if len(keep) != len(shs):
            if keep:
                sk["shapes"] = keep
            else:
                doc["sketches"].remove(sk)


def _detach(doc, src: dict) -> Tuple[int, dict]:
    """Take one tag out of its feature: the feature goes (a single tag) or
    loses that entry (a list). -> (the feature's index, the feature as it was)."""
    fi = src["feature"]
    f = doc["features"][fi]
    old = copy.deepcopy(f)
    if src["entry"] is None:
        doc["features"].pop(fi)
        _gc(doc, _refs(old))
    else:
        refs = list(f["aruco"])
        k = src["entry"]
        gone = refs.pop(k)
        f["aruco"] = refs
        for key in ("marker_ids", "first_id"):
            if isinstance(f.get(key), list) and len(f[key]) > k:
                f[key] = f[key][:k] + f[key][k + 1:]
        if not refs:
            doc["features"].pop(fi)
        _gc(doc, [gone])
    return fi, old


def delete_tag(doc, name: str, presets: Presets = None) -> None:
    tags = _tag_index(doc, presets)
    if name not in tags:
        raise KeyError(name)
    _detach(doc, tags[name].source)
    (doc.get("overrides") or {}).pop(name, None)


def _single_of(f: dict, k: int, label: str, new_id: str) -> dict:
    """Entry k of a list feature as a feature of its own named `new_id`
    (its uid, key and marker id kept)."""
    g = copy.deepcopy(f)
    g["id"] = new_id
    g["aruco"] = f["aruco"][k]
    uid = f"{f.get('uid') or f['id']}.{label}"
    if uid != new_id:
        g["uid"] = uid
    else:
        g.pop("uid", None)
    mids = f.get("marker_ids")
    g.pop("marker_ids", None)
    if isinstance(mids, list) and k < len(mids):
        n = g.get("numbers")
        if isinstance(n, dict):
            g["numbers"] = dict(n, marker_id=int(mids[k]))
    fid = f.get("first_id")
    if isinstance(fid, list):
        if k < len(fid) and fid[k] is not None:
            g["first_id"] = fid[k]
        else:
            g.pop("first_id", None)
    if "key" not in f:
        key = f"{f['id']}.{label}"               # the list tag's key, kept
        if key != new_id:
            g["key"] = key
    return g


def rename_tag(doc, old: str, new: str, presets: Presets = None) -> None:
    tags = _tag_index(doc, presets)
    if old not in tags:
        raise KeyError(old)
    if not new or NAME_BAD.search(new) or re.search(r"\s", new):
        raise ValueError(f"a tag name cannot be empty or hold spaces, + or |: {new!r}")
    if new == old:
        return
    if new in tags:
        raise ValueError(f"there is a tag {new!r} already")
    ids = all_ids(doc)
    if new in ids:
        raise ValueError(f"the name {new!r} is taken by a {ids[new]} of the file")
    src = tags[old].source
    fi = src["feature"]
    f = doc["features"][fi]
    if src["entry"] is None:
        if "uid" not in f:
            f["uid"] = f["id"]                  # the ledger knows the tag by it
        f["id"] = new
        if "key" not in f:
            f["key"] = old                      # the record's key stays (as Scene.rename)
    else:
        k = src["entry"]
        g = _single_of(f, k, f["aruco"][k].split(".")[-1], new)
        if len(f["aruco"]) == 1:
            doc["features"][fi] = g
        else:
            f["aruco"] = f["aruco"][:k] + f["aruco"][k + 1:]
            for key in ("marker_ids", "first_id"):
                if isinstance(f.get(key), list) and len(f[key]) > k:
                    f[key] = f[key][:k] + f[key][k + 1:]
            doc["features"].insert(fi + 1, g)
    ov = doc.get("overrides")
    if isinstance(ov, dict) and old in ov:
        ov[new] = ov.pop(old)


def _anchor(doc, t: SceneTag):
    """(sketch dict, shape dict) the tag sits on."""
    sid = t.source["shape"]
    for sk in doc.get("sketches") or []:
        for sh in (sk.get("shapes") or []) if isinstance(sk, dict) else []:
            if isinstance(sh, dict) and sh.get("id") == sid:
                return sk, sh
    raise KeyError(sid)


def _set_xf(d: dict, xf: Xf) -> None:
    x, y, r = (_clean(xf[0]), _clean(xf[1]), xf[2])
    if x or y:
        d["at"] = [x, y]
    else:
        d.pop("at", None)
    if r:
        d["rot"] = r
    else:
        d.pop("rot", None)


def move_tag(doc, name: str, x: float, y: float, rot: float, presets: Presets = None) -> None:
    """Put a tag's canvas place at (x, y, rot) by moving what it sits on:
    its sketch when the shape is the sketch's only one, else the shape
    (its body and the other tags on it move with it)."""
    tags = _tag_index(doc, presets)
    if name not in tags:
        raise KeyError(name)
    t = tags[name]
    if (t.x_mm, t.y_mm, t.rotation_deg) == (x, y, rot):
        return
    sk, sh = _anchor(doc, t)
    issues: List[Issue] = []
    sxf = _xf_of(sk, "", issues)
    shxf = _xf_of(sh, "", issues)
    net = tuple(t.source.get("local") or IDENT)
    want = (float(x), float(y), float(rot))
    if len([s for s in sk.get("shapes") or [] if isinstance(s, dict)]) == 1:
        _set_xf(sk, compose(want, invert(compose(shxf, net))))
    else:
        _set_xf(sh, compose(invert(sxf), compose(want, invert(net))))


def _state(t: SceneTag) -> tuple:
    return (t.spec.to_dict(), bool(t.locked), bool(t.hidden))


def json_key(d) -> str:
    import json
    return json.dumps(d, sort_keys=True, separators=(",", ":"), default=str)


def _exact(f: dict, spec: TagSpec, tname: str, locked: bool, hidden: bool) -> dict:
    """The feature with exact settings / numbers and no sugar."""
    g = {k: copy.deepcopy(v) for k, v in f.items() if k not in SUGAR and k not in
         ("settings", "numbers", "name", "key", "locked", "hidden")}
    g["settings"] = copy.deepcopy(spec.settings)
    g["numbers"] = dict(spec.numbers)
    if spec.name:
        g["name"] = spec.name
    if spec.key != tname:
        g["key"] = spec.key
    if locked:
        g["locked"] = True
    if hidden:
        g["hidden"] = True
    return g


def _rewrite(doc, fi: int, cur: List[SceneTag], want: Dict[str, SceneTag]) -> List[str]:
    """Feature `fi` rewritten for the wanted states of its tags (exact
    settings / numbers, no sugar). A list stays one feature while its faces
    agree (their ids aside: `marker_ids`); else each face becomes a feature
    of its own, named as its tag was. -> the tags whose TARGET changed:
    they are re-made as parts of their own by the caller."""
    f = doc["features"][fi]
    redo = [t.name for t in cur if want[t.name].spec.target.to_dict() != t.spec.target.to_dict()]
    if isinstance(f.get("aruco"), str):
        t = cur[0]
        w = want[t.name]
        g = _exact(f, w.spec, t.name, w.locked, w.hidden)
        g.pop("marker_ids", None)
        doc["features"][fi] = g
        return redo

    def common(t: SceneTag):
        w = want[t.name]
        n = dict(w.spec.numbers)
        n.pop("marker_id", None)
        key = f"{f['id']}.{f['aruco'][t.source['entry']].split('.')[-1]}"
        return (json_key(w.spec.settings), json_key(n), w.spec.name, w.spec.key == key,
                w.locked, w.hidden)
    if not redo and len({common(t) for t in cur}) == 1 and len(cur) == len(f["aruco"]):
        w0 = want[cur[0].name]
        g = _exact(f, w0.spec, cur[0].name, w0.locked, w0.hidden)
        g.pop("key", None)
        n = dict(w0.spec.numbers)
        mids = [int(round(float(want[t.name].spec.numbers.get("marker_id", 0) or 0)))
                for t in cur]
        if len(set(mids)) > 1:
            n.pop("marker_id", None)
            g["marker_ids"] = mids
        else:
            g.pop("marker_ids", None)
        g["numbers"] = n
        doc["features"][fi] = g
        return redo
    out = []
    for t in sorted(cur, key=lambda t: t.source["entry"]):
        w = want[t.name]
        k = t.source["entry"]
        g = _single_of(f, k, f["aruco"][k].split(".")[-1], t.name)
        out.append(_exact(g, w.spec, t.name, w.locked, w.hidden))
    doc["features"][fi:fi + 1] = out
    return redo


def write_back(doc, scene: Scene, presets: Presets = None) -> dict:
    """`scene` (compiled from `doc`, then changed through the Scene API)
    written back into `doc`, in place. Tags are matched by uid (a rename
    keeps it), then by name. -> doc."""
    cur, _ = compile(doc, presets)
    cur_uids = {t.uid for t in cur.tags}
    by_uid = {w.uid: w for w in scene.tags}
    by_name = {w.name: w for w in scene.tags}
    matched: Dict[str, SceneTag] = {}           # current name -> wanted tag
    used = set()
    for c in cur.tags:
        w = by_uid.get(c.uid)
        if w is None:
            w = by_name.get(c.name)
            if w is not None and w.uid in cur_uids:
                w = None
        if w is not None and id(w) not in used:
            matched[c.name] = w
            used.add(id(w))
    for cname, w in list(matched.items()):                      # renames
        if w.name != cname:
            rename_tag(doc, cname, w.name, presets)
    matched = {w.name: w for w in matched.values()}
    for t in compile(doc, presets)[0].tags:                     # deletions
        if t.name not in matched:
            delete_tag(doc, t.name, presets)
    cur, _ = compile(doc, presets)                              # settings, numbers, flags
    by_feature: Dict[int, List[SceneTag]] = {}
    for t in cur.tags:
        by_feature.setdefault(t.source["feature"], []).append(t)
    redo: List[str] = []
    for fi in sorted(by_feature, reverse=True):
        ts = by_feature[fi]
        if any(_state(t) != _state(matched[t.name]) for t in ts):
            redo += _rewrite(doc, fi, ts, matched)
    for name in redo:                                           # a new target: new parts
        w = matched[name]
        tags = _tag_index(doc, presets)
        fi, _old = _detach(doc, tags[name].source)
        add_tag(doc, w.spec, w.x_mm, w.y_mm, w.rotation_deg, name=name, locked=w.locked,
                hidden=w.hidden, uid=w.uid, index=fi, exact=True)
    for t in compile(doc, presets)[0].tags:                     # places
        w = matched.get(t.name)
        if w is not None and (t.x_mm, t.y_mm, t.rotation_deg) != (w.x_mm, w.y_mm,
                                                                    w.rotation_deg):
            move_tag(doc, t.name, w.x_mm, w.y_mm, w.rotation_deg, presets)
    for w in scene.tags:                                        # new tags, in order
        if id(w) not in used:
            add_tag(doc, w.spec, w.x_mm, w.y_mm, w.rotation_deg, name=w.name, locked=w.locked,
                    hidden=w.hidden, uid=w.uid, exact=True)
    for f in doc.get("features") or []:                         # typed first ids: overrides now
        if isinstance(f, dict):
            f.pop("first_id", None)
    if scene.overrides:
        doc["overrides"] = dict(scene.overrides)
    else:
        doc.pop("overrides", None)
    if scene.ledger is not None:
        doc["ledger"] = copy.deepcopy(scene.ledger)
    else:
        doc.pop("ledger", None)
    doc["name"] = scene.name
    if compile(doc, presets)[0].presets_used != list(scene.presets_used):
        doc["presets_used"] = list(scene.presets_used)
    return doc
