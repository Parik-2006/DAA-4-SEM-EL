"""
schemas/enrollment_schemas.py
─────────────────────────────────────────────────────────────────────────────
Pydantic models for the multi-photo enrollment endpoint.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Request ──────────────────────────────────────────────────────────────────

class EnrollmentMetadata(BaseModel):
    """Optional contextual metadata attached to an enrollment session."""
    device_id: Optional[str] = Field(None, description="Device that captured the images.")
    location:  Optional[str] = Field(None, description="Physical location label.")


# ── Response ─────────────────────────────────────────────────────────────────

class EnrollmentResponse(BaseModel):
    """Returned by POST /user/enroll/{user_id} on success."""
    success:       bool
    user_id:       str
    sample_count:  int   = Field(..., description="Number of images that yielded valid embeddings.")
    centroid_dim:  int   = Field(..., description="Dimensionality of the stored centroid vector.")
    message:       str


class EnrollmentStatsResponse(BaseModel):
    """Returned by GET /user/enroll/{user_id}/stats."""
    user_id:       str
    sample_count:  int
    centroid_dim:  int
    enrolled_at:   Optional[str]
    device_id:     Optional[str]
    location:      Optional[str]