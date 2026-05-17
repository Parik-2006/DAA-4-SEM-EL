"""
models/scoped_matcher.py
──────────────────────────────────────────────────────────────────────────────
Runs cosine-similarity matching against a pre-resolved EmbeddingScope.

The caller already owns the scope (resolved by EmbeddingScopeService), so
this module is pure CPU computation with no I/O.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
from scipy.spatial.distance import cosine

from services.embedding_scope_service import EmbeddingScope

COSINE_THRESHOLD = 0.55


def match_against_scope(
    embedding: np.ndarray,
    scope: EmbeddingScope,
    threshold: float = COSINE_THRESHOLD,
) -> Tuple[Optional[Dict[str, Any]], float, float]:
    """
    Find the best matching student within *scope*.

    Returns
    -------
    (best_student | None, confidence, best_distance)

    For SELF_VERIFY mode the threshold is intentionally stricter (0.45)
    because we are matching against a known identity — false positives here
    mean impersonation.
    """
    effective_threshold = 0.45 if scope.mode == "self_verify" else threshold

    best_distance = float("inf")
    best_student: Optional[Dict[str, Any]] = None

    for student, embeddings in scope.candidates:
        for arr in embeddings:
            if arr.shape != embedding.shape:
                continue
            dist = float(cosine(embedding, arr))
            if dist < best_distance:
                best_distance = dist
                best_student = student

    confidence = float(1.0 - min(best_distance, 1.0)) if best_student else 0.0

    if best_distance > effective_threshold:
        return None, confidence, best_distance

    return best_student, confidence, best_distance
