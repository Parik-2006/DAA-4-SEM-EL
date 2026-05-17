#!/usr/bin/env python
"""
scripts/create_token.py
─────────────────────────────────────────────────────────────────────────────
Generate JWT tokens for testing purposes.

Usage:
  python scripts/create_token.py [--role ROLE] [--user USER_ID] [--section SECTION]

Examples:
  python scripts/create_token.py                                    # admin token
  python scripts/create_token.py --role teacher --user teacher1    # teacher token
  python scripts/create_token.py --role student --user student_001 # student token
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

from utils.token_utils import (
    create_admin_token,
    create_teacher_token,
    create_student_token,
    TokenGenerationError
)


def main():
    """Generate JWT token for specified role and user."""
    parser = argparse.ArgumentParser(
        description="Generate JWT token for testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/create_token.py                                    # admin1 token
  python scripts/create_token.py --role teacher --user teacher1    # teacher token
  python scripts/create_token.py --role student --user student_001 # student token
        """
    )
    parser.add_argument(
        "--role",
        choices=["admin", "teacher", "student"],
        default="admin",
        help="User role (default: admin)"
    )
    parser.add_argument(
        "--user",
        type=str,
        help="User ID (optional, uses role default if not specified)"
    )
    parser.add_argument(
        "--section",
        type=str,
        help="Assigned section (teachers only, default: TEST_SECTION)"
    )
    
    args = parser.parse_args()
    
    try:
        # Generate token based on role
        if args.role == "admin":
            user_id = args.user or "admin1"
            logger.info("Generating admin token for user=%s", user_id)
            token = create_admin_token(user_id=user_id)
        elif args.role == "teacher":
            user_id = args.user or "teacher1"
            sections = [args.section] if args.section else ["TEST_SECTION"]
            logger.info("Generating teacher token for user=%s sections=%s", user_id, sections)
            token = create_teacher_token(user_id=user_id, assigned_sections=sections)
        else:  # student
            user_id = args.user or "student_001"
            logger.info("Generating student token for user=%s", user_id)
            token = create_student_token(user_id=user_id)
        
        # Print token (this is the output that gets captured)
        print(token)
        logger.debug("Token generated successfully")
        return 0
    
    except TokenGenerationError as exc:
        logger.error("Token generation failed: %s", exc)
        return 1
    except Exception as exc:
        logger.error("Unexpected error: %s", exc, exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
