"""Hand-eye calibration: grid of move_cartesian points -> pixel<->arm-XY map."""

import asyncio
import json
import urllib.request

import cv2
import numpy as np
import websockets

Z = 572.0
GRID_X = [-225.0, -250.0, -275.0]
GRID_Y = [-50.0, 0.0, 50.0]
SPEED = 10.0
OUT = "/home/pi/armold_handeye.json"


def grip():
    try:
        c = json.load(urllib.request.urlopen("http://localhost:8091/grip", timeout=3))
        ctr = c.get("center")
        return tuple(ctr) if ctr else None
    except Exception:  # noqa: BLE001
        return None


async def get_state(ws):
    await ws.send(json.dumps({"cmd": "get_state"}))
    while True:
        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
        if m.get("type") == "state":
            return m


async def move(ws, x, y, z):
    await ws.send(
        json.dumps({"cmd": "move_cartesian", "x": x, "y": y, "z": z, "speed": SPEED})
    )
    end = asyncio.get_event_loop().time() + 18
    while asyncio.get_event_loop().time() < end:
        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=12))
        if m.get("type") == "error":
            return None
        if m.get("cmd") == "move_cartesian":
            return m
    return None


async def main() -> None:
    pts_px, pts_xy, rows = [], [], []
    async with websockets.connect("ws://localhost:9090") as ws:
        st = await get_state(ws)
        rail = st["position"][0]
        for gx in GRID_X:
            for gy in GRID_Y:
                ack = await move(ws, gx, gy, Z)
                if not ack:
                    print(f"skip ({gx:.0f},{gy:.0f}) unreachable")
                    continue
                if ack["position_error_mm"] > 2.0:
                    print(
                        f"skip ({gx:.0f},{gy:.0f}) perr={ack['position_error_mm']:.1f}"
                    )
                    continue
                await asyncio.sleep(2.5)
                samples = []
                for _ in range(6):
                    g = grip()
                    if g:
                        samples.append(g)
                    await asyncio.sleep(0.15)
                if len(samples) < 3:
                    print(f"skip ({gx:.0f},{gy:.0f}) marker not visible")
                    continue
                px = float(np.mean([s[0] for s in samples]))
                py = float(np.mean([s[1] for s in samples]))
                ee = ack["end_effector"]
                pts_px.append([px, py])
                pts_xy.append([ee["x"], ee["y"]])
                rows.append([gx, gy, px, py, ee["x"], ee["y"]])
                print(
                    f"pt tgt({gx:.0f},{gy:.0f}) ee=({ee['x']:.0f},{ee['y']:.0f}) px=({px:.0f},{py:.0f})"
                )
        await move(ws, -250.0, 0.0, Z)  # park central

    print(f"collected {len(pts_px)} valid points")
    if len(pts_px) < 4:
        print("NEED >=4 points to fit; aborting")
        return
    P = np.array(pts_px, dtype=np.float64)
    W = np.array(pts_xy, dtype=np.float64)
    H, _ = cv2.findHomography(P, W, cv2.RANSAC, 3.0)
    method = "homography"
    if H is None:
        M, _ = cv2.estimateAffine2D(P, W)
        H = np.vstack([M, [0, 0, 1]])
        method = "affine"
    Ph = np.hstack([P, np.ones((len(P), 1))])
    pred = (H @ Ph.T).T
    pred = pred[:, :2] / pred[:, 2:3]
    err = np.linalg.norm(pred - W, axis=1)
    print(f"method={method} reproj err mm: mean {err.mean():.2f} max {err.max():.2f}")
    with open(OUT, "w") as f:  # noqa: ASYNC230 - one-shot calibration write
        json.dump(
            {
                "type": method,
                "H": H.tolist(),
                "rail_mm": rail,
                "z_plane": Z,
                "points": rows,
                "reproj_mean_mm": float(err.mean()),
                "reproj_max_mm": float(err.max()),
            },
            f,
            indent=2,
        )
    print("saved", OUT)


asyncio.run(main())
