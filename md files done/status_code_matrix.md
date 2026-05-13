# Student API — Auth Guard Status-Code Matrix

## Auth & Role Scenarios

| Scenario | Before patch | After patch | Notes |
|---|---|---|---|
| `X-Student-Token` header absent | **401** | **401** | Unchanged — correct |
| Token present, `auth_tokens/{token}` node **missing** (NotFoundError) | **500** 💥 | **403** ✅ | P-1: NotFoundError is now caught explicitly |
| Token present, RTDB unreachable / permission denied | **500** 💥 | **403** ✅ | P-1: all RTDB errors during token validation → 403 |
| Token found, `role ≠ "student"` | **403** | **403** | Unchanged — correct |
| Token found, `revoked = true` | **403** | **403** | Unchanged — correct |
| Valid token, `student_id` in query **≠** authenticated student | **403** | **403** | Unchanged — correct |
| Valid token, own `student_id`, user profile **exists** | **200** | **200** | Unchanged |
| Valid token, own `student_id`, `/users/{id}` node **missing** | **500** 💥 | **200** ✅ | P-2 / P-3: missing profile → empty dict, not an exception |
| Valid token, dev bypass (`dev_student_{id}`), profile missing | **200** (silent fail) | **200** ✅ | P-2: same helper, warning logged |
| `realtime/token` — valid student, **no class_id** anywhere | **500** 💥 | **422** ✅ | P-3: only raises after both token doc and profile lookup come back empty |
| `realtime/token` — Firebase `set()` fails | **500** | **500** | Correct — this is a genuine infrastructure failure |

---

## Endpoint Errors (service layer)

| Scenario | Before patch | After patch | Notes |
|---|---|---|---|
| `get_today_attendance` — RTDB read fails | **200** `{"status":"error","message":"..."}` 💥 | **500** ✅ | P-4: error body on a 200 was masking failures from clients |
| `get_today_attendance` — attendance node missing (NotFoundError) | **200** `{"status":"error"}` 💥 | **200** `{"status":"not_marked"}` ✅ | P-4: genuinely absent node is "not marked", not an error |
| `get_attendance_history` — service throws | **500** | **500** | Unchanged; error is now also logged |
| `get_dashboard` / `get_timetable` / `get_attendance_summary` / `get_warnings` — service throws | **500** | **500** | Unchanged; errors now logged with `student_id` |

---

## Log Format (P-5)

All warning/error log lines follow a structured key=value format for easy parsing by log aggregators (Datadog, Cloud Logging, etc.):

```
# Auth guard warnings (logger.warning)
users/{id} | reason=profile_not_found_in_rtdb
users/{id} | reason=rtdb_lookup_failed | exc=<exception>
users/{id} | reason=unexpected_profile_type | type=<type>
token={12-char prefix}… | reason=auth_tokens_node_not_found
token={12-char prefix}… | reason=rtdb_token_lookup_failed | exc=<exception>
token={12-char prefix}… | reason=invalid_role_or_revoked | role=<role> | revoked=<bool>

# Service layer errors (logger.error)
get_today_attendance | student_id={id} | exc=<exception>
get_attendance_history | student_id={id} | exc=<exception>
get_dashboard | student_id={id} | exc=<exception>
get_timetable | student_id={id} | exc=<exception>
get_attendance_summary | student_id={id} | exc=<exception>
get_warnings | student_id={id} | exc=<exception>
get_realtime_token | student_id={id} | reason=token_persist_failed | exc=<exception>
```

---

## student_secured.py — Alignment Note (P-6)

`student_secured.py` delegates auth to `decorators/auth_decorators.py`.  
The original 500 risk is the same: if `require_own_student_data` does an RTDB
profile lookup to resolve the student's identity, it must also protect that
lookup with `try/except NotFoundError`.

**Recommended fix** — the decorator should use the token's embedded `uid` as
the ground truth for the student's identity and **not** do a secondary RTDB
profile lookup at all.  The `student_id` is already available in `auth_user.uid`
from the validated token doc.  This eliminates the failure surface entirely.

```python
# decorators/auth_decorators.py  (simplified reference)
def require_own_student_data(param_name: str):
    async def _dep(
        request: Request,
        auth_user: UserContext = Depends(require_student),
    ):
        if auth_user.role == "student":
            queried_id = request.query_params.get(param_name)
            if auth_user.uid != queried_id:          # no RTDB call needed
                raise HTTPException(403, "You may only query your own data.")
        # teachers / admins pass through without check
    return Depends(_dep)
```
