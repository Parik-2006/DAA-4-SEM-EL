import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:smart_attendance/models/face_model.dart';
import 'package:smart_attendance/services/registration_service.dart';

// ── Registration Service Provider ─────────────────────────────────────────────

final registrationServiceProvider = Provider((ref) {
  return RegistrationService();
});

// ── Detected Faces State ──────────────────────────────────────────────────────

class DetectedFacesState {
  final List<DetectedFace> faces;
  final bool isLoading;
  final String? error;
  final DateTime? lastUpdateTime;

  const DetectedFacesState({
    this.faces = const [],
    this.isLoading = false,
    this.error,
    this.lastUpdateTime,
  });

  DetectedFacesState copyWith({
    List<DetectedFace>? faces,
    bool? isLoading,
    String? error,
    DateTime? lastUpdateTime,
  }) {
    return DetectedFacesState(
      faces: faces ?? this.faces,
      isLoading: isLoading ?? this.isLoading,
      error: error ?? this.error,
      lastUpdateTime: lastUpdateTime ?? this.lastUpdateTime,
    );
  }
}

// ── Detected Faces Notifier ───────────────────────────────────────────────────

class DetectedFacesNotifier extends StateNotifier<DetectedFacesState> {
  final RegistrationService _registrationService;

  DetectedFacesNotifier(this._registrationService)
      : super(const DetectedFacesState());

  /// Process a frame and detect faces
  Future<void> detectFaces(String frameBase64) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final response = await _registrationService.detectFaces(
        frameBase64: frameBase64,
      );
      state = state.copyWith(
        faces: response.faces,
        isLoading: false,
        lastUpdateTime: DateTime.now(),
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: e.toString(),
      );
    }
  }

  /// Clear detected faces
  void clearFaces() {
    state = const DetectedFacesState();
  }
}

final detectedFacesProvider =
    StateNotifierProvider<DetectedFacesNotifier, DetectedFacesState>((ref) {
  final registrationService = ref.watch(registrationServiceProvider);
  return DetectedFacesNotifier(registrationService);
});

// ── Registered Students State ─────────────────────────────────────────────────

class RegisteredStudentsState {
  final List<Map<String, dynamic>> students;
  final bool isLoading;
  final String? error;

  const RegisteredStudentsState({
    this.students = const [],
    this.isLoading = false,
    this.error,
  });

  RegisteredStudentsState copyWith({
    List<Map<String, dynamic>>? students,
    bool? isLoading,
    String? error,
  }) {
    return RegisteredStudentsState(
      students: students ?? this.students,
      isLoading: isLoading ?? this.isLoading,
      error: error ?? this.error,
    );
  }
}

// ── Registered Students Notifier ──────────────────────────────────────────────

class RegisteredStudentsNotifier
    extends StateNotifier<RegisteredStudentsState> {
  final RegistrationService _registrationService;

  RegisteredStudentsNotifier(this._registrationService)
      : super(const RegisteredStudentsState());

  /// Fetch list of registered students
  Future<void> fetchStudents() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final students = await _registrationService.getRegisteredStudents();
      state = state.copyWith(
        students: students,
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: e.toString(),
      );
    }
  }
}

final registeredStudentsProvider =
    StateNotifierProvider<RegisteredStudentsNotifier, RegisteredStudentsState>(
        (ref) {
  final registrationService = ref.watch(registrationServiceProvider);
  return RegisteredStudentsNotifier(registrationService);
});
