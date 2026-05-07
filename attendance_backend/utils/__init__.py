"""
Utilities package for the attendance system.

Provides helper functions for preprocessing, embedding search,
image handling, and input validation.
"""

from __future__ import annotations
from importlib import import_module

_EXPORTS = {
    "ImagePreprocessor": ("utils.preprocessing", "ImagePreprocessor"),
    "EmbeddingSearch": ("utils.embedding_search", "EmbeddingSearch"),
    "ImageUtils": ("utils.image_utils", "ImageUtils"),
    "Validators": ("utils.validators", "Validators"),
    "get_period_runtime_status": ("utils.time_validator", "get_period_runtime_status"),
    "get_marking_window_info": ("utils.time_validator", "get_marking_window_info"),
    "is_marking_allowed": ("utils.time_validator", "is_marking_allowed"),
}

def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value

__all__ = [
    "ImagePreprocessor",
    "EmbeddingSearch",
    "ImageUtils",
    "Validators",
    "get_period_runtime_status",
    "get_marking_window_info",
    "is_marking_allowed",
]
