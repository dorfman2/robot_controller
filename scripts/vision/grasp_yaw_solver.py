"""
Grasp-yaw solver — solve (rail, J0, J1, J2, J3) for (X, Y, Z, finger-yaw).

Kinematic basis (verified on the RTB model, edge case C1):
    * For a vertical clean-wrist gripper the wrist is fixed at J4 = -90, J5 = 0
      and J3 provides the pitch that keeps the tool pointing straight down.
      Wrist joints do NOT yaw the gripper — they tilt it.
    * The finger-opening line yaws only with the base joint J0. With this
      arm's convention, ``finger_yaw = -J0`` (finger_yaw = 0 means the fingers
      lie along the base +Y axis) and the arm reaches along azimuth
      ``180 deg - J0`` in the base frame.
    * J0 also sets the reach azimuth, so J0 alone cannot hold a fixed target
      while changing yaw. The LINEAR RAIL (confirmed physically PERPENDICULAR
      to the reach, i.e. along the base Y axis) is the decoupling DOF: sliding
      the arm base along Y repositions it so the SAME J0 (yaw) still reaches
      the target.

Geometry:
    The arm base (rail carriage) sits at base-frame origin offset ``(0, rail,
    0)``; ``ArmIK`` computes FK/IK in that base frame. A target given in the
    (rail-independent) workspace frame at ``(X, Y, Z)`` is, relative to the
    carriage, ``(X, Y - rail, Z)``. For a chosen finger yaw:
        1. J0 = -finger_yaw  -> reach azimuth ``az = 180 - J0`` (deg).
        2. The base->target vector must point along ``az``. With the base on
           the Y rail (base_x = 0), require ``(X, Y - rail)`` parallel to
           ``(cos az, sin az)`` with positive length ``d``:
               d    = X / cos(az)              (d > 0 for the -X reach)
               rail = Y - d * sin(az)
        3. If ``rail`` is within travel, solve the planar J1/J2/J3 for a
           vertical gripper at horizontal distance ``d`` and height ``Z``.
    Because the tool's verticality is invariant to J0, the planar J1/J2/J3
    solution (found in the canonical -X plane) is valid at the real J0.

This module is pure (no I/O, no mocks) and is covered by
``test_grasp_yaw_solver.py`` with the real ``ArmIK``.

References: R10 (grasp-yaw decoupling via rail), edge case C1, design.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from spatialmath import SE3

from armold_controller.ik_solver import ArmIK

logger = logging.getLogger(__name__)

# Fixed wrist/base joints for a clean vertical gripper.
J4_FIXED: float = -90.0
J5_FIXED: float = 0.0

# Rail travel limits (mm) and J0 limits (deg).
RAIL_MIN: float = 0.0
RAIL_MAX: float = 406.0
J0_MIN: float = -180.0
J0_MAX: float = 180.0

# Rail bound tolerance (mm) to absorb trig float noise at yaw extremes.
RAIL_EPS_MM: float = 1e-3

# Convergence tolerances.
POS_TOL_MM: float = 2.0
TILT_TOL_DEG: float = 3.0
VERTICAL_DOT: float = -0.98  # approach-axis Z below this counts as "down"


@dataclass
class GraspYawSolution:
    """Result of solving for a grasp at a specified finger yaw.

    Attributes:
        rail_mm: Required rail position along base-Y (mm).
        joint_angles_deg: Full six arm joint angles ``[J0, J1, J2, J3, J4,
            J5]`` (degrees), with J4 = -90 and J5 = 0.
        finger_yaw_deg: Achieved finger yaw (degrees; equals the request on
            success, since J0 = -finger_yaw is set exactly).
        target_x: Workspace target X (mm).
        target_y: Workspace target Y (mm).
        target_z: Workspace target Z (mm).
        position_error_mm: Euclidean FK tool-tip error from the target in the
            base frame (mm).
        tilt_deg: Tool tilt from vertical (degrees; 0 = straight down).
        success: True when reachable, in rail travel, and vertical.
        failure_reason: Human-readable explanation when ``success`` is False.
    """

    rail_mm: float
    joint_angles_deg: list[float]
    finger_yaw_deg: float
    target_x: float
    target_y: float
    target_z: float
    position_error_mm: float
    tilt_deg: float
    success: bool
    failure_reason: str = ""


@dataclass
class YawWindow:
    """Achievable finger-yaw range at a target XY, given rail travel.

    Attributes:
        target_x: Workspace target X (mm).
        target_y: Workspace target Y (mm).
        target_z: Workspace target Z (mm).
        achievable_yaws_deg: Sorted list of achievable finger yaws (degrees).
        min_yaw_deg: Minimum achievable finger yaw (degrees); NaN if none.
        max_yaw_deg: Maximum achievable finger yaw (degrees); NaN if none.
    """

    target_x: float
    target_y: float
    target_z: float
    achievable_yaws_deg: list[float]
    min_yaw_deg: float
    max_yaw_deg: float


def approach_axis(ik: ArmIK, cfg_deg: list[float]) -> np.ndarray:
    """Return the world-frame unit vector of the tool approach (EE +Y).

    Args:
        ik: The kinematics engine.
        cfg_deg: Six joint angles (degrees, J0..J5).

    Returns:
        A length-3 unit vector; ``[0, 0, -1]`` means straight down.
    """
    q = np.deg2rad(np.asarray(cfg_deg, dtype=float))
    return np.asarray(SE3(ik.ets.eval(q), check=False).R[:, 1]).ravel()


def _solve_planar_j123(
    ik: ArmIK, dist: float, z: float, seed: np.ndarray
) -> tuple[float, float, float, float, float]:
    """Solve J1,J2,J3 for a vertical gripper at (-dist, 0, z) in the base frame.

    The sub-problem is azimuth-invariant, so it is solved in the canonical
    plane at J0 = 0 (target on the -X axis); the resulting J1/J2/J3 are valid
    at any J0.

    Args:
        ik: The kinematics engine.
        dist: Horizontal distance from the base to the target (mm, > 0).
        z: Target height above the desk (mm).
        seed: Initial guess ``[J1, J2, J3]`` (degrees).

    Returns:
        Tuple ``(J1, J2, J3, position_error_mm, tilt_deg)``.
    """

    def cost(j123: np.ndarray) -> float:
        cfg = [0.0, j123[0], j123[1], j123[2], J4_FIXED, J5_FIXED]
        p = ik.fk(cfg)
        pos_sq = (p.x + dist) ** 2 + p.y**2 + (p.z - z) ** 2
        ax = approach_axis(ik, cfg)
        ori_sq = ax[0] ** 2 + ax[1] ** 2 + (ax[2] + 1.0) ** 2
        return float(pos_sq + 500.0 * ori_sq)

    res = minimize(
        cost,
        seed,
        method="Nelder-Mead",
        options={"xatol": 1e-4, "fatol": 1e-6, "maxiter": 4000},
    )
    j1, j2, j3 = (float(v) for v in res.x)
    cfg = [0.0, j1, j2, j3, J4_FIXED, J5_FIXED]
    p = ik.fk(cfg)
    perr = float(np.sqrt((p.x + dist) ** 2 + p.y**2 + (p.z - z) ** 2))
    ax = approach_axis(ik, cfg)
    tilt = float(np.degrees(np.arccos(np.clip(-ax[2], -1.0, 1.0))))
    return j1, j2, j3, perr, tilt


def solve_grasp_yaw(
    ik: ArmIK,
    target_x: float,
    target_y: float,
    target_z: float,
    finger_yaw_deg: float,
    rail_min: float = RAIL_MIN,
    rail_max: float = RAIL_MAX,
) -> GraspYawSolution:
    """Solve ``(rail, J0, J1, J2, J3)`` to reach a target at a given finger yaw.

    Args:
        ik: The kinematics engine.
        target_x: Workspace target X (mm); the arm reaches toward -X.
        target_y: Workspace target Y (mm); the rail axis is along Y.
        target_z: Workspace target Z / height above the desk (mm).
        finger_yaw_deg: Desired finger yaw (degrees; 0 = fingers along +Y).
        rail_min: Minimum rail position (mm).
        rail_max: Maximum rail position (mm).

    Returns:
        A :class:`GraspYawSolution`. On failure ``success`` is False and
        ``failure_reason`` explains why (J0 limit, rail out of travel, or
        unreachable / non-vertical).
    """

    def _fail(reason: str, rail: float = float("nan")) -> GraspYawSolution:
        return GraspYawSolution(
            rail_mm=rail,
            joint_angles_deg=[-finger_yaw_deg, 0.0, 0.0, 0.0, J4_FIXED, J5_FIXED],
            finger_yaw_deg=finger_yaw_deg,
            target_x=target_x,
            target_y=target_y,
            target_z=target_z,
            position_error_mm=float("inf"),
            tilt_deg=float("nan"),
            success=False,
            failure_reason=reason,
        )

    j0 = -finger_yaw_deg
    if not (J0_MIN <= j0 <= J0_MAX):
        return _fail(f"J0={j0:.1f} deg exceeds limits [{J0_MIN}, {J0_MAX}]")

    az = np.radians(180.0 - j0)
    cos_az = float(np.cos(az))
    if abs(cos_az) < 1e-9:
        return _fail("degenerate reach azimuth (~+/-90 deg); target not on -X reach")

    dist = target_x / cos_az
    if dist <= 0.0:
        return _fail("target lies behind the reach direction for this yaw")

    rail = target_y - dist * float(np.sin(az))
    # Tolerate float noise at the travel bounds (e.g. sin(pi) != 0 at yaw=0),
    # then clamp a tiny overshoot back into the valid range.
    if rail < rail_min - RAIL_EPS_MM or rail > rail_max + RAIL_EPS_MM:
        return _fail(f"rail {rail:.0f} mm out of travel [{rail_min}, {rail_max}]", rail)
    rail = min(rail_max, max(rail_min, rail))

    j1, j2, j3, perr, tilt = _solve_planar_j123(
        ik, dist, target_z, np.array([-30.0, 80.0, -30.0])
    )
    cfg = [j0, j1, j2, j3, J4_FIXED, J5_FIXED]

    # Full-FK check in the base frame: target relative to the carriage is
    # (target_x, target_y - rail, target_z).
    pose = ik.fk(cfg)
    tb_y = target_y - rail
    full_perr = float(
        np.sqrt(
            (pose.x - target_x) ** 2 + (pose.y - tb_y) ** 2 + (pose.z - target_z) ** 2
        )
    )
    ax = approach_axis(ik, cfg)
    vertical = bool(ax[2] < VERTICAL_DOT)

    if perr > POS_TOL_MM or full_perr > 2.0 * POS_TOL_MM or tilt > TILT_TOL_DEG:
        return _fail(
            f"unreachable (planar err {perr:.1f} mm, full err {full_perr:.1f} mm, "
            f"tilt {tilt:.1f} deg) at yaw {finger_yaw_deg:.0f} deg",
            rail,
        )
    if not vertical:
        return _fail(f"gripper not vertical (approach z={ax[2]:.2f})", rail)

    return GraspYawSolution(
        rail_mm=rail,
        joint_angles_deg=cfg,
        finger_yaw_deg=finger_yaw_deg,
        target_x=target_x,
        target_y=target_y,
        target_z=target_z,
        position_error_mm=full_perr,
        tilt_deg=tilt,
        success=True,
    )


def map_yaw_window(
    ik: ArmIK,
    target_x: float,
    target_y: float,
    target_z: float,
    yaw_min: float = -90.0,
    yaw_max: float = 90.0,
    yaw_step: float = 5.0,
    rail_min: float = RAIL_MIN,
    rail_max: float = RAIL_MAX,
) -> YawWindow:
    """Map the achievable finger-yaw range at a target XY across rail travel.

    Sweeps finger yaw over ``[yaw_min, yaw_max]`` and records which values
    yield a valid :class:`GraspYawSolution`.

    Args:
        ik: The kinematics engine.
        target_x: Workspace target X (mm).
        target_y: Workspace target Y (mm).
        target_z: Workspace target Z (mm).
        yaw_min: Minimum finger yaw to test (degrees).
        yaw_max: Maximum finger yaw to test (degrees).
        yaw_step: Sweep step (degrees).
        rail_min: Minimum rail position (mm).
        rail_max: Maximum rail position (mm).

    Returns:
        A :class:`YawWindow` with the achievable yaws (min/max NaN if none).
    """
    achievable: list[float] = []
    for yaw in np.arange(yaw_min, yaw_max + yaw_step / 2.0, yaw_step):
        sol = solve_grasp_yaw(
            ik, target_x, target_y, target_z, float(yaw), rail_min, rail_max
        )
        if sol.success:
            achievable.append(round(float(yaw), 3))
    return YawWindow(
        target_x=target_x,
        target_y=target_y,
        target_z=target_z,
        achievable_yaws_deg=achievable,
        min_yaw_deg=min(achievable) if achievable else float("nan"),
        max_yaw_deg=max(achievable) if achievable else float("nan"),
    )


def required_finger_yaw(pen_angle_deg: float) -> float:
    """Return the finger yaw (deg, in [-90, 90]) that grips a pen at an angle.

    The fingers must close ACROSS the pen (perpendicular to its long axis).
    With the finger-line convention (finger_yaw = deviation from +Y), the
    required finger yaw equals the pen long-axis azimuth reduced modulo 180
    into ``[-90, 90]`` (a pen and its 180-degree rotation are the same grasp).

    Args:
        pen_angle_deg: Pen long-axis azimuth in the arm XY frame (degrees).

    Returns:
        Required finger yaw in ``[-90, 90]`` degrees.
    """
    return ((pen_angle_deg + 90.0) % 180.0) - 90.0


def is_yaw_graspable(
    ik: ArmIK,
    target_x: float,
    target_y: float,
    target_z: float,
    pen_angle_deg: float,
    rail_min: float = RAIL_MIN,
    rail_max: float = RAIL_MAX,
) -> tuple[bool, GraspYawSolution]:
    """Check whether a pen at a given angle is graspable at the target.

    Policy for an out-of-window pen angle is REJECT (do not grasp at the wrong
    angle); the caller may skip the target or request a nudge.

    Args:
        ik: The kinematics engine.
        target_x: Workspace target X (mm).
        target_y: Workspace target Y (mm).
        target_z: Workspace target Z (mm).
        pen_angle_deg: Pen long-axis azimuth in the arm XY frame (degrees).
        rail_min: Minimum rail position (mm).
        rail_max: Maximum rail position (mm).

    Returns:
        Tuple ``(graspable, solution)`` where ``solution`` is the attempted
        :class:`GraspYawSolution` (successful or with a failure reason).
    """
    yaw = required_finger_yaw(pen_angle_deg)
    sol = solve_grasp_yaw(ik, target_x, target_y, target_z, yaw, rail_min, rail_max)
    return sol.success, sol


def main() -> None:
    """Demonstrate the corrected grasp-yaw solver on a few targets."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    ik = ArmIK()
    print(f"Grasp-yaw solver ready ({ik.ets.n} joints)")
    print(
        f"{'target':<18}{'yaw':>5}{'ok':>5}{'rail':>7}{'J0':>7}{'perr':>7}{'tilt':>6}"
    )
    print("-" * 60)
    cases = [
        (-350.0, 0.0, 100.0, 0.0),
        (-350.0, 0.0, 100.0, 30.0),
        (-350.0, 0.0, 100.0, -30.0),
        (-300.0, 50.0, 100.0, 20.0),
        (-400.0, 0.0, 80.0, 0.0),
    ]
    for tx, ty, tz, yaw in cases:
        s = solve_grasp_yaw(ik, tx, ty, tz, yaw)
        ok = "OK" if s.success else "FAIL"
        rail = f"{s.rail_mm:.0f}" if s.success else "-"
        j0 = f"{s.joint_angles_deg[0]:.1f}" if s.success else "-"
        perr = f"{s.position_error_mm:.2f}" if s.success else "-"
        tilt = f"{s.tilt_deg:.1f}" if s.success else "-"
        print(
            f"({tx:.0f},{ty:.0f},{tz:.0f})".ljust(18)
            + f"{yaw:>5.0f}{ok:>5}{rail:>7}{j0:>7}{perr:>7}{tilt:>6}"
        )
        if not s.success:
            print(f"    -> {s.failure_reason}")
    for tx, ty, tz in [(-350.0, 0.0, 100.0), (-300.0, 50.0, 100.0)]:
        w = map_yaw_window(ik, tx, ty, tz)
        rng = (
            f"[{w.min_yaw_deg:+.0f}, {w.max_yaw_deg:+.0f}] deg"
            if w.achievable_yaws_deg
            else "NONE"
        )
        print(
            f"yaw window at ({tx:.0f},{ty:.0f},{tz:.0f}): {rng} "
            f"({len(w.achievable_yaws_deg)} samples)"
        )


if __name__ == "__main__":
    main()
