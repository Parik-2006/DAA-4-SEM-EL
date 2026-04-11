# Smart Attendance System (SAT)

A complete end-to-end attendance tracking system with facial recognition, featuring a **Python FastAPI backend**, **React web dashboard**, and **Flutter mobile app**.

---

## 📋 Quick Start

This project has **three independent components** running simultaneously:

1. **Backend API** (Python/FastAPI) - Port 8000
2. **Web Dashboard** (React/Vite) - Port 3000  
3. **Flutter App** (Web/Multi-platform) - Chrome/Web browsers

All can run locally on `localhost` with hot-reload support.

---

## 🔧 Prerequisites

- **Python 3.11+** ([Download](https://www.python.org/downloads/))
- **Node.js 18+** ([Download](https://nodejs.org/))
- **Flutter SDK** ([Download](https://flutter.dev/docs/get-started/install))
- **Docker & Docker Compose** ([Download](https://www.docker.com/products/docker-desktop))
- **Git** (for version control)

### Verify Installation
```bash
python --version        # Python 3.11+
node --version         # Node.js 18+
npm --version          # npm 9+
flutter --version      # Flutter 3.0+
dart --version         # Dart (comes with Flutter)
docker --version       # Docker 20+
docker compose version # Docker Compose 2+
```

---

## 📁 Project Structure

```
P:\DAA LAB EL\
├── attendance_backend/      # FastAPI + ML models
│   ├── main.py
│   ├── requirements.txt
│   ├── docker-compose.yml
│   └── Dockerfile
├── web-dashboard/           # React + Vite
│   ├── package.json
│   ├── src/
│   └── index.html
└── attendance_app/          # Flutter multi-platform
    ├── lib/
    ├── pubspec.yaml
    └── (platform folders: web/, windows/, android/, etc.)
```

---

## 🚀 Setup & Run

### **1️⃣ Backend API (FastAPI)**

**Option A: Using Docker (Recommended)**
```bash
cd attendance_backend
docker compose up -d --build
```
- Container starts on **http://localhost:8000**
- API docs available at **http://localhost:8000/docs** (Swagger UI)

**Option B: Local Python Setup**
```bash
cd attendance_backend
python -m venv venv
source venv/Scripts/Activate.ps1  # On Windows PowerShell
pip install -r requirements.txt
python main.py
```

---

### **2️⃣ Web Dashboard (React)**

```bash
cd web-dashboard
npm install
npm run dev
```
- Server starts on **http://localhost:3000**
- Hot reload enabled - changes reflect instantly

**Build for Production:**
```bash
npm run build  # Creates optimized build in dist/
```

---

### **3️⃣ Flutter App (Mobile/Web)**

#### **Option A: Web Browser (Recommended for Development)**
```bash
cd attendance_app
flutter pub get
flutter run -d chrome
```
- App launches in Chrome with DevTools
- **Hot reload**: Press `r` in terminal
- **Hot restart**: Press `R` in terminal
- **Quit**: Press `q` in terminal

#### **Option B: Desktop (Windows)**
```bash
cd attendance_app
flutter run -d windows
```

#### **Option C: List Available Devices**
```bash
flutter devices  # See all connected devices and simulators
flutter emulators --launch <emulator_id>  # Launch Android emulator
flutter run -d chrome   # Then run on your choice
```

#### **Other Platforms**
```bash
flutter run -d edge              # Microsoft Edge
flutter run -d android-chrome    # Android Chrome
# Or any connected device from `flutter devices`
```

---

## 🔗 API Endpoints

Once backend is running, access the API:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### Common Endpoints
```
POST   /api/v1/auth/login              # User login
POST   /api/v1/auth/register           # User registration
POST   /api/v1/auth/logout             # Logout
GET    /api/v1/auth/me                 # Get current user
POST   /api/v1/attendance/mark         # Mark attendance
GET    /api/v1/attendance/history      # Get attendance history
POST   /api/v1/attendance/face-verify  # Verify face for attendance
```

---

## 🎯 Full System Launch

**Terminal 1 - Backend:**
```bash
cd P:\DAA LAB EL\attendance_backend
docker compose up --build
```

**Terminal 2 - Dashboard:**
```bash
cd P:\DAA LAB EL\web-dashboard
npm run dev
```

**Terminal 3 - Mobile App:**
```bash
cd P:\DAA LAB EL\attendance_app
flutter run -d chrome
```

Once all three are running, you'll have:
- 🔌 **API** running on http://localhost:8000
- 🌐 **Dashboard** running on http://localhost:3000
- 📱 **Mobile App** running in your browser

---

## 🛠️ Development Workflow

### Hot Reload (Flutter)
After modifying Flutter code, press `r` in the terminal to instantly reload without losing state.

### Hot Reload (React/Vite)
Changes to React components automatically reload in the browser.

### Debugging

**Flutter DevTools:**
- Automatically opens in your browser when running `flutter run`
- Inspect widgets, view performance, debug

**React DevTools:**
- Install [React Developer Tools](https://chrome.google.com/webstore/detail/react-developer-tools/) browser extension
- Use browser DevTools (F12) for console/network debugging

**API Debugging:**
- Use [Postman](https://www.postman.com/) to test endpoints
- Visit http://localhost:8000/docs for interactive Swagger UI
- Check backend logs: `docker logs attendance-backend`

---

## 📦 Key Dependencies

**Backend:**
- FastAPI 0.104.1
- PyTorch 2.1.0 (ML models)
- OpenCV 4.8.0 (image processing)
- Firebase Admin SDK (authentication)
- Pydantic (data validation)

**Dashboard:**
- React 18
- Vite 4.5
- Tailwind CSS
- Riverpod (state management)
- Lucide React (icons)

**Mobile App:**
- Flutter 3.41.6
- Dart 3.11.4
- Flutter Riverpod (state management)
- go_router (navigation)
- mobile_scanner (QR code)
- dio (HTTP client)

---

## ⚙️ Configuration

### Backend Environment Variables
Create `.env` in `attendance_backend/`:
```env
FIREBASE_DATABASE_URL=your_firebase_url
DEBUG=True
LOG_LEVEL=INFO
```

### API Base URL (Flutter/Dashboard)
The apps default to `http://localhost:8000` for backend communication.

To change, edit:
- **Flutter**: `attendance_app/lib/services/api_service.dart` → `ApiConfig.baseUrl`
- **React**: `web-dashboard/src/services/api.ts` → `API_BASE_URL`

---

## 🧪 Testing

**Backend Tests:**
```bash
cd attendance_backend
pytest tests/
```

**Flutter Tests:**
```bash
cd attendance_app
flutter test
```

---

## 🐛 Troubleshooting

### Port Already in Use
```bash
# Find process using port
netstat -ano | findstr :8000    # Backend
netstat -ano | findstr :3000    # Dashboard

# Kill process
taskkill /PID <PID> /F
```

### Flutter Build Issues
```bash
flutter clean
flutter pub get
flutter run -d chrome
```

### Docker Build Fails
```bash
docker system prune -a  # Remove old images
docker compose down
docker compose up -d --build
```

### Dependencies Won't Install
```bash
# Clear caches
rm -r node_modules package-lock.json  (Dashboard)
flutter pub cache clean                 (Flutter)
pip cache purge                         (Backend)

# Reinstall
npm install / flutter pub get / pip install -r requirements.txt
```

---

## 📚 Documentation

- **Backend API Docs**: http://localhost:8000/docs
- **Flutter Documentation**: https://flutter.dev/docs
- **React Documentation**: https://react.dev
- **FastAPI Guide**: https://fastapi.tiangolo.com/

---

## 📝 License

This project is part of the DAA Lab curriculum. Modify and distribute as needed.

---

## 🤝 Support

For issues or questions:
1. Check the **Troubleshooting** section above
2. Review API docs at http://localhost:8000/docs
3. Check Flutter DevTools for mobile app issues
4. Review browser console for dashboard issues

---

**Last Updated:** April 11, 2026  
**Status:** Production Ready ✅
