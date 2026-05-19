#!/usr/bin/env python
"""
Legacy compatibility wrapper for the unified backend seeding utilities.

Prefer `scripts/seed_via_backend.py`, which uses `utils.seed_utils` and the
backend's Firebase initialization path.
"""

from seed_via_backend import main


if __name__ == "__main__":
    raise SystemExit(main())
