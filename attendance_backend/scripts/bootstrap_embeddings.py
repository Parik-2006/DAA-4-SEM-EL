#!/usr/bin/env python3
"""
bootstrap_embeddings.py
=======================
One-time utility: scan ``student_photos/`` for JPEG/PNG files whose stem
matches a student_id, extract FaceNet embeddings, and upsert them into
Firebase (Firestore or Realtime DB).

Usage
-----
    cd attendance_backend
    python scripts/bootstrap_embeddings.py [--photos-dir student_photos] [--dry-run]

Directory layout expected
-------------------------
    student_photos/
        STU001.jpg
        STU002.png
        ...

The filename stem (without extension) is treated as the student_id.
The student record must already exist in Firebase.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("bootstrap")


def load_image(path: Path) -> np.ndarray:
    img = Image.open(path).convert("RGB")
    return np.array(img)


def extract_embedding(image_array: np.ndarray) -> np.ndarray:
    from models.facenet_extractor import FaceNetExtractor
    extractor = FaceNetExtractor()
    emb = extractor.extract_embedding(image_array)
    if emb is None:
        raise ValueError("No face detected in image")
    return emb


def bootstrap(photos_dir: Path, dry_run: bool) -> None:
    from services.firebase_service import get_firebase_service, FirebaseService, initialize_firebase

    firebase = get_firebase_service()
    if firebase is None:
        creds = os.getenv("FIREBASE_CREDENTIALS_PATH", "config/firebase-credentials.json")
        db_url = os.getenv("FIREBASE_DATABASE_URL")
        bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
        use_fs = os.getenv("USE_FIRESTORE", "True").lower() == "true"
        firebase = initialize_firebase(creds, db_url, bucket, use_fs)

    extensions = {".jpg", ".jpeg", ".png", ".bmp"}
    photos = sorted(p for p in photos_dir.iterdir() if p.suffix.lower() in extensions)

    if not photos:
        log.warning("No images found in %s", photos_dir)
        return

    ok = failed = skipped = 0

    for photo_path in photos:
        student_id = photo_path.stem
        log.info("Processing %s → student_id=%s", photo_path.name, student_id)

        student = firebase.get_student(student_id)
        if student is None:
            log.warning("  Student %s not found in Firebase — skipping", student_id)
            skipped += 1
            continue

        existing = FirebaseService.get_all_embeddings(student)
        if existing:
            log.info("  Already has %d embedding(s) — skipping (use --force to overwrite)", len(existing))
            skipped += 1
            continue

        try:
            image_array = load_image(photo_path)
            embedding = extract_embedding(image_array)
            log.info("  Embedding shape: %s", embedding.shape)

            if dry_run:
                log.info("  [DRY RUN] Would write embedding for %s", student_id)
            else:
                firebase.store_embedding(student_id, embedding)
                log.info("  ✅ Embedding stored for %s", student_id)
            ok += 1
        except ValueError as e:
            log.error("  ❌ %s", e)
            failed += 1
        except Exception as e:
            log.error("  ❌ Unexpected error: %s", e)
            failed += 1

    log.info("")
    log.info("Bootstrap complete: %d stored, %d skipped, %d failed", ok, skipped, failed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap face embeddings from photos")
    parser.add_argument("--photos-dir", default="student_photos",
                        help="Directory containing <student_id>.<ext> photos")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and extract but do not write to Firebase")
    args = parser.parse_args()

    photos_dir = Path(args.photos_dir)
    if not photos_dir.exists():
        log.error("Photos directory not found: %s", photos_dir)
        sys.exit(1)

    bootstrap(photos_dir, args.dry_run)


if __name__ == "__main__":
    main()
