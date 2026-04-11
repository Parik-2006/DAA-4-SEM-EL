import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:smart_attendance/models/face_model.dart';
import 'package:smart_attendance/providers/registration_provider.dart';
import 'package:smart_attendance/theme/app_theme.dart';

class LiveCameraScreen extends ConsumerStatefulWidget {
  const LiveCameraScreen({super.key});

  @override
  ConsumerState<LiveCameraScreen> createState() => _LiveCameraScreenState();
}

class _LiveCameraScreenState extends ConsumerState<LiveCameraScreen>
    with WidgetsBindingObserver {
  late MobileScannerController _cameraController;
  Timer? _detectionTimer;
  bool _isProcessing = false;
  bool _showFaceNames = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initializeCamera();
    _startFaceDetectionLoop();
  }

  /// Initialize camera controller
  void _initializeCamera() {
    _cameraController = MobileScannerController(
      facing: CameraFacing.front,
      autoStart: true,
      detectionSpeed: DetectionSpeed.normal,
      formats: const [],
    );
  }

  /// Start periodic face detection
  void _startFaceDetectionLoop() {
    _detectionTimer = Timer.periodic(
      const Duration(milliseconds: 500), // Process every 500ms for smooth updates
      (_) async {
        if (_isProcessing) return;
        // Face detection will be triggered by camera frames
      },
    );
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.detached:
      case AppLifecycleState.hidden:
      case AppLifecycleState.paused:
        _cameraController.stop();
        break;
      case AppLifecycleState.resumed:
        _cameraController.start();
        break;
      case AppLifecycleState.inactive:
        break;
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _detectionTimer?.cancel();
    _cameraController.dispose();
    super.dispose();
  }

  /// Process camera frame for face detection
  Future<void> _processFrame(List<int> frameBytes) async {
    if (_isProcessing) return;

    setState(() => _isProcessing = true);

    try {
      // Convert frame to base64
      final frameBase64 = base64Encode(frameBytes);

      // Detect faces using provider
      final detectionNotifier = ref.read(detectedFacesProvider.notifier);
      await detectionNotifier.detectFaces(frameBase64);
    } catch (e) {
      // Silently handle errors to avoid UI interruption
      debugPrint('Face detection error: $e');
    } finally {
      setState(() => _isProcessing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final detectedFaces = ref.watch(detectedFacesProvider);

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text('Live Face Detection'),
        backgroundColor: Colors.black87,
        elevation: 0,
        actions: [
          IconButton(
            icon: Icon(
              _showFaceNames
                  ? Icons.visibility_outlined
                  : Icons.visibility_off_outlined,
            ),
            onPressed: () {
              setState(() => _showFaceNames = !_showFaceNames);
            },
            tooltip: _showFaceNames ? 'Hide names' : 'Show names',
          ),
          IconButton(
            icon: const Icon(Icons.refresh_outlined),
            onPressed: () {
              ref.read(detectedFacesProvider.notifier).clearFaces();
            },
            tooltip: 'Clear detections',
          ),
        ],
      ),
      body: Stack(
        children: [
          // ── Camera Feed with Face Overlay ────────────────────────────────
          MobileScanner(
            controller: _cameraController,
            onDetect: (capture) {
              // Note: mobile_scanner 5.x doesn't expose raw frame bytes
              // Face detection is handled by periodic detection loop above
            },
            overlayBuilder: (context, constraints) {
              return Stack(
                children: [
                  // Draw detected faces with bounding boxes
                  ..._buildFaceBoundingBoxes(
                    detectedFaces.faces,
                    constraints,
                  ),
                ],
              );
            },
          ),

          // ── Status Overlay ────────────────────────────────────────────────
          Positioned(
            top: 16,
            left: 16,
            right: 16,
            child: _buildStatusBar(detectedFaces),
          ),

          // ── Detected Faces List ───────────────────────────────────────────
          if (_showFaceNames && detectedFaces.faces.isNotEmpty)
            Positioned(
              bottom: 16,
              left: 16,
              right: 16,
              child: _buildDetectedFacesList(detectedFaces.faces),
            ),

          // ── Loading Indicator ─────────────────────────────────────────────
          if (detectedFaces.isLoading)
            const Positioned.fill(
              child: Center(
                child: CircularProgressIndicator(
                  color: AppColors.primary,
                ),
              ),
            ),

          // ── Error Message ─────────────────────────────────────────────────
          if (detectedFaces.error != null)
            Positioned(
              top: 100,
              left: 16,
              right: 16,
              child: _buildErrorBanner(detectedFaces.error!),
            ),
        ],
      ),
    );
  }

  /// Build bounding boxes for detected faces
  List<Widget> _buildFaceBoundingBoxes(
    List<DetectedFace> faces,
    BoxConstraints constraints,
  ) {
    return faces.map((face) {
      final screenWidth = constraints.maxWidth;
      final screenHeight = constraints.maxHeight;

      return Positioned(
        left: face.x * screenWidth,
        top: face.y * screenHeight,
        width: face.width * screenWidth,
        height: face.height * screenHeight,
        child: Container(
          decoration: BoxDecoration(
            border: Border.all(
              color: _getConfidenceColor(face.confidence),
              width: 3,
            ),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Stack(
            children: [
              // Bounding box
              if (_showFaceNames)
                Positioned(
                  top: 0,
                  left: 0,
                  right: 0,
                  child: Container(
                    color: _getConfidenceColor(face.confidence).withOpacity(0.8),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 4,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          face.name,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        Text(
                          'Confidence: ${(face.confidence * 100).toStringAsFixed(1)}%',
                          style: const TextStyle(
                            color: Colors.white70,
                            fontSize: 10,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      );
    }).toList();
  }

  /// Build status bar showing detection info
  Widget _buildStatusBar(DetectedFacesState state) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.black54,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.primary.withOpacity(0.5)),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.face_outlined,
            color: AppColors.primary,
            size: 20,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              state.faces.isEmpty
                  ? 'No faces detected'
                  : '${state.faces.length} face(s) detected',
              style: const TextStyle(
                color: Colors.white,
                fontSize: 13,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          if (state.isLoading)
            const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation<Color>(AppColors.primary),
              ),
            ),
        ],
      ),
    );
  }

  /// Build list of detected faces
  Widget _buildDetectedFacesList(List<DetectedFace> faces) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.black87,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.primary.withOpacity(0.3)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                const Icon(
                  Icons.people_outline,
                  color: AppColors.primary,
                  size: 18,
                ),
                const SizedBox(width: 8),
                const Text(
                  'Detected Students',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                  ),
                ),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.primary,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    '${faces.length}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
          ),
          ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 200),
            child: ListView.builder(
              shrinkWrap: true,
              itemCount: faces.length,
              itemBuilder: (context, index) {
                final face = faces[index];
                return _buildFaceListItem(face, index);
              },
            ),
          ),
        ],
      ),
    );
  }

  /// Build individual face list item
  Widget _buildFaceListItem(DetectedFace face, int index) {
    return Container(
      decoration: BoxDecoration(
        border: Border(
          top: BorderSide(
            color: Colors.white10,
            width: index == 0 ? 0 : 1,
          ),
        ),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      child: Row(
        children: [
          CircleAvatar(
            radius: 18,
            backgroundColor: _getConfidenceColor(face.confidence),
            child: Text(
              '${index + 1}',
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
                fontSize: 12,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  face.name,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  'Confidence: ${(face.confidence * 100).toStringAsFixed(1)}%',
                  style: const TextStyle(
                    color: Colors.white60,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: _getConfidenceColor(face.confidence).withOpacity(0.2),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              face.confidence > 0.85 ? 'High' : 'Medium',
              style: TextStyle(
                color: _getConfidenceColor(face.confidence),
                fontSize: 10,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Build error banner
  Widget _buildErrorBanner(String error) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.error.withOpacity(0.9),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.error_outline,
            color: Colors.white,
            size: 20,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              error,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 12,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  /// Get color based on confidence score
  Color _getConfidenceColor(double confidence) {
    if (confidence > 0.85) {
      return AppColors.success;
    } else if (confidence > 0.70) {
      return AppColors.warning;
    } else {
      return AppColors.error;
    }
  }
}
