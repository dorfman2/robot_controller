"""
Shared detection algorithms for the Armold vision system.

Contains pure-function detectors used by both the overhead and side camera
pipelines. All functions take a BGR frame (numpy array) and return structured
detection results.

Detection approaches:
    - Pen: flat-field background subtraction + elongation filter (classic CV).
    - Green marker: HSV thresholding for gripper-tape blobs.
    - Gripper-tip height: vertical edge/contour detection in the side view.
"""

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PenDetection:
    """Result of pen detection in a single frame.

    Attributes:
        center_px: (x, y) pixel coordinates of the pen center.
        angle_deg: Orientation of the pen long axis in degrees.
        box_points: 4 corner points of the oriented bounding box (pixel coords).
        long_side_px: Length of the long side in pixels.
        short_side_px: Length of the short side in pixels.
        confidence: Detection confidence score (elongation * sqrt(area)).
    """

    center_px: tuple[float, float]
    angle_deg: float
    box_points: np.ndarray
    long_side_px: float
    short_side_px: float
    confidence: float


@dataclass
class GreenMarkerDetection:
    """Result of green gripper-marker detection.

    Attributes:
        fingers: List of (x, y) finger-blob centroids (1 when closed, 2 open).
        center_px: (x, y) grasp midpoint (average of finger centroids).
        num_blobs: Number of green blobs detected (1 or 2).
    """

    fingers: list[tuple[float, float]]
    center_px: tuple[float, float]
    num_blobs: int


@dataclass
class GripperTipDetection:
    """Result of gripper-tip height detection from the side camera.

    Attributes:
        tip_y_px: Y pixel coordinate of the gripper tip (bottom of gripper).
        desk_y_px: Y pixel coordinate of the desk surface.
        gap_px: Vertical gap in pixels (desk_y - tip_y; positive = above desk).
        gap_mm: Gap in mm (after calibration), or None if uncalibrated.
    """

    tip_y_px: float
    desk_y_px: float
    gap_px: float
    gap_mm: float | None = None


# ---------------------------------------------------------------------------
# Pen detection (overhead)
# ---------------------------------------------------------------------------


def _long_axis_angle_deg(box: np.ndarray) -> float:
    """Return the long-axis orientation (deg, in [-90, 90)) of an oriented box.

    A version-robust alternative to ``cv2.minAreaRect``'s angle (whose range
    and width/height assignment vary across OpenCV versions): take the longest
    edge of the 4-corner box and return its angle, normalized to ``[-90, 90)``.
    Angles are in image coordinates (y points down); the caller maps to the arm
    frame during hand-eye calibration.

    Args:
        box: A ``(4, 2)`` array of oriented-box corner points (pixels).

    Returns:
        Long-axis angle in degrees, normalized to ``[-90, 90)``.
    """
    edges = [box[(i + 1) % 4] - box[i] for i in range(4)]
    lengths = [float(np.hypot(float(e[0]), float(e[1]))) for e in edges]
    longest = edges[int(np.argmax(lengths))]
    angle = float(np.degrees(np.arctan2(float(longest[1]), float(longest[0]))))
    return ((angle + 90.0) % 180.0) - 90.0


def detect_pen(
    frame: np.ndarray,
    roi_frac: tuple[float, float, float, float] = (0.20, 0.16, 0.60, 0.656),
    min_area_frac: float = 0.0003,
    max_area_frac: float = 0.05,
    min_elongation: float = 3.0,
) -> tuple[tuple[int, int, int, int], PenDetection | None]:
    """Detect a pen-like elongated object in a mat ROI using classic CV.

    Uses flat-field background subtraction (large Gaussian blur as pseudo-BG),
    Otsu thresholding, and elongation filtering to find the best candidate.

    Args:
        frame: BGR image (numpy H×W×3 array).
        roi_frac: (x0, y0, x1, y1) fractions defining the ROI within the frame.
        min_area_frac: Minimum contour area as fraction of total frame area.
        max_area_frac: Maximum contour area as fraction of total frame area.
        min_elongation: Minimum long/short ratio to qualify as a pen.

    Returns:
        Tuple of:
            - (x0, y0, x1, y1) pixel coordinates of the ROI rectangle.
            - PenDetection if found, else None.
    """
    h, w = frame.shape[:2]
    x0 = int(roi_frac[0] * w)
    y0 = int(roi_frac[1] * h)
    x1 = int(roi_frac[2] * w)
    y1 = int(roi_frac[3] * h)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    sub = cv2.GaussianBlur(gray[y0:y1, x0:x1], (5, 5), 0)
    bg = cv2.GaussianBlur(sub, (0, 0), sigmaX=max(9.0, 0.03 * w))
    diff = cv2.absdiff(sub, bg)
    diff = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX).astype("uint8")
    _, mask = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    frame_area = w * h
    best: PenDetection | None = None
    best_score = 0.0

    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area_frac * frame_area:
            continue
        if area > max_area_frac * frame_area:
            continue
        rect = cv2.minAreaRect(c)
        (cx, cy), (rw, rh), _rect_angle = rect
        long_side = max(rw, rh)
        short_side = max(min(rw, rh), 1.0)
        elong = long_side / short_side
        if elong < min_elongation:
            continue
        score = elong * float(np.sqrt(area))
        if score > best_score:
            best_score = score
            raw_box = cv2.boxPoints(rect)
            box = raw_box.astype(np.int32) + np.array([x0, y0])
            best = PenDetection(
                center_px=(cx + x0, cy + y0),
                angle_deg=_long_axis_angle_deg(raw_box),
                box_points=box,
                long_side_px=long_side,
                short_side_px=short_side,
                confidence=score,
            )

    return (x0, y0, x1, y1), best


# ---------------------------------------------------------------------------
# Green marker detection (shared)
# ---------------------------------------------------------------------------


#: Default green-tape HSV bounds (module-level singletons, avoid B008 call-in-default).
GREEN_LOWER_HSV: np.ndarray = np.array([35, 70, 50])
GREEN_UPPER_HSV: np.ndarray = np.array([90, 255, 255])


def detect_green_marker(
    frame: np.ndarray,
    lower_hsv: np.ndarray = GREEN_LOWER_HSV,
    upper_hsv: np.ndarray = GREEN_UPPER_HSV,
    min_area: int = 60,
) -> GreenMarkerDetection | None:
    """Detect green gripper-tape blobs and compute the grasp midpoint.

    Finds up to two green blobs (one per finger when open, one when closed).
    The grasp point is the centroid average.

    Args:
        frame: BGR image (numpy H×W×3 array).
        lower_hsv: Lower HSV bound for green (numpy array of 3).
        upper_hsv: Upper HSV bound for green (numpy array of 3).
        min_area: Minimum blob area in pixels to consider.

    Returns:
        GreenMarkerDetection if at least one blob found, else None.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_hsv, upper_hsv)
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    blobs: list[tuple[float, float, float]] = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        m = cv2.moments(c)
        if m["m00"] == 0:
            continue
        blobs.append((area, m["m10"] / m["m00"], m["m01"] / m["m00"]))

    if not blobs:
        return None

    # Take the two largest blobs (two fingers, or one closed finger)
    blobs.sort(key=lambda b: b[0], reverse=True)
    fingers = [(x, y) for _, x, y in blobs[:2]]
    cx = sum(f[0] for f in fingers) / len(fingers)
    cy = sum(f[1] for f in fingers) / len(fingers)

    return GreenMarkerDetection(
        fingers=fingers,
        center_px=(cx, cy),
        num_blobs=len(fingers),
    )


# ---------------------------------------------------------------------------
# Gripper-tip height detection (side camera)
# ---------------------------------------------------------------------------


def detect_gripper_tip(
    frame: np.ndarray,
    roi_frac: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
    desk_y_frac: float | None = None,
) -> GripperTipDetection | None:
    """Detect the gripper tip vertical position in a side-view frame.

    Uses edge detection and vertical contour analysis to find the lowest
    point of the gripper (tip) and the desk surface line.

    This is a placeholder implementation — will be refined during Phase 4
    calibration with actual side-camera frames.

    Args:
        frame: BGR image from the side camera (numpy H×W×3 array).
        roi_frac: (x0, y0, x1, y1) fractions defining the detection ROI.
        desk_y_frac: If known, the Y fraction where the desk surface is.
                     None means auto-detect.

    Returns:
        GripperTipDetection if the gripper tip is visible, else None.
    """
    h, w = frame.shape[:2]
    x0 = int(roi_frac[0] * w)
    y0 = int(roi_frac[1] * h)
    x1 = int(roi_frac[2] * w)
    y1 = int(roi_frac[3] * h)

    roi = frame[y0:y1, x0:x1]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # Edge detection for the gripper profile
    edges = cv2.Canny(gray, 50, 150)
    # Find the lowest non-zero edge row (gripper tip)
    edge_rows = np.where(edges.any(axis=1))[0]

    if len(edge_rows) == 0:
        return None

    # Gripper tip is the lowest edge cluster (highest Y in image coords)
    tip_y_local = float(edge_rows[-1])
    tip_y = tip_y_local + y0

    # Desk detection: if provided, use it; otherwise find a horizontal line
    if desk_y_frac is not None:
        desk_y = desk_y_frac * h
    else:
        # Simple heuristic: desk is the strongest horizontal edge in lower half
        lower_half = edges[len(edges) // 2 :, :]
        row_sums = lower_half.sum(axis=1)
        if row_sums.max() > 0:
            desk_y_local = float(np.argmax(row_sums)) + len(edges) // 2
            desk_y = desk_y_local + y0
        else:
            # Fallback: assume desk is at the bottom of the ROI
            desk_y = float(y1)

    gap_px = desk_y - tip_y  # positive = tip is above desk

    return GripperTipDetection(
        tip_y_px=tip_y,
        desk_y_px=desk_y,
        gap_px=gap_px,
    )


# ---------------------------------------------------------------------------
# Grasp verification (side camera)
# ---------------------------------------------------------------------------


@dataclass
class GraspVerification:
    """Result of grasp verification from the side camera.

    Attributes:
        object_present: Whether an object is detected between the gripper fingers.
        confidence: Confidence of the detection [0, 1].
        object_width_px: Estimated width of the object in pixels.
        gripper_region: (x0, y0, x1, y1) pixel region where the gripper was found.
    """

    object_present: bool
    confidence: float
    object_width_px: float = 0.0
    gripper_region: tuple[int, int, int, int] | None = None


def verify_grasp(
    frame: np.ndarray,
    gripper_roi_frac: tuple[float, float, float, float] = (0.3, 0.3, 0.7, 0.8),
    min_object_width_px: float = 5.0,
    min_confidence: float = 0.5,
) -> GraspVerification:
    """Verify whether the gripper is holding an object (side-view check).

    Looks for a dark/distinct object between the gripper fingers by detecting
    vertical edges or intensity differences in the gripper region. The gripper
    fingers (green tape) bracket the grasp zone; between them, a held object
    creates additional edge density compared to an empty grasp.

    This is a heuristic approach that works for:
    - Dark objects (pens) against a lighter background.
    - Objects that create distinct edges between the finger blobs.

    Args:
        frame: BGR image from the side camera.
        gripper_roi_frac: (x0, y0, x1, y1) fractions defining where to look
                          for the gripper+object in the frame.
        min_object_width_px: Minimum object width in pixels to confirm grasp.
        min_confidence: Minimum confidence threshold to declare object present.

    Returns:
        GraspVerification with object_present, confidence, and diagnostics.
    """
    h, w = frame.shape[:2]
    x0 = int(gripper_roi_frac[0] * w)
    y0 = int(gripper_roi_frac[1] * h)
    x1 = int(gripper_roi_frac[2] * w)
    y1 = int(gripper_roi_frac[3] * h)

    roi = frame[y0:y1, x0:x1]
    if roi.size == 0:
        return GraspVerification(
            object_present=False, confidence=0.0, gripper_region=(x0, y0, x1, y1)
        )

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # Detect the green finger blobs in the ROI
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    green_mask = cv2.inRange(hsv, np.array([35, 70, 50]), np.array([90, 255, 255]))
    green_mask = cv2.morphologyEx(
        green_mask,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )

    # Find the finger columns (green blob X ranges)
    green_cols = np.where(green_mask.any(axis=0))[0]
    if len(green_cols) < 2:
        # Can't see both fingers — can't verify grasp
        return GraspVerification(
            object_present=False,
            confidence=0.0,
            gripper_region=(x0, y0, x1, y1),
        )

    # The "between fingers" region is between the leftmost and rightmost green
    left_finger = int(green_cols.min())
    right_finger = int(green_cols.max())
    between_width = right_finger - left_finger

    if between_width < 5:
        # Fingers too close (closed, nothing between)
        # But actually when closed on an object, the gap is small
        # Check for non-green content between the finger columns
        pass

    # Look for edge density between the fingers
    between_region = gray[:, left_finger:right_finger]
    if between_region.size == 0:
        return GraspVerification(
            object_present=False,
            confidence=0.0,
            gripper_region=(x0, y0, x1, y1),
        )

    # Vertical edge detection (object creates vertical edges)
    edges = cv2.Canny(between_region, 30, 100)
    edge_density = float(edges.sum()) / (edges.size * 255.0)

    # Also check intensity: an object is typically darker than air/background
    mean_between = float(between_region.mean())
    mean_outside_left = (
        float(gray[:, : max(1, left_finger)].mean()) if left_finger > 0 else 128.0
    )
    mean_outside_right = (
        float(gray[:, right_finger:].mean()) if right_finger < gray.shape[1] else 128.0
    )
    mean_outside = (mean_outside_left + mean_outside_right) / 2.0

    # Object is present if:
    # 1. Edge density is higher than baseline (object has texture/edges)
    # 2. Mean intensity between fingers differs from outside
    intensity_diff = abs(mean_between - mean_outside) / max(mean_outside, 1.0)

    # Combine into a confidence score
    confidence = min(1.0, edge_density * 5.0 + intensity_diff)

    # Estimate object width from the non-green, non-background content
    non_green_between = ~green_mask[:, left_finger:right_finger].astype(bool)
    object_cols = np.where(non_green_between.any(axis=0))[0]
    object_width = float(len(object_cols)) if len(object_cols) > 0 else 0.0

    object_present = (
        confidence >= min_confidence and object_width >= min_object_width_px
    )

    return GraspVerification(
        object_present=object_present,
        confidence=confidence,
        object_width_px=object_width,
        gripper_region=(x0, y0, x1, y1),
    )
