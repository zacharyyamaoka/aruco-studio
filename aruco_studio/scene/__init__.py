"""Many tags on one canvas: the Scene, its numbering and its file.

Standard library only; reuses plan/ and core/, never adapters/, server/ or
verify/ (build123d and viser adapters can use it as it is).
"""
from .model import Scene, SceneTag, pose_of  # noqa: F401
from .file import dumps, loads, SceneFileError  # noqa: F401
from .ids import renumber  # noqa: F401
