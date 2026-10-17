"""The API's request / response shapes (pydantic), so GET /openapi.json
types the web app (openapi-typescript) with the same TagSpec, TagPlan,
Target and Issue as the Python.

Numbers are STRICT: a string where a number goes is a 422 naming its key
path (ARCHITECTURE 5.6). Settings stay a free object here; their types are
checked by plan.spec.TagSpec.from_dict, whose SpecTypeError the app turns
into the same 422.
"""
from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr

Num = StrictFloat               # strict: an int is a number, a string is not
Pt = Tuple[Num, Num]
Loop = List[Pt]


class BodyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    u0: Num
    v0: Num
    u1: Num
    v1: Num
    z0: Num
    z1: Num
    measured: StrictBool = True
    depth: Optional[Num] = None


class TargetIn(BaseModel):
    """The face or sketch area, as numbers (ARCHITECTURE 5.1)."""
    model_config = ConfigDict(extra="allow")
    kind: StrictStr = "face"
    w_mm: Num
    h_mm: Num
    loops_mm: List[Loop] = Field(default_factory=list)
    has_body: StrictBool = True
    z_sign: StrictInt = 1
    x_ref: Optional[Pt] = None
    body_mm: Optional[BodyIn] = None
    body_loops_mm: Optional[List[Loop]] = None
    face_loops_mm: Optional[List[Loop]] = None
    name: StrictStr = ""


class TagSpecIn(BaseModel):
    """The request (ARCHITECTURE 5.2)."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_: Annotated[Literal["arucostudio.tagspec/1"], Field(alias="schema")] =         "arucostudio.tagspec/1"
    settings: Dict[str, Any] = Field(default_factory=dict)
    numbers: Dict[str, Num] = Field(default_factory=dict)
    target: TargetIn
    name: StrictStr = ""
    key: StrictStr = ""

    def plain(self) -> dict:
        d = self.model_dump(by_alias=True, exclude_none=False)
        t = d["target"]
        for k in ("x_ref", "body_mm", "body_loops_mm", "face_loops_mm"):
            if t.get(k) is None:
                t[k] = None
        if t.get("body_mm") is not None and t["body_mm"].get("depth") is None:
            t["body_mm"].pop("depth", None)
        return d


class IssueOut(BaseModel):
    field: str
    level: Literal["error", "warn", "info"]
    text: str


class PolygonOut(BaseModel):
    outer: List[Tuple[float, float]]
    holes: List[List[Tuple[float, float]]] = Field(default_factory=list)


class LayerOut(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    part: str
    solid: int
    step: Literal["add", "sub"]
    op: Literal["add", "cut", "keep"]
    colour: Literal["white", "black", "none"]
    z: Tuple[float, float]
    polygons: List[PolygonOut]
    circles: Optional[List[Dict[str, Any]]] = None


class MeshOut(BaseModel):
    what: str
    colour: str
    z: Tuple[float, float]
    positions: List[float]
    indices: List[int]


class FramesOut(BaseModel):
    opencv: List[float]
    opencv_target: List[float]
    pattern_in_target: List[float]
    detector_z_mm: float
    surface_mm: float


class GuidesOut(BaseModel):
    model_config = ConfigDict(extra="allow")
    sticker: List[float]
    quiet_ring: List[float]
    clear_hard: List[float]
    clear_preferred: List[float]
    keepouts: List[List[Tuple[float, float]]]
    label_preview: List[List[Tuple[float, float]]]
    tile: Optional[List[float]] = None
    target: List[List[Tuple[float, float]]]
    trim: Optional[Dict[str, Any]] = None


class TagPlanOut(BaseModel):
    """The result (ARCHITECTURE 5.3)."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    schema_: Annotated[str, Field(alias="schema")]
    ok: bool
    errors: List[str]
    marker: Optional[Dict[str, Any]] = None
    layout: Optional[Dict[str, Any]] = None
    placement: Optional[Dict[str, Any]] = None
    parts: List[str]
    layers: List[LayerOut]
    combines: List[Dict[str, Any]]
    frames: Optional[FramesOut] = None
    ids: List[int]
    labels: List[Dict[str, Any]]
    mark: Optional[Dict[str, Any]] = None
    label: Optional[Dict[str, Any]] = None
    trim: Optional[Dict[str, Any]] = None
    pins: List[Dict[str, Any]]
    guides: Optional[GuidesOut] = None
    warnings: List[IssueOut]
    rules: Dict[str, Any]
    writes: Optional[Dict[str, Any]] = None
    record: Optional[Dict[str, Any]] = None
    notes: List[str]
    node_warning: str
    digest: Optional[str] = None
    name: str = ""
    key: str = ""
    body: Optional[Dict[str, Any]] = None
    slabs: Optional[Dict[str, Any]] = None
    # (2026-10-17: a make-rule-2 sticker also has `sticker`, plan.sticker_block: extra, so
    # a rule-1 or 3D plan's JSON stays what it was)
    mesh: Optional[List[MeshOut]] = None


class VerifyIn(BaseModel):
    spec: TagSpecIn
    px_per_mm: Num = 20.0
    pose: StrictBool = True
    image: StrictBool = False          # the raster OpenCV read, as a PNG (base64)


class CandidatesIn(BaseModel):
    layout: Literal["single", "grid", "charuco"] = "single"
    dictionary: StrictStr = "DICT_4X4_50"
    quiet_modules: Num = 1.0
    cells: Optional[Dict[str, Any]] = None
    target: TargetIn
    limit: StrictInt = 8


class SceneTagIn(BaseModel):
    spec: TagSpecIn
    x_mm: Num = 0.0
    y_mm: Num = 0.0
    rotation_deg: Num = 0.0
    name: Optional[StrictStr] = None
    locked: StrictBool = False
    # number the new tag at once: the next free ids of its dictionary family
    # (scene.number_one, the Studio's Add); False keeps the spec's marker_id
    number: StrictBool = False


class SceneTagPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x_mm: Optional[Num] = None
    y_mm: Optional[Num] = None
    rotation_deg: Optional[Num] = None
    settings: Optional[Dict[str, Any]] = None
    numbers: Optional[Dict[str, Num]] = None
    target: Optional[TargetIn] = None
    key: Optional[StrictStr] = None
    new_name: Optional[StrictStr] = None
    locked: Optional[StrictBool] = None
    hidden: Optional[StrictBool] = None


class SceneFileIn(BaseModel):
    name: StrictStr


class SceneNewIn(BaseModel):
    name: StrictStr = "scene"


class PresetIn(BaseModel):
    name: StrictStr
    preset: Dict[str, Any]


class OverrideIn(BaseModel):
    id: Optional[StrictInt] = None


# ------------------------------------------------------------- the Studio (M3)

class NewTagIn(BaseModel):
    """A fresh tag's spec (server/newtag.py): a layout on a target from the
    palette (`target_key`, `thickness_mm`) or a typed `target`, under a
    preset (its name; Default when empty)."""
    model_config = ConfigDict(extra="forbid")
    layout: Literal["single", "grid", "charuco"] = "single"
    target_key: Optional[StrictStr] = None
    thickness_mm: Num = 3.0
    target: Optional[TargetIn] = None
    preset: StrictStr = ""
    marker_id: StrictInt = 0
    name: StrictStr = ""
    key: StrictStr = ""
    made_by: Optional[Literal["print3d", "sticker"]] = None    # M6a: overrides the preset's kind


class PresetApplyIn(BaseModel):
    spec: TagSpecIn
    name: StrictStr = ""
    preset: Optional[Dict[str, Any]] = None


class PresetOfIn(BaseModel):
    spec: TagSpecIn
    name: StrictStr = ""


class LibraryCardIn(BaseModel):
    id: StrictStr


class LibrarySaveIn(BaseModel):
    id: StrictStr
    name: StrictStr = ""
    values: Dict[str, Any] = Field(default_factory=dict)


class RecentIn(BaseModel):
    name: StrictStr


class TargetMakeIn(BaseModel):
    """The target editor's numbers (POST /api/target)."""
    model_config = ConfigDict(extra="forbid")
    shape: Literal["box", "disc", "face"] = "box"
    key: Optional[StrictStr] = None
    w_mm: Num = 40.0
    h_mm: Num = 40.0
    r_mm: Num = 20.0
    holes: List[Tuple[Num, Num, Num]] = Field(default_factory=list)
    thickness_mm: Num = 3.0
