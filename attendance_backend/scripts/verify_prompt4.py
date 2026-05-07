"""
Simple code structure verification for PROMPT 4.

This script verifies the implementation without requiring runtime dependencies
or Firebase credentials. It checks:
  1. File existence
  2. Key function/class definitions
  3. Method signatures
  4. Configuration completeness
"""

import sys
from pathlib import Path
import ast
import json

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent

class CodeVerifier:
    def __init__(self):
        self.checks = []
        self.passed = 0
        self.failed = 0
    
    def file_exists(self, path: str, description: str) -> bool:
        full_path = BACKEND_DIR / path
        exists = full_path.exists()
        status = "✓" if exists else "✗"
        print(f"  {status} {description}")
        if exists:
            self.passed += 1
        else:
            self.failed += 1
        return exists
    
    def function_exists_in_file(self, path: str, function_name: str, 
                               description: str) -> bool:
        full_path = BACKEND_DIR / path
        if not full_path.exists():
            print(f"  ✗ {description} (file not found)")
            self.failed += 1
            return False
        
        try:
            with open(full_path) as f:
                tree = ast.parse(f.read())
            
            # Find function or method
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == function_name:
                        print(f"  ✓ {description}")
                        self.passed += 1
                        return True
            
            print(f"  ✗ {description} (not found)")
            self.failed += 1
            return False
        except Exception as e:
            print(f"  ✗ {description} (parse error: {e})")
            self.failed += 1
            return False
    
    def class_exists_in_file(self, path: str, class_name: str,
                            description: str) -> bool:
        full_path = BACKEND_DIR / path
        if not full_path.exists():
            print(f"  ✗ {description} (file not found)")
            self.failed += 1
            return False
        
        try:
            with open(full_path) as f:
                tree = ast.parse(f.read())
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if node.name == class_name:
                        print(f"  ✓ {description}")
                        self.passed += 1
                        return True
            
            print(f"  ✗ {description} (not found)")
            self.failed += 1
            return False
        except Exception as e:
            print(f"  ✗ {description} (parse error: {e})")
            self.failed += 1
            return False
    
    def json_key_exists(self, path: str, key: str, description: str) -> bool:
        full_path = BACKEND_DIR / path
        if not full_path.exists():
            print(f"  ✗ {description} (file not found)")
            self.failed += 1
            return False
        
        try:
            with open(full_path) as f:
                data = json.load(f)
            
            if key in data or any(key in str(v) for v in data.get("indexes", [])):
                print(f"  ✓ {description}")
                self.passed += 1
                return True
            
            print(f"  ✗ {description} (key not found)")
            self.failed += 1
            return False
        except Exception as e:
            print(f"  ✗ {description} (error: {e})")
            self.failed += 1
            return False
    
    def summary(self) -> int:
        total = self.passed + self.failed
        pct = (100 * self.passed // total) if total > 0 else 0
        
        print("\n" + "=" * 70)
        if self.failed == 0:
            print(f"✓ ALL CHECKS PASSED ({pct}%)")
            return 0
        else:
            print(f"✗ {self.failed} check(s) failed ({pct}% pass)")
            return 1


def main():
    print("=" * 70)
    print("PROMPT 4 Implementation - Code Structure Verification")
    print("=" * 70)
    print()
    
    v = CodeVerifier()
    
    # 1. Firebase Client - Section Methods
    print("1. Firebase Client - Section Methods")
    v.class_exists_in_file("database/firebase_client.py", "FirebaseClient", 
                          "FirebaseClient class exists")
    v.function_exists_in_file("database/firebase_client.py", "create_section",
                             "create_section method")
    v.function_exists_in_file("database/firebase_client.py", "enroll_student",
                             "enroll_student method")
    v.function_exists_in_file("database/firebase_client.py", "create_course_assignment",
                             "create_course_assignment method")
    v.function_exists_in_file("database/firebase_client.py", "get_section_attendance",
                             "get_section_attendance method")
    v.function_exists_in_file("database/firebase_client.py", "get_active_period_for_section",
                             "get_active_period_for_section method")
    print()
    
    # 2. Attendance Repository - Section Queries
    print("2. Attendance Repository - Section Queries")
    v.class_exists_in_file("database/attendance_repository.py", "AttendanceRepository",
                          "AttendanceRepository class")
    v.function_exists_in_file("database/attendance_repository.py", "get_section_attendance",
                             "get_section_attendance method")
    v.function_exists_in_file("database/attendance_repository.py", "get_student_attendance_safe",
                             "get_student_attendance_safe method")
    print()
    
    # 3. Teacher API - Authorization
    print("3. Teacher API - Authorization & Validation")
    v.function_exists_in_file("api/teacher.py", "_assert_section_access",
                             "_assert_section_access guard")
    v.function_exists_in_file("api/teacher.py", "_get_assigned_sections",
                             "_get_assigned_sections method")
    v.function_exists_in_file("api/teacher.py", "_enforce_period_access",
                             "_enforce_period_access guard")
    v.function_exists_in_file("api/teacher.py", "mark_single_attendance",
                             "mark_single_attendance endpoint")
    v.function_exists_in_file("api/teacher.py", "mark_bulk_attendance",
                             "mark_bulk_attendance endpoint")
    print()
    
    # 4. Student API - Guards
    print("4. Student API - Own-Record Guards")
    v.function_exists_in_file("api/student.py", "_assert_own_record",
                             "_assert_own_record guard")
    v.function_exists_in_file("api/student.py", "_require_student_role",
                             "_require_student_role auth")
    print()
    
    # 5. Admin API - Role Check
    print("5. Admin API - Role-Based Access")
    with open(BACKEND_DIR / "api/admin.py") as f:
        admin_content = f.read()
    has_analytics_route = (
        "analytics/overview" in admin_content
        or "analytics/sections" in admin_content
        or "analytics/trends" in admin_content
    )
    status = "✓" if has_analytics_route else "✗"
    print(f"  {status} analytics endpoint(s) present")
    if has_analytics_route:
        v.passed += 1
    else:
        v.failed += 1
    print()
    
    # 6. Sections API
    print("6. Sections API - Section Management")
    v.file_exists("api/sections.py", "sections.py router exists")
    print()
    
    # 7. Constants - Section Definitions
    print("7. Constants - Section Definitions")
    v.file_exists("config/constants.py", "constants.py exists")
    with open(BACKEND_DIR / "config/constants.py") as f:
        content = f.read()
        checks = [
            ("sections" in content, "sections collection defined"),
            ("enrollments" in content, "enrollments collection defined"),
            ("course_assignments" in content, "course_assignments defined"),
            ("COLLECTION_SECTIONS" in content, "COLLECTION_SECTIONS constant"),
            ("COLLECTION_ENROLLMENTS" in content, "COLLECTION_ENROLLMENTS constant"),
        ]
        for check, desc in checks:
            status = "✓" if check else "✗"
            print(f"  {status} {desc}")
            if check:
                v.passed += 1
            else:
                v.failed += 1
    print()
    
    # 8. Firestore Indexes
    print("8. Firestore Indexes - Section Support")
    v.file_exists("firestore.indexes.json", "firestore.indexes.json exists")
    if (BACKEND_DIR / "firestore.indexes.json").exists():
        with open(BACKEND_DIR / "firestore.indexes.json") as f:
            data = json.load(f)
            # Check if any index mentions section
            has_section_index = any(
                any(f.get("fieldPath") == "section_id" for f in idx.get("fields", []))
                for idx in data.get("indexes", [])
            )
            status = "✓" if has_section_index else "✗"
            print(f"  {status} Section-scoped indexes defined")
            if has_section_index:
                v.passed += 1
            else:
                v.failed += 1
    print()
    
    # 9. Migration Script
    print("9. Migration Script - Backfill Support")
    v.file_exists("scripts/add_section_to_attendance.py", "Migration script exists")
    print()
    
    # 10. Test Script
    print("10. Test Script - Verification Suite")
    v.file_exists("scripts/test_section_isolation.py", "Test script exists")
    print()
    
    # 11. Documentation
    print("11. Documentation")
    # Prompt 4 documentation lives in the repository root, not inside backend/
    root_files = [
        ("PROMPT_4_IMPLEMENTATION_COMPLETE.md", "Implementation guide"),
        ("PROMPT_4_QUICK_REFERENCE.md", "Quick reference"),
    ]
    for rel_path, desc in root_files:
        full_path = REPO_DIR / rel_path
        exists = full_path.exists()
        status = "✓" if exists else "✗"
        print(f"  {status} {desc}")
        if exists:
            v.passed += 1
        else:
            v.failed += 1
    print()
    
    # Summary
    status = v.summary()
    print("=" * 70)
    
    return status


if __name__ == "__main__":
    sys.exit(main())
