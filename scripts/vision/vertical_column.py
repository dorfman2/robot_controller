"""Precompute a vertical-gripper descent column as joint targets.

At a fixed desk XY and a fixed gripper spin, solve IK (robust home-seeded, with
a per-step warm start from the previous solution) for a descending set of Z
heights, keeping the tool approach axis vertical (down). Emits the full 7-value
board joint targets (rail + J0..J5) for each Z so the descent can be executed as
direct joint-space moves, avoiding on-arm Cartesian IK seed fragility.

The rail value is taken from the CLI (its current mm position) and passed
through unchanged; the rail is not part of the IK chain.

Run:
    PYTHONPATH=/Users/jdorfman/Code/Armold .venv/bin/python \
        scripts/vision/vertical_column.py <x> <rail_mm> [spin_deg]
"""

from __future__ import annotations

import sys

import numpy as np
from spatialmath import SE3

from armold_controller.ik_solver import HOME_POSE_DEG, ArmIK, CartesianTarget

Z_STEPS = [
    260.0,
    240.0,
    220.0,
    200.0,
    180.0,
    160.0,
    140.0,
    120.0,
    100.0,
    80.0,
    60.0,
    40.0,
    25.0,
    15.0,
    5.0,
    0.0,
]


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


def best_spin(ik: ArmIK, x: float) -> float:
    """Pick the spin giving the lowest reachable vertical Z at ``x`` (y=0)."""
    best = (-1.0, 0.0)  # (lowest_z_reach_score, spin)
    for spin in range(-180, 180, 15):
        roll, pitch, yaw = spin_rpy(spin)
        reached = 999.0
        for z in Z_STEPS:
            r = ik.solve_ik(CartesianTarget(x, 0.0, z, roll, pitch, yaw))
            if r.success and approach_axis(ik, r.joint_angles_deg)[2] < -0.98:
                reached = min(reached, z)
        score = -reached  # lower z reached => higher score
        if score > best[0]:
            best = (score, float(spin))
    return best[1]


def main() -> None:
    """Print the vertical descent column of board joint targets."""
    x = float(sys.argv[1])
    rail = float(sys.argv[2])
    ik = ArmIK()
    spin = float(sys.argv[3]) if len(sys.argv) > 3 else best_spin(ik, x)
    roll, pitch, yaw = spin_rpy(spin)
    print(f"# x={x} rail={rail} spin={spin} rpy=({roll:.2f},{pitch:.2f},{yaw:.2f})")
    seed = list(HOME_POSE_DEG)
    prev = None
    for z in Z_STEPS:
        r = ik.solve_ik(CartesianTarget(x, 0.0, z, roll, pitch, yaw), seed_deg=seed)
        ax = approach_axis(ik, r.joint_angles_deg)
        vert = ax[2] < -0.98
        if r.success and vert:
            seed = r.joint_angles_deg  # warm start next (lower) step
            js = [round(j, 2) for j in r.joint_angles_deg]
            board = [rail] + js
            jump = ""
            if prev is not None:
                d = float(np.linalg.norm(np.array(js) - np.array(prev)))
                jump = f"  d={d:.1f}"
            prev = js
            board_str = " ".join(f"{v:.2f}" for v in board)
            print(f"z={z:5.0f}  OK  target=[{board_str}]{jump}")
        else:
            why = "not-vertical" if (r.success and not vert) else r.message
            print(f"z={z:5.0f}  FAIL ({why})")


if __name__ == "__main__":
    main()
