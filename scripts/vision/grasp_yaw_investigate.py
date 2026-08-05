"""Investigate the TRUE grasp-yaw controllability via rail + J0 (edge case C1).

The generated `grasp_yaw_solver.py` reported "only 0deg works", but that is a
solver bug (it never fixes J0 and sweeps the rail along the reach axis, which
cannot change the azimuth for an on-axis target). This script does the correct
geometric analysis:

For a vertical clean-wrist gripper (J4=-90, J5=0, J3 for tilt), the finger yaw
is a function of the base yaw J0, and J0 sets the reach azimuth. To hold a fixed
world target while changing J0, the base must translate (the rail). The base
moves along ONE axis, so we solve: pick rail r so the vector base->target has
the azimuth that J0 reaches; then check the planar reach (distance, height) is
achievable with a vertical gripper. The achievable finger-yaw range = the set of
J0 for which such an r exists within rail travel AND the reach is valid.

Because the physical rail direction (in the arm base frame) is not certain, we
evaluate BOTH a rail along base-Y and a rail along base-X.
"""

from __future__ import annotations

import numpy as np

from armold_controller.ik_solver import ArmIK
from scripts.vision.clean_column import solve_j123  # planar (d,z) reachability

RAIL_MIN, RAIL_MAX = 0.0, 406.0


def reach_azimuth(ik: ArmIK, j0_deg: float) -> float:
    """World-XY azimuth (deg) the arm reaches at base yaw J0 (mid extension)."""
    p = ik.fk([j0_deg, -45.0, 90.0, -45.0, -90.0, 0.0])
    return float(np.degrees(np.arctan2(p.y, p.x)))


def planar_reachable(ik: ArmIK, dist: float, z: float) -> tuple[bool, float]:
    """Is (horizontal distance, height z) reachable with a vertical gripper?

    Uses the azimuth-invariant planar sub-problem (solve J1,J2,J3 with J0=0,
    target on the -X axis at the given distance). Returns (ok, tilt_deg).
    """
    _cfg, perr, tilt = solve_j123(ik, -abs(dist), z, np.array([-30.0, 80.0, 0.0]))
    return (perr < 2.0 and tilt < 3.0), tilt


def yaw_window(
    ik: ArmIK, tx: float, ty: float, tz: float, rail_axis: str
) -> list[float]:
    """Return the achievable finger yaws (deg) at target (tx,ty,tz) for a rail axis."""
    achievable: list[float] = []
    for finger_yaw in range(-90, 91, 5):
        j0 = -float(finger_yaw)  # finger_yaw = -J0 (verified C1)
        az = np.radians(reach_azimuth(ik, j0))  # azimuth the arm reaches at J0
        # Solve rail r so vector base->target has azimuth `az`.
        # base = (r,0) if rail along X, (0,r) if along Y. target_base = target-base.
        # tan(az) = (ty - by) / (tx - bx)
        if rail_axis == "Y":
            # bx=0, by=r  -> (ty-r)/tx = tan(az) -> r = ty - tx*tan(az)
            if abs(np.cos(az)) < 1e-6:
                continue
            r = ty - tx * np.tan(az)
            bx, by = 0.0, r
        else:  # rail along X
            # by=0 -> ty/(tx-r) = tan(az) -> tx - r = ty/tan(az) -> r = tx - ty/tan(az)
            if abs(np.sin(az)) < 1e-6:
                # az ~ 0/180: target must already be on-axis (ty~0); any r keeps az
                if abs(ty) >= 1.0:
                    continue
                r = 0.0
            else:
                r = tx - ty / np.tan(az)
            bx, by = r, 0.0
        if r < RAIL_MIN or r > RAIL_MAX:
            continue
        dist = float(np.hypot(tx - bx, ty - by))
        ok, _ = planar_reachable(ik, dist, tz)
        if ok:
            achievable.append(float(finger_yaw))
    return achievable


def main() -> None:
    ik = ArmIK()
    print("reach_azimuth vs J0 (deg):")
    for j0 in (-60, -30, 0, 30, 60):
        print(f"  J0={j0:+4d} -> azimuth {reach_azimuth(ik, j0):+.1f}")
    print()
    for tx, ty, tz in [(-350, 0, 100), (-300, 50, 100), (-400, 0, 80)]:
        for axis in ("Y", "X"):
            w = yaw_window(ik, tx, ty, tz, axis)
            if w:
                print(
                    f"target({tx:+4d},{ty:+3d},{tz:3d}) rail//{axis}: "
                    f"yaw window [{min(w):+.0f}, {max(w):+.0f}]deg "
                    f"({len(w)} of 37 sampled)"
                )
            else:
                print(f"target({tx:+4d},{ty:+3d},{tz:3d}) rail//{axis}: NONE")


if __name__ == "__main__":
    main()
