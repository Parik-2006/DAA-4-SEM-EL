/// Exception Handling Service for Firebase Operations
/// Handles errors from Android and iOS platforms with proper error messages

class FirebaseException implements Exception {
  final String code;
  final String message;
  final String? originalException;
  final String platform;

  FirebaseException({
    required this.code,
    required this.message,
    this.originalException,
    required this.platform,
  });

  @override
  String toString() => 'FirebaseException($platform): [$code] $message';

  /// Get user-friendly error message
  String get userMessage {
    switch (code) {
      case 'auth/email-already-in-use':
        return 'This email is already registered. Please use another email or login.';
      case 'auth/invalid-email':
        return 'Invalid email address. Please check and try again.';
      case 'auth/weak-password':
        return 'Password is too weak. Use at least 6 characters.';
      case 'auth/user-not-found':
        return 'No user found with this email. Please sign up first.';
      case 'auth/wrong-password':
        return 'Incorrect password. Please try again.';
      case 'auth/too-many-requests':
        return 'Too many login attempts. Please try later.';
      case 'permission-denied':
        return 'You do not have permission to access this resource.';
      case 'not-found':
        return 'The requested resource was not found.';
      case 'storage/object-not-found':
        return 'File not found. Please try uploading again.';
      case 'storage/bucket-not-found':
        return 'Storage bucket error. Please try later.';
      case 'network-error':
        return 'Network connection failed. Check your internet and try again.';
      case 'unavailable':
        return 'Service is temporarily unavailable. Please try later.';
      default:
        return message.isNotEmpty ? message : 'An error occurred. Please try again.';
    }
  }

  /// Get error severity level
  ErrorSeverity get severity {
    if (code.startsWith('auth/')) return ErrorSeverity.medium;
    if (code.startsWith('storage/')) return ErrorSeverity.medium;
    if (code == 'network-error') return ErrorSeverity.high;
    if (code == 'unavailable') return ErrorSeverity.high;
    return ErrorSeverity.low;
  }
}

enum ErrorSeverity {
  low,      // User can retry
  medium,   // User action might be needed
  high,     // Critical error, needs attention
}

/// Firebase Service Exception Handler
class FirebaseExceptionHandler {
  static FirebaseException handleException(
    dynamic exception, {
    required String platform,
  }) {
    if (exception is FirebaseException) {
      return exception;
    }

    // Parse Firebase Auth errors
    if (exception.toString().contains('FirebaseAuthException')) {
      final errorCode = _extractErrorCode(exception.toString());
      final errorMessage = _extractErrorMessage(exception.toString());
      return FirebaseException(
        code: errorCode,
        message: errorMessage,
        originalException: exception.toString(),
        platform: platform,
      );
    }

    // Parse Firestore errors
    if (exception.toString().contains('FirebaseException')) {
      final errorCode = _extractErrorCode(exception.toString());
      final errorMessage = _extractErrorMessage(exception.toString());
      return FirebaseException(
        code: errorCode,
        message: errorMessage,
        originalException: exception.toString(),
        platform: platform,
      );
    }

    // Handle network errors
    if (exception.toString().contains('SocketException') ||
        exception.toString().contains('Connection')) {
      return FirebaseException(
        code: 'network-error',
        message: 'Network connection failed',
        originalException: exception.toString(),
        platform: platform,
      );
    }

    // Generic error
    return FirebaseException(
      code: 'unknown-error',
      message: exception.toString(),
      originalException: exception.toString(),
      platform: platform,
    );
  }

  static String _extractErrorCode(String errorString) {
    final match = RegExp(r'\[(\w+/[\w-]+)\]').firstMatch(errorString);
    return match?.group(1) ?? 'unknown-error';
  }

  static String _extractErrorMessage(String errorString) {
    final match = RegExp(r':\s*(.+?)(?:\s*\[|$)').firstMatch(errorString);
    return match?.group(1)?.trim() ?? 'Unknown error occurred';
  }
}
