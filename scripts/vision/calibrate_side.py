"""
Side camera (OAK-1 Lite) pixel→arm-(Z,Y) calibration.

Steps the arm through the clean-wrist column at known heights (z=74/100/150/200)
at fixed X,Y; records the gripper-tip pixel row at each height; fits a px→mm
mapping. Calibrates the scale as a function of arm-X (edge case C3 — the side
camera cannot resolve depth, so the px/mm scale changes with distance from camera).

Persists to ~/armold_sideview.json.

Usage (on Pi, in armold-venv):
    python scripts/vision/calibrate_side.py
    python scripts/vision/calibrate_side.py --points "(200,180),(150,220),(100,270),(74,320)"
    python scripts/vision/calibrate_side.py --multi-x "(-350,(200,180),(150,220),(100,270),(74,320));(-400,(200,170),(150,210),(100,260),(74,310))"

References:
    R4 (side calibration), R3 (side perception), edge case C3.
"""

import argparse
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path.home() / "armold_sideview.json"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SideCalPoint:
    """A single side calibration measurement.

    Attributes:
        arm_z_mm: Known arm-frame Z height (mm above desk).
        tip_y_px: Measured gripper-tip Y pixel in the side camera frame.
        arm_x_mm: Arm-frame X at which this was measured (for X-dependent scale).
    """

    arm_z_mm: float
    tip_y_px: float
    arm_x_mm: float = -350.0


@dataclass
class SideCalibration:
    """Side camera calibration result.

    The side camera sees the arm in profile. The image Y axis corresponds
    to arm-Z (height) and the mapping px→mm depends on arm-X (depth into
    the image). We fit separate linear px→mm scales for each measured X.

    Attributes:
        scales: Dict of arm_x → (slope_mm_per_px, intercept_mm) linear fit.
        points: All calibration points used.
        rail_mm: Rail position during calibration.
        arm_y_mm: Arm Y during calibration (side camera is at Y≈0).
        calibrated_at: ISO timestamp.
    """

    scales: dict[float, tuple[float, float]]
    points: list[SideCalPoint]
    rail_mm: float
    arm_y_mm: float
    calibrated_at: str


# ---------------------------------------------------------------------------
# Fitting
# ---------------------------------------------------------------------------


def fit_px_to_mm(
    points: list[SideCalPoint],
) -> dict[float, tuple[float, float]]:
    """Fit linear px→mm (Z) scales grouped by arm-X.

    For each unique arm-X value, fit: arm_z_mm = slope * tip_y_px + intercept.

    Note: higher tip_y_px means lower in the image (closer to desk), so
    the slope is typically negative (higher px → lower Z).

    Args:
        points: List of SideCalPoint measurements.

    Returns:
        Dict mapping arm_x → (slope, intercept) of the linear fit.
    """
    # Group by arm_x
    by_x: dict[float, list[SideCalPoint]] = {}
    for p in points:
        by_x.setdefault(p.arm_x_mm, []).append(p)

    scales: dict[float, tuple[float, float]] = {}
    for arm_x, pts in by_x.items():
        if len(pts) < 2:
            logger.warning(
                "Only %d point(s) at X=%.0f; need ≥2 for a linear fit.",
                len(pts),
                arm_x,
            )
            if len(pts) == 1:
                # Can't fit a line with 1 point; use a default scale
                scales[arm_x] = (0.0, pts[0].arm_z_mm)
            continue

        px_arr = np.array([p.tip_y_px for p in pts])
        z_arr = np.array([p.arm_z_mm for p in pts])

        # Linear fit: z = slope * px + intercept
        coeffs = np.polyfit(px_arr, z_arr, 1)
        slope, intercept = float(coeffs[0]), float(coeffs[1])
        scales[arm_x] = (slope, intercept)

        # Residuals
        pred = slope * px_arr + intercept
        residuals = np.abs(pred - z_arr)
        logger.info(
            "X=%.0f: slope=%.3f mm/px, intercept=%.1f mm, "
            "residual mean=%.2f max=%.2f mm",
            arm_x,
            slope,
            intercept,
            residuals.mean(),
            residuals.max(),
        )

    return scales


def predict_z_from_px(
    scales: dict[float, tuple[float, float]],
    tip_y_px: float,
    arm_x: float,
) -> float | None:
    """Predict arm-Z (height above desk) from a side-camera pixel Y.

    Interpolates between calibrated X values if the exact X is not
    in the scale table.

    Args:
        scales: Calibrated scale dict from fit_px_to_mm.
        tip_y_px: Measured gripper-tip Y pixel.
        arm_x: Current arm-frame X position.

    Returns:
        Predicted arm-Z in mm, or None if no calibration available.
    """
    if not scales:
        return None

    # Exact match
    if arm_x in scales:
        slope, intercept = scales[arm_x]
        return slope * tip_y_px + intercept

    # Interpolate between nearest calibrated X values
    xs = sorted(scales.keys())
    if arm_x <= xs[0]:
        slope, intercept = scales[xs[0]]
        return slope * tip_y_px + intercept
    if arm_x >= xs[-1]:
        slope, intercept = scales[xs[-1]]
        return slope * tip_y_px + intercept

    # Find bracketing X values
    for i in range(len(xs) - 1):
        if xs[i] <= arm_x <= xs[i + 1]:
            s0, i0 = scales[xs[i]]
            s1, i1 = scales[xs[i + 1]]
            # Linear interpolation of slope and intercept
            t = (arm_x - xs[i]) / (xs[i + 1] - xs[i])
            slope = s0 + t * (s1 - s0)
            intercept = i0 + t * (i1 - i0)
            return slope * tip_y_px + intercept

    return None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_calibration(cal: SideCalibration) -> None:
    """Persist the side calibration to JSON.

    Args:
        cal: SideCalibration to save.
    """
    data = {
        "scales": {str(k): list(v) for k, v in cal.scales.items()},
        "points": [
            {"arm_z_mm": p.arm_z_mm, "tip_y_px": p.tip_y_px, "arm_x_mm": p.arm_x_mm}
            for p in cal.points
        ],
        "rail_mm": cal.rail_mm,
        "arm_y_mm": cal.arm_y_mm,
        "calibrated_at": cal.calibrated_at,
        "n_points": len(cal.points),
        "note": "scale is X-dependent (edge case C3): interpolate between "
        "calibrated X values for targets at intermediate X.",
    }
    OUTPUT_PATH.write_text(json.dumps(data, indent=2))
    logger.info("Side calibration saved to %s", OUTPUT_PATH)


def load_calibration() -> SideCalibration | None:
    """Load the side calibration from JSON.

    Returns:
        SideCalibration if valid, else None.
    """
    if not OUTPUT_PATH.exists():
        return None
    try:
        data = json.loads(OUTPUT_PATH.read_text())
        scales = {float(k): tuple(v) for k, v in data["scales"].items()}
        points = [SideCalPoint(**p) for p in data["points"]]
        return SideCalibration(
            scales=scales,
            points=points,
            rail_mm=data.get("rail_mm", 0.0),
            arm_y_mm=data.get("arm_y_mm", 0.0),
            calibrated_at=data.get("calibrated_at", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.error("Failed to load side calibration: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse arguments and run side camera calibration."""
    parser = argparse.ArgumentParser(
        description="Side camera pixel→mm calibration (X-dependent scale)."
    )
    parser.add_argument(
        "--points",
        type=str,
        default=None,
        help=(
            "Pre-measured points at a single X: "
            "'(z_mm,tip_y_px),(z_mm,tip_y_px),...' "
            "e.g. '(200,180),(150,220),(100,270),(74,320)'"
        ),
    )
    parser.add_argument(
        "--arm-x",
        type=float,
        default=-350.0,
        help="Arm-X for single-X calibration (default: -350).",
    )
    parser.add_argument(
        "--multi-x",
        type=str,
        default=None,
        help=(
            "Multi-X calibration: "
            "'(x1,(z,px),(z,px),...);(x2,(z,px),(z,px),...);...' "
            "e.g. '(-350,(200,180),(150,220),(74,320));(-400,(200,170),(74,310))'"
        ),
    )
    parser.add_argument(
        "--rail",
        type=float,
        default=0.0,
        help="Rail position (default: 0).",
    )
    parser.add_argument(
        "--arm-y",
        type=float,
        default=0.0,
        help="Arm Y during calibration (default: 0).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    points: list[SideCalPoint] = []

    if args.multi_x:
        # Parse multi-X format: "(x1,(z,px),(z,px),...);(x2,...)"
        sections = args.multi_x.split(";")
        for section in sections:
            section = section.strip()
            # Extract the X value (first number in parens or before the first tuple)
            match = re.match(r"\(([-\d.]+),(.+)\)", section)
            if not match:
                logger.error("Cannot parse section: %s", section)
                continue
            arm_x = float(match.group(1))
            rest = match.group(2)
            tuples = re.findall(r"\(([-\d.]+),([-\d.]+)\)", rest)
            for z_str, px_str in tuples:
                points.append(
                    SideCalPoint(
                        arm_z_mm=float(z_str),
                        tip_y_px=float(px_str),
                        arm_x_mm=arm_x,
                    )
                )
    elif args.points:
        # Parse single-X format: "(z,px),(z,px),..."
        tuples = re.findall(r"\(([-\d.]+),([-\d.]+)\)", args.points)
        for z_str, px_str in tuples:
            points.append(
                SideCalPoint(
                    arm_z_mm=float(z_str),
                    tip_y_px=float(px_str),
                    arm_x_mm=args.arm_x,
                )
            )
    else:
        # Demo with synthetic data
        print("No calibration data provided. Generating demo...")
        print("Use --points or --multi-x with actual measurements.")
        points = [
            SideCalPoint(arm_z_mm=200, tip_y_px=100, arm_x_mm=-350),
            SideCalPoint(arm_z_mm=150, tip_y_px=150, arm_x_mm=-350),
            SideCalPoint(arm_z_mm=100, tip_y_px=200, arm_x_mm=-350),
            SideCalPoint(arm_z_mm=74, tip_y_px=226, arm_x_mm=-350),
        ]

    logger.info("Calibrating with %d points...", len(points))
    scales = fit_px_to_mm(points)

    cal = SideCalibration(
        scales=scales,
        points=points,
        rail_mm=args.rail,
        arm_y_mm=args.arm_y,
        calibrated_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    )

    # Report
    print("\nSide Camera Calibration")
    print(f"{'='*50}")
    print(f"  Points: {len(points)}")
    print(f"  X values: {sorted(scales.keys())}")
    for arm_x, (slope, intercept) in sorted(scales.items()):
        print(f"    X={arm_x:.0f}: z = {slope:.3f} * px + {intercept:.1f}")
    print("\n  Test predictions (X=-350):")
    for px in [100, 150, 200, 250, 300]:
        z = predict_z_from_px(scales, float(px), -350.0)
        print(f"    px={px} → z={z:.1f} mm" if z else f"    px={px} → N/A")

    save_calibration(cal)
    print(f"\n  Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
