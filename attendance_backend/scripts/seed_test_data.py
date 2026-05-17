#!/usr/bin/env python
"""
seed_test_data.py
─────────────────────────────────────────────────────────────────────────────
Populate Firestore with test data for teacher assignments, sections, and 
students. This enables end-to-end testing of role-based access controls.

Usage:
  python scripts/seed_test_data.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

from google.cloud import firestore
from google.oauth2.service_account import Credentials


def init_firestore(credentials_path: str = "config/firebase-credentials.json"):
    """Initialize Firestore client."""
    try:
        creds = Credentials.from_service_account_file(credentials_path)
        db = firestore.Client(credentials=creds)
        logger.info("✓ Firestore connected")
        return db
    except Exception as e:
        logger.error(f"✗ Failed to initialize Firestore: {e}")
        raise


def seed_test_section(db):
    """Create TEST_SECTION if it doesn't exist."""
    try:
        section_ref = db.collection("sections").document("TEST_SECTION")
        section_data = {
            "section_id": "TEST_SECTION",
            "name": "Test Section",
            "code": "TEST-101",
            "department": "Engineering",
            "semester": 4,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        section_ref.set(section_data, merge=True)
        logger.info("✓ TEST_SECTION created/updated")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to create section: {e}")
        return False


def seed_test_teacher(db):
    """Create test teacher 'teacher1' and assign to TEST_SECTION."""
    try:
        teacher_ref = db.collection("users").document("teacher1")
        teacher_data = {
            "user_id": "teacher1",
            "name": "Test Teacher",
            "email": "teacher@test.local",
            "role": "teacher",
            "status": "active",
            "assigned_sections": ["TEST_SECTION"],  # KEY: Assign to test section
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        teacher_ref.set(teacher_data, merge=True)
        logger.info("✓ teacher1 created/updated with TEST_SECTION assignment")
        
        # Also create a faculty assignment record
        faculty_ref = db.collection("faculty_assignments").document("teacher1")
        faculty_data = {
            "user_id": "teacher1",
            "section_id": "TEST_SECTION",
            "role": "instructor",
            "assigned_at": datetime.utcnow().isoformat(),
        }
        faculty_ref.set(faculty_data, merge=True)
        logger.info("✓ faculty_assignment created for teacher1 → TEST_SECTION")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to create teacher: {e}")
        return False


def seed_test_students(db, count: int = 3):
    """Create test students (student_001, student_002, etc) and enroll in TEST_SECTION."""
    try:
        for i in range(1, count + 1):
            student_id = f"student_{i:03d}"
            student_ref = db.collection("users").document(student_id)
            student_data = {
                "user_id": student_id,
                "name": f"Test Student {i}",
                "email": f"student{i}@test.local",
                "role": "student",
                "status": "active",
                "enrolled_sections": ["TEST_SECTION"],
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            student_ref.set(student_data, merge=True)
            
            # Create enrollment record
            enrollment_ref = db.collection("enrollments").document(f"{student_id}_TEST_SECTION")
            enrollment_data = {
                "student_id": student_id,
                "section_id": "TEST_SECTION",
                "enrollment_date": datetime.utcnow().isoformat(),
                "status": "active",
            }
            enrollment_ref.set(enrollment_data, merge=True)
            
            logger.info(f"✓ {student_id} created and enrolled in TEST_SECTION")
        
        return True
    except Exception as e:
        logger.error(f"✗ Failed to create students: {e}")
        return False


def seed_test_timetable(db):
    """Create test timetable entries for TEST_SECTION."""
    try:
        # Get today's date
        today = datetime.utcnow().date()
        start_time = datetime.utcnow().replace(hour=9, minute=0, second=0, microsecond=0)
        
        periods = [
            {"period_id": "1", "start": start_time, "end": start_time + timedelta(hours=1)},
            {"period_id": "2", "start": start_time + timedelta(hours=1), "end": start_time + timedelta(hours=2)},
            {"period_id": "3", "start": start_time + timedelta(hours=2), "end": start_time + timedelta(hours=3)},
        ]
        
        for period in periods:
            timetable_ref = db.collection("timetables").document(
                f"{today.isoformat()}_TEST_SECTION_{period['period_id']}"
            )
            timetable_data = {
                "date": today.isoformat(),
                "section_id": "TEST_SECTION",
                "period_id": period["period_id"],
                "subject": "Test Subject",
                "teacher_id": "teacher1",
                "start_time": period["start"].isoformat(),
                "end_time": period["end"].isoformat(),
                "created_at": datetime.utcnow().isoformat(),
            }
            timetable_ref.set(timetable_data, merge=True)
            logger.info(f"✓ Timetable entry created: Period {period['period_id']}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Failed to create timetable: {e}")
        return False


def main():
    """Run all seeding operations."""
    logger.info("═══ FIRESTORE TEST DATA SEEDING ═══")
    
    try:
        db = init_firestore()
        
        results = {
            "section": seed_test_section(db),
            "teacher": seed_test_teacher(db),
            "students": seed_test_students(db, count=3),
            "timetable": seed_test_timetable(db),
        }
        
        logger.info("═══ SEEDING COMPLETE ═══")
        logger.info(f"Results: {results}")
        
        if all(results.values()):
            logger.info("✓ All test data seeded successfully!")
            return 0
        else:
            logger.warning("⚠ Some seeding operations failed")
            return 1
            
    except Exception as e:
        logger.error(f"✗ Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
