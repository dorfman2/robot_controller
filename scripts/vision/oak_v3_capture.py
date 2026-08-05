"""OAK-1 Lite capture test on DepthAI v3 API."""

import time

import cv2
import depthai as dai

ts = time.strftime("%H%M%S")
outpath = f"/home/pi/oak_snap_{ts}.jpg"

with dai.Pipeline() as pipeline:
    cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    out = cam.requestOutput((1280, 720), dai.ImgFrame.Type.BGR888i)
    q = out.createOutputQueue(maxSize=4, blocking=False)
    pipeline.start()
    frame = None
    t0 = time.time()
    while time.time() - t0 < 3.0:  # settle AE/AF
        frame = q.get().getCvFrame()
    cv2.imwrite(outpath, frame)
    print("PATH", outpath, "shape", frame.shape, "mean", round(float(frame.mean()), 1))
