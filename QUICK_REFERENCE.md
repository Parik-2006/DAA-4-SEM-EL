# Quick Reference Guide

## 🚀 Getting Started (5 minutes)

### 1. Web Dashboard Development

```bash
# Terminal 1: Start Development Server
cd web-dashboard
npm install        # First time only
npm run dev       # http://localhost:5173
```

### 2. Backend Development

```bash
# Terminal 2: Start Backend API
cd attendance_backend (or your backend directory)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py    # http://localhost:8000
```

### 3. Test Connection

```
1. Open http://localhost:5173 in browser
2. Press F12 (Developer Console)
3. Navigate to Dashboard
4. Check "System Online" indicator
5. Check Network tab for API requests
6. Verify no 401 errors
```

---

## 📁 Key File Locations

| Purpose | Path |
|---------|------|
| Web Dashboard | `web-dashboard/` |
| Mobile App | `attendance_app/` |
| API Service | `web-dashboard/src/services/api.ts` |
| State Store | `web-dashboard/src/store/index.ts` |
| Components | `web-dashboard/src/components/` |
| Pages | `web-dashboard/src/pages/` |
| Environment Config | `web-dashboard/.env` |
| Deployment Guide | `web-dashboard/DEPLOYMENT_GUIDE.md` |
| API Reference | `FRONTEND_BACKEND_CONNECTION.md` |

---

## 🔧 Common Tasks

### Start Fresh Development

```bash
# Web Dashboard
cd web-dashboard
npm install
cp .env.example .env
# Edit .env: VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

### Build for Production

```bash
cd web-dashboard
npm run build
npm run preview  # Test production build locally
```

### Deploy to Render

```bash
# 1. Push to GitHub
git add .
git commit -m "Feature: add new feature"
git push origin main

# 2. Render auto-deploys from GitHub
# 3. Check Render dashboard for status
```

### Update Environment Variables

```bash
# Local Development
vim web-dashboard/.env
# Change: VITE_API_BASE_URL, VITE_POLLING_INTERVAL, etc

# Production (Render)
# 1. Go to Render dashboard
# 2. Select service > Environment
# 3. Update variables
# 4. Redeploy
```

### Fix API Connection Issues

```bash
# 1. Check backend is running
curl http://localhost:8000/api/v1/health

# 2. Check .env has correct URL
cat web-dashboard/.env | grep API

# 3. Check browser console (F12)
# - Look for network errors
# - Check 401 vs other errors

# 4. Verify CORS on backend
# - Backend must allow frontend domain
```

---

## 🎨 Styling Quick Reference

### Add New Component

```typescript
// components/MyComponent.tsx
import { Card, Button, Badge } from '@/components';

export const MyComponent = () => (
  <Card>
    <h2 className="text-xl font-bold text-gray-900">Title</h2>
    <p className="text-sm text-gray-600">Description</p>
    <Button variant="primary">Click Me</Button>
  </Card>
);
```

### Tailwind Utility Classes

```
Text: text-xs, text-sm, text-base, text-lg, text-xl, text-2xl, text-3xl
    text-gray-600, text-indigo-600, text-green-600 (color variants)
    font-semibold, font-bold, font-medium

Spacing: p-4 (padding), m-4 (margin), gap-2 (grid gap)
        px-4 (horizontal), py-2 (vertical)

Colors: bg-indigo-50, bg-green-100, text-red-600
        border-gray-200, border-indigo-100

Layout: flex, grid, grid-cols-3, gap-4
        flex-1 (flex grow), w-full, h-10

Responsive: sm:, md:, lg:, xl: (breakpoints)
           Example: grid-cols-1 md:grid-cols-2 lg:grid-cols-4
```

---

## 🔄 API Methods Quick Reference

```typescript
import { attendanceAPI } from '@/services/api';

// Get live attendance (updates every 5 seconds)
const records = await attendanceAPI.getLiveAttendance(courseId);

// Get statistics
const stats = await attendanceAPI.getAttendanceStats(courseId, date);

// Get history with filtering
const history = await attendanceAPI.getAttendanceHistory(
  courseId,
  startDate,
  endDate,
  page=1,
  limit=30
);

// Get summary stats
const summary = await attendanceAPI.getAttendanceSummary(
  courseId,
  startDate,
  endDate
);

// Get students list
const students = await attendanceAPI.getStudents(courseId);

// Get courses
const courses = await attendanceAPI.getCourses();

// Check system health
const health = await attendanceAPI.healthCheck();
```

---

## 🎯 State Management Reference

```typescript
import { useDashboardStore } from '@/store';

// Use in component
const { liveRecords, stats, setLiveRecords, setError } = useDashboardStore();

// Common actions
store.setSystemRunning(true);
store.setLastSyncTime(new Date());
store.setIsPolling(true);
store.setError(null);
store.setLiveRecords([...records]);
store.setStats(stats);
store.setCourses([...courses]);
store.setSelectedCourse(courseId);
store.setStudents([...students]);
```

---

## 📊 Component Examples

### StatCard

```typescript
<StatCard
  label="Present"
  value={45}
  color="success"  // success, warning, danger, info, primary
  icon={<Users size={24} />}
  trend={{ value: 5, isPositive: true }}  // Optional
/>
```

### Badge

```typescript
<Badge variant="success">Present</Badge>
<Badge variant="warning" size="sm">Late</Badge>
```

### Button

```typescript
<Button 
  variant="primary"    // primary, secondary, danger, ghost
  size="md"           // sm, md, lg
  isLoading={false}
  onClick={() => {}}
>
  Click Me
</Button>
```

### Card

```typescript
<Card className="optional-extra-classes">
  {/* Content */}
</Card>
```

---

## 🌐 Deployment Quick Reference

### Render Deployment

**First Time:**
1. Push repo to GitHub
2. Create Render account
3. Connect GitHub
4. Create Web Service
5. Set Build Command: `npm --prefix web-dashboard run build`
6. Set Start Command: `npm --prefix web-dashboard run preview`
7. Add Env Vars: `VITE_API_BASE_URL=https://your-backend`
8. Deploy

**Update Frontend:**
```bash
git push origin main
# Render auto-redeploys
```

**Update Env Vars:**
1. Go to Render dashboard
2. Service > Environment
3. Update VITE_API_BASE_URL
4. Redeploy

### Local Docker

```bash
# Build
docker build -t attendance-dashboard .

# Run
docker run -p 3000:3000 -e VITE_API_BASE_URL=http://your-api.com attendance-dashboard

# Or use compose
docker-compose up -d
```

---

## 🐛 Debugging Checklist

- [ ] Backend running? `curl http://localhost:8000/api/v1/health`
- [ ] .env file exists? `ls web-dashboard/.env`
- [ ] API_URL correct? `grep VITE_API_BASE_URL web-dashboard/.env`
- [ ] Dev server running? Check http://localhost:5173
- [ ] Network requests? F12 > Network tab
- [ ] Console errors? F12 > Console tab
- [ ] 401 errors? Check JWT token
- [ ] CORS error? Check backend CORS config
- [ ] Timeout? Check network latency

---

## 📚 Documentation Links

- **API Reference**: `FRONTEND_BACKEND_CONNECTION.md`
- **Deployment**: `web-dashboard/DEPLOYMENT_GUIDE.md`
- **Dashboard Setup**: `web-dashboard/README.md`
- **Project Overview**: `PROJECT_OVERVIEW.md`

---

## 💡 Tips & Tricks

### Speed Up Development

```bash
# Update single package
npm update react

# Check outdated packages
npm outdated

# Clear cache
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

### Debug API Calls

```typescript
// In any component
useEffect(() => {
  fetchData().then(d => {
    console.log('API Response:', d);
  }).catch(e => {
    console.error('API Error:', e);
  });
}, []);
```

### Check TypeScript

```bash
cd web-dashboard
npm run type-check  # If configured
# Or use VSCode: Problems panel
```

### Format Code

```bash
cd web-dashboard
npm run format      # If configured
# Or use Prettier directly:
npx prettier --write src/**/*.tsx
```

---

## 🎓 Learning Resources

- **React**: https://react.dev
- **TypeScript**: https://www.typescriptlang.org/docs
- **Tailwind**: https://tailwindcss.com/docs
- **Axios**: https://axios-http.com
- **Zustand**: https://github.com/pmndrs/zustand

---

## ⚡ Performance Tips

- Adjust `VITE_POLLING_INTERVAL` (5000 = 5 seconds)
- Use course filtering to reduce data
- Pagination for large datasets
- Browser DevTools Lighthouse for performance audit
- Check Network tab for slow requests

---

## 📞 Common Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| `Cannot GET /undefined` | API URL wrong | Set VITE_API_BASE_URL in .env |
| `401 Unauthorized` | Invalid/expired token | Check JWT token, re-login |
| `CORS error` | Backend CORS misconfigured | Update backend CORS headers |
| `Connection refused` | Backend not running | Start backend server |
| `Cannot find module @/...` | Path alias not working | Check tsconfig.json paths |
| `Polling not working` | Wrong interval | Check VITE_POLLING_INTERVAL |

---

## ✅ Pre-Launch Checklist

Before deploying to production:

- [ ] Test all pages load without errors
- [ ] API endpoints respond correctly
- [ ] No 401/403 errors in production
- [ ] CORS configured properly
- [ ] Environment variables set in Render
- [ ] Backend health check passing
- [ ] Statistics display correctly
- [ ] Filtering/search works
- [ ] Pagination works
- [ ] CSV export works
- [ ] Responsive design on mobile

---

**Last Updated:** January 2024
**Version:** 1.0.0

Keep this handy! 📌
