# Smart Attendance — Flutter App

A production-ready Flutter mobile application for the Smart Attendance System.
Designed to connect seamlessly with a **FastAPI** backend.

---

## 📁 Project Structure

```
lib/
├── main.dart                     # Entry point — Riverpod + GoRouter
├── theme/
│   └── app_theme.dart            # Full Material 3 theme, colors, spacing
├── models/
│   ├── user_model.dart           # User, UserRole
│   ├── attendance_model.dart     # AttendanceModel, AttendanceSummary
│   └── course_model.dart        # CourseModel, ScheduleSlot, AuthTokenModel
├── services/
│   ├── api_service.dart          # Dio client, interceptors, ApiException
│   ├── auth_service.dart         # Login, register, logout, token refresh
│   └── attendance_service.dart   # Attendance CRUD + QR marking
├── providers/
│   ├── auth_provider.dart        # AuthState + AuthNotifier (Riverpod)
│   └── attendance_provider.dart  # Courses, summary, QR marking providers
├── router/
│   └── app_router.dart           # GoRouter with auth guards + transitions
├── screens/
│   ├── splash_screen.dart
│   ├── auth/
│   │   ├── login_screen.dart
│   │   └── register_screen.dart
│   ├── shell/
│   │   └── main_shell.dart       # Bottom nav shell
│   ├── home/
│   │   └── home_screen.dart      # Dashboard with stats
│   ├── attendance/
│   │   ├── attendance_screen.dart
│   │   └── qr_scan_screen.dart   # QR scanner (MobileScanner ready)
│   ├── history/
│   │   └── history_screen.dart
│   └── profile/
│       └── profile_screen.dart
├── components/
│   ├── app_text_field.dart       # Reusable validated text field
│   ├── primary_button.dart       # Full-width CTA with loading state
│   ├── attendance_stat_card.dart
│   ├── course_card.dart
│   └── section_header.dart
└── utils/
    ├── app_constants.dart
    └── date_utils.dart
```

---

## 🚀 Getting Started

### 1. Prerequisites

- Flutter SDK ≥ 3.0.0
- Dart SDK ≥ 3.0.0
- Android Studio / Xcode

### 2. Install dependencies

```bash
flutter pub get
```

### 3. Configure backend URL

Edit `lib/services/api_service.dart`:

```dart
// Android emulator → FastAPI on localhost
static const String devBaseUrl = 'http://10.0.2.2:8000';

// Physical device → your machine's IP on the same network
static const String devBaseUrl = 'http://192.168.1.100:8000';

// Production
static const String prodBaseUrl = 'https://api.yourattendance.com';
```

### 4. Run the app

```bash
flutter run
```

---

## 🔌 FastAPI Backend — Expected Endpoints

### Authentication (`/api/v1/auth`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/login` | OAuth2 form login → returns JWT |
| `POST` | `/register` | Create student account |
| `GET` | `/me` | Get current user profile |
| `POST` | `/refresh` | Refresh access token |
| `POST` | `/logout` | Invalidate token |

**Login request format** (OAuth2 form data):
```
Content-Type: application/x-www-form-urlencoded
username=user@email.com&password=secret
```

**Login response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600,
  "refresh_token": "eyJ..."
}
```

### Courses (`/api/v1/courses`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/enrolled` | Student's enrolled courses |
| `GET` | `/{id}/attendance` | Attendance for a course (teacher) |

**Course response:**
```json
{
  "id": "uuid",
  "name": "Data Structures",
  "code": "CS301",
  "teacher_name": "Dr. Smith",
  "department": "Computer Science",
  "credits": 3,
  "schedule": [
    { "day_of_week": "Monday", "start_time": "09:00", "end_time": "10:30", "room": "LT-4" }
  ],
  "total_students": 45,
  "is_active": true
}
```

### Attendance (`/api/v1/attendance`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/me` | Student's attendance records |
| `GET` | `/me/summary` | Overall stats (present/absent counts) |
| `POST` | `/mark` | Manual attendance mark |
| `POST` | `/mark-qr` | QR code attendance marking |
| `POST` | `/generate-qr` | Generate session QR (teacher) |

**Summary response:**
```json
{
  "total_classes": 45,
  "present_count": 38,
  "absent_count": 5,
  "late_count": 2,
  "excused_count": 0
}
```

**QR mark request:**
```json
{
  "qr_token": "SESSION_TOKEN_HERE",
  "device_id": "optional-device-id",
  "scanned_at": "2024-01-15T10:30:00Z"
}
```

---

## 📱 Enabling QR Camera Scanner

In `lib/screens/attendance/qr_scan_screen.dart`, replace the placeholder with:

```dart
import 'package:mobile_scanner/mobile_scanner.dart';

// Replace the Container placeholder with:
MobileScanner(
  onDetect: (capture) {
    final barcode = capture.barcodes.firstOrNull;
    if (barcode?.rawValue != null) {
      _onQrDetected(barcode!.rawValue!);
    }
  },
),
```

**Android** — Add to `android/app/src/main/AndroidManifest.xml`:
```xml
<uses-permission android:name="android.permission.CAMERA"/>
```

**iOS** — Add to `ios/Runner/Info.plist`:
```xml
<key>NSCameraUsageDescription</key>
<string>Camera is used to scan QR codes for attendance.</string>
```

---

## 🏗️ State Management (Riverpod)

```
authProvider        → AuthState (loading / authenticated / unauthenticated / error)
currentUserProvider → UserModel? (derived from authProvider)
myCoursesProvider   → AsyncValue<List<CourseModel>>
attendanceSummaryProvider → AsyncValue<AttendanceSummary>
myAttendanceProvider → AsyncValue<List<AttendanceModel>>
qrMarkingProvider   → QrMarkingState (loading / success / error)
```

---

## 🎨 Design System

- **Fonts**: Sora (UI text) + JetBrains Mono (IDs, codes)
- **Primary**: Indigo `#4F46E5`
- **Secondary**: Emerald `#10B981`
- **Material 3** with full light + dark theme support
- Custom bottom nav, animated transitions, shimmer skeletons

---

## 📦 Key Dependencies

| Package | Purpose |
|---------|---------|
| `flutter_riverpod` | State management |
| `go_router` | Declarative routing + auth guards |
| `dio` | HTTP client with interceptors |
| `flutter_secure_storage` | JWT token storage |
| `mobile_scanner` | QR code camera scanning |
| `qr_flutter` | QR code generation (teacher view) |
| `intl` | Date/time formatting |
| `shimmer` | Loading skeleton UI |
