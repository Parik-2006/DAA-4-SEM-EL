"""
services/scoped_embedding_search.py
─────────────────────────────────────
Scoped embedding search: applies an IdentityScope to narrow the candidate
pool before running cosine similarity matching.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
from scipy.spatial.distance import cosine

try:
    from attendance_backend.models.identity_context import (
        IdentityScopeType,
        ScopeTarget,
        ScopedMatchResult,
    )
except ImportError:  # pragma: no cover - script-mode fallback
    from models.identity_context import (
        IdentityScopeType,
        ScopeTarget,
        ScopedMatchResult,
    )

logger = logging.getLogger(__name__)

COSINE_THRESHOLD = 0.55


class ScopedEmbeddingSearch:

    def __init__(self, firebase_service=None) -> None:
        self._fb = firebase_service

    def search(self, query_embedding: np.ndarray, scope: ScopeTarget, threshold: float = COSINE_THRESHOLD) -> ScopedMatchResult:
        # Normalize query
        try:
            q = query_embedding.astype(np.float32)
            q_norm = q / (np.linalg.norm(q) + 1e-10)
        except Exception:
            q_norm = query_embedding

        if scope.scope_type == IdentityScopeType.GLOBAL or not scope.student_ids:
            return self._global_search(query_embedding, threshold, scope)

        candidates = self._load_candidates(scope.student_ids)
        if not candidates:
            return ScopedMatchResult(
                matched=False,
                student_id=None,
                student_name=None,
                confidence=0.0,
                distance=1.0,
                scope=scope,
                candidates_searched=0,
                message="No embeddings found for the scoped candidates.",
            )

        # Build prototypes and flattened embedding list for top-K voting
        prototypes = {}
        flat_list = []  # (student_id, emb, name)
        total_vectors = 0
        for student_id, embeddings, name in candidates:
            normed = []
            for emb in embeddings:
                try:
                    if emb.shape != query_embedding.shape:
                        continue
                    e = emb.astype(np.float32)
                    e = e / (np.linalg.norm(e) + 1e-10)
                    normed.append(e)
                    flat_list.append((student_id, e, name))
                    total_vectors += 1
                except Exception:
                    continue
            if normed:
                prototypes[student_id] = np.mean(np.stack(normed, axis=0), axis=0)

        if not flat_list:
            return ScopedMatchResult(
                matched=False,
                student_id=None,
                student_name=None,
                confidence=0.0,
                distance=1.0,
                scope=scope,
                candidates_searched=0,
                message="No valid embeddings in scope.",
            )

        # Prototype scoring
        proto_scores = {}
        for sid, proto in prototypes.items():
            proto_scores[sid] = float(np.dot(q_norm, proto))

        # Top-K voting on raw embeddings
        K = 10
        alpha = 10.0
        T_proto = 0.58
        T_vote = 0.35

        sims = []
        for sid, emb, name in flat_list:
            sim = float(np.dot(q_norm, emb))
            sims.append((sid, sim))

        sims.sort(key=lambda x: x[1], reverse=True)
        topk = sims[:K]
        weights = {}
        total_w = 0.0
        for sid, sim in topk:
            w = float(np.exp(alpha * sim))
            weights[sid] = weights.get(sid, 0.0) + w
            total_w += w

        # Normalize votes
        votes = {sid: (w / total_w if total_w > 0 else 0.0) for sid, w in weights.items()}

        # Choose best by prototype score then validate vote
        if not proto_scores:
            best_sid = max(votes.items(), key=lambda x: x[1])[0]
            best_score = votes.get(best_sid, 0.0)
            best_conf = best_score
            best_distance = 1.0 - best_score
        else:
            best_sid, best_score = max(proto_scores.items(), key=lambda x: x[1])
            best_vote = votes.get(best_sid, 0.0)
            best_conf = float(best_score)
            best_distance = float(max(0.0, 1.0 - best_score))

        # Decision rule
        if best_score < T_proto or best_vote < T_vote:
            return ScopedMatchResult(
                matched=False,
                student_id=None,
                student_name=None,
                confidence=float(best_conf),
                distance=float(best_distance),
                scope=scope,
                candidates_searched=total_vectors,
                message=(
                    f"No match (proto={best_score:.2f}, vote={best_vote:.2f}). Searched {total_vectors} vectors."
                ),
            )

        # Self scope check
        if scope.scope_type == IdentityScopeType.SELF and best_sid != scope.resolved_by:
            logger.warning("SELF scope mismatch: query by %s matched %s — rejecting.", scope.resolved_by, best_sid)
            return ScopedMatchResult(
                matched=False,
                student_id=None,
                student_name=None,
                confidence=float(best_conf),
                distance=float(best_distance),
                scope=scope,
                candidates_searched=total_vectors,
                message="Face did not match your registered profile.",
            )

        matched_name = next((name for sid, _, name in candidates if sid == best_sid), "Unknown")
        logger.info("Scoped prototype match [%s]: %s → %s (proto=%.3f, vote=%.3f, vectors=%d)", scope.scope_type, scope.resolved_by, best_sid, best_score, votes.get(best_sid, 0.0), total_vectors)

        return ScopedMatchResult(
            matched=True,
            student_id=best_sid,
            student_name=matched_name,
            confidence=float(best_conf),
            distance=float(best_distance),
            scope=scope,
            candidates_searched=total_vectors,
        )

    def _load_candidates(self, student_ids: List[str]):
        try:
            from attendance_backend.services.firebase_service import FirebaseService
        except ImportError:  # pragma: no cover - script-mode fallback
            from services.firebase_service import FirebaseService

        results = []
        if not self._fb:
            return results

        for sid in student_ids:
            try:
                student = self._fb.get_student(sid)
                if not student:
                    continue
                embeddings = FirebaseService.get_all_embeddings(student)
                if embeddings:
                    name = student.get("name", sid)
                    results.append((sid, embeddings, name))
            except Exception as exc:
                logger.warning("Could not load embeddings for %s: %s", sid, exc)

        return results

    def _global_search(self, query_embedding: np.ndarray, threshold: float, scope: ScopeTarget) -> ScopedMatchResult:
        if not self._fb:
            return ScopedMatchResult(matched=False, student_id=None, student_name=None, confidence=0.0, distance=1.0, scope=scope, candidates_searched=0, message="Firebase service not available.")

        try:
            from attendance_backend.services.firebase_service import FirebaseService
        except ImportError:  # pragma: no cover - script-mode fallback
            from services.firebase_service import FirebaseService

        all_students = self._fb.get_all_students()
        best_distance = float("inf")
        best_student: Optional[Dict] = None
        total_vectors = 0

        for student in all_students:
            for emb in FirebaseService.get_all_embeddings(student):
                if emb.shape != query_embedding.shape:
                    continue
                d = float(cosine(query_embedding, emb))
                total_vectors += 1
                if d < best_distance:
                    best_distance = d
                    best_student = student

        confidence = float(1.0 - min(best_distance, 1.0))

        if best_distance > threshold or best_student is None:
            return ScopedMatchResult(matched=False, student_id=None, student_name=None, confidence=confidence, distance=best_distance, scope=scope, candidates_searched=total_vectors, message=f"No global match (best conf: {confidence:.2f}).")

        return ScopedMatchResult(
            matched=True,
            student_id=best_student.get("student_id", ""),
            student_name=best_student.get("name", "Unknown"),
            confidence=confidence,
            distance=best_distance,
            scope=scope,
            candidates_searched=total_vectors,
        )
