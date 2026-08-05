"""
Shared camera configuration for the dual-camera vision system.

Defines device addressing, ROI parameters, and detection thresholds
used by both the overhead (OAK-4 S) and side (OAK-1 Lite) streams.

Device addressing uses DepthAI v3 stable identifiers:
    - OAK-4 S: by IP (TCP_IP protocol, RVC4 platform)
    - OAK-1 Lite: by deviceId (USB protocol, MYRIAD_X platform)
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Device addressing (DepthAI v3)
# ---------------------------------------------------------------------------

#: OAK-4 S IP on the local network (DHCP reservation recommended).
OAK4S_IP: str = "192.168.1.138"

#: OAK-4 S deviceId (stable hardware ID).
OAK4S_DEVICE_ID: str = "4119377180"

#: OAK-1 Lite USB deviceId (stable hardware ID).
OAK1_DEVICE_ID: str = "19443010A113177E00"

#: Path to the persisted camera config JSON on the Pi.
CAMERA_CONFIG_PATH: Path = Path.home() / "armold_cameras.json"


# ---------------------------------------------------------------------------
# Stream ports
# ---------------------------------------------------------------------------

#: HTTP port for the overhead (OAK-4 S) stream service.
OVERHEAD_PORT: int = 8091

#: HTTP port for the side (OAK-1 Lite) stream service.
SIDE_PORT: int = 8092


# ---------------------------------------------------------------------------
# Overhead camera (OAK-4 S) settings
# ---------------------------------------------------------------------------


@dataclass
class OverheadConfig:
    """Configuration for the overhead OAK-4 S camera.

    Attributes:
        device_id: DepthAI v3 device identifier (IP address for network).
        resolution: (width, height) for the camera output.
        fps: Frames per second.
        roi_frac: Region of interest as (x0, y0, x1, y1) fractions of frame.
        min_area_frac: Minimum contour area as fraction of frame area.
        max_area_frac: Maximum contour area as fraction of frame area.
        min_elongation: Minimum elongation (long/short) to qualify as a pen.
        jpeg_quality: JPEG encoding quality for the MJPEG stream.
    """

    device_id: str = OAK4S_IP
    resolution: tuple[int, int] = (640, 360)
    fps: int = 15
    roi_frac: tuple[float, float, float, float] = (0.20, 0.16, 0.60, 0.656)
    min_area_frac: float = 0.0003
    max_area_frac: float = 0.05
    min_elongation: float = 3.0
    jpeg_quality: int = 80


# ---------------------------------------------------------------------------
# Side camera (OAK-1 Lite) settings
# ---------------------------------------------------------------------------


@dataclass
class SideConfig:
    """Configuration for the side OAK-1 Lite camera.

    Attributes:
        device_id: DepthAI v3 device identifier (deviceId for USB).
        resolution: (width, height) for the camera output.
        fps: Frames per second.
        roi_frac: Region of interest as (x0, y0, x1, y1) fractions of frame.
        jpeg_quality: JPEG encoding quality for the MJPEG stream.
    """

    device_id: str = OAK1_DEVICE_ID
    resolution: tuple[int, int] = (640, 360)
    fps: int = 15
    roi_frac: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    jpeg_quality: int = 80


# ---------------------------------------------------------------------------
# Green marker detection (shared between cameras)
# ---------------------------------------------------------------------------


@dataclass
class GreenMarkerConfig:
    """HSV thresholds and parameters for green gripper-tape detection.

    Attributes:
        lower_hsv: Lower bound (H, S, V) for green detection.
        upper_hsv: Upper bound (H, S, V) for green detection.
        min_area: Minimum blob area in pixels.
    """

    lower_hsv: np.ndarray = field(default_factory=lambda: np.array([35, 70, 50]))
    upper_hsv: np.ndarray = field(default_factory=lambda: np.array([90, 255, 255]))
    min_area: int = 60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_camera_config() -> dict | None:
    """Load the persisted camera config from ~/armold_cameras.json.

    Returns:
        Parsed JSON dict, or None if the file doesn't exist or is invalid.
    """
    if not CAMERA_CONFIG_PATH.exists():
        logger.warning("Camera config not found at %s", CAMERA_CONFIG_PATH)
        return None
    try:
        data = json.loads(CAMERA_CONFIG_PATH.read_text())
        logger.info("Loaded camera config from %s", CAMERA_CONFIG_PATH)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load camera config: %s", exc)
        return None


def get_device_id_for(camera_name: str) -> str | None:
    """Look up a device identifier from the persisted config by camera name.

    Args:
        camera_name: The camera name (e.g. 'OAK-4 S overhead').

    Returns:
        The device_id or IP string for DepthAI addressing, or None.
    """
    config = load_camera_config()
    if config is None:
        return None
    for cam in config.get("cameras", []):
        if cam.get("name") == camera_name:
            # Prefer IP for network cameras, deviceId for USB
            return cam.get("ip") or cam.get("device_id")
    return None
