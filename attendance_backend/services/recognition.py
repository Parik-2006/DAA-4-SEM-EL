"""
Face Recognition and Embedding Generation using FaceNet.

Generates 128-dimensional embeddings for detected faces using
FaceNet model (VGGFace2 pre-trained via facenet-pytorch).

Usage:
    recognizer = FaceRecognitionPipeline()
    embeddings = recognizer.generate_embeddings(faces)
"""

import cv2
import numpy as np
from typing import List, Tuple, Dict, Optional
import logging
from pathlib import Path

try:
    from facenet_pytorch import InceptionResnetV1, MTCNN
    import torch
except ImportError:
    raise ImportError(
        "facenet-pytorch not installed. Run: pip install facenet-pytorch"
    )


logger = logging.getLogger(__name__)


class FaceRecognitionPipeline:
    """
    Face recognition and embedding generation using FaceNet.
    
    Generates 128-dimensional embeddings for faces using VGGFace2
    pre-trained model via facenet-pytorch library.
    
    Attributes:
        embedding_size: Dimension of face embeddings (128 for FaceNet)
        device: Device to run inference on ('cpu' or 'cuda')
        model: FaceNet model instance
    """
    
    def __init__(
        self,
        model_name: str = "vggface2",
        device: str = "cpu",
        pretrained: bool = True
    ):
        """
        Initialize face recognition pipeline.
        
        Args:
            model_name: Model variant ('vggface2' or 'casia-webface')
            device: Device for inference ('cpu' or 'cuda')
            pretrained: Use pretrained weights
        """
        self.model_name = model_name
        self.device = device
        self.pretrained = pretrained
        self.embedding_size = 128
        self.model = None
        
        self._load_model()
    
    def _load_model(self) -> None:
        """
        Load FaceNet model.
        
        Downloads pre-trained weights automatically if not cached.
        """
        try:
            logger.info(f"Loading FaceNet model ({self.model_name})...")
            
            # Load FaceNet model
            self.model = InceptionResnetV1(
                pretrained=self.pretrained,
                num_classes=None,  # Output embeddings, not classification
                dropout_p=0.0,
                device=self.device
            )
            
            # Set to evaluation mode
            self.model.eval()
            
            logger.info(
                f"✅ FaceNet model loaded successfully\n"
                f"   Model: {self.model_name}\n"
                f"   Device: {self.device}\n"
                f"   Embedding size: {self.embedding_size}"
            )
        
        except Exception as e:
            logger.error(f"❌ Failed to load FaceNet model: {e}")
            raise
    
    def preprocess_face(
        self,
        face: np.ndarray,
        target_size: Tuple[int, int] = (160, 160)
    ) -> Tuple[np.ndarray, bool]:
        """
        Preprocess face image for FaceNet.
        
        Handles:
        - Size validation
        - Resizing to 160x160
        - RGB conversion (from BGR)
        - Normalization to [-1, 1]
        
        Args:
            face: Input face image (BGR from OpenCV)
            target_size: Target size for model input
        
        Returns:
            Tuple of (preprocessed_image, success_flag)
        """
        try:
            if face is None or face.size == 0:
                return None, False
            
            # Check minimum size
            min_size = 20
            if face.shape[0] < min_size or face.shape[1] < min_size:
                logger.warning(f"Face too small: {face.shape[:2]} < {min_size}x{min_size}")
                return None, False
            
            # Clone to avoid modifying original
            processed = face.copy().astype(np.float32)
            
            # Resize to target size
            processed = cv2.resize(
                processed,
                target_size,
                interpolation=cv2.INTER_CUBIC
            )
            
            # Convert BGR to RGB
            processed = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
            
            # Normalize to [-1, 1] (FaceNet expects this)
            # Standard normalization: (x - 127.5) / 128
            processed = (processed - 127.5) / 128.0
            
            # Convert to tensor format (C, H, W)
            processed = np.transpose(processed, (2, 0, 1))
            
            return processed, True
        
        except Exception as e:
            logger.error(f"Error preprocessing face: {e}")
            return None, False
    
    def generate_embedding(
        self,
        face: np.ndarray,
        target_size: Tuple[int, int] = (160, 160)
    ) -> Optional[np.ndarray]:
        """
        Generate 128-dimensional embedding for a single face.
        
        Args:
            face: Input face image (BGR)
            target_size: Target size for model input
        
        Returns:
            128-dim embedding or None if failed
        """
        try:
            # Preprocess
            processed, success = self.preprocess_face(face, target_size)
            
            if not success:
                return None
            
            # Convert to tensor
            face_tensor = torch.from_numpy(processed).unsqueeze(0).float()
            face_tensor = face_tensor.to(self.device)
            
            # Generate embedding
            with torch.no_grad():
                embedding = self.model(face_tensor)
            
            # Convert to numpy and normalize (L2 normalization)
            embedding = embedding.cpu().numpy()[0]
            embedding = embedding / np.linalg.norm(embedding)
            
            return embedding
        
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    def generate_embeddings(
        self,
        faces: List[np.ndarray],
        target_size: Tuple[int, int] = (160, 160),
        batch_size: int = 32
    ) -> List[Optional[np.ndarray]]:
        """
        Generate embeddings for multiple faces (batch processing).
        
        Args:
            faces: List of face images (BGR)
            target_size: Target size for model input
            batch_size: Batch size for processing
        
        Returns:
            List of 128-dim embeddings (None for failed faces)
        """
        embeddings = []
        
        # Process in batches
        for i in range(0, len(faces), batch_size):
            batch = faces[i:i + batch_size]
            processed_batch = []
            valid_indices = []
            
            # Preprocess batch
            for j, face in enumerate(batch):
                processed, success = self.preprocess_face(face, target_size)
                if success:
                    processed_batch.append(processed)
                    valid_indices.append(j)
                else:
                    embeddings.append(None)
            
            if not processed_batch:
                continue
            
            try:
                # Stack into batch tensor
                batch_tensor = torch.from_numpy(
                    np.stack(processed_batch)
                ).float()
                batch_tensor = batch_tensor.to(self.device)
                
                # Generate embeddings
                with torch.no_grad():
                    batch_embeddings = self.model(batch_tensor)
                
                # Process each embedding
                batch_embeddings = batch_embeddings.cpu().numpy()
                
                for j, emb in enumerate(batch_embeddings):
                    # L2 normalization
                    emb_normalized = emb / np.linalg.norm(emb)
                    embeddings.insert(i + valid_indices[j], emb_normalized)
            
            except Exception as e:
                logger.error(f"Error processing batch: {e}")
                for _ in valid_indices:
                    embeddings.append(None)
        
        return embeddings
    
    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        Compute similarity between two embeddings using Euclidean distance.
        
        Args:
            embedding1: First 128-dim embedding
            embedding2: Second 128-dim embedding
        
        Returns:
            Distance between embeddings (lower = more similar)
        """
        if embedding1 is None or embedding2 is None:
            return float('inf')
        
        return float(np.linalg.norm(embedding1 - embedding2))
    
    def compare_faces(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
        threshold: float = 0.6
    ) -> Tuple[bool, float]:
        """
        Compare two face embeddings and determine if they match.
        
        Args:
            embedding1: First face embedding
            embedding2: Second face embedding
            threshold: Distance threshold for match
        
        Returns:
            Tuple of (is_match, distance)
        """
        distance = self.compute_similarity(embedding1, embedding2)
        is_match = distance < threshold
        
        return is_match, distance


class FaceDatabase:
    """
    Simple in-memory face database for storing embeddings and metadata.
    """
    
    def __init__(self):
        """Initialize empty face database."""
        self.embeddings: Dict[str, np.ndarray] = {}
        self.metadata: Dict[str, Dict] = {}
    
    def add_face(
        self,
        face_id: str,
        embedding: np.ndarray,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Add face embedding to database.
        
        Args:
            face_id: Unique identifier for face
            embedding: 128-dim face embedding
            metadata: Additional metadata (name, student_id, etc.)
        """
        self.embeddings[face_id] = embedding
        self.metadata[face_id] = metadata or {}
    
    def find_similar_faces(
        self,
        embedding: np.ndarray,
        threshold: float = 0.6,
        top_k: int = 5
    ) -> List[Tuple[str, float, Dict]]:
        """
        Find similar faces in database.
        
        Args:
            embedding: Query embedding
            threshold: Maximum distance for match
            top_k: Return top K matches
        
        Returns:
            List of (face_id, distance, metadata) sorted by distance
        """
        if not self.embeddings:
            return []
        
        results = []
        
        for face_id, stored_embedding in self.embeddings.items():
            distance = np.linalg.norm(embedding - stored_embedding)
            
            if distance < threshold:
                results.append((
                    face_id,
                    float(distance),
                    self.metadata[face_id]
                ))
        
        # Sort by distance (closest first)
        results.sort(key=lambda x: x[1])
        
        return results[:top_k]
    
    def clear(self) -> None:
        """Clear all embeddings and metadata."""
        self.embeddings.clear()
        self.metadata.clear()


def demo_recognition(num_samples: int = 5):
    """
    Demo script for face recognition and embedding generation.
    
    Captures face samples and generates embeddings.
    
    Args:
        num_samples: Number of face samples to capture
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize recognizer
    recognizer = FaceRecognitionPipeline(device="cpu")
    
    # Create a simple face database
    database = FaceDatabase()
    
    logger.info(f"Capture {num_samples} face samples...")
    
    # For demo, create random embeddings instead of real faces
    # (since we need actual face images to work)
    for i in range(num_samples):
        # Generate random embedding (for demo purposes)
        # In real usage, this would come from detected face
        random_embedding = np.random.randn(128)
        random_embedding = random_embedding / np.linalg.norm(random_embedding)
        
        database.add_face(
            f"person_{i}",
            random_embedding,
            {"name": f"Person {i}", "student_id": f"STU{i:03d}"}
        )
        logger.info(f"Added face: person_{i}")
    
    logger.info(f"\n✅ Database has {len(database.embeddings)} face(s)")
    
    # Demo: Find similar face
    query_embedding = np.random.randn(128)
    query_embedding = query_embedding / np.linalg.norm(query_embedding)
    
    logger.info("\nSearching for similar faces...")
    matches = database.find_similar_faces(query_embedding, threshold=1.0, top_k=3)
    
    if matches:
        logger.info("Matches found:")
        for face_id, distance, metadata in matches:
            logger.info(
                f"  - {face_id}: distance={distance:.4f}, "
                f"name={metadata.get('name', 'Unknown')}"
            )
    else:
        logger.info("No matches found")


if __name__ == "__main__":
    # Run demo
    demo_recognition(num_samples=5)
