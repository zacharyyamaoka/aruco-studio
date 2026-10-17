"""REF's module names, for code copied verbatim from the add-in.

The add-in reached the core through `aruco_core.module("aruco_label")` and its
sibling modules by their own names (`aruco_feature.A()`, `aruco_presets.line_mm`,
`aruco_tags._rot`). Copied functions keep those spellings; this module maps
them onto aruco_studio.core, so the bodies stay byte for byte REF's.
"""
from __future__ import annotations

import importlib

# REF bam_cad_core / add-in module name -> aruco_studio.core module
NAMES = {"aruco_dict": "dictionary", "aruco_board": "board", "aruco_origin": "origin",
         "aruco_slabs": "slabs", "aruco_chamfer": "chamfer", "aruco_autosize": "autosize",
         "aruco_label": "label", "aruco_trim": "trim", "aruco_numbering": "numbering",
         "markers": "markers", "fiducials": "dictionary", "print_sheet": "sheet",
         "print_beds": "beds",
         # add-in modules whose pure halves live in the core
         "aruco_feature": "settings", "aruco_presets": "presets", "aruco_prusa": "prusa",
         "aruco_restructure": "restructure", "aruco_tags": "geometry",
         "aruco_autosize_gallery": "faces", "aruco_marker_table": "marker_table"}


def module(name: str):
    """REF `aruco_core.module(name)`: the core module of that REF name."""
    # package-relative (N-1): the core also runs vendored in the Fusion add-in
    # under a private alias, where "aruco_studio" is not its name
    return importlib.import_module("." + NAMES.get(name, name), __package__)


class _AliasCore:
    """`aruco_core` as REF's add-in used it."""
    module = staticmethod(module)


aruco_core = _AliasCore()
