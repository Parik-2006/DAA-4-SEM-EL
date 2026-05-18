"""
Image preprocessing utilities.

Provides functions for image normalization, face alignment, color conversion,
and other image processing operations required for face recognition.
"""

from typing import Tuple, Optional
import logging

import cv2
import numpy as np


logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """
    Image preprocessing utilities for face recognition pipeline.
    
    Handles image normalization, resizing, color conversion, and
    face region extraction.
    """
    
    @staticmethod
    def load_image(image_path: str) -> Optional[np.ndarray]:
        """
        Load image from file.
        
        Args:
            image_path: Path to image file
        
        Returns:
            Image as numpy array (BGR format) or None if load fails
        """
        try:
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"Failed to load image: {image_path}")
                return None
            return image
        except Exception as e:
            logger.error(f"Error loading image {image_path}: {e}")
            return None
    
    @staticmethod
    def resize_image(
        image: np.ndarray,
        target_size: Tuple[int, int] = (640, 640),
        keep_aspect: bool = True
    ) -> np.ndarray:
        """
        Resize image to target size.
        
        Args:
            image: Input image
            target_size: Target (width, height)
            keep_aspect: Keep aspect ratio by padding if True
        
        Returns:
            Resized image
        """
        if keep_aspect:
            return ImagePreprocessor._resize_with_padding(image, target_size)
        else:
            return cv2.resize(image, target_size, interpolation=cv2.INTER_LINEAR)
    
    @staticmethod
    def _resize_with_padding(
        image: np.ndarray,
        target_size: Tuple[int, int]
    ) -> np.ndarray:
        """
        Resize image while keeping aspect ratio and add padding.
        
        Args:
            image: Input image
            target_size: Target (width, height)
        
        Returns:
            Resized image with padding
        """
        h, w = image.shape[:2]
        target_w, target_h = target_size
        
        # Calculate scaling factor
        scale = min(target_w / w, target_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        # Resize image
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # Create canvas with padding
        canvas = np.zeros((target_h, target_w, image.shape[2]), dtype=image.dtype)
        
        # Calculate padding
        pad_top = (target_h - new_h) // 2
        pad_left = (target_w - new_w) // 2
        
        # Place resized image on canvas
        canvas[pad_top:pad_top + new_h, pad_left:pad_left + new_w] = resized
        
        return canvas
    
    @staticmethod
    def bgr_to_rgb(image: np.ndarray) -> np.ndarray:
        """
        Convert BGR image to RGB.
        
        Args:
            image: Image in BGR format
        
        Returns:
            Image in RGB format
        """
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    @staticmethod
    def rgb_to_bgr(image: np.ndarray) -> np.ndarray:
        """
        Convert RGB image to BGR.
        
        Args:
            image: Image in RGB format
        
        Returns:
            Image in BGR format
        """
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    
    @staticmethod
    def to_grayscale(image: np.ndarray) -> np.ndarray:
        """
        Convert image to grayscale.
        
        Args:
            image: Input image (BGR or RGB)
        
        Returns:
            Grayscale image
        """
        if len(image.shape) == 2:
            return image  # Already grayscale
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    @staticmethod
    def normalize_image(image: np.ndarray, to_range: Tuple[int, int] = (0, 1)) -> np.ndarray:
        """
        Normalize image pixel values.
        
        Args:
            image: Input image
            to_range: Target range (min, max)
        
        Returns:
            Normalized image
        """
        image = image.astype(np.float32)
        
        if to_range == (0, 1):
            return image / 255.0
        elif to_range == (-1, 1):
            return (image / 127.5) - 1.0
        else:
            min_val, max_val = to_range
            current_min = image.min()
            current_max = image.max()
            
            if current_max == current_min:
                return image
            
            normalized = (image - current_min) / (current_max - current_min)
            return normalized * (max_val - min_val) + min_val
    
    @staticmethod
    def extract_face_region(
        image: np.ndarray,
        bbox: Tuple[float, float, float, float],
        padding_percent: float = 0.2
    ) -> np.ndarray:
        """
        Extract face region from image with optional padding.
        
        Args:
            image: Input image
            bbox: Bounding box (x1, y1, x2, y2)
            padding_percent: Percentage padding around face (0.2 = 20%)
        
        Returns:
            Extracted face region
        """
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h, w = image.shape[:2]
        
        # Calculate padding
        pad_x = int((x2 - x1) * padding_percent)
        pad_y = int((y2 - y1) * padding_percent)
        
        # Apply padding with bounds checking
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(w, x2 + pad_x)
        y2 = min(h, y2 + pad_y)
        
        return image[y1:y2, x1:x2]
    
    @staticmethod
    def draw_bbox(
        image: np.ndarray,
        bbox: Tuple[float, float, float, float],
        label: str = "",
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2
    ) -> np.ndarray:
        """
        Draw bounding box on image.
        
        Args:
            image: Input image
            bbox: Bounding box (x1, y1, x2, y2)
            label: Label text to display
            color: Box color (BGR)
            thickness: Line thickness
        
        Returns:
            Image with drawn bbox
        """
        x1, y1, x2, y2 = [int(v) for v in bbox]
        
        # Draw rectangle
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)
        
        # Draw label if provided
        if label:
            text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
            cv2.rectangle(
                image,
                (x1, y1 - text_size[1] - 5),
                (x1 + text_size[0] + 5, y1),
                color,
                -1
            )
            cv2.putText(
                image,
                label,
                (x1 + 2, y1 - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                1
            )
        
        return image
    
    @staticmethod
    def get_image_info(image: np.ndarray) -> dict:
        """
        Get image metadata.
        
        Args:
            image: Input image
        
        Returns:
            Dictionary with image info
        """
        h, w = image.shape[:2]
        channels = 1 if len(image.shape) == 2 else image.shape[2]
        
        return {
            "width": w,
            "height": h,
            "channels": channels,
            "dtype": str(image.dtype),
            "size_mb": image.nbytes / (1024 * 1024),
        }


# ── Face quality analysis ─────────────────────────────────────────────────────

class FaceQualityAnalyzer:
    """
    Cheap, compute-bounded face quality analysis.

    All methods are static and operate on a single cropped face image.
    Total per-face cost: one grayscale conversion + one Laplacian kernel pass
    (~10–50 µs on a 160×160 crop, well within real-time budgets).

    Frontality heuristic
    --------------------
    A fully frontal face detected by YOLO occupies an approximately square
    bounding box: the width-to-height aspect ratio (AR) is typically in the
    range [0.70, 1.15].  Side-profile detections are narrower (AR < 0.55)
    and partial 3/4-profiles fall between.  Because the face crop itself
    inherits the bbox shape, we measure AR directly on the crop rather than
    re-querying the original bbox — no extra arguments needed.

    We further reinforce the heuristic with a horizontal-symmetry check:
    the difference in mean brightness between the left and right halves of
    a frontal face is small; large asymmetry signals a profile or angled pose.
    The symmetry term adds one additional array split and mean computation
    (nanoseconds).

    Sharpness heuristic
    -------------------
    Laplacian variance is a standard no-reference blur detector.  A blurred
    face (motion shake, out-of-focus) produces a low variance; a sharp face
    produces a high one.  We normalise by face area so that small faces
    (farther from the camera) are not unfairly penalised: smaller crops have
    intrinsically lower variance because fewer high-frequency details are
    resolved, but that is a resolution effect, not a blur effect.
    """

    # ── Tunable thresholds ────────────────────────────────────────────────────

    # Aspect-ratio window for a frontal detection.
    # Faces wider or taller than these bounds are likely angled or partially
    # occluded.
    FRONTAL_AR_LOW:  float = 0.70
    FRONTAL_AR_HIGH: float = 1.15

    # Maximum allowed left/right brightness asymmetry (normalised 0-1 scale).
    # Values above this suggest a profile or strong directional lighting.
    SYMMETRY_MAX_DIFF: float = 0.12

    # Laplacian variance thresholds (normalised by pixel count).
    # SHARP  >= SHARP_THRESHOLD
    # SOFT   in [SOFT_THRESHOLD, SHARP_THRESHOLD)
    # BLURRY <  SOFT_THRESHOLD
    SHARP_THRESHOLD: float = 0.012
    SOFT_THRESHOLD:  float = 0.004

    # Composite score tier cut-offs (score is in [0, 1]).
    HIGH_SCORE_MIN:       float = 0.72
    ACCEPTABLE_SCORE_MIN: float = 0.42

    # ── Public API ────────────────────────────────────────────────────────────

    @staticmethod
    def frontality_score(face_image: np.ndarray) -> float:
        """
        Estimate how frontal a face is from its crop alone.

        Returns a float in [0.0, 1.0] where 1.0 is perfectly frontal.

        Algorithm (all O(pixels), no ML model required)
        ------------------------------------------------
        1. Aspect-ratio term  (weight 0.65)
           Map the crop's width/height ratio onto a tent function centred on
           the ideal frontal AR of ~0.90.  AR inside [FRONTAL_AR_LOW,
           FRONTAL_AR_HIGH] scores ≥ 0; outside falls off linearly to 0.

        2. Horizontal symmetry term  (weight 0.35)
           Split the grayscale crop into left/right halves and compare mean
           brightness.  Small difference → high symmetry score.

        Args:
            face_image: Cropped face region, any channel count.
                        Does not need to be pre-normalised.

        Returns:
            Frontality score in [0.0, 1.0].
        """
        if face_image is None or face_image.size == 0:
            return 0.0

        h, w = face_image.shape[:2]
        if h == 0:
            return 0.0

        # ── Term 1: aspect-ratio ─────────────────────────────────────────────
        ar = w / h
        ideal_ar = (FaceQualityAnalyzer.FRONTAL_AR_LOW + FaceQualityAnalyzer.FRONTAL_AR_HIGH) / 2.0
        ar_range = (FaceQualityAnalyzer.FRONTAL_AR_HIGH - FaceQualityAnalyzer.FRONTAL_AR_LOW) / 2.0

        # Tent function: peaks at ideal_ar, falls to 0 at the low/high bounds
        ar_score = max(0.0, 1.0 - abs(ar - ideal_ar) / ar_range)

        # ── Term 2: horizontal symmetry ──────────────────────────────────────
        gray = (
            cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
            if face_image.ndim == 3
            else face_image.astype(np.float32)
        )
        mid = w // 2
        left_mean  = float(gray[:, :mid].mean())   / 255.0
        right_mean = float(gray[:, mid:].mean())   / 255.0
        diff = abs(left_mean - right_mean)
        sym_score = max(0.0, 1.0 - diff / FaceQualityAnalyzer.SYMMETRY_MAX_DIFF)
        sym_score = min(sym_score, 1.0)

        return float(0.65 * ar_score + 0.35 * sym_score)

    @staticmethod
    def sharpness_score(face_image: np.ndarray) -> float:
        """
        Estimate image sharpness via Laplacian variance normalised by face area.

        Returns a float in [0.0, 1.0].

        Normalisation rationale
        -----------------------
        Raw Laplacian variance scales roughly with image area (more pixels =
        more high-frequency energy).  Dividing by pixel count makes the
        threshold independent of crop resolution so a small but sharp face
        gets the same score as a large but equally sharp face.

        Args:
            face_image: Cropped face region (any channel count).

        Returns:
            Sharpness score in [0.0, 1.0].
        """
        if face_image is None or face_image.size == 0:
            return 0.0

        gray = (
            cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
            if face_image.ndim == 3
            else face_image
        )

        pixel_count = gray.shape[0] * gray.shape[1]
        if pixel_count == 0:
            return 0.0

        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        normalised = lap_var / pixel_count

        # Map onto [0, 1]: 0 at SOFT_THRESHOLD, 1 at SHARP_THRESHOLD
        low  = FaceQualityAnalyzer.SOFT_THRESHOLD
        high = FaceQualityAnalyzer.SHARP_THRESHOLD
        if high <= low:
            return 1.0 if normalised >= high else 0.0

        score = (normalised - low) / (high - low)
        return float(min(max(score, 0.0), 1.0))

    @staticmethod
    def composite_score(
        face_image:       np.ndarray,
        motion_magnitude: float = 0.0,
    ) -> float:
        """
        Compute a single composite quality score in [0.0, 1.0].

        Component weights
        -----------------
        - Frontality  : 0.45  (most important for embedding quality)
        - Sharpness   : 0.35  (motion blur / defocus degrades embeddings)
        - Stillness   : 0.20  (derived from ``motion_magnitude``)

        The stillness term penalises high-motion frames even when the face
        crop itself appears sharp — rapid pan can produce a momentarily sharp
        crop that will be blurry in the next frame, so discounting such frames
        stabilises enrollment selection.

        Args:
            face_image:       Cropped face region.
            motion_magnitude: Normalised motion level in [0.0, 1.0] from
                              ``MotionDetector`` (0 = perfectly still,
                              1 = maximum motion).  Pass 0.0 if unavailable.

        Returns:
            Composite score in [0.0, 1.0].
        """
        f_score = FaceQualityAnalyzer.frontality_score(face_image)
        s_score = FaceQualityAnalyzer.sharpness_score(face_image)
        still   = float(max(0.0, 1.0 - min(motion_magnitude, 1.0)))

        return float(0.45 * f_score + 0.35 * s_score + 0.20 * still)

    @classmethod
    def tier(cls, score: float) -> str:
        """
        Map a composite score to a quality tier label.

        Returns one of ``"HIGH"``, ``"ACCEPTABLE"``, or ``"LOW"``.
        """
        if score >= cls.HIGH_SCORE_MIN:
            return "HIGH"
        if score >= cls.ACCEPTABLE_SCORE_MIN:
            return "ACCEPTABLE"
        return "LOW"