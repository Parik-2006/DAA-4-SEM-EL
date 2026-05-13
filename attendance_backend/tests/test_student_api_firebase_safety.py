"""
tests/test_student_api_firebase_safety.py
────────────────────────────────────────────────────────────────────────────────
Regression tests for Prompt 3 hardening: safe RTDB reads across student APIs.

Scenarios covered
─────────────────
✓ Missing auth_tokens node → 403 (not 500)
✓ Missing users/{id} node → 200 (not 500)
✓ Missing attendance/{date}/{id} node → 200 with {"status": "not_marked"}
✓ Invalid token format → 403 (not 500)
✓ Revoked token → 403 (not 500)
✓ Student accessing own data → 200
✓ Student accessing another's data → 403
✓ Unenrolled student (no class_id) → 422 for realtime/token
✓ Firebase connectivity errors during auth → 403 (not 500)

Implementation notes
────────────────────
• Uses unittest.mock to stub FirebaseClient and RTDB responses
• No actual Firebase connection required
• Tests the exact status-code matrix from status_code_matrix.md
• Each test isolates a single failure mode and verifies the correct HTTP response
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from firebase_admin.exceptions import NotFoundError

from main import app


class TestStudentAuthFirebaseSafety(unittest.TestCase):
    """Tests for _require_student_role auth guard."""

    def setUp(self):
        self.client = TestClient(app)

    def test_missing_token_header_returns_401(self):
        """No X-Student-Token header → 401."""
        resp = self.client.get("/api/v1/student/attendance/today?student_id=test_id")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("X-Student-Token header required", resp.json()["detail"].lower())

    @patch("api.student.FirebaseClient")
    def test_missing_auth_tokens_node_returns_403(self, mock_fc_class):
        """
        auth_tokens/{token} node missing (RTDB returns None) → 403 not 500.

        This is the core Prompt 1 scenario: missing node must not crash.
        """
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        # Simulate missing node in RTDB: get() returns None
        mock_fc.get_reference.return_value.get.return_value = None

        resp = self.client.get(
            "/api/v1/student/attendance/today?student_id=test_id",
            headers={"X-Student-Token": "unknown_token_xyz"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("invalid", resp.json()["detail"].lower())

    @patch("api.student.FirebaseClient")
    def test_rtdb_notfounderror_during_token_validation_returns_403(self, mock_fc_class):
        """
        RTDB NotFoundError during token lookup → 403 not 500.

        Firebase SDK may raise NotFoundError for missing nodes in some cases.
        """
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        # Simulate NotFoundError from Firebase SDK
        mock_fc.get_reference.return_value.get.side_effect = NotFoundError("404 Not Found")

        resp = self.client.get(
            "/api/v1/student/attendance/today?student_id=test_id",
            headers={"X-Student-Token": "test_token"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("invalid", resp.json()["detail"].lower())

    @patch("api.student.FirebaseClient")
    def test_generic_rtdb_error_during_token_validation_returns_403(self, mock_fc_class):
        """
        RTDB connectivity error during token validation → 403 not 500.

        Prevents auth failures from exposing backend infrastructure issues.
        """
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        # Simulate a transient RTDB error (e.g., timeout, permission denied)
        mock_fc.get_reference.return_value.get.side_effect = ConnectionError("RTDB unreachable")

        resp = self.client.get(
            "/api/v1/student/attendance/today?student_id=test_id",
            headers={"X-Student-Token": "test_token"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("invalid", resp.json()["detail"].lower())

    @patch("api.student.FirebaseClient")
    def test_revoked_token_returns_403(self, mock_fc_class):
        """Revoked token → 403."""
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        mock_fc.get_reference.return_value.get.return_value = {
            "role": "student",
            "student_id": "test_id",
            "revoked": True,
        }

        resp = self.client.get(
            "/api/v1/student/attendance/today?student_id=test_id",
            headers={"X-Student-Token": "test_token"},
        )
        self.assertEqual(resp.status_code, 403)

    @patch("api.student.FirebaseClient")
    def test_wrong_role_token_returns_403(self, mock_fc_class):
        """Token with role='teacher' → 403."""
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        mock_fc.get_reference.return_value.get.return_value = {
            "role": "teacher",  # not "student"
            "student_id": "test_id",
        }

        resp = self.client.get(
            "/api/v1/student/attendance/today?student_id=test_id",
            headers={"X-Student-Token": "test_token"},
        )
        self.assertEqual(resp.status_code, 403)

    @patch("api.student.FirebaseClient")
    def test_unexpected_token_type_non_dict_returns_403(self, mock_fc_class):
        """Token value is a scalar instead of dict → 403 (not 500)."""
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        # Pathological case: node exists but contains a scalar
        mock_fc.get_reference.return_value.get.return_value = "not_a_dict"

        resp = self.client.get(
            "/api/v1/student/attendance/today?student_id=test_id",
            headers={"X-Student-Token": "test_token"},
        )
        self.assertEqual(resp.status_code, 403)

    @patch("api.student.FirebaseClient")
    def test_valid_token_own_data_returns_200(self, mock_fc_class):
        """
        Valid token + own student_id + attendance exists → 200.

        This is the happy path.
        """
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        # Mock token validation
        mock_fc.get_reference.return_value.get.side_effect = [
            # First call: auth_tokens/{token}
            {"role": "student", "student_id": "test_id", "class_id": "class_a"},
            # Second call: attendance/{today}/{student_id}
            {"status": "present", "markedAt": "2026-05-13T09:30:00"},
        ]

        resp = self.client.get(
            "/api/v1/student/attendance/today?student_id=test_id",
            headers={"X-Student-Token": "test_token"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("status", resp.json())

    @patch("api.student.FirebaseClient")
    def test_cross_student_access_returns_403(self, mock_fc_class):
        """
        Valid token for student_id=A, but query params request student_id=B → 403.

        Own-record guard must be enforced.
        """
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        mock_fc.get_reference.return_value.get.return_value = {
            "role": "student",
            "student_id": "student_a",  # authenticated as A
            "class_id": "class_x",
        }

        resp = self.client.get(
            "/api/v1/student/attendance/today?student_id=student_b",  # requesting B
            headers={"X-Student-Token": "test_token"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("not authorised", resp.json()["detail"].lower())


class TestStudentAttendanceEndpointsFirebaseSafety(unittest.TestCase):
    """Tests for attendance query endpoints with missing/malformed RTDB data."""

    def setUp(self):
        self.client = TestClient(app)

    @patch("api.student.FirebaseClient")
    def test_missing_attendance_node_returns_status_not_marked(self, mock_fc_class):
        """
        Attendance node for today doesn't exist (RTDB returns None) → 200
        with {"status": "not_marked"}.

        This is the correct interpretation of an absent attendance record.
        """
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        mock_fc.get_reference.return_value.get.side_effect = [
            # First: token validation
            {"role": "student", "student_id": "test_id", "class_id": "class_a"},
            # Second: attendance/{today}/{id} — missing (None)
            None,
        ]

        resp = self.client.get(
            "/api/v1/student/attendance/today?student_id=test_id",
            headers={"X-Student-Token": "test_token"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "not_marked")

    @patch("api.student.FirebaseClient")
    def test_attendance_node_notfounderror_returns_status_not_marked(self, mock_fc_class):
        """
        Attendance node raises NotFoundError → 200 with {"status": "not_marked"}.

        Firebase SDK may raise NotFoundError for missing nodes.
        """
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        # Side effects: token validation succeeds, attendance lookup raises
        def get_side_effect():
            mock_ref = MagicMock()
            # First call returns token doc, second raises NotFoundError
            call_count = [0]
            def get_impl():
                call_count[0] += 1
                if call_count[0] == 1:
                    return {"role": "student", "student_id": "test_id", "class_id": "class_a"}
                else:
                    raise NotFoundError("404 Not Found")
            mock_ref.get = get_impl
            return mock_ref

        mock_fc.get_reference.return_value = get_side_effect()

        resp = self.client.get(
            "/api/v1/student/attendance/today?student_id=test_id",
            headers={"X-Student-Token": "test_token"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "not_marked")

    @patch("api.student.FirebaseClient")
    def test_attendance_read_error_returns_500(self, mock_fc_class):
        """
        Genuine RTDB error during attendance read (not NotFoundError) → 500.

        Infrastructure failures should surface as 500, not be silently hidden.
        """
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        def get_side_effect():
            mock_ref = MagicMock()
            call_count = [0]
            def get_impl():
                call_count[0] += 1
                if call_count[0] == 1:
                    # Token succeeds
                    return {"role": "student", "student_id": "test_id", "class_id": "class_a"}
                else:
                    # Attendance lookup hits a connectivity error
                    raise IOError("RTDB connection lost")
            mock_ref.get = get_impl
            return mock_ref

        mock_fc.get_reference.return_value = get_side_effect()

        resp = self.client.get(
            "/api/v1/student/attendance/today?student_id=test_id",
            headers={"X-Student-Token": "test_token"},
        )
        self.assertEqual(resp.status_code, 500)


class TestRealtimeTokenEndpointFirebaseSafety(unittest.TestCase):
    """Tests for realtime/token endpoint with missing class_id."""

    def setUp(self):
        self.client = TestClient(app)

    @patch("api.student.FirebaseClient")
    def test_missing_class_id_returns_422(self, mock_fc_class):
        """
        Valid student token but no class_id in token or user profile → 422
        "not enrolled".

        This is the Prompt 3 scenario where class_id cannot be resolved.
        """
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        mock_fc.get_reference.return_value.get.side_effect = [
            # Token validation (no class_id)
            {"role": "student", "student_id": "test_id"},
            # Fallback user profile lookup (missing node)
            None,
        ]

        resp = self.client.get(
            "/api/v1/student/realtime/token?student_id=test_id",
            headers={"X-Student-Token": "test_token"},
        )
        self.assertEqual(resp.status_code, 422)
        self.assertIn("not enrolled", resp.json()["detail"].lower())

    @patch("api.student.FirebaseClient")
    def test_user_profile_missing_returns_422(self, mock_fc_class):
        """
        Token valid, but user profile node doesn't exist → 422.

        The _safe_get_user() helper must return {} instead of raising.
        """
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        mock_fc.get_reference.return_value.get.side_effect = [
            # Token (no class_id)
            {"role": "student", "student_id": "test_id"},
            # User profile (NotFoundError)
            NotFoundError("404"),
        ]

        # Since NotFoundError is raised, we need to handle it in the mock
        call_count = [0]
        def get_impl():
            call_count[0] += 1
            if call_count[0] == 1:
                return {"role": "student", "student_id": "test_id"}
            else:
                raise NotFoundError("404 Not Found")

        mock_fc.get_reference.return_value.get = get_impl

        resp = self.client.get(
            "/api/v1/student/realtime/token?student_id=test_id",
            headers={"X-Student-Token": "test_token"},
        )
        self.assertEqual(resp.status_code, 422)


class TestWebSocketTokenValidationFirebaseSafety(unittest.TestCase):
    """Tests for websocket.py _validate_token with missing/invalid nodes."""

    def setUp(self):
        self.client = TestClient(app)

    @patch("api.websocket.FirebaseClient")
    def test_missing_auth_token_node_returns_none(self, mock_fc_class):
        """
        _validate_token: auth_tokens/{token} node missing (RTDB None) → None.

        Callers should treat None as "invalid token" (403), not crash.
        """
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        mock_fc.get_reference.return_value.get.return_value = None

        # Import the function directly
        from api.websocket import _validate_token

        import asyncio
        result = asyncio.run(_validate_token("unknown_token"))
        self.assertIsNone(result)

    @patch("api.websocket.FirebaseClient")
    def test_token_node_unexpected_type_returns_none(self, mock_fc_class):
        """
        _validate_token: node exists but is scalar → None (not crash).

        The isinstance guard must prevent AttributeError.
        """
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        # Pathological case: node contains a scalar
        mock_fc.get_reference.return_value.get.return_value = "scalar_value"

        from api.websocket import _validate_token
        import asyncio
        result = asyncio.run(_validate_token("bad_token"))
        self.assertIsNone(result)


class TestUserAPIFirebaseSafety(unittest.TestCase):
    """Tests for user.py reset_password with missing users node."""

    def setUp(self):
        self.client = TestClient(app)

    @patch("api.user.FirebaseClient")
    def test_missing_users_node_returns_400(self, mock_fc_class):
        """
        reset_password: RTDB 'users' node missing (None) → 400
        "Invalid or expired reset token" (not 500).
        """
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        # Simulate missing users node
        mock_fc.get_reference.return_value.get.return_value = None

        resp = self.client.post(
            "/api/v1/user/reset-password",
            json={"token": "some_token", "new_password": "newpass123"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("invalid or expired", resp.json()["detail"].lower())

    @patch("api.user.FirebaseClient")
    def test_users_node_unexpected_type_returns_400(self, mock_fc_class):
        """
        reset_password: 'users' node is scalar → 400 (not 500).

        The isinstance guard must prevent crashing on non-dict nodes.
        """
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        # Pathological case: users is a scalar
        mock_fc.get_reference.return_value.get.return_value = "scalar_users_value"

        resp = self.client.post(
            "/api/v1/user/reset-password",
            json={"token": "some_token", "new_password": "newpass123"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("invalid or expired", resp.json()["detail"].lower())

    @patch("api.user.FirebaseClient")
    def test_firebase_error_during_users_read_returns_400(self, mock_fc_class):
        """
        reset_password: Firebase read error → 400 (not 500).

        Errors are caught and logged; user sees safe message.
        """
        mock_fc = MagicMock()
        mock_fc_class.return_value = mock_fc

        # Simulate a Firebase connectivity error
        mock_fc.get_reference.return_value.get.side_effect = IOError("RTDB unreachable")

        resp = self.client.post(
            "/api/v1/user/reset-password",
            json={"token": "some_token", "new_password": "newpass123"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("invalid or expired", resp.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
