# Face Confirmation Learning - Deployment Checklist

**Last Updated**: May 19, 2026  
**Status**: ✅ 95% Complete (1 critical integration pending)

## Pre-Deployment Verification

### ✅ Core Implementation (7 files)
- [x] `utils/face_exceptions.py` - Exception hierarchy
- [x] `schemas/face_confirmation_schemas.py` - Pydantic models
- [x] `database/face_profile_repository.py` - CRUD repository
- [x] `services/face_confirmation_service.py` - Validation service
- [x] `services/face_profile_learning_service.py` - Learning algorithm
- [x] `services/face_detection_storage.py` - Detection storage helper
- [x] `api/face_confirmation.py` - REST endpoints

### ✅ Integration (1 file - partial)
- [x] `main.py` - Router registered
- [ ] `api/attendance.py` - **TODO**: Call store_pending_detection() in detect_face_only()

### ✅ Testing & Docs (3 files)
- [x] `tests/test_face_confirmation.py` - Test suite
- [x] `FACE_CONFIRMATION_IMPLEMENTATION.md` - Full guide
- [x] `FACE_CONFIRMATION_QUICK_REFERENCE.md` - Quick start

### ✅ Code Quality
- [x] All 8 core files syntax-validated (no errors)
- [x] Exception handling comprehensive
- [x] Authorization checks in place
- [x] Firestore collection schema documented

## Critical Integration Task (BLOCKING)

### Update detect_face_only() Endpoint
**File**: `attendance_backend/api/attendance.py`

**Location**: detect_face_only() function (approximately line 894)

**Changes Required**:

1. Add import at top of file:
   ```python
   from services.face_detection_storage import store_pending_detection
   from utils.face_exceptions import FaceRepositoryError
   ```

2. After successful face detection (when `matched=True`), add:
   ```python
   # Store pending detection for learning
   try:
       detection_id, detection_data = store_pending_detection(
           session_id=session_id or "no_session",
           predicted_student_id=result.student_id,
           candidate_scores=[
               {"student_id": cand.student_id, "similarity": cand.similarity}
               for cand in result.candidates[:5]
           ],
           embedding=embedding.tolist(),
           bbox=face_bbox or [0, 0, 0, 0],
           quality_metrics={
               "tier": quality_tier,
               "score": quality_score,
               "frontality": 0.9,
               "sharpness": 0.85,
           },
           liveness_metrics={
               "is_live": is_live,
               "score": liveness_score,
               "method": "passive",
           },
           confidence=result.confidence,
           fused_confidence=result.fused_confidence,
           period_id=period_id,
           retention_minutes=30,
       )
   except FaceRepositoryError as e:
       logger.warning(f"Failed to store pending detection: {e}")
       detection_id = None
   ```

3. Add `detection_id` to response:
   ```python
   return {
       "matched": True,
       "student_id": result.student_id,
       "detection_id": detection_id,  # NEW
       "can_confirm": True,           # NEW
       "learning_eligible": True,     # NEW
       "candidate_scores": [...],
       "confidence": result.confidence,
       "fused_confidence": result.fused_confidence,
       ...
   }
   ```

**Estimated Time**: 15-30 minutes

**Risk Level**: LOW - Wrapper function, non-blocking error handling

**Testing After Update**:
```bash
# Run face confirmation tests
cd attendance_backend
pytest tests/test_face_confirmation.py -v

# Test detect endpoint manually:
# 1. Call detect-face-only with test image
# 2. Verify response includes detection_id
# 3. Call POST /face-confirmation with that detection_id
# 4. Verify confirmation succeeds
```

## Pre-Production Testing Plan

### Unit Tests ✅ Ready
```bash
cd attendance_backend
pytest tests/test_face_confirmation.py -v
```

### Integration Testing (Post-detect_face_only update)
1. **Test Face Detection → Confirmation → Learning Flow**:
   ```bash
   # Terminal 1: Start backend
   python main.py
   
   # Terminal 2: Run integration test
   pytest tests/test_face_confirmation.py::TestFaceConfirmationIntegration -v
   ```

2. **Manual Testing**:
   - Call detect-face-only with test image
   - Verify detection_id in response
   - Submit confirmation with that detection_id
   - Check learning_status in response
   - Query face-profile/diagnostics endpoint
   - Verify sample_count increased

3. **Gate Validation**:
   - Test with high-quality image → should pass
   - Test with low-quality image → should fail quality gate
   - Test with spoofed image → should fail liveness gate
   - Test similarity gate behavior

### Performance Testing
- [ ] Test with 1000 embeddings (query performance)
- [ ] Test with 100 confirmations/sec (write performance)
- [ ] Verify TTL cleanup doesn't impact queries

### Security Testing
- [ ] Student cannot confirm another student
- [ ] Teacher cannot confirm outside their scope
- [ ] Admin can confirm any student
- [ ] Confirmation events are immutable (not deletable)

## Deployment Steps

### Step 1: Code Update
- [ ] Implement detect_face_only() changes
- [ ] Run syntax check: `get_errors()`
- [ ] Test manually: Call detect-face-only
- [ ] Verify detection_id in response

### Step 2: Database Preparation
- [ ] Firestore collections auto-created on first write
- [ ] No manual migration needed
- [ ] TTL cleanup scheduled (every 6 hours)

### Step 3: Endpoint Testing
- [ ] POST /api/v1/attendance/face-confirmation
- [ ] GET /api/v1/attendance/face-profile/{student_id}/diagnostics

### Step 4: Production Rollout
- [ ] Deploy to staging first
- [ ] Run full test suite
- [ ] Monitor error rates (should be ~0%)
- [ ] Deploy to production
- [ ] Monitor Firestore usage
- [ ] Verify learning gates working

## Post-Deployment Monitoring

### Key Metrics to Track
- **Confirmation Rate**: % of detections that get confirmed
- **Learning Success Rate**: % confirmations that pass all gates
- **Profile Quality**: Mean variance across students
- **Gate Failure Breakdown**: Which gates fail most often
- **False Accept/Reject**: Collect user feedback

### Diagnostic Queries

**Check Learning Status**:
```python
from database.face_profile_repository import FaceProfileRepository

repo = FaceProfileRepository()
events = repo.get_confirmation_events("1RV23CS001", limit=50)
learning_applied = sum(1 for e in events if e['learning_action'] == 'learning_applied')
print(f"Learning applied: {learning_applied}/{len(events)}")
```

**Check Profile Quality**:
```python
repo = FaceProfileRepository()
profile = repo.get_profile("1RV23CS001")
print(f"Variance: {profile['variance']:.4f}")
print(f"Samples: {profile['trusted_sample_count']}")
print(f"Threshold: {profile['adaptive_threshold']:.2f}")
```

**Check Confusable Pairs**:
```python
repo = FaceProfileRepository()
for pair_id in repo.db.collection("face_confusion_pairs").stream():
    pair = pair_id.to_dict()
    print(f"{pair['student_a']} <-> {pair['student_b']}: {pair['count']} times")
```

## Rollback Plan

If critical issues occur:

1. **Disable learning** (keep confirmations):
   - Comment out FaceProfileLearningService.apply_positive_confirmation() call
   - Confirmations still recorded (learning_status = "logged_only")

2. **Disable confirmations entirely**:
   - Comment out face_confirmation_router from main.py
   - Revert detect-face-only changes

3. **Reset student profiles**:
   - Delete face_profiles collection (Firestore UI)
   - Profiles recreate from next confirmation

## Success Criteria

- [x] All 7 core modules syntax-validated
- [x] Router registered in main.py
- [x] No import errors
- [x] Exception hierarchy complete
- [x] Authorization enforced
- [ ] detect_face_only() updated (CRITICAL - PENDING)
- [ ] Integration test passes
- [ ] Performance acceptable
- [ ] Security audit passed

## Sign-Off

- **Implementation**: ✅ Complete (May 19, 2026)
- **Testing**: ⏳ Awaiting detect_face_only() integration
- **Documentation**: ✅ Complete
- **Ready for Staging**: ✅ After detect_face_only() update
- **Ready for Production**: ⏳ Awaiting staging validation

---

**Last Updated**: May 19, 2026  
**Next Action**: Update detect_face_only() endpoint in api/attendance.py
