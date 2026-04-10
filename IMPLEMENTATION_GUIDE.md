# Student Registration & Live Face Detection Implementation

This document describes the implementation of the student registration screen and live camera screen for face detection.

## Features Implemented

### 1. Student Registration Screen (`student_registration_screen.dart`)

**Purpose**: Allows new students to register with personal details and face capture.

**Features:**
- ✅ Form validation for all required fields
- ✅ Real-time camera access for face capture (front-facing camera)
- ✅ Face image preview with retake functionality
- ✅ Base64 encoding of face image for API transmission
- ✅ Automatic login after successful registration
- ✅ Multi-step registration with organized sections:
  - Personal Information (Name, Email)
  - Academic Information (Student ID, Department, Semester)
  - Security (Password & Confirmation)
  - Face Registration (Camera capture)

**Key Components:**
```
- Face Capture Section
  - Camera preview with preview/capture/retake buttons
  - Captured face image display
  - Base64 conversion for API

- Form Sections
  - Personal info validation (name, email)
  - Academic info collection
  - Password strength validation
  - Password confirmation matching
```

**API Integration:**
- Endpoint: `POST /api/v1/auth/register`
- Payload:
  ```json
  {
    "name": "Student Name",
    "email": "student@university.edu",
    "student_id": "STU001234",
    "password": "secure_password",
    "department": "Computer Science",
    "semester": "4th Semester",
    "role": "student",
    "face_image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
  }
  ```

### 2. Live Camera Screen (`live_camera_screen.dart`)

**Purpose**: Displays real-time video feed with face detection and identification.

**Features:**
- ✅ Real-time camera feed with front-facing camera
- ✅ Face detection with bounding boxes
- ✅ Face identification with student names
- ✅ Confidence score display (color-coded: green > 85%, yellow 70-85%, red < 70%)
- ✅ Toggle visibility of face names/info
- ✅ Detected faces list with confidence indicators
- ✅ Status bar showing detection count
- ✅ Smooth UI updates at 500ms intervals
- ✅ Error handling with user-friendly messages

**Display Elements:**
1. **Bounding Boxes**: Color-coded based on confidence
   - Green: High confidence (>85%)
   - Amber: Medium confidence (70-85%)
   - Red: Low confidence (<70%)

2. **Face Information Display** (when enabled):
   - Student name
   - Confidence percentage
   - High/Medium confidence badge

3. **Detected Faces List**:
   - Numbered list of detected faces
   - Confidence scoring
   - Student names

4. **Status Bar**:
   - Real-time detection count
   - Loading indicator
   - Error messages

**API Integration:**
- Endpoint: `POST /api/v1/face-recognition/detect`
- Request:
  ```json
  {
    "frame_base64": "data:image/jpeg;base64,..."
  }
  ```
- Response:
  ```json
  {
    "faces": [
      {
        "name": "John Doe",
        "x": 0.1,
        "y": 0.2,
        "width": 0.3,
        "height": 0.4,
        "confidence": 0.95
      }
    ],
    "frame_id": "frame_001",
    "timestamp": 1681234567
  }
  ```

## Models & Services

### New Models

**FaceData** (`face_model.dart`)
- Represents face data captured during registration
- Properties: id, studentId, faceImageBase64, faceEmbedding, capturedAt, confidence

**DetectedFace** (`face_model.dart`)
- Represents a detected face with bounding box
- Properties: name, x, y, width, height, confidence

**FaceDetectionResponse** (`face_model.dart`)
- API response model for face detection
- Properties: faces[], frameId, timestamp

### New Services

**RegistrationService** (`registration_service.dart`)
- `registerStudent()`: Register new student with face data
- `uploadFaceData()`: Upload additional face data
- `detectFaces()`: Process frame for face detection
- `getRegisteredStudents()`: Fetch student list for face database

### New Providers

**registrationServiceProvider**
- Provides singleton instance of RegistrationService

**detectedFacesProvider**
- StateNotifier for managing detected faces state
- Methods: `detectFaces()`, `clearFaces()`

**registeredStudentsProvider**
- StateNotifier for managing registered students
- Methods: `fetchStudents()`

## Camera Permissions Setup

### Android (`android/app/src/main/AndroidManifest.xml`)
```xml
<uses-permission android:name="android.permission.CAMERA" />
```

Add to `android/app/build.gradle`:
```gradle
android {
    defaultConfig {
        minSdkVersion 21
    }
}
```

### iOS (`ios/Runner/Info.plist`)
```xml
<key>NSCameraUsageDescription</key>
<string>This app needs camera access to capture and verify your face for attendance tracking.</string>
```

### Permission Handling
- Uses `mobile_scanner` package for camera access
- Automatic permission requests on first use
- Graceful error handling if permissions are denied

## Routing

### New Routes Added to `app_router.dart`

```
/student-registration  → StudentRegistrationScreen (Auth page)
/live-camera          → LiveCameraScreen (Full-screen, outside shell)
```

**Navigation:**
```dart
// Navigate to student registration
context.go(AppRoutes.studentRegistration);

// Navigate to live camera
context.go(AppRoutes.liveCamera);
```

## Implementation Details

### Face Capture Process (Registration)
1. User opens registration screen
2. Taps "Open Camera" button
3. Camera preview displays (front-facing)
4. User positions face in frame
5. Taps "Capture" to capture face image
6. Image converted to Base64
7. Form submitted with face data
8. Backend processes and stores face encoding
9. Auto-login on success

### Face Detection Process (Live Camera)
1. Screen opens with real-time camera feed
2. Frame capture every 500ms
3. Frame converted to Base64
4. API request for face detection
5. Backend returns detected faces with coordinates
6. Bounding boxes drawn on screen
7. Face names displayed (if recognition enabled)
8. List updated with detected faces
9. Confidence scores displayed with color coding

### Error Handling
- Camera permission denied: Show permission request dialog
- API failures: Retry logic with exponential backoff
- Invalid face image: Show user-friendly error message
- Face detection timeout: Clear previous detections
- Network errors: Display error banner with retry option

## Dependencies

The following packages are used:
- `mobile_scanner: ^5.0.0` - Camera access and frame capture
- `flutter_riverpod: ^2.5.1` - State management
- `dio: ^5.4.3+1` - API requests
- `flutter: ^3.0.0` - UI framework

## Performance Considerations

1. **Frame Processing**:
   - 500ms interval to balance detection accuracy and UI responsiveness
   - Prevents excessive API calls

2. **Memory Management**:
   - Camera controller properly disposed on screen exit
   - Image data cleared when not needed
   - Lifecycle observer for proper cleanup

3. **Battery Usage**:
   - Camera pauses when app moves to background
   - Detection stops during screen lock

4. **API Optimization**:
   - Base64 encoding for image transmission
   - Confidence-based filtering on client side
   - Batch processing support for multiple detections

## Testing Checklist

- [ ] Registration form validation works
- [ ] Camera permissions request appears on first use
- [ ] Face capture saves image correctly
- [ ] Retake functionality works
- [ ] Form submission sends correct data to API
- [ ] Live camera displays real-time feed
- [ ] Face detection draws bounding boxes
- [ ] Student names display correctly
- [ ] Confidence scores color-code properly
- [ ] Toggle name visibility works
- [ ] Detection list updates in real-time
- [ ] Error messages display appropriately
- [ ] App handles camera permission denial
- [ ] Memory cleanup on screen exit
- [ ] Performance is smooth (60 FPS)

## Future Enhancements

1. **Face Liveness Detection**: Verify face is real (not photo)
2. **Multiple Face Capture**: Multiple angles during registration
3. **Face Quality Assessment**: Pre-validation before registration
4. **Batch Attendance**: Process multiple students simultaneously
5. **Face Recognition Accuracy Metrics**: Track system performance
6. **Local Face Database**: Cache for offline detection
7. **Advanced Analytics**: Attendance patterns and insights

## Troubleshooting

### Camera won't open
- Check camera permissions in device settings
- Ensure Android API level 21+
- Verify iOS privacy settings

### Face detection not working
- Ensure backend face detection API is running
- Check network connectivity
- Verify API endpoint URLs in `.env`
- Check API request/response format

### Low confidence scores
- Ensure good lighting conditions
- Position face directly at camera
- Remove glasses/sunglasses if possible
- Keep face unobstructed

### High memory usage
- Reduce frame capture interval
- Optimize image size before transmission
- Clear old detection data periodically
