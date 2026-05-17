"""
Face Recognition Service for matching detected faces.

Handles embedding extraction, similarity matching (FAISS), multi-photo
enrollment with centroid/variance stats, adaptive per-user thresholding,
liveness scoring, and fused confidence gating before accepting an identity.

Revision history
────────────────
v1  – Base: FAISS search, single-photo enrollment, raw recognize_face()
v2  – Added: compute_enrollment_stats(), enroll_student_multi(),
             compute_adaptive_threshold(), recognize_face(variance=) overload,
             recognize_batch_faces(variances=) overload
v3  – Added: LivenessDetector + FusedConfidenceScorer injection,
             recognize_face_fused() full gated pipeline
This – All three versions merged; every public API preserved.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config.constants import FACE_RECOGNITION_THRESHOLD
from models.model_manager import ModelManager
from utils.embedding_search import EmbeddingSearch
from utils.preprocessing import ImagePreprocessor

# ── Liveness + fused confidence (v3) ──────────────────────────────────────────
from services.liveness import LivenessDetector, LivenessResult, get_liveness_detector
from services.fused_confidence import (
    FusedConfidenceConfig,
    FusedConfidenceResult,
    FusedConfidenceScorer,
    get_fused_scorer,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Module-level helpers (v2)
# ─────────────────────────────────────────────────────────────────────────────

def compute_adaptive_threshold(
    base_threshold: float,
    variance: float,
    k: float = 1.5,
    min_threshold: float = 0.30,
    max_threshold: float = 0.80,
) -> float:
    """
    Compute a per-user adaptive similarity threshold.

    Users whose stored embeddings are tightly clustered (low variance in
    cosine-distance space) get a stricter threshold; users with spread
    embeddings get a slightly looser one so genuine matches are not rejected.

    Formula
    -------
        std_distance  = sqrt(variance)
        adjusted      = base_threshold - k * std_distance
        result        = clip(adjusted, min_threshold, max_threshold)

    Because this is a *similarity* threshold (higher = stricter), lower
    std_distance tightens the requirement; higher relaxes it, bounded by
    max_threshold so a very spread profile cannot accept near-random matches.

    Args:
        base_threshold: Global baseline similarity threshold (e.g. 0.55).
        variance:       Pre-computed variance of cosine distances across the
                        user's stored embeddings (``student["embedding_variance"]``
                        in Firestore).
        k:              Sensitivity multiplier. Default 1.5 — increase to make
                        the system more tolerant of intra-user spread.
        min_threshold:  Floor — never accept anything clearly a stranger (0.30).
        max_threshold:  Ceiling — very spread profiles cannot silently accept
                        near-random matches (0.80).

    Returns:
        Adaptive threshold in [min_threshold, max_threshold].
    """
    std_distance = float(np.sqrt(max(0.0, variance)))
    adjusted = base_threshold - k * std_distance
    return float(np.clip(adjusted, min_threshold, max_threshold))


# ─────────────────────────────────────────────────────────────────────────────
# Main service class
# ─────────────────────────────────────────────────────────────────────────────

class FaceRecognitionService:
    """
    Face Recognition Service.

    Extracts embeddings from face images and matches them against enrolled
    student embeddings using FAISS indexing.

    Three recognition modes are available:

    1. ``recognize_face()``        — raw FAISS match; no liveness / fused gating.
                                     Used as a primitive by aggregation layers.
    2. ``recognize_face()``        — same, but with optional ``variance`` argument
                                     to enable per-user adaptive thresholding (v2).
    3. ``recognize_face_fused()``  — full pipeline: FAISS → liveness → fused
                                     confidence gate (v3).

    Multi-photo enrollment
    ──────────────────────
    ``enroll_student_multi()`` accepts 5–10 images, computes a centroid and
    per-dimension variance, upserts the centroid into FAISS, and returns the
    stats for the caller (API layer) to persist in Firestore.
    """

    # ── Enrollment constants (v2) ──────────────────────────────────────────────
    MIN_ENROLLMENT_IMAGES: int = 5
    MAX_ENROLLMENT_IMAGES: int = 10

    def __init__(
        self,
        liveness_detector: Optional[LivenessDetector] = None,
        fused_scorer: Optional[FusedConfidenceScorer] = None,
    ) -> None:
        """
        Initialise face recognition service.

        Args:
            liveness_detector:  Shared LivenessDetector; one is created if None.
            fused_scorer:       Shared FusedConfidenceScorer; one is created if None.
        """
        self.extractor = None
        self.search_engine = EmbeddingSearch(use_faiss=True, metric="cosine")
        self.preprocessor = ImagePreprocessor()

        # ── Fused confidence components (v3) ──────────────────────────────────
        self.liveness_detector: LivenessDetector = (
            liveness_detector or get_liveness_detector()
        )
        self.fused_scorer: FusedConfidenceScorer = (
            fused_scorer or get_fused_scorer()
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Model loading
    # ─────────────────────────────────────────────────────────────────────────

    def ensure_extractor_loaded(self) -> None:
        """Ensure extractor model is loaded (lazy init)."""
        if self.extractor is None:
            try:
                self.extractor = ModelManager.get_facenet_extractor()
            except RuntimeError:
                logger.error("Failed to load extractor model")
                raise

    # ─────────────────────────────────────────────────────────────────────────
    # Embedding extraction
    # ─────────────────────────────────────────────────────────────────────────

    def extract_embedding(self, face_image: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract a unit-normalised embedding from a face image.

        Args:
            face_image: Face image; resized to 160×160 internally.

        Returns:
            Embedding vector (128-dim, L2-normalised) or None on failure.
        """
        try:
            self.ensure_extractor_loaded()
            processed_face = self.preprocessor.resize_image(
                face_image, target_size=(160, 160), keep_aspect=False
            )
            return self.extractor.extract_embedding(processed_face, normalize=True)
        except Exception as e:
            logger.error(f"Embedding extraction failed: {e}")
            return None

    def extract_batch_embeddings(
        self,
        face_images: List[np.ndarray],
    ) -> np.ndarray:
        """
        Extract embeddings from multiple face images.

        Args:
            face_images: List of face images.

        Returns:
            Array of shape (N, 128); empty array on failure.
        """
        try:
            self.ensure_extractor_loaded()
            return self.extractor.extract_batch_embeddings(face_images, normalize=True)
        except Exception as e:
            logger.error(f"Batch embedding extraction failed: {e}")
            return np.array([])

    # ─────────────────────────────────────────────────────────────────────────
    # Recognition — raw (v1 + v2 adaptive threshold extension)
    # ─────────────────────────────────────────────────────────────────────────

    def recognize_face(
        self,
        face_embedding: np.ndarray,
        threshold: Optional[float] = None,
        variance: Optional[float] = None,
        adaptive_k: float = 1.5,
    ) -> Optional[Tuple[str, float]]:
        """
        Recognise a face via FAISS embedding search (raw; no liveness gating).

        When ``variance`` is supplied the effective threshold is computed via
        :func:`compute_adaptive_threshold` instead of the bare ``threshold``
        value, enabling per-user adaptive thresholding (v2 feature).

        Args:
            face_embedding: L2-normalised embedding vector (128-dim).
            threshold:      Base similarity threshold.  Defaults to the global
                            ``FACE_RECOGNITION_THRESHOLD`` constant.
            variance:       Cosine-distance variance across the user's stored
                            embeddings (from Firestore).  Pass when available.
            adaptive_k:     Sensitivity multiplier forwarded to
                            :func:`compute_adaptive_threshold`.

        Returns:
            ``(student_id, similarity_score)`` or ``None`` if no match.
        """
        try:
            base = threshold if threshold is not None else FACE_RECOGNITION_THRESHOLD

            # v2: compute adaptive threshold when variance is available
            effective_threshold = (
                compute_adaptive_threshold(base, variance, k=adaptive_k)
                if variance is not None
                else base
            )

            if variance is not None:
                logger.debug(
                    "Adaptive threshold: base=%.3f variance=%.4f → effective=%.3f",
                    base, variance, effective_threshold,
                )

            match = self.search_engine.search_single_match(
                face_embedding, threshold=effective_threshold
            )
            if match:
                index, similarity = match
                student_info = self.search_engine.get_student_info(index)
                if student_info:
                    student_id = student_info.get("student_id")
                    logger.debug(
                        "Face recognized as %s (score: %.3f, threshold: %.3f)",
                        student_id, similarity, effective_threshold,
                    )
                    return student_id, similarity

            logger.debug("No matching face found")
            return None

        except Exception as e:
            logger.error(f"Face recognition failed: {e}")
            return None

    def recognize_batch_faces(
        self,
        face_embeddings: np.ndarray,
        threshold: Optional[float] = None,
        variances: Optional[List[Optional[float]]] = None,
        adaptive_k: float = 1.5,
    ) -> List[Optional[Tuple[str, float]]]:
        """
        Recognise multiple faces (raw; no fused gating).

        Args:
            face_embeddings: Array of embeddings (N × 128).
            threshold:       Base similarity threshold.
            variances:       Per-embedding variance values (parallel list).
                             Pass ``None`` items for embeddings without stats.
            adaptive_k:      Sensitivity multiplier for adaptive threshold.

        Returns:
            List of ``(student_id, similarity)`` or ``None`` per embedding.
        """
        results: List[Optional[Tuple[str, float]]] = []
        for i, embedding in enumerate(face_embeddings):
            var = variances[i] if variances and i < len(variances) else None
            results.append(
                self.recognize_face(
                    embedding,
                    threshold=threshold,
                    variance=var,
                    adaptive_k=adaptive_k,
                )
            )
        return results

    # ─────────────────────────────────────────────────────────────────────────
    # Recognition — fused pipeline (v3)
    # ─────────────────────────────────────────────────────────────────────────

    def recognize_face_fused(
        self,
        face_image: np.ndarray,
        *,
        face_embedding: Optional[np.ndarray] = None,
        threshold: Optional[float] = None,
        variance: Optional[float] = None,
        adaptive_k: float = 1.5,
        risk_score: float = 0.0,
        landmarks: Optional[np.ndarray] = None,
        track_id: Optional[int] = None,
        attempt_count: int = 0,
        max_attempts: int = 5,
    ) -> Optional[Tuple[str, FusedConfidenceResult]]:
        """
        Full gated recognition: FAISS match → liveness → fused confidence.

        This is the primary entry point for the optimised attendance pipeline
        when the session is anchored to a logged-in user (SELF_VERIFY mode).
        It combines:
          • Per-user adaptive thresholding (v2) in the raw FAISS step.
          • Liveness scoring (blink / texture heuristic from liveness.py).
          • Fused confidence gating: fused = w1·sim + w2·live + w3·(1−risk).

        Args:
            face_image:     Raw cropped face ROI for liveness scoring.
            face_embedding: Pre-extracted embedding; skips re-extraction when
                            provided (use when the pipeline already ran
                            ``extract_embedding()`` upstream).
            threshold:      Base FAISS similarity threshold.
            variance:       Per-user embedding variance for adaptive threshold.
            adaptive_k:     Sensitivity multiplier for adaptive threshold.
            risk_score:     Pre-computed metadata risk [0, 1].  Build with
                            ``FusedConfidenceScorer.compute_risk_score()``.
            landmarks:      Facial keypoints [N, 2] for blink-based liveness.
            track_id:       SORT track ID for cross-frame blink accumulation.
            attempt_count:  Attempts already consumed (raises risk pressure).
            max_attempts:   Ceiling for pressure calculation.

        Returns:
            ``(student_id, FusedConfidenceResult)`` if accepted, else ``None``.
        """
        # 1. Embedding (re-use if pre-extracted)
        embedding = face_embedding
        if embedding is None:
            embedding = self.extract_embedding(face_image)
            if embedding is None:
                logger.warning("recognize_face_fused: embedding extraction failed")
                return None

        # 2. Raw FAISS match with optional adaptive threshold (v2 + v3 merged)
        raw_match = self.recognize_face(
            embedding,
            threshold=threshold,
            variance=variance,
            adaptive_k=adaptive_k,
        )
        if raw_match is None:
            logger.debug("recognize_face_fused: no FAISS match below threshold")
            return None
        student_id, similarity = raw_match

        # 3. Liveness score
        liveness_result: LivenessResult = self.liveness_detector.check(
            face_image, landmarks=landmarks, track_id=track_id
        )
        liveness_score = liveness_result.score

        # 4. Augment risk_score with attempt pressure (up to +0.25)
        pressure = self.fused_scorer.attempt_pressure(attempt_count, max_attempts)
        effective_risk = min(1.0, risk_score + 0.25 * pressure)

        # 5. Fused confidence gate
        fused_result: FusedConfidenceResult = self.fused_scorer.score(
            similarity=similarity,
            liveness=liveness_score,
            risk_score=effective_risk,
        )

        if fused_result.accepted:
            logger.info(
                "recognize_face_fused: ACCEPTED %s — fused=%.3f "
                "(sim=%.3f, live=%.3f, risk=%.3f, method=%s)",
                student_id, fused_result.fused,
                similarity, liveness_score, effective_risk,
                liveness_result.method,
            )
            return student_id, fused_result

        logger.debug(
            "recognize_face_fused: REJECTED — %s", fused_result.reject_reason
        )
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Multi-photo enrollment (v2)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def compute_enrollment_stats(
        normalized_embeddings: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute centroid and per-dimension variance from unit-normed embeddings.

        The centroid is L2-renormalised so it stays on the unit hypersphere,
        making cosine-similarity comparisons work directly against it.  The
        variance captures per-dimension spread and drives adaptive thresholds.

        Args:
            normalized_embeddings: Float32 array (N, D); every row already
                                   L2-normalised (‖row‖ ≈ 1).

        Returns:
            ``(centroid, variance)`` — both float32 arrays of shape (D,).

        Raises:
            ValueError: if the input is not a 2-D array with ≥ 1 row.
        """
        if normalized_embeddings.ndim != 2 or normalized_embeddings.shape[0] < 1:
            raise ValueError(
                f"Expected 2-D array with ≥1 row, got shape {normalized_embeddings.shape}"
            )
        mean_vec = normalized_embeddings.mean(axis=0).astype(np.float32)
        norm_val = np.linalg.norm(mean_vec) + 1e-10
        centroid = (mean_vec / norm_val).astype(np.float32)
        variance = normalized_embeddings.var(axis=0).astype(np.float32)
        return centroid, variance

    def enroll_student_multi(
        self,
        student_id: str,
        face_images: List[np.ndarray],
        student_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Multi-photo enrollment pipeline for a single student.

        Steps
        -----
        1. Validate image count (MIN ≤ N ≤ MAX).
        2. Extract an embedding per image; skip frames where extraction fails.
        3. Re-validate that at least MIN_ENROLLMENT_IMAGES succeeded.
        4. L2-renormalise all embeddings (defensive; extract already normalises).
        5. Compute centroid + per-dimension variance.
        6. Upsert the **centroid** (one vector per student) into FAISS.

        Note: This method does **not** write to Firestore directly.  The API
        layer calls ``firebase_service.store_enrollment()`` after this method
        returns, passing the returned ``centroid`` and ``variance``.

        Args:
            student_id:   User/student identifier; used as the FAISS metadata key.
            face_images:  Raw face images (uncropped is fine; resized internally).
            student_info: Optional extra metadata merged into the FAISS record
                          (e.g. name, section_id).

        Returns:
            Dict with keys:
                success              – bool
                student_id           – str
                sample_count         – int  (frames that yielded valid embeddings)
                failed_count         – int  (frames that extraction failed for)
                centroid             – np.ndarray (D,)
                variance             – np.ndarray (D,)
                normalized_embeddings – np.ndarray (N, D)
                message              – str

        Raises:
            ValueError: too few images provided, or too few extraction successes.
        """
        n_provided = len(face_images)
        if n_provided < self.MIN_ENROLLMENT_IMAGES:
            raise ValueError(
                f"Enrollment requires at least {self.MIN_ENROLLMENT_IMAGES} images; "
                f"received {n_provided}."
            )
        # Cap to MAX — take the first N (deterministic; caller may send extras)
        face_images = face_images[: self.MAX_ENROLLMENT_IMAGES]

        # Step 1: extract embeddings
        raw_embeddings: List[np.ndarray] = []
        failed_indices: List[int] = []

        for idx, img in enumerate(face_images):
            emb = self.extract_embedding(img)
            if emb is not None and emb.ndim == 1 and emb.shape[0] > 0:
                raw_embeddings.append(emb.astype(np.float32))
            else:
                failed_indices.append(idx)
                logger.warning(
                    "enroll_student_multi: extraction failed for image %d of %s",
                    idx, student_id,
                )

        sample_count = len(raw_embeddings)
        failed_count = len(failed_indices)

        if sample_count < self.MIN_ENROLLMENT_IMAGES:
            raise ValueError(
                f"Only {sample_count} of {len(face_images)} images yielded valid "
                f"embeddings (need at least {self.MIN_ENROLLMENT_IMAGES}). "
                f"Re-capture with better lighting or face angle."
            )

        # Step 2: stack + defensive re-normalise
        stacked = np.stack(raw_embeddings, axis=0)                    # (N, D)
        norms = np.linalg.norm(stacked, axis=1, keepdims=True) + 1e-10
        normalized_embeddings = (stacked / norms).astype(np.float32)  # (N, D)

        # Step 3: compute stats
        centroid, variance = self.compute_enrollment_stats(normalized_embeddings)

        # Step 4: upsert centroid into FAISS (one vector per student, compact index)
        # normalize=False because centroid is already a unit vector.
        info = student_info or {}
        info["student_id"] = student_id
        self.search_engine.add_embedding(centroid, info, normalize=False)

        logger.info(
            "Enrolled %s: sample_count=%d failed=%d centroid_dim=%d mean_variance=%.5f",
            student_id, sample_count, failed_count,
            centroid.shape[0], float(variance.mean()),
        )

        return {
            "success":                True,
            "student_id":             student_id,
            "sample_count":           sample_count,
            "failed_count":           failed_count,
            "centroid":               centroid,
            "variance":               variance,
            "normalized_embeddings":  normalized_embeddings,
            "message": (
                f"Enrollment successful. {sample_count} samples used"
                + (f" ({failed_count} frames skipped)." if failed_count else ".")
            ),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Index management (v1, unchanged)
    # ─────────────────────────────────────────────────────────────────────────

    def build_index(self, embeddings: np.ndarray, metadata: Dict[int, Dict]) -> None:
        """
        Build FAISS search index from student embeddings.

        Args:
            embeddings: Array of student embeddings (N × 128).
            metadata:   Mapping from index position to student info dict.
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
        student_info: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add a single student embedding to the FAISS index.

        Args:
            student_id:   Student identifier.
            embedding:    Student's face embedding.
            student_info: Additional student metadata.

        Returns:
            True if successful.
        """
        try:
            info = student_info or {"student_id": student_id}
            info["student_id"] = student_id
            self.search_engine.add_embedding(embedding, info, normalize=True)
            logger.info(f"Added embedding for student {student_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add student embedding: {e}")
            return False

    def save_index(self, index_path: str, metadata_path: str) -> bool:
        """Persist FAISS index and metadata to disk."""
        try:
            self.search_engine.save_index(index_path, metadata_path)
            return True
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            return False

    def load_index(self, index_path: str, metadata_path: str) -> bool:
        """Load FAISS index and metadata from disk."""
        try:
            self.search_engine.load_index(index_path, metadata_path)
            logger.info("Index loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            return False

    def get_index_stats(self) -> dict:
        """Return FAISS index statistics."""
        return self.search_engine.get_index_stats()

    def get_recognition_stats(self) -> dict:
        """Return extractor model info."""
        try:
            self.ensure_extractor_loaded()
            return self.extractor.get_model_info()
        except Exception as e:
            logger.error(f"Error getting recognition stats: {e}")
            return {}