"""
API package for the attendance system.

Provides FastAPI route modules for different endpoints.
"""

# Import routers to make them available
from . import health
from . import attendance
from . import user
from . import auth         # NEW (Module 1 - Auth & RBAC)
from . import admin
from . import student
from . import admin_students
from . import courses
from . import qr_attendance

__all__ = ["health", "attendance", "user", "auth", "admin", "student", "admin_students", "courses", "qr_attendance"]
