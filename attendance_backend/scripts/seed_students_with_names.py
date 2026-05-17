import os
import sys
import re
from pathlib import Path
import logging
import numpy as np
from PIL import Image

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.firebase_service import initialize_firebase, get_firebase_service
from models.facenet_extractor import FaceNetExtractor

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed")

# Mapping from STUD_ID to Name
STUDENT_MAPPING = {
    "STUD_001": "Parikshith B Bilchode",
    "STUD_002": "Gagan D K",
    "STUD_003": "Prajwal K",
    "STUD_004": "Ved U",
    "STUD_005": "Pranav Kumar M",
    "STUD_006": "Nischith G A"
}


def _normalize_folder_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _resolve_folder_path(photos_base: Path, stud_id: str, name: str) -> Path | None:
    candidates = [
        stud_id.lower(),
        stud_id.lower().replace("stud_", "student_"),
        _normalize_folder_name(name),
        _normalize_folder_name(f"{name}_{stud_id}"),
    ]

    for candidate in dict.fromkeys(candidates):
        folder = photos_base / candidate
        if folder.exists() and folder.is_dir():
            return folder
    return None

def seed():
    # Initialize Firebase
    creds = os.getenv("FIREBASE_CREDENTIALS_PATH", "config/firebase-credentials.json")
    db_url = os.getenv("FIREBASE_DATABASE_URL")
    bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
    firebase = initialize_firebase(creds, db_url, bucket, use_firestore=True)
    
    extractor = FaceNetExtractor()
    
    photos_base = Path("test_data/student_photos")
    if not photos_base.exists():
        logger.error(f"Directory not found: {photos_base}")
        return

    for stud_id, name in STUDENT_MAPPING.items():
        folder_path = _resolve_folder_path(photos_base, stud_id, name)

        if folder_path is None:
            logger.warning(f"Folder not found for {name} ({stud_id})")
            continue
            
        logger.info(f"Processing {name} ({stud_id})...")
        
        # Use every valid image in the folder so the student gets multiple
        # embeddings. This improves recognition stability in live camera scans.
        images = (
            sorted(folder_path.glob("*.jpg"))
            + sorted(folder_path.glob("*.jpeg"))
            + sorted(folder_path.glob("*.png"))
        )
        if not images:
            logger.warning(f"No images in {folder_path}")
            continue

        embeddings: list[np.ndarray] = []
        try:
            for image_path in images:
                img = Image.open(image_path).convert("RGB")
                img_arr = np.array(img)
                embedding = extractor.extract_embedding(img_arr)
                if embedding is not None:
                    embeddings.append(embedding)

            if embeddings:
                # Register the first embedding, then append the remaining ones.
                firebase.register_student(
                    student_id=stud_id,
                    name=name,
                    email=f"{stud_id.lower()}@example.com",
                    embeddings=embeddings[0]
                )

                for extra_embedding in embeddings[1:]:
                    firebase.store_embedding(stud_id, extra_embedding)

                logger.info(f"✅ Registered {name} with {len(embeddings)} embedding(s)")
            else:
                logger.error(f"❌ Failed to extract face for {name} from any image")
        except Exception as e:
            logger.error(f"❌ Error processing {name}: {e}")

if __name__ == "__main__":
    seed()
