import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:smart_attendance/providers/auth_provider.dart';
import 'package:smart_attendance/providers/admin_provider.dart';
import 'package:smart_attendance/theme/app_theme.dart';

class AdminDashboardScreen extends ConsumerWidget {
  const AdminDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);
    final user = authState.user;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Admin Dashboard'),
        elevation: 0,
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await ref.read(authProvider.notifier).logout();
              if (context.mounted) {
                context.go('/login-type');
              }
            },
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Welcome Card
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [AppColors.primary, AppColors.primary.withOpacity(0.7)],
                ),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Welcome Back, Admin!',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    user?.name ?? 'Administrator',
                    style: const TextStyle(
                      fontSize: 16,
                      color: Colors.white70,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    user?.email ?? '',
                    style: const TextStyle(
                      fontSize: 12,
                      color: Colors.white60,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Admin Actions
            const Text(
              'Admin Functions',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 16),

            // Grid of admin options
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 16,
              crossAxisSpacing: 16,
              children: [
                _AdminActionCard(
                  icon: Icons.people,
                  title: 'Manage Students',
                  description: 'View and manage all students',
                  onTap: () {},
                ),
                _AdminActionCard(
                  icon: Icons.assignment,
                  title: 'Attendance Records',
                  description: 'View all attendance data',
                  onTap: () {},
                ),
                _AdminActionCard(
                  icon: Icons.person_add,
                  title: 'Register Student',
                  description: 'Add new student to system',
                  onTap: () {},
                ),
                _AdminActionCard(
                  icon: Icons.assessment,
                  title: 'Generate Reports',
                  description: 'Create attendance reports',
                  onTap: () {},
                ),
                _AdminActionCard(
                  icon: Icons.camera,
                  title: 'Mark Attendance',
                  description: 'Start face recognition',
                  onTap: () {},
                ),
                _AdminActionCard(
                  icon: Icons.settings,
                  title: 'Settings',
                  description: 'System configuration',
                  onTap: () {},
                ),
              ],
            ),
            const SizedBox(height: 32),

            // Quick Stats
            const Text(
              'Statistics',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 16),

            ref.watch(adminTodayStatsProvider).when(
              loading: () => Row(
                children: [
                  Expanded(child: _LoadingSkeleton()),
                  const SizedBox(width: 12),
                  Expanded(child: _LoadingSkeleton()),
                ],
              ),
              error: (err, stack) => const Text('Failed to load stats'),
              data: (stats) => Column(
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: _StatCard(
                          title: 'Total Students',
                          value: stats.totalStudents.toString(),
                          icon: Icons.people,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _StatCard(
                          title: 'Present Today',
                          value: stats.presentToday.toString(),
                          icon: Icons.check_circle,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _StatCard(
                          title: 'Absent Today',
                          value: stats.absentToday.toString(),
                          icon: Icons.cancel,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _StatCard(
                          title: 'Attendance Rate',
                          value: '${stats.attendanceRate.toStringAsFixed(1)}%',
                          icon: Icons.trending_up,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }
}

class _AdminActionCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String description;
  final VoidCallback onTap;

  const _AdminActionCard({
    required this.icon,
    required this.title,
    required this.description,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            border: Border.all(
              color: AppColors.primary.withOpacity(0.2),
            ),
            borderRadius: BorderRadius.circular(12),
            color: Colors.white,
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.primary.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  icon,
                  color: AppColors.primary,
                  size: 28,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                title,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                description,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 11,
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;

  const _StatCard({
    required this.title,
    required this.value,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        border: Border.all(
          color: AppColors.primary.withOpacity(0.2),
        ),
        borderRadius: BorderRadius.circular(12),
        color: Colors.white,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            icon,
            color: AppColors.primary,
            size: 24,
          ),
          const SizedBox(height: 8),
          Text(
            value,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            title,
            style: const TextStyle(
              fontSize: 12,
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}

class _LoadingSkeleton extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        border: Border.all(
          color: AppColors.primary.withOpacity(0.2),
        ),
        borderRadius: BorderRadius.circular(12),
        color: Colors.grey.withOpacity(0.1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(width: 24, height: 24, color: Colors.grey.withOpacity(0.3)),
          const SizedBox(height: 8),
          Container(width: 60, height: 18, color: Colors.grey.withOpacity(0.3)),
          const SizedBox(height: 8),
          Container(width: 100, height: 12, color: Colors.grey.withOpacity(0.3)),
        ],
      ),
    );
  }
}
