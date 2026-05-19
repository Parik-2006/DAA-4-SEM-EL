"""
Legacy Script: seed_timetable_fullweek.py

Purpose: Load timetable periods from a JSON file (e.g., parsed from screenshots).

This script is a data import tool for CSV/JSON timetable files.
For general timetable seeding, use the unified:

    python scripts/seed_via_backend.py [--section SECTION_ID] [--teacher TEACHER]

Or use the REST API directly:
    POST /api/v1/timetable/upload

This legacy script:
  ✓ Reads timetable_from_screenshots.json (or custom TIMETABLE_JSON_PATH)
  ✓ Seeds periods via TimetableService.seed_from_screenshot()
  ✗ Requires manual JSON file preparation
  ✗ Not parameterized

The unified seeding path is recommended for:
  ✓ Creating sections, teachers, students, timetables atomically
  ✓ CLI-driven configuration
  ✓ Using backend's Firebase initialization

To use this legacy script:
    TIMETABLE_JSON_PATH=timetable_from_screenshots.json python scripts/seed_timetable_fullweek.py

Or upload via REST API:
    curl -X POST http://localhost:8000/api/v1/timetable/upload \
      -F "file=@timetable.json"

Status: Deprecated. Prefer REST API or unified seeding.
"""

raise NotImplementedError(
    "This script has been deprecated in favor of the REST API.\n"
    "Use: POST /api/v1/timetable/upload with JSON/CSV file\n"
    "Or: python scripts/seed_via_backend.py"
)

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
DEFAULT_TIMETABLE_JSON_PATH = Path(__file__).with_name("timetable_from_screenshots.json")
TIMETABLE_JSON_PATH = Path(
    os.getenv("TIMETABLE_JSON_PATH", str(DEFAULT_TIMETABLE_JSON_PATH))
)


def seed():
    creds = os.getenv("FIREBASE_CREDENTIALS_PATH", "config/firebase-credentials.json")
    fb = initialize_firebase(credentials_path=creds, use_firestore=True)
    db = getattr(fb, "firestore_db", None) or getattr(fb, "db", None)
    if not db:
        raise SystemExit("Firestore client not available from FirebaseService")

    tt_svc = init_timetable_service(db)

    if not TIMETABLE_JSON_PATH.exists():
        raise SystemExit(f"Timetable JSON not found: {TIMETABLE_JSON_PATH}")

    with open(TIMETABLE_JSON_PATH, "r", encoding="utf-8") as fh:
        periods = json.load(fh)

    result = tt_svc.seed_from_screenshot(periods, actor_id="screenshot_seed")
    print("Seeding result:", result)


if __name__ == "__main__":
    seed()
