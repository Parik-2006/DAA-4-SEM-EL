# Face Confirmation Learning Architecture

## Goal

When the system detects a face and the user clicks "Yes, this is me", that confirmation should become a safe learning signal. The next time the same user appears, recognition should use the confirmed evidence to improve speed and accuracy.

The key rule: do not directly retrain the neural model from every click. Use confirmed detections to update the user's embedding profile, confidence statistics, device/session trust, and thresholds through a gated learning pipeline.

## Current System Fit

The existing backend already has the right base pieces:

- `attendance_backend/api/attendance.py`
  - `POST /api/v1/attendance/anchor` creates a session anchor.
  - `POST /api/v1/attendance/detect-face-only` detects and identifies without writing attendance.
  - `verified_face_outcomes` is already queued after confirmed attendance.
- `attendance_backend/services/session_anchor_service.py`
  - Pins `session_id -> user_id` so later detection can use SELF_VERIFY first.
- `attendance_backend/services/scoped_embedding_search.py`
  - Supports SELF, SELF_VERIFY, section roster search, quick accept, adaptive thresholds, and similarity history.
- `attendance_backend/services/face_recognition_service.py`
  - Extracts FaceNet embeddings.
  - Supports multi-photo enrollment, centroid, variance, adaptive threshold, liveness, and fused confidence.
- `attendance_backend/services/optimized_attendance_pipeline.py`
  - Has quality scoring, tracking, temporal verification, liveness fusion, quick accept, and multi-frame aggregation.

So the new feature should be an extension: a "confirmed learning layer" on top of the current embedding/search stack.

## High-Level Flow

```text
Camera frame / uploaded image
  -> face detection
  -> face crop quality scoring
  -> FaceNet embedding extraction
  -> scoped recognition
  -> UI shows predicted identity
  -> user clicks "Yes, this is me"
  -> backend stores confirmed learning event
  -> learning worker validates quality and safety gates
  -> user profile prototype is updated
  -> FAISS/search cache is refreshed
  -> next detection uses updated prototype, thresholds, history, and session anchor
```

## Proposed Components

### 1. Confirmation API

Add a new endpoint:

```http
POST /api/v1/attendance/face-confirmation
```

Request:

```json
{
  "session_id": "tab_abc123",
  "period_id": "period_001",
  "predicted_student_id": "1RV23CS001",
  "confirmed_student_id": "1RV23CS001",
  "detection_id": "det_20260518_001",
  "yes_this_is_me": true,
  "client_timestamp": "2026-05-18T10:25:00+05:30"
}
```

Backend responsibilities:

- Authenticate the caller.
- If caller is a student, `confirmed_student_id` must equal authenticated `user_id`.
- If caller is teacher/admin, allow confirmation only for their assigned section/class.
- Fetch the pending detection snapshot by `detection_id`.
- Ensure the predicted identity and confirmed identity are compatible.
- Store an immutable confirmation event.
- Queue a learning job.
- Refresh or create a session anchor for fast SELF_VERIFY.

Response:

```json
{
  "accepted": true,
  "learning_status": "queued",
  "anchor_refreshed": true,
  "message": "Face confirmation saved."
}
```

### 2. Pending Detection Store

`detect-face-only` should return a `detection_id` and save a short-lived snapshot. This lets confirmation use the exact embedding that produced the prediction, not a new image.

Collection: `pending_face_detections/{detection_id}`

```json
{
  "detection_id": "det_20260518_001",
  "session_id": "tab_abc123",
  "predicted_student_id": "1RV23CS001",
  "candidate_scores": [
    {"student_id": "1RV23CS001", "similarity": 0.83},
    {"student_id": "1RV23CS014", "similarity": 0.61}
  ],
  "embedding": [0.012, -0.033],
  "embedding_model": "facenet_vggface2",
  "bbox": [120, 80, 310, 300],
  "quality": {
    "tier": "HIGH",
    "score": 0.86,
    "frontality": 0.91,
    "sharpness": 0.82
  },
  "liveness": {
    "is_live": true,
    "score": 0.74,
    "method": "blink_texture"
  },
  "confidence": 0.83,
  "fused_confidence": 0.79,
  "period_id": "period_001",
  "created_at": "2026-05-18T10:25:00+05:30",
  "expires_at": "2026-05-18T10:35:00+05:30",
  "used_for_learning": false
}
```

Retention: 10 to 30 minutes. Delete or redact raw images unless debugging is explicitly enabled.

### 3. Confirmation Event Store

Collection: `face_confirmation_events/{event_id}`

```json
{
  "event_id": "fce_20260518_001",
  "detection_id": "det_20260518_001",
  "session_id": "tab_abc123",
  "confirmed_student_id": "1RV23CS001",
  "predicted_student_id": "1RV23CS001",
  "confirmed_by": "1RV23CS001",
  "confirmed_by_role": "student",
  "decision": "positive",
  "quality_tier": "HIGH",
  "similarity": 0.83,
  "fused_confidence": 0.79,
  "liveness_score": 0.74,
  "learning_action": "queued",
  "created_at": "2026-05-18T10:25:03+05:30"
}
```

This collection is audit-grade. It should not be overwritten.

### 4. User Face Memory Store

Collection: `face_profiles/{student_id}`

```json
{
  "student_id": "1RV23CS001",
  "model_version": "facenet_vggface2",
  "centroid": [0.021, -0.014],
  "variance": 0.018,
  "sample_count": 9,
  "trusted_sample_count": 4,
  "last_positive_similarity": 0.83,
  "rolling_similarity_mean": 0.81,
  "rolling_similarity_std": 0.04,
  "adaptive_threshold": 0.70,
  "last_updated_at": "2026-05-18T10:25:07+05:30",
  "status": "active"
}
```

Collection: `face_profile_samples/{student_id}/samples/{sample_id}`

```json
{
  "sample_id": "fps_20260518_001",
  "source": "yes_this_is_me",
  "embedding": [0.012, -0.033],
  "quality_score": 0.86,
  "quality_tier": "HIGH",
  "liveness_score": 0.74,
  "similarity_to_old_centroid": 0.83,
  "accepted_for_profile": true,
  "created_at": "2026-05-18T10:25:03+05:30"
}
```

Keep only the best recent trusted samples per user, for example 20 to 50. This prevents profile drift and keeps search fast.

## Learning Algorithm

### Positive Confirmation

When `yes_this_is_me = true`, the sample may update the profile only if all gates pass:

- Auth gate: the confirmer is allowed to confirm that identity.
- Detection gate: `detection_id` exists and is not expired.
- Identity gate: predicted and confirmed identity match, or teacher/admin explicitly corrected it.
- Quality gate: quality tier is `HIGH` or `ACCEPTABLE`.
- Liveness gate: liveness score passes the configured floor.
- Similarity gate: embedding is close enough to the existing centroid.
- Anti-drift gate: embedding is not a statistical outlier.

Suggested initial gates:

```text
quality_score >= 0.70
liveness_score >= 0.55
similarity_to_existing_centroid >= max(0.62, adaptive_threshold - 0.08)
fused_confidence >= 0.68
```

If the user has no strong profile yet, require stricter conditions:

```text
quality_score >= 0.80
liveness_score >= 0.65
teacher/admin approval OR at least 3 positive samples across different moments
```

### Prototype Update

Use embedding memory, not neural model retraining.

For each confirmed sample:

1. Normalize the embedding.
2. Compare it to the current centroid.
3. If accepted, append it to trusted samples.
4. Recompute centroid from trusted samples.
5. Recompute variance.
6. Update adaptive threshold.
7. Refresh FAISS/search cache for that student.

Centroid formula:

```text
centroid = normalize(mean(trusted_embeddings))
variance = mean(cosine_distance(embedding_i, centroid)^2)
adaptive_threshold = clamp(mean_similarity - 1.0 * std_similarity, 0.62, 0.88)
```

For production, prefer full recompute from stored trusted samples over incremental math. It is simpler, safer, and the sample count is small.

### Negative Confirmation

If user clicks "No, this is not me", do not update the face profile. Store it as a hard negative.

Collection: `face_negative_events/{event_id}`

Use this for:

- lowering trust in the current session anchor,
- increasing attempt pressure,
- identifying confusing pairs of students,
- building an evaluation set,
- flagging students whose enrolled images need recapture.

If the same wrong pair appears repeatedly, mark the pair as "confusable" and require stronger thresholds or teacher review.

## Search-Time Usage

Every future detection should use the learned data in this order:

1. Active session anchor
   - If `session_id` has an anchor, run SELF_VERIFY against only that user's profile.
   - This is fastest and reduces false matches.

2. Updated face profile
   - Search against the latest centroid/trusted samples.
   - Use adaptive threshold from `face_profiles/{student_id}`.

3. Similarity history
   - Use recent positive confirmations to tune the threshold.

4. Section roster fallback
   - If SELF_VERIFY fails and `force_scope=false`, search section roster.

5. Global search
   - Avoid by default for attendance. It has higher false-positive risk.

## Accuracy Strategy

### Keep the Model Stable

Use FaceNet/InceptionResnetV1 as a fixed embedding extractor. Do not fine-tune it from individual student clicks. Fine-tuning on tiny personal data can overfit and create unpredictable regressions.

Improve accuracy through:

- better enrollment samples,
- high-quality confirmed samples,
- centroid/prototype updates,
- adaptive per-user thresholds,
- liveness and fused confidence,
- multi-frame aggregation,
- section/session scoping.

### Multi-Sample Profiles

Each student should have:

- 5 to 10 initial enrollment photos,
- 5 to 20 trusted confirmation samples over time,
- samples from different days, lighting, expression, glasses/no glasses if applicable.

Avoid storing many near-duplicate frames from the same second. They add size without improving the profile.

### Quality-Aware Learning

Only learn from strong samples:

- face is frontal enough,
- sharp image,
- not too dark,
- not too small,
- one clear face in crop,
- liveness passed,
- confidence is not borderline.

Borderline confirmations can be stored for audit but should not change the profile automatically.

### Confusable Pair Handling

Maintain `face_confusion_pairs/{student_a}_{student_b}` when two students repeatedly appear as top candidates.

```json
{
  "student_a": "1RV23CS001",
  "student_b": "1RV23CS014",
  "count": 4,
  "last_seen": "2026-05-18T10:25:00+05:30",
  "action": "raise_threshold"
}
```

When a pair is confusable:

- require higher similarity margin,
- disable quick accept for that pair,
- prefer teacher confirmation,
- request re-enrollment if needed.

Suggested margin:

```text
best_score - second_best_score >= 0.08
```

## Services To Add

### `FaceConfirmationService`

Responsibilities:

- validate confirmation request,
- fetch pending detection,
- write confirmation event,
- decide whether to queue learning,
- refresh session anchor.

Suggested file:

```text
attendance_backend/services/face_confirmation_service.py
```

### `FaceProfileLearningService`

Responsibilities:

- validate sample quality,
- run anti-drift checks,
- append trusted profile sample,
- recompute centroid/variance/threshold,
- update `face_profiles`,
- refresh search index/cache.

Suggested file:

```text
attendance_backend/services/face_profile_learning_service.py
```

### `FaceProfileRepository`

Responsibilities:

- read/write `face_profiles`,
- read/write profile samples,
- cap sample count,
- expose profile stats for diagnostics.

Suggested file:

```text
attendance_backend/database/face_profile_repository.py
```

## API Changes

### Update `detect-face-only`

Add to response:

```json
{
  "matched": true,
  "student_id": "1RV23CS001",
  "confidence": 0.83,
  "fused_confidence": 0.79,
  "detection_id": "det_20260518_001",
  "can_confirm": true,
  "learning_eligible": true
}
```

### Add `face-confirmation`

Endpoint:

```http
POST /api/v1/attendance/face-confirmation
```

### Add Diagnostics

Endpoint:

```http
GET /api/v1/attendance/face-profile/{student_id}/diagnostics
```

Response:

```json
{
  "student_id": "1RV23CS001",
  "sample_count": 12,
  "trusted_sample_count": 8,
  "variance": 0.018,
  "adaptive_threshold": 0.70,
  "last_updated_at": "2026-05-18T10:25:07+05:30",
  "needs_reenrollment": false
}
```

## Security And Privacy

- Students can confirm only themselves.
- Teachers/admins can confirm only students in their assigned scope.
- Confirmation events are immutable.
- Never learn from expired or reused `detection_id`.
- Do not store raw face crops long-term by default.
- Store embeddings as sensitive biometric data.
- Encrypt at rest where possible.
- Add deletion support for a student's biometric profile.
- Log every profile update with old/new stats, not raw images.

## Failure Modes

| Problem | Protection |
| --- | --- |
| User clicks yes on wrong identity | Auth gate, identity gate, similarity gate |
| Bad lighting corrupts profile | Quality gate, liveness gate, anti-drift gate |
| One strange frame shifts centroid | Store samples and recompute with outlier removal |
| Lookalike students confuse model | Confusable pair tracking and higher margin |
| Spoofed image gets confirmed | Liveness floor and fused confidence |
| System becomes too permissive | Threshold floors and audit metrics |
| Too many samples slow search | Cap trusted samples and search centroids first |

## Rollout Plan

### Phase 1: Safe Confirmation Logging

- Add `detection_id` to `detect-face-only`.
- Store `pending_face_detections`.
- Add `face-confirmation` endpoint.
- Store confirmation events.
- Refresh session anchor after positive confirmation.
- Do not update profile yet.

### Phase 2: Offline Learning

- Build `FaceProfileLearningService`.
- Process confirmed events manually or with a scheduled worker.
- Update `face_profiles`.
- Add diagnostics endpoint.
- Compare pre-learning and post-learning accuracy on test data.

### Phase 3: Online Gated Learning

- Auto-update profiles only when all quality gates pass.
- Keep borderline events in review queue.
- Add confusable pair tracking.
- Refresh FAISS/search index after profile updates.

### Phase 4: Accuracy Dashboard

Track:

- true positive confirmation rate,
- false confirmation reports,
- average similarity per user,
- per-user variance,
- rejected learning samples,
- confusable pairs,
- quick accept success rate,
- manual override rate.

## Evaluation Plan

Before enabling automatic learning, create a small validation set:

- at least 20 students,
- 5 to 10 enrollment photos each,
- 10 to 20 detection samples each,
- different lighting and face angles,
- a few negative/lookalike cases.

Metrics:

- TAR/TPR at target FAR,
- false accept rate,
- false reject rate,
- top-1 accuracy,
- average confidence margin,
- latency with and without session anchor,
- number of attempts before success.

Suggested acceptance targets for attendance:

```text
Top-1 accuracy >= 97% in section-scoped search
False accept rate <= 0.5%
False reject rate <= 3%
SELF_VERIFY median latency <= 300 ms on backend hardware
No automatic profile update from LOW-quality samples
```

## Implementation Notes

- Use the existing FaceNet extractor as the embedding model.
- Use the existing scoped search path for SELF_VERIFY.
- Use `session_anchor_service` after positive confirmation to make the next detection fast.
- Use `verified_face_outcomes` as a related audit signal, but keep `face_confirmation_events` separate because it is specifically user feedback.
- Recompute centroids from stored trusted embeddings instead of updating model weights.
- Keep global thresholds conservative; per-user thresholds should never drop below a safe floor.

## Recommended First Code Tasks

1. Add `detection_id` creation and `pending_face_detections` persistence inside `detect-face-only`.
2. Add `FaceConfirmationService`.
3. Add `POST /api/v1/attendance/face-confirmation`.
4. Add `FaceProfileRepository`.
5. Add offline `FaceProfileLearningService.apply_positive_confirmation(event_id)`.
6. Add tests for:
   - student cannot confirm another student,
   - expired detection is rejected,
   - low-quality sample is logged but not learned,
   - accepted sample updates centroid and threshold,
   - session anchor is refreshed after confirmation.

