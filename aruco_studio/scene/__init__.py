"""Many tags on one canvas: the Scene, its numbering and its file.

Standard library only; reuses plan/ and core/, never adapters/, server/ or
verify/ (build123d and viser adapters can use it as it is).
"""
from .model import Scene, SceneTag, pose_of  # noqa: F401
from .file import (DesignParseError, SceneFileError, dumps, dumps_design, loads,  # noqa: F401
                   loads_design)
from . import design  # noqa: F401
from .ids import check_first_id, number_one, renumber, set_first_id  # noqa: F401
