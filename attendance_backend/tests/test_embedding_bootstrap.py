"""
tests/test_embedding_bootstrap.py
==================================
Verify that bootstrap_embeddings.py correctly skips already-processed
students, handles missing students, and calls store_embedding for valid photos.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _write_photo(directory: Path, stem: str) -> Path:
    img = Image.new("RGB", (100, 100), color=(100, 150, 200))
    p = directory / f"{stem}.jpg"
    img.save(p)
    return p


class TestBootstrapEmbeddings:
    def test_skips_unknown_student(self, tmp_path):
        _write_photo(tmp_path, "UNKNOWN999")
        mock_firebase = MagicMock()
        mock_firebase.get_student.return_value = None  # student not found

        with patch("scripts.bootstrap_embeddings.get_firebase_service",
                   return_value=mock_firebase), \
             patch("scripts.bootstrap_embeddings.initialize_firebase",
                   return_value=mock_firebase):
            from scripts.bootstrap_embeddings import bootstrap
            bootstrap(tmp_path, dry_run=False)

        mock_firebase.store_embedding.assert_not_called()

    def test_stores_embedding_for_valid_photo(self, tmp_path):
        _write_photo(tmp_path, "STU001")
        embedding = np.random.rand(128).astype(np.float32)
        mock_firebase = MagicMock()
        mock_firebase.get_student.return_value = {"student_id": "STU001", "name": "Bob"}

        with patch("scripts.bootstrap_embeddings.get_firebase_service",
                   return_value=mock_firebase), \
             patch("scripts.bootstrap_embeddings.initialize_firebase",
                   return_value=mock_firebase), \
             patch("scripts.bootstrap_embeddings.extract_embedding",
                   return_value=embedding), \
             patch("services.firebase_service.FirebaseService.get_all_embeddings",
                   return_value=[]):
            from scripts.bootstrap_embeddings import bootstrap
            bootstrap(tmp_path, dry_run=False)

        mock_firebase.store_embedding.assert_called_once()
        call_args = mock_firebase.store_embedding.call_args
        assert call_args[0][0] == "STU001"
        np.testing.assert_array_equal(call_args[0][1], embedding)

    def test_dry_run_does_not_write(self, tmp_path):
        _write_photo(tmp_path, "STU002")
        mock_firebase = MagicMock()
        mock_firebase.get_student.return_value = {"student_id": "STU002"}

        with patch("scripts.bootstrap_embeddings.get_firebase_service",
                   return_value=mock_firebase), \
             patch("scripts.bootstrap_embeddings.initialize_firebase",
                   return_value=mock_firebase), \
             patch("scripts.bootstrap_embeddings.extract_embedding",
                   return_value=np.random.rand(128).astype(np.float32)), \
             patch("services.firebase_service.FirebaseService.get_all_embeddings",
                   return_value=[]):
            from scripts.bootstrap_embeddings import bootstrap
            bootstrap(tmp_path, dry_run=True)

        mock_firebase.store_embedding.assert_not_called()

    def test_skips_student_with_existing_embeddings(self, tmp_path):
        """Students that already have embeddings should be skipped."""
        _write_photo(tmp_path, "STU003")
        existing_emb = np.random.rand(128).astype(np.float32)
        mock_firebase = MagicMock()
        mock_firebase.get_student.return_value = {"student_id": "STU003", "embeddings": [existing_emb.tolist()]}

        with patch("scripts.bootstrap_embeddings.get_firebase_service",
                   return_value=mock_firebase), \
             patch("scripts.bootstrap_embeddings.initialize_firebase",
                   return_value=mock_firebase), \
             patch("services.firebase_service.FirebaseService.get_all_embeddings",
                   return_value=[existing_emb]):
            from scripts.bootstrap_embeddings import bootstrap
            bootstrap(tmp_path, dry_run=False)

        mock_firebase.store_embedding.assert_not_called()
