"""
Capture clean overhead frames from the OAK-4 S for pen-detector training data.

Connects directly to the OAK-4 S (so frames are CLEAN — no detection overlay,
unlike the ``/stream`` endpoint) and saves timestamped JPEGs at a fixed interval
so the operator can reposition / rotate the pen (and vary lighting) between
shots. The resulting images are uploaded to Roboflow for annotation.

The OAK-4 must be free, so the overhead service is stopped for the session:
    sudo systemctl stop oak-overhead
    /home/pi/armold-venv/bin/python /home/pi/vision/capture_dataset.py \
        --count 50 --interval 1.5 --outdir /home/pi/pen_dataset
    sudo systemctl start oak-overhead

Guidance for a good dataset: move the pen to different positions and angles
across the mat, include a few cluttered / partially-occluded shots, and vary
lighting. 40-80 varied frames is a reasonable starting set.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import depthai as dai
from camera_config import OAK4S_IP


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the capture session."""
    p = argparse.ArgumentParser(description="Capture OAK-4 S frames for training.")
    p.add_argument("--count", type=int, default=50, help="Number of frames to save.")
    p.add_argument(
        "--interval", type=float, default=1.5, help="Seconds between saved frames."
    )
    p.add_argument(
        "--outdir",
        type=str,
        default=str(Path.home() / "pen_dataset"),
        help="Directory to write JPEGs into (created if missing).",
    )
    p.add_argument("--width", type=int, default=1920, help="Capture width (px).")
    p.add_argument("--height", type=int, default=1080, help="Capture height (px).")
    p.add_argument(
        "--warmup", type=float, default=3.0, help="Seconds to wait before frame 1."
    )
    return p.parse_args()


def main() -> None:
    """Run the interval-based capture session and save JPEGs to ``outdir``."""
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    info = dai.DeviceInfo(OAK4S_IP)
    device = dai.Device(info)
    print(f"connected: {info.name}; saving {args.count} frames to {outdir}")

    with dai.Pipeline(device) as pipeline:
        cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
        out = cam.requestOutput(
            (args.width, args.height), dai.ImgFrame.Type.BGR888i, fps=10
        )
        q = out.createOutputQueue(maxSize=4, blocking=False)
        pipeline.start()

        print(f"get ready — first capture in {args.warmup:.0f}s...")
        time.sleep(args.warmup)

        session = time.strftime("%Y%m%d_%H%M%S")
        saved = 0
        while saved < args.count:
            # Drain to the freshest frame.
            frame = None
            for _ in range(10):
                pkt = q.tryGet()
                if pkt is None:
                    break
                frame = pkt
            if frame is None:
                frame = q.get()
            img = frame.getCvFrame()

            path = outdir / f"pen_{session}_{saved:03d}.jpg"
            cv2.imwrite(str(path), img)
            saved += 1
            print(
                f"  [{saved}/{args.count}] saved {path.name} "
                f"({img.shape[1]}x{img.shape[0]}) — reposition the pen"
            )
            time.sleep(args.interval)

        pipeline.stop()

    print(f"\nDONE: {saved} frames in {outdir}")
    print("Next: copy them off the Pi and upload to Roboflow for annotation.")


if __name__ == "__main__":
    main()
