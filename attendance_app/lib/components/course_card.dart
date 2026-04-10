import 'package:flutter/material.dart';
import 'package:smart_attendance/models/course_model.dart';
import 'package:smart_attendance/theme/app_theme.dart';

/// Card displaying a course with optional attendance action.
class CourseCard extends StatelessWidget {
  final CourseModel course;
  final bool showAttendanceAction;
  final VoidCallback? onTap;

  const CourseCard({
    super.key,
    required this.course,
    this.showAttendanceAction = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = _courseColor(course.code);

    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.grey200),
        ),
        child: Row(
          children: [
            // Course code badge
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: color.withOpacity(0.12),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Center(
                child: Text(
                  course.code.length > 3
                      ? course.code.substring(0, 3)
                      : course.code,
                  style: TextStyle(
                    fontFamily: 'JetBrainsMono',
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: color,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 14),

            // Course info
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    course.name,
                    style: const TextStyle(
                      fontFamily: 'Sora',
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: AppColors.grey900,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 3),
                  Text(
                    course.teacherName,
                    style: const TextStyle(
                      fontFamily: 'Sora',
                      fontSize: 12,
                      color: AppColors.grey500,
                    ),
                  ),
                  const SizedBox(height: 6),
                  // Schedule tags
                  if (course.schedule.isNotEmpty)
                    Wrap(
                      spacing: 6,
                      children: course.schedule.take(2).map((s) {
                        return _ScheduleTag(
                          label:
                              '${s.dayOfWeek.substring(0, 3)} ${s.startTime}',
                        );
                      }).toList(),
                    ),
                ],
              ),
            ),

            if (showAttendanceAction)
              const Icon(
                Icons.chevron_right_rounded,
                color: AppColors.grey300,
                size: 22,
              ),
          ],
        ),
      ),
    );
  }

  Color _courseColor(String code) {
    final colors = [
      AppColors.primary,
      AppColors.secondary,
      AppColors.accent,
      AppColors.info,
      const Color(0xFF8B5CF6),
      const Color(0xFFEC4899),
    ];
    final hash = code.codeUnits.fold(0, (a, b) => a + b);
    return colors[hash % colors.length];
  }
}

class _ScheduleTag extends StatelessWidget {
  final String label;

  const _ScheduleTag({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: AppColors.grey100,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        style: const TextStyle(
          fontFamily: 'Sora',
          fontSize: 10,
          fontWeight: FontWeight.w500,
          color: AppColors.grey600,
        ),
      ),
    );
  }
}
