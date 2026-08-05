"""
Multi-point desk-Z calibration.

Drives the arm to several XY positions across the pick zone in a vertical
clean-wrist config, descends until the operator calls contact (or a known
desk height is reached), and records the commanded model-Z at each point.
Fits/interpolates a Z-offset(X, Y) surface and persists it.

The result is a lookup: given a target arm-(X, Y), what model-Z value
corresponds to physical desk contact? This absorbs the pose-dependent
droop/backlash/finger offset that makes a single z≈74 insufficient.

Usage (on Pi, in armold-venv):
    python scripts/vision/calibrate_desk_z.py
    python scripts/vision/calibrate_desk_z.py --points "(-350,0,74),(-300,0,78),(-400,0,70)"

Or interactively (operator calls contact at each point):
    python scripts/vision/calibrate_desk_z.py --interactive

References:
    R11 (multi-point desk-Z), edge case C2, design.md.
"""

import argparse
import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path.home() / "armold_desk_z.json"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DeskZPoint:
    """A single calibration point for the desk-Z surface.

    Attributes:
        arm_x: Arm-frame X at contact (mm).
        arm_y: Arm-frame Y at contact (mm).
        model_z: Commanded model-Z at desk contact (mm).
        rail_mm: Rail position during this measurement.
    """

    arm_x: float
    arm_y: float
    model_z: float
    rail_mm: float = 0.0


@dataclass
class DeskZCalibration:
    """Multi-point desk-Z calibration result.

    Attributes:
        points: List of calibrated (X, Y, model_Z) contact points.
        fit_type: Type of surface fit ('nearest', 'linear', 'bilinear').
        coefficients: Fit coefficients (depends on fit_type).
        rail_mm: Rail position these measurements are valid for.
        calibrated_at: ISO timestamp of calibration.
    """

    points: list[DeskZPoint]
    fit_type: str
    coefficients: list[float]
    rail_mm: float
    calibrated_at: str


# ---------------------------------------------------------------------------
# Surface fitting
# ---------------------------------------------------------------------------


def fit_desk_z_surface(
    points: list[DeskZPoint],
) -> tuple[str, list[float]]:
    """Fit a Z-offset surface to the calibration points.

    For 1-3 points: uses nearest-neighbor (constant offset).
    For 4+ points: fits a bilinear surface z = a*x + b*y + c*x*y + d.

    Args:
        points: Calibrated DeskZPoint list.

    Returns:
        Tuple of (fit_type, coefficients).
    """
    n = len(points)
    if n == 0:
        return ("constant", [74.0])  # Default fallback

    if n == 1:
        return ("constant", [points[0].model_z])

    if n <= 3:
        # Linear fit: z = a*x + b*y + c
        xs = np.array([p.arm_x for p in points])
        ys = np.array([p.arm_y for p in points])
        zs = np.array([p.model_z for p in points])
        A = np.column_stack([xs, ys, np.ones(n)])
        coeffs, _, _, _ = np.linalg.lstsq(A, zs, rcond=None)
        return ("linear", coeffs.tolist())

    # Bilinear fit: z = a*x + b*y + c*x*y + d
    xs = np.array([p.arm_x for p in points])
    ys = np.array([p.arm_y for p in points])
    zs = np.array([p.model_z for p in points])
    A = np.column_stack([xs, ys, xs * ys, np.ones(n)])
    coeffs, _, _, _ = np.linalg.lstsq(A, zs, rcond=None)
    return ("bilinear", coeffs.tolist())


def predict_desk_z(
    fit_type: str, coefficients: list[float], x: float, y: float
) -> float:
    """Predict the desk-contact model-Z for a given arm (X, Y).

    Args:
        fit_type: The surface fit type ('constant', 'linear', 'bilinear').
        coefficients: Fit coefficients from fit_desk_z_surface.
        x: Target arm-frame X (mm).
        y: Target arm-frame Y (mm).

    Returns:
        Predicted model-Z at desk contact for the given (X, Y).
    """
    if fit_type == "constant":
        return coefficients[0]
    elif fit_type == "linear":
        a, b, c = coefficients
        return a * x + b * y + c
    elif fit_type == "bilinear":
        a, b, c, d = coefficients
        return a * x + b * y + c * x * y + d
    else:
        logger.warning("Unknown fit type %s, using first coefficient.", fit_type)
        return coefficients[0]


# ---------------------------------------------------------------------------
# Calibration persistence
# ---------------------------------------------------------------------------


def save_calibration(cal: DeskZCalibration) -> None:
    """Persist the desk-Z calibration to JSON.

    Args:
        cal: DeskZCalibration dataclass to save.
    """
    data = {
        "points": [asdict(p) for p in cal.points],
        "fit_type": cal.fit_type,
        "coefficients": cal.coefficients,
        "rail_mm": cal.rail_mm,
        "calibrated_at": cal.calibrated_at,
        "n_points": len(cal.points),
    }
    OUTPUT_PATH.write_text(json.dumps(data, indent=2))
    logger.info("Desk-Z calibration saved to %s", OUTPUT_PATH)


def load_calibration() -> DeskZCalibration | None:
    """Load the desk-Z calibration from JSON.

    Returns:
        DeskZCalibration if file exists and is valid, else None.
    """
    if not OUTPUT_PATH.exists():
        return None
    try:
        data = json.loads(OUTPUT_PATH.read_text())
        points = [DeskZPoint(**p) for p in data["points"]]
        return DeskZCalibration(
            points=points,
            fit_type=data["fit_type"],
            coefficients=data["coefficients"],
            rail_mm=data.get("rail_mm", 0.0),
            calibrated_at=data.get("calibrated_at", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.error("Failed to load desk-Z calibration: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse arguments and run the desk-Z calibration.

    In non-interactive mode, accepts pre-measured points as arguments.
    In interactive mode, would drive the arm down and ask the operator to
    call contact (requires arm controller integration).
    """
    parser = argparse.ArgumentParser(
        description="Multi-point desk-Z calibration (R11)."
    )
    parser.add_argument(
        "--points",
        type=str,
        default=None,
        help=(
            "Pre-measured contact points as '(x,y,z),(x,y,z),...' "
            "e.g. '(-350,0,74),(-300,0,78),(-400,0,70),(-350,50,76)'"
        ),
    )
    parser.add_argument(
        "--rail",
        type=float,
        default=0.0,
        help="Rail position these measurements are valid for (default: 0).",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode (not yet implemented — requires arm moves).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.interactive:
        print(
            "Interactive desk-Z calibration not yet implemented.\n"
            "Use --points with pre-measured values, or integrate with\n"
            "the arm controller for automated descent + operator contact call."
        )
        return

    if args.points is None:
        # Use the known single-point calibration as a starting point
        print("No points specified. Using known single-point (x=-350, y=0, z=74).")
        print("Run with --points for multi-point calibration.")
        points = [DeskZPoint(arm_x=-350.0, arm_y=0.0, model_z=74.0, rail_mm=args.rail)]
    else:
        # Parse "(x,y,z),(x,y,z),..." format
        import re

        tuples = re.findall(r"\(([-\d.]+),([-\d.]+),([-\d.]+)\)", args.points)
        if not tuples:
            logger.error("Could not parse --points. Format: '(x,y,z),(x,y,z),...'")
            return
        points = [
            DeskZPoint(
                arm_x=float(t[0]),
                arm_y=float(t[1]),
                model_z=float(t[2]),
                rail_mm=args.rail,
            )
            for t in tuples
        ]

    logger.info("Calibrating with %d points...", len(points))

    # Fit surface
    fit_type, coefficients = fit_desk_z_surface(points)
    logger.info("Fit type: %s, coefficients: %s", fit_type, coefficients)

    # Create calibration object
    cal = DeskZCalibration(
        points=points,
        fit_type=fit_type,
        coefficients=coefficients,
        rail_mm=args.rail,
        calibrated_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    )

    # Report
    print("\nDesk-Z Calibration")
    print(f"{'='*50}")
    print(f"  Points: {len(points)}")
    print(f"  Fit: {fit_type}")
    print(f"  Coefficients: {coefficients}")
    print("\n  Predictions:")
    test_xs = [-400, -375, -350, -325, -300]
    test_ys = [-50, 0, 50]
    for tx in test_xs:
        for ty in test_ys:
            z_pred = predict_desk_z(fit_type, coefficients, float(tx), float(ty))
            print(f"    ({tx:>4}, {ty:>3}) → model z = {z_pred:.1f} mm")

    # Residuals
    if len(points) > 1:
        errors = []
        for p in points:
            z_pred = predict_desk_z(fit_type, coefficients, p.arm_x, p.arm_y)
            errors.append(abs(z_pred - p.model_z))
        print("\n  Fit residuals:")
        print(f"    Mean: {np.mean(errors):.2f} mm")
        print(f"    Max:  {np.max(errors):.2f} mm")

    # Save
    save_calibration(cal)
    print(f"\n  Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
