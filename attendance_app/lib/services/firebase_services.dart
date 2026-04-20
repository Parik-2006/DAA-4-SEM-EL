// Export all Firebase services from a single place
export 'firebase_exception_handler.dart';
export 'firebase_auth_service.dart';
export 'firebase_firestore_service.dart';
export 'firebase_storage_service.dart';

/// Initialize all Firebase services
/// Call this once during app startup
Future<void> initializeFirebaseServices() async {
  // Services initialize on first access (singleton pattern)
  // No additional initialization needed
}
