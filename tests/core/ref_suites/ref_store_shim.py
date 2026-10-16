"""REF's FILE API for presets and PrusaSlicer profiles, over the pure core.

REF's ArucoMarkers/aruco_presets.py and aruco_prusa.py read and wrote files
themselves (`path=`, `prusa_dir=`). The Studio's core never touches a file
(core.presets takes a store with `.text`, core.prusa takes PrusaSources), so
the ported suite test_aruco_presets runs on this shim, which puts REF's
file behaviour back on top: the presets file at a path (a missing file, a
broken file moved aside as aruco_presets.broken-<time>.json, the text
written whole), and PrusaSlicer's folder read the way REF read it.

server/store.py (M2b) is the real home of this; until then the suite proves
the core and the file behaviour together. Test code only.
"""
from __future__ import annotations

import glob
import os
import sys
import time

from aruco_studio.core import presets as _P
from aruco_studio.core import prusa as _R


# ------------------------------------------------------------ PrusaSlicer

def config_dir():
    """REF aruco_prusa.config_dir: the env var, else the OS's folder."""
    env = os.environ.get(_R.CONFIG_ENV)
    if env:
        return env
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
        return os.path.join(base, "PrusaSlicer")
    return os.path.join(os.path.expanduser("~"), ".config", "PrusaSlicer")


def _read(p):
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def sources(base=None):
    base = base or config_dir()
    user = {os.path.splitext(os.path.basename(p))[0]: _read(p)
            for p in sorted(glob.glob(os.path.join(base, "print", "*.ini")))}
    bundles = [_read(p) for p in sorted(glob.glob(os.path.join(base, "vendor", "*.ini")))]
    return _R.sources_from_texts(user, bundles)


class R:
    """aruco_prusa's API with `base` folders."""
    CONFIG_ENV = _R.CONFIG_ENV
    AUTO_WIDTH = _R.AUTO_WIDTH
    config_dir = staticmethod(config_dir)
    width_of = staticmethod(_R.width_of)
    nozzle_of = staticmethod(_R.nozzle_of)
    length = staticmethod(_R.length)
    describe = staticmethod(_R.describe)

    @staticmethod
    def user_prints(base=None):
        return _R.user_prints(sources(base))

    @staticmethod
    def resolve(name, base=None):
        return _R.resolve(name, sources(base))

    @staticmethod
    def profile(name, base=None):
        return _R.profile(name, sources(base))

    @staticmethod
    def aruco_profiles(base=None):
        return _R.aruco_profiles(sources(base))


# --------------------------------------------------------------- presets

class FileStore:
    """core.presets' store on a real file: `text` reads / writes it, a save
    over a broken file first moves that file aside (REF save())."""

    def __init__(self, path):
        self.path = path

    @property
    def text(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return None

    @text.setter
    def text(self, value):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = "%s.%d.tmp" % (self.path, os.getpid())
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(value)
        os.replace(tmp, self.path)

    @property
    def aside(self):
        store = self

        class _Aside(list):
            def append(self, text):
                stamp = time.strftime("%Y%m%d-%H%M%S")
                os.replace(store.path, os.path.join(os.path.dirname(store.path) or ".",
                                                    f"aruco_presets.broken-{stamp}.json"))
        return _Aside()


def presets_path():
    return os.path.join(os.path.expanduser("~"), "CADExporter", _P.FILE_NAME)


def _store(path):
    return FileStore(path or presets_path())


def _prusa(prusa_dir):
    return sources(prusa_dir)


def load(path=None):
    return _P.load(_store(path))


def save(data, path=None):
    _P.save(data, _store(path))
    return path or presets_path()


def builtins(prusa_dir=None):
    return _P.builtins(_prusa(prusa_dir))


def catalog(path=None, prusa_dir=None):
    return _P.catalog(_store(path), _prusa(prusa_dir))


def save_as(name, preset, path=None, prusa_dir=None):
    return _P.save_as(name, preset, _store(path), _prusa(prusa_dir))


def update(name, preset, path=None, prusa_dir=None):
    return _P.update(name, preset, _store(path), _prusa(prusa_dir))


def delete(name, path=None, prusa_dir=None):
    return _P.delete(name, _store(path), _prusa(prusa_dir))


def set_last(name, path=None):
    return _P.set_last(name, _store(path))


def import_profile(profile_name, path=None, prusa_dir=None):
    return _P.import_profile(profile_name, _store(path), _prusa(prusa_dir))


class _PresetsAPI:
    """aruco_presets' API with `path` / `prusa_dir`; everything else is core.presets."""
    presets_path = staticmethod(presets_path)
    load = staticmethod(load)
    save = staticmethod(save)
    builtins = staticmethod(builtins)
    catalog = staticmethod(catalog)
    save_as = staticmethod(save_as)
    update = staticmethod(update)
    delete = staticmethod(delete)
    set_last = staticmethod(set_last)
    import_profile = staticmethod(import_profile)

    def __getattr__(self, name):
        return getattr(_P, name)


P = _PresetsAPI()
