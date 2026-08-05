"""Diagnose green marker detectability: capture raw frame, report green HSV."""

import time

import cv2
import depthai as dai
import numpy as np

ts = time.strftime("%H%M%S")
raw_path = f"/home/pi/green_diag_{ts}.jpg"

with dai.Pipeline() as pipeline:
    cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    out = cam.requestOutput((1280, 720), dai.ImgFrame.Type.BGR888i)
    q = out.createOutputQueue(maxSize=4, blocking=False)
    pipeline.start()
    frame = None
    t0 = time.time()
    while time.time() - t0 < 3.0:
        frame = q.get().getCvFrame()

cv2.imwrite(raw_path, frame)
hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
print("frame brightness (V mean):", round(float(hsv[:, :, 2].mean()), 1))

# Loose green range to see what's actually there.
loose = cv2.inRange(hsv, np.array([25, 25, 25]), np.array([100, 255, 255]))
loose = cv2.morphologyEx(
    loose, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
)
contours, _ = cv2.findContours(loose, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
cand = []
for c in contours:
    area = cv2.contourArea(c)
    if area < 40:
        continue
    m = cv2.moments(c)
    if m["m00"] == 0:
        continue
    cx, cy = m["m10"] / m["m00"], m["m01"] / m["m00"]
    bm = np.zeros(loose.shape, np.uint8)
    cv2.drawContours(bm, [c], -1, 255, -1)
    px = hsv[bm > 0]
    cand.append((area, cx, cy, px))

cand.sort(key=lambda t: t[0], reverse=True)
print(f"loose-green blobs (area>=40): {len(cand)}")
for area, cx, cy, px in cand[:5]:
    print(
        f"  area={area:.0f} center=({cx:.0f},{cy:.0f}) "
        f"H[{px[:,0].min()}-{px[:,0].max()} mean{px[:,0].mean():.0f}] "
        f"S[{px[:,1].min()}-{px[:,1].max()} mean{px[:,1].mean():.0f}] "
        f"V[{px[:,2].min()}-{px[:,2].max()} mean{px[:,2].mean():.0f}]"
    )
print("saved", raw_path)
