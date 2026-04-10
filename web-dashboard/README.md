# Web Dashboard Setup Instructions

## 🚀 Project Overview

This is a complete **React + TypeScript + Tailwind CSS** web dashboard for the Smart Attendance System. It provides real-time monitoring of attendance, student management, and historical records with a modern SaaS interface.

### Key Features

✅ **Real-time Attendance Dashboard** - Live check-in tracking with auto-refresh
✅ **Attendance History** - Advanced search, filtering, and date range selection
✅ **Student Management** - View and filter students by course
✅ **System Monitoring** - Online/offline status indicator
✅ **Responsive Design** - Works on desktop, tablet, and mobile
✅ **Type-Safe** - Full TypeScript support with Zod schemas
✅ **Production Ready** - Optimized build with Vite

---

## 📁 Project Structure

```
web-dashboard/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── UI.tsx          # Button, Card, Badge, StatCard
│   │   ├── Layout.tsx      # Main layout with sidebar
│   │   ├── Cards.tsx       # AttendanceRecordCard, Table
│   │   └── index.ts        # Component exports
│   │
│   ├── pages/              # Page components
│   │   ├── DashboardPage.tsx      # Main dashboard
│   │   ├── HistoryPage.tsx        # History with filtering
│   │   ├── StudentsPage.tsx       # Student list
│   │   ├── SettingsPage.tsx       # Settings
│   │   └── index.ts
│   │
│   ├── services/           # API communication
│   │   ├── api.ts          # Axios client + TypeScript interfaces
│   │   └── types.ts        # Type definitions (if needed)
│   │
│   ├── store/              # State management (Zustand)
│   │   └── index.ts        # Global app state
│   │
│   ├── App.tsx             # Main app component with routing
│   ├── main.tsx            # Entry point
│   └── index.css           # Global styles & Tailwind
│
├── public/                 # Static assets
├── index.html             # HTML template
├── vite.config.ts         # Vite configuration
├── tsconfig.json          # TypeScript configuration
├── tailwind.config.js     # Tailwind CSS configuration
├── postcss.config.js      # PostCSS configuration
├── package.json           # Dependencies
├── .env                   # Environment variables
├── .env.example           # Environment template
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Docker Compose
├── render.yaml            # Render deployment config
├── DEPLOYMENT_GUIDE.md    # Detailed deployment steps
└── README.md              # This file
```

---

## 🔧 Installation & Setup

### Prerequisites

- **Node.js** 18+ ([Download](https://nodejs.org))
- **npm** or **yarn** (comes with Node.js)
- **Backend API** running (FastAPI server at port 8000)
- **Git** for version control

### Step 1: Install Dependencies

```bash
cd web-dashboard
npm install
```

This installs all packages from `package.json`:
- React 18.2
- React Router 6.11
- TypeScript 5.0
- Tailwind CSS 3.3
- Axios 1.4
- Zustand 4.3
- Lucide Icons
- And more...

### Step 2: Environment Configuration

```bash
# Create .env file
cp .env.example .env

# Edit .env with your configuration
```

**Development Configuration (.env):**
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_TIMEOUT=15000
VITE_POLLING_INTERVAL=5000
```

**Production Configuration (.env - Render):**
```env
VITE_API_BASE_URL=https://your-backend-api.onrender.com
VITE_API_TIMEOUT=15000
VITE_POLLING_INTERVAL=5000
```

### Step 3: Start Development Server

```bash
npm run dev
```

Output:
```
  VITE v4.3.0  ready in 456 ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

Open http://localhost:5173 in your browser

---

## 📊 Component Architecture

### UI Components (`components/UI.tsx`)

**Card**
```typescript
<Card>
  <h3>Card Title</h3>
  <p>Card content</p>
</Card>
```

**StatCard**
```typescript
<StatCard
  label="Present"
  value={45}
  color="success"
  icon={<Users size={24} />}
/>
```

**Button**
```typescript
<Button variant="primary" size="md" isLoading={false}>
  Click Me
</Button>
```

Variants: `primary`, `secondary`, `danger`, `ghost`
Sizes: `sm`, `md`, `lg`

**Badge**
```typescript
<Badge variant="success" size="sm">Present</Badge>
```

### Layout Component (`components/Layout.tsx`)

Provides:
- Responsive sidebar navigation
- Top header with system status
- System status indicator (green/red dot)
- Last sync time display
- User profile area

### Page Components (`pages/`)

#### 1. Dashboard Page
- Real-time attendance statistics
- Live check-in list with avatars
- Course filtering
- Auto-refresh every 5 seconds
- System status indicator

#### 2. History Page
- Advanced search (name/ID)
- Date range filtering
- Course filtering
- Pagination (30 records per page)
- Export to CSV

#### 3. Students Page
- Student list with avatars
- Search by name/ID/email
- Course filtering
- Summary statistics

#### 4. Settings Page
- API URL configuration
- Polling interval adjustment
- Theme selection (light/dark)
- Notification preferences
- Application info

---

## 🔄 State Management (Zustand)

Global state stored in `store/index.ts`:

```typescript
useDashboardStore.getState() returns:
{
  // System Status
  systemRunning: boolean,
  lastSyncTime: Date | null,
  isPolling: boolean,
  error: string | null,

  // Data
  liveRecords: AttendanceRecord[],
  stats: AttendanceStats | null,
  students: Student[],
  courses: Course[],
  selectedCourse: string | null,

  // UI
  showSuccess: boolean,
  successMessage: string,

  // Actions (to update state)
  setSystemRunning, setLastSyncTime, setIsPolling, setError,
  setLiveRecords, setStats, setStudents, setCourses,
  setSelectedCourse, showSuccessNotification
}
```

**Usage in Components:**
```typescript
const { liveRecords, setLiveRecords } = useDashboardStore();
```

---

## 🌐 API Integration

### Axios Client (`services/api.ts`)

**TypeScript Interfaces:**
```typescript
AttendanceRecord - Single attendance entry
AttendanceStats - Aggregated statistics
Student - Student information
Course - Course information
```

**Methods:**
```typescript
attendanceAPI.getLiveAttendance(courseId?, limit=50)
attendanceAPI.getAttendanceStats(courseId?, date?)
attendanceAPI.getAttendanceHistory(courseId?, startDate?, endDate?, page=1, limit=30)
attendanceAPI.getAttendanceSummary(courseId?, startDate?, endDate?)
attendanceAPI.getStudents(courseId?)
attendanceAPI.getCourses()
attendanceAPI.healthCheck()
```

**Error Handling:**
- Automatic 401 error handling
- Token injection from localStorage
- 15-second timeout
- Console logging for debugging

---

## 🎨 Styling

### Tailwind CSS Configuration

**Custom Colors:**
```javascript
Primary: #4F46E5 (Indigo)
Success: #10B981 (Green)
Warning: #F59E0B (Amber)
Danger: #EF4444 (Red)
Info: #3B82F6 (Blue)
```

**Font:**
- Primary: Sora (imported from Google Fonts via Tailwind)
- Fallback: system-ui

**Responsive Breakpoints:**
```
sm: 640px
md: 768px
lg: 1024px
xl: 1280px
```

### Global Styles (`index.css`)

- Custom scrollbar styling
- Animation keyframes (`fadeIn`, `loading`)
- Component utility classes
- Smooth transitions

---

## 🚀 Build & Production

### Build for Production

```bash
npm run build
```

Output:
```
dist/
├── index.html
├── assets/
│   ├── index-xxxxx.js      # Minified & bundled JS
│   └── index-xxxxx.css     # Minified & bundled CSS
```

### Preview Production Build

```bash
npm run preview
# Serves dist/ folder on http://localhost:4173
```

### Build Optimization

- **Code Splitting**: Each page loads only needed code
- **Tree Shaking**: Unused code removed
- **Minification**: All files compressed
- **Asset Optimization**: Images optimized
- **CSS Purging**: Unused Tailwind removed

---

## 🐳 Docker Deployment

### Build Docker Image

```bash
docker build -t attendance-dashboard .
```

### Run Container

```bash
docker run -p 3000:3000 \
  -e VITE_API_BASE_URL=http://your-api.com \
  attendance-dashboard
```

### Docker Compose

```bash
docker-compose up -d
# Dashboard accessible at http://localhost:3000
```

---

## 📤 Render Deployment

See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) for complete instructions.

**Quick Render Steps:**
1. Push code to GitHub
2. Create Render account
3. Connect GitHub repository
4. Set build command: `npm --prefix web-dashboard run build`
5. Set start command: `npm --prefix web-dashboard run preview`
6. Add environment variables
7. Deploy

**Result:** https://attendance-dashboard.onrender.com

---

## 🔗 Frontend-Backend Connection

See [FRONTEND_BACKEND_CONNECTION.md](../FRONTEND_BACKEND_CONNECTION.md) for:
- API endpoint reference
- Request/response formats
- Error handling
- Production configuration
- Troubleshooting

---

## 🧪 Development Workflow

### Development Process

1. **Create feature branch**
   ```bash
   git checkout -b feature/new-feature
   ```

2. **Make changes and test**
   ```bash
   npm run dev
   # Test in browser at http://localhost:5173
   ```

3. **Format and lint** (optional)
   ```bash
   npm run lint    # Check for issues
   npm run format  # Format code
   ```

4. **Build and test production**
   ```bash
   npm run build
   npm run preview
   ```

5. **Commit and push**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   git push origin feature/new-feature
   ```

6. **Create Pull Request on GitHub**

---

## 🐛 Debugging

### Browser DevTools

1. Open Developer Console (F12)
2. **Console Tab**: Check for errors/warnings
3. **Network Tab**: Monitor API requests
4. **React DevTools**: Inspect component state (install extension)
5. **Storage Tab**: Check localStorage for tokens/settings

### Common Issues

**Issue: "Cannot find module"**
- Run `npm install`
- Check import paths

**Issue: "VITE_API_BASE_URL is undefined"**
- Create `.env` file
- Restart dev server

**Issue: API requests fail**
- Check backend is running
- Verify API URL in .env
- Check CORS configuration

---

## 📚 Technologies Used

| Technology | Purpose |
|-----------|---------|
| React 18.2 | UI framework |
| TypeScript 5.0 | Type safety |
| Vite 4.3 | Build tool |
| React Router 6.11 | Navigation |
| Tailwind CSS 3.3 | Styling |
| Axios 1.4 | HTTP client |
| Zustand 4.3 | State management |
| Lucide Icons | Icons |

---

## 📖 Useful Commands

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Type check
npm run type-check

# Format code (if configured)
npm run format

# Lint code (if configured)
npm run lint
```

---

## 🎯 Next Steps

1. ✅ **Environment Setup** - Configure .env
2. ✅ **Local Development** - Run `npm run dev`
3. ✅ **Test Backend Connection** - Verify API calls work
4. ⏳ **Production Build** - Run `npm run build`
5. ⏳ **Deploy on Render** - Follow DEPLOYMENT_GUIDE.md
6. ⏳ **Configure Custom Domain** - Add your domain
7. ⏳ **Monitor Performance** - Check logs and metrics

---

## 📞 Support & Resources

- **React Documentation**: https://react.dev
- **TypeScript Handbook**: https://www.typescriptlang.org/docs
- **Tailwind CSS**: https://tailwindcss.com/docs
- **Vite Guide**: https://vitejs.dev/guide
- **Render Docs**: https://render.com/docs

---

## 📝 Notes

- This dashboard is designed to work with the FastAPI backend
- Polling interval can be adjusted in Settings page (1-60 seconds)  
- All timestamps are in ISO 8601 format
- User credentials stored in localStorage (consider httpOnly cookies for production)
- CORS must be properly configured on backend

---

**Happy Coding! 🎉**

For issues or improvements, please check the logs and troubleshooting section above.
