import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:smart_attendance/models/attendance_model.dart';
import 'package:smart_attendance/providers/attendance_provider.dart';
import 'package:smart_attendance/theme/app_theme.dart';

class HistoryScreen extends ConsumerStatefulWidget {
  const HistoryScreen({super.key});

  @override
  ConsumerState<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends ConsumerState<HistoryScreen> {
  String? _selectedCourseId;
  final _filter = const AttendanceFilter();

  @override
  Widget build(BuildContext context) {
    final coursesAsync = ref.watch(myCoursesProvider);
    final attendanceAsync = ref.watch(
      myAttendanceProvider(AttendanceFilter(courseId: _selectedCourseId)),
    );

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Attendance History'),
        backgroundColor: AppColors.surface,
      ),
      body: Column(
        children: [
          // Course filter chips
          coursesAsync.when(
            data: (courses) => _CourseFilterBar(
              courses: courses
                  .map((c) => _CourseChip(id: c.id, name: c.code))
                  .toList(),
              selectedId: _selectedCourseId,
              onSelected: (id) =>
                  setState(() => _selectedCourseId = id),
            ),
            loading: () => const SizedBox(height: 56),
            error: (_, __) => const SizedBox.shrink(),
          ),

          // Attendance list
          Expanded(
            child: attendanceAsync.when(
              data: (records) => records.isEmpty
                  ? const _EmptyState()
                  : ListView.separated(
                      padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
                      itemCount: records.length,
                      separatorBuilder: (_, __) =>
                          const SizedBox(height: 10),
                      itemBuilder: (context, i) =>
                          _AttendanceRecord(record: records[i]),
                    ),
              loading: () => ListView.separated(
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
                itemCount: 6,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (_, __) => const _RecordSkeleton(),
              ),
              error: (e, _) => Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.error_outline,
                        size: 48, color: AppColors.grey400),
                    const SizedBox(height: 12),
                    const Text('Failed to load history'),
                    TextButton(
                      onPressed: () => ref.refresh(
                        myAttendanceProvider(
                          AttendanceFilter(courseId: _selectedCourseId),
                        ),
                      ),
                      child: const Text('Try again'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Course filter bar ──────────────────────────────────────────────────────────

class _CourseChip {
  final String id;
  final String name;
  const _CourseChip({required this.id, required this.name});
}

class _CourseFilterBar extends StatelessWidget {
  final List<_CourseChip> courses;
  final String? selectedId;
  final ValueChanged<String?> onSelected;

  const _CourseFilterBar({
    required this.courses,
    required this.selectedId,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.surface,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            _FilterChip(
              label: 'All',
              isSelected: selectedId == null,
              onTap: () => onSelected(null),
            ),
            const SizedBox(width: 8),
            ...courses.map(
              (c) => Padding(
                padding: const EdgeInsets.only(right: 8),
                child: _FilterChip(
                  label: c.name,
                  isSelected: selectedId == c.id,
                  onTap: () =>
                      onSelected(selectedId == c.id ? null : c.id),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _FilterChip({
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected
              ? AppColors.primary
              : AppColors.grey100,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontFamily: 'Sora',
            fontSize: 13,
            fontWeight: FontWeight.w500,
            color: isSelected ? Colors.white : AppColors.grey600,
          ),
        ),
      ),
    );
  }
}

// ── Single attendance record card ──────────────────────────────────────────────

class _AttendanceRecord extends StatelessWidget {
  final AttendanceModel record;

  const _AttendanceRecord({required this.record});

  @override
  Widget build(BuildContext context) {
    final statusColor = _statusColor(record.status);
    final statusIcon = _statusIcon(record.status);
    final statusLabel = _statusLabel(record.status);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.grey200),
      ),
      child: Row(
        children: [
          // Status dot
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: statusColor.withOpacity(0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(statusIcon, color: statusColor, size: 22),
          ),
          const SizedBox(width: 14),

          // Course info
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  record.courseName,
                  style: Theme.of(context).textTheme.titleMedium,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 3),
                Text(
                  DateFormat('EEE, MMM d • h:mm a')
                      .format(record.markedAt),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),

          // Status badge
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: 10,
              vertical: 5,
            ),
            decoration: BoxDecoration(
              color: statusColor.withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              statusLabel,
              style: TextStyle(
                fontFamily: 'Sora',
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: statusColor,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Color _statusColor(AttendanceStatus status) => switch (status) {
        AttendanceStatus.present => AppColors.success,
        AttendanceStatus.absent => AppColors.error,
        AttendanceStatus.late => AppColors.warning,
        AttendanceStatus.excused => AppColors.info,
      };

  IconData _statusIcon(AttendanceStatus status) => switch (status) {
        AttendanceStatus.present =>
          Icons.check_circle_outline_rounded,
        AttendanceStatus.absent => Icons.cancel_outlined,
        AttendanceStatus.late => Icons.watch_later_outlined,
        AttendanceStatus.excused => Icons.info_outline_rounded,
      };

  String _statusLabel(AttendanceStatus status) => switch (status) {
        AttendanceStatus.present => 'Present',
        AttendanceStatus.absent => 'Absent',
        AttendanceStatus.late => 'Late',
        AttendanceStatus.excused => 'Excused',
      };
}

// ── Skeleton & empty states ────────────────────────────────────────────────────

class _RecordSkeleton extends StatelessWidget {
  const _RecordSkeleton();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 76,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.grey200),
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppColors.grey200,
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  height: 14,
                  width: 160,
                  decoration: BoxDecoration(
                    color: AppColors.grey200,
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
                const SizedBox(height: 8),
                Container(
                  height: 11,
                  width: 120,
                  decoration: BoxDecoration(
                    color: AppColors.grey100,
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
              ],
            ),
          ),
          Container(
            width: 60,
            height: 26,
            decoration: BoxDecoration(
              color: AppColors.grey200,
              borderRadius: BorderRadius.circular(8),
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: AppColors.grey100,
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.history_rounded,
              size: 36,
              color: AppColors.grey400,
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'No records found',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 6),
          Text(
            'Your attendance history will appear here.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}
