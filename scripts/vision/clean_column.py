"""Generate a clean-wrist vertical descent column (J5=0, no singularity games).

The prior column forced a gripper yaw, which drove the IK to a fragile
J3/J5 cancellation right at the J4=-90 wrist singularity — it computed as
vertical but did not execute reliably on hardware (landed ~30 deg off).

This generator instead FIXES J0=0, J4=-90, J5=0 and solves only J1, J2, J3 so
the tool tip reaches (x, 0, z) with the approach axis pointing straight down.
With J5=0, J3 alone controls the tool pitch (monotonic, robust), so there is no
delicate cancellation. The gripper's finger yaw is left to whatever the planar
arm produces (to be set later via the base J0 for pen alignment).

Run:
    PYTHONPATH=/Users/jdorfman/Code/Armold .venv/bin/python \
        scripts/vision/clean_column.py <x> <rail_mm>
"""

from __future__ import annotations

import sys

import numpy as np
from scipy.optimize import minimize
from spatialmath import SE3

from armold_controller.ik_solver import ArmIK

Z_STEPS = [
    260.0, 240.0, 220.0, 200.0, 180.0, 160.0, 140.0, 120.0,
    100.0, 80.0, 60.0, 40.0, 25.0, 15.0, 5.0, 0.0,
]

# Fixed wrist/base joints: J0=0 (base), J4=-90 (tool down), J5=0 (no roll).
J0_FIXED, J4_FIXED, J5_FIXED = 0.0, -90.0, 0.0


def approach_axis(ik: ArmIK, cfg: list[float]) -> np.ndarray:
    """World-frame tool approach (EE +Y) unit vector at ``cfg``."""
    q = np.deg2rad(np.asarray(cfg, dtype=float))
    return np.asarray(SE3(ik.ets.eval(q), check=False).R[:, 1]).ravel()


def solve_j123(ik: ArmIK, x: float, z: float, seed: np.ndarray) -> tuple[list[float], float, float]:
    """Solve J1,J2,J3 (deg) so the tip hits (x,0,z) pointing straight down.

    Returns (cfg6, pos_err_mm, tilt_deg).
    """

    def cost(j123: np.ndarray) -> float:
        cfg = [J0_FIXED, j123[0], j123[1], j123[2], J4_FIXED, J5_FIXED]
        p = ik.fk(cfg)
        pos = (p.x - x) ** 2 + (p.y - 0.0) ** 2 + (p.z - z) ** 2
        ax = approach_axis(ik, cfg)
        # penalise deviation of approach from straight-down [0,0,-1]
        ori = (ax[0]) ** 2 + (ax[1]) ** 2 + (ax[2] + 1.0) ** 2
        return pos + 500.0 * ori

    res = minimize(cost, seed, method="Nelder-Mead",
                   options={"xatol": 1e-4, "fatol": 1e-6, "maxiter": 4000})
    j1, j2, j3 = res.x
    cfg = [J0_FIXED, float(j1), float(j2), float(j3), J4_FIXED, J5_FIXED]
    p = ik.fk(cfg)
    pos_err = float(np.sqrt((p.x - x) ** 2 + (p.y) ** 2 + (p.z - z) ** 2))
    ax = approach_axis(ik, cfg)
    tilt = float(np.degrees(np.arccos(np.clip(-ax[2], -1, 1))))
    return cfg, pos_err, tilt


def main() -> None:
    """Print the clean-wrist descent column of board joint targets."""
    x = float(sys.argv[1])
    rail = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    ik = ArmIK()
    print(f"# clean-wrist column  x={x} rail={rail}  J0=0 J4=-90 J5=0")
    seed = np.array([-30.0, 70.0, 0.0])  # J1,J2,J3 initial guess
    prev = None
    for z in Z_STEPS:
        cfg, perr, tilt = solve_j123(ik, x, z, seed)
        seed = np.array(cfg[1:4])  # warm-start next step
        board = [rail] + [round(v, 2) for v in cfg]
        jump = ""
        if prev is not None:
            d = float(np.linalg.norm(np.array(cfg[1:4]) - np.array(prev)))
            jump = f"  d={d:.1f}"
        prev = cfg[1:4]
        ok = "OK " if (perr < 2.0 and tilt < 3.0) else "CHK"
        bstr = " ".join(f"{v:.2f}" for v in board)
        print(f"z={z:5.0f} {ok} perr={perr:4.1f} tilt={tilt:4.1f}  "
              f"target=[{bstr}]{jump}")


if __name__ == "__main__":
    main()
