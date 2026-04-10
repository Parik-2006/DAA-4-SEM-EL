import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:smart_attendance/models/user_model.dart';
import 'package:smart_attendance/providers/attendance_provider.dart';
import 'package:smart_attendance/providers/auth_provider.dart';
import 'package:smart_attendance/router/app_router.dart';
import 'package:smart_attendance/theme/app_theme.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final summaryAsync = ref.watch(attendanceSummaryProvider(null));

    if (user == null) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      backgroundColor: AppColors.background,
      body: CustomScrollView(
        slivers: [
          // Profile header
          SliverToBoxAdapter(
            child: _ProfileHeader(user: user),
          ),

          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Attendance stats
                  Text(
                    'Attendance Overview',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 12),
                  summaryAsync.when(
                    data: (s) => _AttendanceOverview(
                      percentage: s.attendancePercentage,
                      present: s.presentCount,
                      absent: s.absentCount,
                      late: s.lateCount,
                      total: s.totalClasses,
                    ),
                    loading: () => const _OverviewSkeleton(),
                    error: (_, __) => const SizedBox.shrink(),
                  ),
                  const SizedBox(height: 24),

                  // Account info
                  Text(
                    'Account Details',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 12),
                  _InfoCard(user: user),
                  const SizedBox(height: 24),

                  // Settings
                  Text(
                    'Settings',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 12),
                  _SettingsTile(
                    icon: Icons.notifications_outlined,
                    label: 'Notifications',
                    onTap: () {},
                  ),
                  _SettingsTile(
                    icon: Icons.lock_outline,
                    label: 'Change Password',
                    onTap: () {},
                  ),
                  _SettingsTile(
                    icon: Icons.help_outline_rounded,
                    label: 'Help & Support',
                    onTap: () {},
                  ),
                  const SizedBox(height: 8),

                  // Logout
                  _LogoutButton(
                    onTap: () async {
                      await ref.read(authProvider.notifier).logout();
                      if (context.mounted) context.go(AppRoutes.login);
                    },
                  ),
                  const SizedBox(height: 40),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Profile header ─────────────────────────────────────────────────────────────

class _ProfileHeader extends StatelessWidget {
  final UserModel user;

  const _ProfileHeader({required this.user});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.surface,
      padding: EdgeInsets.fromLTRB(
        20,
        MediaQuery.of(context).padding.top + 20,
        20,
        24,
      ),
      child: Row(
        children: [
          // Avatar
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [AppColors.primary, AppColors.primaryDark],
              ),
              shape: BoxShape.circle,
            ),
            child: Center(
              child: Text(
                user.initials,
                style: const TextStyle(
                  fontFamily: 'Sora',
                  fontSize: 26,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                ),
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  user.name,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 4),
                Text(
                  user.email,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                if (user.studentId != null) ...[
                  const SizedBox(height: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppColors.primary.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      'ID: ${user.studentId}',
                      style: const TextStyle(
                        fontFamily: 'JetBrainsMono',
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                        color: AppColors.primary,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
          // Edit icon
          IconButton(
            onPressed: () {}, // TODO: Edit profile
            icon: const Icon(Icons.edit_outlined,
                color: AppColors.grey400, size: 22),
          ),
        ],
      ),
    );
  }
}

// ── Attendance overview ────────────────────────────────────────────────────────

class _AttendanceOverview extends StatelessWidget {
  final double percentage;
  final int present;
  final int absent;
  final int late;
  final int total;

  const _AttendanceOverview({
    required this.percentage,
    required this.present,
    required this.absent,
    required this.late,
    required this.total,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.grey200),
      ),
      child: Column(
        children: [
          Row(
            children: [
              // Circular progress
              SizedBox(
                width: 80,
                height: 80,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    CircularProgressIndicator(
                      value: percentage / 100,
                      strokeWidth: 8,
                      backgroundColor: AppColors.grey200,
                      valueColor: AlwaysStoppedAnimation(
                        _percentageColor(percentage),
                      ),
                    ),
                    Text(
                      '${percentage.toInt()}%',
                      style: TextStyle(
                        fontFamily: 'Sora',
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: _percentageColor(percentage),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 20),
              Expanded(
                child: Column(
                  children: [
                    _StatRow('Total Classes', '$total',
                        AppColors.grey600),
                    const SizedBox(height: 8),
                    _StatRow('Present', '$present', AppColors.success),
                    const SizedBox(height: 8),
                    _StatRow('Absent', '$absent', AppColors.error),
                    const SizedBox(height: 8),
                    _StatRow('Late', '$late', AppColors.warning),
                  ],
                ),
              ),
            ],
          ),
          if (percentage < 75) ...[
            const SizedBox(height: 16),
            const Divider(),
            const SizedBox(height: 12),
            Row(
              children: [
                const Icon(Icons.warning_amber_rounded,
                    color: AppColors.warning, size: 18),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Your attendance is below 75%. You may be at risk of not meeting requirements.',
                    style: Theme.of(context)
                        .textTheme
                        .bodySmall
                        ?.copyWith(color: AppColors.warning),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Color _percentageColor(double p) {
    if (p >= 75) return AppColors.success;
    if (p >= 60) return AppColors.warning;
    return AppColors.error;
  }
}

class _StatRow extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _StatRow(this.label, this.value, this.color);

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: Theme.of(context).textTheme.bodySmall),
        Text(
          value,
          style: TextStyle(
            fontFamily: 'Sora',
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: color,
          ),
        ),
      ],
    );
  }
}

class _OverviewSkeleton extends StatelessWidget {
  const _OverviewSkeleton();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 120,
      decoration: BoxDecoration(
        color: AppColors.grey200,
        borderRadius: BorderRadius.circular(16),
      ),
    );
  }
}

// ── Info card ──────────────────────────────────────────────────────────────────

class _InfoCard extends StatelessWidget {
  final UserModel user;

  const _InfoCard({required this.user});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.grey200),
      ),
      child: Column(
        children: [
          if (user.department != null)
            _InfoRow(
              icon: Icons.school_outlined,
              label: 'Department',
              value: user.department!,
            ),
          if (user.department != null && user.semester != null)
            const Divider(height: 1, indent: 56),
          if (user.semester != null)
            _InfoRow(
              icon: Icons.calendar_today_outlined,
              label: 'Semester',
              value: user.semester!,
            ),
          const Divider(height: 1, indent: 56),
          _InfoRow(
            icon: Icons.person_outline,
            label: 'Role',
            value: user.role.name[0].toUpperCase() +
                user.role.name.substring(1),
          ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _InfoRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Row(
        children: [
          Icon(icon, size: 20, color: AppColors.grey400),
          const SizedBox(width: 12),
          Text(
            label,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const Spacer(),
          Text(
            value,
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(color: AppColors.grey800),
          ),
        ],
      ),
    );
  }
}

// ── Settings tile ──────────────────────────────────────────────────────────────

class _SettingsTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _SettingsTile({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.grey200),
      ),
      child: ListTile(
        leading: Icon(icon, color: AppColors.grey500, size: 22),
        title: Text(
          label,
          style: const TextStyle(
            fontFamily: 'Sora',
            fontSize: 14,
            fontWeight: FontWeight.w500,
            color: AppColors.grey800,
          ),
        ),
        trailing: const Icon(
          Icons.chevron_right_rounded,
          color: AppColors.grey400,
          size: 20,
        ),
        onTap: onTap,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
        ),
      ),
    );
  }
}

// ── Logout button ──────────────────────────────────────────────────────────────

class _LogoutButton extends StatelessWidget {
  final VoidCallback onTap;

  const _LogoutButton({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: OutlinedButton.icon(
        onPressed: onTap,
        icon: const Icon(Icons.logout_rounded, size: 18),
        label: const Text('Sign Out'),
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.error,
          side: const BorderSide(color: AppColors.error, width: 1.5),
          padding: const EdgeInsets.symmetric(vertical: 14),
        ),
      ),
    );
  }
}
