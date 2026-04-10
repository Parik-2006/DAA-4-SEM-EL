"""
Image I/O and encoding utilities.

Provides utilities for image loading, saving, encoding/decoding,
and format conversion.
"""

from pathlib import Path
from typing import Optional, List
import logging
import base64
import io

import cv2
import numpy as np
from PIL import Image


logger = logging.getLogger(__name__)


class ImageUtils:
    """
    Utilities for image I/O operations.
    
    Handles loading, saving, encoding/decoding images in various formats.
    """
    
    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif'}
    
    @staticmethod
    def load_image(image_path: str) -> Optional[np.ndarray]:
        """
        Load image from file.
        
        Args:
            image_path: Path to image file
        
        Returns:
            Image as numpy array (BGR) or None if failed
        """
        try:
            path = Path(image_path)
            
            if not path.exists():
                raise FileNotFoundError(f"Image file not found: {image_path}")
            
            if path.suffix.lower() not in ImageUtils.SUPPORTED_FORMATS:
                raise ValueError(f"Unsupported image format: {path.suffix}")
            
            image = cv2.imread(str(path))
            
            if image is None:
                raise ValueError(f"Failed to decode image: {image_path}")
            
            logger.debug(f"Loaded image: {image_path}, shape: {image.shape}")
            return image
        
        except Exception as e:
            logger.error(f"Error loading image {image_path}: {e}")
            return None
    
    @staticmethod
    def save_image(image: np.ndarray, output_path: str) -> bool:
        """
        Save image to file.
        
        Args:
            image: Image array
            output_path: Path to save image
        
        Returns:
            True if successful, False otherwise
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            success = cv2.imwrite(str(output_path), image)
            
            if success:
                logger.debug(f"Saved image to {output_path}")
            else:
                logger.error(f"Failed to save image: {output_path}")
            
            return success
        
        except Exception as e:
            logger.error(f"Error saving image {output_path}: {e}")
            return False
    
    @staticmethod
    def encode_to_base64(image: np.ndarray, format: str = '.jpg') -> str:
        """
        Encode image to base64 string.
        
        Args:
            image: Image array (BGR)
            format: Image format ('.jpg' or '.png')
        
        Returns:
            Base64 encoded string
        """
        try:
            # Encode image
            success, buffer = cv2.imencode(format, image)
            
            if not success:
                raise ValueError(f"Failed to encode image to {format}")
            
            # Convert to base64
            base64_string = base64.b64encode(buffer).decode('utf-8')
            return base64_string
        
        except Exception as e:
            logger.error(f"Error encoding image to base64: {e}")
            raise
    
    @staticmethod
    def decode_from_base64(base64_string: str) -> Optional[np.ndarray]:
        """
        Decode image from base64 string.
        
        Args:
            base64_string: Base64 encoded image string
        
        Returns:
            Image array (BGR) or None if failed
        """
        try:
            # Decode base64
            image_data = base64.b64decode(base64_string)
            
            # Convert to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            
            # Decode image
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                raise ValueError("Failed to decode image from base64")
            
            return image
        
        except Exception as e:
            logger.error(f"Error decoding base64 image: {e}")
            return None
    
    @staticmethod
    def encode_to_bytes(image: np.ndarray, format: str = '.jpg') -> bytes:
        """
        Encode image to bytes.
        
        Args:
            image: Image array (BGR)
            format: Image format ('.jpg' or '.png')
        
        Returns:
            Image as bytes
        """
        success, buffer = cv2.imencode(format, image)
        
        if not success:
            raise ValueError(f"Failed to encode image to {format}")
        
        return buffer.tobytes()
    
    @staticmethod
    def decode_from_bytes(image_bytes: bytes) -> Optional[np.ndarray]:
        """
        Decode image from bytes.
        
        Args:
            image_bytes: Image data as bytes
        
        Returns:
            Image array (BGR) or None if failed
        """
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return image if image is not None else None
    
    @staticmethod
    def convert_to_rgb(image: np.ndarray) -> np.ndarray:
        """
        Convert BGR image to RGB.
        
        Args:
            image: Image in BGR format
        
        Returns:
            Image in RGB format
        """
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    @staticmethod
    def convert_to_bgr(image: np.ndarray) -> np.ndarray:
        """
        Convert RGB image to BGR.
        
        Args:
            image: Image in RGB format
        
        Returns:
            Image in BGR format
        """
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    
    @staticmethod
    def get_image_shape(image: np.ndarray) -> tuple:
        """
        Get image dimensions.
        
        Args:
            image: Image array
        
        Returns:
            Tuple of (height, width, channels) or (height, width) for grayscale
        """
        return image.shape
    
    @staticmethod
    def batch_load_images(image_paths: List[str]) -> List[np.ndarray]:
        """
        Load multiple images.
        
        Args:
            image_paths: List of image file paths
        
        Returns:
            List of loaded images (skips failed images)
        """
        images = []
        
        for path in image_paths:
            image = ImageUtils.load_image(path)
            if image is not None:
                images.append(image)
        
        return images
    
    @staticmethod
    def pil_to_cv(pil_image: Image.Image) -> np.ndarray:
        """
        Convert PIL Image to OpenCV array (BGR).
        
        Args:
            pil_image: PIL Image object
        
        Returns:
            Image as numpy array (BGR)
        """
        # Convert RGBA to RGB if needed
        if pil_image.mode == 'RGBA':
            pil_image = pil_image.convert('RGB')
        
        # Convert to numpy array (RGB)
        image_array = np.array(pil_image)
        
        # Convert RGB to BGR
        image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
        
        return image_bgr
    
    @staticmethod
    def cv_to_pil(cv_image: np.ndarray) -> Image.Image:
        """
        Convert OpenCV array (BGR) to PIL Image.
        
        Args:
            cv_image: Image as numpy array (BGR)
        
        Returns:
            PIL Image object (RGB)
        """
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        
        # Convert to PIL
        pil_image = Image.fromarray(image_rgb)
        
        return pil_image
    
    @staticmethod
    def validate_image(image: np.ndarray) -> bool:
        """
        Validate image array.
        
        Args:
            image: Image array to validate
        
        Returns:
            True if valid, False otherwise
        """
        if image is None or image.size == 0:
            return False
        
        if len(image.shape) not in [2, 3]:  # Grayscale or color
            return False
        
        if image.dtype not in [np.uint8, np.float32, np.float64]:
            return False
        
        return True
