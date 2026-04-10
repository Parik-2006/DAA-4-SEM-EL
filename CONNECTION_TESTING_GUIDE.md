# 🧪 Connection Testing & Verification Guide

## Quick Test Checklist

Use this guide to verify all connections are working before deploying.

---

## ✅ TEST 1: Backend Health Check

### Without Tools (Plain Terminal)
```bash
# Windows
curl http://localhost:8000/health

# Expected Response:
{
  "status": "healthy",
  "uptime": 1234,
  "version": "1.0.0"
}
```

### Using Python
```bash
python -m pip install requests
python -c "
import requests
try:
    r = requests.get('http://localhost:8000/health', timeout=5)
    print(f'Status: {r.status_code}')
    print(f'Response: {r.json()}')
except Exception as e:
    print(f'ERROR: {e}')
"
```

### Using Postman
1. Open Postman
2. Create new GET request
3. URL: `http://localhost:8000/health`
4. Click Send
5. Should get 200 response

**✅ PASS** if response is `{"status": "healthy"}`  
**❌ FAIL** if connection refused → Backend not running

---

## ✅ TEST 2: Web Dashboard Connection

### Step 1: Start Dashboard
```bash
cd web-dashboard
npm install   # First time only
npm run dev
```

### Step 2: Open in Browser
```
URL: http://localhost:5173
```

### Step 3: Check Connection
- Look for **green indicator** at top (if implemented)
- Open **DevTools** (F12)
- Go to **Network** tab
- Trigger a dashboard refresh (F5)
- Look for `GET /api/v1/health` request
- Should see **200 OK** response

### Step 4: Verify Data Loading
- Dashboard should show stats (Present, Late, Absent, Excused)
- Attendance records should displayed
- No error messages in console

**✅ PASS** if dashboard loads data from backend  
**❌ FAIL** if stuck on loading or shows connection error

---

## ✅ TEST 3: Flutter App Connection

### For Android Emulator
```bash
# Terminal 1: Start backend
cd attendance_backend
python main.py

# Terminal 2: Start app
cd attendance_app
flutter pub get
flutter run -d emulator-5554  # or your emulator ID
```

### For Physical Device
1. Get your PC IP:
   ```bash
   # Windows
   ipconfig | findstr "IPv4"
   
   # Output example: 192.168.1.100
   ```

2. Update Flutter app base URL:
   ```dart
   // lib/services/api_service.dart
   static const String devBaseUrl = 'http://192.168.1.100:8000';
   ```

3. Run app on device:
   ```bash
   flutter run
   ```

### Verify Connection
- App should launch without errors
- Can login with backend credentials
- Dashboard shows attendance stats
- No "Connection Failed" messages

**✅ PASS** if app successfully authenticates  
**❌ FAIL** if login fails or network error

---

## ✅ TEST 4: API Endpoint Testing

### Using Postman Collection
1. Import: `attendance_backend/Attendance_API.postman_collection.json`
2. Set variables:
   - `base_url`: `http://localhost:8000`
   - `token`: (Get from login response)
3. Run each endpoint

### Manual Testing with Curl

**Test: Get Health Status**
```bash
curl -X GET http://localhost:8000/health
```

**Test: Get Live Attendance**
```bash
curl -X GET "http://localhost:8000/api/v1/attendance/live" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json"
```

**Test: Get Students**
```bash
curl -X GET "http://localhost:8000/api/v1/students" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Test: Get Courses**
```bash
curl -X GET "http://localhost:8000/api/v1/courses" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

---

## ✅ TEST 5: Authentication Flow

### Get JWT Token

**Via Postman:**
```
Method: POST
URL: http://localhost:8000/api/v1/auth/login
Body (raw JSON):
{
  "username": "admin",
  "password": "admin123"
}
```

**Via Curl:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

**Expected Response:**
```json
{
  "access_token": "eyJhbG...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Use Token in Request
```bash
TOKEN="eyJhbG..."

curl -X GET http://localhost:8000/api/v1/attendance/live \
  -H "Authorization: Bearer $TOKEN"
```

**✅ PASS** if you get 200 with data  
**❌ FAIL** if you get 401 (unauthorized)

---

## ✅ TEST 6: CORS Configuration

### Test CORS Headers
```bash
# Make request from dashboard (http://localhost:5173)
curl -X OPTIONS http://localhost:8000/api/v1/health \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: GET" \
  -v
```

### Check Response Headers
Should include:
```
Access-Control-Allow-Origin: http://localhost:5173
Access-Control-Allow-Methods: *
Access-Control-Allow-Headers: *
```

**✅ PASS** if CORS headers are present  
**❌ FAIL** if missing (won't affect same-origin requests)

---

## ✅ TEST 7: Database Connection (Firebase)

### Check Firebase Initialization
Look in backend console output:
```
✓ Firebase initialized successfully
```

OR
```
⚠️ Firebase credentials path not configured
Operating without Firebase (data won't be persisted)
```

### Test Firestore Connection
```bash
python -c "
from services.firebase_service import initialize_firebase
initialize_firebase('config/firebase-credentials.json')
print('✓ Firebase connected')
"
```

**✅ PASS** if no errors and data persists  
**❌ FAIL** if Firebase not initialized (optional for dev, needed for prod)

---

## ✅ TEST 8: Performance/Load Testing

### Dashboard Polling Test
1. Open dashboard at `http://localhost:5173`
2. Open DevTools → Performance tab
3. Record for 10 seconds
4. Check:
   - Non-blocking requests (Network tab)
   - Smooth UI updates
   - No memory leaks
   - Consistent 5-second polling interval

### Backend Load Test
```bash
pip install locust

# Create locustfile.py
# Run: locust -f locustfile.py
```

Or use Apache Bench:
```bash
# Install: apt-get install apache2-utils
# Test: ab -c 10 -n 100 http://localhost:8000/health
```

---

## ✅ TEST 9: Error Scenarios

### Test: Backend Down
1. Stop backend server (`Ctrl+C`)
2. Try to access dashboard
3. Should show error message
4. Start backend again
5. Dashboard should auto-reconnect

### Test: Wrong API URL
1. Change `.env` VITE_API_BASE_URL to wrong address
2. Reload dashboard
3. Should show connection error
4. Fix URL and reload
5. Should work again

### Test: Expired Token
1. Get JWT token
2. Wait 1 hour (or modify token payload)
3. Make API request with expired token
4. Should get 401 response
5. App should refresh token automatically

### Test: Invalid Permissions
1. Login with limited user account
2. Try accessing admin-only endpoints
3. Should get 403 Forbidden
4. Error message displayed

---

## ✅ TEST 10: End-to-End Flow

### Complete User Journey

**Step 1: Start System**
```bash
# Terminal 1: Backend
cd attendance_backend
python main.py

# Terminal 2: Dashboard
cd web-dashboard
npm run dev

# Terminal 3: App (Optional)
cd attendance_app
flutter run
```

**Step 2: Access Dashboard**
- Open http://localhost:5173
- Should auto-connect to backend
- Shows attendance data

**Step 3: Verify Live Updates**
- Wait for auto-refresh (5 seconds)
- Data updates should be visible
- No errors in console

**Step 4: Test Search/Filter**
- Click on different courses
- Filter attendance records
- Search by student name
- All should work smoothly

**Step 5: Check Mobile (Optional)**
- Login with same credentials
- Should see same data
- Both interfaces working simultaneously

**✅ PASS**: All features work without errors  
**❌ FAIL**: Check specific issue and refer to troubleshooting

---

## 🔧 Troubleshooting Quick Guide

| Error | Likely Cause | Solution |
|-------|---|---|
| `Connection Refused` | Backend not running | `python main.py` in `attendance_backend/` |
| `CORS Error` | Origin not allowed | Add origin to `CORS_ORIGINS` in settings |
| `401 Unauthorized` | Invalid/expired token | Get new token via login |
| `404 Not Found` | Wrong endpoint URL | Check `/docs` for correct endpoints |
| `Timeout` | Slow network/backend hanging | Check backend logs, restart if needed |
| `localhost:8000 times out` | Port 8000 in use | Change port or kill process on 8000 |
| `Flutter can't reach backend` | Wrong base URL in app | Update `devBaseUrl` to match your IP |
| `Dashboard shows empty` | API returning no data | Check database is populated |
| `Firebase error` | Credentials missing | Ensure `.json` file in `config/` |
| `Models not loading` | Weight files missing | Download YOLOv8 & FaceNet models |

---

## 📋 Pre-Deployment Checklist

Before going to production, verify:

- [ ] All 3 components start without errors
- [ ] Backend health endpoint responds
- [ ] Dashboard connects and loads data
- [ ] Mobile app authenticates successfully
- [ ] CORS configured correctly
- [ ] Firebase credentials set up
- [ ] ML models available (YOLOv8, FaceNet)
- [ ] Database populated with test data
- [ ] Environment variables (.env) configured
- [ ] No console errors/warnings
- [ ] Response times acceptable (<2s)
- [ ] Token refresh works
- [ ] Error handling works
- [ ] Docker build successful (if containerizing)
- [ ] All tests pass

---

**Use this guide to validate every connection before deployment!**
