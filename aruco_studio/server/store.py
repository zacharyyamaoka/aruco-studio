"""Every file the Studio reads or writes. The ONLY module that does.

| What | Where |
|---|---|
| the Studio's home | `ARUCO_STUDIO_HOME`, else `ROOT/.studio_data/` (git-ignored) |
| user print presets | `<home>/aruco_presets.json` (REF's `bam_aruco_presets/1` shape: a REF file can be copied over); a broken file is moved aside on the next save, never overwritten |
| remembered options | `<home>/remembered.json` (REF aruco_settings' shape) |
| exports | `<home>/exports/<scene>/` |
| scenes | `ARUCO_STUDIO_SCENES`, else `ROOT/scenes/` (`<name>.arucostudio.json`) |
| PrusaSlicer's profiles | `BAM_ARUCO_PRUSASLICER_DIR`, else PrusaSlicer's own config folder: READ ONLY |
| an open design file (M8a) | anywhere Zach says (`design_path`): never under the two folders below |

Never `%USERPROFILE%\\CADExporter` (Zach's live add-in's files): a path
under it is refused even when an environment variable points there.
Writes are atomic (a temp file beside it, then os.replace).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

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


def _prusa_owned(p: Path) -> bool:
    """Is `p` under PrusaSlicer's own config folder (APPDATA/PrusaSlicer)?"""
    appdata = os.environ.get("APPDATA")
    bases = [Path(appdata) / "PrusaSlicer"] if appdata else []
    bases.append(Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "PrusaSlicer")
    if os.environ.get("BAM_ARUCO_PRUSASLICER_DIR"):     # M8c: the folder read, wherever it is
        bases.append(Path(os.environ["BAM_ARUCO_PRUSASLICER_DIR"]))
    for base in bases:
        try:
            Path(p).resolve().relative_to(base.resolve())
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


_WRITTEN: Dict[str, str] = {}
_WLOCK = threading.Lock()


def text_hash(data) -> str:
    """sha256 of a text (utf-8) or bytes: the watcher's rule."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def written_hash(path: Path) -> Optional[str]:
    """The sha256 of the last bytes write_atomic wrote at `path` (None: none)."""
    with _WLOCK:
        return _WRITTEN.get(str(Path(path).resolve()))


def write_atomic(path: Path, data, binary: bool = False) -> Path:
    path = _checked(Path(path))
    if _prusa_owned(path):
        raise StoreError(f"{path}: the Studio never writes under PrusaSlicer's folder")
    with _WLOCK:
        _WRITTEN[str(path.resolve())] = text_hash(data)
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


def prusa_sources(files: Optional[Dict[str, str]] = None):
    """core.prusa.PrusaSources from PrusaSlicer's config folder (read only):
    its print/*.ini and vendor/*.ini texts; M8c: also physical_printer/*.ini
    (through the allow-list), printer/*.ini and PrusaSlicer.ini (its
    [presets] and [vendor:...] only), every private key dropped as the file
    is read. `files`: {relpath: text} already read (prusa_read). None when
    there is no folder."""
    if files is None:
        d = prusa_dir()
        if d is None or not d.is_dir():
            return None
        # a file that does not parse (half written) is left out
        files = {rel: t for rel, (t, ok) in prusa_read(d).items() if ok}
    groups: Dict[str, Dict[str, str]] = {"print": {}, "vendor": {}, "printer": {},
                                         "physical_printer": {}}
    ini = None
    for rel in sorted(files):
        if rel == PRUSA_INI:
            ini = files[rel]
            continue
        sub, _sep, name = rel.partition("/")
        if sub in groups and name.endswith(".ini"):
            groups[sub][name[:-4]] = files[rel]
    return _PR.sources_from_texts(groups["print"], [groups["vendor"][k] for k in
                                                    sorted(groups["vendor"])],
                                  printer_texts=groups["printer"],
                                  physical_texts=groups["physical_printer"], ini_text=ini)


# M8c: what is read of PrusaSlicer's folder, and how (never written)
PRUSA_INI = "PrusaSlicer.ini"
PRUSA_KINDS = {"physical_printer": "physical", "printer": "printer", "print": "print",
               "vendor": "vendor"}


def prusa_paths(d: Optional[Path] = None) -> List[Path]:
    """The files watched and read: PrusaSlicer.ini, physical_printer/,
    printer/, print/ and vendor/ *.ini (about twenty on Zach's box)."""
    d = d if d is not None else prusa_dir()
    if d is None or not Path(d).is_dir():
        return []
    d = Path(d)
    out = [d / PRUSA_INI] if (d / PRUSA_INI).is_file() else []
    for sub in PRUSA_KINDS:
        if (d / sub).is_dir():
            out += sorted((d / sub).glob("*.ini"))
    return out


def prusa_rel(d: Path, path: Path) -> str:
    return Path(path).resolve().relative_to(Path(d).resolve()).as_posix()


def prusa_kind(rel: str) -> str:
    if rel == PRUSA_INI:
        return "ini"
    return PRUSA_KINDS.get(rel.partition("/")[0], "")


def read_prusa_file(path: Path, kind: str):
    """One file of PrusaSlicer's folder, read line by line and filtered as
    it is read -> (the kept text, complete?). A physical printer keeps only
    core.prusa.PHYSICAL_KEYS; every other file drops each private key
    (core.prusa.private_key); PrusaSlicer.ini keeps [presets] and
    [vendor:...]. `complete`: every line a key = value, a comment or a
    section head, a newline at the end, and the kind's own key (a
    half-written file is not). (None, False) when it cannot be read."""
    if kind in ("print", "printer", "vendor"):    # the big files: one pass, by regex
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                raw = fh.read()
        except OSError:
            return None, False
        text = _PR.drop_private(raw)
        return text, _PR.ini_complete(text, kind)
    keep: List[str] = []
    ok = True
    last = ""
    section = None
    try:
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
            for line in fh:
                last = line
                s = line.strip()
                if not s or s[0] in "#;":
                    continue
                if s[0] == "[" and s.endswith("]"):
                    section = s[1:-1]
                    if kind != "ini" or section == "presets" or section.startswith("vendor:"):
                        keep.append(s + "\n")
                    continue
                if "=" not in s:
                    ok = False
                    continue
                k = s.split("=", 1)[0].strip()
                if kind == "physical":
                    if k in _PR.PHYSICAL_KEYS:
                        keep.append(s + "\n")
                elif _PR.private_key(k):
                    continue
                elif kind == "ini":
                    if section == "presets" or (section or "").startswith("vendor:"):
                        keep.append(s + "\n")
                else:
                    keep.append(s + "\n")
    except OSError:
        return None, False
    text = "".join(keep)
    ok = ok and (kind == "vendor" or last.endswith(("\n", "\r")))
    if ok:
        ok = _PR.ini_complete(text, kind)
    return text, ok


def prusa_read(d: Optional[Path] = None) -> Dict[str, tuple]:
    """{relpath: (kept text, complete?)} of every watched file."""
    d = d if d is not None else prusa_dir()
    out = {}
    for p in prusa_paths(d):
        rel = prusa_rel(d, p)
        text, ok = read_prusa_file(p, prusa_kind(rel))
        if text is not None:
            out[rel] = (text, ok)
    return out


def prusa_bundle_text(name: str = "PrusaResearch") -> Optional[str]:
    """A vendor bundle's kept text (private keys dropped): for a project's
    filament chain on Send."""
    d = prusa_dir()
    if d is None:
        return None
    p = Path(d) / "vendor" / f"{name}.ini"
    if not p.is_file():
        return None
    text, _ok = read_prusa_file(p, "vendor")
    return text


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


# ------------------------------------------------------------- design files

def design_path(path) -> Path:
    """A design file anywhere Zach says, made absolute; refused under
    USERPROFILE/CADExporter and PrusaSlicer's folder."""
    p = Path(os.path.expanduser(str(path)))
    if not p.is_absolute():
        p = Path.cwd() / p
    p = _checked(p)
    if _prusa_owned(p):
        raise StoreError(f"{p}: the Studio never writes under PrusaSlicer's folder")
    return p


def read_design(path: Path):
    """A design file -> (its text (utf-8, a BOM dropped), the sha256 of its bytes)."""
    with open(_checked(Path(path)), "rb") as fh:
        b = fh.read()
    return b.decode("utf-8-sig", errors="replace"), text_hash(b)


# ------------------------------------------------------------- the Open dialog (audit 2026-10-17)

EXAMPLES = ROOT / "examples"
MAX_RECENT_DESIGNS = 12


def recent_path() -> Path:
    return home() / "recent_designs.json"


def recent_designs() -> List[dict]:
    """The design files opened lately, newest first: {path, name, exists, modified}."""
    try:
        data = json.loads(recent_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    out = []
    for x in data.get("recent") or []:
        if not isinstance(x, str) or not x:
            continue
        f = Path(x)
        ok = f.is_file()
        out.append({"path": x, "name": f.name[:-len(SCENE_EXT)] if f.name.endswith(SCENE_EXT)
                    else f.name, "exists": ok,
                    "modified": time.strftime("%Y-%m-%dT%H:%M:%S",
                                              time.localtime(f.stat().st_mtime)) if ok else None})
    return out


def remember_design(path: Path) -> None:
    """Put `path` first in the recent list (best effort: never raises)."""
    try:
        now = [x["path"] for x in recent_designs()]
        p = str(Path(path).resolve())
        rec = ([p] + [x for x in now if x != p])[:MAX_RECENT_DESIGNS]
        write_atomic(recent_path(), json.dumps({"schema": "arucostudio.recent/1", "recent": rec},
                                               indent=1) + "\n")
    except (OSError, StoreError, ValueError):
        pass


def examples() -> List[dict]:
    """ROOT/examples' design files: {name, file, title}."""
    out = []
    for f in sorted(EXAMPLES.glob("*" + SCENE_EXT)):
        title = ""
        try:
            title = str(json.loads(f.read_text(encoding="utf-8")).get("name") or "")
        except (OSError, ValueError):
            pass
        out.append({"name": f.name[:-len(SCENE_EXT)], "file": f.name, "title": title})
    return out


def copy_example(name: str) -> Path:
    """An example copied into the scenes folder (a fresh name when taken):
    the repo's examples are never opened, so never written."""
    n = name[:-len(SCENE_EXT)] if name.endswith(SCENE_EXT) else name
    src = EXAMPLES / (n + SCENE_EXT)
    if safe_name(n) != n or not src.is_file():
        raise FileNotFoundError(name)
    text = src.read_text(encoding="utf-8")
    dst = scene_path(n)
    k = 2
    while dst.exists():
        dst = scene_path(f"{n}-{k}")
        k += 1
    write_atomic(dst, text)
    return dst


def browse(folder=None) -> dict:
    """A folder's design files and subfolders (not recursive): {dir, parent,
    folders: [{name, path}], files: [{name, path, bytes, modified}]}. The
    scenes folder when `folder` is empty."""
    if folder:
        d = design_path(folder)
    else:
        d = scenes_dir()
        d.mkdir(parents=True, exist_ok=True)          # a fresh box: the folder New writes to
    if not d.is_dir():
        raise FileNotFoundError(str(d))
    folders, files = [], []
    try:
        entries = sorted(d.iterdir(), key=lambda x: x.name.lower())
    except OSError:
        entries = []
    for f in entries:
        try:
            if f.is_dir():
                if not f.name.startswith(".") and not _forbidden(f):
                    folders.append({"name": f.name, "path": str(f)})
            elif f.name.endswith(SCENE_EXT):
                st = f.stat()
                files.append({"name": f.name[:-len(SCENE_EXT)], "path": str(f), "bytes": st.st_size,
                              "modified": time.strftime("%Y-%m-%dT%H:%M:%S",
                                                        time.localtime(st.st_mtime))})
        except OSError:
            continue
    parent = str(d.parent) if d.parent != d else None
    return {"dir": str(d), "parent": parent, "folders": folders, "files": files}


# ------------------------------------------------------------- remembered

def remembered_path() -> Path:
    return home() / "remembered.json"
