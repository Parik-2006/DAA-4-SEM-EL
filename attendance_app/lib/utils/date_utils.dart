import 'package:intl/intl.dart';

extension DateTimeExtensions on DateTime {
  String get timeAgo {
    final now = DateTime.now();
    final diff = now.difference(this);

    if (diff.inSeconds < 60) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays == 1) return 'yesterday';
    if (diff.inDays < 7) return '${diff.inDays} days ago';
    return DateFormat('MMM d, y').format(this);
  }

  String get shortDate => DateFormat('MMM d').format(this);

  String get fullDate => DateFormat('EEEE, MMMM d, y').format(this);

  String get timeOfDay => DateFormat('h:mm a').format(this);

  String get dateTime => DateFormat('MMM d • h:mm a').format(this);

  bool get isToday {
    final now = DateTime.now();
    return year == now.year && month == now.month && day == now.day;
  }

  bool get isYesterday {
    final yesterday = DateTime.now().subtract(const Duration(days: 1));
    return year == yesterday.year &&
        month == yesterday.month &&
        day == yesterday.day;
  }

  String get relativeDay {
    if (isToday) return 'Today';
    if (isYesterday) return 'Yesterday';
    return DateFormat('EEEE, MMM d').format(this);
  }
}

class DateUtils {
  static List<DateTime> daysInRange(DateTime start, DateTime end) {
    final days = <DateTime>[];
    var current = start;
    while (!current.isAfter(end)) {
      days.add(current);
      current = current.add(const Duration(days: 1));
    }
    return days;
  }

  static DateTime startOfDay(DateTime date) =>
      DateTime(date.year, date.month, date.day);

  static DateTime endOfDay(DateTime date) =>
      DateTime(date.year, date.month, date.day, 23, 59, 59);

  static DateTime startOfWeek(DateTime date) {
    final weekday = date.weekday; // 1=Mon, 7=Sun
    return startOfDay(date.subtract(Duration(days: weekday - 1)));
  }

  static DateTime startOfMonth(DateTime date) =>
      DateTime(date.year, date.month);

  static DateTime endOfMonth(DateTime date) =>
      DateTime(date.year, date.month + 1, 0);
}
