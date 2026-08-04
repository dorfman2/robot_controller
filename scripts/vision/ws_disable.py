"""Disable (de-energize) all motors on the armold daemon.

Sends the ``disable`` command to the controller, which issues M84 to Klipper so
every stepper free-spins. Only run this with the arm in a safe resting pose
(e.g. straight-up home), since de-energized joints sag under gravity.
"""

import asyncio
import json

import websockets


async def main() -> None:
    """Send the disable command and print the ack status."""
    async with websockets.connect("ws://localhost:9090") as ws:
        await ws.send(json.dumps({"cmd": "disable"}))
        end = asyncio.get_event_loop().time() + 8
        while asyncio.get_event_loop().time() < end:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
            if m.get("type") == "ack" and m.get("cmd") == "disable":
                print("disable:", m.get("status"))
                return


asyncio.run(main())
