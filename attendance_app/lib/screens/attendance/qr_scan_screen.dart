import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:smart_attendance/providers/attendance_provider.dart';
import 'package:smart_attendance/theme/app_theme.dart';

/// QR scan screen for marking attendance.
/// Integrates with mobile_scanner package in production.
class QrScanScreen extends ConsumerStatefulWidget {
  const QrScanScreen({super.key});

  @override
  ConsumerState<QrScanScreen> createState() => _QrScanScreenState();
}

class _QrScanScreenState extends ConsumerState<QrScanScreen> {
  bool _scanned = false;

  void _onQrDetected(String qrToken) async {
    if (_scanned) return;
    setState(() => _scanned = true);

    await ref.read(qrMarkingProvider.notifier).markWithQr(qrToken);
  }

  @override
  Widget build(BuildContext context) {
    final markingState = ref.watch(qrMarkingProvider);

    // Navigate back after success
    ref.listen(qrMarkingProvider, (prev, next) {
      if (next.isSuccess) {
        _showSuccessSheet(context, next.result?.courseName ?? 'the course');
      }
    });

    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          // ── Camera preview placeholder ──────────────────────────────────
          // In production, replace with MobileScanner widget:
          //
          // MobileScanner(
          //   onDetect: (capture) {
          //     final barcode = capture.barcodes.first;
          //     if (barcode.rawValue != null) {
          //       _onQrDetected(barcode.rawValue!);
          //     }
          //   },
          // ),
          //
          Container(
            color: const Color(0xFF1A1A2E),
            child: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    Icons.camera_alt_outlined,
                    color: Colors.white.withOpacity(0.3),
                    size: 64,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Camera preview\n(MobileScanner plugin)',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.4),
                      fontFamily: 'Sora',
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
          ),

          // ── Scan overlay ────────────────────────────────────────────────
          SafeArea(
            child: Column(
              children: [
                // Top bar
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  child: Row(
                    children: [
                      IconButton(
                        onPressed: () => context.pop(),
                        icon: const Icon(
                          Icons.close_rounded,
                          color: Colors.white,
                          size: 24,
                        ),
                      ),
                      const Spacer(),
                      const Text(
                        'Scan QR Code',
                        style: TextStyle(
                          fontFamily: 'Sora',
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const Spacer(),
                      const SizedBox(width: 48),
                    ],
                  ),
                ),

                const Spacer(),

                // Scan frame
                _ScanFrame(isLoading: markingState.isLoading),

                const SizedBox(height: 32),

                Text(
                  markingState.isLoading
                      ? 'Marking your attendance...'
                      : 'Point your camera at the\nlecturer\'s QR code',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontFamily: 'Sora',
                    color: Colors.white,
                    fontSize: 15,
                    height: 1.5,
                  ),
                ),

                // Error message
                if (markingState.errorMessage != null) ...[
                  const SizedBox(height: 16),
                  Container(
                    margin: const EdgeInsets.symmetric(horizontal: 40),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.error.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: AppColors.error.withOpacity(0.4),
                      ),
                    ),
                    child: Text(
                      markingState.errorMessage!,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        fontFamily: 'Sora',
                        color: Colors.white,
                        fontSize: 13,
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextButton(
                    onPressed: () {
                      setState(() => _scanned = false);
                      ref.read(qrMarkingProvider.notifier).reset();
                    },
                    child: const Text(
                      'Try again',
                      style: TextStyle(
                        color: Colors.white,
                        fontFamily: 'Sora',
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],

                const Spacer(),

                // Manual entry button
                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 0, 24, 32),
                  child: OutlinedButton(
                    onPressed: () => _showManualEntry(context),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.white,
                      side: const BorderSide(color: Colors.white54),
                      minimumSize: const Size(double.infinity, 52),
                    ),
                    child: const Text('Enter code manually'),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _showSuccessSheet(BuildContext context, String courseName) {
    showModalBottomSheet(
      context: context,
      isDismissible: false,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: AppColors.success.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.check_circle_rounded,
                color: AppColors.success,
                size: 40,
              ),
            ),
            const SizedBox(height: 16),
            const Text(
              'Attendance Marked!',
              style: TextStyle(
                fontFamily: 'Sora',
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: AppColors.grey900,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'You have been marked present for $courseName.',
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontFamily: 'Sora',
                fontSize: 14,
                color: AppColors.grey600,
              ),
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  Navigator.pop(context);
                  context.pop();
                },
                child: const Text('Done'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showManualEntry(BuildContext context) {
    final ctrl = TextEditingController();
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => Padding(
        padding: EdgeInsets.fromLTRB(
          24,
          24,
          24,
          MediaQuery.of(context).viewInsets.bottom + 24,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Enter session code',
              style: TextStyle(
                fontFamily: 'Sora',
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: ctrl,
              decoration: const InputDecoration(
                hintText: 'e.g. ATT-2024-ABCD',
                label: Text('Session code'),
              ),
              textCapitalization: TextCapitalization.characters,
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  if (ctrl.text.isNotEmpty) {
                    Navigator.pop(context);
                    _onQrDetected(ctrl.text.trim());
                  }
                },
                child: const Text('Submit'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ScanFrame extends StatelessWidget {
  final bool isLoading;

  const _ScanFrame({required this.isLoading});

  @override
  Widget build(BuildContext context) {
    return Stack(
      alignment: Alignment.center,
      children: [
        // Dim overlay with frame cutout
        Container(
          width: 260,
          height: 260,
          decoration: BoxDecoration(
            border: Border.all(
              color: isLoading ? AppColors.warning : Colors.white,
              width: 3,
            ),
            borderRadius: BorderRadius.circular(20),
          ),
        ),
        // Corner accents
        ..._cornerAccents(isLoading ? AppColors.warning : AppColors.primary),
        if (isLoading)
          const CircularProgressIndicator(
            valueColor: AlwaysStoppedAnimation(Colors.white),
          ),
      ],
    );
  }

  List<Widget> _cornerAccents(Color color) {
    return [
      _corner(color, top: 0, left: 0),
      _corner(color, top: 0, right: 0, rotateY: true),
      _corner(color, bottom: 0, left: 0, rotateX: true),
      _corner(color, bottom: 0, right: 0, rotateX: true, rotateY: true),
    ];
  }

  Widget _corner(
    Color color, {
    double? top,
    double? bottom,
    double? left,
    double? right,
    bool rotateX = false,
    bool rotateY = false,
  }) {
    return Positioned(
      top: top,
      bottom: bottom,
      left: left,
      right: right,
      child: Transform(
        alignment: Alignment.center,
        transform: Matrix4.identity()
          ..scale(rotateY ? -1.0 : 1.0, rotateX ? -1.0 : 1.0),
        child: CustomPaint(
          size: const Size(28, 28),
          painter: _CornerPainter(color: color),
        ),
      ),
    );
  }
}

class _CornerPainter extends CustomPainter {
  final Color color;
  const _CornerPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 4
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final path = Path()
      ..moveTo(0, size.height * 0.6)
      ..lineTo(0, 0)
      ..lineTo(size.width * 0.6, 0);

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(_CornerPainter old) => old.color != color;
}
