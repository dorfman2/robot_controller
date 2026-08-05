"""Explore the straight-down-gripper workspace of the Armold arm near the desk.

The tool's long axis is the EE frame +Y axis (the ETS ends with ``ty(tool_len)``).
For the gripper to point straight down, that +Y axis must align with world -Z.
A straight-down gripper still has one free DOF: rotation about the vertical
(the finger-opening direction). This script (a) reports the approach axis and
RPY at the known J4=-90 "pick" landmark, then (b) for a set of desk XY targets
sweeps both the descent Z and the gripper spin, reporting the lowest Z reachable
with a vertical gripper for ANY spin.

Run:
    PYTHONPATH=/Users/jdorfman/Code/Armold .venv/bin/python \
        scripts/vision/explore_straightdown.py
"""

from __future__ import annotations

import numpy as np
from spatialmath import SE3

from armold_controller.ik_solver import ArmIK, CartesianTarget


def spin_rpy(spin_deg: float) -> tuple[float, float, float]:
    """RPY (deg, xyz) for a vertical gripper spun ``spin_deg`` about vertical.

    The EE +Y axis (tool approach) points to world -Z; the EE +X axis (finger
    line) is placed at angle ``spin_deg`` in the world XY plane.

    Args:
        spin_deg: Rotation of the finger line about the vertical, degrees.

    Returns:
        (roll, pitch, yaw) degrees, xyz intrinsic order.
    """
    a = np.deg2rad(spin_deg)
    x_ee = np.array([np.cos(a), np.sin(a), 0.0])
    y_ee = np.array([0.0, 0.0, -1.0])
    z_ee = np.cross(x_ee, y_ee)
    z_ee /= np.linalg.norm(z_ee)
    x_ee = np.cross(y_ee, z_ee)
    r = np.column_stack([x_ee, y_ee, z_ee])
    rpy = SE3(SE3.Rt(r, [0, 0, 0])).rpy(unit="deg", order="xyz")
    return (float(rpy[0]), float(rpy[1]), float(rpy[2]))


def approach_axis(ik: ArmIK, q_deg: list[float]) -> np.ndarray:
    """World-frame unit vector of the tool approach (EE +Y) at ``q_deg``."""
    q = np.deg2rad(np.asarray(q_deg, dtype=float))
    pose = SE3(ik.ets.eval(q), check=False)
    return np.asarray(pose.R[:, 1]).ravel()


def main() -> None:
    """Diagnose the pick landmark and sweep the vertical-gripper workspace."""
    ik = ArmIK()

    landmark = [0.0, -89.0, 0.0, 0.0, -90.0, 0.0]
    pose = ik.fk(landmark)
    axis = approach_axis(ik, landmark)
    print(f"pick landmark {landmark}:")
    print(
        f"  ee=({pose.x:.1f},{pose.y:.1f},{pose.z:.1f}) "
        f"rpy=({pose.roll:.1f},{pose.pitch:.1f},{pose.yaw:.1f})"
    )
    print(
        f"  approach axis=[{axis[0]:.2f} {axis[1]:.2f} {axis[2]:.2f}] (want [0 0 -1])"
    )

    spins = list(range(-180, 180, 15))
    print("\nLowest reachable Z (vertical gripper, best spin) by horizontal reach:")
    for x in (-300.0, -350.0, -400.0, -450.0, -480.0):
        best_low = None
        best = None
        for z in [float(z) for z in range(160, -5, -5)]:
            reached = False
            for spin in spins:
                roll, pitch, yaw = spin_rpy(spin)
                r = ik.solve_ik(
                    CartesianTarget(x=x, y=0.0, z=z, roll=roll, pitch=pitch, yaw=yaw)
                )
                if r.success:
                    ax = approach_axis(ik, r.joint_angles_deg)
                    if ax[2] < -0.98:  # genuinely vertical (down)
                        reached = True
                        best_low = z
                        best = (spin, r.joint_angles_deg)
                        break
            if not reached:
                break
        if best_low is not None:
            spin, js = best
            print(
                f"  x={x:6.0f}  lowest z={best_low:5.0f} mm  spin={spin:4d}  "
                f"joints={[round(j,1) for j in js]}"
            )
        else:
            print(f"  x={x:6.0f}  no vertical-gripper solution down to z=160")


if __name__ == "__main__":
    main()
