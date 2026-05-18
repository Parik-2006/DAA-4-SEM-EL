Top 5 features to raise 1–2-frame face-detection accuracy (backend-focused)

1) Account‑scoped enrollment & SELF‑VERIFY
- What: Tie a signed-in identity (email/JWT) to a small per-user gallery and use SELF_VERIFY scope first.
- Implemented: `attendance_backend/services/embedding_scope_service.py`, `attendance_backend/services/scoped_embedding_search.py`, `attendance_backend/services/face_attempt_service.py`.
- Missing: server endpoint to trigger `resolve_student_scope` from a login flow (API glue), per-session anchoring cache (session store), and UI enrollment flow (outside backend).
- Files to change: [attendance_backend/services/embedding_scope_service.py](attendance_backend/services/embedding_scope_service.py), [attendance_backend/services/scoped_embedding_search.py](attendance_backend/services/scoped_embedding_search.py), add API route in [attendance_backend/api/attendance.py](attendance_backend/api/attendance.py#L1).

2) Multi-photo enrollment + per-user centroid & variance
- What: Require 5–10 enrollment images; compute centroid and variance for adaptive thresholds.
- Implemented: embedding extraction + FAISS index (see [attendance_backend/services/face_recognition_service.py](attendance_backend/services/face_recognition_service.py), [attendance_backend/services/optimized_attendance_pipeline.py](attendance_backend/services/optimized_attendance_pipeline.py)).
- Missing: storage schema for centroid/variance, enrollment API that accepts multi-sample payloads, code to compute/store per-user stats and use them in matching.
- Files to change: [attendance_backend/services/face_recognition_service.py](attendance_backend/services/face_recognition_service.py), [attendance_backend/services/firebase_service.py](attendance_backend/services/firebase_service.py#L1), add DB fields to Firestore docs.

3) Scoped search + session anchoring
- What: Use IdentityScope (SELF, SECTION_Roster) and after a successful login-face match keep the session anchored so subsequent frames search only that user.
- Implemented: `EmbeddingScopeService` and `ScopedEmbeddingSearch` already provide scoping and cached roster resolve.
- Missing: session anchoring logic (associate RTSP stream/session to a current_user key); API hooks to set/clear anchored scope.
- Files to change: [attendance_backend/services/embedding_scope_service.py](attendance_backend/services/embedding_scope_service.py), [attendance_backend/services/scoped_embedding_search.py](attendance_backend/services/scoped_embedding_search.py), [attendance_backend/services/rtsp_stream_handler.py](attendance_backend/services/rtsp_stream_handler.py#L1).

4) Motion gating + multi-frame aggregation (robust capture)
- What: Use motion detector to gate expensive models and aggregate embeddings across 2–5 frames (voting/averaging) before decision.
- Implemented: `optimized_attendance_pipeline.py` already has MotionDetector, frame-skip, SORT, and TemporalVerification.
- Missing: tuned aggregation policy for 1–2 attempt goal (e.g., aggressive voting + adapt thresholds on SELF_VERIFY), and single-frame fallback for quick confirmation.
- Files to change: [attendance_backend/services/optimized_attendance_pipeline.py](attendance_backend/services/optimized_attendance_pipeline.py), [attendance_backend/services/sorting_tracker.py](attendance_backend/services/sorting_tracker.py#L1).

5) Liveness & metadata fusion (final fused confidence)
- What: Add liveness checks (blink/texture/depth), fuse embedding similarity with liveness, login-origin metadata (device_id, IP, geolocation, time-of-day), and face attempt limits to raise acceptance confidence.
- Implemented: Attempt tracking exists (`face_attempt_service.py`); metadata is partially present in Firestore docs.
- Missing: liveness model integration, metadata-weighted decision function, endpoint to ingest login metadata.
- Files to change: [attendance_backend/services/face_attempt_service.py](attendance_backend/services/face_attempt_service.py), [attendance_backend/services/face_recognition_service.py](attendance_backend/services/face_recognition_service.py), add liveness module placeholder at [attendance_backend/services/liveness.py](attendance_backend/services/liveness.py) (new).

Summary of current coverage (non-Dart)
- Detection: implemented — [attendance_backend/services/face_detection_service.py](attendance_backend/services/face_detection_service.py)
- Embeddings & FAISS: implemented — [attendance_backend/services/face_recognition_service.py](attendance_backend/services/face_recognition_service.py)
- Scoped search: implemented — [attendance_backend/services/scoped_embedding_search.py](attendance_backend/services/scoped_embedding_search.py)
- Motion gating + optimized pipeline: implemented — [attendance_backend/services/optimized_attendance_pipeline.py](attendance_backend/services/optimized_attendance_pipeline.py)
- Attempt limiting: implemented — [attendance_backend/services/face_attempt_service.py](attendance_backend/services/face_attempt_service.py)

Gaps to implement for 1–2 attempt high-confidence flow
- Enrollment API to collect multi-photo samples and compute centroid/variance.
- Session anchoring (bind login to RTSP or session) and prefer SELF_VERIFY scope.
- Liveness model and fusion rule combining embedding score + liveness + metadata.
- Short-circuit logic: if SELF_VERIFY centroid match above adaptive threshold + liveness pass → immediate accept.
- Storage schema: per-user stats and short-term session anchor cache.

Next focus: implement a lightweight backend patch that (A) prefers SELF_VERIFY on a logged-in camera/session, (B) computes/stores per-user centroid/variance at enrollment, and (C) fuses liveness + embedding with metadata-based thresholding.