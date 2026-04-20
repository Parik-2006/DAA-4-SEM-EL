import 'dart:io';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'firebase_exception_handler.dart';

/// Student Model
class StudentModel {
  final String? id;
  final String name;
  final String email;
  final String rollNumber;
  final String courseId;
  final String? photoUrl;
  final DateTime? createdAt;

  StudentModel({
    this.id,
    required this.name,
    required this.email,
    required this.rollNumber,
    required this.courseId,
    this.photoUrl,
    this.createdAt,
  });

  Map<String, dynamic> toMap() {
    return {
      'name': name,
      'email': email,
      'rollNumber': rollNumber,
      'courseId': courseId,
      'photoUrl': photoUrl,
      'createdAt': createdAt ?? Timestamp.now(),
    };
  }

  factory StudentModel.fromMap(Map<String, dynamic> map, String id) {
    return StudentModel(
      id: id,
      name: map['name'] ?? '',
      email: map['email'] ?? '',
      rollNumber: map['rollNumber'] ?? '',
      courseId: map['courseId'] ?? '',
      photoUrl: map['photoUrl'],
      createdAt: (map['createdAt'] as Timestamp?)?.toDate(),
    );
  }
}

/// Attendance Record Model
class AttendanceRecordModel {
  final String? id;
  final String studentId;
  final String courseId;
  final DateTime date;
  final bool isPresent;
  final String? photoUrl;
  final DateTime? timestamp;

  AttendanceRecordModel({
    this.id,
    required this.studentId,
    required this.courseId,
    required this.date,
    required this.isPresent,
    this.photoUrl,
    this.timestamp,
  });

  Map<String, dynamic> toMap() {
    return {
      'studentId': studentId,
      'courseId': courseId,
      'date': date,
      'isPresent': isPresent,
      'photoUrl': photoUrl,
      'timestamp': timestamp ?? Timestamp.now(),
    };
  }

  factory AttendanceRecordModel.fromMap(Map<String, dynamic> map, String id) {
    return AttendanceRecordModel(
      id: id,
      studentId: map['studentId'] ?? '',
      courseId: map['courseId'] ?? '',
      date: (map['date'] as Timestamp?)?.toDate() ?? DateTime.now(),
      isPresent: map['isPresent'] ?? false,
      photoUrl: map['photoUrl'],
      timestamp: (map['timestamp'] as Timestamp?)?.toDate(),
    );
  }
}

/// Firebase Firestore Service
class FirebaseFirestoreService {
  static final FirebaseFirestoreService _instance =
      FirebaseFirestoreService._internal();
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;

  factory FirebaseFirestoreService() {
    return _instance;
  }

  FirebaseFirestoreService._internal();

  /// Add a new student
  Future<String> addStudent(StudentModel student) async {
    try {
      final docRef = await _firestore
          .collection('students')
          .add(student.toMap());
      return docRef.id;
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

  /// Get student by ID
  Future<StudentModel?> getStudent(String studentId) async {
    try {
      final doc = await _firestore
          .collection('students')
          .doc(studentId)
          .get();

      if (!doc.exists) return null;
      return StudentModel.fromMap(doc.data() as Map<String, dynamic>, doc.id);
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

  /// Get all students
  Future<List<StudentModel>> getAllStudents() async {
    try {
      final querySnapshot = await _firestore.collection('students').get();
      return querySnapshot.docs
          .map((doc) =>
              StudentModel.fromMap(doc.data() as Map<String, dynamic>, doc.id))
          .toList();
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

  /// Get students by course
  Future<List<StudentModel>> getStudentsByCourse(String courseId) async {
    try {
      final querySnapshot = await _firestore
          .collection('students')
          .where('courseId', isEqualTo: courseId)
          .get();

      return querySnapshot.docs
          .map((doc) =>
              StudentModel.fromMap(doc.data() as Map<String, dynamic>, doc.id))
          .toList();
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

  /// Update student
  Future<void> updateStudent(String studentId, StudentModel student) async {
    try {
      await _firestore
          .collection('students')
          .doc(studentId)
          .update(student.toMap());
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

  /// Delete student
  Future<void> deleteStudent(String studentId) async {
    try {
      await _firestore.collection('students').doc(studentId).delete();
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

  /// Record attendance
  Future<String> recordAttendance(AttendanceRecordModel record) async {
    try {
      final docRef = await _firestore
          .collection('attendance')
          .add(record.toMap());
      return docRef.id;
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

  /// Get attendance records for student
  Future<List<AttendanceRecordModel>> getStudentAttendance(
    String studentId, {
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    try {
      var query = _firestore
          .collection('attendance')
          .where('studentId', isEqualTo: studentId);

      if (startDate != null) {
        query = query.where('date', isGreaterThanOrEqualTo: startDate);
      }
      if (endDate != null) {
        query = query.where('date', isLessThanOrEqualTo: endDate);
      }

      final querySnapshot = await query.get();
      return querySnapshot.docs
          .map((doc) => AttendanceRecordModel.fromMap(
              doc.data() as Map<String, dynamic>, doc.id))
          .toList();
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

  /// Get attendance statistics
  Future<Map<String, dynamic>> getAttendanceStats(String courseId) async {
    try {
      final recordsSnapshot =
          await _firestore
              .collection('attendance')
              .where('courseId', isEqualTo: courseId)
              .get();

      int totalRecords = recordsSnapshot.docs.length;
      int presentCount = recordsSnapshot.docs
          .where((doc) => doc['isPresent'] == true)
          .length;

      return {
        'totalRecords': totalRecords,
        'presentCount': presentCount,
        'absentCount': totalRecords - presentCount,
        'percentage': totalRecords > 0
            ? ((presentCount / totalRecords) * 100).toStringAsFixed(2)
            : '0.00',
      };
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

  /// Batch write records
  Future<void> batchWriteAttendance(
      List<AttendanceRecordModel> records) async {
    try {
      final batch = _firestore.batch();
      for (final record in records) {
        final docRef = _firestore.collection('attendance').doc();
        batch.set(docRef, record.toMap());
      }
      await batch.commit();
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
