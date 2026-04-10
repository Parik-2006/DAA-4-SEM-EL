/// Central location for app-wide constants, keys, and config values.
class AppConstants {
  // Storage keys
  static const String tokenKey = 'access_token';
  static const String refreshTokenKey = 'refresh_token';
  static const String userCacheKey = 'cached_user';
  static const String themeKey = 'app_theme';
  static const String onboardedKey = 'onboarded';

  // Attendance thresholds
  static const double minAttendancePercentage = 75.0;
  static const double warningAttendancePercentage = 60.0;

  // Pagination
  static const int defaultPageSize = 20;

  // QR session
  static const int qrExpiryMinutes = 10;

  // Animation durations
  static const Duration shortAnimation = Duration(milliseconds: 200);
  static const Duration mediumAnimation = Duration(milliseconds: 350);
  static const Duration longAnimation = Duration(milliseconds: 600);

  // App info
  static const String appName = 'AttendAI';
  static const String appVersion = '1.0.0';
}
