"""
On-device detection pipeline for the OAK-4 S (RVC4).

When a trained detection model is available (YOLO/SSD compiled for RVC4),
this module runs inference on-device so the Pi only receives detection
results, not raw frames. Falls back to host-side classic-CV if no model
is configured.

Usage:
    When a model blob/archive is available, set MODEL_PATH and restart
    the overhead service. The pipeline will switch from host-side to
    on-device inference automatically.

DepthAI v3 on-device inference:
    DetectionNetwork node consumes camera frames on-device and outputs
    ImgDetections. The Pi receives only the lightweight detection list.

Status: INFRASTRUCTURE READY — awaiting a trained model for the RVC4.
        Currently falls back to host-side classic-CV (detectors.py).

References:
    R2 (on-device inference frees Pi CPU), design.md capability #1.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Path to the compiled detection model for on-device inference.
#: Set to a valid .blob or nn_archive path to enable on-device detection.
#: When None, the overhead service uses host-side classic-CV.
MODEL_PATH: Path | None = None

#: Detection confidence threshold for on-device inference.
CONFIDENCE_THRESHOLD: float = 0.5

#: Maximum number of detections to return per frame.
MAX_DETECTIONS: int = 10


@dataclass
class OnDeviceDetection:
    """A single detection result from on-device inference.

    Attributes:
        label: Class label string (e.g. 'pen', 'marker').
        confidence: Detection confidence [0, 1].
        bbox_norm: Normalized bounding box (x_min, y_min, x_max, y_max) in [0,1].
        center_px: (x, y) pixel center (computed from bbox and frame size).
        angle_deg: Orientation angle in degrees (if the model provides it).
    """

    label: str
    confidence: float
    bbox_norm: tuple[float, float, float, float]
    center_px: tuple[float, float]
    angle_deg: float | None = None


# ---------------------------------------------------------------------------
# On-device pipeline builder (for when a model is available)
# ---------------------------------------------------------------------------


def is_on_device_available() -> bool:
    """Check if on-device detection is configured and available.

    Returns:
        True if MODEL_PATH is set and the file exists.
    """
    if MODEL_PATH is None:
        return False
    if not MODEL_PATH.exists():
        logger.warning("Model path configured but file not found: %s", MODEL_PATH)
        return False
    return True


def build_on_device_pipeline_nodes(pipeline, camera_node):
    """Build the on-device DetectionNetwork nodes in a DepthAI v3 pipeline.

    This function adds a DetectionNetwork node to the pipeline that consumes
    camera frames on-device and produces ImgDetections. Call this instead of
    creating an output queue for raw frames when on-device mode is enabled.

    NOTE: This is a placeholder that will be completed when a compiled model
    is available. The actual implementation depends on the model format
    (blob vs nn_archive) and the detection network type.

    Args:
        pipeline: The dai.Pipeline being constructed.
        camera_node: The Camera node whose output feeds the detector.

    Returns:
        The detection output queue (or None if not yet implemented).

    Raises:
        NotImplementedError: Until a model is compiled and available.
    """
    if not is_on_device_available():
        raise NotImplementedError(
            "On-device detection not available: no model configured. "
            "Set MODEL_PATH in on_device_detect.py to a valid RVC4 model."
        )

    # --- PLACEHOLDER: Uncomment and adapt when a model is available ---
    #
    # import depthai as dai
    #
    # # Create detection network node
    # det_nn = pipeline.create(dai.node.DetectionNetwork).build(
    #     camera_node, type=dai.DetectionNetworkType.YOLO
    # )
    # det_nn.setConfidenceThreshold(CONFIDENCE_THRESHOLD)
    # det_nn.setBlobPath(str(MODEL_PATH))
    #
    # # Create output queue for detections (lightweight, not frames)
    # det_q = det_nn.out.createOutputQueue(maxSize=4, blocking=False)
    # return det_q
    #
    # --- END PLACEHOLDER ---

    raise NotImplementedError(
        "On-device pipeline builder not yet implemented. "
        "Waiting for a compiled detection model for the RVC4."
    )


def parse_on_device_detections(
    raw_detections,
    frame_width: int,
    frame_height: int,
) -> list[OnDeviceDetection]:
    """Parse raw DepthAI ImgDetections into OnDeviceDetection dataclasses.

    Args:
        raw_detections: DepthAI ImgDetections message from the DetectionNetwork.
        frame_width: Frame width in pixels (for denormalizing bbox).
        frame_height: Frame height in pixels.

    Returns:
        List of OnDeviceDetection results.
    """
    results: list[OnDeviceDetection] = []

    for det in raw_detections.detections[:MAX_DETECTIONS]:
        # Normalized bbox
        x_min = det.xmin
        y_min = det.ymin
        x_max = det.xmax
        y_max = det.ymax

        # Pixel center
        cx = (x_min + x_max) / 2.0 * frame_width
        cy = (y_min + y_max) / 2.0 * frame_height

        # Label (from model's label map)
        label = str(det.label) if hasattr(det, "label") else "object"
        confidence = float(det.confidence)

        results.append(
            OnDeviceDetection(
                label=label,
                confidence=confidence,
                bbox_norm=(x_min, y_min, x_max, y_max),
                center_px=(cx, cy),
                angle_deg=None,  # Requires oriented-bbox model
            )
        )

    return results
