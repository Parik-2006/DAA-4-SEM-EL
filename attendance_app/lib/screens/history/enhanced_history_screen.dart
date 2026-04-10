import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:smart_attendance/components/attendance_record_card.dart';
import 'package:smart_attendance/models/dashboard_model.dart';
import 'package:smart_attendance/providers/attendance_provider.dart';
import 'package:smart_attendance/providers/dashboard_provider.dart';
import 'package:smart_attendance/theme/app_theme.dart';

class EnhancedHistoryScreen extends ConsumerStatefulWidget {
  const EnhancedHistoryScreen({super.key});

  @override
  ConsumerState<EnhancedHistoryScreen> createState() =>
      _EnhancedHistoryScreenState();
}

class _EnhancedHistoryScreenState extends ConsumerState<EnhancedHistoryScreen> {
  String? _selectedCourseId;
  DateTime? _startDate;
  DateTime? _endDate;
  int _currentPage = 1;
  final int _itemsPerPage = 30;
  String _searchQuery = '';
  late TextEditingController _searchController;

  @override
  void initState() {
    super.initState();
    _searchController = TextEditingController();
    // Initialize dates to last 30 days
    _endDate = DateTime.now();
    _startDate = DateTime.now().subtract(const Duration(days: 30));
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final coursesAsync = ref.watch(myCoursesProvider);
    final historyAsync = ref.watch(
      attendanceHistoryProvider(
        AttendanceHistoryFilter(
          courseId: _selectedCourseId,
          startDate: _startDate,
          endDate: _endDate,
          page: _currentPage,
          limit: _itemsPerPage,
        ),
      ),
    );

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Attendance History'),
        backgroundColor: AppColors.surface,
        elevation: 0,
      ),
      body: Column(
        children: [
          // Search bar
          _buildSearchBar(),

          // Filters
          _buildFilterSection(coursesAsync),

          // History list
          Expanded(
            child: historyAsync.when(
              data: (records) {
                // Filter by search query
                final filteredRecords = _searchQuery.isEmpty
                    ? records
                    : records
                        .where((r) =>
                            r.studentName.toLowerCase().contains(
                                  _searchQuery.toLowerCase(),
                                ) ||
                            r.studentId.toLowerCase().contains(
                                  _searchQuery.toLowerCase(),
                                ))
                        .toList();

                return filteredRecords.isEmpty
                    ? _buildEmptyState()
                    : _buildRecordsList(filteredRecords);
              },
              loading: () => _buildLoadingState(),
              error: (e, _) => _buildErrorState(() {
                ref.refresh(
                  attendanceHistoryProvider(
                    AttendanceHistoryFilter(
                      courseId: _selectedCourseId,
                      startDate: _startDate,
                      endDate: _endDate,
                      page: _currentPage,
                      limit: _itemsPerPage,
                    ),
                  ),
                );
              }),
            ),
          ),
        ],
      ),
    );
  }

  /// Build search bar
  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: TextField(
        controller: _searchController,
        onChanged: (value) {
          setState(() => _searchQuery = value);
        },
        decoration: InputDecoration(
          hintText: 'Search by name or ID...',
          prefixIcon: const Icon(Icons.search, color: AppColors.grey400),
          suffixIcon: _searchQuery.isNotEmpty
              ? GestureDetector(
                  onTap: () {
                    _searchController.clear();
                    setState(() => _searchQuery = '');
                  },
                  child: const Icon(Icons.clear, color: AppColors.grey400),
                )
              : null,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: AppColors.grey200),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: AppColors.grey200),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: AppColors.primary),
          ),
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
      ),
    );
  }

  /// Build filter section
  Widget _buildFilterSection(AsyncValue<List<dynamic>> coursesAsync) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Course filter
          if (coursesAsync.hasValue) ...[
            Text(
              'Filter by Course',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 8),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: FilterChip(
                      label: const Text('All'),
                      selected: _selectedCourseId == null,
                      onSelected: (_) {
                        setState(() {
                          _selectedCourseId = null;
                          _currentPage = 1;
                        });
                      },
                    ),
                  ),
                  ...coursesAsync.whenData((courses) {
                    return courses.map((course) {
                      return Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: FilterChip(
                          label: Text(course.code ?? 'Course'),
                          selected: _selectedCourseId == course.id,
                          onSelected: (_) {
                            setState(() {
                              _selectedCourseId = course.id;
                              _currentPage = 1;
                            });
                          },
                        ),
                      );
                    }).toList();
                  }).value ?? [],
                ],
              ),
            ),
          ],

          const SizedBox(height: 12),

          // Date range filter
          Row(
            children: [
              // Start date
              Expanded(
                child: _buildDateButton(
                  label: 'From',
                  date: _startDate,
                  onTap: () => _selectStartDate(context),
                ),
              ),
              const SizedBox(width: 12),

              // End date
              Expanded(
                child: _buildDateButton(
                  label: 'To',
                  date: _endDate,
                  onTap: () => _selectEndDate(context),
                ),
              ),

              const SizedBox(width: 8),

              // Reset button
              GestureDetector(
                onTap: () {
                  setState(() {
                    _endDate = DateTime.now();
                    _startDate =
                        DateTime.now().subtract(const Duration(days: 30));
                  });
                },
                child: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppColors.grey100,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.refresh,
                    color: AppColors.grey600,
                    size: 20,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// Build date button
  Widget _buildDateButton({
    required String label,
    required DateTime? date,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          border: Border.all(color: AppColors.grey200),
          borderRadius: BorderRadius.circular(8),
          color: AppColors.surface,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: const TextStyle(
                fontSize: 10,
                color: AppColors.grey500,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              date != null ? DateFormat('MMM dd').format(date) : 'Select',
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: AppColors.grey900,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Select start date
  Future<void> _selectStartDate(BuildContext context) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _startDate ?? DateTime.now(),
      firstDate: DateTime(2020),
      lastDate: _endDate ?? DateTime.now(),
    );

    if (picked != null) {
      setState(() {
        _startDate = picked;
        _currentPage = 1;
      });
    }
  }

  /// Select end date
  Future<void> _selectEndDate(BuildContext context) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _endDate ?? DateTime.now(),
      firstDate: _startDate ?? DateTime(2020),
      lastDate: DateTime.now(),
    );

    if (picked != null) {
      setState(() {
        _endDate = picked;
        _currentPage = 1;
      });
    }
  }

  /// Build records list
  Widget _buildRecordsList(List<RealtimeAttendanceRecord> records) {
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
      itemCount: records.length + 1,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        if (index == records.length) {
          return _buildPaginationControls();
        }

        final record = records[index];
        return AttendanceRecordCard(
          studentName: record.studentName,
          studentId: record.studentId,
          status: record.status,
          markedAt: record.markedAt,
          avatarUrl: record.avatarUrl,
          confidence: record.confidence,
        );
      },
    );
  }

  /// Build pagination controls
  Widget _buildPaginationControls() {
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          ElevatedButton.icon(
            onPressed: _currentPage > 1
                ? () {
                    setState(() => _currentPage--);
                  }
                : null,
            icon: const Icon(Icons.chevron_left),
            label: const Text('Previous'),
          ),
          const SizedBox(width: 16),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: AppColors.primary.withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              'Page $_currentPage',
              style: const TextStyle(
                fontWeight: FontWeight.w600,
                color: AppColors.primary,
              ),
            ),
          ),
          const SizedBox(width: 16),
          ElevatedButton.icon(
            onPressed: () {
              setState(() => _currentPage++);
            },
            icon: const Icon(Icons.chevron_right),
            label: const Text('Next'),
          ),
        ],
      ),
    );
  }

  /// Build loading state
  Widget _buildLoadingState() {
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
      itemCount: 6,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (_, __) => Container(
        height: 80,
        decoration: BoxDecoration(
          color: AppColors.grey100,
          borderRadius: BorderRadius.circular(12),
        ),
      ),
    );
  }

  /// Build empty state
  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.history,
            size: 48,
            color: AppColors.grey300,
          ),
          const SizedBox(height: 16),
          Text(
            'No attendance records',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: AppColors.grey600,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Try adjusting your filters',
            style: TextStyle(
              fontSize: 14,
              color: AppColors.grey500,
            ),
          ),
        ],
      ),
    );
  }

  /// Build error state
  Widget _buildErrorState(VoidCallback onRetry) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.error_outline,
            size: 48,
            color: AppColors.error,
          ),
          const SizedBox(height: 16),
          const Text('Failed to load history'),
          const SizedBox(height: 12),
          ElevatedButton(
            onPressed: onRetry,
            child: const Text('Try again'),
          ),
        ],
      ),
    );
  }
}
