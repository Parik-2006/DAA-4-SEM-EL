# Attendance Dashboard & History Implementation

This document describes the implementation of the real-time attendance dashboard and enhanced history screen.

## Features Overview

### 1. Real-Time Attendance Dashboard

**Location**: `lib/screens/attendance/dashboard_screen.dart`

**Purpose**: Display live attendance data with real-time updates via polling mechanism.

#### Key Features

✅ **Real-Time Updates**
- 5-second polling interval for live updates
- Stream-based data flow using Riverpod
- Auto-refresh when app returns to foreground
- Manual refresh via pull-to-refresh gesture

✅ **Live Attendance Records**
- Display student names and IDs
- Show attendance status (Present, Late, Absent, Excused)
- Display marked timestamp with relative time (e.g., "5m ago")
- Show face detection confidence scores
- Display student avatars with initials fallback

✅ **Statistics Dashboard**
- Present count with percentage
- Late count with percentage
- Absent count with percentage
- Excused count with percentage
- Color-coded status indicators
- Progress bars for visual representation

✅ **Filtering & Navigation**
- Filter by course (All courses option)
- Real-time filter switching
- Status indicator showing polling state
- Last sync timestamp display

✅ **UI/UX**
- Modern card-based design
- Color-coded status badges
- Status indicator with live/updating status
- Smooth animations and transitions
- Pull-to-refresh functionality
- Loading states and error handling

#### Component Architecture

```
AttendanceDashboardScreen
├── AppBar (with refresh button)
├── Course Filter (horizontal chips)
├── Main Content (CustomScrollView)
│   ├── Status Indicator (polling status)
│   ├── Statistics Grid (4 cards)
│   │   ├── Present Statistics
│   │   ├── Late Statistics
│   │   ├── Absent Statistics
│   │   └── Excused Statistics
│   └── Attendance Records List
│       └── AttendanceRecordCard (repeating)
└── Real-time Updates (via polling)
```

#### How to Use

**For Users**:
1. Navigate to Dashboard from home or menu
2. View live attendance statistics at the top
3. See recent check-ins in the scrollable list below
4. Filter by course using top filter chips
5. Pull to refresh for manual updates
6. View relative timestamps and student details

**For Developers**:
```dart
// Navigate to dashboard
context.go(AppRoutes.dashboard);

// Access dashboard state
final dashboard = ref.watch(realtimeAttendanceProvider);
final stats = ref.watch(attendanceStatsProvider);

// Control polling manually
ref.read(realtimeAttendanceProvider.notifier).startPolling(courseId: 'COURSE_ID');
ref.read(realtimeAttendanceProvider.notifier).stopPolling();
ref.read(realtimeAttendanceProvider.notifier).refreshData(courseId: 'COURSE_ID');
```

### 2. Enhanced History Screen

**Location**: `lib/screens/history/enhanced_history_screen.dart`

**Purpose**: Display past attendance records with advanced filtering and pagination.

#### Key Features

✅ **Search Functionality**
- Search by student name
- Search by student ID
- Real-time search filtering
- Clear search with one tap

✅ **Advanced Filtering**
- Filter by course
- Filter by date range (start & end date)
- Quick reset button for date range
- Filter by attendance status (via column headers)

✅ **Pagination**
- 30 records per page (configurable)
- Previous/Next page navigation
- Current page indicator
- Dynamic page controls

✅ **Attendance Records Display**
- Sorted by date (newest first)
- Student name and ID
- Attendance status
- Marked timestamp
- Student avatar/initials
- Face detection confidence

✅ **User Experience**
- Loading skeletons during fetch
- Empty state messaging
- Error handling with retry option
- Responsive to window size
- Smooth list animations

#### Component Architecture

```
EnhancedHistoryScreen
├── AppBar
├── Search Bar (with clear button)
├── Filter Section
│   ├── Course Filter (chips)
│   ├── Date Range Selector
│   │   ├── From date button
│   │   ├── To date button
│   │   └── Reset button
│   └── Applied Filters Display
└── Content Area
    ├── Empty State (if no results)
    ├── Loading State (skeletons)
    ├── Error State (with retry)
    └── Records List
        ├── AttendanceRecordCard (repeating)
        └── Pagination Controls
            ├── Previous button
            ├── Page indicator
            └── Next button
```

#### How to Use

**For Users**:
1. Navigate to Enhanced History
2. Use search to find specific students
3. Filter by course using chips
4. Select date range for time period
5. Browse records with pagination
6. View detailed attendance information
7. Use reset button to clear filters

**For Developers**:
```dart
// Navigate to enhanced history
context.go(AppRoutes.enhancedHistory);

// Access history data
final history = ref.watch(
  attendanceHistoryProvider(
    AttendanceHistoryFilter(
      courseId: 'COURSE_ID',
      startDate: DateTime.now().subtract(Duration(days: 30)),
      endDate: DateTime.now(),
      page: 1,
      limit: 30,
    ),
  ),
);

// Access summary data
final summary = ref.watch(
  attendanceSummaryProvider(
    AttendanceSummaryFilter(
      courseId: 'COURSE_ID',
      startDate: startDate,
      endDate: endDate,
    ),
  ),
);
```

## Models

### RealtimeAttendanceRecord
```dart
class RealtimeAttendanceRecord {
  final String id;
  final String studentName;
  final String studentId;
  final String courseName;
  final DateTime markedAt;
  final String status; // present, late, absent, excused
  final String? avatarUrl;
  final double? confidence; // For face detection
}
```

### AttendanceStats
```dart
class AttendanceStats {
  final int totalPresent;
  final int totalLate;
  final int totalAbsent;
  final int totalExcused;
  final DateTime lastUpdated;
  
  // Computed properties
  double get presentPercent => (totalPresent / total) * 100;
  double get latePercent => (totalLate / total) * 100;
  double get absentPercent => (totalAbsent / total) * 100;
}
```

### DashboardState
```dart
class DashboardState {
  final List<RealtimeAttendanceRecord> records;
  final AttendanceStats stats;
  final bool isLoading;
  final String? error;
  final DateTime? lastSyncTime;
  final bool isAutoRefreshing;
}
```

## Services

### DashboardService

**File**: `lib/services/dashboard_service.dart`

**Key Methods**:

1. **getLiveAttendance(courseId?, limit?)**
   - Fetch real-time attendance records
   - Endpoint: `GET /api/v1/attendance/live`
   - Returns: `List<RealtimeAttendanceRecord>`

2. **getAttendanceStats(courseId?, date?)**
   - Fetch attendance statistics
   - Endpoint: `GET /api/v1/attendance/stats`
   - Returns: `AttendanceStats`

3. **startPolling(courseId?)**
   - Start automatic polling for updates
   - Interval: 5 seconds
   - Emits updates via streams

4. **stopPolling()**
   - Stop automatic polling
   - Cleanup resources

5. **getAttendanceHistory(courseId?, startDate?, endDate?, page?, limit?)**
   - Fetch historical records
   - Endpoint: `GET /api/v1/attendance/history`
   - Returns: `List<RealtimeAttendanceRecord>`

6. **getAttendanceSummary(courseId?, startDate?, endDate?)**
   - Fetch attendance summary by status
   - Endpoint: `GET /api/v1/attendance/summary`
   - Returns: `Map<String, int>`

## Providers

### realtimeAttendanceProvider
```dart
// State management for real-time records
final realtimeAttendanceProvider = 
  StateNotifierProvider<RealtimeAttendanceNotifier, RealtimeAttendanceState>();

// Methods:
- startPolling(courseId?)
- stopPolling()
- refreshData(courseId?)
```

### attendanceStatsProvider
```dart
// State management for statistics
final attendanceStatsProvider = 
  StateNotifierProvider<AttendanceStatsNotifier, AttendanceStatsState>();

// Methods:
- startListening()
- fetchStats(courseId?, date?)
```

### attendanceHistoryProvider
```dart
// Fetch historical records
final attendanceHistoryProvider = 
  FutureProvider.family<List<RealtimeAttendanceRecord>, AttendanceHistoryFilter>();

// With filtering:
AttendanceHistoryFilter(
  courseId: 'COURSE_ID',
  startDate: DateTime.now().subtract(Duration(days: 30)),
  endDate: DateTime.now(),
  page: 1,
  limit: 30,
)
```

### attendanceSummaryProvider
```dart
// Fetch summary statistics
final attendanceSummaryProvider = 
  FutureProvider.family<Map<String, int>, AttendanceSummaryFilter>();

// With filtering:
AttendanceSummaryFilter(
  courseId: 'COURSE_ID',
  startDate: startDate,
  endDate: endDate,
)
```

## Components

### AttendanceRecordCard
Displays a single attendance record with:
- Student avatar/initials
- Student name and ID
- Attendance status badge
- Marked timestamp
- Face detection confidence (if available)

### StatisticsCard
Displays a single statistic with:
- Title and value
- Icon
- Progress bar (optional)
- Percentage display
- Color-coded styling

### StatisticsGrid
Grid layout for multiple StatisticsCard components

## API Endpoints Required

### Backend Endpoints

1. **GET /api/v1/attendance/live**
   - Query params: course_id?, limit?
   - Response:
   ```json
   [
     {
       "id": "att_001",
       "student_name": "John Doe",
       "student_id": "STU001",
       "course_name": "CS101",
       "marked_at": "2024-04-10T14:30:00Z",
       "status": "present",
       "avatar_url": "https://...",
       "confidence": 0.95
     }
   ]
   ```

2. **GET /api/v1/attendance/stats**
   - Query params: course_id?, date?
   - Response:
   ```json
   {
     "total_present": 45,
     "total_late": 5,
     "total_absent": 3,
     "total_excused": 2,
     "last_updated": "2024-04-10T14:35:00Z"
   }
   ```

3. **GET /api/v1/attendance/history**
   - Query params: course_id?, start_date?, end_date?, page, limit
   - Response: Same as `/live` but with pagination

4. **GET /api/v1/attendance/summary**
   - Query params: course_id?, start_date?, end_date?
   - Response:
   ```json
   {
     "present": 100,
     "late": 15,
     "absent": 10,
     "excused": 5
   }
   ```

## State Management Flow

### Dashboard Real-Time Updates

```
User Opens Dashboard
        ↓
startPolling() called
        ↓
DashboardService starts 5-second timer
        ↓
Every 5 seconds:
  - Fetch live records
  - Fetch statistics
  - Emit via streams
        ↓
StateNotifier receives updates
        ↓
UI rebuilds with new data
        ↓
User sees real-time updates
```

### History Filtering

```
User Adjusts Filters
        ↓
State variables updated (course, dates, page)
        ↓
attendanceHistoryProvider refetches
        ↓
API call made with new params
        ↓
Results returned and sorted
        ↓
UI displays filtered results
        ↓
User can paginate through results
```

## Performance Optimization

1. **Polling Interval**: 5 seconds (adjustable)
   - Balances real-time updates with server load
   - Can be configured based on backend capacity

2. **Pagination**: 30 records per page
   - Reduces memory usage for large datasets
   - Improves initial load time

3. **Stream-Based Updates**: Riverpod streams
   - Efficient state management
   - Automatic cleanup on disposal
   - Only rebuilds affected widgets

4. **Search Filtering**: Client-side
   - Instant search results
   - Reduces API calls

5. **Date Range Filtering**:
   - Server-side filtering via query params
   - Reduces data transfer

## Error Handling

- Network errors: Show error banner with retry button
- Empty results: Show empty state message
- API failures: Graceful degradation with last known state
- Permission issues: Show appropriate error messages

## Testing Checklist

- [ ] Dashboard displays live attendance
- [ ] Real-time updates appear every 5 seconds
- [ ] Course filtering works correctly
- [ ] Pull-to-refresh triggers data reload
- [ ] Auto-pause polling when app backgrounded
- [ ] Auto-resume polling when app returns to foreground
- [ ] Statistics calculations are accurate
- [ ] History search filters correctly
- [ ] Date range filtering works
- [ ] Pagination navigates through pages
- [ ] Empty states display correctly
- [ ] Error messages appear on API failures
- [ ] UI is responsive on different screen sizes
- [ ] Performance is smooth (60 FPS)
- [ ] Memory cleanup on screen exit

## Troubleshooting

### No data appearing
1. Verify backend API endpoints are implemented
2. Check network connectivity
3. Verify API response format matches models
4. Check database has attendance records

### Polling not updating
1. Check polling interval isn't too short
2. Verify backend is returning new data
3. Check Riverpod logs for errors
4. Ensure app isn't backgrounded

### Search/Filters not working
1. Verify search query is valid
2. Check course IDs are correct
3. Verify date range is valid
4. Check data exists for filters

## Future Enhancements

1. **Offline Support**: Cache data locally
2. **WebSocket Support**: Real-time updates via WebSocket instead of polling
3. **Advanced Analytics**: Charts and graphs for attendance trends
4. **Export Features**: Export attendance as PDF/CSV
5. **Batch Operations**: Mark multiple students at once
6. **Notifications**: Alert for high absence rates
7. **Attendance Appeals**: Allow students to appeal marks
8. **Scheduled Reports**: Automatic attendance reports

## Related Documentation

- `FEATURES_OVERVIEW.md` - Overall feature summary
- `IMPLEMENTATION_GUIDE.md` - Technical implementation details
- `CAMERA_SETUP.md` - Camera permission setup
