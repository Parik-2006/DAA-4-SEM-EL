"""
Seed script: convert provided timetable screenshots (pre-parsed into JSON)
into Firestore `periods` collection via TimetableService.seed_from_screenshot.

Usage: set environment FIREBASE_CREDENTIALS_PATH and run locally.
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.firebase_service import initialize_firebase, get_firebase_service
from services.timetable_service import init_timetable_service

# Replace this with JSON parsed from your screenshots.
# Example structure is a list of period dicts with keys matching timetable schema.
TIMETABLE_JSON_PATH = os.getenv("TIMETABLE_JSON_PATH", "./timetable_from_screenshots.json")


def seed():
    creds = os.getenv("FIREBASE_CREDENTIALS_PATH", "config/firebase-credentials.json")
    fb = initialize_firebase(credentials_path=creds, use_firestore=True)
    db = getattr(fb, "firestore_db", None) or getattr(fb, "db", None)
    if not db:
        raise SystemExit("Firestore client not available from FirebaseService")

    tt_svc = init_timetable_service(db)

    if not os.path.exists(TIMETABLE_JSON_PATH):
        raise SystemExit(f"Timetable JSON not found: {TIMETABLE_JSON_PATH}")

    with open(TIMETABLE_JSON_PATH, "r", encoding="utf-8") as fh:
        periods = json.load(fh)

    result = tt_svc.seed_from_screenshot(periods, actor_id="screenshot_seed")
    print("Seeding result:", result)


if __name__ == "__main__":
    seed()
