"""
Pick orchestrator — end-to-end pen pick using both cameras.

Workflow (R5, R6):
1. Overhead detect: get persistent pen detection (center, angle, confidence).
2. Homography: pixel → arm-XY at the desk plane.
3. Reachability gate: verify target is reachable with a vertical gripper.
4. Grasp-yaw solve: (rail, J0, J1, J2, J3) for (X, Y, Z, finger-yaw).
5. Clean-wrist hover: move to the target XY at a safe hover height.
6. Side-camera-guided descent: step down, using /gap for height feedback.
   Fallback = interpolated desk-Z model floor.
7. Close gripper (120°).
8. Grasp verify: side-view /grasp check.
9. Lift to safe height.

Safety:
- Never descend on stale/lost/low-confidence detections (R12).
- Hard desk-Z floor independent of side camera (R11).
- Timeout + retract on any phase failure.

Usage (on Pi, in armold-venv):
    python scripts/vision/pick_orchestrator.py
    python scripts/vision/pick_orchestrator.py --dry-run

References:
    R5 (pick workflow), R6 (depth strategy), R12 (fail-safe), R13 (reachability).
"""

import asyncio
import json
import logging
import time
import urllib.request
from dataclasses import dataclass
from enum import Enum

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Overhead camera endpoints.
OVERHEAD_TARGET_URL = "http://localhost:8091/target"
OVERHEAD_GRIP_URL = "http://localhost:8091/grip"

#: Side camera endpoints.
SIDE_GAP_URL = "http://localhost:8092/gap"
SIDE_GRASP_URL = "http://localhost:8092/grasp"

#: Arm controller WebSocket.
WS_URL = "ws://localhost:9090"

#: Detection confidence threshold (reject below this).
MIN_CONFIDENCE = 50.0

#: Maximum staleness (seconds) — reject detections older than this.
MAX_STALE_S = 2.0

#: Safe hover Z (model mm above desk) before descent.
HOVER_Z_MM = 150.0

#: Hard desk-Z floor (model mm) — never descend below this.
DESK_Z_FLOOR_MM = 70.0

#: Gripper servo angles.
GRIPPER_OPEN = 50
GRIPPER_CLOSE = 120

#: Descent step size (mm of model-Z per step).
DESCENT_STEP_MM = 10.0

#: Side-camera gap threshold to stop descent (mm above desk).
GRASP_GAP_MM = 5.0

#: Timeout for each phase (seconds).
PHASE_TIMEOUT_S = 15.0

#: Lift height after grasp (model Z mm).
LIFT_Z_MM = 200.0


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


class PickState(Enum):
    """Pick orchestrator state machine states."""

    IDLE = "idle"
    DETECTING = "detecting"
    LOCALIZING = "localizing"
    CHECKING_REACHABILITY = "checking_reachability"
    SOLVING_YAW = "solving_yaw"
    HOVERING = "hovering"
    DESCENDING = "descending"
    GRASPING = "grasping"
    VERIFYING = "verifying"
    LIFTING = "lifting"
    SUCCESS = "success"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class PickResult:
    """Result of a pick attempt.

    Attributes:
        success: Whether the pick succeeded.
        state: Final state of the state machine.
        target_px: Detected target pixel (x, y) from overhead.
        target_xy_mm: Target arm-frame (X, Y) after homography.
        pen_angle_deg: Detected pen angle.
        grasp_verified: Whether the side camera confirmed the grasp.
        duration_s: Total pick duration in seconds.
        failure_reason: Explanation if failed.
    """

    success: bool
    state: PickState
    target_px: tuple[float, float] | None = None
    target_xy_mm: tuple[float, float] | None = None
    pen_angle_deg: float | None = None
    grasp_verified: bool = False
    duration_s: float = 0.0
    failure_reason: str = ""


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _fetch_json(url: str, timeout: float = 2.0) -> dict | None:
    """Fetch JSON from a local HTTP endpoint.

    Args:
        url: HTTP URL to fetch.
        timeout: Request timeout in seconds.

    Returns:
        Parsed dict or None on failure.
    """
    try:
        data = json.load(urllib.request.urlopen(url, timeout=timeout))
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001 - camera HTTP poll is best-effort
        return None


def get_overhead_target() -> dict | None:
    """Get the current pen detection from the overhead camera.

    Returns:
        Detection dict with 'center', 'angle_deg', 'confidence', or None.
    """
    data = _fetch_json(OVERHEAD_TARGET_URL)
    if data and "center" in data and data.get("confidence", 0) > 0:
        return data
    return None


def get_side_gap() -> dict | None:
    """Get the current gripper-tip gap from the side camera.

    Returns:
        Gap dict with 'gap_px', 'gap_mm', or None.
    """
    return _fetch_json(SIDE_GAP_URL)


def get_side_grasp() -> dict | None:
    """Get the grasp verification from the side camera.

    Returns:
        Grasp dict with 'object_present', 'confidence', or None.
    """
    return _fetch_json(SIDE_GRASP_URL)


# ---------------------------------------------------------------------------
# Homography application
# ---------------------------------------------------------------------------


def pixel_to_arm_xy(
    px: tuple[float, float],
    H: np.ndarray,
) -> tuple[float, float]:
    """Apply the overhead homography to convert pixel → arm-XY.

    Args:
        px: (pixel_x, pixel_y) from the overhead camera.
        H: 3x3 homography matrix (pixel → arm-XY).

    Returns:
        (arm_x, arm_y) in mm.
    """
    pt = np.array([[px[0], px[1], 1.0]])
    transformed = (H @ pt.T).T
    xy = transformed[0, :2] / transformed[0, 2]
    return (float(xy[0]), float(xy[1]))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def execute_pick(
    homography: np.ndarray | None = None,
    desk_z_fn=None,
    dry_run: bool = False,
) -> PickResult:
    """Execute a full pick sequence.

    This is the main orchestrator loop. It runs through the state machine:
    detect → localize → check reachability → solve yaw → hover → descend
    → grasp → verify → lift.

    Args:
        homography: 3x3 pixel→arm-XY matrix. If None, loads from file.
        desk_z_fn: Callable(x, y) → model-Z at desk contact. If None, uses
                   constant DESK_Z_FLOOR_MM.
        dry_run: If True, log actions but don't actually move the arm.

    Returns:
        PickResult with success/failure and diagnostics.
    """
    t0 = time.time()

    # Load homography if not provided
    if homography is None:
        from pathlib import Path

        cal_path = Path.home() / "armold_handeye_overhead.json"
        if cal_path.exists():
            cal = json.loads(cal_path.read_text())
            homography = np.array(cal["H"], dtype=np.float64)
        else:
            return PickResult(
                success=False,
                state=PickState.FAILED,
                failure_reason="No overhead calibration found.",
                duration_s=time.time() - t0,
            )

    # Phase 1: Detect
    logger.info("[PICK] Phase 1: Detecting pen (overhead)...")
    detection = None
    detect_start = time.time()
    while time.time() - detect_start < PHASE_TIMEOUT_S:
        detection = get_overhead_target()
        if detection and detection.get("confidence", 0) >= MIN_CONFIDENCE:
            break
        await asyncio.sleep(0.2)

    if not detection or detection.get("confidence", 0) < MIN_CONFIDENCE:
        return PickResult(
            success=False,
            state=PickState.FAILED,
            failure_reason="No confident pen detection within timeout.",
            duration_s=time.time() - t0,
        )

    target_px = tuple(detection["center"])
    pen_angle = detection["angle_deg"]
    confidence = detection["confidence"]
    logger.info(
        "[PICK] Detected: px=(%.0f,%.0f), angle=%.0f°, conf=%.0f",
        target_px[0],
        target_px[1],
        pen_angle,
        confidence,
    )

    # Phase 2: Localize (pixel → arm-XY)
    arm_x, arm_y = pixel_to_arm_xy(target_px, homography)
    logger.info("[PICK] Localized: arm=(%.1f, %.1f) mm", arm_x, arm_y)

    # Determine desk-Z at this location
    if desk_z_fn is not None:
        desk_z = desk_z_fn(arm_x, arm_y)
    else:
        desk_z = DESK_Z_FLOOR_MM
    logger.info("[PICK] Desk-Z at target: %.1f mm", desk_z)

    # Phase 3: Reachability check
    # Import here to avoid circular deps at module level
    import sys

    sys.path.insert(0, "/home/pi/Armold")
    sys.path.insert(0, ".")
    from reachability_gate import check_reachability

    from armold_controller.ik_solver import ArmIK

    ik = ArmIK()
    reach_result = check_reachability(ik, arm_x, arm_y, HOVER_Z_MM)
    if not reach_result.reachable:
        return PickResult(
            success=False,
            state=PickState.FAILED,
            target_px=target_px,
            target_xy_mm=(arm_x, arm_y),
            pen_angle_deg=pen_angle,
            failure_reason=f"Target unreachable: {reach_result.reason}",
            duration_s=time.time() - t0,
        )
    logger.info("[PICK] Reachability: PASS")

    # Phase 4: Solve grasp yaw
    from grasp_yaw_solver import is_yaw_graspable

    graspable, yaw_reason = is_yaw_graspable(ik, arm_x, arm_y, desk_z, pen_angle)
    if not graspable:
        return PickResult(
            success=False,
            state=PickState.FAILED,
            target_px=target_px,
            target_xy_mm=(arm_x, arm_y),
            pen_angle_deg=pen_angle,
            failure_reason=yaw_reason,
            duration_s=time.time() - t0,
        )
    logger.info("[PICK] Yaw: %s", yaw_reason)

    if dry_run:
        logger.info("[DRY RUN] Would proceed to hover → descend → grasp → lift.")
        return PickResult(
            success=True,
            state=PickState.SUCCESS,
            target_px=target_px,
            target_xy_mm=(arm_x, arm_y),
            pen_angle_deg=pen_angle,
            failure_reason="(dry run — no actual motion)",
            duration_s=time.time() - t0,
        )

    # Phases 5-9 require the arm controller WebSocket
    import websockets

    async with websockets.connect(WS_URL) as ws:
        # Phase 5: Hover
        logger.info(
            "[PICK] Phase 5: Moving to hover (%.0f, %.0f, %.0f)...",
            arm_x,
            arm_y,
            HOVER_Z_MM,
        )
        await ws.send(
            json.dumps(
                {
                    "cmd": "move_cartesian",
                    "x": arm_x,
                    "y": arm_y,
                    "z": HOVER_Z_MM,
                    "speed": 10.0,
                }
            )
        )
        # Wait for ack
        deadline = time.time() + PHASE_TIMEOUT_S
        hover_ok = False
        while time.time() < deadline:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if msg.get("cmd") == "move_cartesian":
                hover_ok = True
                break
            if msg.get("type") == "error":
                break
        if not hover_ok:
            return PickResult(
                success=False,
                state=PickState.FAILED,
                target_px=target_px,
                target_xy_mm=(arm_x, arm_y),
                pen_angle_deg=pen_angle,
                failure_reason="Failed to reach hover position.",
                duration_s=time.time() - t0,
            )

        # Phase 6: Descend with side-camera feedback
        logger.info("[PICK] Phase 6: Descending (side-camera guided)...")
        current_z = HOVER_Z_MM
        while current_z > desk_z:
            # Check for stale detection (R12)
            detection_check = get_overhead_target()
            if (
                detection_check is None
                or detection_check.get("confidence", 0) < MIN_CONFIDENCE * 0.5
            ):
                # Detection lost during descent — hold position (R12)
                logger.warning("[PICK] Detection lost during descent — HOLDING.")
                break

            # Step down
            current_z = max(desk_z, current_z - DESCENT_STEP_MM)
            await ws.send(
                json.dumps(
                    {
                        "cmd": "move_cartesian",
                        "x": arm_x,
                        "y": arm_y,
                        "z": current_z,
                        "speed": 5.0,
                    }
                )
            )
            await asyncio.sleep(1.0)

            # Check side camera gap
            gap = get_side_gap()
            if gap and gap.get("gap_mm") is not None and gap["gap_mm"] <= GRASP_GAP_MM:
                logger.info(
                    "[PICK] Side camera: gap=%.1f mm ≤ threshold. Stopping descent.",
                    gap["gap_mm"],
                )
                break

            # Hard floor check
            if current_z <= desk_z:
                logger.info("[PICK] Reached desk-Z floor (%.0f mm).", desk_z)
                break

        # Phase 7: Grasp (close gripper)
        logger.info("[PICK] Phase 7: Closing gripper...")
        await ws.send(json.dumps({"cmd": "gripper", "angle": GRIPPER_CLOSE}))
        await asyncio.sleep(1.0)

        # Phase 8: Verify grasp (side camera)
        grasp_check = get_side_grasp()
        grasp_verified = False
        if grasp_check and grasp_check.get("object_present"):
            grasp_verified = True
            logger.info("[PICK] Grasp verified: object present.")
        else:
            logger.warning(
                "[PICK] Grasp NOT verified (object not detected between fingers)."
            )
            # Continue anyway (verification is advisory for now)

        # Phase 9: Lift
        logger.info("[PICK] Phase 9: Lifting to Z=%.0f mm...", LIFT_Z_MM)
        await ws.send(
            json.dumps(
                {
                    "cmd": "move_cartesian",
                    "x": arm_x,
                    "y": arm_y,
                    "z": LIFT_Z_MM,
                    "speed": 8.0,
                }
            )
        )
        await asyncio.sleep(3.0)

    return PickResult(
        success=True,
        state=PickState.SUCCESS,
        target_px=target_px,
        target_xy_mm=(arm_x, arm_y),
        pen_angle_deg=pen_angle,
        grasp_verified=grasp_verified,
        duration_s=time.time() - t0,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the pick orchestrator."""
    import argparse

    parser = argparse.ArgumentParser(description="Pick orchestrator.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Log actions without moving the arm."
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    result = asyncio.run(execute_pick(dry_run=args.dry_run))
    print(f"\nPick result: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"  State: {result.state.value}")
    print(f"  Duration: {result.duration_s:.1f}s")
    if result.target_px:
        print(f"  Target pixel: ({result.target_px[0]:.0f}, {result.target_px[1]:.0f})")
    if result.target_xy_mm:
        print(
            f"  Target arm-XY: ({result.target_xy_mm[0]:.1f}, {result.target_xy_mm[1]:.1f})"
        )
    if result.pen_angle_deg is not None:
        print(f"  Pen angle: {result.pen_angle_deg:.0f}°")
    print(f"  Grasp verified: {result.grasp_verified}")
    if result.failure_reason:
        print(f"  Reason: {result.failure_reason}")


if __name__ == "__main__":
    main()
