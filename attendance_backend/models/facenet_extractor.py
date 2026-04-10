"""
FaceNet Embedding Extractor Model.

This module provides a wrapper around FaceNet for extracting face embeddings,
which are used for face recognition via similarity matching.
"""

from pathlib import Path
from typing import List, Optional, Union
import logging

import cv2
import numpy as np
import torch
from facenet_pytorch import InceptionResnetV1

from config.settings import get_settings
from config.constants import FACE_EMBEDDING_DIM


logger = logging.getLogger(__name__)


class FaceNetExtractor:
    """
    FaceNet Embedding Extractor.
    
    Extracts 128-dimensional embeddings from face images using the
    InceptionResnetV1 architecture pre-trained on VGGFace2.
    
    Attributes:
        model: FaceNet model instance
        device: Device to run inference on (cuda or cpu)
        embedding_dim: Dimension of output embeddings (typically 128)
    """
    
    def __init__(
        self,
        pretrained: bool = True,
        device: str = "cpu"
    ):
        """
        Initialize FaceNet extractor.
        
        Args:
            pretrained: Load pre-trained VGGFace2 weights (recommended)
            device: Device to run inference on ('cuda', 'cpu', or number)
        
        Raises:
            RuntimeError: If model loading fails
        """
        self.device = device
        self.embedding_dim = FACE_EMBEDDING_DIM
        self.model = None
        
        self._load_model(pretrained)
    
    def _load_model(self, pretrained: bool) -> None:
        """
        Load FaceNet model.
        
        Args:
            pretrained: Load pre-trained weights
        
        Raises:
            RuntimeError: If model loading fails
        """
        try:
            logger.info(f"Loading FaceNet model (pretrained={pretrained})")
            
            # Load InceptionResnetV1 model
            self.model = InceptionResnetV1(
                pretrained='vggface2' if pretrained else None,
                classify=False,  # Use embedding mode (not classification)
                num_classes=None,
                dropout_p=0.5,
                device=self.device
            )
            
            # Set to evaluation mode (disables dropout)
            self.model.eval()
            
            logger.info("FaceNet model loaded successfully")
        
        except Exception as e:
            logger.error(f"Failed to load FaceNet model: {e}")
            raise RuntimeError(f"Model loading failed: {e}")
    
    def extract_embedding(
        self,
        face_image: np.ndarray,
        normalize: bool = True
    ) -> np.ndarray:
        """
        Extract embedding from a single face image.
        
        Args:
            face_image: Face image (BGR or RGB, should be 160x160 for FaceNet)
            normalize: L2 normalize the embedding
        
        Returns:
            Face embedding (128-dimensional vector)
        
        Raises:
            ValueError: If image is invalid
            RuntimeError: If embedding extraction fails
        """
        if face_image is None or face_image.size == 0:
            raise ValueError("Invalid face image provided")
        
        try:
            # Prepare image tensor
            image_tensor = self._prepare_image(face_image)
            
            # Extract embedding
            with torch.no_grad():
                embedding = self.model(image_tensor)
            
            # Convert to numpy
            embedding = embedding.cpu().numpy().squeeze()
            
            # L2 normalization (optional but recommended for similarity matching)
            if normalize:
                embedding = embedding / np.linalg.norm(embedding)
            
            return embedding.astype(np.float32)
        
        except Exception as e:
            logger.error(f"Embedding extraction failed: {e}")
            raise RuntimeError(f"Extraction failed: {e}")
    
    def extract_batch_embeddings(
        self,
        face_images: List[np.ndarray],
        normalize: bool = True
    ) -> np.ndarray:
        """
        Extract embeddings from multiple face images.
        
        Args:
            face_images: List of face images
            normalize: L2 normalize embeddings
        
        Returns:
            Array of embeddings (N x 128)
        """
        embeddings = []
        
        for face_image in face_images:
            try:
                embedding = self.extract_embedding(face_image, normalize)
                embeddings.append(embedding)
            except Exception as e:
                logger.warning(f"Skipped embedding extraction for one image: {e}")
                # Add zero embedding as placeholder
                embeddings.append(np.zeros(FACE_EMBEDDING_DIM, dtype=np.float32))
        
        return np.array(embeddings, dtype=np.float32)
    
    def _prepare_image(self, image: np.ndarray) -> torch.Tensor:
        """
        Prepare image for FaceNet inference.
        
        FaceNet expects:
        - Size: 160x160
        - Normalized to [-1, 1] or [0, 1]
        - Channels: RGB (not BGR)
        
        Args:
            image: Input image (BGR or grayscale)
        
        Returns:
            Prepared tensor (1 x 3 x 160 x 160)
        """
        # Convert BGR to RGB if needed
        if len(image.shape) == 2:
            # Grayscale to RGB
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.shape[2] == 3:
            # BGR to RGB
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Resize to 160x160 (FaceNet standard input)
        image = cv2.resize(image, (160, 160), interpolation=cv2.INTER_LINEAR)
        
        # Normalize to [0, 1]
        image = image.astype(np.float32) / 255.0
        
        # Convert to tensor and add batch dimension
        tensor = torch.from_numpy(image).unsqueeze(0)
        
        # Permute to (B, C, H, W)
        tensor = tensor.permute(0, 3, 1, 2)
        
        # Move to device
        tensor = tensor.to(self.device)
        
        return tensor
    
    def get_embedding_dim(self) -> int:
        """
        Get embedding dimension.
        
        Returns:
            Embedding dimension (128 for FaceNet)
        """
        return self.embedding_dim
    
    def get_model_info(self) -> dict:
        """
        Get model information.
        
        Returns:
            Dictionary with model metadata
        """
        return {
            "model_type": "FaceNet (InceptionResnetV1)",
            "embedding_dim": self.embedding_dim,
            "device": str(self.device),
            "dataset": "VGGFace2",
        }
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        if self.model is not None:
            try:
                del self.model
                logger.debug("FaceNet model cleaned up")
            except Exception as e:
                logger.warning(f"Error during model cleanup: {e}")
