# Live Camera Attendance — Fix Runbook
## Root-cause summary & verification guide

---

## What was broken and why

| Area | Problem | Fix |
|---|---|---|
| `api.ts` `detectAndMarkAttendance` | Fell back to POSTing base64 as a URL **query param** (`mark-mobile?image_base64=…`). 1–5 MB images cause HTTP 414 (URI Too Long), leak image data in server access logs, and produce opaque failures. | Removed the fallback entirely. Only `multipart/form-data POST /detect-face` is used. All errors are now returned as `DetectFaceResponse { matched: false, message }` so the UI can display them. |
| `LiveCamera.tsx` | `matched === false` was silently ignored. Only `matched === true` surfaced anything to the parent. "No face", "not registered", and server errors all produced the same invisible no-op. | Added `lastFeedback` state with three severity levels (info/warn/error). A banner renders in-frame. Persistent server errors after 3 consecutive failures stop the camera and call `onAttendanceMarked({ status: 'error' })`. |
| `firebase_service.py` `store_embedding` | Wrote only `embedding` (single vector). `attendance.py` read only `embeddings` (array of arrays). A student registered via the mobile app had an `embedding` key; the web matcher read `embeddings` and found nothing → every face came back unrecognised. | `register_student` now writes **both** keys. `get_all_embeddings()` static helper normalises all three storage layouts: `embeddings` list, legacy `embedding` key, or both. |
| `attendance.py` detect-face | Used `student.get("embeddings", [])` raw — broke silently when the field was a single vector instead of a list. Shape mismatches during cosine comparison raised cryptic errors. | Now calls `FirebaseService.get_all_embeddings(student)` which always returns `List[np.ndarray]`. Adds shape-mismatch logging. Improved response payload order (record_id before student_name). |
| Bootstrap / no embeddings | No way to seed embeddings from existing student photos without writing custom Firebase queries. | `scripts/bootstrap_embeddings.py` scans `student_photos/<student_id>.jpg` and calls `store_embedding`. Idempotent (skips students that already have embeddings). |
| CORS | `127.0.0.1` variants of localhost were missing. Long image URLs in mark-mobile triggered pre-flight failures. | Added `127.0.0.1:3000/5173/8080` to `CORS_ALLOWED_ORIGINS`. Added `CORS_ALLOW_ALL_LOCALHOST=true` env-var escape hatch. |

---

## Applying the patch

```bash
# From the repo root:
git apply live-camera-fix.patch

# OR apply section by section if you prefer manual review:
# 1. web-dashboard/src/services/api.ts
# 2. web-dashboard/src/components/LiveCamera.tsx
# 3. attendance_backend/services/firebase_service.py
# 4. attendance_backend/api/attendance.py
# 5. attendance_backend/config/constants.py
# 6. attendance_backend/scripts/bootstrap_embeddings.py  (new file)
# 7. attendance_backend/tests/test_detect_face.py        (new file)
# 8. attendance_backend/tests/test_embedding_bootstrap.py (new file)
```

---

## Verification — Backend (pytest)

```bash
cd attendance_backend
pip install pytest pillow scipy numpy --break-system-packages

# Run all new tests (mocked — no Firebase / GPU needed)
pytest tests/test_detect_face.py tests/test_embedding_bootstrap.py -v
```

**Expected output (all passing):**

```
tests/test_detect_face.py::TestGetAllEmbeddings::test_new_format_multi_shot        PASSED
tests/test_detect_face.py::TestGetAllEmbeddings::test_legacy_single_embedding_field PASSED
tests/test_detect_face.py::TestGetAllEmbeddings::test_both_fields_deduplication    PASSED
tests/test_detect_face.py::TestGetAllEmbeddings::test_empty_student_returns_empty  PASSED
tests/test_detect_face.py::TestGetAllEmbeddings::test_none_values_skipped          PASSED
tests/test_detect_face.py::TestDetectFaceEndpoint::test_empty_file_returns_400     PASSED
tests/test_detect_face.py::TestDetectFaceEndpoint::test_no_face_in_image_...       PASSED
tests/test_detect_face.py::TestDetectFaceEndpoint::test_no_registered_students...  PASSED
tests/test_detect_face.py::TestDetectFaceEndpoint::test_matched_student_...        PASSED
tests/test_embedding_bootstrap.py::TestBootstrapEmbeddings::test_skips_unknown...  PASSED
tests/test_embedding_bootstrap.py::TestBootstrapEmbeddings::test_stores_embedding  PASSED
tests/test_embedding_bootstrap.py::TestBootstrapEmbeddings::test_dry_run_...       PASSED
============ 12 passed in X.Xs ============
```

---

## Verification — Live endpoint with curl

Start the backend:

```bash
cd attendance_backend
docker compose up -d --build
# or: uvicorn main:app --reload --port 8000
```

### Case 1: Detect-face success (valid face, student registered)

```bash
# First register a test student (requires a real FaceNet model loaded)
# Then send a photo:
curl -s -X POST http://localhost:8000/api/v1/attendance/detect-face \
  -F "file=@/path/to/student_face.jpg" | python3 -m json.tool
```

**Expected:**
```json
{
  "matched": true,
  "message": "Attendance marked successfully for Alice Smith",
  "record_id": "AbCdEf...",
  "student_name": "Alice Smith",
  "student_id": "STU001",
  "confidence": 0.9712,
  "timestamp": "2026-04-23T10:00:00.000000"
}
```

### Case 2: Unmatched face

```bash
curl -s -X POST http://localhost:8000/api/v1/attendance/detect-face \
  -F "file=@/path/to/unknown_face.jpg" | python3 -m json.tool
```

**Expected:**
```json
{
  "matched": false,
  "message": "Face not recognised. Best similarity: 0.43 (threshold: 0.45). ..."
}
```
HTTP status is **200** (not 404) — the detection ran fine, just no match.

### Case 3: Missing / no embeddings for student

If a student exists in Firebase but has no `embedding` or `embeddings` field:

```bash
curl -s -X POST http://localhost:8000/api/v1/attendance/detect-face \
  -F "file=@face.jpg" | python3 -m json.tool
```

**Expected** (student ID appears in best-match but embeddings list is empty → treated as no match):
```json
{
  "matched": false,
  "message": "Face not recognised. Best similarity: 0.00 (threshold: 0.45). ..."
}
```

### Case 4: Empty file

```bash
curl -s -X POST http://localhost:8000/api/v1/attendance/detect-face \
  -F "file=@/dev/null;type=image/jpeg" | python3 -m json.tool
```

**Expected:**
```json
{"detail": "Empty file received"}
```
HTTP **400**.

### Case 5: Confirm mark-mobile still works for backward compat (mobile app)

```bash
# Valid student_id + small base64 image (mobile-sized, <1 KB test image)
python3 -c "
import base64, io
from PIL import Image
buf = io.BytesIO()
Image.new('RGB',(50,50)).save(buf,'JPEG')
print(base64.b64encode(buf.getvalue()).decode())
" > /tmp/b64.txt

STUDENT_ID=STU001
B64=$(cat /tmp/b64.txt)
curl -s -X POST \
  "http://localhost:8000/api/v1/attendance/mark-mobile?student_id=${STUDENT_ID}&image_base64=${B64}" \
  | python3 -m json.tool
```
Expect a 200 or 404 depending on whether embeddings exist — the endpoint
remains available for the Flutter app but is NOT used by the web frontend.

---

## Verification — Frontend (browser DevTools)

1. Start the dashboard: `cd web-dashboard && npm run dev`
2. Open `http://localhost:3000/attendance`, choose **Live Camera**.
3. Click **Start Camera** — allow permission.

**Scenario A — No face centred:**
> The in-camera banner should show **"👁 Centre your face in the frame…"** (blue).

**Scenario B — Face detected but not registered:**
> Banner turns **red**: "❌ No face profile registered. Ask admin to register your face."

**Scenario C — Server error (kill backend mid-scan):**
> Banner turns **red**: "⚠️ Server error (503): …"
> After 3 consecutive errors the camera stops automatically.

**Scenario D — Successful match:**
> Banner shows **"✅ Recognised: Alice Smith"** then camera stops and the
> parent page shows the success card.

**Network tab confirmation:** every detection attempt sends a `POST` to
`/api/v1/attendance/detect-face` with `Content-Type: multipart/form-data`.
No request to `mark-mobile` should appear.

---

## Bootstrapping embeddings from existing photos

```bash
cd attendance_backend
mkdir -p student_photos
# Copy photos named <student_id>.jpg:
cp /path/to/photos/STU001.jpg student_photos/
cp /path/to/photos/STU002.jpg student_photos/

# Dry run first:
python scripts/bootstrap_embeddings.py --photos-dir student_photos --dry-run

# Then for real:
python scripts/bootstrap_embeddings.py --photos-dir student_photos
```

**Expected output:**
```
INFO  Processing STU001.jpg → student_id=STU001
INFO    Embedding shape: (128,)
INFO    ✅ Embedding stored for STU001
INFO  Processing STU002.jpg → student_id=STU002
INFO    Embedding shape: (128,)
INFO    ✅ Embedding stored for STU002
INFO
INFO  Bootstrap complete: 2 stored, 0 skipped, 0 failed
```

---

## Environment checklist

| Variable | Where | Required value |
|---|---|---|
| `VITE_API_BASE_URL` | `web-dashboard/.env` | `http://localhost:8000` (no trailing slash) |
| `FIREBASE_CREDENTIALS_PATH` | `attendance_backend/.env` | Path to service-account JSON |
| `USE_FIRESTORE` | `attendance_backend/.env` | `True` (or `False` for Realtime DB) |
| `CORS_ALLOW_ALL_LOCALHOST` | `attendance_backend/.env` | `true` during dev (optional) |
