#!/usr/bin/env python
"""
seed_via_backend.py
─────────────────────────────────────────────────────────────────────────────
Seed test data using the backend's Firebase service initialization.

This ensures credentials and connectivity match what the backend uses.
Uses the unified seed_utils module for robust exception handling.

Usage:
  python scripts/seed_via_backend.py [--section SECTION] [--teacher TEACHER] [--students COUNT]

Examples:
  python scripts/seed_via_backend.py                                    # default TEST_SECTION
  python scripts/seed_via_backend.py --section CS101                    # custom section
  python scripts/seed_via_backend.py --teacher prof1 --students 5       # custom params
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Import backend services
from services.firebase_service import initialize_firebase
from utils.seed_utils import (
    seed_complete_test_environment,
    SeedError
)


def main():
    """Run all seeding operations using backend's Firebase service."""
    parser = argparse.ArgumentParser(
        description="Seed test data to Firestore",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/seed_via_backend.py                                    # default TEST_SECTION
  python scripts/seed_via_backend.py --section CS101                    # custom section
  python scripts/seed_via_backend.py --teacher prof1 --students 5       # custom params
        """
    )
    parser.add_argument(
        "--section",
        default="TEST_SECTION",
        help="Section ID to create (default: TEST_SECTION)"
    )
    parser.add_argument(
        "--teacher",
        default="teacher1",
        help="Teacher user ID (default: teacher1)"
    )
    parser.add_argument(
        "--students",
        type=int,
        default=3,
        help="Number of students to create (default: 3)"
    )
    
    args = parser.parse_args()
    
    logger.info("═══ FIRESTORE TEST DATA SEEDING ═══")
    logger.info("Configuration: section=%s, teacher=%s, students=%d",
                args.section, args.teacher, args.students)
    
    try:
        # Initialize Firebase using backend's same method
        logger.debug("Initializing Firebase service...")
        firebase_svc = initialize_firebase(
            credentials_path="config/firebase-credentials.json"
        )
        
        if firebase_svc is None:
            logger.error("✗ Firebase service initialization returned None")
            return 1
        
        # Get Firestore DB using same attribute lookup as backend
        db = (
            getattr(firebase_svc, "firestore_db", None) or
            getattr(firebase_svc, "_firestore", None) or
            getattr(firebase_svc, "db", None)
        )
        
        if db is None:
            logger.error(
                "✗ Could not obtain Firestore database from Firebase service. "
                "Checked attributes: firestore_db, _firestore, db"
            )
            return 1
        
        logger.info("✓ Firebase service initialized with Firestore DB")
        
        # Generate student IDs
        student_ids = [f"student_{i:03d}" for i in range(1, args.students + 1)]
        
        # Seed complete environment
        logger.debug("Starting seeding process...")
        success, results = seed_complete_test_environment(
            db,
            section_id=args.section,
            teacher_id=args.teacher,
            student_ids=student_ids
        )
        
        # Log results
        logger.info("═══ SEEDING RESULTS ═══")
        for step_name, step_success, error in results:
            status = "✓" if step_success else "✗"
            logger.info("%s %s", status, step_name)
            if error:
                logger.warning("  Error: %s", error)
        
        if success:
            logger.info("✓ All test data seeded successfully!")
            logger.info("Environment ready:")
            logger.info("  Section: %s", args.section)
            logger.info("  Teacher: %s", args.teacher)
            logger.info("  Students: %s", ", ".join(student_ids))
            return 0
        else:
            logger.error("✗ Seeding failed at one or more steps")
            return 1
    
    except SeedError as exc:
        logger.error("✗ Seeding error: %s", exc)
        return 1
    except FileNotFoundError as exc:
        logger.error(
            "✗ Firebase credentials file not found: %s "
            "(expected: config/firebase-credentials.json)",
            exc
        )
        return 1
    except Exception as exc:
        logger.error("✗ Unexpected error during seeding: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
