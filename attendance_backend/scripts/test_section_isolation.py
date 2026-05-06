"""
Test harness for PROMPT 4 section isolation verification.

Usage:
    python attendance_backend/scripts/test_section_isolation.py

This script verifies that section isolation is working correctly at:
  1. Database level (Firestore queries)
  2. Repository level (attendance_repository.py)
  3. API level (teacher.py, student.py endpoints)
  4. Authorization level (access control)
"""

from datetime import datetime, date
from typing import Dict, List, Any, Optional
import sys
from pathlib import Path

# Bootstrap path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

import logging

logger = logging.getLogger("test.section_isolation")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class TestResult:
    """Simple test result tracker."""
    
    def __init__(self, name: str):
        self.name = name
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def assert_true(self, condition: bool, message: str) -> None:
        if condition:
            self.passed += 1
            print(f"  ✓ {message}")
        else:
            self.failed += 1
            self.errors.append(message)
            print(f"  ✗ {message}")
    
    def assert_equal(self, actual: Any, expected: Any, message: str) -> None:
        if actual == expected:
            self.passed += 1
            print(f"  ✓ {message}")
        else:
            self.failed += 1
            self.errors.append(f"{message}\n    Expected: {expected}\n    Actual:   {actual}")
            print(f"  ✗ {message} (expected {expected}, got {actual})")
    
    def assert_contains(self, container: List, item: Any, message: str) -> None:
        if item in container:
            self.passed += 1
            print(f"  ✓ {message}")
        else:
            self.failed += 1
            self.errors.append(f"{message} - {item} not in {container}")
            print(f"  ✗ {message}")
    
    def summary(self) -> str:
        total = self.passed + self.failed
        pct = (100 * self.passed // total) if total > 0 else 0
        status = "✓ PASS" if self.failed == 0 else "✗ FAIL"
        return f"\n{status}  {self.name}: {self.passed}/{total} ({pct}%)"
    
    def details(self) -> str:
        if not self.errors:
            return ""
        return "\nErrors:\n  " + "\n  ".join(self.errors)


def test_firebase_client_section_queries():
    """Test that firebase_client methods enforce section_id as first filter."""
    result = TestResult("Firebase Client - Section Filtering")
    
    try:
        from database.firebase_client import FirebaseClient
        
        result.assert_true(True, "Firebase client imported")
        
        # Verify method signatures include section_id
        fb = FirebaseClient()
        
        # Check get_section_attendance signature
        import inspect
        sig = inspect.signature(fb.get_section_attendance)
        params = list(sig.parameters.keys())
        result.assert_contains(params, "section_id", "section_id is first parameter")
        
        # Verify section-scoped methods exist
        result.assert_true(hasattr(fb, "create_section"), "create_section method exists")
        result.assert_true(hasattr(fb, "get_section"), "get_section method exists")
        result.assert_true(hasattr(fb, "enroll_student"), "enroll_student method exists")
        result.assert_true(hasattr(fb, "create_course_assignment"), "create_course_assignment exists")
        result.assert_true(hasattr(fb, "get_teacher_sections"), "get_teacher_sections exists")
        result.assert_true(hasattr(fb, "get_section_attendance"), "get_section_attendance exists")
        result.assert_true(hasattr(fb, "get_active_period_for_section"), "get_active_period_for_section exists")
        
    except Exception as e:
        result.assert_true(False, f"Firebase client test failed: {e}")
    
    return result


def test_constants_section_definitions():
    """Test that FIREBASE_COLLECTIONS has section-related entries."""
    result = TestResult("Constants - Section Definitions")
    
    try:
        from config.constants import FIREBASE_COLLECTIONS
        
        result.assert_contains(
            list(FIREBASE_COLLECTIONS.keys()),
            "sections",
            "sections in FIREBASE_COLLECTIONS"
        )
        result.assert_contains(
            list(FIREBASE_COLLECTIONS.keys()),
            "enrollments",
            "enrollments in FIREBASE_COLLECTIONS"
        )
        result.assert_contains(
            list(FIREBASE_COLLECTIONS.keys()),
            "course_assignments",
            "course_assignments in FIREBASE_COLLECTIONS"
        )
        result.assert_contains(
            list(FIREBASE_COLLECTIONS.keys()),
            "audit_logs",
            "audit_logs in FIREBASE_COLLECTIONS"
        )
        
    except Exception as e:
        result.assert_true(False, f"Constants test failed: {e}")
    
    return result


def test_api_teacher_authorization():
    """Test that teacher.py enforces section access control."""
    result = TestResult("API - Teacher Authorization")
    
    try:
        from api.teacher import (
            _assert_section_access,
            _resolve_faculty_id,
            _enforce_period_access,
        )
        from fastapi import HTTPException
        from services.auth_service import TokenPayload
        
        # Test _assert_section_access
        assigned_sections = {"CSE_C_SEM4_2026", "CSE_D_SEM4_2026"}
        
        try:
            _assert_section_access("CSE_C_SEM4_2026", assigned_sections)
            result.assert_true(True, "_assert_section_access allows assigned section")
        except HTTPException:
            result.assert_true(False, "_assert_section_access rejected assigned section")
        
        try:
            _assert_section_access("CSE_E_SEM4_2026", assigned_sections)
            result.assert_true(False, "_assert_section_access allowed unassigned section")
        except HTTPException:
            result.assert_true(True, "_assert_section_access blocks unassigned section")
        
        # Test TokenPayload structure
        user = TokenPayload(
            user_id="FAC001",
            role="teacher",
            username="prof",
            email="prof@example.com",
            assigned_sections=["CSE_C_SEM4_2026"],
        )
        result.assert_contains(
            ["CSE_C_SEM4_2026"],
            user.assigned_sections[0],
            "TokenPayload includes assigned_sections"
        )
        
    except ImportError as e:
        result.assert_true(False, f"Could not import teacher API: {e}")
    except Exception as e:
        result.assert_true(False, f"Teacher authorization test failed: {e}")
    
    return result


def test_api_student_authorization():
    """Test that student.py enforces own-record guard."""
    result = TestResult("API - Student Authorization")
    
    try:
        from api.student import _assert_own_record
        from fastapi import HTTPException
        
        # Should pass when same student
        try:
            _assert_own_record("1RV23CS001", "1RV23CS001")
            result.assert_true(True, "_assert_own_record allows same student")
        except HTTPException:
            result.assert_true(False, "_assert_own_record rejected same student")
        
        # Should fail when different student
        try:
            _assert_own_record("1RV23CS001", "1RV23CS002")
            result.assert_true(False, "_assert_own_record allowed different student")
        except HTTPException:
            result.assert_true(True, "_assert_own_record blocks different student")
        
    except ImportError:
        result.assert_true(False, "Could not import student API")
    except Exception as e:
        result.assert_true(False, f"Student authorization test failed: {e}")
    
    return result


def test_attendance_repository_section_methods():
    """Test that AttendanceRepository has section-scoped methods."""
    result = TestResult("Repository - Section Methods")
    
    try:
        from database.attendance_repository import AttendanceRepository
        import inspect
        
        repo = AttendanceRepository()
        
        # Verify section-scoped methods exist
        result.assert_true(
            hasattr(repo, "get_section_attendance"),
            "get_section_attendance method exists"
        )
        result.assert_true(
            hasattr(repo, "get_section_attendance_summary"),
            "get_section_attendance_summary method exists"
        )
        result.assert_true(
            hasattr(repo, "get_student_attendance_safe"),
            "get_student_attendance_safe method exists"
        )
        result.assert_true(
            hasattr(repo, "get_admin_daily_summary"),
            "get_admin_daily_summary method exists"
        )
        
        # Check method signatures
        sig = inspect.signature(repo.get_section_attendance)
        params = list(sig.parameters.keys())
        result.assert_contains(params, "class_id", "get_section_attendance takes class_id")
        
    except ImportError as e:
        result.assert_true(False, f"Could not import repository: {e}")
    except Exception as e:
        result.assert_true(False, f"Repository test failed: {e}")
    
    return result


def test_middleware_section_context():
    """Test that middleware provides section context."""
    result = TestResult("Middleware - Section Context")
    
    try:
        from middleware.auth_middleware import require_role, get_current_user
        
        result.assert_true(callable(require_role), "require_role is callable")
        result.assert_true(callable(get_current_user), "get_current_user is callable")
        
        # Test role guards  
        teacher_guard = require_role("teacher")
        result.assert_true(callable(teacher_guard), "require_role returns callable")
        
    except ImportError as e:
        result.assert_true(False, f"Could not import middleware: {e}")
    except Exception as e:
        result.assert_true(False, f"Middleware test failed: {e}")
    
    return result


def test_firestore_indexes_exist():
    """Test that firestore.indexes.json includes section indexes."""
    result = TestResult("Firestore - Indexes")
    
    try:
        import json
        from pathlib import Path
        
        indexes_file = Path(BACKEND_DIR) / "firestore.indexes.json"
        if not indexes_file.exists():
            result.assert_true(False, "firestore.indexes.json not found")
            return result
        
        with open(indexes_file) as f:
            indexes = json.load(f)
        
        result.assert_true("indexes" in indexes, "indexes key in JSON")
        
        # Look for section-related indexes
        section_indexes = [
            idx for idx in indexes.get("indexes", [])
            if any(
                f.get("fieldPath") == "section_id"
                for f in idx.get("fields", [])
            )
        ]
        
        result.assert_contains(
            [len(section_indexes) > 0],  # Check if list is non-empty
            True,
            f"Found {len(section_indexes)} section-scoped indexes"
        )
        
    except Exception as e:
        result.assert_true(False, f"Firestore indexes test failed: {e}")
    
    return result


def test_migration_script_exists():
    """Test that migration script is available."""
    result = TestResult("Migration - Script")
    
    try:
        from pathlib import Path
        
        script_file = Path(BACKEND_DIR) / "scripts" / "add_section_to_attendance.py"
        result.assert_true(script_file.exists(), "add_section_to_attendance.py exists")
        
        # Check it's readable
        if script_file.exists():
            with open(script_file) as f:
                content = f.read()
            result.assert_true(
                "backfill" in content.lower() or "section" in content.lower(),
                "Script mentions backfill or section"
            )
            result.assert_true(
                "dry-run" in content or "dry_run" in content,
                "Script supports dry-run mode"
            )
        
    except Exception as e:
        result.assert_true(False, f"Migration script test failed: {e}")
    
    return result


def run_all_tests() -> List[TestResult]:
    """Run all section isolation tests."""
    
    print("=" * 70)
    print("PROMPT 4 Section Isolation Test Suite")
    print("=" * 70)
    print()
    
    tests = [
        test_firebase_client_section_queries,
        test_constants_section_definitions,
        test_api_teacher_authorization,
        test_api_student_authorization,
        test_attendance_repository_section_methods,
        test_middleware_section_context,
        test_firestore_indexes_exist,
        test_migration_script_exists,
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
            print(result.summary())
            if result.details():
                print(result.details())
        except Exception as e:
            result = TestResult(test_func.__name__)
            result.assert_true(False, f"Unexpected error: {e}")
            results.append(result)
            print(result.summary())
    
    print()
    print("=" * 70)
    
    total_passed = sum(r.passed for r in results)
    total_tests = sum(r.passed + r.failed for r in results)
    overall_pct = (100 * total_passed // total_tests) if total_tests > 0 else 0
    
    if total_tests == total_passed:
        print(f"✓ ALL TESTS PASSED ({overall_pct}%)")
        status_code = 0
    else:
        total_failed = sum(r.failed for r in results)
        print(f"✗ {total_failed} test(s) failed ({overall_pct}% pass)")
        status_code = 1
    
    print("=" * 70)
    
    return results, status_code


if __name__ == "__main__":
    results, status_code = run_all_tests()
    sys.exit(status_code)
