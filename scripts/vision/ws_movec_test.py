"""Validate move_cartesian on hardware: small +30mm X move, report results."""

import asyncio
import json
import urllib.request

import websockets


async def get_state(ws):
    await ws.send(json.dumps({"cmd": "get_state"}))
    while True:
        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
        if m.get("type") == "state":
            return m


def grip():
    try:
        return json.load(
            urllib.request.urlopen("http://localhost:8091/grip", timeout=3)
        ).get("center")
    except Exception as e:  # noqa: BLE001
        return f"err {e}"


async def main() -> None:
    async with websockets.connect("ws://localhost:9090") as ws:
        st = await get_state(ws)
        ee = st["end_effector"]
        print(
            "BEFORE ee=", {k: round(ee[k], 1) for k in ("x", "y", "z")}, "grip=", grip()
        )

        tx, ty, tz = ee["x"] + 30.0, ee["y"], ee["z"]
        print(
            f"commanding move_cartesian to ({tx:.0f},{ty:.0f},{tz:.0f}) position-only"
        )
        await ws.send(
            json.dumps(
                {"cmd": "move_cartesian", "x": tx, "y": ty, "z": tz, "speed": 10}
            )
        )

        end = asyncio.get_event_loop().time() + 15
        while asyncio.get_event_loop().time() < end:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if m.get("cmd") == "move_cartesian" or m.get("type") == "error":
                print("RESPONSE:", json.dumps(m))
                break

        await asyncio.sleep(4)
        st = await get_state(ws)
        ee = st["end_effector"]
        print(
            "AFTER ee=", {k: round(ee[k], 1) for k in ("x", "y", "z")}, "grip=", grip()
        )


asyncio.run(main())
