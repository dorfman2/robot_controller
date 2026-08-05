"""
Validate the overhead homography calibration (pixel → arm-XY → pixel round-trip).

Loads ~/armold_handeye_overhead.json, applies the homography to each calibration
point's pixel coordinates, and checks the reprojection against the known arm-XY.
Also tests the inverse (arm-XY → pixel) for diagnostics.

Success criterion: reproj error ≤ ±10 mm on all points (R4 success criteria).

Usage (on Pi, in armold-venv):
    python scripts/vision/validate_overhead_cal.py
    python scripts/vision/validate_overhead_cal.py --cal-file ~/armold_handeye_overhead.json

References:
    R4 (calibration validation), design.md success criteria.
"""

import argparse
import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_CAL_PATH = Path.home() / "armold_handeye_overhead.json"
SUCCESS_THRESHOLD_MM = 10.0


def load_calibration(path: Path) -> dict:
    """Load calibration data from JSON.

    Args:
        path: Path to the calibration JSON file.

    Returns:
        Parsed calibration dict.

    Raises:
        FileNotFoundError: If the calibration file doesn't exist.
        json.JSONDecodeError: If the file is invalid JSON.
    """
    if not path.exists():
        raise FileNotFoundError(f"Calibration file not found: {path}")
    return json.loads(path.read_text())


def apply_homography(H: np.ndarray, points_px: np.ndarray) -> np.ndarray:
    """Apply a 3x3 homography to pixel points, returning arm-XY.

    Args:
        H: 3x3 homography matrix (pixel → arm-XY).
        points_px: Nx2 array of pixel coordinates.

    Returns:
        Nx2 array of predicted arm-XY coordinates.
    """
    n = len(points_px)
    Ph = np.hstack([points_px, np.ones((n, 1))])
    transformed = (H @ Ph.T).T
    return transformed[:, :2] / transformed[:, 2:3]


def validate(cal_data: dict) -> bool:
    """Validate the calibration round-trip error.

    Args:
        cal_data: Parsed calibration dict with 'H', 'points', etc.

    Returns:
        True if all points within SUCCESS_THRESHOLD_MM.
    """
    H = np.array(cal_data["H"], dtype=np.float64)
    points = cal_data.get("points", [])

    if not points:
        logger.error("No calibration points in the file.")
        return False

    # Points format: [target_x, target_y, px_x, px_y, arm_x, arm_y]
    pts_px = np.array([[row[2], row[3]] for row in points], dtype=np.float64)
    pts_xy_true = np.array([[row[4], row[5]] for row in points], dtype=np.float64)

    # Apply homography: pixel → arm-XY
    pts_xy_pred = apply_homography(H, pts_px)

    # Compute per-point errors
    errors = np.linalg.norm(pts_xy_pred - pts_xy_true, axis=1)
    mean_err = float(errors.mean())
    max_err = float(errors.max())
    std_err = float(errors.std())

    print("\nOverhead Calibration Validation")
    print(f"{'='*50}")
    print(f"  Camera: {cal_data.get('camera', 'unknown')}")
    print(f"  Method: {cal_data.get('type', 'unknown')}")
    print(f"  Points: {len(points)}")
    print(f"  Rail:   {cal_data.get('rail_mm', '?')} mm")
    print(f"  Z plane: {cal_data.get('z_plane', '?')} mm")
    print(f"  Calibrated: {cal_data.get('calibrated_at', '?')}")
    print()
    print("  Reprojection error (pixel → arm-XY):")
    print(f"    Mean: {mean_err:.2f} mm")
    print(f"    Max:  {max_err:.2f} mm")
    print(f"    Std:  {std_err:.2f} mm")
    print()

    # Per-point breakdown
    print(
        f"  {'#':<3} {'Pixel (x,y)':<16} {'True XY':<16} "
        f"{'Pred XY':<16} {'Error mm'}"
    )
    print(f"  {'-'*70}")
    all_pass = True
    for i, (row, pred, err) in enumerate(zip(points, pts_xy_pred, errors)):
        status = "✓" if err <= SUCCESS_THRESHOLD_MM else "✗"
        if err > SUCCESS_THRESHOLD_MM:
            all_pass = False
        print(
            f"  {i:<3} ({row[2]:>5.0f},{row[3]:>5.0f})   "
            f"({row[4]:>6.1f},{row[5]:>6.1f}) "
            f"({pred[0]:>6.1f},{pred[1]:>6.1f}) "
            f"{err:>6.2f}  {status}"
        )

    print()
    if all_pass:
        print(f"  ✓ PASS — All points within ±{SUCCESS_THRESHOLD_MM} mm.")
    else:
        print(
            f"  ✗ FAIL — {sum(errors > SUCCESS_THRESHOLD_MM)} point(s) "
            f"exceed ±{SUCCESS_THRESHOLD_MM} mm threshold."
        )

    # Also compute the inverse homography (arm-XY → pixel) for diagnostics
    H_inv = np.linalg.inv(H)
    pts_px_pred = apply_homography(H_inv, pts_xy_true)
    px_errors = np.linalg.norm(pts_px_pred - pts_px, axis=1)
    print("\n  Inverse check (arm-XY → pixel):")
    print(f"    Mean pixel error: {px_errors.mean():.1f} px")
    print(f"    Max pixel error:  {px_errors.max():.1f} px")

    return all_pass


def main() -> None:
    """Load calibration and run validation."""
    parser = argparse.ArgumentParser(
        description="Validate overhead calibration (reproj ≤ ±10 mm)."
    )
    parser.add_argument(
        "--cal-file",
        type=str,
        default=str(DEFAULT_CAL_PATH),
        help=f"Calibration JSON path (default: {DEFAULT_CAL_PATH}).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cal_path = Path(args.cal_file)
    try:
        cal_data = load_calibration(cal_path)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        print("\nRun calibrate_overhead.py first to generate the calibration.")
        return

    passed = validate(cal_data)
    if not passed:
        logger.warning(
            "Calibration validation FAILED. Consider recalibrating with "
            "more points or better lighting."
        )


if __name__ == "__main__":
    main()
