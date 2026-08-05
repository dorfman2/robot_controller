"""Command the six arm joints to absolute angles via Moonraker MANUAL_STEPPER.

Replays one rung of a precomputed joint column by issuing an absolute
``MANUAL_STEPPER MOVE`` (SYNC=0, concurrent) for each arm joint directly through
Moonraker's gcode endpoint, bypassing the controller daemon's Cartesian IK
(which is seed-fragile near the reach edge). The rail (stepper_x) is never
touched. After commanding, reports the OAK gripper-marker pixel for reference.

Joint order is J0..J5 mapped to stepper_y/z/a/b/c/u.

Run (on the Pi):
    python col_move.py <J0> <J1> <J2> <J3> <J4> <J5> [speed_deg_s]
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

STEPPERS = [
    "stepper_y",
    "stepper_z",
    "stepper_a",
    "stepper_b",
    "stepper_c",
    "stepper_u",
]
MOONRAKER = "http://localhost:7125"


def grip() -> object:
    """Return the OAK detect-stream gripper-marker center pixel, or an error."""
    try:
        c = json.load(urllib.request.urlopen("http://localhost:8091/grip", timeout=3))
        return {"center": c.get("center"), "n": c.get("n")}
    except Exception as e:  # noqa: BLE001
        return f"grip err {e}"


def main() -> None:
    """Issue concurrent absolute MANUAL_STEPPER moves for the six arm joints."""
    angles = [float(a) for a in sys.argv[1:7]]
    speed = float(sys.argv[7]) if len(sys.argv) > 7 else 8.0
    lines = [
        f"MANUAL_STEPPER STEPPER={s} MOVE={a:.4f} SPEED={speed:.1f} "
        f"ACCEL=300 SYNC=0"
        for s, a in zip(STEPPERS, angles)
    ]
    script = "\n".join(lines)
    data = urllib.parse.urlencode({"script": script}).encode()
    req = urllib.request.Request(
        f"{MOONRAKER}/printer/gcode/script", data=data, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    print("result:", body.get("result"))
    print("commanded:", [round(a, 2) for a in angles], "speed:", speed)
    print("grip:", grip())


if __name__ == "__main__":
    main()
