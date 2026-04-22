"""
Firebase Database Client.

Provides connection and initialization for Firebase Realtime Database
with error handling and retry logic.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
import time

import firebase_admin
from firebase_admin import credentials, db, initialize_app
from firebase_admin.exceptions import FirebaseError

from config.settings import get_settings
from config.constants import MAX_DATABASE_RETRIES, DATABASE_RETRY_DELAY


logger = logging.getLogger(__name__)


class FirebaseClient:
    """
    Firebase Realtime Database Client.
    
    Manages connection to Firebase with connection retry logic,
    error handling, and transaction management.
    """
    
    _instance: Optional['FirebaseClient'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'FirebaseClient':
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize Firebase client."""
        if self._initialized:
            return
        
        self.settings = get_settings()
        self.db = None
        self._initialize_connection()
    
    def _initialize_connection(self) -> None:
        """
        Initialize Firebase connection.
        
        Raises:
            RuntimeError: If connection fails
        """
        try:
            logger.info("Initializing Firebase connection...")
            
            # Check credentials file exists
            cred_path = self.settings.get_credentials_path()
            if not cred_path.exists():
                raise FileNotFoundError(
                    f"Firebase credentials file not found: {cred_path}"
                )
            
            # Load credentials
            cred = credentials.Certificate(str(cred_path))
            
            # Initialize Firebase
            initialize_app(
                cred,
                {
                    'databaseURL': self.settings.firebase_database_url
                }
            )
            
            self.db = db.reference()
            FirebaseClient._initialized = True
            
            logger.info("Firebase connection initialized successfully")
        
        except FileNotFoundError as e:
            logger.error(f"Credentials file error: {e}")
            raise RuntimeError(f"Firebase initialization failed: {e}")
        except FirebaseError as e:
            logger.error(f"Firebase error: {e}")
            raise RuntimeError(f"Firebase initialization failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during Firebase initialization: {e}")
            raise RuntimeError(f"Firebase initialization failed: {e}")
    
    def get_reference(self, path: str) -> db.Reference:
        """
        Get database reference for path.
        
        Args:
            path: Database path (e.g., 'students/S001')
        
        Returns:
            Firebase database reference
        
        Raises:
            RuntimeError: If connection not initialized
        """
        if self.db is None:
            raise RuntimeError("Firebase not initialized")
        
        return self.db.child(path)
    
    def write_data(
        self,
        path: str,
        data: Dict[str, Any],
        retry: int = 0
    ) -> bool:
        """
        Write data to database.
        
        Args:
            path: Database path
            data: Data to write
            retry: Retry count (internal)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            ref = self.get_reference(path)
            ref.set(data)
            logger.debug(f"Wrote data to {path}")
            return True
        
        except FirebaseError as e:
            if retry < MAX_DATABASE_RETRIES:
                logger.warning(f"Write failed, retrying... (attempt {retry + 1})")
                time.sleep(DATABASE_RETRY_DELAY * (2 ** retry))  # Exponential backoff
                return self.write_data(path, data, retry + 1)
            else:
                logger.error(f"Write failed after {MAX_DATABASE_RETRIES} retries: {e}")
                return False
        except Exception as e:
            logger.error(f"Error writing to {path}: {e}")
            return False
    
    def read_data(
        self,
        path: str,
        retry: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        Read data from database.
        
        Args:
            path: Database path
            retry: Retry count (internal)
        
        Returns:
            Data dictionary or None if failed
        """
        try:
            ref = self.get_reference(path)
            data = ref.get()
            if data is None:
                logger.debug(f"No data at {path}")
                return None

            logger.debug(f"Read data from {path}")
            return data
        
        except FirebaseError as e:
            if retry < MAX_DATABASE_RETRIES:
                logger.warning(f"Read failed, retrying... (attempt {retry + 1})")
                time.sleep(DATABASE_RETRY_DELAY * (2 ** retry))
                return self.read_data(path, retry + 1)
            else:
                logger.error(f"Read failed after {MAX_DATABASE_RETRIES} retries: {e}")
                return None
        except Exception as e:
            logger.error(f"Error reading from {path}: {e}")
            return None
    
    def update_data(self, path: str, data: Dict[str, Any]) -> bool:
        """
        Update existing data (shallow merge).
        
        Args:
            path: Database path
            data: Data to update
        
        Returns:
            True if successful, False otherwise
        """
        try:
            ref = self.get_reference(path)
            ref.update(data)
            logger.debug(f"Updated data at {path}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating {path}: {e}")
            return False
    
    def delete_data(self, path: str) -> bool:
        """
        Delete data from database.
        
        Args:
            path: Database path
        
        Returns:
            True if successful, False otherwise
        """
        try:
            ref = self.get_reference(path)
            ref.delete()
            logger.debug(f"Deleted data at {path}")
            return True
        
        except Exception as e:
            logger.error(f"Error deleting {path}: {e}")
            return False
    
    def list_children(self, path: str) -> Optional[List[str]]:
        """
        List child keys at path.
        
        Args:
            path: Database path
        
        Returns:
            List of child keys or None if failed
        """
        try:
            ref = self.get_reference(path)
            data = ref.get()
            if isinstance(data, dict):
                return list(data.keys())
            return []
        
        except Exception as e:
            logger.error(f"Error listing children at {path}: {e}")
            return None
    
    def transaction(self, path: str, update_fn) -> Any:
        """
        Perform transaction at path.
        
        Args:
            path: Database path
            update_fn: Function to apply in transaction
        
        Returns:
            Transaction result or None if failed
        """
        try:
            ref = self.get_reference(path)
            return ref.transaction(update_fn)
        
        except Exception as e:
            logger.error(f"Transaction failed at {path}: {e}")
            return None
    
    def get_connection_status(self) -> dict:
        """
        Get connection status.
        
        Returns:
            Dictionary with connection info
        """
        return {
            "initialized": self._initialized,
            "database_url": self.settings.firebase_database_url,
            "credentials_path": str(self.settings.get_credentials_path()),
        }
