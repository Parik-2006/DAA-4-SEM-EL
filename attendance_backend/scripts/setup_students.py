"""
setup_students.py — Register students in Firebase with emails and passwords
════════════════════════════════════════════════════════════════════════════════

Usage:
    python setup_students.py

This script creates student records in Firestore with:
  - Email login credentials
  - Hashed passwords
  - Student metadata (name, roll number, etc.)
  - Prepared embeddings storage
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.auth_service import AuthService
from services.firebase_service import FirebaseService


FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "config/firebase-credentials.json")
FIRESTORE_WRITE_TIMEOUT_SECONDS = int(os.getenv("FIRESTORE_WRITE_TIMEOUT_SECONDS", "30"))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# ── Student data ─────────────────────────────────────────────────────────────
STUDENTS = [
    {
        "student_id": "STUD_001",
        "name": "Parikshith B Bilchode",
        "email": "parikshithbb.cs25@rvce.edu.in",
        "password": "viratkohli18",
        "roll_no": "4CS01",
        "class_id": "4CS",
        "section": "A",
    },
    {
        "student_id": "STUD_002",
        "name": "Gagan D K",
        "email": "gagandk2005@gmail.com",
        "password": "password123",
        "roll_no": "4CS02",
        "class_id": "4CS",
        "section": "A",
    },
    {
        "student_id": "STUD_003",
        "name": "Prajwal K",
        "email": "prajwalk.cs24@rvce.edu.in",
        "password": "password123",
        "roll_no": "4CS03",
        "class_id": "4CS",
        "section": "A",
    },
    {
        "student_id": "STUD_004",
        "name": "Ved U",
        "email": "vedu.cs25@rvce.edu.in",
        "password": "password123",
        "roll_no": "4CS04",
        "class_id": "4CS",
        "section": "A",
    },
    {
        "student_id": "STUD_005",
        "name": "Pranav Kumar M",
        "email": "pranavkumarm.cs24@rvce.edu.in",
        "password": "password123",
        "roll_no": "4CS05",
        "class_id": "4CS",
        "section": "A",
    },
    {
        "student_id": "STUD_006",
        "name": "Nischith G A",
        "email": "nishchithgarg.cs24@rvce.edu.in",
        "password": "password123",
        "roll_no": "4CS06",
        "class_id": "4CS",
        "section": "A",
    },
    {
        "student_id": "STUD_007",
        "name": "Yohith N",
        "email": "nyohith.cs24@rvce.edu.in",
        "password": "password123",
        "roll_no": "4CS07",
        "class_id": "4CS",
        "section": "A",
    },
    {
        "student_id": "STUD_008",
        "name": "Mahesh Raju",
        "email": "nrmaheshraju.cs24@rvce.edu.in",
        "password": "password123",
        "roll_no": "4CS08",
        "class_id": "4CS",
        "section": "A",
    },
]


def setup_students():
    """Create student records in Firestore."""
    try:
        # Initialize Firebase
        firebase = FirebaseService.initialize(
            credentials_path=FIREBASE_CREDENTIALS_PATH,
            use_firestore=True,
        )
        db = firebase.firestore_db
        
        if not db:
            logger.error("❌ Firebase not initialized properly")
            return False
        
        auth_svc = AuthService()
        
        logger.info("📋 Setting up student records...")
        logger.info("=" * 70)
        
        success_count = 0
        
        for student_data in STUDENTS:
            try:
                student_id = student_data["student_id"]
                email = student_data["email"]
                password = student_data["password"]
                name = student_data["name"]
                
                # Check if user already exists
                existing = db.collection("users").where(
                    filter=__import__('google.cloud.firestore_v1', fromlist=['FieldFilter']).FieldFilter("email", "==", email)
                ).limit(1).stream()
                
                existing_list = list(existing)
                if existing_list:
                    logger.info(f"⏭️  {student_id}: {email} — already exists")
                    success_count += 1
                    continue
                
                # Hash password
                password_hash = auth_svc.hash_password(password)
                
                # Create user record
                user_doc = {
                    "id": student_id,
                    "name": name,
                    "email": email,
                    "password_hash": password_hash,
                    "role": "student",
                    "assigned_sections": [],
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "status": "active",
                    "roll_no": student_data.get("roll_no", ""),
                    "class_id": student_data.get("class_id", ""),
                    "section": student_data.get("section", ""),
                }
                
                # Add to Firestore
                db.collection("users").document(student_id).set(
                    user_doc,
                    timeout=FIRESTORE_WRITE_TIMEOUT_SECONDS,
                )
                
                # Create embeddings storage structure
                db.collection("students").document(student_id).set(
                    {
                        "student_id": student_id,
                        "name": name,
                        "email": email,
                        "roll_no": student_data.get("roll_no", ""),
                        "class_id": student_data.get("class_id", ""),
                        "section": student_data.get("section", ""),
                        "embeddings": [],  # Will be populated when images are uploaded
                        "enrollment_status": "active",
                        "registered_at": datetime.now().isoformat(),
                    },
                    timeout=FIRESTORE_WRITE_TIMEOUT_SECONDS,
                )
                
                logger.info(f"✅ {student_id}: {name} ({email}) created successfully")
                success_count += 1
                
            except Exception as e:
                logger.error(f"❌ {student_data['student_id']}: Failed — {e}")
                continue
        
        logger.info("=" * 70)
        logger.info(f"✅ Setup complete: {success_count}/{len(STUDENTS)} students configured")
        return success_count == len(STUDENTS)
        
    except Exception as e:
        logger.error(f"❌ Setup failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = setup_students()
    sys.exit(0 if success else 1)
