"""Move via move_cartesian to X Y Z (argv) and report ack + grip pixel."""
import asyncio
import json
import sys
import urllib.request

import websockets

TX, TY, TZ = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
SPEED = float(sys.argv[4]) if len(sys.argv) > 4 else 10.0


def grip():
    try:
        c = json.load(urllib.request.urlopen("http://localhost:8091/grip", timeout=3))
        return c.get("center"), c.get("n")
    except Exception as e:  # noqa: BLE001
        return f"err {e}", None


async def get_state(ws):
    await ws.send(json.dumps({"cmd": "get_state"}))
    while True:
        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
        if m.get("type") == "state":
            return m


async def main() -> None:
    async with websockets.connect("ws://localhost:9090") as ws:
        await get_state(ws)
        await ws.send(
            json.dumps({"cmd": "move_cartesian", "x": TX, "y": TY, "z": TZ, "speed": SPEED})
        )
        end = asyncio.get_event_loop().time() + 15
        while asyncio.get_event_loop().time() < end:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if m.get("cmd") == "move_cartesian" or m.get("type") == "error":
                if m.get("type") == "error":
                    print("ERROR:", m.get("message"))
                else:
                    ee = m["end_effector"]
                    print(
                        f"ok ee=({ee['x']:.0f},{ee['y']:.0f},{ee['z']:.0f}) "
                        f"perr={m['position_error_mm']:.2f}mm"
                    )
                break
        await asyncio.sleep(4)
        print("grip:", grip())


asyncio.run(main())
