"""
Firebase Authentication utilities for backend API.

Provides JWT token validation and user authentication checks.
"""

import logging
from typing import Optional, Dict, Any
from functools import wraps

try:
    import firebase_admin
    from firebase_admin import auth
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class FirebaseAuthService:
    """Firebase Authentication service for backend."""
    
    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """
        Verify Firebase ID token.
        
        Args:
            token: Firebase ID token
        
        Returns:
            Decoded token claims
        
        Raises:
            HTTPException: If token is invalid
        """
        if not FIREBASE_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Firebase not available"
            )
        
        try:
            decoded_token = auth.verify_id_token(token)
            return decoded_token
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
    
    @staticmethod
    def get_user(uid: str) -> Dict[str, Any]:
        """
        Get user details by UID.
        
        Args:
            uid: Firebase user UID
        
        Returns:
            User details
        """
        if not FIREBASE_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Firebase not available"
            )
        
        try:
            user = auth.get_user(uid)
            return {
                'uid': user.uid,
                'email': user.email,
                'display_name': user.display_name,
                'photo_url': user.photo_url,
                'disabled': user.disabled,
            }
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            raise
    
    @staticmethod
    def create_user(
        email: str,
        password: str,
        display_name: Optional[str] = None
    ) -> str:
        """
        Create a new Firebase user.
        
        Args:
            email: User email
            password: User password
            display_name: Optional display name
        
        Returns:
            User UID
        """
        if not FIREBASE_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Firebase not available"
            )
        
        try:
            user = auth.create_user(
                email=email,
                password=password,
                display_name=display_name
            )
            logger.info(f"User created: {user.uid}")
            return user.uid
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise
    
    @staticmethod
    def delete_user(uid: str) -> None:
        """Delete a Firebase user."""
        if not FIREBASE_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Firebase not available"
            )
        
        try:
            auth.delete_user(uid)
            logger.info(f"User deleted: {uid}")
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            raise
