"""
utils/seed_utils.py
─────────────────────────────────────────────────────────────────────────────
Test data seeding utilities with robust exception handling and logging.

Provides functions for creating test users, sections, enrollments, and
timetables in Firestore.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SeedError(Exception):
    """Raised when seeding fails."""
    pass


def seed_test_section(
    db,
    section_id: str = "TEST_SECTION",
    section_name: str = "Test Section",
    code: str = "TEST-101"
) -> Tuple[bool, Optional[str]]:
    """
    Create a test section in Firestore.
    
    Parameters
    ----------
    db : firestore.Client
        Firestore database client
    section_id : str
        Section ID (default: "TEST_SECTION")
    section_name : str
        Display name (default: "Test Section")
    code : str
        Course code (default: "TEST-101")
    
    Returns
    -------
    tuple[bool, str | None]
        (success, error_message)
    """
    try:
        if db is None:
            raise SeedError("Firestore database not available")
        
        section_ref = db.collection("sections").document(section_id)
        section_data = {
            "section_id": section_id,
            "name": section_name,
            "code": code,
            "department": "Engineering",
            "semester": 4,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        section_ref.set(section_data, merge=True)
        logger.info("✓ Section %s created/updated", section_id)
        return True, None
    except Exception as exc:
        error_msg = f"Failed to create section {section_id}: {exc}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg


def seed_test_teacher(
    db,
    user_id: str = "teacher1",
    name: str = "Test Teacher",
    email: str = "teacher@test.local",
    section_id: str = "TEST_SECTION"
) -> Tuple[bool, Optional[str]]:
    """
    Create a test teacher and assign to section.
    
    Parameters
    ----------
    db : firestore.Client
        Firestore database client
    user_id : str
        Teacher user ID (default: "teacher1")
    name : str
        Teacher name (default: "Test Teacher")
    email : str
        Teacher email (default: "teacher@test.local")
    section_id : str
        Section to assign (default: "TEST_SECTION")
    
    Returns
    -------
    tuple[bool, str | None]
        (success, error_message)
    """
    try:
        if db is None:
            raise SeedError("Firestore database not available")
        
        # Create user
        teacher_ref = db.collection("users").document(user_id)
        teacher_data = {
            "user_id": user_id,
            "name": name,
            "email": email,
            "role": "teacher",
            "assigned_sections": [section_id],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        teacher_ref.set(teacher_data, merge=True)
        logger.info("✓ Teacher user %s created", user_id)
        
        # Create faculty assignment
        faculty_ref = db.collection("faculty_assignments").document(f"{user_id}_{section_id}")
        faculty_data = {
            "user_id": user_id,
            "section_id": section_id,
            "assigned_at": datetime.utcnow().isoformat(),
        }
        faculty_ref.set(faculty_data, merge=True)
        logger.info("✓ Faculty assignment created for %s → %s", user_id, section_id)
        
        return True, None
    except Exception as exc:
        error_msg = f"Failed to create teacher {user_id}: {exc}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg


def seed_test_students(
    db,
    student_ids: Optional[List[str]] = None,
    section_id: str = "TEST_SECTION"
) -> Tuple[bool, Optional[str]]:
    """
    Create test students and enroll in section.
    
    Parameters
    ----------
    db : firestore.Client
        Firestore database client
    student_ids : list[str], optional
        Student IDs to create (default: ["student_001", "student_002", "student_003"])
    section_id : str
        Section to enroll in (default: "TEST_SECTION")
    
    Returns
    -------
    tuple[bool, str | None]
        (success, error_message)
    """
    try:
        if db is None:
            raise SeedError("Firestore database not available")
        
        if student_ids is None:
            student_ids = ["student_001", "student_002", "student_003"]
        
        now = datetime.utcnow().isoformat()
        
        for student_id in student_ids:
            try:
                # Create user
                student_ref = db.collection("users").document(student_id)
                student_data = {
                    "user_id": student_id,
                    "name": f"Test Student {student_id[-3:]}",
                    "email": f"{student_id}@test.local",
                    "role": "student",
                    "created_at": now,
                    "updated_at": now,
                }
                student_ref.set(student_data, merge=True)
                
                # Create enrollment
                enrollment_ref = db.collection("enrollments").document(f"{student_id}_{section_id}")
                enrollment_data = {
                    "user_id": student_id,
                    "section_id": section_id,
                    "enrolled_at": now,
                }
                enrollment_ref.set(enrollment_data, merge=True)
                
                logger.info("✓ Student %s created and enrolled in %s", student_id, section_id)
            except Exception as student_exc:
                logger.error("Failed to create student %s: %s", student_id, student_exc)
                return False, f"Failed to create student {student_id}: {student_exc}"
        
        return True, None
    except Exception as exc:
        error_msg = f"Failed to create students: {exc}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg


def seed_test_timetable(
    db,
    section_id: str = "TEST_SECTION",
    periods_per_day: int = 3,
    start_hour: int = 9
) -> Tuple[bool, Optional[str]]:
    """
    Create test timetable entries.
    
    Parameters
    ----------
    db : firestore.Client
        Firestore database client
    section_id : str
        Section ID (default: "TEST_SECTION")
    periods_per_day : int
        Number of periods per day (default: 3)
    start_hour : int
        Starting hour (default: 9)
    
    Returns
    -------
    tuple[bool, str | None]
        (success, error_message)
    """
    try:
        if db is None:
            raise SeedError("Firestore database not available")
        
        now = datetime.utcnow().isoformat()
        
        # Monday-Friday, periods 1-3
        for day in range(5):
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            day_name = day_names[day]
            
            for period in range(1, periods_per_day + 1):
                try:
                    start_time = f"{start_hour + (period - 1):02d}:00"
                    end_time = f"{start_hour + period:02d}:00"
                    
                    timetable_ref = db.collection("timetables").document(
                        f"{section_id}_{day_name}_{period}"
                    )
                    timetable_data = {
                        "section_id": section_id,
                        "day": day_name,
                        "period_id": period,
                        "start_time": start_time,
                        "end_time": end_time,
                        "subject": f"Subject {period}",
                        "created_at": now,
                        "updated_at": now,
                    }
                    timetable_ref.set(timetable_data, merge=True)
                except Exception as period_exc:
                    logger.error(
                        "Failed to create timetable for %s %s period %d: %s",
                        section_id,
                        day_name,
                        period,
                        period_exc
                    )
                    return False, f"Failed to create timetable entry: {period_exc}"
        
        logger.info("✓ Timetable entries created for %s", section_id)
        return True, None
    except Exception as exc:
        error_msg = f"Failed to create timetable: {exc}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg


def seed_complete_test_environment(
    db,
    section_id: str = "TEST_SECTION",
    teacher_id: str = "teacher1",
    student_ids: Optional[List[str]] = None
) -> Tuple[bool, List[Tuple[str, bool, Optional[str]]]]:
    """
    Seed a complete test environment (section, teacher, students, timetable).
    
    Parameters
    ----------
    db : firestore.Client
        Firestore database client
    section_id : str
        Section ID (default: "TEST_SECTION")
    teacher_id : str
        Teacher ID (default: "teacher1")
    student_ids : list[str], optional
        Student IDs (default: ["student_001", "student_002", "student_003"])
    
    Returns
    -------
    tuple[bool, list]
        (all_succeeded, list of (step_name, success, error_message))
    """
    try:
        results = []
        
        # Step 1: Section
        success, error = seed_test_section(db, section_id)
        results.append(("Create section", success, error))
        if not success:
            logger.error("Cannot continue without section: %s", error)
            return False, results
        
        # Step 2: Teacher
        success, error = seed_test_teacher(db, teacher_id, section_id=section_id)
        results.append(("Create teacher", success, error))
        if not success:
            logger.error("Cannot continue without teacher: %s", error)
            return False, results
        
        # Step 3: Students
        success, error = seed_test_students(db, student_ids, section_id)
        results.append(("Create students", success, error))
        if not success:
            logger.error("Cannot continue without students: %s", error)
            return False, results
        
        # Step 4: Timetable
        success, error = seed_test_timetable(db, section_id)
        results.append(("Create timetable", success, error))
        if not success:
            logger.error("Cannot continue without timetable: %s", error)
            return False, results
        
        logger.info("✓ Complete test environment seeded successfully")
        return True, results
    
    except Exception as exc:
        logger.error("Error seeding test environment: %s", exc, exc_info=True)
        return False, [("Unexpected error", False, str(exc))]
