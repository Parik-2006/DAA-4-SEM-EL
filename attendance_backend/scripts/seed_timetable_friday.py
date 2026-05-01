import os
import sys
from pathlib import Path
import logging
from datetime import datetime

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.firebase_service import initialize_firebase, get_firebase_service
from services.timetable_service import TimetableService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed_timetable")

# Friday Timetable for CSE C 4th Sem
FRIDAY_PERIODS = [
    {
        "class_id": "CSE-C-4SEM",
        "faculty_id": "T001",
        "course_id": "CS343AI",
        "course_name": "DAA LAB",
        "day_of_week": "Friday",
        "start_time": "09:00",
        "end_time": "11:00",
        "period_type": "lab",
        "room": "CC 203"
    },
    {
        "class_id": "CSE-C-4SEM",
        "faculty_id": "T002",
        "course_id": "HS248AT",
        "course_name": "UHV",
        "day_of_week": "Friday",
        "start_time": "11:30",
        "end_time": "12:30",
        "period_type": "lecture",
        "room": "CC 203"
    },
    {
        "class_id": "CSE-C-4SEM",
        "faculty_id": "T003",
        "course_id": "CS241AT",
        "course_name": "DMS",
        "day_of_week": "Friday",
        "start_time": "12:30",
        "end_time": "13:30",
        "period_type": "lecture",
        "room": "CC 203"
    },
    {
        "class_id": "CSE-C-4SEM",
        "faculty_id": "T001",
        "course_id": "CD343AI",
        "course_name": "DAA",
        "day_of_week": "Friday",
        "start_time": "14:30",
        "end_time": "15:30",
        "period_type": "lecture",
        "room": "CC 203"
    },
    {
        "class_id": "CSE-C-4SEM",
        "faculty_id": "T004",
        "course_id": "COUNSEL",
        "course_name": "COUNSELLING",
        "day_of_week": "Friday",
        "start_time": "15:30",
        "end_time": "16:30",
        "period_type": "lecture",
        "room": "CC 203"
    }
]

def seed():
    # Initialize Firebase
    creds = os.getenv("FIREBASE_CREDENTIALS_PATH", "config/firebase-credentials.json")
    db_url = os.getenv("FIREBASE_DATABASE_URL")
    bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
    firebase = initialize_firebase(creds, db_url, bucket, use_firestore=True)
    
    # Use Firestore client directly to add to 'timetable' collection
    db = firebase.db
    
    logger.info("Seeding Friday timetable for CSE-C-4SEM...")
    
    for period in FRIDAY_PERIODS:
        # Create a unique ID or let Firestore generate one
        # Using class_id + day + start_time as a key for idempotency
        period_id = f"{period['class_id']}_{period['day_of_week']}_{period['start_time'].replace(':', '')}"
        
        doc_ref = db.collection("timetable").document(period_id)
        period["id"] = period_id
        period["active_status"] = True
        period["created_at"] = datetime.utcnow().isoformat() + "Z"
        
        doc_ref.set(period)
        logger.info(f"✅ Added {period['course_name']} ({period['start_time']} - {period['end_time']})")

if __name__ == "__main__":
    seed()
