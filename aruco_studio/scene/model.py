"""A Scene: many tags on one canvas (ARCHITECTURE 5.5). Standard library
only; never imports adapters/, server/ or verify/.

Each SceneTag is a TagSpec (its target included) placed on the canvas: its
target's frame sits at (x_mm, y_mm), turned by rotation_deg about +z. The
canvas is mm, x right, y up (the 2D view flips y on screen).

`locked`: a printed tag. An edit that would change its ink (the board, its
frame, the corner mark, the label's text and strokes) is refused with an
Issue; moving it on the canvas, renaming it or hiding it is allowed.
"""
from __future__ import annotations

import copy
import math
import re
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..plan import plan_tag
from ..plan.record import ink_digest
from ..plan.spec import Issue, TagSpec

SCHEMA = "arucostudio.scene/1"
NAME_BAD = re.compile(r"[+|]")          # the numbering's path / key separators


def pose_of(x_mm: float, y_mm: float, rotation_deg: float) -> List[float]:
    """The target frame in the scene: a row-major 4x4 (mm)."""
    a = math.radians(rotation_deg)
    c, s = math.cos(a), math.sin(a)
    if abs(rotation_deg % 90.0) < 1e-12:
        c, s = round(c), round(s)
    return [c, -s, 0.0, float(x_mm), s, c, 0.0, float(y_mm), 0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0]


def mat_mul(a, b):
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4)]


@dataclass
class SceneTag:
    name: str
    spec: TagSpec
    x_mm: float = 0.0
    y_mm: float = 0.0
    rotation_deg: float = 0.0
    locked: bool = False
    hidden: bool = False
    uid: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def pose(self) -> List[float]:
        return pose_of(self.x_mm, self.y_mm, self.rotation_deg)

    def to_dict(self) -> dict:
        return {"name": self.name, "uid": self.uid, "spec": self.spec.to_dict(),
                "x_mm": float(self.x_mm), "y_mm": float(self.y_mm),
                "rotation_deg": float(self.rotation_deg), "pose": self.pose,
                "locked": bool(self.locked), "hidden": bool(self.hidden), "plan": None}

    @classmethod
    def from_dict(cls, d: dict) -> "SceneTag":
        if not isinstance(d, dict) or not isinstance(d.get("name"), str):
            raise ValueError("a scene tag needs a name")
        for k in ("x_mm", "y_mm", "rotation_deg"):
            v = d.get(k, 0.0)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(f"tag {d['name']!r}: {k} must be a number")
        return cls(name=d["name"], spec=TagSpec.from_dict(d["spec"]),
                   x_mm=float(d.get("x_mm", 0.0)), y_mm=float(d.get("y_mm", 0.0)),
                   rotation_deg=float(d.get("rotation_deg", 0.0)),
                   locked=bool(d.get("locked", False)), hidden=bool(d.get("hidden", False)),
                   uid=str(d.get("uid") or uuid.uuid4().hex[:12]))


@dataclass
class Scene:
    name: str = "scene"
    tags: List[SceneTag] = field(default_factory=list)
    ledger: Optional[dict] = None
    overrides: Dict[str, int] = field(default_factory=dict)
    presets_used: List[str] = field(default_factory=list)
    units: str = "mm"
    schema: str = SCHEMA

    # ------------------------------------------------------------ reading

    def names(self) -> List[str]:
        return [t.name for t in self.tags]

    def get(self, name: str) -> SceneTag:
        for t in self.tags:
            if t.name == name:
                return t
        raise KeyError(name)

    def plans(self) -> Dict[str, object]:
        """Every tag's TagPlan (a cache is never stored)."""
        return {t.name: plan_tag(t.spec) for t in self.tags}

    def to_dict(self) -> dict:
        return {"schema": self.schema, "units": self.units, "name": self.name,
                "tags": [t.to_dict() for t in self.tags],
                "ledger": copy.deepcopy(self.ledger), "overrides": dict(self.overrides),
                "presets_used": list(self.presets_used)}

    # ------------------------------------------------------------ editing

    def unique_name(self, base: str) -> str:
        base = NAME_BAD.sub("_", base or "tag").strip() or "tag"
        taken = set(self.names())
        if base not in taken:
            return base
        m = re.match(r"^(.*?)(\d+)$", base)
        stem, k = (m.group(1), int(m.group(2))) if m else (base, 1)
        while f"{stem}{k}" in taken:
            k += 1
        return f"{stem}{k}"

    def add(self, spec: TagSpec, x_mm: float = 0.0, y_mm: float = 0.0, rotation_deg: float = 0.0,
            name: Optional[str] = None, locked: bool = False) -> SceneTag:
        layout = (spec.settings or {}).get("layout", "single")
        nm = self.unique_name(name or {"grid": "board", "charuco": "charuco"}.get(layout, "tag") + "1")
        spec = copy.deepcopy(spec)
        if not spec.key:
            spec.key = nm
        t = SceneTag(name=nm, spec=spec, x_mm=x_mm, y_mm=y_mm, rotation_deg=rotation_deg,
                     locked=locked)
        self.tags.append(t)
        return t

    def move(self, name: str, x_mm: float = None, y_mm: float = None,
             rotation_deg: float = None) -> SceneTag:
        t = self.get(name)
        if x_mm is not None:
            t.x_mm = float(x_mm)
        if y_mm is not None:
            t.y_mm = float(y_mm)
        if rotation_deg is not None:
            t.rotation_deg = float(rotation_deg)
        return t

    def rename(self, old: str, new: str) -> SceneTag:
        t = self.get(old)
        if NAME_BAD.search(new or "") or not new:
            raise ValueError(f"a tag name cannot be empty or hold + or |: {new!r}")
        if new != old and new in self.names():
            raise ValueError(f"there is a tag {new!r} already")
        t.name = new
        if old in self.overrides:
            self.overrides[new] = self.overrides.pop(old)
        return t

    def delete(self, name: str) -> None:
        t = self.get(name)
        self.tags.remove(t)
        self.overrides.pop(name, None)

    def duplicate(self, name: str, dx_mm: float = 10.0, dy_mm: float = 0.0,
                  new_name: Optional[str] = None) -> SceneTag:
        """A copy (a new tag: its own uid; renumbering gives it its own ids)."""
        t = self.get(name)
        spec = copy.deepcopy(t.spec)
        nm = self.unique_name(new_name or t.name)
        spec.key = nm if t.spec.key == t.name else spec.key
        c = SceneTag(name=nm, spec=spec, x_mm=t.x_mm + dx_mm, y_mm=t.y_mm + dy_mm,
                     rotation_deg=t.rotation_deg)
        self.tags.append(c)
        return c

    def edit(self, name: str, settings: Optional[dict] = None, numbers: Optional[dict] = None,
             target: Optional[dict] = None, tag_name: Optional[str] = None,
             key: Optional[str] = None) -> List[Issue]:
        """Change a tag's request (merged in). A locked tag refuses any change
        of its ink; -> [Issue] ([] when done)."""
        t = self.get(name)
        new = copy.deepcopy(t.spec)
        if settings:
            s = dict(new.settings)
            for k, v in settings.items():
                if isinstance(v, dict) and isinstance(s.get(k), dict) and k in ("label",):
                    s[k] = dict(s[k], **v)
                elif v is None:
                    s.pop(k, None)
                else:
                    s[k] = copy.deepcopy(v)
            new.settings = s
        if numbers:
            new.numbers = dict(new.numbers, **numbers)
        if target is not None:
            from ..plan.target import Target
            new.target = Target.from_dict(target)
        if key is not None:
            new.key = key
        if t.locked:
            a, b = plan_tag(t.spec), plan_tag(new)
            if not b.ok or ink_digest(a.data) != ink_digest(b.data):
                fld = _changed_field(settings, numbers, target, key)
                return [Issue(fld, "error", "locked: a printed tag -- its ink cannot change "
                              "(unlock it first)")]
        t.spec = new
        if tag_name is not None and tag_name != name:
            self.rename(name, tag_name)
        return []


def _changed_field(settings, numbers, target, key) -> str:
    if settings:
        k = sorted(settings)[0]
        v = settings[k]
        if isinstance(v, dict) and v:
            return f"settings.{k}.{sorted(v)[0]}"
        return f"settings.{k}"
    if numbers:
        return f"numbers.{sorted(numbers)[0]}"
    if target is not None:
        return "target"
    if key is not None:
        return "key"
    return "tag"
