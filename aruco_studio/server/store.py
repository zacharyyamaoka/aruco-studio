"""Every file the Studio reads or writes. The ONLY module that does.

| What | Where |
|---|---|
| the Studio's home | `ARUCO_STUDIO_HOME`, else `ROOT/.studio_data/` (git-ignored) |
| user print presets | `<home>/aruco_presets.json` (REF's `bam_aruco_presets/1` shape: a REF file can be copied over); a broken file is moved aside on the next save, never overwritten |
| remembered options | `<home>/remembered.json` (REF aruco_settings' shape) |
| exports | `<home>/exports/<scene>/` |
| scenes | `ARUCO_STUDIO_SCENES`, else `ROOT/scenes/` (`<name>.arucostudio.json`) |
| PrusaSlicer's profiles | `BAM_ARUCO_PRUSASLICER_DIR`, else PrusaSlicer's own config folder: READ ONLY |

Never `%USERPROFILE%\\CADExporter` (Zach's live add-in's files): a path
under it is refused even when an environment variable points there.
Writes are atomic (a temp file beside it, then os.replace).
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import List, Optional

from ..core import presets as _P
from ..core import prusa as _PR

ROOT = Path(__file__).resolve().parents[2]
SCENE_EXT = ".arucostudio.json"


class StoreError(ValueError):
    pass


def _forbidden(p: Path) -> bool:
    """Is `p` under %USERPROFILE%\\CADExporter (the live add-in's files)?"""
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    real = Path(os.path.expanduser("~"))
    for base in {Path(home), real}:
        try:
            Path(p).resolve().relative_to((base / "CADExporter").resolve())
            return True
        except (ValueError, OSError):
            continue
    return False


def _checked(p: Path) -> Path:
    p = Path(p)
    if _forbidden(p):
        raise StoreError(f"{p}: the Studio never writes under %USERPROFILE%\\CADExporter")
    return p


def home() -> Path:
    return _checked(Path(os.environ.get("ARUCO_STUDIO_HOME") or (ROOT / ".studio_data")))


def scenes_dir() -> Path:
    return _checked(Path(os.environ.get("ARUCO_STUDIO_SCENES") or (ROOT / "scenes")))


def exports_dir(scene: str) -> Path:
    return _checked(home() / "exports" / safe_name(scene or "scene"))


def safe_name(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9 ._-]+", "_", (name or "").strip()).strip(" .")
    return s[:80] or "untitled"


def write_atomic(path: Path, data, binary: bool = False) -> Path:
    path = _checked(Path(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        if binary:
            tmp.write_bytes(data)
        else:
            tmp.write_text(data, encoding="utf-8", newline="\n")
        for attempt in range(20):                  # Windows: a reader may hold it a moment
            try:
                os.replace(tmp, path)
                return path
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.05)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return path


# ------------------------------------------------------------- presets

class FileStore:
    """core.presets' store (`.text`, `.aside`) on a file: reading sets
    .text, `flush()` writes it (atomic) and moves a broken file aside."""

    def __init__(self, path: Path):
        self.path = _checked(Path(path))
        self.text: Optional[str] = (self.path.read_text(encoding="utf-8")
                                    if self.path.exists() else None)
        self.aside: List[str] = []

    def flush(self):
        for k, old in enumerate(self.aside):
            stamp = time.strftime("%Y%m%d-%H%M%S")
            write_atomic(self.path.with_name(f"aruco_presets.broken-{stamp}-{k}.json"), old)
        self.aside = []
        if self.text is not None:
            write_atomic(self.path, self.text)


def presets_path() -> Path:
    return home() / _P.FILE_NAME


def presets_store() -> FileStore:
    return FileStore(presets_path())


def prusa_dir() -> Optional[Path]:
    d = os.environ.get("BAM_ARUCO_PRUSASLICER_DIR")
    if d:
        return Path(d)
    appdata = os.environ.get("APPDATA")
    if appdata and (Path(appdata) / "PrusaSlicer").is_dir():
        return Path(appdata) / "PrusaSlicer"
    return None


def prusa_sources():
    """core.prusa.PrusaSources from PrusaSlicer's config folder (read only):
    its print/*.ini and vendor/*.ini texts. None when there is no folder."""
    d = prusa_dir()
    if d is None or not d.is_dir():
        return None
    users = {}
    for f in sorted((d / "print").glob("*.ini")) if (d / "print").is_dir() else []:
        try:
            users[f.stem] = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    bundles = []
    for f in sorted((d / "vendor").glob("*.ini")) if (d / "vendor").is_dir() else []:
        try:
            bundles.append(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return _PR.sources_from_texts(users, bundles)


# ------------------------------------------------------------- scenes

def scene_path(name: str) -> Path:
    n = name[:-len(SCENE_EXT)] if name.endswith(SCENE_EXT) else name
    p = scenes_dir() / (safe_name(n) + SCENE_EXT)
    return _checked(p)


def list_scenes() -> List[dict]:
    d = scenes_dir()
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob("*" + SCENE_EXT)):
        st = f.stat()
        out.append({"name": f.name[:-len(SCENE_EXT)], "file": f.name, "bytes": st.st_size,
                    "modified": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime))})
    return out


# ------------------------------------------------------------- remembered

def remembered_path() -> Path:
    return home() / "remembered.json"
