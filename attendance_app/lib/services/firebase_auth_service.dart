import 'dart:io';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'firebase_exception_handler.dart';

/// Firebase Authentication Service
/// Handles user authentication operations with comprehensive error handling
class FirebaseAuthService {
  static final FirebaseAuthService _instance = FirebaseAuthService._internal();
  final FirebaseAuth _firebaseAuth = FirebaseAuth.instance;

  factory FirebaseAuthService() {
    return _instance;
  }

  FirebaseAuthService._internal();

  /// Get current authenticated user
  User? get currentUser => _firebaseAuth.currentUser;

  /// Get auth state stream
  Stream<User?> get authStateChanges => _firebaseAuth.authStateChanges();

  /// Sign up with email and password
  Future<UserCredential> signUp({
    required String email,
    required String password,
    required String displayName,
  }) async {
    try {
      final userCredential = await _firebaseAuth.createUserWithEmailAndPassword(
        email: email.trim(),
        password: password,
      );

      // Update display name
      await userCredential.user?.updateDisplayName(displayName);
      await userCredential.user?.reload();

      return userCredential;
    } on FirebaseAuthException catch (e) {
      throw FirebaseExceptionHandler.handleException(
        e,
        platform: Platform.operatingSystem,
      );
    } catch (e) {
      throw FirebaseExceptionHandler.handleException(
        e,
        platform: Platform.operatingSystem,
      );
    }
  }

  /// Sign in with email and password
  Future<UserCredential> signIn({
    required String email,
    required String password,
  }) async {
    try {
      return await _firebaseAuth.signInWithEmailAndPassword(
        email: email.trim(),
        password: password,
      );
    } on FirebaseAuthException catch (e) {
      throw FirebaseExceptionHandler.handleException(
        e,
        platform: Platform.operatingSystem,
      );
    } catch (e) {
      throw FirebaseExceptionHandler.handleException(
        e,
        platform: Platform.operatingSystem,
      );
    }
  }

  /// Sign out
  Future<void> signOut() async {
    try {
      await _firebaseAuth.signOut();
    } catch (e) {
      throw FirebaseExceptionHandler.handleException(
        e,
        platform: Platform.operatingSystem,
      );
    }
  }

  /// Get ID token for API calls
  Future<String?> getIdToken() async {
    try {
      return await _firebaseAuth.currentUser?.getIdToken();
    } catch (e) {
      throw FirebaseExceptionHandler.handleException(
        e,
        platform: Platform.operatingSystem,
      );
    }
  }

  /// Send password reset email
  Future<void> sendPasswordResetEmail(String email) async {
    try {
      await _firebaseAuth.sendPasswordResetEmail(email: email.trim());
    } on FirebaseAuthException catch (e) {
      throw FirebaseExceptionHandler.handleException(
        e,
        platform: Platform.operatingSystem,
      );
    } catch (e) {
      throw FirebaseExceptionHandler.handleException(
        e,
        platform: Platform.operatingSystem,
      );
    }
  }

  /// Update user profile
  Future<void> updateProfile({
    String? displayName,
    String? photoUrl,
  }) async {
    try {
      final user = _firebaseAuth.currentUser;
      if (user == null) throw Exception('No user currently signed in');

      await user.updateDisplayName(displayName);
      if (photoUrl != null) {
        await user.updatePhotoURL(photoUrl);
      }
      await user.reload();
    } catch (e) {
      throw FirebaseExceptionHandler.handleException(
        e,
        platform: Platform.operatingSystem,
      );
    }
  }

  /// Check if user is authenticated
  bool get isAuthenticated => _firebaseAuth.currentUser != null;

  /// Get current user email
  String? get userEmail => _firebaseAuth.currentUser?.email;

  /// Get current user name
  String? get userName => _firebaseAuth.currentUser?.displayName;

  /// Get current user UID
  String? get userId => _firebaseAuth.currentUser?.uid;
}
