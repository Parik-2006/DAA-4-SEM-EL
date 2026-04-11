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

⚡ WDS Scheduling Engine (Weighted Dynamic Scoring)
A Next-Generation Non-Preemptive CPU Scheduler. Designed for High-Performance Computing, Cloud Clusters, and Autonomous Systems.

📖 Project Objective
Modern computing environments (like 5G Edge Gateways and AI Training Clusters) suffer from inefficiencies when using standard CPU schedulers:

FCFS (First-Come-First-Serve): causes the "Convoy Effect" (UI freezes behind background tasks).
SJF (Shortest Job First): causes "Starvation" (Long tasks never run).
The Solution: The Weighted Dynamic Score (WDS) algorithm. It utilizes a Cooperative Multitasking Architecture where tasks yield control at specific checkpoints. The scheduler calculates a dynamic score based on Efficiency, Fairness, and Priority to decide the next task.

⚙️ The WDS Formula
The engine calculates a score (S) for every waiting process in real-time:

S = (Wwait × Twaiting) + (Wburst × 30/Tburst) + (Wprio × Plevel)

Wwait (Aging Factor): Prevents starvation by boosting the score of waiting tasks.
Wburst (Efficiency): Favors short jobs to reduce system latency.
Wprio (Urgency): Allows critical operations (e.g., "Emergency Braking") to override standard logic.

🌍 Real-World Scenarios
This project simulates WDS performance in four specific industries:

| Industry         | The Problem                                 | The WDS Solution                                 |
|------------------|---------------------------------------------|--------------------------------------------------|
| 🤖 AI Clusters   | Long training epochs block checkpoint saves.| Yield Points: WDS pauses training to run quick saves. |
| 📡 5G Edge       | 4K video streams block health alert packets.| Packet Yielding: Emergency packets get priority override. |
| 🚗 Autonomous OS | Map downloads block Lidar obstacle detection.| Context Switch: Lidar gets instant CPU access.    |
| ☁️ Cloud Functions | Cold starts delay user login requests.     | Aging Factor: Login requests gain score while waiting. |

🛠️ Tech Stack
Backend: Python (Flask)
Algorithm: Weighted Dynamic Scoring (Custom Heuristic)
Frontend: HTML5, CSS3, JavaScript (Fetch API)
Visualization: Chart.js (for Latency Graphs)

🚀 How to Run Locally
Clone the Repository

```bash
}
cd wds-scheduler
```
Install Dependencies

```bash
pip install -r requirements.txt
```
Run the Server

```bash
python app.py
```
Open in Browser Visit http://127.0.0.1:5000

☁️ Deployment
This project is deployed on Vercel.

1. Push code to GitHub.
2. Import repository into Vercel.
3. Vercel automatically detects the Python runtime via vercel.json.

📄 License
This project is for educational research purposes.

🤝 Contributing & Issues
This project is open for viewing. Direct changes are restricted.

Found a bug? Please Open a New Issue and describe the problem.
Want to fix it? Please Fork the repo and submit a Pull Request (PR) for review.
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
