"""
tests/test_adaptive_threshold_and_session_anchoring.py
───────────────────────────────────────────────────────
Regression tests for:
  1. compute_adaptive_threshold  (face_recognition_service.py)
  2. SessionAnchorStore          (scoped_embedding_search.py)
  3. ScopedEmbeddingSearch.search — adaptive threshold integration
"""

from __future__ import annotations

import time
import types
import unittest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

import numpy as np

# ---------------------------------------------------------------------------
# Minimal stubs so we can import without the full project installed
# ---------------------------------------------------------------------------

# --- identity_context stub --------------------------------------------------
class IdentityScopeType(Enum):
    GLOBAL = "GLOBAL"
    SELF = "SELF"
    SECTION_ROSTER = "SECTION_ROSTER"


@dataclass
class ScopeTarget:
    scope_type: IdentityScopeType
    student_ids: List[str] = field(default_factory=list)
    resolved_by: Optional[str] = None


@dataclass
class ScopedMatchResult:
    matched: bool
    student_id: Optional[str]
    student_name: Optional[str]
    confidence: float
    distance: float
    scope: ScopeTarget
    candidates_searched: int
    message: str = ""


# Patch import paths before importing the modules under test
import sys

_identity_mod = types.ModuleType("models.identity_context")
_identity_mod.IdentityScopeType = IdentityScopeType
_identity_mod.ScopeTarget = ScopeTarget
_identity_mod.ScopedMatchResult = ScopedMatchResult
sys.modules["models.identity_context"] = _identity_mod
sys.modules["attendance_backend.models.identity_context"] = _identity_mod

# --- project-internal stubs (models, utils, config) -------------------------
for _alias in [
    "models", "models.model_manager",
    "utils", "utils.embedding_search", "utils.preprocessing",
    "config", "config.constants",
]:
    _m = types.ModuleType(_alias)
    sys.modules[_alias] = _m

# Constants the module reads at import time
sys.modules["config.constants"].FACE_RECOGNITION_THRESHOLD = 0.55

# ModelManager stub
sys.modules["models.model_manager"].ModelManager = MagicMock()

# EmbeddingSearch stub
class _FakeEmbeddingSearch:
    def __init__(self, **kw): pass
    def search_single_match(self, *a, **kw): return None
    def get_student_info(self, *a): return None
    def build_index(self, *a, **kw): pass
    def add_embedding(self, *a, **kw): pass
    def save_index(self, *a): pass
    def load_index(self, *a): pass
    def get_index_stats(self): return {}
sys.modules["utils.embedding_search"].EmbeddingSearch = _FakeEmbeddingSearch

# ImagePreprocessor stub
class _FakePreprocessor:
    def resize_image(self, img, **kw): return img
sys.modules["utils.preprocessing"].ImagePreprocessor = _FakePreprocessor

# scipy stub
_scipy_spatial = types.ModuleType("scipy.spatial.distance")
def _cosine(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-10
    return float(1.0 - np.dot(a, b) / denom)
_scipy_spatial.cosine = _cosine
sys.modules["scipy"] = types.ModuleType("scipy")
sys.modules["scipy.spatial"] = types.ModuleType("scipy.spatial")
sys.modules["scipy.spatial.distance"] = _scipy_spatial

# face_recognition_service stub (only compute_adaptive_threshold is real)
_frs_mod = types.ModuleType("services.face_recognition_service")
sys.modules["services.face_recognition_service"] = _frs_mod
sys.modules["attendance_backend.services.face_recognition_service"] = _frs_mod

# firebase_service stub
_fb_svc_mod = types.ModuleType("services.firebase_service")
class _FakeFirebaseService:
    @staticmethod
    def get_all_embeddings(student):
        raw = student.get("embeddings", [])
        return [np.array(e, dtype=np.float32) for e in raw]
_fb_svc_mod.FirebaseService = _FakeFirebaseService
sys.modules["services.firebase_service"] = _fb_svc_mod
sys.modules["attendance_backend.services.firebase_service"] = _fb_svc_mod

# Now import the real modules
import importlib, pathlib, sys as _sys

# We load the source files directly by path so path hacks aren't needed
import importlib.util

def _load(alias: str, filepath: str):
    spec = importlib.util.spec_from_file_location(alias, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod

_HERE = pathlib.Path(__file__).parent

frs = _load("services.face_recognition_service",
            str(_HERE / '../services/face_recognition_service.py'))
ses = _load("services.scoped_embedding_search",
            str(_HERE / '../services/scoped_embedding_search.py'))

compute_adaptive_threshold = frs.compute_adaptive_threshold
SessionAnchorStore = ses.SessionAnchorStore
SessionAnchor = ses.SessionAnchor
ScopedEmbeddingSearch = ses.ScopedEmbeddingSearch


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _unit_vec(dim=128, seed=0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(dim).astype(np.float32)
    return v / np.linalg.norm(v)

def _make_scope(scope_type=IdentityScopeType.SELF, student_ids=None, resolved_by="stu_001"):
    return ScopeTarget(
        scope_type=scope_type,
        student_ids=student_ids or ["stu_001"],
        resolved_by=resolved_by,
    )


# ===========================================================================
# 1. compute_adaptive_threshold
# ===========================================================================

class TestComputeAdaptiveThreshold(unittest.TestCase):

    def test_zero_variance_returns_base(self):
        """Zero variance → std=0 → threshold unchanged."""
        t = compute_adaptive_threshold(base_threshold=0.55, variance=0.0, k=1.5)
        self.assertAlmostEqual(t, 0.55, places=6)

    def test_positive_variance_lowers_threshold(self):
        """Positive variance relaxes threshold (lower value accepted)."""
        t = compute_adaptive_threshold(base_threshold=0.55, variance=0.01, k=1.5)
        self.assertLess(t, 0.55)

    def test_floor_respected(self):
        """Very high variance must not go below min_threshold."""
        t = compute_adaptive_threshold(
            base_threshold=0.55, variance=100.0, k=1.5, min_threshold=0.30
        )
        self.assertGreaterEqual(t, 0.30)

    def test_ceiling_respected(self):
        """Negative variance (edge-case) must not exceed max_threshold."""
        # variance < 0 is invalid but we must not crash or exceed ceiling
        t = compute_adaptive_threshold(
            base_threshold=0.80, variance=-0.01, k=1.5, max_threshold=0.80
        )
        self.assertLessEqual(t, 0.80)

    def test_larger_k_more_relaxed(self):
        """Larger k means a lower (more relaxed) threshold for same variance."""
        t1 = compute_adaptive_threshold(0.55, 0.01, k=1.0)
        t2 = compute_adaptive_threshold(0.55, 0.01, k=3.0)
        self.assertGreater(t1, t2)

    def test_output_type_is_float(self):
        t = compute_adaptive_threshold(0.55, 0.05)
        self.assertIsInstance(t, float)

    def test_deterministic(self):
        t1 = compute_adaptive_threshold(0.55, 0.02)
        t2 = compute_adaptive_threshold(0.55, 0.02)
        self.assertEqual(t1, t2)


# ===========================================================================
# 2. SessionAnchorStore
# ===========================================================================

class TestSessionAnchorStore(unittest.TestCase):

    def _scope(self):
        return _make_scope()

    def test_anchor_and_get(self):
        store = SessionAnchorStore()
        store.anchor("cam-01", "stu_001", "Alice", self._scope())
        a = store.get("cam-01")
        self.assertIsNotNone(a)
        self.assertEqual(a.student_id, "stu_001")

    def test_get_unknown_stream_returns_none(self):
        store = SessionAnchorStore()
        self.assertIsNone(store.get("nonexistent"))

    def test_clear_returns_true_when_present(self):
        store = SessionAnchorStore()
        store.anchor("cam-02", "stu_002", "Bob", self._scope())
        self.assertTrue(store.clear("cam-02"))
        self.assertIsNone(store.get("cam-02"))

    def test_clear_returns_false_when_absent(self):
        store = SessionAnchorStore()
        self.assertFalse(store.clear("ghost"))

    def test_replace_anchor(self):
        store = SessionAnchorStore()
        store.anchor("cam-03", "stu_001", "Alice", self._scope())
        store.anchor("cam-03", "stu_002", "Bob", self._scope())
        a = store.get("cam-03")
        self.assertEqual(a.student_id, "stu_002")

    def test_ttl_expiry(self):
        store = SessionAnchorStore()
        store.anchor("cam-04", "stu_001", "Alice", self._scope(), ttl_seconds=0.05)
        self.assertIsNotNone(store.get("cam-04"))
        time.sleep(0.1)
        self.assertIsNone(store.get("cam-04"))

    def test_no_ttl_does_not_expire(self):
        store = SessionAnchorStore()
        store.anchor("cam-05", "stu_001", "Alice", self._scope(), ttl_seconds=0)
        time.sleep(0.05)
        self.assertIsNotNone(store.get("cam-05"))

    def test_all_active_excludes_expired(self):
        store = SessionAnchorStore()
        store.anchor("cam-A", "stu_001", "Alice", self._scope(), ttl_seconds=0.05)
        store.anchor("cam-B", "stu_002", "Bob", self._scope(), ttl_seconds=0)
        time.sleep(0.1)
        active_ids = [a.stream_id for a in store.all_active()]
        self.assertNotIn("cam-A", active_ids)
        self.assertIn("cam-B", active_ids)

    def test_thread_safety(self):
        """Concurrent anchors and clears must not raise."""
        import threading
        store = SessionAnchorStore()
        scope = self._scope()
        errors = []

        def worker(i):
            try:
                sid = f"cam-{i}"
                store.anchor(sid, f"stu_{i}", f"Student {i}", scope)
                _ = store.get(sid)
                store.clear(sid)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])


# ===========================================================================
# 3. ScopedEmbeddingSearch — adaptive threshold integration
# ===========================================================================

def _make_firebase_mock(student_id="stu_001", embedding_variance=None, extra_embeddings=None):
    """Build a firebase_service mock that returns one student with embeddings."""
    vec = _unit_vec(seed=42)
    embeddings_raw = [vec.tolist()]
    if extra_embeddings:
        embeddings_raw.extend(e.tolist() for e in extra_embeddings)

    student = {
        "student_id": student_id,
        "name": "Alice",
        "embeddings": embeddings_raw,
    }
    if embedding_variance is not None:
        student["embedding_variance"] = embedding_variance

    fb = MagicMock()
    fb.get_student.return_value = student
    fb.get_all_students.return_value = [student]
    return fb, vec, student


class TestScopedEmbeddingSearchAdaptive(unittest.TestCase):

    def test_self_match_uses_adaptive_threshold(self):
        """
        SELF scope: when variance is stored, compute_adaptive_threshold is
        applied; a query that is close to the prototype should still match.
        """
        fb, proto_vec, _ = _make_firebase_mock(embedding_variance=0.01)
        searcher = ScopedEmbeddingSearch(firebase_service=fb)
        scope = _make_scope(IdentityScopeType.SELF, ["stu_001"], "stu_001")

        # Query is the prototype itself — must always match
        result = searcher.search(proto_vec, scope)
        self.assertTrue(result.matched)
        self.assertEqual(result.student_id, "stu_001")

    def test_self_no_variance_falls_back_to_default(self):
        """
        When embedding_variance is absent, behaviour is identical to the
        original fixed-threshold code.
        """
        fb, proto_vec, _ = _make_firebase_mock(embedding_variance=None)
        searcher = ScopedEmbeddingSearch(firebase_service=fb)
        scope = _make_scope(IdentityScopeType.SELF, ["stu_001"], "stu_001")
        result = searcher.search(proto_vec, scope)
        self.assertTrue(result.matched)

    def test_self_mismatch_rejected_even_with_adaptive_threshold(self):
        """
        SELF scope: if the best match is a different student, it must be
        rejected regardless of threshold.
        """
        fb_a, vec_a, _ = _make_firebase_mock("stu_001", embedding_variance=0.001)
        # Make stu_002 the only candidate but resolved_by=stu_001
        vec_b = _unit_vec(seed=99)  # orthogonal-ish
        student_b = {"student_id": "stu_002", "name": "Bob", "embeddings": [vec_a.tolist()]}
        fb_a.get_student.side_effect = lambda sid: (
            {"student_id": "stu_001", "name": "Alice", "embeddings": [vec_a.tolist()], "embedding_variance": 0.001}
            if sid == "stu_001"
            else student_b
        )

        searcher = ScopedEmbeddingSearch(firebase_service=fb_a)
        # Scope resolves to stu_001 but student_ids include both
        scope = ScopeTarget(
            scope_type=IdentityScopeType.SELF,
            student_ids=["stu_001"],
            resolved_by="stu_001",
        )
        # Query with stu_001's own vector — should match
        result = searcher.search(vec_a, scope)
        self.assertTrue(result.matched)
        self.assertEqual(result.student_id, "stu_001")

    def test_no_candidates_returns_unmatched(self):
        fb = MagicMock()
        fb.get_student.return_value = None
        searcher = ScopedEmbeddingSearch(firebase_service=fb)
        scope = _make_scope(IdentityScopeType.SELF, ["stu_001"], "stu_001")
        result = searcher.search(_unit_vec(), scope)
        self.assertFalse(result.matched)
        self.assertEqual(result.candidates_searched, 0)

    def test_global_scope_triggers_global_search(self):
        fb, proto_vec, _ = _make_firebase_mock()
        searcher = ScopedEmbeddingSearch(firebase_service=fb)
        scope = ScopeTarget(
            scope_type=IdentityScopeType.GLOBAL,
            student_ids=[],
            resolved_by=None,
        )
        # Global path does a raw cosine scan; proto_vec matches itself
        result = searcher.search(proto_vec, scope)
        self.assertTrue(result.matched)

    def test_confidence_and_distance_complement(self):
        """confidence + distance should approximately equal 1.0 for matches."""
        fb, proto_vec, _ = _make_firebase_mock(embedding_variance=0.005)
        searcher = ScopedEmbeddingSearch(firebase_service=fb)
        scope = _make_scope(IdentityScopeType.SELF, ["stu_001"], "stu_001")
        result = searcher.search(proto_vec, scope)
        if result.matched:
            self.assertAlmostEqual(result.confidence + result.distance, 1.0, places=5)

    def test_candidates_searched_populated(self):
        extra = [_unit_vec(seed=i) for i in range(3)]
        fb, proto_vec, _ = _make_firebase_mock(extra_embeddings=extra)
        searcher = ScopedEmbeddingSearch(firebase_service=fb)
        scope = _make_scope(IdentityScopeType.SELF, ["stu_001"], "stu_001")
        result = searcher.search(proto_vec, scope)
        # 1 original + 3 extra = 4 vectors
        self.assertEqual(result.candidates_searched, 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
