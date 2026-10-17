"""The oracle: render a TagPlan, let OpenCV read it, check its pose.

numpy and opencv-contrib-python-headless are imported here only; core/,
plan/ and scene/ never import this package.
"""
from .report import verify_plan, verify_scene  # noqa: F401
