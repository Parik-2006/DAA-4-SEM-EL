# 🔥 Firebase Setup Guide

Complete step-by-step guide to configure Firebase for the Attendance System.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Create Firebase Project](#create-firebase-project)
3. [Set Up Database](#set-up-database)
4. [Get Admin Credentials](#get-admin-credentials)
5. [Configure Local Environment](#configure-local-environment)
6. [Verify Connection](#verify-connection)
7. [Database Schema](#database-schema)
8. [Environment Options](#environment-options)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Google Account (personal or organizational)
- Administrator or Editor role in Google Cloud
- Internet connection
- Text editor for configuration files

---

## Create Firebase Project

### Step 1: Visit Firebase Console

1. Open https://console.firebase.google.com/
2. Click **+ Add Project**
3. Enter project name: `attendance-system` (or your preferred name)

### Step 2: Configure Project

```
Name: attendance-system
Analytics: ✓ Enable (optional)
```

4. Click **Create Project**
5. Wait 30-60 seconds for initialization

### Step 3: Select Project

Once created, you'll be redirected to the Firebase console. You're now in your project dashboard.

---

## Set Up Database

### Option A: Firestore (Recommended for Complex Queries)

**Best For:**
- Complex filtering and aggregation
- Better query capabilities
- Document-based structure
- Easier scaling

#### 1. Navigate to Firestore Database

1. In Firebase Console, open **Build** → **Firestore Database**
2. Click **Create Database**

#### 2. Configure Firestore

```
Region: us-central1 (or closest to you)
Mode: Start in production mode
```

3. Click **Create**

#### 4. Set Up Security Rules

Replace default rules with:

```firestore
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Allow admin to read/write everything (authenticate via Firebase Admin SDK)
    match /{document=**} {
      allow read, write: if request.auth.uid != null;
      allow read, write: if request.auth == null; // For backend service account
    }
    
    // Students collection
    match /students/{student_id} {
      allow read, write: if request.auth == null; // Backend service account
      allow read: if request.auth.uid != null;
    }
    
    // Attendance collection
    match /attendance/{record_id} {
      allow read, write: if request.auth == null;
      allow read: if request.auth.uid != null;
    }
    
    // Embeddings collection
    match /embeddings/{document=**} {
      allow read, write: if request.auth == null;
    }
    
    // Sessions collection
    match /sessions/{document=**} {
      allow read, write: if request.auth == null;
    }
  }
}
```

Click **Publish**

### Option B: Realtime Database (Recommended for Real-time Updates)

**Best For:**
- Real-time stream data
- Simpler data structure
- Lower latency
- RTSP stream metrics

#### 1. Navigate to Realtime Database

1. In Firebase Console, open **Build** → **Realtime Database**
2. Click **Create Database**

#### 2. Configure Realtime DB

```
Location: us-central1 (or closest to you)
Security Rules: Start in test mode
```

3. Click **Enable**

#### 4. Set Up Security Rules

Replace default rules with:

```json
{
  "rules": {
    ".read": true,
    ".write": true,
    "students": {
      ".indexOn": ["email", "registered_at"]
    },
    "attendance": {
      ".indexOn": ["student_id", "timestamp", "date"]
    },
    "embeddings": {
      ".indexOn": ["student_id"]
    },
    "sessions": {
      ".indexOn": ["created_at"]
    }
  }
}
```

Click **Publish**

---

## Get Admin Credentials

### Step 1: Access Project Settings

1. In Firebase Console, click ⚙️ **Project Settings** (top left)
2. Go to **Service Accounts** tab

### Step 2: Generate Private Key

1. Click **Generate New Private Key**
2. A JSON file will download automatically
3. **Save this file securely**: `config/firebase-credentials.json`

**Important**: Never commit this file to version control!

### Step 3: Add to .gitignore

```bash
echo "config/firebase-credentials.json" >> .gitignore
```

### Step 4: Verify File Contents

The JSON should look like:

```json
{
  "type": "service_account",
  "project_id": "attendance-system-xxxxx",
  "private_key_id": "xxxxx",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...",
  "client_email": "firebase-adminsdk-xxxxx@attendance-system-xxxxx.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/..."
}
```

---

## Configure Local Environment

### Step 1: Copy Environment Template

```bash
cp .env.example .env
```

### Step 2: Edit .env

Add Firebase configuration:

```env
# Firebase Configuration
FIREBASE_CREDENTIALS_PATH=config/firebase-credentials.json
FIREBASE_DATABASE_URL=https://your-project.firebaseio.com
USE_FIRESTORE=True  # Use Firestore
# OR
USE_FIRESTORE=False  # Use Realtime Database

# API Configuration
FASTAPI_ENV=development
API_TITLE=Attendance System API
API_VERSION=1.0.0
API_PREFIX=/api/v1

# Processing Configuration
PROCESSING_DEVICE=cuda  # or 'cpu'
BATCH_SIZE=32
NUM_WORKERS=4
FRAME_SKIP=2
MIN_CONSECUTIVE_FRAMES=5
ATTENDANCE_CONFIDENCE_THRESHOLD=0.6

# RTSP Configuration
RTSP_BUFFER_SIZE=1
RECONNECT_ATTEMPTS=5
RECONNECT_DELAY=5

# CORS
CORS_ALLOWED_ORIGINS=["http://localhost:3000", "http://localhost:8000"]
```

### Step 3: Verify Keys

From Firebase Console **Settings** → **General**:

```
Project ID: attendance-system-xxxxx
```

From the credentials JSON:

```json
{
  "project_id": "attendance-system-xxxxx"
}
```

These should match!

---

## Verify Connection

### Test 1: Python Import

```bash
python -c "import firebase_admin; print('✓ Firebase Admin SDK installed')"
```

### Test 2: Connection Test

Create `test_firebase_connection.py`:

```python
import os
import json
from firebase_admin import initialize_app, credentials, firestore, db

credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "config/firebase-credentials.json")

if not os.path.exists(credentials_path):
    print(f"❌ Credentials file not found: {credentials_path}")
    exit(1)

try:
    # Initialize Firebase
    cred = credentials.Certificate(credentials_path)
    app = initialize_app(cred, {
        'databaseURL': os.getenv("FIREBASE_DATABASE_URL")
    })
    
    print("✓ Firebase initialized successfully")
    
    # Test Firestore
    try:
        firestore_db = firestore.client()
        # Try to read a collection to verify access
        docs = firestore_db.collection('students').limit(1).stream()
        print("✓ Firestore connection successful")
    except Exception as e:
        print(f"⚠ Firestore unavailable: {e}")
    
    # Test Realtime Database
    try:
        rtdb = db.reference()
        rtdb.set({"test": "connection"})
        print("✓ Realtime Database connection successful")
    except Exception as e:
        print(f"⚠ Realtime Database unavailable: {e}")
        
except Exception as e:
    print(f"❌ Firebase connection failed: {e}")
    exit(1)
```

Run test:

```bash
python test_firebase_connection.py
```

Expected output:

```
✓ Firebase initialized successfully
✓ Firestore connection successful
```

### Test 3: API Health Check

```bash
# Start the server
python main.py

# In another terminal
curl http://localhost:8000/api/v1/attendance/health

# Should show:
# {
#   "status": "healthy",
#   "services": {
#     "firebase": "healthy",
#     "streams": "healthy"
#   }
# }
```

---

## Database Schema

### Firestore Collections

#### 1. Students Collection

```
/students/{student_id}
├── student_id: STRING
├── name: STRING
├── email: STRING (indexed)
├── phone: STRING
├── registered_at: TIMESTAMP (indexed)
├── last_seen: TIMESTAMP
├── attendance_count: INTEGER
├── status: STRING (active/inactive)
└── metadata: MAP
    ├── department: STRING
    └── section: STRING
```

**Create Example:**

```python
from firebase_admin import firestore

db = firestore.client()

db.collection('students').document('STU001').set({
    'student_id': 'STU001',
    'name': 'John Doe',
    'email': 'john@college.edu',
    'phone': '+1234567890',
    'registered_at': firestore.SERVER_TIMESTAMP,
    'last_seen': None,
    'attendance_count': 0,
    'status': 'active'
})
```

#### 2. Attendance Collection

```
/attendance/{record_id}
├── record_id: STRING (auto-generated)
├── student_id: STRING (indexed)
├── timestamp: TIMESTAMP (indexed)
├── date: STRING (indexed)
├── time: STRING
├── confidence: FLOAT
├── track_id: INTEGER
├── camera_id: STRING
├── status: STRING (present/absent)
└── metadata: MAP
```

#### 3. Embeddings Collection

```
/embeddings/{embedding_id}
├── student_id: STRING (indexed)
├── embedding: ARRAY (128 floats)
├── created_at: TIMESTAMP
├── quality_score: FLOAT
└── face_region: MAP
```

#### 4. Sessions Collection

```
/sessions/{session_id}
├── session_id: STRING
├── camera_id: STRING
├── start_time: TIMESTAMP
├── end_time: TIMESTAMP
├── total_detections: INTEGER
└── status: STRING (active/completed)
```

### Realtime Database Structure

```
{
  "students": {
    "STU001": {
      "name": "John Doe",
      "email": "john@college.edu",
      ...
    }
  },
  "attendance": {
    "2024-04-10": {
      "REC001": {...}
    }
  },
  "embeddings": {
    "STU001": {
      "EMP001": [...128 values...]
    }
  },
  "sessions": {
    "SESSION001": {...}
  }
}
```

---

## Environment Options

### Using Firestore

Recommended for complex queries and better scaling.

```env
USE_FIRESTORE=True
FIREBASE_CREDENTIALS_PATH=config/firebase-credentials.json
FIREBASE_DATABASE_URL=  # Not needed for Firestore
```

### Using Realtime Database

Recommended for real-time updates and simpler structure.

```env
USE_FIRESTORE=False
FIREBASE_CREDENTIALS_PATH=config/firebase-credentials.json
FIREBASE_DATABASE_URL=https://your-project.firebaseio.com
```

### Both Database Types

System automatically detects which to use based on `USE_FIRESTORE` setting.

```python
# services/firebase_service.py
if use_firestore:
    self.db = firestore.client()
else:
    self.firebase_db = db.reference()
```

---

## Troubleshooting

### Issue: Credentials File Not Found

**Error:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'config/firebase-credentials.json'
```

**Solution:**
```bash
# Verify file exists
ls -la config/firebase-credentials.json

# Or download again from Firebase Console
# Project Settings → Service Accounts → Generate Key
```

### Issue: Invalid Credentials

**Error:**
```
google.auth.exceptions.DefaultCredentialsError: Could not automatically determine credentials
```

**Solution:**
```bash
# Verify credentials path in .env
cat .env | grep FIREBASE_CREDENTIALS_PATH

# Verify JSON is valid
python -c "import json; json.load(open('config/firebase-credentials.json'))"
```

### Issue: Firestore Database Not Active

**Error:**
```
Error: FAILED_PRECONDITION: The operation could not be completed. This typically indicates that you are attempting to write to a document that does not exist
```

**Solution:**
1. Go to Firebase Console → Firestore Database
2. Verify database is in "Active" state
3. Create first document manually if needed

### Issue: Realtime Database Connection Timeout

**Error:**
```
ConnectionError: Failed to establish connection to Realtime Database
```

**Solution:**
1. Verify URL format: `https://project.firebaseio.com`
2. Check network connectivity: `ping -c 1 firebaseio.com`
3. Verify security rules allow access

### Issue: Permission Denied

**Error:**
```
PermissionError: Missing or insufficient permissions
```

**Solution:**
1. Go to Firebase Console → Database → Security Rules
2. Use provided rules from [Set Up Database](#set-up-database)
3. Click **Publish**

### Issue: Environment Variable Not Loaded

**Error:**
```
KeyError: 'FIREBASE_CREDENTIALS_PATH'
```

**Solution:**
```bash
# Verify .env exists
ls -la .env

# Reload environment
source venv/bin/activate
pip install python-dotenv
```

Or in code:

```python
import os
from dotenv import load_dotenv

load_dotenv()  # Load .env file
credentials_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
```

### Issue: Duplicate Student Registration Fails

**Error:**
```
Student with ID STU001 already exists
```

**Solution:**
```bash
# Check if student exists
curl http://localhost:8000/api/v1/attendance/students/STU001

# If exists, either:
# 1. Use different student ID
# 2. Delete student from Firebase first
# 3. Update student instead
```

---

## Quick Migration Between Databases

### From Realtime DB to Firestore

```python
from firebase_admin import db, firestore

# Get all data from RTDB
rtdb = db.reference()
data = rtdb.get().val()

# Write to Firestore
firestore_db = firestore.client()
for collection, documents in data.items():
    for doc_id, doc_data in documents.items():
        firestore_db.collection(collection).document(doc_id).set(doc_data)
```

### From Firestore to Realtime DB

```python
from firebase_admin import firestore, db

firestore_db = firestore.client()
rtdb = db.reference()

# Export all collections
for collection in ['students', 'attendance', 'embeddings', 'sessions']:
    docs = firestore_db.collection(collection).stream()
    for doc in docs:
        rtdb.child(collection).child(doc.id).set(doc.to_dict())
```

---

## Performance Tips

### Firestore Optimization

```env
# Add indexes for better query performance
# Index on students(email, registered_at)
# Index on attendance(student_id, timestamp)
```

### Realtime DB Optimization

```json
{
  "rules": {
    "students": {
      ".indexOn": ["email", "registered_at", "status"]
    },
    "attendance": {
      ".indexOn": ["student_id", "date", "timestamp"]
    }
  }
}
```

### Batching Operations

```python
# Batch writes for better performance
batch = firestore_db.batch()

for student in students_list:
    batch.set(firestore_db.collection('students').document(student['id']), student)

batch.commit()
```

---

## Backup & Export

### Export Firestore

```bash
gcloud firestore export gs://your-bucket/firestore-backup
```

### Export Realtime DB

```bash
gcloud database instances describe your-database --format="value(databaseUrl)"
gcloud database export gs://your-bucket/rtdb-backup
```

---

## Security Best Practices

✅ **DO:**
- Keep credentials file outside version control
- Use `.gitignore` to exclude credentials
- Use environment variables for sensitive data
- Enable Firebase security rules
- Rotate credentials periodically
- Use service accounts with minimal permissions

❌ **DON'T:**
- Commit service account keys to git
- Share credentials in Slack/Email
- Use credentials in public code
- Allow overly permissive security rules
- Use old/unused service accounts

---

## Support

**Resources:**
- [Firebase Documentation](https://firebase.google.com/docs)
- [Firestore Best Practices](https://firebase.google.com/docs/firestore/best-practices)
- [RTDB Documentation](https://firebase.google.com/docs/database)
- [Firebase Console](https://console.firebase.google.com/)

**Get Help:**
- Check API logs: Firebase Console → **Logs**
- Enable debug logging in code
- Contact Firebase Support

---

**Version**: 1.0  
**Last Updated**: 2024  
**Status**: ✅ Complete
