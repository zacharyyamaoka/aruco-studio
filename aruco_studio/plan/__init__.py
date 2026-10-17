"""The adapter contract: TagSpec in, TagPlan out (ARCHITECTURE 3.2).

Standard library only, and never imports adapters/, server/ or verify/:
build123d, viser and Fusion reuse it as it is.
"""
from .spec import Issue, TagSpec, check  # noqa: F401
from .target import SpecTypeError, Target  # noqa: F401
from .plan import TagPlan, plan_sticker, plan_tag, validate  # noqa: F401
