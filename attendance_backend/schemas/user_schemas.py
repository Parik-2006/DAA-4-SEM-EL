"""
User registration and authentication schemas.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional

class UserRole(str):
    ADMIN = "admin"
    STUDENT = "student"

class UserRegistrationRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password")
    name: str = Field(..., min_length=2, max_length=100, description="Full name")
    role: str = Field(..., description="User role: 'admin' or 'student'")

class UserRegistrationResponse(BaseModel):
    success: bool
    user_id: str
    message: Optional[str] = None

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserLoginResponse(BaseModel):
    success: bool
    user_id: str
    role: str
    token: Optional[str] = None
    message: Optional[str] = None

class UserProfileResponse(BaseModel):
    user_id: str
    name: str
    email: str
    role: str
    is_active: bool = True
