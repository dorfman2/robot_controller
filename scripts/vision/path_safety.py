"""Simulate a MANUAL_STEPPER SYNC=0 concurrent move and report min tip height.

``goto_positions`` issues each joint as an independent ``MANUAL_STEPPER MOVE``
at the same SPEED (deg/s) with ``SYNC=0``, so joints ramp linearly in time and
shorter moves finish first (this is NOT a straight joint-space line). This
script reconstructs that time-parameterised path from a start config A to a
target config B and reports the minimum tool-tip Z along it, so we can confirm
a reorientation near the desk will not clip the surface.

Run:
    PYTHONPATH=/Users/jdorfman/Code/Armold .venv/bin/python \
        scripts/vision/path_safety.py
"""

from __future__ import annotations

import numpy as np

from armold_controller.ik_solver import ArmIK

# Current physical arm joints (J0..J5), from the live daemon state.
A = [0.31, -89.53, 64.75, -103.69, -89.25, 9.6]
# Vertical-column top rung (z=260), arm joints (rail dropped).
B = [0.0, -15.92, 69.62, 30.82, -90.0, -26.36]

SPEED_DEG_S = 8.0


def simulate(a: list[float], b: list[float], label: str) -> None:
    """Print the minimum tip Z along the SYNC=0 concurrent move from a to b."""
    ik = ArmIK()
    a_arr = np.array(a, dtype=float)
    b_arr = np.array(b, dtype=float)
    deltas = np.abs(b_arr - a_arr)
    t_end = float(deltas.max()) / SPEED_DEG_S
    min_z = 1e9
    min_t = 0.0
    min_q: list[float] = list(a)
    for t in np.linspace(0.0, t_end, 200):
        travelled = np.minimum(SPEED_DEG_S * t, deltas)
        q = a_arr + np.sign(b_arr - a_arr) * travelled
        z = ik.fk(q.tolist()).z
        if z < min_z:
            min_z, min_t, min_q = z, float(t), q.tolist()
    print(f"{label}: t_end={t_end:.1f}s  min tip z={min_z:.1f} mm at t={min_t:.1f}s")
    print(f"   worst-case config={[round(v,1) for v in min_q]}")
    print(f"   start tip z={ik.fk(a).z:.1f}  end tip z={ik.fk(b).z:.1f}")


if __name__ == "__main__":
    simulate(A, B, "direct reorient (no lift)")
    simulate([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], B, "from HOME -> z=260 vertical")
