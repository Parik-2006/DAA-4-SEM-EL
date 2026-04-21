"""
User data repository for admin and student users.
"""
from typing import Optional, Dict, Any, List
from config.constants import FIREBASE_COLLECTIONS
from database.firebase_client import FirebaseClient
import logging

logger = logging.getLogger(__name__)

class UserRepository:
    def __init__(self, db: Optional[FirebaseClient] = None):
        self.db = db or FirebaseClient()
        self.collection = FIREBASE_COLLECTIONS.get('users', 'users')

    def create_user(self, user_id: str, user_data: Dict[str, Any]) -> bool:
        """Create a new user."""
        path = f"{self.collection}/{user_id}"
        try:
            self.db.write_data(path, user_data)
            logger.info(f"User created: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return False

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email address."""
        path = self.collection
        try:
            users = self.db.read_data(path)
            if users and isinstance(users, dict):
                for user_id, user in users.items():
                    if isinstance(user, dict) and user.get('email') == email:
                        return {**user, 'user_id': user_id}
            return None
        except Exception as e:
            logger.error(f"Error fetching user by email: {e}")
            return None

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        path = f"{self.collection}/{user_id}"
        try:
            user = self.db.read_data(path)
            if user:
                return {**user, 'user_id': user_id}
            return None
        except Exception as e:
            logger.error(f"Error fetching user {user_id}: {e}")
            return None

    def update_user(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        """Update user data."""
        path = f"{self.collection}/{user_id}"
        try:
            user = self.db.read_data(path)
            if user:
                updated_user = {**user, **update_data}
                self.db.write_data(path, updated_user)
                logger.info(f"User updated: {user_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return False

    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        path = f"{self.collection}/{user_id}"
        try:
            self.db.delete_data(path)
            logger.info(f"User deleted: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False

    def list_users_by_role(self, role: str) -> List[Dict[str, Any]]:
        """List all users with a specific role."""
        path = self.collection
        try:
            users = self.db.read_data(path)
            result = []
            if users and isinstance(users, dict):
                for user_id, user in users.items():
                    if isinstance(user, dict) and user.get('role') == role:
                        result.append({**user, 'user_id': user_id})
            return result
        except Exception as e:
            logger.error(f"Error listing users by role {role}: {e}")
            return []

    def list_all_users(self) -> List[Dict[str, Any]]:
        """List all users."""
        path = self.collection
        try:
            users = self.db.read_data(path)
            result = []
            if users and isinstance(users, dict):
                for user_id, user in users.items():
                    if isinstance(user, dict):
                        result.append({**user, 'user_id': user_id})
            return result
        except Exception as e:
            logger.error(f"Error listing all users: {e}")
            return []
