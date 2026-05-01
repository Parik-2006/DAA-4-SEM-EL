import os
import sys
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
    "STUD_004": "Ved U"
}

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
        # Folder names are student_001, etc.
        folder_name = stud_id.lower().replace("stud_", "student_")
        folder_path = photos_base / folder_name
        
        if not folder_path.exists():
            logger.warning(f"Folder not found: {folder_path}")
            continue
            
        logger.info(f"Processing {name} ({stud_id})...")
        
        # Get first image from folder
        images = list(folder_path.glob("*.jpg")) + list(folder_path.glob("*.png"))
        if not images:
            logger.warning(f"No images in {folder_path}")
            continue
            
        try:
            img = Image.open(images[0]).convert("RGB")
            img_arr = np.array(img)
            embedding = extractor.extract_embedding(img_arr)
            
            if embedding is not None:
                # Register student
                firebase.register_student(
                    student_id=stud_id,
                    name=name,
                    email=f"{stud_id.lower()}@example.com",
                    embeddings=embedding
                )
                logger.info(f"✅ Registered {name}")
            else:
                logger.error(f"❌ Failed to extract face for {name}")
        except Exception as e:
            logger.error(f"❌ Error processing {name}: {e}")

if __name__ == "__main__":
    seed()
