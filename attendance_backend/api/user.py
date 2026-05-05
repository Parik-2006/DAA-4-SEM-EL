"""
User registration and authentication endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException, status
from schemas.user_schemas import (
    UserRegistrationRequest, UserRegistrationResponse,
    UserLoginRequest, UserLoginResponse, UserProfileResponse
)
from database.user_repository import UserRepository
from services.auth_service import AuthService
from services.email_service import EmailService
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user", tags=["user"])
user_repo = UserRepository()
auth_service = AuthService()
email_service = EmailService()

@router.post("/register", response_model=UserRegistrationResponse, status_code=201)
def register_user(request: UserRegistrationRequest):
    """Register a new user (admin or student)."""
    try:
        # Check if user already exists
        existing = user_repo.get_user_by_email(request.email)
        if existing:
            raise HTTPException(
                status_code=409,
                detail="User with this email already exists"
            )
        
        # Validate role
        if request.role not in ["admin", "student"]:
            raise HTTPException(
                status_code=400,
                detail="Role must be 'admin' or 'student'"
            )
        
        user_id = str(uuid.uuid4())
        user_data = {
            "email": request.email,
            "name": request.name,
            "role": request.role,
            "password_hash": auth_service.hash_password(request.password),
            "is_active": True,
            "created_at": datetime.utcnow().isoformat(),
        }
        
        success = user_repo.create_user(user_id, user_data)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to create user"
            )
        
        logger.info(f"User registered: {user_id} with role {request.role}")
        return UserRegistrationResponse(
            success=True,
            user_id=user_id,
            message="User registered successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/login", response_model=UserLoginResponse)
def login_user(request: UserLoginRequest):
    """Login a user (admin or student) — DEPRECATED: Use /api/v1/auth/login instead."""
    try:
        user = user_repo.get_user_by_email(request.email)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )
        
        if not auth_service.verify_password(request.password, user.get("password_hash", "")):
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )
        
        if not user.get("is_active"):
            raise HTTPException(
                status_code=403,
                detail="User account is inactive"
            )
        
        # Use new JWT token pair from PROMPT 1
        tokens = auth_service.generate_token_pair(user)
        logger.info(f"User logged in: {user['user_id']} with role {user['role']}")
        
        return UserLoginResponse(
            success=True,
            user_id=user["user_id"],
            role=user["role"],
            token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=int(__import__('os').getenv("JWT_EXPIRE_MINUTES", "60")) * 60,
            permissions=auth_service.get_permissions_for_role(user.get("role", "student")),
            assigned_sections=user.get("assigned_sections", []),
            message="Login successful"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/profile/{user_id}", response_model=UserProfileResponse)
def get_profile(user_id: str):
    """Get user profile by user ID."""
    try:
        user = user_repo.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserProfileResponse(
            user_id=user_id,
            name=user["name"],
            email=user["email"],
            role=user["role"],
            is_active=user.get("is_active", True),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/users/by-role/{role}")
def get_users_by_role(role: str):
    """Get all users by role (admin only)."""
    try:
        if role not in ["admin", "student"]:
            raise HTTPException(
                status_code=400,
                detail="Role must be 'admin' or 'student'"
            )
        
        users = user_repo.list_users_by_role(role)
        # Remove password hashes from response
        for user in users:
            user.pop("password_hash", None)
        
        return {
            "success": True,
            "role": role,
            "count": len(users),
            "users": users
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching users by role: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/forgot-password")
def forgot_password(email: str):
    """Generate password reset token and send email."""
    try:
        user = user_repo.get_user_by_email(email)
        # Always return success to prevent email enumeration
        if not user:
            return {
                "success": True,
                "message": "If email exists, password reset link will be sent"
            }
        
        reset_token = str(uuid.uuid4())
        reset_expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()
        
        user_repo.update_user(user.get("user_id"), {
            "reset_token": reset_token,
            "reset_expires": reset_expires
        })
        
        # Send email (async would be better but keeping simple for now)
        email_service.send_password_reset(email, reset_token)
        
        logger.info(f"Password reset requested for: {email}")
        return {
            "success": True,
            "message": "If email exists, password reset link will be sent"
        }
    except Exception as e:
        logger.error(f"Forgot password error: {e}")
        # Still return success to prevent email enumeration
        return {
            "success": True,
            "message": "If email exists, password reset link will be sent"
        }


@router.post("/reset-password")
def reset_password(token: str, new_password: str):
    """Reset password using token."""
    try:
        from database.firebase_client import FirebaseClient
        
        if len(new_password) < 6:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 6 characters"
            )
        
        fb = FirebaseClient()
        ref = fb.get_reference("users")
        users_data = ref.get() or {}
        
        user_id = None
        for uid, user_data in users_data.items():
            if isinstance(user_data, dict):
                if user_data.get("reset_token") == token:
                    reset_expires = user_data.get("reset_expires")
                    if reset_expires:
                        try:
                            expires_dt = datetime.fromisoformat(reset_expires)
                            if expires_dt > datetime.utcnow():
                                user_id = uid
                                break
                        except:
                            pass
        
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired reset token"
            )
        
        hashed_password = auth_service.hash_password(new_password)
        user_repo.update_user(user_id, {
            "password_hash": hashed_password,
            "reset_token": None,
            "reset_expires": None
        })
        
        logger.info(f"Password reset successful for user: {user_id}")
        return {
            "success": True,
            "message": "Password reset successfully. You can now login with your new password."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset password error: {e}")
        raise HTTPException(status_code=400, detail="Password reset failed")
