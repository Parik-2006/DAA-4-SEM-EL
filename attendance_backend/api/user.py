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
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user", tags=["user"])
user_repo = UserRepository()
auth_service = AuthService()

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
    """Login a user (admin or student)."""
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
        
        token = auth_service.generate_token()
        logger.info(f"User logged in: {user['user_id']} with role {user['role']}")
        
        return UserLoginResponse(
            success=True,
            user_id=user["user_id"],
            role=user["role"],
            token=token,
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
