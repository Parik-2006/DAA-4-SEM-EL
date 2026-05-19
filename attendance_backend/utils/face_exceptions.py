"""
Face Confirmation Learning exceptions.

Provides domain-specific exceptions for face confirmation, learning, and profile management.
"""


class FaceConfirmationError(Exception):
    """Base exception for face confirmation operations."""
    pass


class FaceDetectionNotFoundError(FaceConfirmationError):
    """Raised when a detection_id cannot be found or has expired."""
    pass


class FaceDetectionExpiredError(FaceConfirmationError):
    """Raised when a detection has expired and cannot be used."""
    pass


class FaceAuthorizationError(FaceConfirmationError):
    """Raised when user is not authorized to confirm an identity."""
    pass


class FaceIdentityMismatchError(FaceConfirmationError):
    """Raised when predicted and confirmed identities are incompatible."""
    pass


class FaceProfileError(FaceConfirmationError):
    """Base exception for face profile operations."""
    pass


class FaceProfileNotFoundError(FaceProfileError):
    """Raised when a face profile does not exist."""
    pass


class FaceProfileUpdateError(FaceProfileError):
    """Raised when face profile update fails."""
    pass


class FaceLearningError(FaceConfirmationError):
    """Base exception for face learning operations."""
    pass


class FaceLearningGateError(FaceLearningError):
    """Raised when a learning gate (quality, liveness, etc.) fails."""
    pass


class FaceAntiDriftError(FaceLearningError):
    """Raised when anti-drift gate rejects a sample as an outlier."""
    pass


class FaceRepositoryError(FaceConfirmationError):
    """Base exception for face repository operations."""
    pass
