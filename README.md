# Smart Attendance System ⚡
A Next-Generation Real-Time Face Recognition Attendance Platform for Modern Institutions

## 📖 Project Objective
Traditional attendance systems are slow, error-prone, and not scalable for large organizations. The Smart Attendance System leverages AI-powered face recognition and a modern web/mobile stack to deliver:

- Automated, contactless attendance marking
- Real-time dashboards for monitoring and analytics
- Seamless integration with cloud databases and scalable APIs

## ⚙️ System Architecture
The platform consists of three main components:

| Component         | Technology Stack                | Description |
|-------------------|---------------------------------|-------------|
| Backend API       | Python, FastAPI, YOLOv8, FaceNet, FAISS, Firebase | Real-time face detection, recognition, and attendance logic |
| Web Dashboard     | React, TypeScript, Tailwind CSS, Zustand, Chart.js | Admin dashboard for live monitoring, history, and management |
| Mobile App        | Flutter, Dart                   | Student/teacher app for QR and face-based attendance |

### Backend Overview
- **Face Detection**: YOLOv8 for fast, accurate detection
- **Face Recognition**: FaceNet embeddings, FAISS for similarity search
- **Data Storage**: Firebase Realtime Database
- **API**: FastAPI async endpoints for high throughput

### Dashboard Overview
- **Live Attendance**: Real-time check-in/out, status indicators
- **History & Analytics**: Search, filter, and visualize attendance data
- **Student Management**: Add, edit, and view student/course info

## 🌍 Real-World Scenarios
| Scenario                | Problem                                   | Our Solution |
|-------------------------|-------------------------------------------|--------------|
| Large Classrooms        | Manual roll-call is slow and error-prone  | Face recognition automates and speeds up process |
| Remote/Hybrid Learning  | Attendance fraud (proxy attendance)       | Liveness detection and unique face matching |
| Health & Safety         | Contact-based systems risk disease spread | Contactless, camera-based check-in |
| Analytics & Compliance  | No insights from paper records            | Dashboard with analytics and export features |

## 🛠️ Tech Stack
- **Backend**: Python, FastAPI, YOLOv8, FaceNet, FAISS, Firebase
- **Frontend**: React, TypeScript, Tailwind CSS, Zustand, Chart.js
- **Mobile**: Flutter, Dart

## 🚀 How to Run Locally

### Backend
```bash
cd attendance_backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit .env as needed
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Web Dashboard
```bash
cd web-dashboard
npm install
npm run dev
# Visit http://localhost:5173
```

### Mobile App
```bash
cd attendance_app
flutter pub get
flutter run
```

## ☁️ Deployment
- Backend: Deployable via Docker, cloud VM, or serverless
- Dashboard: Vercel, Netlify, or any static host
- Mobile: Android/iOS app stores

## 📄 License
This project is for educational and research purposes.

## 🤝 Contributing & Issues
Open for viewing and learning. For issues, open a GitHub issue. For contributions, fork and submit a PR for review.