# Backend Quick Reference Guide

## 🚀 Start Backend in 5 Minutes

### 1. Setup
```bash
cd attendance_backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env with your Firebase credentials
```

### 3. Run
```bash
python -m uvicorn main:app --reload
# Visit http://localhost:8000/docs for API docs
```

## 📁 Project Structure Quick Navigation

```
attendance_backend/
├── /config         → App settings, constants, logging
├── /models         → YOLOv8 + FaceNet model wrappers
├── /services       → Detection, recognition, tracking
├── /utils          → Image processing, search, validators
├── /database       → Firebase client and repositories
├── /api            → API routes and endpoints
├── main.py         → FastAPI application
└── requirements.txt → Python dependencies
```

## 🔧 Key Modules and Their Purpose

### Configuration (`/config`)
```python
from config.settings import get_settings  # Get all settings
from config.constants import FACE_RECOGNITION_THRESHOLD
from config.logging_config import logger
```

### Models (`/models`)
```python
from models import ModelManager

# Initialize models at startup
ModelManager.initialize(device="cuda")

# Get detector and extractor
detector = ModelManager.get_yolov8_detector()
extractor = ModelManager.get_facenet_extractor()
```

### Services (`/services`)
```python
from services import AttendanceService

service = AttendanceService()
results = service.process_frame(image, "CS101")
```

### Database (`/database`)
```python
from database import StudentRepository, AttendanceRepository

students_db = StudentRepository()
attendance_db = AttendanceRepository()

# Create student
students_db.create_student("S001", "John Doe", "john@uni.edu")

# Mark attendance
attendance_db.mark_attendance("S001", "CS101", confidence=0.95)
```

### Utilities (`/utils`)
```python
from utils import ImagePreprocessor, EmbeddingSearch, Validators

# Image processing
img = ImagePreprocessor.load_image("face.jpg")
img = ImagePreprocessor.resize_image(img, (160, 160))

# Validation
is_valid = Validators.validate_student_id("S001")
```

## 📊 Configuration Parameters (in `.env`)

### Model Settings
```env
YOLOV8_MODEL_PATH=weights/yolov8n-face.pt
YOLOV8_CONFIDENCE_THRESHOLD=0.5
FACENET_MODEL_PATH=weights/facenet_model.pt
FACE_RECOGNITION_THRESHOLD=0.6
```

### Database
```env
FIREBASE_DATABASE_URL=https://your-project.firebaseio.com
FIREBASE_CREDENTIALS_PATH=config/firebase-credentials.json
```

### API
```env
FASTAPI_ENV=development
HOST=0.0.0.0
PORT=8000
```

## 🔌 API Endpoints (Current)

```
GET  /                  → API root info
GET  /info              → System information
GET  /api/v1/health     → Health check
GET  /api/v1/health/models      → Model status
GET  /api/v1/health/database    → Database status
GET  /api/v1/health/config      → Configuration status
```

**Interactive API docs**: http://localhost:8000/docs

## 💡 Common Tasks

### Process an Image for Attendance
```python
import cv2
from services.attendance_service import AttendanceService

service = AttendanceService()
image = cv2.imread("attendance_frame.jpg")

results = service.process_frame(
    image,
    course_id="CS101",
    auto_mark=True
)

print(f"Detected: {results['faces_detected']}")
print(f"Recognized: {results['faces_recognized']}")
print(f"Marked: {results['attendance_marked']}")
```

### Register a New Student
```python
from database.student_repository import StudentRepository
from services.face_recognition_service import FaceRecognitionService
import cv2
import numpy as np

# Create student record
student_repo = StudentRepository()
student_repo.create_student("S001", "Jane Doe", "jane@uni.edu", "CS101")

# Extract and store face embedding
recognition = FaceRecognitionService()
face_image = cv2.imread("jane_face.jpg")
embedding = recognition.extract_embedding(face_image)

# Add to search index
recognition.add_student_embedding("S001", embedding)
```

### Query Attendance
```python
from database.attendance_repository import AttendanceRepository
from datetime import date

repo = AttendanceRepository()

# Get student attendance
records = repo.get_student_attendance("S001", "CS101")

# Get statistics
stats = repo.get_attendance_statistics(
    "S001",
    "CS101",
    start_date=date(2024, 1, 1)
)
print(f"Attendance: {stats['attendance_percent']}%")
```

## 🧪 Development Tips

### Enable Debug Logging
```bash
LOG_LEVEL=DEBUG python -m uvicorn main:app --reload
```

### Test Face Detection
```python
from models import ModelManager
import cv2

ModelManager.initialize("cpu")
detector = ModelManager.get_yolov8_detector()

image = cv2.imread("test_image.jpg")
detections = detector.detect(image)
print(f"Found {len(detections)} faces")
```

### Check Component Status
```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/health/models
curl http://localhost:8000/api/v1/health/database
```

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| Models not loading | Check `weights/` directory exists |
| Firebase error | Verify credentials path in `.env` |
| Out of memory | Reduce `BATCH_SIZE`, use smaller model |
| Low accuracy | Adjust `FACE_RECOGNITION_THRESHOLD` |
| Duplicate marks | Check `TRACK_BUFFER_SIZE` in `/services/tracking_service.py` |

## 🔗 Integration Points

### With React Web Dashboard
- Base URL: `http://localhost:8000`
- API Prefix: `/api/v1`
- CORS enabled for `localhost:3000`, `localhost:5173`

### With Flutter Mobile App
- Same base URL and prefix
- CORS enabled for `localhost:8080`

## 📝 File Locations

```
Project Root: p:\DAA LAB EL\attendance_backend\

.env                      → Configuration (create from .env.example)
config/
├── settings.py           → Settings management
├── constants.py          → Application constants
├── logging_config.py     → Logging setup
└── __init__.py           → Package init

logs/
├── attendance_system.log → Main application log
└── errors.log            → Errors only

requirements.txt          → Production dependencies
requirements-dev.txt      → Development dependencies
```

## ⚙️ Deployment

### Local Development
```bash
python -m uvicorn main:app --reload
```

### Docker
```bash
docker build -t attendance-backend .
docker run -p 8000:8000 --env-file .env attendance-backend
```

### Production
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
```

## 📚 Documentation Files

- **README.md** - Full documentation
- **BACKEND_IMPLEMENTATION_SUMMARY.md** - Implementation details
- **API docstring at `/docs`** - Interactive API docs

## 🆘 Getting Help

1. Check logs: `tail -f logs/attendance_system.log`
2. API docs: http://localhost:8000/docs
3. Health check: `curl http://localhost:8000/api/v1/health`
4. Module docstrings: `python -c "from models import ModelManager; help(ModelManager)"`

---

**Last Updated**: January 2024  
**Version**: 1.0.0
