# QUICK REFERENCE — INTEGRATED TEST UTILITIES

## New Utility Modules

### 1. Token Utilities (`utils/token_utils.py`)

```python
from utils.token_utils import (
    create_admin_token,        # Create admin JWT
    create_teacher_token,      # Create teacher JWT
    create_student_token,      # Create student JWT
    validate_token,            # Validate JWT token
    TokenGenerationError,      # Exception for token generation
    TokenValidationError       # Exception for token validation
)

# Create tokens
admin = create_admin_token(user_id="admin1")
teacher = create_teacher_token(user_id="prof1", assigned_sections=["CS101"])
student = create_student_token(user_id="student_001")

# Validate token
claims = validate_token(admin)  # Returns: {user_id, email, role, permissions, ...}
```

---

### 2. Seed Utilities (`utils/seed_utils.py`)

```python
from utils.seed_utils import (
    seed_test_section,              # Create section
    seed_test_teacher,              # Create teacher
    seed_test_students,             # Create students
    seed_test_timetable,            # Create timetable
    seed_complete_test_environment, # Seed everything
    SeedError                       # Exception for seeding
)

# Seed individual components
success, error = seed_test_section(db, "CS101")
success, error = seed_test_teacher(db, "prof1", "CS101")
success, error = seed_test_students(db, ["s001", "s002"], "CS101")
success, error = seed_test_timetable(db, "CS101")

# Or seed complete environment
success, results = seed_complete_test_environment(
    db,
    section_id="CS101",
    teacher_id="prof1",
    student_ids=["s001", "s002", "s003"]
)

# Check results
if success:
    print("✓ All seeded")
else:
    for step, passed, error in results:
        if not passed:
            print(f"✗ {step}: {error}")
```

---

### 3. Validation Utilities (`utils/validation_utils.py`)

```python
from utils.validation_utils import (
    check_health,                    # Check system health
    validate_endpoint,               # Validate API endpoint
    verify_firestore_persistence,    # Check if doc exists
    log_validation_summary,          # Log results
    ValidationError,                 # Exception
    EndpointError                    # Exception
)

# Check health
is_healthy, status = check_health()
# Returns: (True/False, {status: "healthy", services: {...}})

# Validate endpoint
status, data = validate_endpoint(
    method="GET",
    path="/teacher/attendance/history",
    token="eyJ...",
    params={"class_id": "TEST_SECTION"}
)

# Verify document in Firestore
exists, doc = verify_firestore_persistence(
    collection="verified_face_outcomes",
    document_id="record_abc"
)

# Log summary
results = {
    "health_check": True,
    "endpoint_validation": True,
    "persistence_check": True
}
log_validation_summary(results)
```

---

## Enhanced CLI Scripts

### Create Token
```bash
# Default (admin token)
python scripts/create_token.py

# Teacher token
python scripts/create_token.py --role teacher

# Specific teacher with sections
python scripts/create_token.py --role teacher --user prof1 --section CS101

# Student token
python scripts/create_token.py --role student --user student_001

# Help
python scripts/create_token.py --help
```

### Seed Data
```bash
# Default (TEST_SECTION, teacher1, 3 students)
python scripts/seed_via_backend.py

# Custom configuration
python scripts/seed_via_backend.py \
    --section "Data Structures" \
    --teacher "dr_smith" \
    --students 50

# Help
python scripts/seed_via_backend.py --help
```

---

## Exception Classes

All modules provide custom exceptions:

```python
from utils.token_utils import TokenGenerationError, TokenValidationError
from utils.seed_utils import SeedError
from utils.validation_utils import ValidationError, EndpointError

try:
    token = create_admin_token()
except TokenGenerationError as e:
    print(f"Token creation failed: {e}")

try:
    success, results = seed_complete_test_environment(db, "CS101")
except SeedError as e:
    print(f"Seeding failed: {e}")

try:
    is_healthy, status = check_health()
except ValidationError as e:
    print(f"Health check failed: {e}")

try:
    status, data = validate_endpoint(...)
except EndpointError as e:
    print(f"Endpoint error: {e}")
```

---

## Common Usage Patterns

### Pattern 1: Full Test Setup
```python
from utils.token_utils import create_teacher_token
from utils.seed_utils import seed_complete_test_environment
from utils.validation_utils import validate_endpoint
from services.firebase_service import initialize_firebase

# 1. Initialize Firebase
firebase_svc = initialize_firebase("config/firebase-credentials.json")
db = getattr(firebase_svc, "firestore_db", None)

# 2. Seed environment
success, results = seed_complete_test_environment(db, "CS101")
if not success:
    print("Seeding failed")
    exit(1)

# 3. Generate token
token = create_teacher_token(user_id="prof1", assigned_sections=["CS101"])

# 4. Validate endpoint
status, data = validate_endpoint(
    method="GET",
    path="/teacher/attendance/history",
    token=token,
    params={"class_id": "CS101"}
)

print(f"Endpoint returned: {status}")
```

### Pattern 2: Error Handling
```python
from utils.seed_utils import seed_test_section, SeedError

try:
    success, error = seed_test_section(db, "CS101")
    if success:
        print("✓ Section created")
    else:
        print(f"✗ Seeding failed: {error}")
except SeedError as e:
    print(f"✗ Unexpected error: {e}")
```

### Pattern 3: Token Validation
```python
from utils.token_utils import validate_token, TokenValidationError

try:
    claims = validate_token(token)
    print(f"User: {claims['user_id']}, Role: {claims['role']}")
except TokenValidationError as e:
    print(f"✗ Invalid token: {e}")
```

---

## Error Recovery

| Error | Likely Cause | Solution |
|-------|---|---|
| `TokenGenerationError` | AuthService not initialized | Check JWT_SECRET env var |
| `SeedError` | Firestore unavailable | Check credentials file, GCP project |
| `ValidationError` | Backend not running | Start backend with `python -m uvicorn main:app` |
| `EndpointError` | Endpoint returned error | Check logs, verify token, check parameters |

---

## Testing

Run all integration tests:
```bash
python scripts/test_integrations.py
```

This verifies:
- ✅ All token generation functions
- ✅ All seed functions
- ✅ All validation functions
- ✅ All exception classes
- ✅ Import paths

---

## Logging

All operations are logged at appropriate levels:

```python
import logging

logger = logging.getLogger(__name__)

# DEBUG: Detailed flow
logger.debug("Starting operation with params=%s", params)

# INFO: Operation success
logger.info("✓ Verified outcome queued: record_id=%s", record_id)

# WARNING: Recoverable error
logger.warning("Firebase service unavailable; skipping operation")

# ERROR: Failed operation with context
logger.error(
    "Failed operation: user=%s section=%s error=%s",
    user_id,
    section_id,
    exc,
    exc_info=True
)
```

---

## Documentation

- **Full Guide**: [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
- **Summary**: [INTEGRATION_SUMMARY.md](INTEGRATION_SUMMARY.md)
- **Tests**: [scripts/test_integrations.py](scripts/test_integrations.py)

---

## Integration Status

✅ **All utilities integrated**  
✅ **All tests passing**  
✅ **Ready for production**  

Date: May 16, 2026
