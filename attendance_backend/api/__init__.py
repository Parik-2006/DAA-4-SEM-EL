"""
API package for the attendance system.

Provides FastAPI route modules for different endpoints.
"""

# Import routers to make them available
from . import health

__all__ = ["health"]
