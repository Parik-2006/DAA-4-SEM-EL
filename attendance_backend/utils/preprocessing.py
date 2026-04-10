"""
Image preprocessing utilities.

Provides functions for image normalization, face alignment, color conversion,
and other image processing operations required for face recognition.
"""

from typing import Tuple, Optional
import logging

import cv2
import numpy as np


logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """
    Image preprocessing utilities for face recognition pipeline.
    
    Handles image normalization, resizing, color conversion, and
    face region extraction.
    """
    
    @staticmethod
    def load_image(image_path: str) -> Optional[np.ndarray]:
        """
        Load image from file.
        
        Args:
            image_path: Path to image file
        
        Returns:
            Image as numpy array (BGR format) or None if load fails
        """
        try:
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"Failed to load image: {image_path}")
                return None
            return image
        except Exception as e:
            logger.error(f"Error loading image {image_path}: {e}")
            return None
    
    @staticmethod
    def resize_image(
        image: np.ndarray,
        target_size: Tuple[int, int] = (640, 640),
        keep_aspect: bool = True
    ) -> np.ndarray:
        """
        Resize image to target size.
        
        Args:
            image: Input image
            target_size: Target (width, height)
            keep_aspect: Keep aspect ratio by padding if True
        
        Returns:
            Resized image
        """
        if keep_aspect:
            return ImagePreprocessor._resize_with_padding(image, target_size)
        else:
            return cv2.resize(image, target_size, interpolation=cv2.INTER_LINEAR)
    
    @staticmethod
    def _resize_with_padding(
        image: np.ndarray,
        target_size: Tuple[int, int]
    ) -> np.ndarray:
        """
        Resize image while keeping aspect ratio and add padding.
        
        Args:
            image: Input image
            target_size: Target (width, height)
        
        Returns:
            Resized image with padding
        """
        h, w = image.shape[:2]
        target_w, target_h = target_size
        
        # Calculate scaling factor
        scale = min(target_w / w, target_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        # Resize image
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # Create canvas with padding
        canvas = np.zeros((target_h, target_w, image.shape[2]), dtype=image.dtype)
        
        # Calculate padding
        pad_top = (target_h - new_h) // 2
        pad_left = (target_w - new_w) // 2
        
        # Place resized image on canvas
        canvas[pad_top:pad_top + new_h, pad_left:pad_left + new_w] = resized
        
        return canvas
    
    @staticmethod
    def bgr_to_rgb(image: np.ndarray) -> np.ndarray:
        """
        Convert BGR image to RGB.
        
        Args:
            image: Image in BGR format
        
        Returns:
            Image in RGB format
        """
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    @staticmethod
    def rgb_to_bgr(image: np.ndarray) -> np.ndarray:
        """
        Convert RGB image to BGR.
        
        Args:
            image: Image in RGB format
        
        Returns:
            Image in BGR format
        """
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    
    @staticmethod
    def to_grayscale(image: np.ndarray) -> np.ndarray:
        """
        Convert image to grayscale.
        
        Args:
            image: Input image (BGR or RGB)
        
        Returns:
            Grayscale image
        """
        if len(image.shape) == 2:
            return image  # Already grayscale
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    @staticmethod
    def normalize_image(image: np.ndarray, to_range: Tuple[int, int] = (0, 1)) -> np.ndarray:
        """
        Normalize image pixel values.
        
        Args:
            image: Input image
            to_range: Target range (min, max)
        
        Returns:
            Normalized image
        """
        image = image.astype(np.float32)
        
        if to_range == (0, 1):
            return image / 255.0
        elif to_range == (-1, 1):
            return (image / 127.5) - 1.0
        else:
            min_val, max_val = to_range
            current_min = image.min()
            current_max = image.max()
            
            if current_max == current_min:
                return image
            
            normalized = (image - current_min) / (current_max - current_min)
            return normalized * (max_val - min_val) + min_val
    
    @staticmethod
    def extract_face_region(
        image: np.ndarray,
        bbox: Tuple[float, float, float, float],
        padding_percent: float = 0.2
    ) -> np.ndarray:
        """
        Extract face region from image with optional padding.
        
        Args:
            image: Input image
            bbox: Bounding box (x1, y1, x2, y2)
            padding_percent: Percentage padding around face (0.2 = 20%)
        
        Returns:
            Extracted face region
        """
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h, w = image.shape[:2]
        
        # Calculate padding
        pad_x = int((x2 - x1) * padding_percent)
        pad_y = int((y2 - y1) * padding_percent)
        
        # Apply padding with bounds checking
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(w, x2 + pad_x)
        y2 = min(h, y2 + pad_y)
        
        return image[y1:y2, x1:x2]
    
    @staticmethod
    def draw_bbox(
        image: np.ndarray,
        bbox: Tuple[float, float, float, float],
        label: str = "",
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2
    ) -> np.ndarray:
        """
        Draw bounding box on image.
        
        Args:
            image: Input image
            bbox: Bounding box (x1, y1, x2, y2)
            label: Label text to display
            color: Box color (BGR)
            thickness: Line thickness
        
        Returns:
            Image with drawn bbox
        """
        x1, y1, x2, y2 = [int(v) for v in bbox]
        
        # Draw rectangle
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)
        
        # Draw label if provided
        if label:
            text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
            cv2.rectangle(
                image,
                (x1, y1 - text_size[1] - 5),
                (x1 + text_size[0] + 5, y1),
                color,
                -1
            )
            cv2.putText(
                image,
                label,
                (x1 + 2, y1 - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                1
            )
        
        return image
    
    @staticmethod
    def get_image_info(image: np.ndarray) -> dict:
        """
        Get image metadata.
        
        Args:
            image: Input image
        
        Returns:
            Dictionary with image info
        """
        h, w = image.shape[:2]
        channels = 1 if len(image.shape) == 2 else image.shape[2]
        
        return {
            "width": w,
            "height": h,
            "channels": channels,
            "dtype": str(image.dtype),
            "size_mb": image.nbytes / (1024 * 1024),
        }
