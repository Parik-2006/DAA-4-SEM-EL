"""
Prompt 6 integration verifier.

This script checks that the system integration pieces described in
PROMPT 6 are present and wired together:

- middleware stack in main.py
- role-based routers and API integration
- realtime fan-out and websocket endpoints
- timetable validation and attendance locking
- audit logging and rate limiting

It is intentionally lightweight and does not require running the app.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


ROOT = Path(__file__).resolve().parents[2]


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str = ""


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def file_exists(relative_path: str) -> bool:
    return (ROOT / relative_path).exists()


def ast_functions(relative_path: str) -> List[str]:
    tree = ast.parse(read_text(relative_path))
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]


def ast_classes(relative_path: str) -> List[str]:
    tree = ast.parse(read_text(relative_path))
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


def contains_all(relative_path: str, needles: Iterable[str]) -> bool:
    text = read_text(relative_path)
    return all(needle in text for needle in needles)


def check_prompt6_artifacts() -> List[CheckResult]:
    results: List[CheckResult] = []

    docs = [
        "PROMPT_6_IMPLEMENTATION_PLAN.md",
        "SYSTEM_REDESIGN_PLAN.md",
        "PROMPT_4_IMPLEMENTATION_COMPLETE.md",
        "PROMPT_4_STATUS_FINAL.md",
    ]
    missing_docs = [doc for doc in docs if not file_exists(doc)]
    results.append(
        CheckResult(
            name="Prompt 6 documentation exists",
            passed=not missing_docs,
            details="Missing: " + ", ".join(missing_docs) if missing_docs else "All required docs found",
        )
    )

    main_checks = [
        "from api.sections   import router as sections_router",
        "from api.websocket import router as websocket_router",
        "from middleware.permission_middleware import PermissionMiddleware",
        "from middleware.audit_middleware      import AuditMiddleware",
        "from utils.rate_limiter               import RateLimitMiddleware",
        "app.add_middleware(AuthMiddleware)",
        "app.add_middleware(PermissionMiddleware)",
        "app.add_middleware(AuditMiddleware)",
        "app.add_middleware(RateLimitMiddleware)",
        "app.include_router(sections_router)",
        "app.include_router(websocket_router)",
        "app.include_router(audit_router)",
    ]
    results.append(
        CheckResult(
            name="main.py integration wiring",
            passed=contains_all("attendance_backend/main.py", main_checks),
            details="Main app wiring verified" if contains_all("attendance_backend/main.py", main_checks) else "One or more integration imports/router registrations are missing",
        )
    )

    realtime_checks = [
        "class RealtimeService",
        "async def broadcast(",
        "async def connect_ws(",
        "async def sse_stream(",
        "TEACHER_CACHE_TTL",
    ]
    results.append(
        CheckResult(
            name="Realtime service implementation",
            passed=contains_all("attendance_backend/services/realtime_service.py", realtime_checks),
            details="Realtime service supports websocket/SSE/caching" if contains_all("attendance_backend/services/realtime_service.py", realtime_checks) else "Realtime service missing required behaviors",
        )
    )

    websocket_checks = [
        "/ws/{section_id}",
        "/sse/{section_id}",
        "async def websocket_endpoint(",
        "async def sse_endpoint(",
    ]
    results.append(
        CheckResult(
            name="WebSocket/SSE routes",
            passed=contains_all("attendance_backend/api/websocket.py", websocket_checks),
            details="Realtime subscription endpoints verified" if contains_all("attendance_backend/api/websocket.py", websocket_checks) else "Missing websocket or SSE endpoint",
        )
    )

    teacher_checks = [
        "get_realtime_service",
        "await rt_svc.broadcast(",
        "get_timetable_service",
        "get_lock_service",
        "TimeValidator",
    ]
    results.append(
        CheckResult(
            name="Teacher API realtime + timetable hooks",
            passed=contains_all("attendance_backend/api/teacher.py", teacher_checks),
            details="Teacher API wired for realtime and timetable validation" if contains_all("attendance_backend/api/teacher.py", teacher_checks) else "Teacher API missing realtime/timetable integration",
        )
    )

    student_checks = [
        "_require_student_role",
        "_assert_own_record",
        "realtime/token",
    ]
    results.append(
        CheckResult(
            name="Student API own-data isolation",
            passed=contains_all("attendance_backend/api/student.py", student_checks),
            details="Student API keeps own-record and realtime token flow" if contains_all("attendance_backend/api/student.py", student_checks) else "Student API missing own-data checks",
        )
    )

    admin_checks = ["require_role(\"admin\")"]
    results.append(
        CheckResult(
            name="Admin API role restriction",
            passed=contains_all("attendance_backend/api/admin.py", admin_checks),
            details="Admin-only routes remain protected" if contains_all("attendance_backend/api/admin.py", admin_checks) else "Admin guard missing",
        )
    )

    security_checks = [
        "class PermissionMiddleware",
        "class AuditMiddleware",
        "class RateLimitMiddleware",
        "_AUDITED_METHODS",
        "RATE_LIMITS",
    ]
    security_text = read_text("attendance_backend/main.py") + read_text("attendance_backend/middleware/permission_middleware.py") + read_text("attendance_backend/middleware/audit_middleware.py") + read_text("attendance_backend/utils/rate_limiter.py")
    results.append(
        CheckResult(
            name="Security layer present",
            passed=all(token in security_text for token in security_checks),
            details="Permission, audit, and rate limit layers present" if all(token in security_text for token in security_checks) else "One or more security components missing",
        )
    )

    return results


def main() -> int:
    results = check_prompt6_artifacts()
    passed = sum(1 for result in results if result.passed)
    total = len(results)

    print("PROMPT 6 INTEGRATION VERIFIER")
    print("=" * 70)
    for result in results:
        status = "✓" if result.passed else "✗"
        print(f"{status} {result.name}")
        if result.details:
            print(f"  {result.details}")

    print("=" * 70)
    print(f"Summary: {passed}/{total} checks passed")
    if passed == total:
        print("PROMPT 6 integration is present in the codebase.")
        return 0

    print("PROMPT 6 integration is incomplete or partially wired.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())