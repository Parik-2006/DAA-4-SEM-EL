import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:smart_attendance/components/attendance_stat_card.dart';
import 'package:smart_attendance/components/course_card.dart';
import 'package:smart_attendance/components/section_header.dart';
import 'package:smart_attendance/providers/attendance_provider.dart';
import 'package:smart_attendance/providers/auth_provider.dart';
import 'package:smart_attendance/router/app_router.dart';
import 'package:smart_attendance/theme/app_theme.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final coursesAsync = ref.watch(myCoursesProvider);
    final summaryAsync = ref.watch(attendanceSummaryProvider(null));

    return Scaffold(
      backgroundColor: AppColors.background,
      body: CustomScrollView(
        slivers: [
          // App bar
          SliverAppBar(
            floating: true,
            backgroundColor: AppColors.background,
            elevation: 0,
            title: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _greeting(),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppColors.grey500,
                      ),
                ),
                Text(
                  user?.name.split(' ').first ?? 'Student',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
              ],
            ),
            actions: [
              // QR Scan button
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: IconButton(
                  onPressed: () => context.push(AppRoutes.qrScan),
                  icon: Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppColors.primary,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(
                      Icons.qr_code_scanner_rounded,
                      color: Colors.white,
                      size: 20,
                    ),
                  ),
                ),
              ),
            ],
          ),

          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Date chip
                  _DateChip(),
                  const SizedBox(height: 20),

                  // Attendance overview card
                  summaryAsync.when(
                    data: (summary) => _OverviewCard(
                      percentage: summary.attendancePercentage,
                      present: summary.presentCount,
                      absent: summary.absentCount,
                      total: summary.totalClasses,
                    ),
                    loading: () => const _OverviewCardSkeleton(),
                    error: (e, _) => _OverviewCard(
                      percentage: 0,
                      present: 0,
                      absent: 0,
                      total: 0,
                    ),
                  ),
                  const SizedBox(height: 28),

                  // Stats row
                  summaryAsync.when(
                    data: (summary) => Row(
                      children: [
                        Expanded(
                          child: AttendanceStatCard(
                            label: 'Present',
                            value: '${summary.presentCount}',
                            color: AppColors.success,
                            icon: Icons.check_circle_outline_rounded,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: AttendanceStatCard(
                            label: 'Absent',
                            value: '${summary.absentCount}',
                            color: AppColors.error,
                            icon: Icons.cancel_outlined,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: AttendanceStatCard(
                            label: 'Late',
                            value: '${summary.lateCount}',
                            color: AppColors.warning,
                            icon: Icons.watch_later_outlined,
                          ),
                        ),
                      ],
                    ),
                    loading: () => const _StatRowSkeleton(),
                    error: (_, __) => const SizedBox.shrink(),
                  ),
                  const SizedBox(height: 28),

                  // My courses
                  SectionHeader(
                    title: 'My Courses',
                    onSeeAll: () => context.go(AppRoutes.attendance),
                  ),
                  const SizedBox(height: 12),
                ],
              ),
            ),
          ),

          // Course cards
          coursesAsync.when(
            data: (courses) => SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 32),
              sliver: SliverList.separated(
                itemCount: courses.take(4).length,
                separatorBuilder: (_, __) => const SizedBox(height: 12),
                itemBuilder: (context, index) {
                  return CourseCard(course: courses[index]);
                },
              ),
            ),
            loading: () => SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Column(
                  children: List.generate(
                    3,
                    (i) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: _CourseCardSkeleton(),
                    ),
                  ),
                ),
              ),
            ),
            error: (e, _) => SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Center(
                  child: Text(
                    'Failed to load courses.',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _greeting() {
    final hour = DateTime.now().hour;
    if (hour < 12) return 'Good morning,';
    if (hour < 17) return 'Good afternoon,';
    return 'Good evening,';
  }
}

class _DateChip extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final formatted = DateFormat('EEEE, MMMM d').format(now);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.primary.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.calendar_today_rounded,
            size: 13,
            color: AppColors.primary,
          ),
          const SizedBox(width: 6),
          Text(
            formatted,
            style: const TextStyle(
              fontFamily: 'Sora',
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppColors.primary,
            ),
          ),
        ],
      ),
    );
  }
}

class _OverviewCard extends StatelessWidget {
  final double percentage;
  final int present;
  final int absent;
  final int total;

  const _OverviewCard({
    required this.percentage,
    required this.present,
    required this.absent,
    required this.total,
  });

  @override
  Widget build(BuildContext context) {
    final color = percentage >= 75
        ? AppColors.success
        : percentage >= 60
            ? AppColors.warning
            : AppColors.error;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [AppColors.primary, AppColors.primaryDark],
        ),
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withOpacity(0.3),
            blurRadius: 20,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Overall Attendance',
                  style: TextStyle(
                    fontFamily: 'Sora',
                    fontSize: 13,
                    color: Colors.white70,
                    fontWeight: FontWeight.w400,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  '${percentage.toStringAsFixed(1)}%',
                  style: const TextStyle(
                    fontFamily: 'Sora',
                    fontSize: 38,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                    letterSpacing: -1,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '$present of $total classes attended',
                  style: const TextStyle(
                    fontFamily: 'Sora',
                    fontSize: 12,
                    color: Colors.white60,
                  ),
                ),
                const SizedBox(height: 16),
                // Progress bar
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: percentage / 100,
                    backgroundColor: Colors.white.withOpacity(0.2),
                    valueColor: const AlwaysStoppedAnimation(Colors.white),
                    minHeight: 6,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 20),
          // Status badge
          Column(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  percentage >= 75 ? '✓ Good' : '⚠ Low',
                  style: const TextStyle(
                    fontFamily: 'Sora',
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _OverviewCardSkeleton extends StatelessWidget {
  const _OverviewCardSkeleton();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 140,
      decoration: BoxDecoration(
        color: AppColors.grey200,
        borderRadius: BorderRadius.circular(20),
      ),
    );
  }
}

class _StatRowSkeleton extends StatelessWidget {
  const _StatRowSkeleton();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: List.generate(
        3,
        (i) => Expanded(
          child: Container(
            margin: EdgeInsets.only(right: i < 2 ? 12 : 0),
            height: 80,
            decoration: BoxDecoration(
              color: AppColors.grey200,
              borderRadius: BorderRadius.circular(16),
            ),
          ),
        ),
      ),
    );
  }
}

class _CourseCardSkeleton extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      height: 80,
      decoration: BoxDecoration(
        color: AppColors.grey200,
        borderRadius: BorderRadius.circular(16),
      ),
    );
  }
}
