"""
Student service layer — business logic for the student-facing API.

All public methods are async and return plain dicts/lists suitable for
direct serialisation by FastAPI.  Database I/O is done through the shared
FirebaseClient helper that wraps the Firebase Admin SDK.

Colour conventions used throughout (also defined in attendance_schemas.py):
    present  →  #22C55E  (green-500)
    absent   →  #EF4444  (red-500)
    late     →  #F59E0B  (amber-500)
    pending  →  #94A3B8  (slate-400)
    warning  →  #F97316  (orange-500)

Attendance threshold:
    < 75 %  → danger  (red)
    75–85 % → warning (yellow)
    > 85 %  → safe    (green)
"""

from __future__ import annotations

import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from database.firebase_client import FirebaseClient

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

ATTENDANCE_DANGER_THRESHOLD = 75.0
ATTENDANCE_WARNING_THRESHOLD = 85.0

STATUS_COLORS: Dict[str, str] = {
    "present": "#22C55E",
    "absent":  "#EF4444",
    "late":    "#F59E0B",
    "pending": "#94A3B8",
}

ATTENDANCE_BAND_COLORS: Dict[str, str] = {
    "safe":    "#22C55E",
    "warning": "#F59E0B",
    "danger":  "#EF4444",
}

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# A palette of 12 distinct colours used to tint courses in the timetable
COURSE_PALETTE: List[str] = [
    "#6366F1", "#EC4899", "#14B8A6", "#F59E0B",
    "#8B5CF6", "#10B981", "#F97316", "#3B82F6",
    "#EF4444", "#06B6D4", "#84CC16", "#D946EF",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _course_color(course_code: str, palette: List[str] = COURSE_PALETTE) -> str:
    """Deterministically assign a colour from the palette to a course code."""
    return palette[hash(course_code) % len(palette)]


def _attendance_band(pct: float) -> str:
    if pct >= ATTENDANCE_WARNING_THRESHOLD:
        return "safe"
    if pct >= ATTENDANCE_DANGER_THRESHOLD:
        return "warning"
    return "danger"


def _minutes_since_midnight(t: str) -> int:
    """'HH:MM' → minutes since midnight."""
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _now_minutes() -> int:
    n = datetime.now()
    return n.hour * 60 + n.minute


def _today_str() -> str:
    return date.today().isoformat()


def _today_weekday() -> int:
    """0 = Monday … 6 = Sunday, matching period schema."""
    return date.today().weekday()


# ── Service class ──────────────────────────────────────────────────────────────

class StudentService:
    """Encapsulates all student-facing business logic."""

    # ------------------------------------------------------------------
    # Internal Firebase helpers
    # ------------------------------------------------------------------

    def _fb(self) -> FirebaseClient:
        return FirebaseClient()

    def _get(self, path: str) -> Any:
        return self._fb().get_reference(path).get()

    # ------------------------------------------------------------------
    # Attendance data helpers
    # ------------------------------------------------------------------

    def _fetch_all_attendance(self) -> Dict[str, Any]:
        """Return the entire attendance subtree (keyed by date)."""
        return self._get("attendance") or {}

    def _student_attendance_records(
        self,
        student_id: str,
        course_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return all attendance records for *student_id*, optionally filtered
        by course, start_date, and end_date (all inclusive).
        """
        all_dates = self._fetch_all_attendance()
        records: List[Dict[str, Any]] = []

        for d in sorted(all_dates.keys(), reverse=True):
            if start_date and d < start_date:
                continue
            if end_date and d > end_date:
                continue
            day_data = all_dates[d]
            if not isinstance(day_data, dict):
                continue
            if student_id not in day_data:
                continue
            raw = day_data[student_id]
            if not isinstance(raw, dict):
                continue
            record = dict(raw)
            record["date"] = d
            if course_id and record.get("course_code") != course_id:
                continue
            records.append(record)

        return records

    # ------------------------------------------------------------------
    # Period / timetable helpers
    # ------------------------------------------------------------------

    def _fetch_periods(self, class_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all period documents from Firebase.
        If *class_id* is given, filter to that class only.
        """
        raw = self._get("periods") or {}
        periods: List[Dict[str, Any]] = []
        for pid, doc in raw.items():
            if not isinstance(doc, dict):
                continue
            if class_id and doc.get("class_id") != class_id:
                continue
            doc.setdefault("period_id", pid)
            periods.append(doc)
        return periods

    def _student_class_id(self, student_id: str) -> Optional[str]:
        """Look up the class_id FK stored on the student document."""
        student_doc = self._get(f"students/{student_id}")
        if isinstance(student_doc, dict):
            return student_doc.get("class_id")
        return None

    def _fetch_faculty_name(self, faculty_id: str) -> str:
        """Return faculty display name, falling back to faculty_id."""
        if not faculty_id:
            return "Unknown"
        doc = self._get(f"faculty/{faculty_id}")
        if isinstance(doc, dict):
            return doc.get("name", faculty_id)
        return faculty_id

    # ------------------------------------------------------------------
    # Active period detection
    # ------------------------------------------------------------------

    def _detect_active_period(
        self, periods: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Return the period currently in progress (if any) based on wall-clock
        time and day-of-week.  Returns None between classes.
        """
        today_dow = _today_weekday()
        now_min = _now_minutes()
        for p in periods:
            if p.get("day_of_week") != today_dow:
                continue
            start_min = _minutes_since_midnight(p.get("start_time", "00:00"))
            end_min   = _minutes_since_midnight(p.get("end_time",   "00:00"))
            if start_min <= now_min < end_min:
                return p
        return None

    def _period_status(
        self,
        period: Dict[str, Any],
        today_records: List[Dict[str, Any]],
        active_period: Optional[Dict[str, Any]],
    ) -> str:
        """
        Determine the attendance status for a single today-period.

        Logic:
        - If the period is currently active → 'pending'
        - If a matching attendance record exists with status present/late → use it
        - If the period end time has passed and no record → 'absent'
        - If the period hasn't started yet → 'pending'
        """
        now_min   = _now_minutes()
        start_min = _minutes_since_midnight(period.get("start_time", "00:00"))
        end_min   = _minutes_since_midnight(period.get("end_time",   "00:00"))
        course    = period.get("course_code", "")

        # Check existing record for this course today
        for rec in today_records:
            if rec.get("course_code") == course:
                return rec.get("status", "present")

        if active_period and active_period.get("period_id") == period.get("period_id"):
            return "pending"
        if now_min >= end_min:
            return "absent"
        return "pending"

    # ------------------------------------------------------------------
    # Public: calculate_attendance_percentage
    # ------------------------------------------------------------------

    def calculate_attendance_percentage(
        self,
        student_id: str,
        course_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Return overall (or per-course) attendance percentage plus counts.

        Returns
        -------
        {
            "percentage": float,
            "present": int,
            "absent": int,
            "late": int,
            "total": int,
            "band": "safe"|"warning"|"danger",
            "color": hex_str,
        }
        """
        records = self._student_attendance_records(student_id, course_id=course_id)
        present = sum(1 for r in records if r.get("status") in ("present",))
        late    = sum(1 for r in records if r.get("status") == "late")
        absent  = sum(1 for r in records if r.get("status") == "absent")
        total   = present + late + absent

        # "late" counts as attended for percentage purposes
        attended = present + late
        pct = round(attended / total * 100, 2) if total else 0.0
        band = _attendance_band(pct)

        return {
            "percentage": pct,
            "present": present,
            "late": late,
            "absent": absent,
            "total": total,
            "band": band,
            "color": ATTENDANCE_BAND_COLORS[band],
        }

    # ------------------------------------------------------------------
    # Public: get_weekly_timetable
    # ------------------------------------------------------------------

    def get_weekly_timetable(self, student_id: str) -> Dict[str, Any]:
        """
        Return a full weekly timetable grid for the student.

        Structure
        ---------
        {
            "class_id": str,
            "days": {
                "Monday": [ { period fields + faculty_name + color } ],
                ...
            },
            "all_courses": { course_code: { name, color } },
        }
        """
        class_id = self._student_class_id(student_id)
        periods  = self._fetch_periods(class_id=class_id)

        days: Dict[str, List[Dict[str, Any]]] = {d: [] for d in DAY_NAMES}
        all_courses: Dict[str, Dict[str, str]] = {}

        for p in periods:
            dow = p.get("day_of_week", -1)
            if dow < 0 or dow > 6:
                continue
            day_name = DAY_NAMES[dow]
            faculty_name = self._fetch_faculty_name(p.get("faculty_id", ""))
            color = _course_color(p.get("course_code", ""))

            card = {
                "period_id":    p.get("period_id"),
                "start_time":   p.get("start_time"),
                "end_time":     p.get("end_time"),
                "duration_minutes": p.get("duration_minutes"),
                "course_code":  p.get("course_code"),
                "course_name":  p.get("course_name"),
                "faculty_id":   p.get("faculty_id"),
                "faculty_name": faculty_name,
                "is_lab_class": p.get("is_lab_class", False),
                "room":         p.get("room_override"),
                "color":        color,
            }
            days[day_name].append(card)
            all_courses[p.get("course_code", "")] = {
                "name": p.get("course_name", ""),
                "color": color,
            }

        # Sort each day's list by start_time
        for day_name in days:
            days[day_name].sort(key=lambda x: x.get("start_time", ""))

        return {
            "class_id":    class_id,
            "days":        days,
            "all_courses": all_courses,
        }

    # ------------------------------------------------------------------
    # Public: get_low_attendance_courses
    # ------------------------------------------------------------------

    def get_low_attendance_courses(self, student_id: str) -> List[Dict[str, Any]]:
        """
        Return list of course-wise attendance dicts for courses below or
        near the 75 % threshold, sorted by percentage ascending.

        Each dict:
        {
            course_code, course_name, percentage, present, absent, late,
            total, band, color, required_to_reach_75, is_critical
        }
        """
        timetable = self.get_weekly_timetable(student_id)
        all_courses = timetable.get("all_courses", {})
        results: List[Dict[str, Any]] = []

        for course_code, course_meta in all_courses.items():
            stats = self.calculate_attendance_percentage(student_id, course_id=course_code)
            total = stats["total"]
            attended = stats["present"] + stats["late"]
            pct = stats["percentage"]

            # How many consecutive classes must be attended to reach 75 %?
            required = 0
            if pct < ATTENDANCE_DANGER_THRESHOLD and total > 0:
                # solve: (attended + x) / (total + x) >= 0.75
                # x >= (0.75*total - attended) / 0.25
                x = (0.75 * total - attended) / 0.25
                required = max(0, int(x) + (1 if x % 1 else 0))

            results.append({
                "course_code": course_code,
                "course_name": course_meta.get("name", ""),
                "color":       course_meta.get("color", "#6366F1"),
                "percentage":  pct,
                "present":     stats["present"],
                "late":        stats["late"],
                "absent":      stats["absent"],
                "total":       total,
                "band":        stats["band"],
                "band_color":  ATTENDANCE_BAND_COLORS[stats["band"]],
                "required_consecutive_to_reach_75": required,
                "is_critical": pct < ATTENDANCE_DANGER_THRESHOLD,
            })

        results.sort(key=lambda x: x["percentage"])
        return results

    # ------------------------------------------------------------------
    # Public: build_dashboard_data
    # ------------------------------------------------------------------

    def build_dashboard_data(self, student_id: str) -> Dict[str, Any]:
        """
        Aggregate everything needed for the student dashboard in one call.

        Returns
        -------
        {
            today_date, day_name,
            active_period | None,
            periods_today: [ { ...card, status, status_color, countdown_seconds? } ],
            summary: { total_periods, present, absent, late, pending },
            overall_attendance: { percentage, ... },
        }
        """
        today_str = _today_str()
        today_dow = _today_weekday()
        day_name  = DAY_NAMES[today_dow]

        class_id    = self._student_class_id(student_id)
        all_periods = self._fetch_periods(class_id=class_id)
        today_periods = [
            p for p in all_periods
            if p.get("day_of_week") == today_dow
        ]
        today_periods.sort(key=lambda p: p.get("start_time", ""))

        # Today's existing attendance records
        all_dates = self._fetch_all_attendance()
        today_records: List[Dict[str, Any]] = []
        if today_str in all_dates and isinstance(all_dates[today_str], dict):
            student_today = all_dates[today_str].get(student_id)
            if isinstance(student_today, dict):
                today_records = [student_today]
            elif isinstance(student_today, list):
                today_records = student_today

        active_period = self._detect_active_period(today_periods)

        period_cards: List[Dict[str, Any]] = []
        summary_counts = {"total": 0, "present": 0, "absent": 0, "late": 0, "pending": 0}

        now_min = _now_minutes()

        for p in today_periods:
            status     = self._period_status(p, today_records, active_period)
            fac_name   = self._fetch_faculty_name(p.get("faculty_id", ""))
            color      = _course_color(p.get("course_code", ""))
            end_min    = _minutes_since_midnight(p.get("end_time", "00:00"))
            countdown  = None
            if status == "pending" and active_period and \
                    active_period.get("period_id") == p.get("period_id"):
                countdown = max(0, (end_min - now_min) * 60)

            card = {
                "period_id":    p.get("period_id"),
                "start_time":   p.get("start_time"),
                "end_time":     p.get("end_time"),
                "duration_minutes": p.get("duration_minutes"),
                "course_code":  p.get("course_code"),
                "course_name":  p.get("course_name"),
                "faculty_id":   p.get("faculty_id"),
                "faculty_name": fac_name,
                "is_lab_class": p.get("is_lab_class", False),
                "room":         p.get("room_override"),
                "course_color": color,
                "status":       status,
                "status_color": STATUS_COLORS.get(status, STATUS_COLORS["pending"]),
                "is_active":    active_period is not None and
                                active_period.get("period_id") == p.get("period_id"),
                "countdown_seconds": countdown,
            }
            period_cards.append(card)
            summary_counts["total"] += 1
            summary_counts[status]  += 1

        overall = self.calculate_attendance_percentage(student_id)

        active_card = None
        if active_period:
            active_card = next(
                (c for c in period_cards if c["period_id"] == active_period.get("period_id")),
                None,
            )

        return {
            "today_date":         today_str,
            "day_name":           day_name,
            "active_period":      active_card,
            "periods_today":      period_cards,
            "summary":            summary_counts,
            "overall_attendance": overall,
        }

    # ------------------------------------------------------------------
    # Public: get_attendance_history (paginated + filtered)
    # ------------------------------------------------------------------

    def get_attendance_history(
        self,
        student_id: str,
        page: int = 1,
        page_size: int = 20,
        course_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Return paginated attendance history with faculty name enrichment.
        """
        records = self._student_attendance_records(
            student_id,
            course_id=course_id,
            start_date=start_date,
            end_date=end_date,
        )

        total = len(records)
        start_idx = (page - 1) * page_size
        end_idx   = start_idx + page_size
        page_records = records[start_idx:end_idx]

        enriched: List[Dict[str, Any]] = []
        for rec in page_records:
            marked_by_id   = rec.get("marked_by") or rec.get("camera_id", "system")
            marked_by_name = self._fetch_faculty_name(marked_by_id) \
                if marked_by_id and not marked_by_id.startswith("cam") \
                else marked_by_id
            status = rec.get("status", "present")
            enriched.append({
                **rec,
                "marked_by_name": marked_by_name,
                "status_color":   STATUS_COLORS.get(status, STATUS_COLORS["present"]),
            })

        return {
            "page":        page,
            "page_size":   page_size,
            "total":       total,
            "total_pages": max(1, -(-total // page_size)),  # ceiling division
            "records":     enriched,
        }

    # ------------------------------------------------------------------
    # Public: get_attendance_summary
    # ------------------------------------------------------------------

    def get_attendance_summary(self, student_id: str) -> Dict[str, Any]:
        """
        Return overall + course-wise attendance breakdown for the summary card.
        """
        overall   = self.calculate_attendance_percentage(student_id)
        course_breakdown = self.get_low_attendance_courses(student_id)

        # Sort for display: alphabetical within band groups
        by_band: Dict[str, List] = {"danger": [], "warning": [], "safe": []}
        for c in course_breakdown:
            by_band[c["band"]].append(c)

        return {
            "overall":         overall,
            "course_breakdown": course_breakdown,
            "has_critical":    any(c["is_critical"] for c in course_breakdown),
            "critical_courses": [c for c in course_breakdown if c["is_critical"]],
        }

    # ------------------------------------------------------------------
    # Public: get_warnings
    # ------------------------------------------------------------------

    def get_warnings(self, student_id: str) -> Dict[str, Any]:
        """
        Return attendance warnings.  Courses are colour-coded by band.
        has_critical_warning is True if any course is below 75 %.
        """
        courses   = self.get_low_attendance_courses(student_id)
        critical  = [c for c in courses if c["band"] == "danger"]
        warning   = [c for c in courses if c["band"] == "warning"]

        messages: List[str] = []
        if critical:
            names = ", ".join(c["course_code"] for c in critical)
            messages.append(
                f"⚠ CRITICAL: You are below 75% attendance in: {names}. "
                "You may be debarred from the examination."
            )
        if warning:
            names = ", ".join(c["course_code"] for c in warning)
            messages.append(
                f"Your attendance in {names} is between 75–85%. "
                "Maintain regular attendance to stay above the threshold."
            )

        return {
            "has_critical_warning": bool(critical),
            "messages":             messages,
            "courses":              courses,
            "legend": {
                "safe":    {"label": "> 85%",   "color": ATTENDANCE_BAND_COLORS["safe"]},
                "warning": {"label": "75–85%",  "color": ATTENDANCE_BAND_COLORS["warning"]},
                "danger":  {"label": "< 75%",   "color": ATTENDANCE_BAND_COLORS["danger"]},
            },
        }
