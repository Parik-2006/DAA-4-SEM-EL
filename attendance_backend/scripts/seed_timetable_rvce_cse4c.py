"""
scripts/seed_timetable_rvce_cse4c.py
──────────────────────────────────────────────────────────────────────────────
Seeds the Firestore `periods`, `courses`, and `course_assignments` collections
from the real RVCE CSE 4C Semester 4 (Even Sem 2025-26) timetable.

Run once during initial setup:
    python -m scripts.seed_timetable_rvce_cse4c

Idempotent: uses period_id as the document ID so re-running is safe.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Timetable constants ────────────────────────────────────────────────────────

CLASS_ID     = "CSE_4C_SEM4"
CLASSROOM    = "CSE-CC-203"
SEMESTER     = 4
SECTION      = "C"
PROGRAM      = "UG CSE"
ACADEMIC_YR  = "2025-26"
EFFECTIVE_DT = "2026-03-09"   # w.e.f on the timetable sheet

# Day-of-week integers (0 = Monday … 5 = Saturday)
MON, TUE, WED, THU, FRI, SAT = 0, 1, 2, 3, 4, 5

# ── Course catalogue ────────────────────────────────────────────────────────────
# course_id → {name, faculty_id, email}

COURSES = {
    "CS241AT": {
        "name":       "Discrete Mathematical Structures and Combinatorics",
        "short":      "DMS",
        "faculty_id": "FAC_ANITHA",
        "faculty":    "Dr. Anitha Sandeep",
        "email":      "anithasandeep@rvce.edu.in",
    },
    "CD343AI": {
        "name":       "Design and Analysis of Algorithms",
        "short":      "DAA",
        "faculty_id": "FAC_SARASWATHI",
        "faculty":    "Prof. Saraswathi G Datar",
        "email":      "saraswathigd@rvce.edu.in",
    },
    "CS344AI": {
        "name":       "IoT and Embedded Computing",
        "short":      "IOT",
        "faculty_id": "FAC_NEETHU",
        "faculty":    "Prof. Neethu Srikumaran",
        "email":      "neethus@rvce.edu.in",
    },
    "CY245AT": {
        "name":       "Computer Networks",
        "short":      "CN",
        "faculty_id": "FAC_NAGARAJA",
        "faculty":    "Dr. G S Nagaraja",
        "email":      "nagarajasg@rvce.edu.in",
    },
    "HS248AT": {
        "name":       "Universal Human Values",
        "short":      "UHV",
        "faculty_id": "FAC_RAVIKIRAN",
        "faculty":    "Prof. Ravikiran S Wali",
        "email":      "ravikiransw@rvce.edu.in",
    },
    "CS246TX": {
        "name":       "Professional Elective Course – Group B",
        "short":      "EL",
        "faculty_id": "FAC_ELECTIVE",
        "faculty":    "TBD",
        "email":      "",
    },
    "HS247LX": {
        "name":       "Ability Enhancement Course – Group C",
        "short":      "AEC",
        "faculty_id": "FAC_AEC",
        "faculty":    "TBD",
        "email":      "",
    },
    "CV242AT": {
        "name":       "Basket Course",
        "short":      "BASKET",
        "faculty_id": "FAC_BASKET",
        "faculty":    "TBD",
        "email":      "",
    },
    "MAT149AT": {
        "name":       "Bridge Course: Mathematics",
        "short":      "BCM",
        "faculty_id": "FAC_BRIDGE_MATHS",
        "faculty":    "TBD",
        "email":      "",
    },
    "XX_COUNSEL": {
        "name":       "Counselling",
        "short":      "COUNSEL",
        "faculty_id": "FAC_COUNSELLOR",
        "faculty":    "TBD",
        "email":      "",
    },
    "XX_IOT_LAB": {
        "name":       "IoT Lab",
        "short":      "IOT LAB",
        "faculty_id": "FAC_NEETHU",
        "faculty":    "Prof. Neethu Srikumaran",
        "email":      "neethus@rvce.edu.in",
    },
    "XX_DAA_LAB": {
        "name":       "Design and Analysis of Algorithms Lab",
        "short":      "DAA LAB",
        "faculty_id": "FAC_SARASWATHI",
        "faculty":    "Prof. Saraswathi G Datar",
        "email":      "saraswathigd@rvce.edu.in",
    },
    "XX_DMS_LAB": {
        "name":       "DMS Lab / Tutorial",
        "short":      "DMS*",
        "faculty_id": "FAC_ANITHA",
        "faculty":    "Dr. Anitha Sandeep",
        "email":      "anithasandeep@rvce.edu.in",
    },
}


# ── Period definitions ─────────────────────────────────────────────────────────
# Each tuple: (period_id, day, start, end, course_id, period_type)
#
# Period IDs are stable and used as Firestore document IDs.
# Short Break  11:00–11:30  →  period_type="break"  (no attendance)
# Lunch Break  1:30–2:30    →  period_type="break"   (no attendance)

PERIODS: list[tuple] = [

    # ── MONDAY ────────────────────────────────────────────────────────────────
    ("CSE4C_MON_0900", MON, "09:00", "10:00", "CS344AI", "lecture"),  # IOT
    ("CSE4C_MON_1000", MON, "10:00", "11:00", "CD343AI", "lecture"),  # DAA
    ("CSE4C_MON_1100", MON, "11:00", "11:30", None,      "break"),    # Short break
    ("CSE4C_MON_1130", MON, "11:30", "12:30", "CS241AT", "lecture"),  # DMS
    ("CSE4C_MON_1230", MON, "12:30", "13:30", "CY245AT", "lecture"),  # CN
    ("CSE4C_MON_1330", MON, "13:30", "14:30", None,      "break"),    # Lunch
    ("CSE4C_MON_1430", MON, "14:30", "16:30", "CV242AT", "lecture"),  # BASKET COURSE (2 h)

    # ── TUESDAY ───────────────────────────────────────────────────────────────
    ("CSE4C_TUE_0900", TUE, "09:00", "10:00", "CD343AI", "lecture"),  # DAA
    ("CSE4C_TUE_1000", TUE, "10:00", "11:00", "CV242AT", "lecture"),  # BASKET COURSE
    ("CSE4C_TUE_1100", TUE, "11:00", "11:30", None,      "break"),
    ("CSE4C_TUE_1130", TUE, "11:30", "12:30", "CY245AT", "lecture"),  # CN
    ("CSE4C_TUE_1230", TUE, "12:30", "13:30", "CS344AI", "lecture"),  # IOT
    ("CSE4C_TUE_1330", TUE, "13:30", "14:30", None,      "break"),
    ("CSE4C_TUE_1430", TUE, "14:30", "16:30", "HS247LX", "lecture"),  # AEC COURSE (2 h)

    # ── WEDNESDAY ─────────────────────────────────────────────────────────────
    ("CSE4C_WED_0900", WED, "09:00", "10:00", "CS241AT", "lecture"),  # DMS
    ("CSE4C_WED_1000", WED, "10:00", "11:00", "CY245AT", "lecture"),  # CN
    ("CSE4C_WED_1100", WED, "11:00", "11:30", None,      "break"),
    ("CSE4C_WED_1130", WED, "11:30", "12:30", "CS344AI", "lecture"),  # IOT
    ("CSE4C_WED_1230", WED, "12:30", "13:30", "CS246TX", "lecture"),  # EL
    ("CSE4C_WED_1330", WED, "13:30", "14:30", None,      "break"),
    ("CSE4C_WED_1430", WED, "14:30", "16:30", "MAT149AT","lecture"),  # BRIDGE MATHS (2 h)

    # ── THURSDAY ──────────────────────────────────────────────────────────────
    ("CSE4C_THU_0900", THU, "09:00", "11:00", "XX_IOT_LAB", "lab"),   # IOT LAB (2 h)
    ("CSE4C_THU_1100", THU, "11:00", "11:30", None,         "break"),
    ("CSE4C_THU_1130", THU, "11:30", "12:30", "HS248AT",    "lecture"),  # UHV
    ("CSE4C_THU_1230", THU, "12:30", "13:30", "XX_DMS_LAB", "lab"),      # DMS*
    ("CSE4C_THU_1330", THU, "13:30", "14:30", None,         "break"),
    # No afternoon periods on Thursday

    # ── FRIDAY ────────────────────────────────────────────────────────────────
    ("CSE4C_FRI_0900", FRI, "09:00", "11:00", "XX_DAA_LAB", "lab"),      # DAA LAB (2 h)
    ("CSE4C_FRI_1100", FRI, "11:00", "11:30", None,         "break"),
    ("CSE4C_FRI_1130", FRI, "11:30", "12:30", "HS248AT",    "lecture"),  # UHV
    ("CSE4C_FRI_1230", FRI, "12:30", "13:30", "CS241AT",    "lecture"),  # DMS
    ("CSE4C_FRI_1330", FRI, "13:30", "14:30", None,         "break"),
    ("CSE4C_FRI_1430", FRI, "14:30", "15:30", "CD343AI",    "lecture"),  # DAA
    ("CSE4C_FRI_1530", FRI, "15:30", "16:30", "XX_COUNSEL", "lecture"),  # COUNSELLING

    # SATURDAY — no periods
]


# ── Firestore seeding helpers ──────────────────────────────────────────────────

def _now() -> str:
    return datetime.utcnow().isoformat()


def seed_courses(db) -> None:
    """Write course documents."""
    col = db.collection("courses")
    now = _now()
    for course_id, meta in COURSES.items():
        doc = {
            "course_id":    course_id,
            "name":         meta["name"],
            "short_name":   meta["short"],
            "faculty_id":   meta["faculty_id"],
            "faculty_name": meta["faculty"],
            "email":        meta["email"],
            "class_id":     CLASS_ID,
            "semester":     SEMESTER,
            "academic_year": ACADEMIC_YR,
            "active_status": True,
            "created_at":   now,
            "updated_at":   now,
        }
        col.document(course_id).set(doc, merge=True)
        logger.info("Seeded course: %s (%s)", course_id, meta["short"])


def seed_faculty(db) -> None:
    """Write minimal faculty stubs — fill in face embeddings later."""
    col = db.collection("faculty")
    now = _now()
    seen: set[str] = set()
    for meta in COURSES.values():
        fid = meta["faculty_id"]
        if fid in seen:
            continue
        seen.add(fid)
        doc = {
            "faculty_id":  fid,
            "name":        meta["faculty"],
            "email":       meta["email"],
            "class_ids":   [CLASS_ID],
            "active_status": True,
            "created_at":  now,
            "updated_at":  now,
        }
        col.document(fid).set(doc, merge=True)
        logger.info("Seeded faculty: %s", fid)


def seed_periods(db) -> None:
    """Write period documents. Skips break rows (course_id is None)."""
    col = db.collection("periods")
    now = _now()

    for row in PERIODS:
        pid, day, start, end, course_id, p_type = row

        if p_type == "break":
            # Still store breaks so the UI can show them;
            # attendance window logic skips them.
            doc = {
                "period_id":    pid,
                "class_id":     CLASS_ID,
                "day_of_week":  day,
                "start_time":   start,
                "end_time":     end,
                "period_type":  p_type,
                "course_id":    None,
                "faculty_id":   None,
                "room":         CLASSROOM,
                "active_status": True,
                "created_at":   now,
                "updated_at":   now,
                "metadata":     {},
            }
            col.document(pid).set(doc, merge=True)
            logger.info("Seeded break: %s (%s–%s)", pid, start, end)
            continue

        course = COURSES[course_id]
        doc = {
            "period_id":    pid,
            "class_id":     CLASS_ID,
            "day_of_week":  day,
            "start_time":   start,
            "end_time":     end,
            "period_type":  p_type,
            "course_id":    course_id,
            "course_name":  course["name"],
            "course_short": course["short"],
            "faculty_id":   course["faculty_id"],
            "room":         CLASSROOM,
            "active_status": True,
            "created_at":   now,
            "updated_at":   now,
            "metadata": {
                "academic_year": ACADEMIC_YR,
                "effective_date": EFFECTIVE_DT,
            },
        }
        col.document(pid).set(doc, merge=True)
        logger.info(
            "Seeded period: %s  day=%d  %s–%s  [%s]",
            pid, day, start, end, course["short"],
        )


def seed_class(db) -> None:
    """Write the class document linking everything together."""
    doc = {
        "class_id":     CLASS_ID,
        "classroom":    CLASSROOM,
        "program":      PROGRAM,
        "semester":     SEMESTER,
        "section":      SECTION,
        "academic_year": ACADEMIC_YR,
        "effective_date": EFFECTIVE_DT,
        "active_status": True,
        "created_at":   _now(),
        "updated_at":   _now(),
    }
    db.collection("classes").document(CLASS_ID).set(doc, merge=True)
    logger.info("Seeded class: %s", CLASS_ID)


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        from services.firebase_service import get_firebase_service
        fb = get_firebase_service()
        db = getattr(fb, "firestore_db", None) or getattr(fb, "_firestore", None)
        if db is None:
            logger.error("Firestore client not available. Check firebase credentials.")
            sys.exit(1)
    except Exception as exc:
        logger.error("Could not initialise Firebase: %s", exc)
        sys.exit(1)

    logger.info("── Seeding RVCE CSE 4C Sem-4 timetable ──")
    seed_class(db)
    seed_courses(db)
    seed_faculty(db)
    seed_periods(db)
    logger.info("── Done. %d periods written. ──", len(PERIODS))


if __name__ == "__main__":
    main()
