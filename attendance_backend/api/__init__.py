"""
API package for the attendance system.

Provides FastAPI route modules for different endpoints.
"""

# Keep the package import lightweight; individual router modules are imported
# directly by the application entrypoint to avoid import-order issues.
__all__ = [
	"health",
	"attendance",
	"user",
	"auth",
	"admin",
	"student",
	"admin_students",
	"courses",
	"qr_attendance",
	"sections",
]
