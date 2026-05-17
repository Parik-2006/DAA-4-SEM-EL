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
import re
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


def normalize_folder_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def resolve_student_id(folder_name: str) -> str:
    """Infer a student id when the folder name already follows an ID pattern.

    This utility stays conservative: if the folder is a human name, it should
    be paired with an explicit mapping file or use the named seeder script.
    """
    normalized = normalize_folder_name(folder_name)
    if normalized.startswith("student_") or normalized.startswith("stud_"):
        return normalized
    return folder_name


def bootstrap(photos_dir: Path, dry_run: bool) -> None:
    from services.firebase_service import get_firebase_service, FirebaseService, initialize_firebase

    if not photos_dir.exists():
        log.warning("No images found in %s", photos_dir)
        return
    folder_candidates = [p for p in photos_dir.iterdir() if p.is_dir()]
    if not folder_candidates:
        folder_candidates = [photos_dir]

    ok = failed = skipped = 0

    # If dry-run, avoid initializing Firebase (credentials may not be present).
    if dry_run:
        for folder_path in folder_candidates:
            student_id = resolve_student_id(folder_path.name)
            log.info("Processing %s → student_id=%s", folder_path.name, student_id)

            try:
                extensions = {".jpg", ".jpeg", ".png", ".bmp"}
                images = sorted(p for p in folder_path.iterdir() if p.suffix.lower() in extensions)
                if not images:
                    log.warning("  No images found in %s", folder_path)
                    skipped += 1
                    continue

                embeddings: list[np.ndarray] = []
                for photo_path in images:
                    image_array = load_image(photo_path)
                    embedding = extract_embedding(image_array)
                    log.info("  %s embedding shape: %s", photo_path.name, embedding.shape)
                    embeddings.append(embedding)

                log.info("  [DRY RUN] Would write %d embedding(s) for %s", len(embeddings), student_id)
                ok += 1
            except ValueError as e:
                log.error("  ❌ %s", e)
                failed += 1
            except Exception as e:
                log.error("  ❌ Unexpected error: %s", e)
                failed += 1
        log.info("")
        log.info("Bootstrap dry-run complete: %d processed, %d skipped, %d failed", ok, skipped, failed)
        return

    # Non-dry-run: initialize Firebase and write embeddings
    firebase = get_firebase_service()
    if firebase is None:
        creds = os.getenv("FIREBASE_CREDENTIALS_PATH", "config/firebase-credentials.json")
        db_url = os.getenv("FIREBASE_DATABASE_URL")
        bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
        use_fs = os.getenv("USE_FIRESTORE", "True").lower() == "true"
        firebase = initialize_firebase(creds, db_url, bucket, use_fs)

    for folder_path in folder_candidates:
        student_id = resolve_student_id(folder_path.name)
        log.info("Processing %s → student_id=%s", folder_path.name, student_id)

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
            extensions = {".jpg", ".jpeg", ".png", ".bmp"}
            images = sorted(p for p in folder_path.iterdir() if p.suffix.lower() in extensions)
            if not images:
                log.warning("  No images found in %s", folder_path)
                skipped += 1
                continue

            embeddings: list[np.ndarray] = []
            for photo_path in images:
                image_array = load_image(photo_path)
                embedding = extract_embedding(image_array)
                log.info("  %s embedding shape: %s", photo_path.name, embedding.shape)
                embeddings.append(embedding)

            firebase.store_embedding(student_id, embeddings[0])
            for embedding in embeddings[1:]:
                firebase.store_embedding(student_id, embedding)
            log.info("  ✅ Embedding stored for %s (%d image(s))", student_id, len(embeddings))
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
