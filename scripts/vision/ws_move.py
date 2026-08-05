"""Enable motors and jog the shoulder joint (J1) to -30 deg. Reads back state."""

import asyncio
import json

import websockets


async def _read_until(ws, pred, timeout=8.0):
    end = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < end:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if pred(msg):
            return msg
    return None


async def main() -> None:
    async with websockets.connect("ws://localhost:9090") as ws:
        await ws.send(json.dumps({"cmd": "enable"}))
        ack = await _read_until(
            ws, lambda m: m.get("type") == "ack" and m.get("cmd") == "enable"
        )
        print("enable ack:", ack)

        # joint index 2 = J1 shoulder; -30 deg at 8 deg/s
        await ws.send(
            json.dumps({"cmd": "jog", "joint": 2, "delta": -30.0, "speed": 8.0})
        )
        ack = await _read_until(
            ws, lambda m: m.get("type") == "ack" and m.get("cmd") == "jog"
        )
        print("jog ack:", ack)

        await asyncio.sleep(7)
        await ws.send(json.dumps({"cmd": "get_state"}))
        st = await _read_until(ws, lambda m: m.get("type") == "state")
        if st:
            print("position:", [round(p, 2) for p in st.get("position", [])])
            print("end_effector:", st.get("end_effector"))


asyncio.run(main())
