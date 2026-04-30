"""
csv_parser.py
-------------
Utilities for parsing and validating attendance-system CSV files.

Two parsers are exposed:
    parse_timetable_csv(file_bytes)  ->  ParseResult
    parse_roster_csv(file_bytes)     ->  ParseResult

Both return a ParseResult dataclass so callers can branch on `.ok` before
accessing `.rows` or `.errors`.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

TIMETABLE_REQUIRED_COLUMNS: set[str] = {
    "day",
    "start_time",
    "end_time",
    "course_code",
    "course_name",
    "faculty_id",
    "class_id",
}

ROSTER_REQUIRED_COLUMNS: set[str] = {
    "student_id",
    "name",
    "email",
    "class_id",
}

VALID_DAYS: set[str] = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    # common abbreviations
    "mon", "tue", "wed", "thu", "fri", "sat", "sun",
}

TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RowError:
    row: int            # 1-indexed (header is row 0)
    column: str
    value: str
    message: str

    def to_dict(self) -> dict:
        return {
            "row": self.row,
            "column": self.column,
            "value": self.value,
            "message": self.message,
        }


@dataclass
class ParseResult:
    ok: bool
    rows: list[dict] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)
    total_rows: int = 0
    valid_row_count: int = 0
    invalid_row_count: int = 0

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "total_rows": self.total_rows,
            "valid_row_count": self.valid_row_count,
            "invalid_row_count": self.invalid_row_count,
            "rows": self.rows,
            "errors": [e.to_dict() for e in self.errors],
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _decode_bytes(file_bytes: bytes) -> str:
    """Try UTF-8 then latin-1 decoding."""
    try:
        return file_bytes.decode("utf-8-sig")   # strips BOM if present
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1")


def _check_headers(
    actual: list[str],
    required: set[str],
) -> list[str]:
    """Return list of missing required columns (lowercased comparison)."""
    actual_lower = {c.strip().lower() for c in actual}
    return sorted(required - actual_lower)


def _normalise_row(row: dict) -> dict:
    """Strip whitespace from all keys and values."""
    return {k.strip().lower(): str(v).strip() for k, v in row.items()}


def _validate_time(value: str) -> bool:
    """Return True for valid HH:MM or H:MM format."""
    if not TIME_RE.match(value):
        return False
    try:
        datetime.strptime(value, "%H:%M")
        return True
    except ValueError:
        return False


def _times_end_after_start(start: str, end: str) -> bool:
    """Return True when end > start (both validated HH:MM)."""
    s = datetime.strptime(start, "%H:%M")
    e = datetime.strptime(end, "%H:%M")
    return e > s


# ---------------------------------------------------------------------------
# Timetable CSV parser
# ---------------------------------------------------------------------------

def parse_timetable_csv(file_bytes: bytes) -> ParseResult:
    """
    Parse a timetable CSV file.

    Expected columns (case-insensitive, order-independent):
        day, start_time, end_time, course_code, course_name, faculty_id, class_id

    Per-row validations:
    - ``day``        : must be a recognised weekday name / abbreviation.
    - ``start_time`` : HH:MM or H:MM.
    - ``end_time``   : HH:MM or H:MM; must be later than start_time.
    - ``course_code``: non-empty.
    - ``course_name``: non-empty.
    - ``faculty_id`` : non-empty.
    - ``class_id``   : non-empty.

    Parameters
    ----------
    file_bytes : bytes
        Raw content of the uploaded CSV file.

    Returns
    -------
    ParseResult
    """
    text = _decode_bytes(file_bytes)
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        return ParseResult(
            ok=False,
            errors=[RowError(row=0, column="header", value="", message="CSV file is empty or has no header row.")]
        )

    missing_cols = _check_headers(list(reader.fieldnames), TIMETABLE_REQUIRED_COLUMNS)
    if missing_cols:
        return ParseResult(
            ok=False,
            errors=[
                RowError(
                    row=0,
                    column=col,
                    value="",
                    message=f"Required column '{col}' is missing from CSV header.",
                )
                for col in missing_cols
            ],
        )

    rows: list[dict] = []
    errors: list[RowError] = []
    total = 0

    for raw_row in reader:
        total += 1
        row_num = total + 1   # +1 because header is line 1
        row = _normalise_row(raw_row)
        row_errors: list[RowError] = []

        # --- day ---
        day = row.get("day", "")
        if not day:
            row_errors.append(RowError(row_num, "day", day, "day is required."))
        elif day.lower() not in VALID_DAYS:
            row_errors.append(
                RowError(row_num, "day", day, f"'{day}' is not a recognised weekday.")
            )

        # --- start_time ---
        start_time = row.get("start_time", "")
        if not start_time:
            row_errors.append(RowError(row_num, "start_time", start_time, "start_time is required."))
        elif not _validate_time(start_time):
            row_errors.append(
                RowError(row_num, "start_time", start_time, "start_time must be HH:MM format.")
            )

        # --- end_time ---
        end_time = row.get("end_time", "")
        if not end_time:
            row_errors.append(RowError(row_num, "end_time", end_time, "end_time is required."))
        elif not _validate_time(end_time):
            row_errors.append(
                RowError(row_num, "end_time", end_time, "end_time must be HH:MM format.")
            )
        elif _validate_time(start_time) and not _times_end_after_start(start_time, end_time):
            row_errors.append(
                RowError(
                    row_num, "end_time", end_time,
                    f"end_time '{end_time}' must be after start_time '{start_time}'."
                )
            )

        # --- string fields ---
        for col in ("course_code", "course_name", "faculty_id", "class_id"):
            val = row.get(col, "")
            if not val:
                row_errors.append(RowError(row_num, col, val, f"{col} is required."))

        if row_errors:
            errors.extend(row_errors)
        else:
            rows.append(
                {
                    "row": row_num,
                    "day": row["day"].lower(),
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "course_code": row["course_code"].upper(),
                    "course_name": row["course_name"],
                    "faculty_id": row["faculty_id"],
                    "class_id": row["class_id"],
                }
            )

    invalid = len({e.row for e in errors})  # unique rows with errors
    valid = total - invalid

    return ParseResult(
        ok=len(errors) == 0,
        rows=rows,
        errors=errors,
        total_rows=total,
        valid_row_count=valid,
        invalid_row_count=invalid,
    )


# ---------------------------------------------------------------------------
# Roster CSV parser
# ---------------------------------------------------------------------------

def parse_roster_csv(file_bytes: bytes) -> ParseResult:
    """
    Parse a student roster CSV file.

    Expected columns (case-insensitive, order-independent):
        student_id, name, email, class_id

    Per-row validations:
    - ``student_id``: non-empty; alphanumeric with hyphens/underscores.
    - ``name``       : non-empty.
    - ``email``      : valid email address format.
    - ``class_id``   : non-empty.

    Batch validations:
    - Duplicate student_id values within the file.
    - Duplicate email values within the file.

    Parameters
    ----------
    file_bytes : bytes
        Raw content of the uploaded CSV file.

    Returns
    -------
    ParseResult
    """
    ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")

    text = _decode_bytes(file_bytes)
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        return ParseResult(
            ok=False,
            errors=[RowError(row=0, column="header", value="", message="CSV file is empty or has no header row.")]
        )

    missing_cols = _check_headers(list(reader.fieldnames), ROSTER_REQUIRED_COLUMNS)
    if missing_cols:
        return ParseResult(
            ok=False,
            errors=[
                RowError(row=0, column=col, value="", message=f"Required column '{col}' is missing.")
                for col in missing_cols
            ],
        )

    rows: list[dict] = []
    errors: list[RowError] = []
    seen_ids: dict[str, int] = {}
    seen_emails: dict[str, int] = {}
    total = 0

    for raw_row in reader:
        total += 1
        row_num = total + 1
        row = _normalise_row(raw_row)
        row_errors: list[RowError] = []

        sid = row.get("student_id", "")
        name = row.get("name", "")
        email = row.get("email", "").lower()
        class_id = row.get("class_id", "")

        # --- student_id ---
        if not sid:
            row_errors.append(RowError(row_num, "student_id", sid, "student_id is required."))
        elif not ID_RE.match(sid):
            row_errors.append(
                RowError(row_num, "student_id", sid,
                         "student_id must be alphanumeric (hyphens and underscores allowed).")
            )
        elif sid in seen_ids:
            row_errors.append(
                RowError(row_num, "student_id", sid,
                         f"Duplicate student_id (first occurrence on row {seen_ids[sid]}).")
            )
        else:
            seen_ids[sid] = row_num

        # --- name ---
        if not name:
            row_errors.append(RowError(row_num, "name", name, "name is required."))

        # --- email ---
        if not email:
            row_errors.append(RowError(row_num, "email", email, "email is required."))
        elif not EMAIL_RE.match(email):
            row_errors.append(
                RowError(row_num, "email", email, f"'{email}' is not a valid email address.")
            )
        elif email in seen_emails:
            row_errors.append(
                RowError(row_num, "email", email,
                         f"Duplicate email (first occurrence on row {seen_emails[email]}).")
            )
        else:
            seen_emails[email] = row_num

        # --- class_id ---
        if not class_id:
            row_errors.append(RowError(row_num, "class_id", class_id, "class_id is required."))

        if row_errors:
            errors.extend(row_errors)
        else:
            rows.append(
                {
                    "row": row_num,
                    "student_id": sid,
                    "name": name,
                    "email": email,
                    "class_id": class_id,
                }
            )

    invalid = len({e.row for e in errors})
    valid = total - invalid

    return ParseResult(
        ok=len(errors) == 0,
        rows=rows,
        errors=errors,
        total_rows=total,
        valid_row_count=valid,
        invalid_row_count=invalid,
    )
