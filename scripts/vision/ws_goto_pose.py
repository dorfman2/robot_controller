"""Full-pose ``move_cartesian`` helper: X Y Z ROLL PITCH YAW [SPEED].

Unlike ``ws_goto.py`` (position-only), this preserves a commanded tool
orientation, which is required for a straight-down descent that keeps the
gripper pointing at the desk. Reports the ack (achieved EE pose + residual
error) and the current gripper-marker pixel from the OAK detect-stream.

Usage:
    python ws_goto_pose.py <x> <y> <z> <roll> <pitch> <yaw> [speed]
"""

import asyncio
import json
import sys
import urllib.request

import websockets

TX, TY, TZ = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
ROLL, PITCH, YAW = float(sys.argv[4]), float(sys.argv[5]), float(sys.argv[6])
SPEED = float(sys.argv[7]) if len(sys.argv) > 7 else 8.0


def grip() -> tuple[object, object]:
    """Return (center_pixel, n_blobs) from the OAK detect-stream ``/grip``."""
    try:
        c = json.load(urllib.request.urlopen("http://localhost:8091/grip", timeout=3))
        return c.get("center"), c.get("n")
    except Exception as e:  # noqa: BLE001
        return f"err {e}", None


async def get_state(ws: object) -> dict:
    """Request one state frame and return it."""
    await ws.send(json.dumps({"cmd": "get_state"}))
    while True:
        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
        if m.get("type") == "state":
            return m


async def main() -> None:
    """Send a full-pose move_cartesian and print the ack + grip pixel."""
    async with websockets.connect("ws://localhost:9090") as ws:
        await get_state(ws)
        await ws.send(
            json.dumps(
                {
                    "cmd": "move_cartesian",
                    "x": TX,
                    "y": TY,
                    "z": TZ,
                    "roll": ROLL,
                    "pitch": PITCH,
                    "yaw": YAW,
                    "speed": SPEED,
                }
            )
        )
        end = asyncio.get_event_loop().time() + 15
        while asyncio.get_event_loop().time() < end:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if m.get("cmd") == "move_cartesian" or m.get("type") == "error":
                if m.get("type") == "error":
                    print("ERROR:", m.get("message"), "reachable=", m.get("reachable"))
                else:
                    ee = m["end_effector"]
                    print(
                        f"ok ee=({ee['x']:.1f},{ee['y']:.1f},{ee['z']:.1f}) "
                        f"rpy=({ee['roll']:.1f},{ee['pitch']:.1f},{ee['yaw']:.1f}) "
                        f"perr={m['position_error_mm']:.2f}mm"
                    )
                break
        await asyncio.sleep(4)
        print("grip:", grip())


asyncio.run(main())
