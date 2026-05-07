"""
models/timetable.py

Core timetable models used by Prompt 2 workflow.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class TimetablePeriod(BaseModel):
    period_id: str = Field(..., min_length=1)
    class_id: str = Field(..., min_length=1)
    faculty_id: str = Field(..., min_length=1)
    course_id: str = Field(..., min_length=1)
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: str
    end_time: str
    period_type: str = "lecture"
    room: Optional[str] = None
    active_status: bool = True

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time(cls, value: str) -> str:
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError("time must be HH:MM")
        hh, mm = int(parts[0]), int(parts[1])
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError("invalid HH:MM value")
        return f"{hh:02d}:{mm:02d}"


class CourseAssignment(BaseModel):
    assignment_id: str = Field(..., min_length=1)
    faculty_id: str = Field(..., min_length=1)
    class_id: str = Field(..., min_length=1)
    course_ids: List[str] = Field(default_factory=list)
    active_status: bool = True
