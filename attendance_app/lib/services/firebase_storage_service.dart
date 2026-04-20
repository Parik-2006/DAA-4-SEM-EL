import 'dart:io';
import 'package:firebase_storage/firebase_storage.dart';
import 'firebase_exception_handler.dart';

/// Firebase Storage Service
/// Handles file uploads, downloads, and management with error handling
class FirebaseStorageService {
  static final FirebaseStorageService _instance =
      FirebaseStorageService._internal();
  final FirebaseStorage _storage = FirebaseStorage.instance;

  factory FirebaseStorageService() {
    return _instance;
  }

  FirebaseStorageService._internal();

  /// Upload file from path
  Future<String> uploadFile({
    required File file,
    required String path,
    void Function(TaskSnapshot)? onProgress,
  }) async {
    try {
      final fileName = file.path.split('/').last;
      final ref = _storage.ref('$path/$fileName');

      final uploadTask = ref.putFile(file);

      uploadTask.snapshotEvents.listen((TaskSnapshot snapshot) {
        onProgress?.call(snapshot);
      });

      final snapshot = await uploadTask;
      return await snapshot.ref.getDownloadURL();
    } on FirebaseException catch (e) {
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

  /// Upload file with bytes
  Future<String> uploadBytes({
    required List<int> bytes,
    required String fileName,
    required String path,
    String? contentType,
  }) async {
    try {
      final ref = _storage.ref('$path/$fileName');
      final metadata = SettableMetadata(contentType: contentType);

      final uploadTask = ref.putData(bytes, metadata);
      final snapshot = await uploadTask;
      return await snapshot.ref.getDownloadURL();
    } on FirebaseException catch (e) {
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

  /// Upload attendance photo
  Future<String> uploadAttendancePhoto({
    required File photoFile,
    required String studentId,
    required String courseId,
    DateTime? dateTime,
  }) async {
    try {
      final timestamp = (dateTime ?? DateTime.now()).millisecondsSinceEpoch;
      final fileName = 'attendance_${studentId}_$timestamp.jpg';
      final path = 'attendance/$courseId/$studentId';

      return await uploadFile(
        file: photoFile,
        path: path,
      );
    } on FirebaseException catch (e) {
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

  /// Upload student avatar
  Future<String> uploadStudentAvatar({
    required File avatarFile,
    required String studentId,
  }) async {
    try {
      final fileName = 'avatar_$studentId.jpg';
      final path = 'avatars/students';

      return await uploadFile(
        file: avatarFile,
        path: path,
      );
    } on FirebaseException catch (e) {
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

  /// Download file
  Future<List<int>> downloadFile(String path) async {
    try {
      final ref = _storage.ref(path);
      final data = await ref.getData();
      return data ?? [];
    } on FirebaseException catch (e) {
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

  /// Get file download URL
  Future<String> getFileUrl(String path) async {
    try {
      final ref = _storage.ref(path);
      return await ref.getDownloadURL();
    } on FirebaseException catch (e) {
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

  /// Delete file
  Future<void> deleteFile(String path) async {
    try {
      final ref = _storage.ref(path);
      await ref.delete();
    } on FirebaseException catch (e) {
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

  /// List files in folder
  Future<List<Reference>> listFiles(String path) async {
    try {
      final ref = _storage.ref(path);
      final result = await ref.listAll();
      return result.items;
    } on FirebaseException catch (e) {
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

  /// Get file metadata
  Future<FullMetadata> getFileMetadata(String path) async {
    try {
      final ref = _storage.ref(path);
      return await ref.getMetadata();
    } on FirebaseException catch (e) {
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
}
