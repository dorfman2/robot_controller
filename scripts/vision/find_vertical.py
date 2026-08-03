"""Find the least-motion vertical-gripper IK solution at a given XY/Z.

Given the current physical joint configuration and a Cartesian target (X, Y, Z),
sweep the gripper spin (rotation about the vertical) and return the RPY + joint
solution that (a) yields a genuinely vertical approach axis, (b) is within joint
limits, and (c) is closest (L2 in joint space) to the current configuration, so
the reorientation move is as small as possible.

Run:
    PYTHONPATH=/Users/jdorfman/Code/Armold .venv/bin/python \
        scripts/vision/find_vertical.py <x> <y> <z>
"""

from __future__ import annotations

import sys

import numpy as np
from spatialmath import SE3

from armold_controller.ik_solver import ArmIK, CartesianTarget

CURRENT = [0.31, -89.53, 64.75, -103.69, -89.25, 9.6]


def spin_rpy(spin_deg: float) -> tuple[float, float, float]:
    """RPY (deg, xyz) for a vertical gripper spun ``spin_deg`` about vertical."""
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
    """World-frame tool approach (EE +Y) unit vector at ``q_deg``."""
    q = np.deg2rad(np.asarray(q_deg, dtype=float))
    return np.asarray(SE3(ik.ets.eval(q), check=False).R[:, 1]).ravel()


def main() -> None:
    """Print the least-motion vertical-gripper solution for the CLI target."""
    x, y, z = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
    ik = ArmIK()
    best = None
    for spin in range(-180, 180, 5):
        roll, pitch, yaw = spin_rpy(spin)
        r = ik.solve_ik(
            CartesianTarget(x=x, y=y, z=z, roll=roll, pitch=pitch, yaw=yaw),
            seed_deg=CURRENT,
        )
        if not r.success:
            continue
        ax = approach_axis(ik, r.joint_angles_deg)
        if ax[2] >= -0.98:
            continue
        dist = float(np.linalg.norm(np.array(r.joint_angles_deg) - np.array(CURRENT)))
        if best is None or dist < best[0]:
            best = (dist, spin, roll, pitch, yaw, r.joint_angles_deg)
    if best is None:
        print(f"NO vertical-gripper solution at ({x:.1f},{y:.1f},{z:.1f})")
        return
    dist, spin, roll, pitch, yaw, js = best
    print(f"target ({x:.1f},{y:.1f},{z:.1f}) vertical gripper:")
    print(f"  spin={spin}  rpy=({roll:.2f},{pitch:.2f},{yaw:.2f})")
    print(f"  joints={[round(j,1) for j in js]}  jointmove={dist:.1f} deg-L2")
    print(f"  CMD: {x:.1f} {y:.1f} {z:.1f} {roll:.3f} {pitch:.3f} {yaw:.3f}")


if __name__ == "__main__":
    main()
