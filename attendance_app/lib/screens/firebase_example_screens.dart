import 'package:flutter/material.dart';
import 'package:smart_attendance/services/firebase_services.dart';

/// Example Login Screen with Proper Exception Handling
class LoginScreenExample extends StatefulWidget {
  const LoginScreenExample({Key? key}) : super(key: key);

  @override
  State<LoginScreenExample> createState() => _LoginScreenExampleState();
}

class _LoginScreenExampleState extends State<LoginScreenExample> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _authService = FirebaseAuthService();
  
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  /// Handle login with comprehensive error handling
  Future<void> _handleLogin() async {
    // Clear previous error
    setState(() => _errorMessage = null);

    // Validate inputs
    if (_emailController.text.isEmpty || _passwordController.text.isEmpty) {
      _showError('Please fill in all fields');
      return;
    }

    setState(() => _isLoading = true);

    try {
      await _authService.signIn(
        email: _emailController.text,
        password: _passwordController.text,
      );

      // Success - navigate to home
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Login successful!')),
        );
        // Navigate to home screen
        // Navigator.of(context).pushReplacementNamed('/home');
      }
    } on FirebaseException catch (e) {
      _showError(e.userMessage);

      // Log based on severity
      if (e.severity == ErrorSeverity.high) {
        debugPrint('HIGH SEVERITY ERROR: ${e.code} - ${e.message}');
        // Could send to analytics or error tracking service
      }
    } catch (e) {
      _showError('An unexpected error occurred: $e');
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  /// Show error message to user
  void _showError(String message) {
    setState(() => _errorMessage = message);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Login')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Email field
            TextField(
              controller: _emailController,
              keyboardType: TextInputType.emailAddress,
              decoration: InputDecoration(
                labelText: 'Email',
                hintText: 'user@example.com',
                errorText: _errorMessage,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
              enabled: !_isLoading,
            ),
            const SizedBox(height: 16),

            // Password field
            TextField(
              controller: _passwordController,
              obscureText: true,
              decoration: InputDecoration(
                labelText: 'Password',
                hintText: 'Enter your password',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
              enabled: !_isLoading,
            ),
            const SizedBox(height: 24),

            // Login button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _isLoading ? null : _handleLogin,
                child: _isLoading
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            Colors.white,
                          ),
                        ),
                      )
                    : const Text('Login'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Example Student Attendance Screen with Error Handling
class AttendanceScreenExample extends StatefulWidget {
  const AttendanceScreenExample({Key? key}) : super(key: key);

  @override
  State<AttendanceScreenExample> createState() =>
      _AttendanceScreenExampleState();
}

class _AttendanceScreenExampleState extends State<AttendanceScreenExample> {
  final _firestoreService = FirebaseFirestoreService();
  final _storageService = FirebaseStorageService();

  List<StudentModel>? _students;
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadStudents();
  }

  /// Load students with error handling
  Future<void> _loadStudents() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final students = await _firestoreService.getAllStudents();
      setState(() => _students = students);
    } on FirebaseException catch (e) {
      setState(() => _error = e.userMessage);
      _showErrorDialog(e.userMessage);
    } catch (e) {
      setState(() => _error = 'Failed to load students');
      _showErrorDialog('An unexpected error occurred');
    } finally {
      setState(() => _isLoading = false);
    }
  }

  /// Mark attendance with error handling
  Future<void> _markAttendance(
    StudentModel student, {
    required String photoUrl,
  }) async {
    try {
      final record = AttendanceRecordModel(
        studentId: student.id!,
        courseId: student.courseId,
        date: DateTime.now(),
        isPresent: true,
        photoUrl: photoUrl,
      );

      final recordId = await _firestoreService.recordAttendance(record);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Attendance marked for ${student.name}'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } on FirebaseException catch (e) {
      _showErrorDialog(e.userMessage);
    } catch (e) {
      _showErrorDialog('Failed to mark attendance');
    }
  }

  /// Show error dialog
  void _showErrorDialog(String message) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Error'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    if (_error != null) {
      return Scaffold(
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 64, color: Colors.red),
              const SizedBox(height: 16),
              Text(_error!),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _loadStudents,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Mark Attendance')),
      body: _students == null || _students!.isEmpty
          ? const Center(
              child: Text('No students found'),
            )
          : ListView.builder(
              itemCount: _students!.length,
              itemBuilder: (context, index) {
                final student = _students![index];
                return Card(
                  margin: const EdgeInsets.all(8),
                  child: ListTile(
                    title: Text(student.name),
                    subtitle: Text(student.rollNumber),
                    trailing: ElevatedButton(
                      onPressed: () {
                        // Handle attendance marking
                        _markAttendance(
                          student,
                          photoUrl: student.photoUrl ?? '',
                        );
                      },
                      child: const Text('Mark Present'),
                    ),
                  ),
                );
              },
            ),
    );
  }
}
