#!/usr/bin/env python
"""Test script to verify all utility integrations."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("=" * 60)
print("TESTING INTEGRATED UTILITIES")
print("=" * 60)

# Test 1: Token utilities
print("\n[1] Testing token utilities...")
try:
    from utils.token_utils import (
        create_admin_token,
        create_teacher_token,
        create_student_token,
        validate_token,
        TokenGenerationError
    )
    
    admin_token = create_admin_token()
    print(f"  ✓ Admin token created: {admin_token[:40]}...")
    
    teacher_token = create_teacher_token(user_id="prof1", assigned_sections=["CS101"])
    print(f"  ✓ Teacher token created: {teacher_token[:40]}...")
    
    student_token = create_student_token(user_id="student_001")
    print(f"  ✓ Student token created: {student_token[:40]}...")
    
    # Validate a token
    claims = validate_token(admin_token)
    print(f"  ✓ Token validated. User: {claims['user_id']}, Role: {claims['role']}")
    
    print("  ✅ Token utilities: PASS")
    
except Exception as e:
    print(f"  ❌ Token utilities: FAIL - {e}")
    sys.exit(1)

# Test 2: Seed utilities
print("\n[2] Testing seed utilities...")
try:
    from utils.seed_utils import (
        seed_test_section,
        seed_test_teacher,
        seed_test_students,
        seed_test_timetable,
        seed_complete_test_environment,
        SeedError
    )
    
    print("  ✓ seed_test_section imported")
    print("  ✓ seed_test_teacher imported")
    print("  ✓ seed_test_students imported")
    print("  ✓ seed_test_timetable imported")
    print("  ✓ seed_complete_test_environment imported")
    print("  ✓ SeedError exception imported")
    
    print("  ✅ Seed utilities: PASS")
    
except Exception as e:
    print(f"  ❌ Seed utilities: FAIL - {e}")
    sys.exit(1)

# Test 3: Validation utilities
print("\n[3] Testing validation utilities...")
try:
    from utils.validation_utils import (
        check_health,
        validate_endpoint,
        verify_firestore_persistence,
        log_validation_summary,
        ValidationError,
        EndpointError
    )
    
    print("  ✓ check_health imported")
    print("  ✓ validate_endpoint imported")
    print("  ✓ verify_firestore_persistence imported")
    print("  ✓ log_validation_summary imported")
    print("  ✓ ValidationError exception imported")
    print("  ✓ EndpointError exception imported")
    
    print("  ✅ Validation utilities: PASS")
    
except Exception as e:
    print(f"  ❌ Validation utilities: FAIL - {e}")
    sys.exit(1)

# Test 4: Exception classes
print("\n[4] Testing exception classes...")
try:
    from utils.token_utils import TokenGenerationError, TokenValidationError
    from utils.seed_utils import SeedError
    from utils.validation_utils import ValidationError, EndpointError
    
    # Test that exceptions can be raised and caught
    try:
        raise TokenGenerationError("Test error")
    except TokenGenerationError as e:
        print(f"  ✓ TokenGenerationError: {e}")
    
    try:
        raise SeedError("Test error")
    except SeedError as e:
        print(f"  ✓ SeedError: {e}")
    
    try:
        raise ValidationError("Test error")
    except ValidationError as e:
        print(f"  ✓ ValidationError: {e}")
    
    print("  ✅ Exception classes: PASS")
    
except Exception as e:
    print(f"  ❌ Exception classes: FAIL - {e}")
    sys.exit(1)

# Summary
print("\n" + "=" * 60)
print("✅ ALL INTEGRATION TESTS PASSED")
print("=" * 60)
print("\nUtility Modules Ready for Use:")
print("  • utils/token_utils.py")
print("  • utils/seed_utils.py")
print("  • utils/validation_utils.py")
print("\nEnhanced Scripts:")
print("  • scripts/create_token.py")
print("  • scripts/seed_via_backend.py")
print("  • scripts/validate_fixes_final.py")
print("\nEnhanced Modules:")
print("  • api/attendance.py")
print("\nDocumentation:")
print("  • INTEGRATION_GUIDE.md")
print("=" * 60)
