# Attendance Analytics — Integration Guide
**CSE 4C Section C · RV College of Engineering**

---

## What was built

| File | Purpose |
|------|---------|
| `src/config/timetable.ts` | All 22 real periods, 60 student names, helper functions |
| `src/pages/AttendanceAnalyticsPage.tsx` | Full analytics page — KPIs, charts, filters, activity log |
| `src/hooks/useAttendanceAnalytics.ts` | Data hook — real API + mock fallback + polling |
| `src/services/api.analytics.ts` | 6 new backend API methods |
| `src/components/Layout.tsx` | Sidebar updated with Analytics nav link |
| `src/AppRouter.tsx` | `/analytics` route added |
| `src/pages/index.ts` | `AttendanceAnalyticsPage` export added |

---

## Step 1 — Copy files into your project

```
web-dashboard/
├── src/
│   ├── config/
│   │   └── timetable.ts                  ← NEW  (copy from outputs)
│   ├── pages/
│   │   ├── AttendanceAnalyticsPage.tsx   ← NEW  (copy from outputs)
│   │   └── index.ts                      ← REPLACE (pages-index.ts → index.ts)
│   ├── hooks/
│   │   └── useAttendanceAnalytics.ts     ← NEW  (copy from outputs)
│   ├── components/
│   │   └── Layout.tsx                    ← REPLACE (copy from outputs)
│   └── AppRouter.tsx                     ← REPLACE (copy from outputs)
```

---

## Step 2 — Add new API methods to api.ts

Open `src/services/api.ts` and paste the contents of
`api.analytics.ts` **inside the `AttendanceAPI` class**, after the
existing `deleteCourse` method, before the closing `}`.

```ts
// api.ts  — inside class AttendanceAPI { ... }

  // ↓ paste the 6 methods from api.analytics.ts here

  async getPeriodAttendance(...) { ... }
  async getCourseTrend(...)       { ... }
  async markPeriodAttendance(...) { ... }
  async bulkMarkPeriod(...)       { ... }
  async getSectionSummary(...)    { ... }
  async exportPeriodCSV(...)      { ... }
```

---

## Step 3 — Verify the route works

Start the dev server:

```bash
cd web-dashboard
npm run dev
```

Navigate to **http://localhost:3000/analytics**

You should see:
- Header: "RV College of Engineering · UG CSE · 4C · Even Sem 2025-26"
- Period selector with all 5 days and 22 period options
- 5 KPI cards (Present / Absent / Late / Not Marked / Attendance %)
- 7-session bar chart with colour-coded bars (green ≥ 80 %, amber 70–80 %, red < 70 %)
- Donut distribution chart with inline legend
- Activity log with status / method / search filters
- Live dot pulsing; numbers updating every ~5 s

---

## Step 4 — Swap mock data for real API (when backend is ready)

### Option A — Use the hook (recommended refactor)

Replace the inline state management in `AttendanceAnalyticsPage.tsx`
with the `useAttendanceAnalytics` hook:

```tsx
// AttendanceAnalyticsPage.tsx — top of component
import { useAttendanceAnalytics } from '../hooks/useAttendanceAnalytics';

// Inside the component:
const {
  state, trendData, donutData,
  attendancePct, markingPct,
  lastUpdated, isLoading, error,
  refetch, simulateMark,
} = useAttendanceAnalytics({ periodId: selectedId, pollMs: 6000 });
```

The hook automatically:
1. Calls `attendanceAPI.getAdminAttendanceToday()` (existing endpoint).
2. Tries to coerce the response into `AnalyticsState`.
3. Falls back to mock data silently if the API returns nothing useful.
4. Polls every 6 s.

### Option B — Add the period-specific endpoint

Add this to your FastAPI backend:

```python
# attendance_backend/routers/analytics.py

from fastapi import APIRouter, Query
from datetime import date as Date

router = APIRouter(prefix="/api/v1/attendance", tags=["analytics"])

@router.get("/period")
async def get_period_attendance(
    course_code: str,
    day: str,
    date: Date | None = None,
    limit: int = 100,
):
    """Return all attendance records for one class period."""
    # Query your DB here
    return {
        "records": [...],
        "summary": {
            "present": 0, "absent": 0,
            "late": 0, "not_marked": 0, "total": 60,
        },
        "period": {"course_code": course_code, "day": day, "date": str(date)},
    }

@router.get("/trend")
async def get_course_trend(
    course_code: str,
    day: str,
    sessions: int = 7,
):
    """Return last N session attendance percentages for a course."""
    return [
        {"date": "May 2", "percentage": 82},
        # ... 6 more
    ]
```

Then in the hook set `mockOnly: false` (which is already the default).

---

## Step 5 — Update real student names

Replace the `STUDENT_NAMES` array in `src/config/timetable.ts`
with actual names from your student database.

```ts
// timetable.ts
export const STUDENT_NAMES: string[] = [
  // Pull from your DB:  SELECT name FROM students WHERE class_id = 'CSE-4C'
  'Actual Student 1',
  'Actual Student 2',
  // ... 60 names
];
```

Or fetch dynamically inside the hook:

```ts
// useAttendanceAnalytics.ts — inside fetchOrMock()
const students = await attendanceAPI.getStudents(); // existing method
const names    = students.map(s => s.name);
```

---

## Step 6 — Enable CSV export (server-side)

The `exportPeriodCSV` method in `api.analytics.ts` calls:

```
GET /api/v1/attendance/export/period
    ?course_code=CS344AI&day=FRI&date=2026-05-08
```

Add this endpoint to your backend and return a `StreamingResponse`
with `media_type="text/csv"`.

For now, client-side export is available via the **Export CSV** button
in the activity log (handled by `exportActivityCSV()` in the hook file).

---

## Feature summary

### Period selector
All 22 periods from the uploaded timetable, grouped by day using
`<optgroup>`. Switching periods resets filters and rebuilds all charts.

### KPI cards
| Card | Source |
|------|--------|
| Present | `state.present` |
| Absent | `state.absent` |
| Late | `state.late` |
| Not Marked | `state.notMarked` |
| Attendance % | `(present + late) / total × 100` |

All values animate via CSS when they change.

### 7-session trend chart
- X-axis: last 7 actual calendar dates when that day of the week fell.
  (e.g. for FRI: May 8, May 1, Apr 24, Apr 17, Apr 10, Apr 3, Mar 27)
- Bar colour: green ≥ 80 %, amber 70–80 %, red < 70 %.
- Tooltip: shows `COURSE_CODE · NN%`.
- Data source: `period.trendBase` (static) → swap for `getCourseTrend()`.

### Distribution donut
Recharts `PieChart` with `innerRadius`. Custom HTML legend below
the chart with exact counts and percentages. Updates in real time.

### Activity log
- Shows newest 25 entries (configurable).
- Filter by: status, mark method, student name (live search).
- Client-side CSV export button.
- "Showing N of M" footer when results are truncated.

### Live simulation
`setInterval(simulateMark, 5500)` fires every 5.5 s while the page
is mounted. Each tick picks a random unmarked student and assigns
`present` (78 %), `late` (11 %), or `absent` (11 %).
Stop it by passing `pollMs={0}` to the hook, or by replacing the
interval with a real WebSocket / SSE listener.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Period not found" error | Ensure `timetable.ts` is at `src/config/timetable.ts` |
| Charts not rendering | `recharts` must be installed — `npm install recharts` |
| `BarChart2` icon missing | Update lucide-react — `npm install lucide-react@latest` |
| TypeScript errors on `Period` type | Import from `../config/timetable`, not from a re-export |
| Hook always uses mock | Backend health check failing — check `VITE_API_BASE_URL` |
| Blank page at `/analytics` | Check AppRouter.tsx has the `/analytics` route |

---

## Next enhancements

- [ ] Replace `trendBase` with live `getCourseTrend()` call
- [ ] WebSocket / SSE for instant push updates instead of polling
- [ ] Per-student attendance detail modal (click row → expand)
- [ ] Week-view heatmap (all courses × all days in one grid)
- [ ] Low-attendance alert emails via backend scheduler
- [ ] Admin bulk-mark modal using `bulkMarkPeriod()` API method
