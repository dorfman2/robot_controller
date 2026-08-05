"""Read current arm state from the armold daemon WebSocket (no motion)."""

import asyncio
import json

import websockets


async def main() -> None:
    async with websockets.connect("ws://localhost:9090") as ws:
        await ws.send(json.dumps({"cmd": "get_state"}))
        deadline = asyncio.get_event_loop().time() + 6
        while asyncio.get_event_loop().time() < deadline:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            if msg.get("type") == "state":
                print("motors_enabled:", msg.get("motors_enabled"))
                print("position:", msg.get("position"))
                print("end_effector:", msg.get("end_effector"))
                print("axes_registered:", msg.get("axes_registered"))
                return


asyncio.run(main())
