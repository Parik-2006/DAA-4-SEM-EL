import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:smart_attendance/components/course_card.dart';
import 'package:smart_attendance/providers/attendance_provider.dart';
import 'package:smart_attendance/router/app_router.dart';
import 'package:smart_attendance/theme/app_theme.dart';

class AttendanceScreen extends ConsumerWidget {
  const AttendanceScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final coursesAsync = ref.watch(myCoursesProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Mark Attendance'),
        backgroundColor: AppColors.surface,
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: ElevatedButton.icon(
              onPressed: () => context.push(AppRoutes.qrScan),
              icon: const Icon(Icons.qr_code_scanner_rounded, size: 18),
              label: const Text('Scan QR'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                textStyle: const TextStyle(
                  fontFamily: 'Sora',
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
        ],
      ),
      body: coursesAsync.when(
        data: (courses) => ListView(
          padding: const EdgeInsets.all(20),
          children: [
            // Info banner
            _InfoBanner(),
            const SizedBox(height: 20),

            Text(
              'Your Courses',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 4),
            Text(
              'Tap a course to view or mark attendance',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 16),

            ...courses.map(
              (course) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: CourseCard(
                  course: course,
                  showAttendanceAction: true,
                ),
              ),
            ),
          ],
        ),
        loading: () => const Center(
          child: CircularProgressIndicator(),
        ),
        error: (e, _) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 48, color: AppColors.grey400),
              const SizedBox(height: 12),
              const Text('Failed to load courses'),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () => ref.refresh(myCoursesProvider),
                child: const Text('Try again'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _InfoBanner extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.info.withOpacity(0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.info.withOpacity(0.2)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: AppColors.info.withOpacity(0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(
              Icons.info_outline_rounded,
              color: AppColors.info,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Mark your attendance',
                  style: TextStyle(
                    fontFamily: 'Sora',
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppColors.grey800,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'Scan the QR code shown by your lecturer to mark yourself present.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
