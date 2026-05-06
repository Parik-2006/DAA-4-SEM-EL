# Security Layer — Smart Attendance System

## Architecture Overview

```
HTTP request
     │
     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  CORSMiddleware                                                             │
│  (outermost — handles preflight, injects CORS headers)                     │
└───────────────────────────────┬────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  RateLimitMiddleware                                          utils/        │
│  • student  → 100 req/min                                    rate_limiter  │
│  • teacher  → 500 req/min                                                  │
│  • admin    → unlimited                                                    │
│  • anon     →  20 req/min                                                  │
│  Returns HTTP 429 + Retry-After header on breach                           │
└───────────────────────────────┬────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  AuditMiddleware                                          middleware/       │
│  • Intercepts POST/PUT/PATCH/DELETE                       audit_middleware │
│  • Reads + buffers request body (re-injected for handler)                  │
│  • Writes to AuditService after response                                   │
│  • Sanitises sensitive fields (passwords, face_image_base64, tokens)       │
│  • Never crashes the request — degrades gracefully                         │
└───────────────────────────────┬────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  PermissionMiddleware                                     middleware/       │
│  • Matches URL prefix → required role set                 permission_      │
│  • /api/v1/admin/*   → admin only                        middleware       │
│  • /api/v1/teacher/* → teacher | admin                                    │
│  • /api/v1/student/* → student | teacher | admin                          │
│  • Injects QueryFilterContext into request.state.query_filter              │
│    (section_ids, student_id filters for Firestore queries)                 │
└───────────────────────────────┬────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  AuthMiddleware                                           middleware/       │
│  (innermost — runs first on request, last on response)    auth_middleware  │
│  • Extracts Bearer token from Authorization header                         │
│  • Decodes + validates JWT via AuthService                                 │
│  • Attaches UserContext to request.state.user                              │
│  • Returns HTTP 401 for missing/invalid/expired tokens                     │
│  • Public paths bypass auth entirely                                       │
└───────────────────────────────┬────────────────────────────────────────────┘
                                │
                                ▼
                     FastAPI Route Handler
                     (endpoint-level deps)
```

---

## New Files

| File | Purpose |
|------|---------|
| `services/auth_service.py` | JWT issuance and validation, password hashing, user authentication |
| `services/audit_service.py` | Writes immutable audit records to Firestore `audit_logs` collection |
| `middleware/auth_middleware.py` | JWT extraction → `request.state.user` |
| `middleware/permission_middleware.py` | URL-prefix role enforcement + `QueryFilterContext` injection |
| `middleware/audit_middleware.py` | Auto-audit all mutating requests |
| `decorators/auth_decorators.py` | FastAPI dependency factories for fine-grained authz |
| `utils/rate_limiter.py` | Sliding-window rate limiter (middleware + dependency) |
| `api/auth.py` | `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `GET /api/v1/auth/me` |
| `api/audit.py` | Admin-only audit log query endpoints |

---

## Modified Files

| File | Changes |
|------|---------|
| `main.py` | Middleware stack wired in correct order; auth + audit routers registered |
| `api/admin.py` | `require_admin` dep on every endpoint; audit logging on writes |
| `api/teacher.py` | `require_teacher` + `require_faculty_access` on every endpoint; section auth in `mark-bulk` |
| `api/student.py` | `require_student` + `require_own_student_data` on every endpoint |
| `api/attendance.py` | Per-endpoint role deps; section check in `mark-attendance`; self-check in `mark-mobile` |

---

## JWT Token

### Issue

```
POST /api/v1/auth/login
Content-Type: application/json

{ "email": "teacher@college.edu", "password": "secret" }
```

Response:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 28800,
  "user_id": "abc123",
  "role": "teacher",
  "permissions": ["mark_attendance", "list_assigned_students", ...],
  "assigned_sections": ["CS-A", "CS-B"]
}
```

### Use

```
GET /api/v1/teacher/dashboard?faculty_id=abc123
Authorization: Bearer eyJ...
```

### Refresh

```
POST /api/v1/auth/refresh
Authorization: Bearer eyJ...
```

---

## Role Permissions

| Permission | admin | teacher | student |
|-----------|-------|---------|---------|
| `list_all_students` | ✅ | ❌ | ❌ |
| `list_all_attendance` | ✅ | ❌ | ❌ |
| `manage_users` | ✅ | ❌ | ❌ |
| `manage_sections` | ✅ | ❌ | ❌ |
| `view_analytics` | ✅ | ❌ | ❌ |
| `upload_timetable` | ✅ | ❌ | ❌ |
| `view_audit_logs` | ✅ | ❌ | ❌ |
| `list_assigned_students` | ✅ | ✅ | ❌ |
| `list_assigned_attendance` | ✅ | ✅ | ❌ |
| `mark_attendance` | ✅ | ✅ | ❌ |
| `view_section_analytics` | ✅ | ✅ | ❌ |
| `view_own_attendance` | ✅ | ✅ | ✅ |
| `view_own_analytics` | ✅ | ✅ | ✅ |

---

## Decorator Reference

```python
from decorators.auth_decorators import (
    get_current_user,          # any authenticated user
    require_admin,             # admin only
    require_teacher,           # teacher or admin
    require_student,           # student only
    require_role,              # custom: require_role("teacher","admin")
    require_permission,        # require_permission("mark_attendance")
    require_section_access,    # teacher owns the section
    require_own_student_data,  # student sees only own records
    require_faculty_access,    # teacher acts only as themselves
    get_section_filter,        # helper: returns section list or None
)
```

### Usage patterns

```python
# 1. Any authenticated user
@router.get("/me")
async def profile(user: UserContext = Depends(get_current_user)):
    return {"user_id": user.user_id}

# 2. Admin only — dependency shorthand
@router.get("/admin/users")
async def list_users(admin: UserContext = require_admin):
    ...

# 3. Teacher marking attendance (also validates section ownership)
@router.post("/attendance/mark")
async def mark(
    section_id: str = Query(...),
    auth_user: UserContext = require_teacher,
    _: None = require_section_access("section_id"),
):
    ...

# 4. Student reads own data only
@router.get("/student/attendance")
async def my_attendance(
    student_id: str = Query(...),
    auth_user: UserContext = require_student,
    _: None = require_own_student_data("student_id"),
):
    ...
```

---

## QueryFilterContext

Injected into `request.state.query_filter` by `PermissionMiddleware` before
the handler runs.  Use it to scope Firestore queries automatically:

```python
@router.get("/sections")
async def list_sections(request: Request, auth_user: UserContext = Depends(get_current_user)):
    ctx = request.state.query_filter        # QueryFilterContext

    query = db.collection("periods")
    section_filter = ctx.to_firestore_section_filter()
    if section_filter is not None:          # None = admin, no filter needed
        query = query.where("section_id", "in", section_filter)

    return [d.to_dict() for d in query.stream()]
```

---

## Audit Log

Every state-changing API call is automatically logged to the Firestore
`audit_logs` collection by `AuditMiddleware`.  Write endpoints can also call
`get_audit_service().log(...)` explicitly for richer context.

### Schema

```json
{
  "log_id":      "uuid",
  "user_id":     "abc123",
  "user_role":   "teacher",
  "action":      "MARK_ATTENDANCE",
  "resource":    "attendance",
  "resource_id": "2025-01-15_period-1_student-42",
  "before":      null,
  "after":       { "status": "present", ... },
  "ip_address":  "203.0.113.5",
  "user_agent":  "Mozilla/5.0 ...",
  "timestamp":   "2025-01-15T09:05:23.412Z",
  "details":     { "method": "face_recognition", "confidence": 0.97 },
  "success":     true,
  "error":       null
}
```

### Querying (admin only)

```
GET /api/v1/audit/logs?action=MARK_ATTENDANCE&date_from=2025-01-01&page=1&limit=50
GET /api/v1/audit/logs/{log_id}
GET /api/v1/audit/attendance/{record_id}   # full trail for one attendance record
GET /api/v1/audit/user/{user_id}           # all actions by one user
```

---

## Rate Limits

| Role | Limit | Window |
|------|-------|--------|
| `admin` | unlimited | — |
| `teacher` | 500 req | 60 s |
| `student` | 100 req | 60 s |
| anonymous | 20 req | 60 s |

On breach: `HTTP 429` with headers:
```
Retry-After: 47
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1737000570
```

---

## API Versioning

All routes are prefixed `/api/v1/...`.  To add v2 without breaking v1:

```python
# main.py
from api.v2 import router as v2_router
app.include_router(v2_router)   # registers /api/v2/...

# v1 routers remain untouched — full backward compatibility
```

---

## Environment Variables

```bash
# .env
JWT_SECRET=your-random-256-bit-secret-here   # REQUIRED in production
JWT_EXPIRY_SECONDS=28800                      # optional, default 8 hours
```

Generate a secret:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Firestore Index Requirements

The `audit_logs` collection requires these composite indexes:

```
Collection: audit_logs
  user_id   ASC, timestamp DESC
  action    ASC, timestamp DESC
  resource  ASC, timestamp DESC
  resource_id ASC, timestamp ASC
  success   ASC, timestamp DESC
```

Create them via the Firebase Console → Firestore → Indexes → Composite,
or add to `firestore.indexes.json`:

```json
{
  "indexes": [
    {
      "collectionGroup": "audit_logs",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "user_id",   "order": "ASCENDING" },
        { "fieldPath": "timestamp", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "audit_logs",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "resource_id", "order": "ASCENDING" },
        { "fieldPath": "timestamp",   "order": "ASCENDING" }
      ]
    }
  ]
}
```

---

## Migration Checklist

- [ ] Set `JWT_SECRET` in `.env` (random 256-bit hex)
- [ ] Add user documents to Firestore `users` collection with `role`, `email`, `password_hash`, `assigned_sections`
- [ ] Run `bash install_security_layer.sh` from the project root
- [ ] Create Firestore composite indexes for `audit_logs`
- [ ] Update frontend: store JWT from `/api/v1/auth/login`, send as `Authorization: Bearer <token>`
- [ ] Restart uvicorn
- [ ] Verify `/api/v1/health` returns 200 (no auth needed)
- [ ] Verify unauthenticated request to `/api/v1/admin/students` returns 401
- [ ] Verify teacher token cannot access `/api/v1/admin/students` (403)
- [ ] Verify student token cannot mark attendance for another student (403)
- [ ] Check `audit_logs` collection in Firestore for entries
