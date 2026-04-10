# Camera Permissions Setup Guide

## Android Setup

### 1. Update AndroidManifest.xml

Edit `android/app/src/main/AndroidManifest.xml`:

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <!-- Add these permissions -->
    <uses-permission android:name="android.permission.CAMERA" />
    <uses-permission android:name="android.permission.INTERNET" />
    
    <!-- ... rest of manifest ... -->
</manifest>
```

### 2. Update build.gradle

Edit `android/app/build.gradle`:

```gradle
android {
    compileSdkVersion 34  // or your target SDK version
    
    defaultConfig {
        applicationId "com.example.smart_attendance"
        minSdkVersion 21    // Minimum for camera support
        targetSdkVersion 34
        versionCode 1
        versionName "1.0.0"
    }
    
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_11
        targetCompatibility JavaVersion.VERSION_11
    }
}

dependencies {
    // Camera permissions are handled by mobile_scanner
    implementation 'androidx.camera:camera-core:1.3.0'
    implementation 'androidx.camera:camera-camera2:1.3.0'
    implementation 'androidx.camera:camera-lifecycle:1.3.0'
}
```

### 3. Runtime Permissions (Android 6.0+)

The `mobile_scanner` package handles runtime permission requests automatically. When the camera is accessed, a system dialog will appear asking for permission.

Users need to grant "Camera" permission in the app settings.

## iOS Setup

### 1. Update Info.plist

Edit `ios/Runner/Info.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- Add camera permission request -->
    <key>NSCameraUsageDescription</key>
    <string>This app needs camera access to capture and verify your face for attendance tracking.</string>
    
    <!-- Add internet permission -->
    <key>NSBonjourServiceTypes</key>
    <array>
        <string>_http._tcp</string>
    </array>
    
    <!-- ... rest of plist ... -->
</dict>
</plist>
```

### 2. Podfile Configuration

Edit `ios/Podfile`:

```ruby
post_install do |installer|
  installer.pods_project.targets.each do |target|
    flutter_additional_ios_build_settings(target)
    
    # Permissions configuration
    target.build_configurations.each do |config|
      config.build_settings['GCC_ENABLE_OBJC_WEAK'] = 'YES'
    end
  end
end
```

### 3. Xcode Configuration

1. Open `ios/Runner.xcworkspace` in Xcode
2. Select Runner project
3. Select Runner target
4. Go to Build Settings
5. Search for "Code Signing"
6. Ensure signing certificate is configured

## Testing Camera Access

### Test on Android Emulator

```bash
# Start Android emulator with camera support
flutter emulators --launch Pixel_4_API_31

# Install and run app
flutter run -d emulator-5554
```

### Test on iOS Simulator

```bash
# Camera is automatically available in iOS simulator
flutter run -d "iPhone 15"
```

### Test on Physical Device

1. **Android**: Grant camera permission when app first requests it
2. **iOS**: Grant camera permission in App Settings → Camera

## Permission Request Flow

### First Time App Launch

1. User navigates to registration or live camera screen
2. `mobile_scanner` requests camera permission
3. System permission dialog appears
4. User grants/denies permission
5. If granted: Camera opens and works
6. If denied: Show error message and guide to settings

### Checking Permission Status

The app gracefully handles permission states:

```dart
// Permission already granted: Camera works immediately
// Permission denied: Error dialog with settings navigation
// Permission not requested yet: System dialog appears
```

## Troubleshooting

### Camera permission always denied on Android

1. Check AndroidManifest.xml has camera permission
2. Verify minSdkVersion >= 21
3. Clear app data and reinstall
4. Check Settings → Apps → Permissions

### iOS simulator shows black screen

1. Simulator might not have camera support
2. Use physical device for testing
3. Check Xcode project settings for camera entitlements

### Permission dialog not appearing (Android)

1. Ensure minSdkVersion is set to 21 or higher
2. Verify the APK is not in release mode without permissions
3. Check device Android version (6.0+ requires runtime permissions)

### Camera access fails silently

1. Check if permissions are granted in app settings
2. Verify network connectivity (for API calls)
3. Check Logcat (Android) or Console (iOS) for error messages

## API Requirements

### Backend Face Detection API

The backend must implement:

**Endpoint**: `POST /api/v1/face-recognition/detect`

**Request**:
```json
{
  "frame_base64": "base64_encoded_jpeg_image"
}
```

**Response**:
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
  "frame_id": "frame_123",
  "timestamp": 1681234567
}
```

### Student Registration API

**Endpoint**: `POST /api/v1/auth/register`

**Request**:
```json
{
  "name": "John Doe",
  "email": "john@university.edu",
  "student_id": "STU001234",
  "password": "secure_password",
  "department": "Computer Science",
  "semester": "4th Semester",
  "role": "student",
  "face_image_base64": "base64_encoded_jpeg_image"
}
```

**Response**:
```json
{
  "id": "user_uuid",
  "name": "John Doe",
  "email": "john@university.edu",
  "student_id": "STU001234",
  "department": "Computer Science",
  "semester": "4th Semester",
  "role": "student",
  "avatar_url": "https://api.example.com/avatars/user_uuid.jpg",
  "is_active": true,
  "created_at": "2024-04-10T10:30:00Z"
}
```

## Environment Configuration

Update `.env` file:

```
# API Configuration
BASE_URL=http://10.0.2.2:8000

# Face Detection Settings
FACE_DETECTION_INTERVAL_MS=500
FACE_CONFIDENCE_THRESHOLD=0.70
MAX_DETECTION_RESULTS=10
```

## Security Considerations

1. **Sensitive Data**:
   - Face images are encoded in Base64
   - Always use HTTPS in production
   - Store images securely on backend
   - Implement access controls on API endpoints

2. **Privacy**:
   - Clearly inform users about face data collection
   - Follow GDPR/local privacy regulations
   - Provide data deletion options
   - Encrypt data in transit and at rest

3. **App Security**:
   - Validate all API responses
   - Implement certificate pinning for production
   - Sanitize user inputs
   - Use Firebase Security Rules if applicable

## Performance Optimization

1. **Image Compression**:
   - Compress JPEG before encoding
   - Target ~200KB per frame

2. **Frame Rate**:
   - Default: 500ms interval (2 fps)
   - Adjust based on backend capacity

3. **Memory**:
   - Dispose camera controller properly
   - Clear old detections periodically
   - Use image caching efficiently

## Deployment Checklist

- [ ] Android permissions configured
- [ ] iOS Info.plist updated
- [ ] Camera tested on physical devices
- [ ] Backend APIs implemented and tested
- [ ] Error handling in place
- [ ] Performance tested
- [ ] Privacy policy updated
- [ ] Release builds tested
- [ ] App signed and ready for store
