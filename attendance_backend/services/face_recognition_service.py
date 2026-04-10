"""
Face Recognition Service for matching detected faces.

Handles embedding extraction and similarity matching using FAISS.
"""

from typing import List, Tuple, Optional, Dict, Any
import logging

import numpy as np

from models.model_manager import ModelManager
from utils.embedding_search import EmbeddingSearch
from utils.preprocessing import ImagePreprocessor
from config.constants import FACE_RECOGNITION_THRESHOLD


logger = logging.getLogger(__name__)


class FaceRecognitionService:
    """
    Face Recognition Service.
    
    Extracts embeddings from face images and matches them against
    enrolled student embeddings using FAISS indexing.
    """
    
    def __init__(self):
        """Initialize face recognition service."""
        self.extractor = None
        self.search_engine = EmbeddingSearch(use_faiss=True, metric="cosine")
        self.preprocessor = ImagePreprocessor()
    
    def ensure_extractor_loaded(self) -> None:
        """Ensure extractor model is loaded."""
        if self.extractor is None:
            try:
                self.extractor = ModelManager.get_facenet_extractor()
            except RuntimeError:
                logger.error("Failed to load extractor model")
                raise
    
    def extract_embedding(self, face_image: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract embedding from face image.
        
        Args:
            face_image: Face image (should be ~160x160)
        
        Returns:
            Embedding vector (128-dim) or None if extraction fails
        """
        try:
            self.ensure_extractor_loaded()
            
            # Preprocess face image
            processed_face = self.preprocessor.resize_image(
                face_image,
                target_size=(160, 160),
                keep_aspect=False
            )
            
            # Extract embedding
            embedding = self.extractor.extract_embedding(
                processed_face,
                normalize=True
            )
            
            return embedding
        
        except Exception as e:
            logger.error(f"Embedding extraction failed: {e}")
            return None
    
    def extract_batch_embeddings(
        self,
        face_images: List[np.ndarray]
    ) -> np.ndarray:
        """
        Extract embeddings from multiple faces.
        
        Args:
            face_images: List of face images
        
        Returns:
            Array of embeddings (N x 128)
        """
        try:
            self.ensure_extractor_loaded()
            return self.extractor.extract_batch_embeddings(
                face_images,
                normalize=True
            )
        except Exception as e:
            logger.error(f"Batch embedding extraction failed: {e}")
            return np.array([])
    
    def recognize_face(
        self,
        face_embedding: np.ndarray,
        threshold: Optional[float] = None
    ) -> Optional[Tuple[str, float]]:
        """
        Recognize face using embedding.
        
        Args:
            face_embedding: Face embedding vector
            threshold: Similarity threshold
        
        Returns:
            Tuple of (student_id, similarity_score) or None if no match
        """
        try:
            threshold = threshold or FACE_RECOGNITION_THRESHOLD
            
            # Search for matching embedding
            match = self.search_engine.search_single_match(
                face_embedding,
                threshold=threshold
            )
            
            if match:
                index, similarity = match
                student_info = self.search_engine.get_student_info(index)
                
                if student_info:
                    student_id = student_info.get('student_id')
                    logger.debug(f"Face recognized as {student_id} (score: {similarity:.3f})")
                    return student_id, similarity
            
            logger.debug("No matching face found")
            return None
        
        except Exception as e:
            logger.error(f"Face recognition failed: {e}")
            return None
    
    def recognize_batch_faces(
        self,
        face_embeddings: np.ndarray,
        threshold: Optional[float] = None
    ) -> List[Optional[Tuple[str, float]]]:
        """
        Recognize multiple faces.
        
        Args:
            face_embeddings: Array of embeddings (N x 128)
            threshold: Similarity threshold
        
        Returns:
            List of recognition results
        """
        results = []
        
        for embedding in face_embeddings:
            result = self.recognize_face(embedding, threshold)
            results.append(result)
        
        return results
    
    def build_index(self, embeddings: np.ndarray, metadata: Dict[int, Dict]) -> None:
        """
        Build search index from student embeddings.
        
        Args:
            embeddings: Array of student embeddings (N x 128)
            metadata: Metadata mapping index to student info
        """
        try:
            self.search_engine.build_index(embeddings, metadata, normalize=True)
            logger.info(f"Built recognition index with {len(embeddings)} faces")
        except Exception as e:
            logger.error(f"Failed to build index: {e}")
            raise
    
    def add_student_embedding(
        self,
        student_id: str,
        embedding: np.ndarray,
        student_info: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add student embedding to index.
        
        Args:
            student_id: Student identifier
            embedding: Student's face embedding
            student_info: Additional student metadata
        
        Returns:
            True if successful
        """
        try:
            info = student_info or {'student_id': student_id}
            info['student_id'] = student_id
            
            self.search_engine.add_embedding(embedding, info, normalize=True)
            logger.info(f"Added embedding for student {student_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to add student embedding: {e}")
            return False
    
    def save_index(self, index_path: str, metadata_path: str) -> bool:
        """
        Save index to disk.
        
        Args:
            index_path: Path to save index
            metadata_path: Path to save metadata
        
        Returns:
            True if successful
        """
        try:
            self.search_engine.save_index(index_path, metadata_path)
            return True
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            return False
    
    def load_index(self, index_path: str, metadata_path: str) -> bool:
        """
        Load index from disk.
        
        Args:
            index_path: Path to loaded index
            metadata_path: Path to loaded metadata
        
        Returns:
            True if successful
        """
        try:
            self.search_engine.load_index(index_path, metadata_path)
            logger.info("Index loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            return False
    
    def get_index_stats(self) -> dict:
        """
        Get index statistics.
        
        Returns:
            Dictionary with stats
        """
        return self.search_engine.get_index_stats()
    
    def get_recognition_stats(self) -> dict:
        """
        Get recognition model statistics.
        
        Returns:
            Dictionary with model info
        """
        try:
            self.ensure_extractor_loaded()
            return self.extractor.get_model_info()
        except Exception as e:
            logger.error(f"Error getting recognition stats: {e}")
            return {}
