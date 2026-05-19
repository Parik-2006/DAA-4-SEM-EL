"""
Legacy Script: setup_students.py

Purpose: Register students in Firebase Auth with email/password credentials.

This script is specialized for Firebase Auth enrollment with hardcoded credentials.
For general student seeding (Firestore records, test data), use the unified:

    python scripts/seed_via_backend.py [--section SECTION] [--teacher TEACHER] [--students N]

Status: Deprecated. Use unified seeding path instead.
"""

raise NotImplementedError(
    "This script has been deprecated in favor of the unified seeding path.\n"
    "Use: python scripts/seed_via_backend.py --section SECTION --students N\n"
    "For secure auth testing, use token_utils.create_student_token() from utils/token_utils.py"
)
