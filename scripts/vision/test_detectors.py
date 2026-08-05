"""
No-mock tests for :mod:`detectors` (pen orientation + green marker).

These exercise the REAL OpenCV pipeline on synthetic images (no mocks). They
require ``cv2``/``numpy`` and therefore run on the Pi (opencv-headless), where
the vision code is deployed flat in ``/home/pi/vision``:

    cd /home/pi/vision && /home/pi/armold-venv/bin/python test_detectors.py
"""

from __future__ import annotations

import math
import sys

import cv2
import numpy as np
from detectors import _long_axis_angle_deg, detect_green_marker, detect_pen


def _blank(w: int = 640, h: int = 360, bg: int = 120) -> np.ndarray:
    """Return a uniform-gray BGR image of the given size."""
    return np.full((h, w, 3), bg, np.uint8)


def _draw_pen(
    img: np.ndarray,
    center: tuple[float, float],
    length: float,
    width: float,
    deg: float,
    color: tuple[int, int, int] = (25, 25, 25),
) -> None:
    """Draw a filled oriented rectangle (pen) with its long axis at ``deg``."""
    rad = math.radians(deg)
    dx, dy = math.cos(rad), math.sin(rad)  # long-axis unit vector
    px, py = -dy, dx  # perpendicular unit vector
    hl, hw = length / 2.0, width / 2.0
    corners = []
    for sl, sw in ((1, 1), (1, -1), (-1, -1), (-1, 1)):
        corners.append(
            [
                center[0] + sl * hl * dx + sw * hw * px,
                center[1] + sl * hl * dy + sw * hw * py,
            ]
        )
    cv2.fillPoly(img, [np.array(corners, np.int32)], color)


def _angdiff(a: float, b: float) -> float:
    """Absolute angular difference (deg) modulo 180 (long-axis symmetry)."""
    return abs((a - b + 90.0) % 180.0 - 90.0)


def test_long_axis_helper_is_pure_and_correct() -> None:
    """The corner-based long-axis angle is exact for axis-aligned boxes."""
    horizontal = np.array([[0, 0], [100, 0], [100, 10], [0, 10]], dtype=float)
    assert _angdiff(_long_axis_angle_deg(horizontal), 0.0) < 1e-6
    vertical = np.array([[0, 0], [10, 0], [10, 100], [0, 100]], dtype=float)
    assert _angdiff(_long_axis_angle_deg(vertical), 90.0) < 1e-6


def test_detects_pen_center_and_confidence() -> None:
    """A drawn pen is detected near its true center with positive confidence."""
    img = _blank()
    _draw_pen(img, (256, 146), 90, 12, 20.0)
    _, det = detect_pen(img)
    assert det is not None, "expected a detection"
    assert abs(det.center_px[0] - 256) < 15
    assert abs(det.center_px[1] - 146) < 15
    assert det.confidence > 0.0


def test_long_axis_angle_matches_drawn_angle() -> None:
    """detect_pen recovers the drawn long-axis angle within tolerance."""
    for deg in (0.0, 20.0, 45.0, -30.0, 70.0):
        img = _blank()
        _draw_pen(img, (256, 146), 100, 12, deg)
        _, det = detect_pen(img)
        assert det is not None, f"no detection at {deg} deg"
        assert (
            _angdiff(det.angle_deg, deg) < 8.0
        ), f"recovered {det.angle_deg:.1f} vs drawn {deg}"


def test_no_pen_returns_none() -> None:
    """A blank field yields no pen detection."""
    _, det = detect_pen(_blank())
    assert det is None


def test_green_marker_two_blobs_midpoint() -> None:
    """Two green blobs are detected and the grasp midpoint is their average."""
    img = _blank()
    cv2.circle(img, (240, 146), 8, (0, 200, 0), -1)
    cv2.circle(img, (272, 146), 8, (0, 200, 0), -1)
    det = detect_green_marker(img)
    assert det is not None
    assert det.num_blobs == 2
    assert abs(det.center_px[0] - 256) < 6
    assert abs(det.center_px[1] - 146) < 6


def _run_all() -> int:
    """Run every ``test_*`` in this module; return the failure count."""
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return failures


if __name__ == "__main__":
    sys.exit(1 if _run_all() else 0)
