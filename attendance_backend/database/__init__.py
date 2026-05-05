"""
Database package for the attendance system.

Provides Firebase integration and data repositories for students,
attendance records, and face embeddings.
"""

from database.firebase_client import FirebaseClient
from database.student_repository import StudentRepository
from database.attendance_repository import AttendanceRepository
from database.user_repository import UserRepository
from database.timetable_repository import TimetableRepository

__all__ = [
    "FirebaseClient",
    "StudentRepository",
    "AttendanceRepository",
    "UserRepository",
    "TimetableRepository",
]
