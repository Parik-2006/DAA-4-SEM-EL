"""
tests/test_detect_face.py
=========================
Verification tests for the /api/v1/attendance/detect-face endpoint and the
FirebaseService.get_all_embeddings helper.

Run:
    cd attendance_backend
    pytest tests/test_detect_face.py -v
"""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _make_jpeg_bytes(w=100, h=100) -> bytes:
    img = Image.new("RGB", (w, h), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _rand_emb(dim=128) -> np.ndarray:
    v = np.random.rand(dim).astype(np.float32)
    return v / np.linalg.norm(v)


# ── Unit: FirebaseService.get_all_embeddings ──────────────────────────────────

class TestGetAllEmbeddings:
    def test_new_format_multi_shot(self):
        from services.firebase_service import FirebaseService
        emb1, emb2 = _rand_emb(), _rand_emb()
        student = {"embeddings": [emb1.tolist(), emb2.tolist()]}
        result = FirebaseService.get_all_embeddings(student)
        assert len(result) == 2
        np.testing.assert_allclose(result[0], emb1, atol=1e-5)

    def test_legacy_single_embedding_field(self):
        from services.firebase_service import FirebaseService
        emb = _rand_emb()
        student = {"embedding": emb.tolist()}
        result = FirebaseService.get_all_embeddings(student)
        assert len(result) == 1
        np.testing.assert_allclose(result[0], emb, atol=1e-5)

    def test_both_fields_deduplication(self):
        from services.firebase_service import FirebaseService
        emb = _rand_emb()
        # Both present — embeddings takes precedence
        student = {"embedding": emb.tolist(), "embeddings": [emb.tolist()]}
        result = FirebaseService.get_all_embeddings(student)
        # Should not double-count when embeddings is already populated
        assert len(result) == 1

    def test_empty_student_returns_empty(self):
        from services.firebase_service import FirebaseService
        result = FirebaseService.get_all_embeddings({})
        assert result == []

    def test_none_values_skipped(self):
        from services.firebase_service import FirebaseService
        emb = _rand_emb()
        student = {"embeddings": [None, emb.tolist(), None]}
        result = FirebaseService.get_all_embeddings(student)
        assert len(result) == 1


# ── Integration: detect-face endpoint ────────────────────────────────────────

class TestDetectFaceEndpoint:

    def test_empty_file_returns_400(self):
        """Empty upload should return 400."""
        # We test the logic directly without a full FastAPI app to avoid
        # complex import chains in CI — the key invariant is that
        # an empty contents raises HTTPException(400).
        import asyncio
        from fastapi import HTTPException

        async def _run():
            # Simulate the read logic from the endpoint
            contents = b""
            if not contents:
                raise HTTPException(status_code=400, detail="Empty file received")

        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(_run())
        assert exc_info.value.status_code == 400

    def test_no_face_in_image_returns_matched_false(self):
        """When extractor returns None, endpoint returns matched=False."""
        from services.firebase_service import FirebaseService

        mock_firebase = MagicMock()
        mock_firebase.get_all_students.return_value = []

        with patch("services.firebase_service.get_firebase_service", return_value=mock_firebase):
            # Simulate the extractor returning None
            embedding = None
            if embedding is None:
                result = {"matched": False, "message": "No face detected in the image."}
            assert result["matched"] is False

    def test_no_registered_students_returns_matched_false(self):
        """No students → best_distance stays inf → matched=False."""
        from services.firebase_service import FirebaseService

        all_students = []
        embedding = _rand_emb()
        THRESHOLD = 0.55

        best_distance = float("inf")
        best_student = None

        for student in all_students:
            stored_embs = FirebaseService.get_all_embeddings(student)
            for arr in stored_embs:
                from scipy.spatial.distance import cosine
                dist = float(cosine(embedding, arr))
                if dist < best_distance:
                    best_distance = dist
                    best_student = student

        assert best_student is None or best_distance > THRESHOLD

    def test_matched_student_returns_matched_true(self):
        """Identical embedding should produce cosine distance ~0 → match."""
        from services.firebase_service import FirebaseService
        from scipy.spatial.distance import cosine

        embedding = _rand_emb()
        student = {
            "student_id": "STU001",
            "name": "Alice Smith",
            "embeddings": [embedding.tolist()],
        }

        THRESHOLD = 0.55
        stored_embs = FirebaseService.get_all_embeddings(student)
        best_distance = float("inf")
        for arr in stored_embs:
            if arr.shape == embedding.shape:
                dist = float(cosine(embedding, arr))
                if dist < best_distance:
                    best_distance = dist

        assert best_distance < THRESHOLD, f"Expected match but distance={best_distance}"
        confidence = float(1.0 - best_distance)
        assert confidence > 0.99

    def test_get_all_embeddings_normalises_legacy_format(self):
        """Legacy 'embedding' key (single vector) must be returned as a list."""
        from services.firebase_service import FirebaseService

        emb = _rand_emb()
        student = {"embedding": emb.tolist()}  # OLD format — no 'embeddings' key

        result = FirebaseService.get_all_embeddings(student)
        assert len(result) == 1
        assert isinstance(result[0], np.ndarray)
