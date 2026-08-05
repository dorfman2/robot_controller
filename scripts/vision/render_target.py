"""Render the arm at a target joint config, showing the tool approach axis.

Builds the ArmIK ETS, evaluates ``fkine_all`` at the given J0..J5 config, and
draws a 3D stick figure of the link frames plus the tool approach axis (the EE
+Y direction, which is "straight down" iff it points along world -Z). A desk
plane at z=0 is drawn for reference. Saves an isometric and a side (XZ) view so
the gripper orientation is unambiguous.

Run:
    PYTHONPATH=/Users/jdorfman/Code/Armold .venv/bin/python \
        scripts/vision/render_target.py <J0> <J1> <J2> <J3> <J4> <J5>
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from roboticstoolbox import Robot

from armold_controller.ik_solver import ArmIK

# Workspace-local output folder (repo_root/renders), created on demand.
RENDER_DIR = Path(__file__).resolve().parents[2] / "renders"


def main() -> None:
    """Render the given config to /tmp/target_render.png."""
    cfg = (
        [float(a) for a in sys.argv[1:7]]
        if len(sys.argv) >= 7
        else [0.0, -15.92, 69.62, 30.82, -90.0, -26.36]
    )
    ik = ArmIK()
    robot = Robot(ik.ets)
    q = np.deg2rad(cfg)

    frames = robot.fkine_all(q)  # SE3 array, one pose per ETS frame
    pts = np.array([np.asarray(T.t).ravel() for T in frames])

    pose = ik.fk(cfg)
    ee = np.array([pose.x, pose.y, pose.z])
    # Tool approach axis = EE frame +Y column (the ty(tool_len) direction).
    from spatialmath import SE3

    r_ee = SE3(ik.ets.eval(q), check=False).R
    approach = np.asarray(r_ee[:, 1]).ravel()

    fig = plt.figure(figsize=(13, 6))
    for idx, (elev, azim, title) in enumerate(
        [
            (22, -60, "isometric"),
            (2, -90, "side view (looking along +Y = -X..-Z plane)"),
        ]
    ):
        ax = fig.add_subplot(1, 2, idx + 1, projection="3d")
        ax.plot(pts[:, 0], pts[:, 1], pts[:, 2], "-o", color="#1f77b4", lw=2, ms=3)
        ax.scatter(*ee, color="red", s=60, label="tool tip (EE)")
        # Approach axis arrow (100 mm) from the EE.
        ax.quiver(
            ee[0],
            ee[1],
            ee[2],
            approach[0] * 120,
            approach[1] * 120,
            approach[2] * 120,
            color="green",
            lw=3,
            label="tool approach (+Y)",
        )
        # Desk plane at z=0.
        xx, yy = np.meshgrid(np.linspace(-500, 100, 2), np.linspace(-150, 250, 2))
        ax.plot_surface(xx, yy, np.zeros_like(xx), alpha=0.15, color="gray")
        ax.set_xlabel("X (mm)")
        ax.set_ylabel("Y (mm)")
        ax.set_zlabel("Z (mm, height above desk)")
        ax.set_title(title)
        ax.view_init(elev=elev, azim=azim)
        ax.set_xlim(-550, 100)
        ax.set_ylim(-200, 300)
        ax.set_zlim(0, 750)
        if idx == 0:
            ax.legend(loc="upper left", fontsize=8)

    tilt_deg = float(np.degrees(np.arccos(np.clip(-approach[2], -1, 1))))
    fig.suptitle(
        f"config {cfg}\n"
        f"EE=({pose.x:.0f},{pose.y:.0f},{pose.z:.0f}) "
        f"rpy=({pose.roll:.1f},{pose.pitch:.1f},{pose.yaw:.1f})  "
        f"approach=[{approach[0]:.2f},{approach[1]:.2f},{approach[2]:.2f}]  "
        f"tilt-from-vertical={tilt_deg:.1f} deg",
        fontsize=9,
    )
    fig.tight_layout()
    RENDER_DIR.mkdir(exist_ok=True)
    # Filename encodes the config so renders are kept (not overwritten).
    tag = "_".join(f"{v:g}" for v in cfg)
    out = RENDER_DIR / f"pose_{tag}.png"
    fig.savefig(out, dpi=110)
    print(f"wrote {out}  tilt-from-vertical={tilt_deg:.1f} deg")


if __name__ == "__main__":
    main()
