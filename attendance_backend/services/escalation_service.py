"""
escalation_service.py — Secondary-factor escalation after repeated face-auth failures
══════════════════════════════════════════════════════════════════════════════════════

Trigger
───────
When a student's face-auth fails ESCALATION_FAIL_THRESHOLD times (default 2)
inside one period, `EscalationService.maybe_escalate()` is called.  It writes
a record to the Firestore `face_verification_escalations` collection and returns
an `EscalationEvent` that the caller includes in its API response so the client
knows what secondary factor is required.

Secondary factors
─────────────────
  "otp"              — 6-digit code generated server-side, hashed with SHA-256
                       + per-record salt, stored in Firestore.  The plain code
                       is returned ONCE in the trigger response so the caller
                       can forward it to the student (SMS / email / push).
                       Verified via POST /api/v1/escalation/{id}/otp/verify.

  "teacher_approval" — A pending approval record is created.  A teacher calls
                       POST /api/v1/escalation/{id}/approve (or /reject).
                       Client polls GET /api/v1/escalation/{id}/status.

Firestore schema  (collection: face_verification_escalations)
──────────────────────────────────────────────────────────────
{
  escalation_id:   str          # document ID (uuid4)
  student_id:      str
  period_id:       str
  triggered_at:    str          # ISO-8601
  expires_at:      str          # ISO-8601  (triggered_at + TTL)
  trigger_reason:  str          # "quick_fail_threshold" | "manual"
  fail_count:      int
  status:          str          # "pending" | "approved" | "rejected" | "expired"
  method:          str          # "otp" | "teacher_approval"
  otp_salt:        str | None   # hex  (otp path only)
  otp_hash:        str | None   # hex SHA-256(salt + plain_otp)  (otp path only)
  otp_attempts:    int          # failed OTP verify attempts
  resolved_at:     str | None   # ISO-8601
  resolved_by:     str | None   # teacher_id | "otp" | "system"
  session_notes:   str | None   # free-text from teacher on approve/reject
}

Environment variables
─────────────────────
  ESCALATION_FAIL_THRESHOLD   int    default 2   — failures before escalation
  ESCALATION_METHOD           str    default "otp" — "otp" | "teacher_approval"
  ESCALATION_TTL_MINUTES      int    default 15  — escalation expires after N min
  ESCALATION_OTP_DIGITS       int    default 6
  ESCALATION_MAX_OTP_ATTEMPTS int    default 3   — wrong OTP → auto-reject
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Env-driven constants ──────────────────────────────────────────────────────
_FAIL_THRESHOLD: int = int(os.getenv("ESCALATION_FAIL_THRESHOLD", "2"))
_METHOD: str = os.getenv("ESCALATION_METHOD", "otp")          # otp | teacher_approval
_TTL_MIN: int = int(os.getenv("ESCALATION_TTL_MINUTES", "15"))
_OTP_DIGITS: int = int(os.getenv("ESCALATION_OTP_DIGITS", "6"))
_MAX_OTP_ATTEMPTS: int = int(os.getenv("ESCALATION_MAX_OTP_ATTEMPTS", "3"))

_COLLECTION = "face_verification_escalations"

EscalationMethod = Literal["otp", "teacher_approval"]
EscalationStatus = Literal["pending", "approved", "rejected", "expired"]


# ── Data classes ──────────────────────────────────────────────────────────────
@dataclass
class EscalationEvent:
    """
    Returned by `maybe_escalate` and `get_escalation`.
    The API layer serialises this into the response body.
    """
    escalation_id: str
    student_id: str
    period_id: str
    method: EscalationMethod
    status: EscalationStatus
    triggered_at: str
    expires_at: str
    fail_count: int
    # Present only on initial trigger for OTP path — never stored plain-text.
    otp_plain: Optional[str] = field(default=None, repr=False)
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    session_notes: Optional[str] = None

    @property
    def is_resolved(self) -> bool:
        return self.status in ("approved", "rejected", "expired")


@dataclass
class OTPVerifyResult:
    success: bool
    status: EscalationStatus
    attempts_remaining: int
    message: str


# ── Helpers ───────────────────────────────────────────────────────────────────
def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _generate_otp(digits: int = _OTP_DIGITS) -> str:
    """Cryptographically-random zero-padded decimal OTP."""
    upper = 10 ** digits
    return str(secrets.randbelow(upper)).zfill(digits)


def _hash_otp(salt: str, plain: str) -> str:
    """SHA-256(salt + plain) returned as hex digest."""
    return hashlib.sha256(f"{salt}{plain}".encode()).hexdigest()


def _new_salt() -> str:
    return secrets.token_hex(16)


def _check_expired(doc_dict: dict) -> bool:
    try:
        expires_at = datetime.fromisoformat(doc_dict["expires_at"])
        return _now_utc() > expires_at
    except Exception:
        return False


# ── Service ───────────────────────────────────────────────────────────────────
class EscalationService:
    """
    Server-side escalation manager.

    All public methods are safe to call when `self.db` is None — they log a
    warning and return a graceful no-op / None so the pipeline never crashes
    due to a missing Firestore connection.
    """

    def __init__(self, firestore_db: Any = None) -> None:
        self.db = firestore_db

    # ── Primary entry-point ───────────────────────────────────────────────────
    def should_escalate(self, fail_count: int) -> bool:
        """True when the failure count has reached the escalation threshold."""
        return fail_count >= _FAIL_THRESHOLD

    def maybe_escalate(
        self,
        *,
        student_id: str,
        period_id: str,
        fail_count: int,
        trigger_reason: str = "quick_fail_threshold",
        method: Optional[EscalationMethod] = None,
    ) -> Optional[EscalationEvent]:
        """
        Create an escalation event if `fail_count` >= threshold AND no active
        escalation already exists for this student+period.

        Returns the EscalationEvent (with otp_plain set for OTP path) or None
        if escalation is not needed / already active.
        """
        if not self.should_escalate(fail_count):
            return None

        # Idempotency: don't open a second escalation if one is already pending
        existing = self._find_active(student_id, period_id)
        if existing is not None:
            logger.debug(
                f"Escalation already active for {student_id}/{period_id}: "
                f"{existing.escalation_id}"
            )
            return existing

        chosen_method: EscalationMethod = method or _METHOD  # type: ignore[assignment]
        return self._create_escalation(
            student_id=student_id,
            period_id=period_id,
            fail_count=fail_count,
            trigger_reason=trigger_reason,
            method=chosen_method,
        )

    # ── OTP verification ──────────────────────────────────────────────────────
    def verify_otp(
        self,
        escalation_id: str,
        plain_otp: str,
    ) -> OTPVerifyResult:
        """
        Verify a student-submitted OTP.

        Side-effects:
          • Increments otp_attempts on wrong code.
          • Auto-rejects and sets status="rejected" after MAX_OTP_ATTEMPTS.
          • Sets status="approved", resolved_at, resolved_by on correct code.
          • Sets status="expired" if the record's expires_at has passed.
        """
        if not self.db:
            return OTPVerifyResult(
                success=False, status="pending",
                attempts_remaining=_MAX_OTP_ATTEMPTS,
                message="Verification service unavailable.",
            )

        try:
            doc_ref = self.db.collection(_COLLECTION).document(escalation_id)
            doc = doc_ref.get()

            if not doc.exists:
                return OTPVerifyResult(
                    success=False, status="rejected",
                    attempts_remaining=0,
                    message="Escalation record not found.",
                )

            data = doc.to_dict()

            # Already resolved?
            status: EscalationStatus = data.get("status", "pending")
            if status != "pending":
                return OTPVerifyResult(
                    success=status == "approved",
                    status=status,
                    attempts_remaining=0,
                    message=f"Escalation already {status}.",
                )

            # Expired?
            if _check_expired(data):
                doc_ref.update({"status": "expired"})
                return OTPVerifyResult(
                    success=False, status="expired",
                    attempts_remaining=0,
                    message="Escalation has expired. Please try again.",
                )

            # Check OTP method
            if data.get("method") != "otp":
                return OTPVerifyResult(
                    success=False, status="pending",
                    attempts_remaining=0,
                    message="This escalation requires teacher approval, not OTP.",
                )

            salt = data.get("otp_salt", "")
            stored_hash = data.get("otp_hash", "")
            otp_attempts: int = data.get("otp_attempts", 0)

            submitted_hash = _hash_otp(salt, plain_otp.strip())

            if submitted_hash == stored_hash:
                now = _iso(_now_utc())
                doc_ref.update({
                    "status": "approved",
                    "resolved_at": now,
                    "resolved_by": "otp",
                    "otp_attempts": otp_attempts + 1,
                })
                logger.info(f"OTP verified for escalation {escalation_id}")
                return OTPVerifyResult(
                    success=True, status="approved",
                    attempts_remaining=0,
                    message="Identity verified via OTP.",
                )

            # Wrong OTP
            otp_attempts += 1
            remaining = max(0, _MAX_OTP_ATTEMPTS - otp_attempts)

            if otp_attempts >= _MAX_OTP_ATTEMPTS:
                doc_ref.update({
                    "status": "rejected",
                    "otp_attempts": otp_attempts,
                    "resolved_at": _iso(_now_utc()),
                    "resolved_by": "system",
                    "session_notes": "Max OTP attempts exceeded.",
                })
                logger.warning(
                    f"Escalation {escalation_id} auto-rejected after "
                    f"{otp_attempts} OTP failures."
                )
                return OTPVerifyResult(
                    success=False, status="rejected",
                    attempts_remaining=0,
                    message="Too many incorrect attempts. Escalation rejected.",
                )

            doc_ref.update({"otp_attempts": otp_attempts})
            return OTPVerifyResult(
                success=False, status="pending",
                attempts_remaining=remaining,
                message=f"Incorrect OTP. {remaining} attempt(s) remaining.",
            )

        except Exception as exc:
            logger.error(f"OTP verification error for {escalation_id}: {exc}")
            return OTPVerifyResult(
                success=False, status="pending",
                attempts_remaining=_MAX_OTP_ATTEMPTS,
                message="Verification error. Please try again.",
            )

    # ── Teacher approval ──────────────────────────────────────────────────────
    def resolve_teacher(
        self,
        escalation_id: str,
        *,
        teacher_id: str,
        approve: bool,
        notes: Optional[str] = None,
    ) -> Optional[EscalationEvent]:
        """
        Teacher approves or rejects a pending escalation.

        Returns the updated EscalationEvent or None on error.
        """
        if not self.db:
            logger.warning("resolve_teacher: no Firestore connection")
            return None

        try:
            doc_ref = self.db.collection(_COLLECTION).document(escalation_id)
            doc = doc_ref.get()

            if not doc.exists:
                logger.warning(f"resolve_teacher: {escalation_id} not found")
                return None

            data = doc.to_dict()
            if data.get("status") != "pending":
                logger.info(
                    f"resolve_teacher: {escalation_id} already "
                    f"{data.get('status')}"
                )
                return self._dict_to_event(escalation_id, data)

            now = _iso(_now_utc())
            new_status: EscalationStatus = "approved" if approve else "rejected"

            doc_ref.update({
                "status": new_status,
                "resolved_at": now,
                "resolved_by": teacher_id,
                "session_notes": notes or "",
            })

            data.update({
                "status": new_status,
                "resolved_at": now,
                "resolved_by": teacher_id,
                "session_notes": notes or "",
            })

            logger.info(
                f"Escalation {escalation_id} {new_status} by teacher {teacher_id}"
            )
            return self._dict_to_event(escalation_id, data)

        except Exception as exc:
            logger.error(f"resolve_teacher error for {escalation_id}: {exc}")
            return None

    # ── Read ──────────────────────────────────────────────────────────────────
    def get_escalation(self, escalation_id: str) -> Optional[EscalationEvent]:
        """Fetch an escalation by ID. Marks as expired if TTL passed."""
        if not self.db:
            return None
        try:
            doc_ref = self.db.collection(_COLLECTION).document(escalation_id)
            doc = doc_ref.get()
            if not doc.exists:
                return None

            data = doc.to_dict()

            # Lazily expire
            if data.get("status") == "pending" and _check_expired(data):
                doc_ref.update({"status": "expired"})
                data["status"] = "expired"

            return self._dict_to_event(escalation_id, data)

        except Exception as exc:
            logger.error(f"get_escalation error: {exc}")
            return None

    # ── Private helpers ───────────────────────────────────────────────────────
    def _find_active(
        self, student_id: str, period_id: str
    ) -> Optional[EscalationEvent]:
        """Return an existing pending escalation for this student+period, if any."""
        if not self.db:
            return None
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            results = (
                self.db.collection(_COLLECTION)
                .where("student_id", "==", student_id)
                .where("period_id", "==", period_id)
                .where("status", "==", "pending")
                .limit(1)
                .stream()
            )
            for doc in results:
                data = doc.to_dict()
                if _check_expired(data):
                    doc.reference.update({"status": "expired"})
                    continue
                return self._dict_to_event(doc.id, data)
        except Exception as exc:
            logger.warning(f"_find_active query failed: {exc}")
        return None

    def _create_escalation(
        self,
        *,
        student_id: str,
        period_id: str,
        fail_count: int,
        trigger_reason: str,
        method: EscalationMethod,
    ) -> EscalationEvent:
        """Write a new escalation document and return the event."""
        escalation_id = str(uuid.uuid4())
        now = _now_utc()
        expires_at = now + timedelta(minutes=_TTL_MIN)

        otp_plain: Optional[str] = None
        otp_salt: Optional[str] = None
        otp_hash_val: Optional[str] = None

        if method == "otp":
            otp_plain = _generate_otp()
            otp_salt = _new_salt()
            otp_hash_val = _hash_otp(otp_salt, otp_plain)

        doc_data: dict = {
            "student_id": student_id,
            "period_id": period_id,
            "triggered_at": _iso(now),
            "expires_at": _iso(expires_at),
            "trigger_reason": trigger_reason,
            "fail_count": fail_count,
            "status": "pending",
            "method": method,
            "otp_salt": otp_salt,
            "otp_hash": otp_hash_val,
            "otp_attempts": 0,
            "resolved_at": None,
            "resolved_by": None,
            "session_notes": None,
        }

        if self.db:
            try:
                self.db.collection(_COLLECTION).document(escalation_id).set(doc_data)
                logger.info(
                    f"Escalation created: id={escalation_id} student={student_id} "
                    f"period={period_id} method={method} fails={fail_count}"
                )
            except Exception as exc:
                logger.error(f"Failed to write escalation to Firestore: {exc}")
        else:
            logger.warning(
                "EscalationService: no Firestore — escalation event not persisted."
            )

        event = self._dict_to_event(escalation_id, doc_data)
        event.otp_plain = otp_plain   # returned ONCE; never stored plain
        return event

    @staticmethod
    def _dict_to_event(escalation_id: str, data: dict) -> EscalationEvent:
        return EscalationEvent(
            escalation_id=escalation_id,
            student_id=data.get("student_id", ""),
            period_id=data.get("period_id", ""),
            method=data.get("method", "otp"),
            status=data.get("status", "pending"),
            triggered_at=data.get("triggered_at", ""),
            expires_at=data.get("expires_at", ""),
            fail_count=data.get("fail_count", 0),
            resolved_at=data.get("resolved_at"),
            resolved_by=data.get("resolved_by"),
            session_notes=data.get("session_notes"),
        )


# ── Module-level singleton ────────────────────────────────────────────────────
_service: Optional[EscalationService] = None


def get_escalation_service(firestore_db: Any = None) -> EscalationService:
    """Return a shared EscalationService (lazy init)."""
    global _service
    if _service is None:
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
        _service = EscalationService(firestore_db)
    return _service