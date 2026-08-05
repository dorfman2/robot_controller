"""
Reachability gate for the pick orchestrator.

Before any pick, verifies the target is reachable with a vertical clean-wrist
gripper (J4=-90, J5=0) at the current or a commandable rail position.
Unreachable targets are REJECTED — no clamped or partial moves.

Usage:
    from reachability_gate import check_reachability, ReachabilityResult
    result = check_reachability(ik, target_x, target_y, target_z)
    if not result.reachable:
        print(f"REJECT: {result.reason}")

References:
    R13 (reachability gating), design.md edge cases (kinematics).
"""

import logging
import sys
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

sys.path.insert(0, "/home/pi/Armold")
sys.path.insert(0, ".")
try:
    from armold_controller.ik_solver import ArmIK, CartesianTarget
except ImportError as exc:
    logger.error("Cannot import ArmIK: %s", exc)
    raise


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Rail travel limits (mm).
RAIL_MIN: float = 0.0
RAIL_MAX: float = 406.0

#: Maximum arm horizontal reach (to J5, excluding perpendicular tool).
MAX_REACH_MM: float = 490.0

#: Minimum Z achievable with a vertical gripper at x=-400 (empirical).
MIN_Z_AT_MAX_REACH: float = 0.0

#: Maximum X for desk contact with a vertical gripper (empirical).
MAX_DESK_REACH_X: float = -400.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ReachabilityResult:
    """Result of a reachability check.

    Attributes:
        reachable: Whether the target can be reached.
        rail_mm: Suggested rail position for reaching the target, or None.
        joint_angles_deg: IK solution if reachable, else None.
        reason: Explanation of why the target is not reachable.
        distance_from_base_mm: XY distance from arm base to target.
        requires_rail_move: Whether the rail must move to reach the target.
    """

    reachable: bool
    rail_mm: float | None = None
    joint_angles_deg: list[float] | None = None
    reason: str = ""
    distance_from_base_mm: float = 0.0
    requires_rail_move: bool = False


# ---------------------------------------------------------------------------
# Reachability check
# ---------------------------------------------------------------------------


def check_reachability(
    ik: ArmIK,
    target_x: float,
    target_y: float,
    target_z: float,
    rail_current: float = 0.0,
    require_vertical: bool = True,
) -> ReachabilityResult:
    """Check if a target is reachable with a vertical clean-wrist gripper.

    Strategy:
    1. Quick geometric check: is the XY distance within the arm's reach?
    2. Full IK check: can the solver find a solution at the target?
    3. If not reachable at current rail, check if a rail move would help.

    Args:
        ik: ArmIK instance.
        target_x: Target X in arm-frame (mm). Negative = away from base.
        target_y: Target Y in arm-frame (mm).
        target_z: Target Z in arm-frame (mm, height above desk).
        rail_current: Current rail position (mm).
        require_vertical: If True, use a vertical-gripper seed (J4=-90, J5=0).

    Returns:
        ReachabilityResult with reachable flag, solution, and diagnostics.
    """
    # Step 1: Geometric pre-check
    xy_distance = float(np.sqrt(target_x**2 + target_y**2))

    if xy_distance > MAX_REACH_MM:
        return ReachabilityResult(
            reachable=False,
            distance_from_base_mm=xy_distance,
            reason=(
                f"Target ({target_x:.0f}, {target_y:.0f}) is {xy_distance:.0f} mm "
                f"from base (max reach {MAX_REACH_MM:.0f} mm). "
                f"Cannot reach even with rail at 0."
            ),
        )

    # Step 2: IK check with vertical-gripper seed
    target = CartesianTarget(x=target_x, y=target_y, z=target_z)
    seed = [0.0, -30.0, 80.0, -30.0, -90.0, 0.0] if require_vertical else None
    result = ik.solve_ik(target, seed_deg=seed)

    if result.success and result.position_error_mm < 5.0:
        # Check that J4 is near -90 and J5 near 0 (vertical gripper maintained)
        j4 = result.joint_angles_deg[4]
        j5 = result.joint_angles_deg[5]
        if require_vertical and (abs(j4 - (-90)) > 10 or abs(j5) > 10):
            # IK solved but gripper isn't vertical
            return ReachabilityResult(
                reachable=False,
                distance_from_base_mm=xy_distance,
                reason=(
                    f"IK solved but gripper not vertical "
                    f"(J4={j4:.0f}°, J5={j5:.0f}°). "
                    f"Target may be at the edge of the vertical-gripper workspace."
                ),
            )

        return ReachabilityResult(
            reachable=True,
            rail_mm=rail_current,
            joint_angles_deg=list(result.joint_angles_deg),
            distance_from_base_mm=xy_distance,
            requires_rail_move=False,
        )

    # Step 3: Current rail position doesn't work — check if a rail move helps
    # The rail shifts the arm base along one axis. Try different offsets.
    for rail_offset in [50, 100, 150, 200, -50, -100, -150, -200]:
        candidate_rail = rail_current + rail_offset
        if candidate_rail < RAIL_MIN or candidate_rail > RAIL_MAX:
            continue

        # In arm-frame, rail offset shifts the target X
        shifted_target = CartesianTarget(
            x=target_x - rail_offset,
            y=target_y,
            z=target_z,
        )
        shifted_result = ik.solve_ik(shifted_target, seed_deg=seed)

        if shifted_result.success and shifted_result.position_error_mm < 5.0:
            j4 = shifted_result.joint_angles_deg[4]
            j5 = shifted_result.joint_angles_deg[5]
            if require_vertical and (abs(j4 - (-90)) > 10 or abs(j5) > 10):
                continue

            return ReachabilityResult(
                reachable=True,
                rail_mm=candidate_rail,
                joint_angles_deg=list(shifted_result.joint_angles_deg),
                distance_from_base_mm=xy_distance,
                requires_rail_move=True,
                reason=f"Reachable with rail at {candidate_rail:.0f} mm "
                f"(current: {rail_current:.0f}).",
            )

    # Not reachable at any rail position
    return ReachabilityResult(
        reachable=False,
        distance_from_base_mm=xy_distance,
        reason=(
            f"Target ({target_x:.0f}, {target_y:.0f}, {target_z:.0f}) "
            f"not reachable with a vertical gripper at any rail position "
            f"[{RAIL_MIN:.0f}, {RAIL_MAX:.0f}]."
        ),
    )


# ---------------------------------------------------------------------------
# Test / Demo
# ---------------------------------------------------------------------------


def main() -> None:
    """Demonstrate the reachability gate with test targets."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    ik = ArmIK()
    print("Reachability Gate Test")
    print("=" * 60)

    test_cases = [
        (-350, 0, 100, "Normal pick zone"),
        (-400, 0, 80, "Edge of reach"),
        (-300, 50, 150, "Off-center, high"),
        (-500, 0, 50, "Beyond reach"),
        (-200, 100, 200, "Close but off to the side"),
        (-350, 0, 10, "Very low (near desk)"),
    ]

    print(f"\n{'Target (X,Y,Z)':<18} {'Reach?':<8} {'Rail':<8} {'Note'}")
    print("-" * 70)
    for tx, ty, tz, note in test_cases:
        result = check_reachability(ik, float(tx), float(ty), float(tz))
        reach = "YES" if result.reachable else "NO"
        rail = f"{result.rail_mm:.0f}" if result.rail_mm is not None else "-"
        rail_note = " (rail move)" if result.requires_rail_move else ""
        print(f"({tx:>4},{ty:>3},{tz:>3})     {reach:<8} {rail:<8} {note}{rail_note}")
        if not result.reachable:
            print(f"  → {result.reason}")


if __name__ == "__main__":
    main()
