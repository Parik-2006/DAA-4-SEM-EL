"""Models package for the attendance system.

The package now uses lazy imports so importing helper modules does not require
loading the full ML stack immediately.
"""

from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "YOLOv8Detector": ("models.yolov8_detector", "YOLOv8Detector"),
    "FaceNetExtractor": ("models.facenet_extractor", "FaceNetExtractor"),
    "ModelManager": ("models.model_manager", "ModelManager"),
    "TimetablePeriod": ("models.timetable", "TimetablePeriod"),
    "CourseAssignment": ("models.timetable", "CourseAssignment"),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = list(_EXPORTS)
