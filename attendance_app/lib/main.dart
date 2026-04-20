import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:firebase_core/firebase_core.dart';
import 'firebase_options.dart';
import 'package:smart_attendance/theme/app_theme.dart';
import 'package:smart_attendance/services/firebase_services.dart';
import 'package:smart_attendance/services/firebase_auth_service.dart';
import 'package:smart_attendance/screens/login_screen.dart';
import 'package:smart_attendance/screens/home_screen.dart';
import 'package:smart_attendance/screens/profile_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  try {
    // Initialize Firebase
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    );

    // Initialize Firebase services
    await initializeFirebaseServices();
  } catch (e) {
    debugPrint('Firebase initialization error: $e');
  }

  // Lock to portrait orientation
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // Style the system status bar
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
    ),
  );

  runApp(
    const ProviderScope(
      child: SmartAttendanceApp(),
    ),
  );
}

class SmartAttendanceApp extends ConsumerWidget {
  const SmartAttendanceApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authService = FirebaseAuthService();

    return StreamBuilder(
      stream: authService.authStateChanges,
      builder: (context, snapshot) {
        return MaterialApp(
          title: 'AttendMate Mobile',
          debugShowCheckedModeBanner: false,
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.darkTheme,
          themeMode: ThemeMode.light,
          onGenerateRoute: _generateRoute,
          home: snapshot.connectionState == ConnectionState.waiting
              ? const Scaffold(
                  body: Center(child: CircularProgressIndicator()),
                )
              : snapshot.hasData
                  ? const HomeScreen()
                  : const LoginScreen(),
        );
      },
    );
  }

  static Route<dynamic> _generateRoute(RouteSettings settings) {
    switch (settings.name) {
      case '/login':
        return MaterialPageRoute(builder: (_) => const LoginScreen());
      case '/home':
        return MaterialPageRoute(builder: (_) => const HomeScreen());
      case '/profile':
        return MaterialPageRoute(builder: (_) => const ProfileScreen());
      case '/camera':
        return MaterialPageRoute(
          builder: (_) => const Scaffold(
            body: Center(child: Text('Camera Screen - Coming Soon')),
          ),
        );
      case '/qr-scanner':
        return MaterialPageRoute(
          builder: (_) => const Scaffold(
            body: Center(child: Text('QR Scanner - Coming Soon')),
          ),
        );
      default:
        return MaterialPageRoute(
          builder: (_) => const LoginScreen(),
        );
    }
  }
}

