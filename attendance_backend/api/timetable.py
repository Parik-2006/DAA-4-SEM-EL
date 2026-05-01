"""
api/timetable.py
─────────────────────────────────────────────────────────────────────────────
FastAPI router that exposes all timetable-related endpoints.

Endpoints
---------
POST   /api/v1/timetable/upload             Upload CSV or JSON timetable
GET    /api/v1/timetable/current-period     Get currently active period
GET    /api/v1/timetable/{class_id}         Fetch a class timetable
PUT    /api/v1/timetable/{period_id}        Update a period
DELETE /api/v1/timetable/{period_id}        Soft-delete a period
GET    /api/v1/timetable/{period_id}/audit  View audit log for a period

Notes
-----
* ``/current-period`` is declared BEFORE ``/{class_id}`` so FastAPI does not
  route "current-period" as a class_id path parameter.
* CSV upload accepts ``multipart/form-data`` with a single ``file`` field.
* JSON bulk upload is available via the same endpoint with
  ``Content-Type: application/json`` body (list of period objects).
* All mutating endpoints accept an optional ``actor_id`` query param for audit
  logging (default: "api").
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Body,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse

from config.constants import (
    ATTENDANCE_WINDOW_MINUTES,
    LATE_THRESHOLD_MINUTES,
    NOTIFICATION_TRIGGER_MINUTES,
)
from services.period_detection_service import get_period_detection_service
from services.timetable_service import get_timetable_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/timetable", tags=["timetable"])

# ── Dependency helpers ─────────────────────────────────────────────────────────

def _require_timetable_service():
    svc = get_timetable_service()
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TimetableService is not initialised. Check server startup.",
        )
    return svc


def _require_detection_service():
    svc = get_period_detection_service()
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PeriodDetectionService is not initialised. Check server startup.",
        )
    return svc


# ══════════════════════════════════════════════════════════════════════════════
# POST /upload  — CSV or JSON timetable upload
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/upload",
    status_code=status.HTTP_200_OK,
    summary="Upload a timetable via CSV file or raw JSON body",
    response_description=(
        "Summary of how many periods were inserted and any validation errors"
    ),
)
async def upload_timetable(
    request: Request,
    file: Optional[UploadFile] = File(None, description="CSV timetable file"),
    actor_id: str = Query("api", description="Who is performing this upload (for audit)"),
    dry_run: bool = Query(
        False,
        description="Validate only — do not write to Firestore",
    ),
    check_overlaps: bool = Query(
        True,
        description="Run overlap detection after parsing",
    ),
):
    """
    Accepts either:

    * ``multipart/form-data`` with a ``file`` field containing a CSV.
    * ``application/json`` body that is a JSON array of period objects.

    CSV required columns: class_id, faculty_id, course_id, day_of_week,
    start_time, end_time

    Optional CSV columns: period_type (default: lecture), room, metadata

    Returns a summary including inserted count, validation errors, and any
    overlap warnings.
    """
    timetable_svc = _require_timetable_service()

    content_type = request.headers.get("content-type", "")

    # ── Determine source: file upload vs JSON body ─────────────────────────────
    if file is not None:
        # CSV upload
        try:
            csv_bytes = await file.read()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not read file: {exc}")

        if not csv_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        valid_rows, parse_errors = timetable_svc.parse_csv(csv_bytes)

    elif "application/json" in content_type:
        # JSON body
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid JSON body: {exc}"
            )
        if not isinstance(body, list):
            raise HTTPException(
                status_code=400,
                detail="JSON body must be an array of period objects.",
            )
        valid_rows, parse_errors = timetable_svc.parse_json(body)

    else:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported media type. "
                "Send multipart/form-data with a CSV file, "
                "or application/json with a list of period objects."
            ),
        )

    # ── Overlap detection (optional) ───────────────────────────────────────────
    overlap_warnings: List[Dict[str, Any]] = []
    if check_overlaps and valid_rows:
        # Group by class_id for overlap analysis
        from collections import defaultdict
        by_class: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in valid_rows:
            by_class[row["class_id"]].append(row)

        for cid, rows in by_class.items():
            overlaps = timetable_svc.detect_overlaps(cid, new_periods=rows)
            if overlaps:
                overlap_warnings.extend(overlaps)

    # ── Dry-run: return analysis without writing ───────────────────────────────
    if dry_run:
        return JSONResponse(
            status_code=200,
            content={
                "dry_run":          True,
                "valid_count":      len(valid_rows),
                "error_count":      len(parse_errors),
                "errors":           parse_errors,
                "overlap_warnings": overlap_warnings,
                "inserted":         0,
            },
        )

    # ── Bail if nothing to insert ──────────────────────────────────────────────
    if not valid_rows:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "No valid periods to insert.",
                "errors":  parse_errors,
            },
        )

    # ── Bulk insert ────────────────────────────────────────────────────────────
    result = timetable_svc.bulk_insert(valid_rows, actor_id=actor_id)

    # ── Invalidate period detection cache ──────────────────────────────────────
    detection_svc = get_period_detection_service()
    if detection_svc:
        detection_svc.force_refresh()

    return JSONResponse(
        status_code=200,
        content={
            "dry_run":          False,
            "valid_count":      len(valid_rows),
            "error_count":      len(parse_errors),
            "errors":           parse_errors[:50],   # cap returned errors
            "overlap_warnings": overlap_warnings,
            **result,   # inserted, failed, error_details
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# GET /current-period  — must be declared BEFORE /{class_id}
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/current-period",
    summary="Get the currently active timetable period",
)
async def get_current_period():
    """
    Returns the period(s) active right now based on the current day and time.

    Reads from the in-memory (or Redis) cache maintained by
    ``PeriodDetectionService``; response is at most 60 seconds stale.

    Response includes:
    * ``primary_period``  — the single authoritative active period
    * ``active_periods``  — all overlapping active periods (if any)
    * ``upcoming_period`` — next period starting within the notification window
    * Per-period annotations: ``attendance_open``, ``is_late_threshold``,
      ``attendance_status_hint``, ``minutes_elapsed``, ``minutes_remaining``

    Configuration (from constants)
    --------------------------------
    * Attendance window  : {ATTENDANCE_WINDOW_MINUTES} min after period end
    * Late threshold     : {LATE_THRESHOLD_MINUTES} min into the period
    * Notification window: {NOTIFICATION_TRIGGER_MINUTES} min before start
    """
    detection_svc = _require_detection_service()
    payload = detection_svc.get_active_period()

    if payload is None:
        # Service has not ticked yet (first 60 s after startup)
        return JSONResponse(
            status_code=200,
            content={
                "is_period_active": False,
                "primary_period":   None,
                "active_periods":   [],
                "upcoming_period":  None,
                "last_check":       None,
                "message":          (
                    "Period detection has not completed its first cycle yet. "
                    "Retry in a few seconds."
                ),
            },
        )

    payload["last_check"] = detection_svc.get_last_check_time()
    payload["config"] = {
        "attendance_window_minutes":    ATTENDANCE_WINDOW_MINUTES,
        "late_threshold_minutes":       LATE_THRESHOLD_MINUTES,
        "notification_trigger_minutes": NOTIFICATION_TRIGGER_MINUTES,
    }
    return JSONResponse(status_code=200, content=payload)


# ══════════════════════════════════════════════════════════════════════════════
# GET /{class_id}  — fetch class timetable
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/{class_id}",
    summary="Fetch the full timetable for a class",
)
async def get_class_timetable(
    class_id: str,
    include_inactive: bool = Query(
        False,
        description="Include soft-deleted (inactive) periods",
    ),
):
    """
    Returns all timetable entries for ``class_id`` sorted by day then
    start_time.

    Overlap warnings are computed on-the-fly and included in the response
    to help administrators identify scheduling conflicts.
    """
    timetable_svc = _require_timetable_service()

    try:
        periods = timetable_svc.get_periods_by_class(
            class_id, include_inactive=include_inactive
        )
    except Exception as exc:
        logger.error("get_class_timetable error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    overlaps = timetable_svc.detect_overlaps(class_id) if periods else []

    return JSONResponse(
        status_code=200,
        content={
            "class_id":       class_id,
            "count":          len(periods),
            "periods":        periods,
            "overlap_count":  len(overlaps),
            "overlaps":       overlaps,
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# PUT /{period_id}  — update a period
# ══════════════════════════════════════════════════════════════════════════════

@router.put(
    "/{period_id}",
    summary="Update a timetable period",
)
async def update_period(
    period_id: str,
    updates: Dict[str, Any] = Body(
        ...,
        examples={
            "default": {
                "summary": "Update fields",
                "value": {
                    "start_time":  "09:30",
                    "end_time":    "10:30",
                    "room":        "B-204",
                    "period_type": "lab",
                },
            }
        },
    ),
    actor_id: str = Query("api", description="User performing the update"),
    reason: Optional[str] = Query(None, description="Reason for the change (stored in audit log)"),
):
    """
    Partially update any fields of a period.  Immutable fields
    (``period_id``, ``created_at``) are silently ignored.

    All changes are recorded in an audit sub-collection under the period
    document.  The ``PeriodDetectionService`` cache is invalidated so the
    next detection cycle picks up the new data immediately.
    """
    timetable_svc = _require_timetable_service()

    try:
        updated = timetable_svc.update_period(
            period_id,
            updates=dict(updates),
            actor_id=actor_id,
            reason=reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("update_period error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    # Invalidate detection cache
    detection_svc = get_period_detection_service()
    if detection_svc:
        detection_svc.force_refresh()

    return JSONResponse(
        status_code=200,
        content={"success": True, "period": updated},
    )


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /{period_id}  — soft-delete a period
# ══════════════════════════════════════════════════════════════════════════════

@router.delete(
    "/{period_id}",
    summary="Soft-delete a timetable period",
)
async def delete_period(
    period_id: str,
    actor_id: str = Query("api", description="User performing the deletion"),
    reason: Optional[str] = Query(
        None,
        description="Reason for deletion (stored in audit log)",
    ),
):
    """
    Soft-deletes the period by setting ``active_status = False``.

    The document is **not** removed from Firestore; historical attendance
    records that reference this period remain valid.

    An audit entry is written and the ``PeriodDetectionService`` cache is
    invalidated immediately.
    """
    timetable_svc = _require_timetable_service()

    try:
        timetable_svc.delete_period(period_id, actor_id=actor_id, reason=reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("delete_period error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    detection_svc = get_period_detection_service()
    if detection_svc:
        detection_svc.force_refresh()

    return JSONResponse(
        status_code=200,
        content={
            "success":   True,
            "period_id": period_id,
            "message":   f"Period {period_id} soft-deleted successfully.",
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# GET /{period_id}/audit  — audit trail
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/{period_id}/audit",
    summary="View the audit trail for a period",
)
async def get_period_audit(period_id: str):
    """
    Returns all audit-log entries for ``period_id``, newest first.

    Each entry records who changed what and when, including the before/after
    values of every modified field.
    """
    timetable_svc = _require_timetable_service()

    # Verify period exists
    period = timetable_svc.get_period(period_id)
    if period is None:
        raise HTTPException(
            status_code=404,
            detail=f"Period '{period_id}' not found.",
        )

    try:
        log_entries = timetable_svc.get_audit_log(period_id)
    except Exception as exc:
        logger.error("get_period_audit error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse(
        status_code=200,
        content={
            "period_id":   period_id,
            "entry_count": len(log_entries),
            "audit_log":   log_entries,
        },
    )
