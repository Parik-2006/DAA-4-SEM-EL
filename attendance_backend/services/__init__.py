"""Services package for the attendance system.

The package uses lazy imports so lightweight utility tests do not require the
full optional ML stack at import time.
"""

from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    # Legacy services
    "FaceDetectionService": ("services.face_detection_service", "FaceDetectionService"),
    "FaceRecognitionService": ("services.face_recognition_service", "FaceRecognitionService"),
    "TrackingService": ("services.tracking_service", "TrackingService"),
    "AttendanceService": ("services.attendance_service", "AttendanceLockService"),
    # New core pipelines
    "FaceDetectionPipeline": ("services.detection", "FaceDetectionPipeline"),
    "FaceRecognitionPipeline": ("services.recognition", "FaceRecognitionPipeline"),
    "FaceDatabase": ("services.recognition", "FaceDatabase"),
    "AttendancePipeline": ("services.attendance_pipeline", "AttendancePipeline"),
    "DetectedFace": ("services.attendance_pipeline", "DetectedFace"),
    # Demo functions
    "demo_detection": ("services.detection", "demo_detection"),
    "demo_recognition": ("services.recognition", "demo_recognition"),
    "demo_attendance_pipeline": ("services.attendance_pipeline", "demo_attendance_pipeline"),
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
