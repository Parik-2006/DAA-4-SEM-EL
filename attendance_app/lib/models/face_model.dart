import 'package:equatable/equatable.dart';

/// Represents face data captured during registration
class FaceData extends Equatable {
  final String id;
  final String studentId;
  final String faceImageBase64; // Base64 encoded image
  final String? faceEmbedding; // Optional: face vector embedding as JSON string
  final DateTime capturedAt;
  final double? confidence; // Confidence score of face detection (0-1)

  const FaceData({
    required this.id,
    required this.studentId,
    required this.faceImageBase64,
    this.faceEmbedding,
    required this.capturedAt,
    this.confidence,
  });

  factory FaceData.fromJson(Map<String, dynamic> json) {
    return FaceData(
      id: json['id'] as String,
      studentId: json['student_id'] as String,
      faceImageBase64: json['face_image_base64'] as String? ?? '',
      faceEmbedding: json['face_embedding'] as String?,
      capturedAt: DateTime.parse(
        json['captured_at'] as String? ?? DateTime.now().toIso8601String(),
      ),
      confidence: (json['confidence'] as num?)?.toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'student_id': studentId,
        'face_image_base64': faceImageBase64,
        'face_embedding': faceEmbedding,
        'captured_at': capturedAt.toIso8601String(),
        'confidence': confidence,
      };

  @override
  List<Object?> get props => [
        id,
        studentId,
        faceImageBase64,
        faceEmbedding,
        capturedAt,
        confidence,
      ];
}

/// Represents a detected face with bounding box and name
class DetectedFace extends Equatable {
  final String name;
  final double x; // Bounding box left
  final double y; // Bounding box top
  final double width; // Bounding box width
  final double height; // Bounding box height
  final double confidence; // Detection confidence (0-1)

  const DetectedFace({
    required this.name,
    required this.x,
    required this.y,
    required this.width,
    required this.height,
    required this.confidence,
  });

  factory DetectedFace.fromJson(Map<String, dynamic> json) {
    return DetectedFace(
      name: json['name'] as String? ?? 'Unknown',
      x: (json['x'] as num?)?.toDouble() ?? 0.0,
      y: (json['y'] as num?)?.toDouble() ?? 0.0,
      width: (json['width'] as num?)?.toDouble() ?? 0.0,
      height: (json['height'] as num?)?.toDouble() ?? 0.0,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {
        'name': name,
        'x': x,
        'y': y,
        'width': width,
        'height': height,
        'confidence': confidence,
      };

  @override
  List<Object?> get props => [name, x, y, width, height, confidence];
}

/// Response from face detection API
class FaceDetectionResponse extends Equatable {
  final List<DetectedFace> faces;
  final String frameId;
  final int timestamp;

  const FaceDetectionResponse({
    required this.faces,
    required this.frameId,
    required this.timestamp,
  });

  factory FaceDetectionResponse.fromJson(Map<String, dynamic> json) {
    return FaceDetectionResponse(
      faces: (json['faces'] as List<dynamic>?)
              ?.map((f) => DetectedFace.fromJson(f as Map<String, dynamic>))
              .toList() ??
          [],
      frameId: json['frame_id'] as String? ?? '',
      timestamp: json['timestamp'] as int? ?? 0,
    );
  }

  @override
  List<Object?> get props => [faces, frameId, timestamp];
}
