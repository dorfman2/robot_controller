"""
Prove on-device NN inference on the OAK-4 S (RVC4) via DepthAI v3.

Runs the stock ``yolov6-nano`` DetectionNetwork on the OAK-4 S: the model is
downloaded from the HubAI Model Zoo and compiled for RVC4, inference AND output
decoding run on-camera, and this script (the "Pi host") receives only
``ImgDetections`` — not raw frames for inference. Prints the detections and the
achieved on-device NN FPS, then exits.

NOTE: ``yolov6-nano`` is COCO-trained (no "pen" class), so this validates the
on-device pipeline and throughput, NOT pen detection. The pen detector needs a
custom-trained model (see the spec's custom-model plan).

Run on the Pi with the OAK-4 free (stop the overhead service first):
    sudo systemctl stop oak-overhead
    /home/pi/armold-venv/bin/python /home/pi/vision/oak4_nn_test.py
    sudo systemctl start oak-overhead

First run downloads + compiles the model for RVC4 (may take a minute and
requires internet on the Pi).
"""

from __future__ import annotations

import time

import depthai as dai
from camera_config import OAK4S_IP

MODEL_SLUG: str = "yolov6-nano"
RUN_SECONDS: float = 12.0
MAX_SAMPLE_PRINTS: int = 8


def main() -> None:
    """Connect to the OAK-4 S, run yolov6-nano on-device, and report FPS."""
    info = dai.DeviceInfo(OAK4S_IP)
    device = dai.Device(info)
    try:
        platform = device.getPlatformAsString()
    except Exception:  # noqa: BLE001 - platform query is informational only
        platform = "unknown"
    print(f"connected: {info.name} platform={platform}")

    with dai.Pipeline(device) as pipeline:
        cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
        print(f"building DetectionNetwork({MODEL_SLUG}) — may download/compile...")
        det = pipeline.create(dai.node.DetectionNetwork).build(
            cam, dai.NNModelDescription(MODEL_SLUG)
        )
        labels = det.getClasses()
        print(f"model ready: {MODEL_SLUG}, {len(labels)} classes")

        q = det.out.createOutputQueue(maxSize=4, blocking=False)
        pipeline.start()
        print(f"pipeline started; reading detections for {RUN_SECONDS:.0f}s...")

        t0 = time.monotonic()
        frames = 0
        total_dets = 0
        samples = 0
        while time.monotonic() - t0 < RUN_SECONDS:
            in_det = q.tryGet()
            if in_det is None:
                time.sleep(0.005)
                continue
            frames += 1
            dets = in_det.detections
            total_dets += len(dets)
            if dets and samples < MAX_SAMPLE_PRINTS:
                d = dets[0]
                print(
                    f"  frame {frames}: {len(dets)} det | top="
                    f"{labels[d.label]} {d.confidence:.2f} "
                    f"bbox=({d.xmin:.2f},{d.ymin:.2f},{d.xmax:.2f},{d.ymax:.2f})"
                )
                samples += 1

        dt = time.monotonic() - t0
        fps = frames / dt if dt > 0 else 0.0
        print(
            f"\nRESULT: {frames} NN frames in {dt:.1f}s = {fps:.1f} FPS on-device; "
            f"{total_dets} total detections."
        )
        pipeline.stop()


if __name__ == "__main__":
    main()
