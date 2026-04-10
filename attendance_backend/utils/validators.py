"""
Input validation utilities.

Provides validation functions for API inputs, image data, and parameters.
"""

from typing import Optional, Any, List
import logging
import re

import numpy as np


logger = logging.getLogger(__name__)


class Validators:
    """
    Input validation utilities for the API.
    
    Provides methods to validate various input types and formats.
    """
    
    @staticmethod
    def validate_student_id(student_id: Any) -> bool:
        """
        Validate student ID format.
        
        Args:
            student_id: Student ID to validate
        
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(student_id, str):
            return False
        
        # Allow alphanumeric with hyphens and underscores
        pattern = r'^[a-zA-Z0-9_-]{3,20}$'
        return bool(re.match(pattern, student_id))
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validate email address.
        
        Args:
            email: Email address to validate
        
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(email, str):
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_course_id(course_id: str) -> bool:
        """
        Validate course ID format.
        
        Args:
            course_id: Course ID to validate
        
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(course_id, str):
            return False
        
        pattern = r'^[a-zA-Z0-9_-]{3,20}$'
        return bool(re.match(pattern, course_id))
    
    @staticmethod
    def validate_confidence_score(score: float) -> bool:
        """
        Validate confidence score (must be 0-1).
        
        Args:
            score: Confidence score
        
        Returns:
            True if valid, False otherwise
        """
        try:
            score = float(score)
            return 0.0 <= score <= 1.0
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def validate_embedding(embedding: Any) -> bool:
        """
        Validate face embedding.
        
        Args:
            embedding: Embedding to validate
        
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(embedding, (list, np.ndarray)):
            return False
        
        try:
            arr = np.array(embedding, dtype=np.float32)
            return arr.shape == (128,)  # FaceNet embedding dimension
        except Exception:
            return False
    
    @staticmethod
    def validate_bounding_box(bbox: Any) -> bool:
        """
        Validate bounding box coordinates.
        
        Args:
            bbox: Bounding box (x1, y1, x2, y2)
        
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(bbox, (list, tuple)):
            return False
        
        if len(bbox) != 4:
            return False
        
        try:
            x1, y1, x2, y2 = bbox
            x1, y1, x2, y2 = float(x1), float(y1), float(x2), float(y2)
            
            # Check ordering and minimum size
            if x1 >= x2 or y1 >= y2:
                return False
            
            if (x2 - x1) < 10 or (y2 - y1) < 10:  # Minimum 10x10px
                return False
            
            return True
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def validate_image_size(width: int, height: int) -> bool:
        """
        Validate image dimensions.
        
        Args:
            width: Image width in pixels
            height: Image height in pixels
        
        Returns:
            True if valid, False otherwise
        """
        try:
            width = int(width)
            height = int(height)
            
            # Check reasonable bounds
            if width < 10 or height < 10:
                return False
            
            if width > 8192 or height > 8192:  # Prevent memory issues
                return False
            
            return True
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def validate_base64_image(base64_str: str) -> bool:
        """
        Validate base64 encoded image.
        
        Args:
            base64_str: Base64 encoded image string
        
        Returns:
            True if valid format, False otherwise
        """
        if not isinstance(base64_str, str):
            return False
        
        if len(base64_str) == 0:
            return False
        
        # Check if string is valid base64 (basic check)
        if not re.match(r'^[A-Za-z0-9+/]*={0,2}$', base64_str):
            return False
        
        # Check length (rough estimate)
        if len(base64_str) < 100:  # Too short for an image
            return False
        
        return True
    
    @staticmethod
    def validate_timestamp(timestamp: Any) -> bool:
        """
        Validate timestamp format.
        
        Args:
            timestamp: Timestamp to validate
        
        Returns:
            True if valid, False otherwise
        """
        if isinstance(timestamp, (int, float)):
            # Unix timestamp
            return 0 < timestamp < 2**32  # Reasonable range
        
        if isinstance(timestamp, str):
            # ISO format or similar
            try:
                # Accept common formats
                patterns = [
                    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',  # ISO
                    r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',  # Common
                ]
                return any(re.match(p, timestamp) for p in patterns)
            except Exception:
                return False
        
        return False
    
    @staticmethod
    def validate_page_size(page_size: int, max_size: int = 100) -> bool:
        """
        Validate pagination page size.
        
        Args:
            page_size: Page size value
            max_size: Maximum allowed page size
        
        Returns:
            True if valid, False otherwise
        """
        try:
            page_size = int(page_size)
            return 1 <= page_size <= max_size
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def validate_date_range(start_date: str, end_date: str) -> bool:
        """
        Validate date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
        
        Returns:
            True if valid, False otherwise
        """
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        
        if not (isinstance(start_date, str) and isinstance(end_date, str)):
            return False
        
        if not (re.match(date_pattern, start_date) and re.match(date_pattern, end_date)):
            return False
        
        return start_date <= end_date
    
    @staticmethod
    def validate_request_body(data: dict, required_fields: List[str]) -> tuple:
        """
        Validate request body has required fields.
        
        Args:
            data: Request body dictionary
            required_fields: List of required field names
        
        Returns:
            Tuple of (is_valid, missing_fields)
        """
        if not isinstance(data, dict):
            return False, ["Request body must be a JSON object"]
        
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return False, missing_fields
        
        return True, []
    
    @staticmethod
    def sanitize_input(user_input: str, max_length: int = 500) -> str:
        """
        Sanitize user input string.
        
        Args:
            user_input: Raw user input
            max_length: Maximum allowed length
        
        Returns:
            Sanitized string
        """
        if not isinstance(user_input, str):
            return ""
        
        # Truncate
        user_input = user_input[:max_length]
        
        # Remove null bytes
        user_input = user_input.replace('\0', '')
        
        # Remove excessive whitespace
        user_input = ' '.join(user_input.split())
        
        return user_input
