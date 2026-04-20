"""
Firebase Cloud Storage service for Smart Attendance System.

Handles image uploads, downloads, and management for students and attendance records.
"""

import logging
import io
from pathlib import Path
from typing import Optional, BinaryIO
from datetime import datetime

try:
    import firebase_admin
    from firebase_admin import credentials, storage
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

logger = logging.getLogger(__name__)


class FirebaseStorageService:
    """Firebase Cloud Storage service for managing files."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.bucket = None
    
    @classmethod
    def initialize(
        cls,
        credentials_path: str,
        storage_bucket: str
    ) -> 'FirebaseStorageService':
        """
        Initialize Firebase Storage service.
        
        Args:
            credentials_path: Path to Firebase credentials JSON
            storage_bucket: Firebase Storage bucket name (e.g., 'project.appspot.com')
        
        Returns:
            FirebaseStorageService instance
        """
        if not FIREBASE_AVAILABLE:
            raise RuntimeError("Firebase Admin SDK not installed")
        
        service = cls()
        
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(credentials_path)
                firebase_admin.initialize_app(cred)
            
            service.bucket = storage.bucket(storage_bucket)
            logger.info(f"Firebase Storage initialized: {storage_bucket}")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Storage: {e}")
            raise
        
        return service
    
    # ============ Upload Operations ============
    
    def upload_file(
        self,
        local_path: str,
        remote_path: str
    ) -> str:
        """
        Upload a file to Firebase Storage.
        
        Args:
            local_path: Path to local file
            remote_path: Remote path in storage (e.g., 'students/S001/avatar.jpg')
        
        Returns:
            Public URL of uploaded file
        """
        try:
            blob = self.bucket.blob(remote_path)
            blob.upload_from_filename(local_path)
            blob.make_public()
            
            logger.info(f"File uploaded: {remote_path}")
            return blob.public_url
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            raise
    
    def upload_bytes(
        self,
        file_bytes: bytes,
        remote_path: str,
        content_type: str = 'application/octet-stream'
    ) -> str:
        """
        Upload file from bytes.
        
        Args:
            file_bytes: File content as bytes
            remote_path: Remote path in storage
            content_type: MIME type
        
        Returns:
            Public URL of uploaded file
        """
        try:
            blob = self.bucket.blob(remote_path)
            blob.upload_from_string(file_bytes, content_type=content_type)
            blob.make_public()
            
            logger.info(f"File uploaded from bytes: {remote_path}")
            return blob.public_url
        except Exception as e:
            logger.error(f"Error uploading bytes: {e}")
            raise
    
    def upload_image(
        self,
        image_path: str,
        student_id: str,
        image_type: str = 'avatar'
    ) -> str:
        """
        Upload a student image (avatar or photo).
        
        Args:
            image_path: Path to image file
            student_id: Student ID
            image_type: Type of image ('avatar' or 'photo')
        
        Returns:
            Public URL of uploaded image
        """
        try:
            file_ext = Path(image_path).suffix
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            remote_path = f'students/{student_id}/{image_type}_{timestamp}{file_ext}'
            
            return self.upload_file(image_path, remote_path)
        except Exception as e:
            logger.error(f"Error uploading image: {e}")
            raise
    
    def upload_attendance_photo(
        self,
        image_path: str,
        attendance_id: str
    ) -> str:
        """
        Upload an attendance photo.
        
        Args:
            image_path: Path to image file
            attendance_id: Attendance record ID
        
        Returns:
            Public URL of uploaded image
        """
        try:
            file_ext = Path(image_path).suffix
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            remote_path = f'attendance/{attendance_id}/photo_{timestamp}{file_ext}'
            
            return self.upload_file(image_path, remote_path)
        except Exception as e:
            logger.error(f"Error uploading attendance photo: {e}")
            raise
    
    # ============ Download Operations ============
    
    def download_file(
        self,
        remote_path: str,
        local_path: str
    ) -> None:
        """
        Download a file from Firebase Storage.
        
        Args:
            remote_path: Remote path in storage
            local_path: Local path to save file
        """
        try:
            blob = self.bucket.blob(remote_path)
            blob.download_to_filename(local_path)
            logger.info(f"File downloaded: {remote_path}")
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            raise
    
    def download_as_bytes(self, remote_path: str) -> bytes:
        """
        Download file as bytes.
        
        Args:
            remote_path: Remote path in storage
        
        Returns:
            File content as bytes
        """
        try:
            blob = self.bucket.blob(remote_path)
            return blob.download_as_bytes()
        except Exception as e:
            logger.error(f"Error downloading bytes: {e}")
            raise
    
    def get_public_url(self, remote_path: str) -> str:
        """Get public URL for a file."""
        try:
            blob = self.bucket.blob(remote_path)
            blob.make_public()
            return blob.public_url
        except Exception as e:
            logger.error(f"Error getting public URL: {e}")
            raise
    
    # ============ Delete Operations ============
    
    def delete_file(self, remote_path: str) -> None:
        """Delete a file from Firebase Storage."""
        try:
            blob = self.bucket.blob(remote_path)
            blob.delete()
            logger.info(f"File deleted: {remote_path}")
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            raise
    
    def delete_folder(self, folder_path: str) -> int:
        """
        Delete all files in a folder.
        
        Args:
            folder_path: Folder path (e.g., 'students/S001/')
        
        Returns:
            Number of files deleted
        """
        try:
            blobs = self.bucket.list_blobs(prefix=folder_path)
            count = 0
            for blob in blobs:
                blob.delete()
                count += 1
            
            logger.info(f"Deleted {count} files from {folder_path}")
            return count
        except Exception as e:
            logger.error(f"Error deleting folder: {e}")
            raise
    
    # ============ List Operations ============
    
    def list_files(self, prefix: str = '', delimiter: str = '/'):
        """List files in a directory."""
        try:
            return self.bucket.list_blobs(prefix=prefix, delimiter=delimiter)
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            raise
    
    def get_student_files(self, student_id: str) -> list:
        """Get all files for a student."""
        try:
            prefix = f'students/{student_id}/'
            blobs = list(self.bucket.list_blobs(prefix=prefix))
            return [
                {
                    'name': blob.name,
                    'url': blob.public_url,
                    'size': blob.size,
                    'updated': blob.updated,
                }
                for blob in blobs
            ]
        except Exception as e:
            logger.error(f"Error getting student files: {e}")
            raise
