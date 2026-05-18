Below are 10 Claude prompts (each a separate paragraph) to hand off implementation tasks. Each prompt lists the exact backend files to inspect/update and the inputs the assistant should expect. Use lightweight changes (small functions, config flags, DB fields) and keep runtime overhead minimal.

1) "Implement SELF_VERIFY-first pipeline and session anchoring"
Files: [attendance_backend/services/embedding_scope_service.py](attendance_backend/services/embedding_scope_service.py), [attendance_backend/services/scoped_embedding_search.py](attendance_backend/services/scoped_embedding_search.py), [attendance_backend/services/rtsp_stream_handler.py](attendance_backend/services/rtsp_stream_handler.py#L1), [attendance_backend/api/attendance.py](attendance_backend/api/attendance.py#L1)
Inputs: JWT-authenticated `user_id` (string), `session_id` or `stream_id` (string), optional `force_scope` flag.
Task: Modify the attendance processing path so that when an authenticated user is active on a camera/session, the pipeline resolves a SELF_VERIFY scope and caches an anchored scope for the session. Short-circuit search to only this user's embeddings first. Provide API endpoints: `POST /api/v1/attendance/anchor` (body: {session_id, user_id}) and `DELETE /api/v1/attendance/anchor`.

2) "Add multi-photo enrollment API + centroid/variance computation"
Files: [attendance_backend/services/face_recognition_service.py](attendance_backend/services/face_recognition_service.py), [attendance_backend/services/firebase_service.py](attendance_backend/services/firebase_service.py#L1), [attendance_backend/api/user.py](attendance_backend/api/user.py#L1)
Inputs: `user_id` (string), list of images (multipart/form-data or base64 array), enrollment metadata (device_id, location).
Task: Implement `POST /api/v1/user/enroll` that accepts 5+ images, extracts embeddings, computes normalized centroid and per-dimension variance, stores centroid/variance in Firestore alongside raw embeddings, and update FAISS index. Keep storage small: store centroid (float32 array) + variance (float32 array) + sample_count.

3) "Adaptive thresholding using per-user stats"
Files: [attendance_backend/services/face_recognition_service.py](attendance_backend/services/face_recognition_service.py), [attendance_backend/services/scoped_embedding_search.py](attendance_backend/services/scoped_embedding_search.py)
Inputs: query embedding (128-dim), user centroid + variance, base threshold (env var).
Task: Implement a lightweight function that computes an adaptive threshold per user: e.g., threshold_user = base_threshold - k*std_distance where std_distance derived from variance. Use this to accept SELF_VERIFY matches immediately when similarity > threshold_user.

4) "Fuse liveness score + embedding similarity + login metadata"
Files: [attendance_backend/services/face_recognition_service.py](attendance_backend/services/face_recognition_service.py), [attendance_backend/services/liveness.py](attendance_backend/services/liveness.py) (new), [attendance_backend/services/face_attempt_service.py](attendance_backend/services/face_attempt_service.py)
Inputs: embedding similarity (0–1), liveness score (0–1), metadata vector (risk_score from device/IP/time: 0–1).
Task: Add a fused confidence function: fused = w1*sim + w2*liveness + w3*(1 - risk_score). Expose weights via env/config and require fused >= require_confidence to accept. Create `liveness.py` placeholder that returns a simple heuristic (blink detection or texture) if hardware liveness model missing.

5) "Single-frame quick-accept policy for SELF_VERIFY"
Files: [attendance_backend/services/optimized_attendance_pipeline.py](attendance_backend/services/optimized_attendance_pipeline.py), [attendance_backend/services/scoped_embedding_search.py](attendance_backend/services/scoped_embedding_search.py)
Inputs: SELF_VERIFY anchored scope, current frame embedding, centrifuge threshold.
Task: Implement a fast path: when session is anchored to `user_id` and the per-user adaptive threshold is exceeded and liveness passes, accept immediately (mark attendance) without waiting for multi-frame temporal verifier. Add config switch `QUICK_ACCEPT_SELF_VERIFY`.

6) "Aggressive multi-frame aggregation fallback"
Files: [attendance_backend/services/optimized_attendance_pipeline.py](attendance_backend/services/optimized_attendance_pipeline.py), [attendance_backend/services/sorting_tracker.py](attendance_backend/services/sorting_tracker.py#L1)
Inputs: 2–5 consecutive embeddings from same track, voting/average scheme.
Task: Implement small aggregation: compute mean embedding across up to N recent frames, normalize and search once. If mean confidence exceeds threshold, accept. Keep N small (3) to limit latency.

7) "Motion-aware capture guidance: capture only steady frontal faces"
Files: [attendance_backend/services/face_detection_service.py](attendance_backend/services/face_detection_service.py), [attendance_backend/services/optimized_attendance_pipeline.py](attendance_backend/services/optimized_attendance_pipeline.py), [attendance_backend/utils/preprocessing.py](attendance_backend/utils/preprocessing.py#L1)
Inputs: detection bbox, face pose/yaw estimate (simple heuristic), motion vector from MotionDetector.
Task: Add logic to estimate face pose (via bbox aspect ratio or small pose estimator). If face is frontal and motion low, mark as high-quality capture. Prefer these frames for enrollment and QUICK_ACCEPT. Keep compute cheap.

8) "Expose diagnostic endpoint for per-session anchored status + embedding stats"
Files: [attendance_backend/api/attendance.py](attendance_backend/api/attendance.py#L1), [attendance_backend/services/embedding_scope_service.py](attendance_backend/services/embedding_scope_service.py)
Inputs: `session_id` (string), auth admin or owner
Task: Implement `GET /api/v1/attendance/session/{session_id}` returning anchored `user_id` (if any), last matched similarity, last fused score, and per-user centroid/sample_count. Useful for tuning thresholds in the field.

9) "Fail-safe: escalate to secondary factor after N quick failures"
Files: [attendance_backend/services/face_attempt_service.py](attendance_backend/services/face_attempt_service.py), [attendance_backend/api/auth.py](attendance_backend/api/auth.py#L1)
Inputs: `student_id`, `period_id`, current attempt_count
Task: If a session fails to QUICK_ACCEPT 2 times (or face_attempt_service count >= 2), require a secondary factor (e.g., OTP or teacher approval). Implement server-side flagging and an event in Firestore `face_verification_escalations`.

10) "Lightweight liveness fallback and test harness"
Files: [attendance_backend/services/liveness.py] (new), [attendance_backend/tests/test_liveness_placeholder.py] (new test)
Inputs: face ROI image, a short video of 1–2s for blink heuristic (optional)
Task: Provide a tiny liveness placeholder function: simple texture+motion heuristic that returns a confidence 0–1. Add a unit test that loads a sample still and simulates blink frames; keep dependencies minimal (OpenCV + numpy). Document env flags to disable strict liveness in constrained devices.

Usage notes for the Claude prompts
- Always prefer minimal changes: add small helper functions, config flags, and DB fields before refactors. Use existing services and singletons (e.g., `init_scope_service`) rather than adding heavy new infra.
- Inputs to each prompt: example payload JSON, relevant env variables (e.g., FACE_RECOGNITION_THRESHOLD, QUICK_ACCEPT_SELF_VERIFY=true), and a small sample of enrollment images (or base64 placeholder).
- Goal: enable a pipeline that for a logged-in user reaches high-confidence accept in 1–2 attempts by combining SELF_VERIFY scoping + per-user adaptive threshold + liveness + motion-aware capture.

End of prompts.