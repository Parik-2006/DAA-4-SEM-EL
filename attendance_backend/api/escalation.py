"""
api/escalation.py — Secondary-factor escalation endpoints
══════════════════════════════════════════════════════════

Routes
──────
GET  /api/v1/escalation/{escalation_id}
        Poll escalation status (student or teacher).

POST /api/v1/escalation/{escalation_id}/otp/verify
        Student submits their OTP code.

POST /api/v1/escalation/{escalation_id}/approve
        Teacher approves a pending teacher-approval escalation.

POST /api/v1/escalation/{escalation_id}/reject
        Teacher rejects a pending teacher-approval escalation.

POST /api/v1/escalation/trigger   (internal / admin)
        Manually trigger an escalation for a student (testing / override).

Registration
────────────
Add to your FastAPI app (e.g. main.py or app.py):

    from api.escalation import router as escalation_router
    app.include_router(escalation_router)
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from decorators.auth_decorators import get_current_user
from services.auth_service import UserContext
from services.escalation_service import EscalationEvent, get_escalation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/escalation", tags=["escalation"])


# ── Helpers ───────────────────────────────────────────────────────────────────
def _get_firestore():
    try:
        from services.firebase_service import get_firebase_service
        fb = get_firebase_service()
        return getattr(fb, "firestore_db", None) or getattr(fb, "_firestore", None)
    except Exception as exc:
        logger.error("Could not obtain Firestore: %s", exc)
        return None


def _event_to_dict(event: EscalationEvent) -> dict:
    """Serialise EscalationEvent to a JSON-safe dict (never exposes OTP hash)."""
    return {
        "escalation_id": event.escalation_id,
        "student_id": event.student_id,
        "period_id": event.period_id,
        "method": event.method,
        "status": event.status,
        "triggered_at": event.triggered_at,
        "expires_at": event.expires_at,
        "fail_count": event.fail_count,
        "resolved_at": event.resolved_at,
        "resolved_by": event.resolved_by,
        "session_notes": event.session_notes,
    }


# ── Request / response schemas ────────────────────────────────────────────────
class OTPVerifyRequest(BaseModel):
    otp: str = Field(..., min_length=4, max_length=12, description="OTP code")


class TeacherResolveRequest(BaseModel):
    notes: Optional[str] = Field(None, description="Optional notes from teacher")


class ManualTriggerRequest(BaseModel):
    student_id: str
    period_id: str
    method: str = Field("otp", pattern="^(otp|teacher_approval)$")
    trigger_reason: str = "manual"


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/escalation/{escalation_id}
# ══════════════════════════════════════════════════════════════════════════════
@router.get(
    "/{escalation_id}",
    summary="Poll escalation status",
)
async def get_escalation_status(
    escalation_id: str,
    user: UserContext = Depends(get_current_user),
):
    """
    Returns the current state of an escalation record.

    Accessible by the student who owns the escalation, any teacher,
    or an admin.  Students see all fields except OTP hashes (those are
    never returned by any endpoint).
    """
    svc = get_escalation_service(_get_firestore())
    event = svc.get_escalation(escalation_id)

    if event is None:
        raise HTTPException(status_code=404, detail="Escalation not found.")

    # Students may only see their own escalations
    if user.role == "student" and event.student_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    return {"escalation": _event_to_dict(event)}


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/escalation/{escalation_id}/otp/verify
# ══════════════════════════════════════════════════════════════════════════════
@router.post(
    "/{escalation_id}/otp/verify",
    summary="Verify OTP for an escalated face-auth session",
)
async def verify_otp(
    escalation_id: str,
    body: OTPVerifyRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
):
    """
    Student submits the OTP they received (SMS / email / push).

    On success the escalation is marked **approved** and the pipeline
    should proceed to mark attendance.

    On failure the attempt is counted; after `ESCALATION_MAX_OTP_ATTEMPTS`
    wrong submissions the escalation is auto-**rejected**.
    """
    svc = get_escalation_service(_get_firestore())

    # Fetch to permission-check before calling verify
    event = svc.get_escalation(escalation_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Escalation not found.")

    if user.role == "student" and event.student_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    if event.method != "otp":
        raise HTTPException(
            status_code=400,
            detail="This escalation requires teacher approval, not OTP.",
        )

    result = svc.verify_otp(escalation_id, body.otp)

    # Audit log
    try:
        from services.audit_services import get_audit_service
        get_audit_service().log(
            action="ESCALATION_OTP_VERIFY",
            resource="escalation",
            resource_id=escalation_id,
            user=user,
            request=request,
            details={
                "student_id": event.student_id,
                "success": result.success,
                "status": result.status,
            },
            success=result.success,
            error=None if result.success else result.message,
        )
    except Exception:
        pass

    if result.success:
        return {
            "verified": True,
            "status": result.status,
            "message": result.message,
            "escalation_id": escalation_id,
        }

    # Not verified — return 200 with verified=False so the client can show
    # remaining attempts without treating it as an HTTP error.
    return {
        "verified": False,
        "status": result.status,
        "message": result.message,
        "attempts_remaining": result.attempts_remaining,
        "escalation_id": escalation_id,
    }


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/escalation/{escalation_id}/approve
# ══════════════════════════════════════════════════════════════════════════════
@router.post(
    "/{escalation_id}/approve",
    summary="Teacher approves a pending escalation",
)
async def approve_escalation(
    escalation_id: str,
    body: TeacherResolveRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
):
    """
    A teacher (or admin) approves the escalation, allowing the student's
    attendance to be marked despite failed face-auth attempts.

    Only **teacher** and **admin** roles may call this endpoint.
    """
    if user.role not in ("teacher", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Only teachers or admins can approve escalations.",
        )

    svc = get_escalation_service(_get_firestore())
    event = svc.resolve_teacher(
        escalation_id,
        teacher_id=user.user_id,
        approve=True,
        notes=body.notes,
    )

    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Escalation not found or could not be resolved.",
        )

    _audit_resolve(request, user, escalation_id, event, action="ESCALATION_APPROVED")

    return {
        "resolved": True,
        "status": event.status,
        "escalation": _event_to_dict(event),
    }


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/escalation/{escalation_id}/reject
# ══════════════════════════════════════════════════════════════════════════════
@router.post(
    "/{escalation_id}/reject",
    summary="Teacher rejects a pending escalation",
)
async def reject_escalation(
    escalation_id: str,
    body: TeacherResolveRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
):
    """
    A teacher (or admin) rejects the escalation.  The student's attendance
    will NOT be marked for this period.
    """
    if user.role not in ("teacher", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Only teachers or admins can reject escalations.",
        )

    svc = get_escalation_service(_get_firestore())
    event = svc.resolve_teacher(
        escalation_id,
        teacher_id=user.user_id,
        approve=False,
        notes=body.notes,
    )

    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Escalation not found or could not be resolved.",
        )

    _audit_resolve(request, user, escalation_id, event, action="ESCALATION_REJECTED")

    return {
        "resolved": True,
        "status": event.status,
        "escalation": _event_to_dict(event),
    }


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/escalation/trigger  (admin / internal)
# ══════════════════════════════════════════════════════════════════════════════
@router.post(
    "/trigger",
    summary="Manually trigger an escalation (admin/testing only)",
)
async def manual_trigger(
    body: ManualTriggerRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
):
    """
    Admin-only endpoint to manually open an escalation for a student.

    Useful for testing the flow end-to-end, or for cases where a teacher
    wants to force secondary verification outside of the automated pipeline.
    """
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")

    svc = get_escalation_service(_get_firestore())
    from services.escalation_service import _FAIL_THRESHOLD  # re-use threshold

    event = svc.maybe_escalate(
        student_id=body.student_id,
        period_id=body.period_id,
        fail_count=_FAIL_THRESHOLD,   # guarantee threshold is met
        trigger_reason=body.trigger_reason,
        method=body.method,           # type: ignore[arg-type]
    )

    if event is None:
        raise HTTPException(
            status_code=409,
            detail="An active escalation already exists for this student/period.",
        )

    response: dict = {
        "triggered": True,
        "escalation": _event_to_dict(event),
    }
    # Surface the plain OTP to the admin so they can relay it (test/override)
    if event.otp_plain:
        response["otp"] = event.otp_plain

    return response


# ── Internal audit helper ─────────────────────────────────────────────────────
def _audit_resolve(
    request: Any,
    user: UserContext,
    escalation_id: str,
    event: EscalationEvent,
    action: str,
) -> None:
    try:
        from services.audit_services import get_audit_service
        get_audit_service().log(
            action=action,
            resource="escalation",
            resource_id=escalation_id,
            user=user,
            request=request,
            details={
                "student_id": event.student_id,
                "period_id": event.period_id,
                "resolved_by": event.resolved_by,
                "notes": event.session_notes,
            },
            success=True,
        )
    except Exception:
        pass