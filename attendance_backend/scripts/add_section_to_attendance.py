"""
Migration Tool: add_section_to_attendance.py
=============================================

Purpose: One-time data migration to backfill missing section_id on attendance records.

This is a DATA MIGRATION tool, separate from the seeding path.
Use this ONLY if upgrading from an older schema that lacked section_id.

What it does:
  ✓ Finds all attendance records with missing/empty section_id
  ✓ Stamps them with a default section_id (configurable)
  ✓ Creates seed documents (Course, Section, Enrollment, CourseAssignment)
  ✓ Uses atomic Firestore batched commits
  ✓ Provides detailed reporting and dry-run mode
  ✓ Safe to re-run (already-patched docs are skipped)

Usage (one-time migration):
  python attendance_backend/scripts/add_section_to_attendance.py

With options:
  --dry-run              Preview changes without writing
  --default-section CSE_C  Override default section name
  --section-id ID        Explicitly set section_id to stamp
  --batch-size 500       Firestore batch size (default 400, max 500)
  --verbose              Print every document processed

Example:
  python attendance_backend/scripts/add_section_to_attendance.py --dry-run
  python attendance_backend/scripts/add_section_to_attendance.py --default-section CSE_4C

Notes:
  • Run once during schema upgrade.
  • Safe to re-run (idempotent).
  • Batched writes are atomic per batch.
  • Only edits docs with missing section_id.

NOTE: For NEW sections/attendance, use the unified seeding path:
  python scripts/seed_via_backend.py [--section SECTION]

Status: Active (migration tool, not seeding).
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── path bootstrap ─────────────────────────────────────────────────────────────
# Allow running from the repo root without installing the package.
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

# ── project imports ────────────────────────────────────────────────────────────
try:
    from database.firebase_client import FirebaseClient
    from config.constants import FIREBASE_COLLECTIONS
except ImportError as exc:
    sys.exit(
        f"[ERROR] Could not import project modules. "
        f"Run from the project root.\nDetail: {exc}"
    )

logger = logging.getLogger("migration.add_section_to_attendance")

# ── constants ──────────────────────────────────────────────────────────────────

DEFAULT_SECTION_NAME = "CSE_C"
DEFAULT_COURSE_ID    = "CSE"
DEFAULT_SEMESTER     = 4
DEFAULT_YEAR         = datetime.now().year
MAX_BATCH_SIZE       = 400   # Firestore hard limit is 500; leave headroom

COL_ATTENDANCE         = FIREBASE_COLLECTIONS.get("attendance", "attendance")
COL_STUDENTS           = FIREBASE_COLLECTIONS.get("students", "students")
COL_COURSES            = FIREBASE_COLLECTIONS.get("courses", "courses")
COL_SECTIONS           = FIREBASE_COLLECTIONS.get("sections", "sections")
COL_ENROLLMENTS        = FIREBASE_COLLECTIONS.get("enrollments", "enrollments")
COL_COURSE_ASSIGNMENTS = FIREBASE_COLLECTIONS.get("course_assignments", "course_assignments")


# ── helpers ────────────────────────────────────────────────────────────────────

def build_section_id(section_name: str, semester: int, year: int) -> str:
    """Derive a canonical section_id from its parts."""
    return f"{section_name}_SEM{semester}_{year}"


def chunk(lst: list, size: int):
    """Yield successive chunks of ``size`` from ``lst``."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


# ── seed helpers ───────────────────────────────────────────────────────────────

def seed_course(client: FirebaseClient, course_id: str, dry_run: bool) -> None:
    """Create the default Course document if it doesn't already exist."""
    existing = client._fs_get(COL_COURSES, course_id)
    if existing:
        logger.info("Course %s already exists — skipping.", course_id)
        return
    course = {
        "course_id":   course_id,
        "name":        "Computer Science Engineering",
        "code":        course_id,
        "credits":     4,
        "department":  "Computer Science",
        "created_at":  datetime.now().isoformat(),
    }
    if dry_run:
        logger.info("[DRY-RUN] Would create course: %s", course)
        return
    ok = client._fs_set(COL_COURSES, course_id, course)
    logger.info("Created course %s: %s", course_id, "OK" if ok else "FAILED")


def seed_section(
    client: FirebaseClient,
    section_id: str,
    section_name: str,
    course_id: str,
    semester: int,
    year: int,
    dry_run: bool,
) -> None:
    """Create the default Section document if it doesn't already exist."""
    existing = client._fs_get(COL_SECTIONS, section_id)
    if existing:
        logger.info("Section %s already exists — skipping.", section_id)
        return
    section = {
        "section_id":   section_id,
        "course_id":    course_id,
        "section_name": section_name,
        "semester":     semester,
        "year":         year,
        "capacity":     60,
        "created_at":   datetime.now().isoformat(),
    }
    if dry_run:
        logger.info("[DRY-RUN] Would create section: %s", section)
        return
    ok = client._fs_set(COL_SECTIONS, section_id, section)
    logger.info("Created section %s: %s", section_id, "OK" if ok else "FAILED")


def seed_enrollments(
    client: FirebaseClient,
    section_id: str,
    dry_run: bool,
) -> int:
    """
    Create Enrollment documents for every existing student that doesn't
    already have one for this section.

    Returns the number of enrollments created.
    """
    students = client._fs_list(COL_STUDENTS)
    created = 0
    fs = client._require_fs()

    for student in students:
        student_id = student.get("student_id") or student.get("id")
        if not student_id:
            continue
        enrollment_id = f"{student_id}_{section_id}"
        if client._fs_get(COL_ENROLLMENTS, enrollment_id):
            continue   # already enrolled
        enrollment = {
            "enrollment_id":   enrollment_id,
            "student_id":      student_id,
            "section_id":      section_id,
            "enrollment_date": datetime.now().date().isoformat(),
            "created_at":      datetime.now().isoformat(),
        }
        if dry_run:
            logger.debug("[DRY-RUN] Would enroll %s in %s", student_id, section_id)
            created += 1
            continue
        ok = client._fs_set(COL_ENROLLMENTS, enrollment_id, enrollment)
        if ok:
            created += 1

    logger.info("Enrollments created: %d", created)
    return created


def seed_course_assignment(
    client: FirebaseClient,
    section_id: str,
    dry_run: bool,
) -> None:
    """
    Create a placeholder CourseAssignment for the default admin teacher
    if none exists.  This satisfies the FK constraint so section queries work.
    Admins should replace this with real teacher assignments via the UI.
    """
    assignment_id = f"ADMIN_{section_id}"
    if client._fs_get(COL_COURSE_ASSIGNMENTS, assignment_id):
        logger.info("CourseAssignment %s already exists — skipping.", assignment_id)
        return
    assignment = {
        "assignment_id": assignment_id,
        "teacher_id":    "ADMIN",
        "faculty_id":    "ADMIN",   # legacy alias
        "section_id":    section_id,
        "courses":       [DEFAULT_COURSE_ID],
        "start_date":    datetime.now().date().isoformat(),
        "is_primary":    True,
        "note":          "Auto-created by migration script — replace with real teacher.",
        "created_at":    datetime.now().isoformat(),
    }
    if dry_run:
        logger.info("[DRY-RUN] Would create course assignment: %s", assignment)
        return
    ok = client._fs_set(COL_COURSE_ASSIGNMENTS, assignment_id, assignment)
    logger.info(
        "Created placeholder course assignment %s: %s",
        assignment_id,
        "OK" if ok else "FAILED",
    )


# ── main migration ─────────────────────────────────────────────────────────────

def migrate_attendance(
    client: FirebaseClient,
    section_id: str,
    batch_size: int,
    dry_run: bool,
    verbose: bool,
) -> Dict[str, int]:
    """
    Scan the attendance collection and stamp missing section_id fields.

    Returns a summary dict: {total, patched, skipped, errors}.
    """
    fs = client._require_fs()
    col_ref = fs.collection(COL_ATTENDANCE)

    logger.info("Scanning attendance collection…")
    all_docs = list(col_ref.stream())
    total = len(all_docs)
    logger.info("Found %d attendance documents total.", total)

    to_patch: List[Any] = []
    skipped = 0

    for doc in all_docs:
        data = doc.to_dict() or {}
        existing_section = data.get("section_id", "").strip()
        if existing_section:
            skipped += 1
            if verbose:
                logger.debug("SKIP %s  (section_id=%s)", doc.id, existing_section)
            continue
        to_patch.append(doc)

    logger.info(
        "Documents to patch: %d  |  Already have section_id (skip): %d",
        len(to_patch),
        skipped,
    )

    if not to_patch:
        logger.info("Nothing to do — all records already have section_id.")
        return {"total": total, "patched": 0, "skipped": skipped, "errors": 0}

    patched = 0
    errors  = 0

    for batch_docs in chunk(to_patch, batch_size):
        if dry_run:
            for doc in batch_docs:
                logger.info("[DRY-RUN] Would patch %s → section_id=%s", doc.id, section_id)
            patched += len(batch_docs)
            continue

        # Firestore batched write
        batch = fs.batch()
        for doc in batch_docs:
            doc_ref = col_ref.document(doc.id)
            batch.update(doc_ref, {
                "section_id": section_id,
                "migrated_at": datetime.now().isoformat(),
                "migration_note": (
                    "Backfilled by add_section_to_attendance.py — "
                    "default section assigned."
                ),
            })
            if verbose:
                logger.info("PATCH %s → section_id=%s", doc.id, section_id)

        try:
            batch.commit()
            patched += len(batch_docs)
            logger.info("Committed batch of %d documents.", len(batch_docs))
        except Exception as exc:
            errors += len(batch_docs)
            logger.error("Batch commit failed: %s", exc)
        # Brief pause to avoid Firestore rate limits on large collections
        time.sleep(0.1)

    return {"total": total, "patched": patched, "skipped": skipped, "errors": errors}


# ── also patch timetable / period documents ────────────────────────────────────

def migrate_periods(
    client: FirebaseClient,
    section_id: str,
    batch_size: int,
    dry_run: bool,
    verbose: bool,
) -> Dict[str, int]:
    """
    Stamp any timetable period documents that are missing section_id.

    This is a best-effort pass; periods without a class_id are also stamped
    so get_section_timetable() returns them.
    """
    try:
        fs = client._require_fs()
    except RuntimeError:
        logger.warning("Firestore unavailable — skipping period migration.")
        return {"total": 0, "patched": 0, "skipped": 0, "errors": 0}

    col_ref = fs.collection("periods")
    all_docs = list(col_ref.stream())
    total = len(all_docs)
    to_patch = [d for d in all_docs if not (d.to_dict() or {}).get("section_id", "").strip()]
    skipped = total - len(to_patch)

    logger.info(
        "Periods: %d total, %d to patch, %d skip.", total, len(to_patch), skipped
    )

    patched = errors = 0
    for batch_docs in chunk(to_patch, batch_size):
        if dry_run:
            for doc in batch_docs:
                logger.info("[DRY-RUN] Would patch period %s → section_id=%s", doc.id, section_id)
            patched += len(batch_docs)
            continue

        batch = fs.batch()
        for doc in batch_docs:
            batch.update(col_ref.document(doc.id), {
                "section_id":      section_id,
                "migrated_at":     datetime.now().isoformat(),
            })
            if verbose:
                logger.info("PATCH period %s → section_id=%s", doc.id, section_id)
        try:
            batch.commit()
            patched += len(batch_docs)
        except Exception as exc:
            errors += len(batch_docs)
            logger.error("Period batch commit failed: %s", exc)
        time.sleep(0.1)

    return {"total": total, "patched": patched, "skipped": skipped, "errors": errors}


# ── entrypoint ─────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill existing attendance (and period) records with a section_id. "
            "Also seeds Course, Section, Enrollment, and CourseAssignment documents."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the migration without writing any data.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=MAX_BATCH_SIZE,
        metavar="N",
        help=f"Firestore batch commit size (default: {MAX_BATCH_SIZE}, max: 500).",
    )
    parser.add_argument(
        "--default-section",
        default=DEFAULT_SECTION_NAME,
        metavar="NAME",
        help=f"Section name to stamp (default: {DEFAULT_SECTION_NAME}).",
    )
    parser.add_argument(
        "--section-id",
        default=None,
        metavar="ID",
        help=(
            "Override the full section_id (default: auto-derived from "
            "--default-section, semester, and year)."
        ),
    )
    parser.add_argument(
        "--semester",
        type=int,
        default=DEFAULT_SEMESTER,
        help=f"Semester number for the default section (default: {DEFAULT_SEMESTER}).",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_YEAR,
        help=f"Academic year for the default section (default: {DEFAULT_YEAR}).",
    )
    parser.add_argument(
        "--skip-periods",
        action="store_true",
        help="Skip patching period/timetable documents.",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip creating Course / Section / Enrollment / CourseAssignment documents.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print each document ID as it is processed.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if args.batch_size > 500:
        logger.warning(
            "batch-size %d exceeds Firestore maximum of 500 — clamping to 400.",
            args.batch_size,
        )
        args.batch_size = MAX_BATCH_SIZE

    section_name = args.default_section
    section_id   = args.section_id or build_section_id(
        section_name, args.semester, args.year
    )

    logger.info("=" * 60)
    logger.info("Attendance section migration")
    logger.info("  Default section : %s", section_name)
    logger.info("  section_id      : %s", section_id)
    logger.info("  Batch size      : %d", args.batch_size)
    logger.info("  Dry run         : %s", args.dry_run)
    logger.info("=" * 60)

    # ── connect ────────────────────────────────────────────────────────────────
    try:
        client = FirebaseClient()
    except Exception as exc:
        sys.exit(f"[ERROR] Firebase connection failed: {exc}")

    start = time.time()

    # ── 1. Seed reference data ─────────────────────────────────────────────────
    if not args.skip_seed:
        logger.info("--- Seeding reference data ---")
        seed_course(client, DEFAULT_COURSE_ID, args.dry_run)
        seed_section(
            client,
            section_id,
            section_name,
            DEFAULT_COURSE_ID,
            args.semester,
            args.year,
            args.dry_run,
        )
        seed_enrollments(client, section_id, args.dry_run)
        seed_course_assignment(client, section_id, args.dry_run)
    else:
        logger.info("--- Skipping seed (--skip-seed) ---")

    # ── 2. Patch attendance ────────────────────────────────────────────────────
    logger.info("--- Patching attendance collection ---")
    att_summary = migrate_attendance(
        client,
        section_id,
        args.batch_size,
        args.dry_run,
        args.verbose,
    )

    # ── 3. Patch periods ───────────────────────────────────────────────────────
    per_summary = {"total": 0, "patched": 0, "skipped": 0, "errors": 0}
    if not args.skip_periods:
        logger.info("--- Patching periods (timetable) collection ---")
        per_summary = migrate_periods(
            client,
            section_id,
            args.batch_size,
            args.dry_run,
            args.verbose,
        )
    else:
        logger.info("--- Skipping periods (--skip-periods) ---")

    elapsed = time.time() - start

    # ── summary ────────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("Migration complete%s  (%.1fs)", " [DRY RUN]" if args.dry_run else "", elapsed)
    logger.info("")
    logger.info("Attendance")
    logger.info("  Total docs   : %d", att_summary["total"])
    logger.info("  Patched      : %d", att_summary["patched"])
    logger.info("  Skipped      : %d", att_summary["skipped"])
    logger.info("  Errors       : %d", att_summary["errors"])
    logger.info("")
    logger.info("Periods")
    logger.info("  Total docs   : %d", per_summary["total"])
    logger.info("  Patched      : %d", per_summary["patched"])
    logger.info("  Skipped      : %d", per_summary["skipped"])
    logger.info("  Errors       : %d", per_summary["errors"])
    logger.info("=" * 60)

    total_errors = att_summary["errors"] + per_summary["errors"]
    if total_errors:
        logger.error(
            "%d batch(es) failed. Re-run the script to retry — already-patched "
            "records are safely skipped.",
            total_errors,
        )
        sys.exit(1)

    if args.dry_run:
        logger.info(
            "Dry run finished. Re-run without --dry-run to apply changes."
        )


if __name__ == "__main__":
    main()
