"""
Overhead camera (OAK-4 S) hand-eye calibration.

Drives the arm to a grid of known XY positions at a fixed hover Z and rail
position, detects the green gripper-marker in the overhead camera, pairs
pixel↔arm-XY, and computes a homography (pixel → arm-XY at the desk plane).

Persists the calibration to ~/armold_handeye_overhead.json with metadata
(rail position, Z plane, reprojection error, points used).

Usage (on Pi, in armold-venv):
    python scripts/vision/calibrate_overhead.py
    python scripts/vision/calibrate_overhead.py --z-hover 200 --grid-step 30

Prerequisites:
    - Arm homed and enabled (armold_controller running on ws://localhost:9090).
    - Overhead service running (oak-overhead on :8091 with /grip endpoint).
    - Green marker on the gripper visible from above at the hover Z.

References:
    R4 (calibration), design.md (overhead pixel → arm-XY homography).
"""

import argparse
import asyncio
import json
import logging
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Output calibration file path.
OUTPUT_PATH = Path.home() / "armold_handeye_overhead.json"

#: Overhead camera grip endpoint.
GRIP_URL = "http://localhost:8091/grip"

#: WebSocket address for the arm controller.
WS_URL = "ws://localhost:9090"

#: Default hover Z for calibration (arm model height above desk).
DEFAULT_Z_HOVER = 200.0

#: Default grid center and range.
DEFAULT_GRID_CENTER_X = -300.0
DEFAULT_GRID_CENTER_Y = 0.0
DEFAULT_GRID_RANGE = 80.0
DEFAULT_GRID_STEP = 40.0

#: Movement speed during calibration (deg/s or mm/s).
CALIBRATION_SPEED = 8.0

#: Settle time after each move (seconds) for marker to stabilize.
SETTLE_TIME = 2.5

#: Minimum samples required per point for averaging.
MIN_SAMPLES = 3

#: Number of pixel samples to average per point.
NUM_SAMPLES = 6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def read_grip() -> tuple[float, float] | None:
    """Read the green marker grasp center from the overhead /grip endpoint.

    Returns:
        (px_x, px_y) pixel center, or None if not detected.
    """
    try:
        data = json.load(urllib.request.urlopen(GRIP_URL, timeout=3))
        center = data.get("center")
        if center and len(center) == 2:
            return (float(center[0]), float(center[1]))
        return None
    except Exception:  # noqa: BLE001 - grip read is best-effort telemetry
        return None


async def get_arm_state(ws) -> dict:
    """Request and return the current arm state over WebSocket.

    Args:
        ws: Open WebSocket connection.

    Returns:
        State message dict with 'position', etc.
    """
    await ws.send(json.dumps({"cmd": "get_state"}))
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
        if msg.get("type") == "state":
            return msg


async def move_cartesian(
    ws, x: float, y: float, z: float, speed: float = CALIBRATION_SPEED
) -> dict | None:
    """Command a Cartesian move and wait for completion.

    Args:
        ws: Open WebSocket connection.
        x: Target X in arm frame (mm).
        y: Target Y in arm frame (mm).
        z: Target Z in arm frame (mm).
        speed: Movement speed.

    Returns:
        Ack message dict on success, or None on failure/timeout.
    """
    await ws.send(
        json.dumps(
            {
                "cmd": "move_cartesian",
                "x": x,
                "y": y,
                "z": z,
                "speed": speed,
            }
        )
    )
    deadline = asyncio.get_event_loop().time() + 20
    while asyncio.get_event_loop().time() < deadline:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
        if msg.get("type") == "error":
            return None
        if msg.get("cmd") == "move_cartesian":
            return msg
    return None


# ---------------------------------------------------------------------------
# Calibration routine
# ---------------------------------------------------------------------------


async def run_calibration(
    z_hover: float,
    grid_xs: list[float],
    grid_ys: list[float],
) -> None:
    """Execute the calibration grid and compute the homography.

    Moves the arm to each grid point, samples the green marker pixel,
    pairs with the achieved arm-XY, then fits a homography.

    Args:
        z_hover: Fixed hover Z for all grid points.
        grid_xs: List of X coordinates in arm frame.
        grid_ys: List of Y coordinates in arm frame.
    """
    import websockets

    pts_px: list[list[float]] = []
    pts_xy: list[list[float]] = []
    rows: list[list[float]] = []

    async with websockets.connect(WS_URL) as ws:
        state = await get_arm_state(ws)
        rail_mm = state["position"][0]
        logger.info("Rail position: %.1f mm", rail_mm)
        logger.info(
            "Calibration grid: %d points at Z=%.0f",
            len(grid_xs) * len(grid_ys),
            z_hover,
        )

        for gx in grid_xs:
            for gy in grid_ys:
                logger.info("Moving to (%.0f, %.0f, %.0f)...", gx, gy, z_hover)
                ack = await move_cartesian(ws, gx, gy, z_hover)

                if not ack:
                    logger.warning(
                        "Skip (%.0f, %.0f): unreachable or IK failure.", gx, gy
                    )
                    continue

                perr = ack.get("position_error_mm", 0)
                if perr > 3.0:
                    logger.warning(
                        "Skip (%.0f, %.0f): position error %.1f mm too high.",
                        gx,
                        gy,
                        perr,
                    )
                    continue

                # Settle, then sample the marker pixel
                await asyncio.sleep(SETTLE_TIME)
                samples: list[tuple[float, float]] = []
                for _ in range(NUM_SAMPLES):
                    g = read_grip()
                    if g is not None:
                        samples.append(g)
                    await asyncio.sleep(0.15)

                if len(samples) < MIN_SAMPLES:
                    logger.warning(
                        "Skip (%.0f, %.0f): only %d/%d marker samples.",
                        gx,
                        gy,
                        len(samples),
                        MIN_SAMPLES,
                    )
                    continue

                # Average pixel position
                px_x = float(np.mean([s[0] for s in samples]))
                px_y = float(np.mean([s[1] for s in samples]))

                # Achieved arm-XY from the IK/FK
                ee = ack.get("end_effector", {})
                arm_x = ee.get("x", gx)
                arm_y = ee.get("y", gy)

                pts_px.append([px_x, px_y])
                pts_xy.append([arm_x, arm_y])
                rows.append([gx, gy, px_x, px_y, arm_x, arm_y])
                logger.info(
                    "  Point: target(%.0f,%.0f) → ee(%.1f,%.1f) → px(%.0f,%.0f)",
                    gx,
                    gy,
                    arm_x,
                    arm_y,
                    px_x,
                    px_y,
                )

        # Park central after calibration
        mid_x = float(np.mean(grid_xs))
        mid_y = float(np.mean(grid_ys))
        await move_cartesian(ws, mid_x, mid_y, z_hover)

    # Compute homography
    logger.info("Collected %d valid calibration points.", len(pts_px))
    if len(pts_px) < 4:
        logger.error(
            "Need >= 4 points for homography; only got %d. Aborting.",
            len(pts_px),
        )
        return

    P = np.array(pts_px, dtype=np.float64)
    W = np.array(pts_xy, dtype=np.float64)
    H, _ = cv2.findHomography(P, W, cv2.RANSAC, 3.0)
    method = "homography"

    if H is None:
        logger.warning("Homography failed; falling back to affine.")
        M, _ = cv2.estimateAffine2D(P, W)
        H = np.vstack([M, [0, 0, 1]])
        method = "affine"

    # Compute reprojection error
    Ph = np.hstack([P, np.ones((len(P), 1))])
    pred = (H @ Ph.T).T
    pred = pred[:, :2] / pred[:, 2:3]
    errors = np.linalg.norm(pred - W, axis=1)
    mean_err = float(errors.mean())
    max_err = float(errors.max())

    logger.info(
        "Method=%s, reproj error: mean=%.2f mm, max=%.2f mm",
        method,
        mean_err,
        max_err,
    )

    # Persist
    cal_data = {
        "type": method,
        "H": H.tolist(),
        "rail_mm": rail_mm,
        "z_plane": z_hover,
        "camera": "OAK-4 S overhead",
        "camera_ip": "192.168.1.138",
        "points": rows,
        "n_points": len(rows),
        "reproj_mean_mm": mean_err,
        "reproj_max_mm": max_err,
        "calibrated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    OUTPUT_PATH.write_text(json.dumps(cal_data, indent=2))
    logger.info("Calibration saved to %s", OUTPUT_PATH)
    print(f"\n✓ Calibration complete: {method}, {len(rows)} points")
    print(f"  Reprojection error: mean={mean_err:.2f} mm, max={max_err:.2f} mm")
    print(f"  Saved: {OUTPUT_PATH}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse arguments and run the overhead calibration routine."""
    global OUTPUT_PATH
    parser = argparse.ArgumentParser(
        description="OAK-4 S overhead hand-eye calibration."
    )
    parser.add_argument(
        "--z-hover",
        type=float,
        default=DEFAULT_Z_HOVER,
        help=f"Hover Z during calibration (default: {DEFAULT_Z_HOVER}).",
    )
    parser.add_argument(
        "--center-x",
        type=float,
        default=DEFAULT_GRID_CENTER_X,
        help=f"Grid center X (default: {DEFAULT_GRID_CENTER_X}).",
    )
    parser.add_argument(
        "--center-y",
        type=float,
        default=DEFAULT_GRID_CENTER_Y,
        help=f"Grid center Y (default: {DEFAULT_GRID_CENTER_Y}).",
    )
    parser.add_argument(
        "--range",
        type=float,
        default=DEFAULT_GRID_RANGE,
        help=f"Grid half-range in mm (default: {DEFAULT_GRID_RANGE}).",
    )
    parser.add_argument(
        "--step",
        type=float,
        default=DEFAULT_GRID_STEP,
        help=f"Grid step size in mm (default: {DEFAULT_GRID_STEP}).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(OUTPUT_PATH),
        help=f"Output calibration JSON path (default: {OUTPUT_PATH}).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Build grid
    half = args.range
    grid_xs = list(
        np.arange(args.center_x - half, args.center_x + half + 0.01, args.step)
    )
    grid_ys = list(
        np.arange(args.center_y - half, args.center_y + half + 0.01, args.step)
    )

    if args.output != str(OUTPUT_PATH):
        OUTPUT_PATH = Path(args.output)

    logger.info(
        "Grid: X=%s, Y=%s (%d points total)",
        [f"{x:.0f}" for x in grid_xs],
        [f"{y:.0f}" for y in grid_ys],
        len(grid_xs) * len(grid_ys),
    )

    asyncio.run(run_calibration(args.z_hover, grid_xs, grid_ys))


if __name__ == "__main__":
    main()
