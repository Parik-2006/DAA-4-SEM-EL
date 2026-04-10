"""
Face embedding search utilities using FAISS and KD-tree.

Provides efficient similarity search for face embeddings to match
detected faces with enrolled students.
"""

from pathlib import Path
from typing import List, Tuple, Optional, Dict
import logging
import pickle

import numpy as np
import faiss
from sklearn.neighbors import KDTree

from config.settings import get_settings
from config.constants import FACE_EMBEDDING_DIM, FACE_SIMILARITY_THRESHOLD


logger = logging.getLogger(__name__)


class EmbeddingSearch:
    """
    Face embedding search engine using FAISS and KD-tree.
    
    Supports fast similarity search for face embeddings with multiple
    backend options (FAISS or KD-tree).
    """
    
    def __init__(self, use_faiss: bool = True, metric: str = "cosine"):
        """
        Initialize embedding search engine.
        
        Args:
            use_faiss: Use FAISS backend (faster) or KD-tree
            metric: Distance metric ('cosine', 'euclidean')
        """
        self.use_faiss = use_faiss
        self.metric = metric
        self.embeddings: Optional[np.ndarray] = None
        self.metadata: Dict[int, Dict] = {}  # Maps index to student info
        
        # FAISS index
        self.faiss_index: Optional[faiss.IndexFlatIP] = None  # Inner product for cosine
        
        # KD-tree
        self.kdtree: Optional[KDTree] = None
        
        logger.info(f"Initialized embedding search with backend: {'FAISS' if use_faiss else 'KD-tree'}")
    
    def build_index(
        self,
        embeddings: np.ndarray,
        metadata: Dict[int, Dict],
        normalize: bool = True
    ) -> None:
        """
        Build search index from embeddings.
        
        Args:
            embeddings: Array of embeddings (N x 128)
            metadata: Dictionary mapping index to student info
            normalize: L2 normalize embeddings
        
        Raises:
            ValueError: If embeddings have invalid shape
        """
        if embeddings.shape[1] != FACE_EMBEDDING_DIM:
            raise ValueError(
                f"Embeddings must have {FACE_EMBEDDING_DIM} dimensions, "
                f"got {embeddings.shape[1]}"
            )
        
        # Normalize embeddings
        if normalize:
            embeddings = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)
        
        self.embeddings = embeddings.astype(np.float32)
        self.metadata = metadata
        
        if self.use_faiss:
            self._build_faiss_index()
        else:
            self._build_kdtree_index()
        
        logger.info(f"Built index with {len(embeddings)} embeddings")
    
    def _build_faiss_index(self) -> None:
        """Build FAISS index for fast similarity search."""
        try:
            # Use IndexFlatIP for cosine similarity (inner product)
            # Embeddings should be L2 normalized
            self.faiss_index = faiss.IndexFlatIP(FACE_EMBEDDING_DIM)
            self.faiss_index.add(self.embeddings)
            logger.info(f"FAISS index built with {self.embeddings.shape[0]} vectors")
        except Exception as e:
            logger.error(f"Failed to build FAISS index: {e}")
            raise
    
    def _build_kdtree_index(self) -> None:
        """Build KD-tree index for similarity search."""
        try:
            # Use euclidean metric
            self.kdtree = KDTree(self.embeddings, leaf_size=50, metric=self.metric)
            logger.info(f"KD-tree built with {self.embeddings.shape[0]} vectors")
        except Exception as e:
            logger.error(f"Failed to build KD-tree: {e}")
            raise
    
    def search_top_k(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        threshold: Optional[float] = None
    ) -> List[Tuple[int, float]]:
        """
        Search for top-k closest embeddings.
        
        Args:
            query_embedding: Query embedding (128-dim vector)
            k: Number of results to return
            threshold: Similarity threshold to filter results
        
        Returns:
            List of (index, distance) tuples sorted by distance
        """
        if self.embeddings is None:
            raise RuntimeError("Index not built. Call build_index() first.")
        
        threshold = threshold or FACE_SIMILARITY_THRESHOLD
        
        # Normalize query
        query_embedding = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        query_embedding = query_embedding.astype(np.float32).reshape(1, -1)
        
        if self.use_faiss:
            distances, indices = self.faiss_index.search(query_embedding, k)
            results = list(zip(indices[0], distances[0]))
        else:
            distances, indices = self.kdtree.query(query_embedding, k=k)
            results = list(zip(indices[0], distances[0]))
        
        # Filter by threshold
        results = [(idx, dist) for idx, dist in results if dist >= threshold]
        
        return results
    
    def search_single_match(
        self,
        query_embedding: np.ndarray,
        threshold: Optional[float] = None
    ) -> Optional[Tuple[int, float]]:
        """
        Search for single closest match.
        
        Args:
            query_embedding: Query embedding (128-dim vector)
            threshold: Similarity threshold
        
        Returns:
            (index, similarity) tuple or None if no match found
        """
        results = self.search_top_k(query_embedding, k=1, threshold=threshold)
        return results[0] if results else None
    
    def get_student_info(self, index: int) -> Optional[Dict]:
        """
        Get student metadata by index.
        
        Args:
            index: Embedding index
        
        Returns:
            Student metadata dictionary or None
        """
        return self.metadata.get(index)
    
    def add_embedding(
        self,
        embedding: np.ndarray,
        student_info: Dict,
        normalize: bool = True
    ) -> None:
        """
        Add new embedding to index (requires rebuilding).
        
        Args:
            embedding: New embedding
            student_info: Student metadata
            normalize: L2 normalize embedding
        """
        if self.embeddings is None:
            logger.warning("No index built yet. Building with single embedding.")
            self.embeddings = embedding.reshape(1, -1).astype(np.float32)
            new_index = 0
        else:
            if normalize:
                embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
            
            embedding = embedding.astype(np.float32).reshape(1, -1)
            self.embeddings = np.vstack([self.embeddings, embedding])
            new_index = len(self.embeddings) - 1
        
        # Update metadata
        self.metadata[new_index] = student_info
        
        # Rebuild index
        if self.use_faiss:
            self._build_faiss_index()
        else:
            self._build_kdtree_index()
        
        logger.info(f"Added embedding for student {student_info.get('student_id')}")
    
    def save_index(self, index_path: str, metadata_path: str) -> None:
        """
        Save index to disk.
        
        Args:
            index_path: Path to save FAISS index or KD-tree data
            metadata_path: Path to save metadata
        """
        try:
            Path(index_path).parent.mkdir(parents=True, exist_ok=True)
            
            if self.use_faiss and self.faiss_index:
                faiss.write_index(self.faiss_index, index_path)
            else:
                np.save(index_path, self.embeddings)
            
            # Save metadata
            with open(metadata_path, 'wb') as f:
                pickle.dump(self.metadata, f)
            
            logger.info(f"Index saved to {index_path}")
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            raise
    
    def load_index(self, index_path: str, metadata_path: str) -> None:
        """
        Load index from disk.
        
        Args:
            index_path: Path to saved index
            metadata_path: Path to saved metadata
        """
        try:
            if self.use_faiss:
                self.faiss_index = faiss.read_index(index_path)
                # Estimate embeddings size from index
                self.embeddings = np.zeros(
                    (self.faiss_index.ntotal, FACE_EMBEDDING_DIM),
                    dtype=np.float32
                )
            else:
                self.embeddings = np.load(index_path)
            
            # Load metadata
            with open(metadata_path, 'rb') as f:
                self.metadata = pickle.load(f)
            
            logger.info(f"Index loaded from {index_path}")
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            raise
    
    def get_index_stats(self) -> dict:
        """
        Get index statistics.
        
        Returns:
            Dictionary with index stats
        """
        if self.embeddings is None:
            return {"status": "not_built"}
        
        return {
            "num_embeddings": len(self.embeddings),
            "embedding_dim": FACE_EMBEDDING_DIM,
            "backend": "FAISS" if self.use_faiss else "KD-tree",
            "metric": self.metric,
            "num_students": len(self.metadata),
        }
