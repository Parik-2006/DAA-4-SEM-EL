"""
face_attempt_service.py — Track face detection attempts per student per period
════════════════════════════════════════════════════════════════════════════════
Enforces a maximum of 5 face detection attempts per student per period.
After 5 failed attempts, no more attempts are allowed until the period closes.

Updated in this revision
─────────────────────────
* `increment_and_check()` — increments the counter, then checks whether the
  new count crosses the escalation threshold.  Returns both the new count and
  an optional EscalationEvent so callers get everything in one call.
* `get_escalation_status()` — convenience proxy to EscalationService.
"""

import logging
from datetime import datetime
from typing import Any, Optional, Tuple

from services.escalation_service import (
    EscalationEvent,
    EscalationService,
    get_escalation_service,
)

logger = logging.getLogger(__name__)

# Maximum attempts per student per period
MAX_FACE_DETECTION_ATTEMPTS = 5


class FaceAttemptService:
    """Track face detection attempts in Firestore."""

    def __init__(
        self,
        firestore_db: Any = None,
        escalation_service: Optional[EscalationService] = None,
    ) -> None:
        self.db = firestore_db
        self.escalation_svc: EscalationService = (
            escalation_service or get_escalation_service(firestore_db)
        )

    # ── Attempt tracking (unchanged behaviour) ────────────────────────────────
    def get_attempt_count(
        self, student_id: str, period_id: Optional[str] = None
    ) -> int:
        """Get the current attempt count for a student in a period."""
        if not self.db or not student_id:
            return 0

        try:
            today = datetime.now().strftime("%Y-%m-%d")
            attempt_key = f"{student_id}_{period_id or 'unknown'}_{today}"
            doc = self.db.collection("face_attempts").document(attempt_key).get()
            return doc.to_dict().get("count", 0) if doc.exists else 0
        except Exception as e:
            logger.warning(f"Could not retrieve attempt count: {e}")
            return 0

    def increment_attempt(
        self, student_id: str, period_id: Optional[str] = None
    ) -> int:
        """
        Increment the attempt count and return the new count.
        Returns the new count after incrementing.
        """
        if not self.db or not student_id:
            return 1

        try:
            today = datetime.now().strftime("%Y-%m-%d")
            attempt_key = f"{student_id}_{period_id or 'unknown'}_{today}"
            doc_ref = self.db.collection("face_attempts").document(attempt_key)
            doc = doc_ref.get()

            new_count = (doc.to_dict().get("count", 0) + 1) if doc.exists else 1

            doc_ref.set({
                "student_id": student_id,
                "period_id": period_id or "unknown",
                "date": today,
                "count": new_count,
                "last_attempt": datetime.now().isoformat(),
            })
            return new_count
        except Exception as e:
            logger.warning(f"Could not increment attempt count: {e}")
            return 1

    def can_attempt(
        self, student_id: str, period_id: Optional[str] = None
    ) -> Tuple[bool, int]:
        """
        Check if a student can attempt face detection.
        Returns (can_attempt, current_count).
        """
        current_count = self.get_attempt_count(student_id, period_id)
        return current_count < MAX_FACE_DETECTION_ATTEMPTS, current_count

    def reset_attempts(
        self, student_id: str, period_id: Optional[str] = None
    ) -> None:
        """Reset attempts for a student in a period (on successful detection)."""
        if not self.db or not student_id:
            return

        try:
            today = datetime.now().strftime("%Y-%m-%d")
            attempt_key = f"{student_id}_{period_id or 'unknown'}_{today}"
            self.db.collection("face_attempts").document(attempt_key).delete()
            logger.info(f"Reset attempts for {student_id} in period {period_id}")
        except Exception as e:
            logger.warning(f"Could not reset attempts: {e}")

    # ── NEW: combined increment + escalation check ────────────────────────────
    def increment_and_check(
        self,
        student_id: str,
        period_id: Optional[str] = None,
        trigger_reason: str = "quick_fail_threshold",
    ) -> Tuple[int, Optional[EscalationEvent]]:
        """
        Increment the failure counter and trigger escalation when the threshold
        is crossed for the first time.

        Returns
        -------
        (new_count, escalation_event)
            escalation_event is None when the threshold has not been reached or
            an escalation is already active for this student+period.

        Usage in pipeline
        -----------------
            count, escalation = attempt_svc.increment_and_check(student_id, period_id)
            if escalation:
                # Return escalation_id + method to the client
                return {"status": "escalation_required", "escalation": asdict(escalation)}
        """
        new_count = self.increment_attempt(student_id, period_id)

        escalation_event: Optional[EscalationEvent] = (
            self.escalation_svc.maybe_escalate(
                student_id=student_id,
                period_id=period_id or "unknown",
                fail_count=new_count,
                trigger_reason=trigger_reason,
            )
        )

        if escalation_event:
            logger.info(
                f"Escalation triggered: student={student_id} period={period_id} "
                f"count={new_count} id={escalation_event.escalation_id} "
                f"method={escalation_event.method}"
            )

        return new_count, escalation_event

    # ── NEW: escalation status convenience proxy ──────────────────────────────
    def get_escalation_status(
        self, escalation_id: str
    ) -> Optional[EscalationEvent]:
        """Proxy to EscalationService.get_escalation for callers that only
        hold a FaceAttemptService reference."""
        return self.escalation_svc.get_escalation(escalation_id)


def get_face_attempt_service(firestore_db: Any = None) -> FaceAttemptService:
    """Get or create a face attempt service instance."""
    if firestore_db is None:
        try:
            from services.firebase_service import get_firebase_service
            fb = get_firebase_service()
            firestore_db = (
                getattr(fb, "firestore_db", None)
                or getattr(fb, "_firestore", None)
            )
        except Exception:
            pass

    return FaceAttemptService(firestore_db)