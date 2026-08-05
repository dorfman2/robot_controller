"""
On-device detection for the OAK-4 S (RVC4) via DepthAI v3.

Runs a DetectionNetwork *on the camera*: the model is sourced from the HubAI
Model Zoo (by slug, e.g. ``"yolov6-nano"``) or from a local ``nn_archive``, is
compiled for RVC4, and both inference and output decoding happen on-device. The
Pi host receives only lightweight ``ImgDetections`` — not raw frames for
inference (design.md capability #1, verified: yolov6-nano ran ~29 FPS on-device
and the Pi received only detections).

Model formats (RVC4):
    * HubAI Model Zoo slug  → ``dai.NNModelDescription("<slug>")`` (auto
      download + compile for the connected platform).
    * Local NN archive path → ``dai.NNModelDescription(<path>)`` (a ``.tar``
      produced by the HubAI ModelConverter for a custom-trained model).
    NOTE: ``.blob`` is the RVC2 / Myriad-X format and does NOT apply to the
    RVC4-based OAK-4 S.

Enablement:
    Set :data:`MODEL_SLUG` to a zoo slug or archive path to run on-device;
    leave it ``None`` to keep host-side classic-CV (``detectors.detect_pen``).
    A COCO model (yolov6-nano) has no "pen" class — a custom-trained model is
    required for pen detection (see the spec's custom-model plan).

References: R2 (on-device inference frees the Pi), design.md capability #1.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import depthai as dai

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: HubAI Model Zoo slug OR local nn_archive path enabling on-device detection.
#: None → on-device disabled; the overhead service uses host-side classic-CV.
#: A COCO model (e.g. "yolov6-nano") proves the pipeline but has no "pen" class.
MODEL_SLUG: str | None = None

#: Detection confidence threshold (applied on-device when supported).
CONFIDENCE_THRESHOLD: float = 0.5

#: Maximum number of detections to return per frame.
MAX_DETECTIONS: int = 20


@dataclass
class OnDeviceDetection:
    """A single detection parsed from on-device inference.

    Attributes:
        label: Class label string (from the model's class list).
        confidence: Detection confidence in ``[0, 1]``.
        bbox_norm: Normalized box ``(xmin, ymin, xmax, ymax)`` in ``[0, 1]``.
        center_px: Pixel center ``(x, y)`` (denormalized to the frame size).
        angle_deg: Long-axis orientation in degrees, or ``None`` when the
            model does not provide orientation (axis-aligned detectors).
    """

    label: str
    confidence: float
    bbox_norm: tuple[float, float, float, float]
    center_px: tuple[float, float]
    angle_deg: float | None = None


def is_enabled() -> bool:
    """Return whether on-device detection is configured.

    Returns:
        True when :data:`MODEL_SLUG` is set (zoo slug or archive path).
    """
    return MODEL_SLUG is not None


def build_detection_network(
    pipeline: Any,
    camera_node: Any,
    model_slug: str | None = None,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> Any:
    """Attach a DetectionNetwork to the pipeline, running a model on-device.

    Mirrors the verified DepthAI v3 flow: build a ``DetectionNetwork`` from the
    camera node and an :class:`dai.NNModelDescription`. The node downloads /
    compiles the model for RVC4 and decodes detections on-camera.

    Args:
        pipeline: The active ``dai.Pipeline``.
        camera_node: The ``dai.node.Camera`` node feeding the detector.
        model_slug: Zoo slug or ``nn_archive`` path. Defaults to
            :data:`MODEL_SLUG`.
        confidence_threshold: Confidence threshold applied on-device when the
            node supports ``setConfidenceThreshold``.

    Returns:
        The built ``DetectionNetwork`` node. Use ``node.out.createOutputQueue()``
        for detections, ``node.passthrough.createOutputQueue()`` for the frames
        the model saw, and ``node.getClasses()`` for the label list.

    Raises:
        ValueError: If no model slug/path is configured.
    """
    slug = model_slug if model_slug is not None else MODEL_SLUG
    if slug is None:
        raise ValueError(
            "On-device detection requires a model: set MODEL_SLUG to a HubAI "
            "zoo slug (e.g. 'yolov6-nano') or a local nn_archive path."
        )

    net = pipeline.create(dai.node.DetectionNetwork).build(
        camera_node, dai.NNModelDescription(slug)
    )
    # Confidence threshold is optional across model types; apply if available.
    setter = getattr(net, "setConfidenceThreshold", None)
    if callable(setter):
        setter(confidence_threshold)
    logger.info("On-device DetectionNetwork built for model '%s'", slug)
    return net


def parse_detections(
    img_detections: Any,
    labels: list[str],
    frame_width: int,
    frame_height: int,
) -> list[OnDeviceDetection]:
    """Convert a DepthAI ``ImgDetections`` message to dataclasses.

    Args:
        img_detections: The ``dai.ImgDetections`` from the DetectionNetwork out
            queue (each detection has ``label``, ``confidence``, and normalized
            ``xmin``/``ymin``/``xmax``/``ymax``).
        labels: Class label list from ``DetectionNetwork.getClasses()``.
        frame_width: Frame width in pixels (to denormalize the box center).
        frame_height: Frame height in pixels.

    Returns:
        A list of :class:`OnDeviceDetection` (capped at :data:`MAX_DETECTIONS`).
    """
    results: list[OnDeviceDetection] = []
    for det in list(img_detections.detections)[:MAX_DETECTIONS]:
        xmin, ymin, xmax, ymax = det.xmin, det.ymin, det.xmax, det.ymax
        cx = (xmin + xmax) / 2.0 * frame_width
        cy = (ymin + ymax) / 2.0 * frame_height
        idx = int(det.label)
        label = labels[idx] if 0 <= idx < len(labels) else str(idx)
        results.append(
            OnDeviceDetection(
                label=label,
                confidence=float(det.confidence),
                bbox_norm=(float(xmin), float(ymin), float(xmax), float(ymax)),
                center_px=(cx, cy),
                angle_deg=None,  # axis-aligned detector; oriented model needed
            )
        )
    return results
