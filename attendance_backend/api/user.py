"""
api/user.py
─────────────────────────────────────────────────────────────────────────────
User registration, profile, and enrollment endpoints.

Changes from original (backward-compatible)
-------------------------------------------
• POST /user/register   — persists ``assigned_sections``; validates role.
• POST /user/login      — returns JWT access+refresh token pair.
• GET  /user/profile/{user_id}   — includes permissions and sections.
• GET  /user/users/by-role/{role} — unchanged.
• POST /user/forgot-password     — unchanged.
• POST /user/reset-password      — unchanged.
• PATCH /user/profile/{user_id}  — self-service name update.

New (multi-photo enrollment)
----------------------------
• POST /user/enroll/{user_id}
    Accept 5–10 face images (multipart/form-data), extract embeddings,
    compute centroid + per-dimension variance, persist to Firestore, and
    update the in-process FAISS index.

• GET  /user/enroll/{user_id}/stats
    Return stored enrollment statistics (sample_count, centroid_dim,
    enrolled_at, etc.) without exposing the raw vectors.

Hardening (reset-password, 2024-05 pass)
-----------------------------------------
See original docstring for details.
"""
from __future__ import annotations

import base64
import io
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from database.user_repository import UserRepository
from middleware.auth_middleware import get_current_user, require_own_resource_or_admin, TokenPayload
from schemas.enrollment_schemas import EnrollmentResponse, EnrollmentStatsResponse
from schemas.user_schemas import (
    UserLoginRequest,
    UserLoginResponse,
    UserProfileResponse,
    UserRegistrationRequest,
    UserRegistrationResponse,
    VALID_ROLES,
)
from services.auth_service import AuthService
from services.email_service import EmailService
from services.face_recognition_service import FaceRecognitionService
from services.firebase_service import get_firebase_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user", tags=["user"])

_user_repo  = UserRepository()
_auth_svc   = AuthService()
_email_svc  = EmailService()
_face_svc   = FaceRecognitionService()   # shared instance; FAISS index lives here

_JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# Maximum size accepted for a single uploaded image (10 MB)
_MAX_IMAGE_BYTES: int = 10 * 1024 * 1024


# ─────────────────────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserRegistrationResponse, status_code=201)
def register_user(request: UserRegistrationRequest):
    """
    Register a new user.

    Role must be one of: admin | teacher | student.
    Teachers may supply ``assigned_sections`` at registration time.
    """
    try:
        # Duplicate email check
        if _user_repo.get_user_by_email(request.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists.",
            )

        # Role guard (also enforced by Pydantic validator — double-safe)
        if request.role not in VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role must be one of {sorted(VALID_ROLES)}.",
            )

        user_id = str(uuid.uuid4())
        user_data = {
            "email":             request.email,
            "name":              request.name,
            "role":              request.role,
            "password_hash":     AuthService.hash_password(request.password),
            "assigned_sections": request.assigned_sections,   # [] for non-teachers
            "is_active":         True,
            "created_at":        datetime.utcnow().isoformat(),
        }

        if not _user_repo.create_user(user_id, user_data):
            raise HTTPException(status_code=500, detail="Failed to create user.")

        logger.info("User registered: %s role=%s", user_id, request.role)
        return UserRegistrationResponse(
            success=True,
            user_id=user_id,
            message="User registered successfully.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Registration error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error.")


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=UserLoginResponse)
def login_user(request: UserLoginRequest):
    """
    Authenticate a user and return a JWT access+refresh token pair.

    The ``token`` field contains the access token for backward compatibility
    with clients that only read that field.
    """
    _auth_err = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        user = _user_repo.get_user_by_email(request.email)
        if not user:
            raise _auth_err

        if not AuthService.verify_password(request.password, user.get("password_hash", "")):
            raise _auth_err

        if not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive. Contact your administrator.",
            )

        tokens    = AuthService.generate_token_pair(user)
        perms     = AuthService.get_permissions_for_role(user.get("role", "student"))
        expire_s  = _JWT_EXPIRE_MINUTES * 60

        logger.info("Login: user=%s role=%s", user["user_id"], user.get("role"))
        return UserLoginResponse(
            success=True,
            user_id=user["user_id"],
            role=user.get("role", "student"),
            token=tokens["access_token"],            # backward-compatible field
            refresh_token=tokens["refresh_token"],
            expires_in=expire_s,
            permissions=perms,
            assigned_sections=user.get("assigned_sections", []),
            message="Login successful.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Login error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error.")


# ─────────────────────────────────────────────────────────────────────────────
# Profile
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/profile/{user_id}", response_model=UserProfileResponse)
def get_profile(
    user_id: str,
    caller: TokenPayload = Depends(require_own_resource_or_admin("user_id")),
):
    """
    Fetch user profile by ID.

    Callers may only view their own profile unless they are admin.
    """
    try:
        user = _user_repo.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        perms = AuthService.get_permissions_for_role(user.get("role", "student"))
        return UserProfileResponse(
            user_id=user_id,
            name=user["name"],
            email=user["email"],
            role=user.get("role", "student"),
            is_active=user.get("is_active", True),
            permissions=perms,
            assigned_sections=user.get("assigned_sections", []),
            created_at=user.get("created_at"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error fetching profile %s: %s", user_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.patch("/profile/{user_id}")
def update_own_profile(
    user_id: str,
    name: str,
    caller: TokenPayload = Depends(require_own_resource_or_admin("user_id")),
):
    """
    Self-service name update.

    Students and teachers can update their own name.
    Admins can update any user's name via this endpoint.
    For role/section changes use PATCH /api/v1/admin/users/{user_id}.
    """
    if len(name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters.")
    ok = _user_repo.update_user(user_id, {"name": name.strip()})
    if not ok:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"success": True, "user_id": user_id, "name": name.strip()}


# ─────────────────────────────────────────────────────────────────────────────
# Users by role  (admin utility)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/users/by-role/{role}")
def get_users_by_role(
    role: str,
    caller: TokenPayload = Depends(get_current_user),
):
    """
    List users by role.

    Admins see any role. Teachers/students are blocked (use admin router instead).
    """
    if caller.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins may list users by role.",
        )
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Role must be one of {sorted(VALID_ROLES)}.",
        )

    try:
        users = _user_repo.list_users_by_role(role)
        for u in users:
            u.pop("password_hash", None)
            u.pop("reset_token", None)
            u.pop("reset_expires", None)
        return {"success": True, "role": role, "count": len(users), "users": users}
    except Exception as exc:
        logger.error("Error fetching users by role %s: %s", role, exc)
        raise HTTPException(status_code=500, detail="Internal server error.")


# ─────────────────────────────────────────────────────────────────────────────
# Password reset
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/forgot-password")
def forgot_password(email: str):
    """
    Send a password-reset link if the email is registered.

    Always returns success to prevent email enumeration.
    """
    try:
        user = _user_repo.get_user_by_email(email)
        if user:
            token   = str(uuid.uuid4())
            expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()
            _user_repo.update_user(user["user_id"], {
                "reset_token":   token,
                "reset_expires": expires,
            })
            _email_svc.send_password_reset(email, token)
            logger.info("Password reset requested: %s", email)
    except Exception as exc:
        logger.error("Forgot-password error: %s", exc)

    # Always return the same response
    return {"success": True, "message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(token: str, new_password: str):
    """
    Reset password using a valid reset token (expires in 24 h).

    Hardening: RTDB ``users`` node may be None (empty deployment) or a non-dict
    value.  Both cases are now explicitly handled — a warning is logged and the
    caller receives the same user-visible 400 "Invalid or expired reset token."
    response.  Firebase errors are logged at ERROR level for observability.
    """
    if len(new_password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters.",
        )

    try:
        from database.firebase_client import FirebaseClient
        fb = FirebaseClient()

        try:
            raw_users = fb.get_reference("users").get()
        except Exception as fb_exc:
            # Firebase transport / auth error — log loudly, respond safely
            logger.error("reset_password: Firebase read error: %s", fb_exc)
            raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

        # Guard: missing node (None) or unexpected type both mean no valid token
        if raw_users is None:
            logger.warning("reset_password: RTDB 'users' node is absent (None)")
            raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

        if not isinstance(raw_users, dict):
            logger.warning(
                "reset_password: RTDB 'users' node is type %s, expected dict",
                type(raw_users).__name__,
            )
            raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

        users_data: dict = raw_users  # now guaranteed to be dict

        user_id = None
        for uid, udata in users_data.items():
            if not isinstance(udata, dict):
                continue
            if udata.get("reset_token") == token:
                expires_raw = udata.get("reset_expires")
                if expires_raw:
                    try:
                        if datetime.fromisoformat(expires_raw) > datetime.utcnow():
                            user_id = uid
                            break
                    except ValueError:
                        logger.warning(
                            "reset_password: malformed reset_expires '%s' for user %s",
                            expires_raw, uid,
                        )

        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

        _user_repo.update_user(user_id, {
            "password_hash": AuthService.hash_password(new_password),
            "reset_token":   None,
            "reset_expires": None,
        })
        logger.info("Password reset successful: user=%s", user_id)
        return {"success": True, "message": "Password reset. You may now log in."}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Reset-password error: %s", exc)
        raise HTTPException(status_code=400, detail="Password reset failed.")


# ─────────────────────────────────────────────────────────────────────────────
# Multi-photo enrollment
# ─────────────────────────────────────────────────────────────────────────────

def _decode_upload(upload: UploadFile) -> np.ndarray:
    """
    Read an UploadFile and decode it to a BGR numpy array (via OpenCV).

    Raises:
        HTTPException 400 if the file exceeds ``_MAX_IMAGE_BYTES``, cannot be
        read, or cannot be decoded as an image.
    """
    raw = upload.file.read()
    if len(raw) > _MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Image '{upload.filename}' exceeds the 10 MB size limit.",
        )
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(
            status_code=400,
            detail=f"Could not decode '{upload.filename}' as an image. "
                   "Supported formats: JPEG, PNG, BMP, WEBP.",
        )
    return img


@router.post(
    "/enroll/{user_id}",
    response_model=EnrollmentResponse,
    status_code=201,
    summary="Multi-photo face enrollment",
    description=(
        "Accept 5–10 face images for the user, extract embeddings, "
        "compute a normalised centroid and per-dimension variance, "
        "persist the stats to Firestore, and update the in-process FAISS index. "
        "Callers may only enroll their own user_id unless they are admin."
    ),
)
async def enroll_user(
    user_id: str,
    files: List[UploadFile] = File(
        ...,
        description="5–10 face images (JPEG / PNG / BMP / WEBP). "
                    "Each file must be ≤ 10 MB.",
    ),
    device_id: Optional[str] = Form(None, description="Device that captured the images."),
    location:  Optional[str] = Form(None, description="Physical capture location label."),
    caller:    TokenPayload  = Depends(require_own_resource_or_admin("user_id")),
):
    """
    Multi-photo face enrollment endpoint.

    Pipeline
    --------
    1. Verify the user exists in the user repository.
    2. Validate image count (5 ≤ N ≤ 10).
    3. Decode each uploaded file to a numpy BGR image.
    4. Delegate to ``FaceRecognitionService.enroll_student_multi()``
       which handles extraction, normalisation, centroid/variance computation,
       and FAISS index update.
    5. Persist centroid + variance + capped raw embeddings to Firestore via
       ``FirebaseService.store_enrollment()``.

    Auth
    ----
    A user may enroll themselves.  An admin may enroll any user.

    Request (multipart/form-data)
    -----------------------------
    files     – 5–10 image files
    device_id – optional string
    location  – optional string

    Response (201)
    --------------
    EnrollmentResponse with success, user_id, sample_count, centroid_dim,
    and a human-readable message.
    """
    # ── 0. user must exist ────────────────────────────────────────────────────
    if not _user_repo.get_user(user_id):
        raise HTTPException(status_code=404, detail="User not found.")

    min_img = FaceRecognitionService.MIN_ENROLLMENT_IMAGES
    max_img = FaceRecognitionService.MAX_ENROLLMENT_IMAGES

    # ── 1. file-count pre-check (fast-fail before decoding) ──────────────────
    n_files = len(files)
    if n_files < min_img:
        raise HTTPException(
            status_code=400,
            detail=f"Please upload at least {min_img} images (received {n_files}).",
        )
    if n_files > max_img:
        raise HTTPException(
            status_code=400,
            detail=f"Please upload at most {max_img} images (received {n_files}).",
        )

    # ── 2. decode images ──────────────────────────────────────────────────────
    face_images: List[np.ndarray] = []
    for upload in files:
        face_images.append(_decode_upload(upload))

    # ── 3. extract embeddings + build stats + update FAISS ───────────────────
    try:
        result = _face_svc.enroll_student_multi(
            student_id=user_id,
            face_images=face_images,
            student_info={"user_id": user_id},
        )
    except ValueError as exc:
        # Covers too-few-successful-embeddings case
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        logger.error("enroll_user: model error for %s: %s", user_id, exc)
        raise HTTPException(status_code=503, detail="Face recognition model unavailable.")

    # ── 4. persist to Firestore ───────────────────────────────────────────────
    fb = get_firebase_service()
    if fb is not None:
        meta = {"device_id": device_id, "location": location}
        stored = fb.store_enrollment(
            student_id=user_id,
            normalized_embeddings=result["normalized_embeddings"],
            metadata=meta,
        )
        if not stored:
            # Non-fatal: FAISS is already updated; log and continue.
            logger.warning(
                "enroll_user: Firestore write failed for %s — FAISS index updated "
                "but stats not persisted.",
                user_id,
            )
    else:
        logger.warning(
            "enroll_user: Firebase service unavailable; enrollment stats not persisted for %s.",
            user_id,
        )

    centroid_dim = int(result["centroid"].shape[0])
    logger.info(
        "Enrollment complete: user=%s sample_count=%d centroid_dim=%d",
        user_id, result["sample_count"], centroid_dim,
    )

    return EnrollmentResponse(
        success=True,
        user_id=user_id,
        sample_count=result["sample_count"],
        centroid_dim=centroid_dim,
        message=result["message"],
    )


@router.get(
    "/enroll/{user_id}/stats",
    response_model=EnrollmentStatsResponse,
    summary="Enrollment statistics",
    description=(
        "Return stored enrollment metadata for the user: sample count, "
        "centroid dimensionality, timestamp, and capture context.  "
        "Raw vectors are NOT returned. "
        "Callers may only view their own stats unless they are admin."
    ),
)
def get_enrollment_stats(
    user_id: str,
    caller: TokenPayload = Depends(require_own_resource_or_admin("user_id")),
):
    """
    Return stored enrollment statistics (no raw vectors).

    Raises 404 if the user has not been enrolled yet.
    """
    fb = get_firebase_service()
    if fb is None:
        raise HTTPException(
            status_code=503,
            detail="Firebase service unavailable.",
        )

    stats = fb.get_enrollment_stats(user_id)
    if stats is None:
        raise HTTPException(
            status_code=404,
            detail="Enrollment stats not found. The user may not have been enrolled yet.",
        )

    return EnrollmentStatsResponse(
        user_id=user_id,
        sample_count=stats.get("sample_count", 0),
        centroid_dim=len(stats.get("centroid", [])),
        enrolled_at=stats.get("enrolled_at"),
        device_id=stats.get("device_id"),
        location=stats.get("location"),
    )