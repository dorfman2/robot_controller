"""
Overhead camera stream service (OAK-4 S).

Connects to the OAK-4 S over the local network (by IP), runs the classic-CV
pen detector, and serves an MJPEG overlay stream + JSON detection endpoint.

Endpoints:
    http://armold.local:8091/         — HTML page with embedded stream.
    http://armold.local:8091/stream   — MJPEG multipart stream (overlay).
    http://armold.local:8091/target   — JSON: pen detection (center, angle, conf).
    http://armold.local:8091/grip     — JSON: green marker (grasp midpoint).

Usage (on Pi, in armold-venv):
    python scripts/vision/overhead_stream.py
    python scripts/vision/overhead_stream.py --device 192.168.1.138

Systemd:
    sudo systemctl start oak-overhead

References:
    R1 (two-camera architecture), R2 (overhead perception), R8 (services).
"""

import argparse
import logging
import signal
import sys
import time

import cv2
import depthai as dai
import numpy as np
from camera_config import OAK4S_IP, OVERHEAD_PORT, OverheadConfig
from detectors import PenDetection, detect_green_marker, detect_pen
from on_device_detect import is_on_device_available
from stream_server import FrameStore, start_stream_server

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Overlay drawing
# ---------------------------------------------------------------------------


def draw_overlay(
    frame: np.ndarray,
    roi: tuple[int, int, int, int],
    pen: PenDetection | None,
    grip: dict | None,
) -> np.ndarray:
    """Draw detection overlays on the frame (in-place).

    Args:
        frame: BGR image to annotate.
        roi: (x0, y0, x1, y1) pixel ROI rectangle.
        pen: PenDetection result, or None.
        grip: Green marker result dict, or None.

    Returns:
        The annotated frame (same object, modified in-place).
    """
    rx0, ry0, rx1, ry1 = roi

    # ROI rectangle (cyan)
    cv2.rectangle(frame, (rx0, ry0), (rx1, ry1), (255, 200, 0), 1)

    # Pen detection (red)
    if pen is not None:
        cv2.drawContours(frame, [pen.box_points], 0, (0, 0, 255), 2)
        cx, cy = int(pen.center_px[0]), int(pen.center_px[1])
        cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)
        cv2.putText(
            frame,
            f"pen ({cx},{cy}) {pen.angle_deg:.0f}deg",
            (rx0, max(12, ry0 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 0, 255),
            1,
        )
    else:
        cv2.putText(
            frame,
            "no pen",
            (rx0, max(12, ry0 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 180, 255),
            1,
        )

    # Green marker / grip (yellow/magenta)
    if grip is not None:
        for fx, fy in grip["fingers"]:
            cv2.circle(frame, (int(fx), int(fy)), 5, (255, 0, 255), 2)
        gx, gy = grip["center"]
        cv2.drawMarker(
            frame,
            (int(gx), int(gy)),
            (0, 255, 255),
            cv2.MARKER_CROSS,
            16,
            2,
        )
        cv2.putText(
            frame,
            f"grip ({int(gx)},{int(gy)}) n={grip['n']}",
            (int(gx) + 8, int(gy) - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 255),
            1,
        )

    return frame


# ---------------------------------------------------------------------------
# Camera loop
# ---------------------------------------------------------------------------


def camera_loop(store: FrameStore, config: OverheadConfig) -> None:
    """Run the OAK-4 S camera pipeline, detect, and publish to the FrameStore.

    Connects to the OAK-4 S by its network IP, captures frames, runs pen
    and green-marker detection, draws overlays, and pushes results to the
    FrameStore for the HTTP server to serve.

    This function runs indefinitely. On camera disconnect (X_LINK_ERROR),
    it logs the error and retries after a delay.

    Args:
        store: FrameStore to publish JPEG frames and JSON detections.
        config: OverheadConfig with device address, resolution, thresholds.
    """
    while True:
        try:
            logger.info(
                "Connecting to OAK-4 S at %s (%dx%d @ %dfps)...",
                config.device_id,
                config.resolution[0],
                config.resolution[1],
                config.fps,
            )

            # Check if on-device inference is available
            if is_on_device_available():
                logger.info(
                    "On-device detection model available — "
                    "Pi receives detections only (RVC4 inference)."
                )
                # TODO: Switch to on-device pipeline when model is compiled.
                # For now, fall through to host-side classic-CV.
                logger.info(
                    "Falling back to host-side classic-CV (model not yet integrated)."
                )
            else:
                logger.info(
                    "Using host-side classic-CV detection (no on-device model)."
                )

            info = dai.DeviceInfo(config.device_id)
            device = dai.Device(info)

            with dai.Pipeline(device) as pipeline:
                cam = pipeline.create(dai.node.Camera).build(
                    dai.CameraBoardSocket.CAM_A
                )
                out = cam.requestOutput(
                    config.resolution,
                    dai.ImgFrame.Type.BGR888i,
                    fps=config.fps,
                )
                q = out.createOutputQueue(maxSize=4, blocking=False)
                pipeline.start()
                logger.info("OAK-4 S pipeline running.")

                while pipeline.isRunning():
                    in_frame = q.get()
                    if in_frame is None:
                        continue
                    frame = in_frame.getCvFrame()

                    # Detect pen
                    roi, pen_det = detect_pen(
                        frame,
                        roi_frac=config.roi_frac,
                        min_area_frac=config.min_area_frac,
                        max_area_frac=config.max_area_frac,
                        min_elongation=config.min_elongation,
                    )

                    # Detect green marker
                    green = detect_green_marker(frame)
                    grip_data: dict | None = None
                    if green is not None:
                        grip_data = {
                            "center": list(green.center_px),
                            "n": green.num_blobs,
                            "fingers": [[fx, fy] for fx, fy in green.fingers],
                        }

                    # Publish JSON endpoints
                    target_data: dict = {}
                    if pen_det is not None:
                        target_data = {
                            "center": list(pen_det.center_px),
                            "angle_deg": pen_det.angle_deg,
                            "confidence": pen_det.confidence,
                            "long_px": pen_det.long_side_px,
                            "short_px": pen_det.short_side_px,
                        }
                    store.put_json("target", target_data)
                    store.put_json("grip", grip_data if grip_data else {})

                    # Draw overlay and encode JPEG
                    draw_overlay(frame, roi, pen_det, grip_data)
                    ok, buf = cv2.imencode(
                        ".jpg",
                        frame,
                        [cv2.IMWRITE_JPEG_QUALITY, config.jpeg_quality],
                    )
                    if ok:
                        store.put_frame(buf.tobytes())

        except Exception as exc:  # noqa: BLE001 - camera loop must retry, not die
            logger.error("OAK-4 S camera error: %s. Retrying in 3s...", exc)
            time.sleep(3.0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the overhead camera stream service.

    Connects to the OAK-4 S, starts the HTTP server on OVERHEAD_PORT,
    and runs the detection loop indefinitely.
    """
    parser = argparse.ArgumentParser(
        description="Overhead OAK-4 S stream + pen detection service."
    )
    parser.add_argument(
        "--device",
        type=str,
        default=OAK4S_IP,
        help=f"OAK-4 S IP or deviceId (default: {OAK4S_IP}).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=OVERHEAD_PORT,
        help=f"HTTP port (default: {OVERHEAD_PORT}).",
    )
    parser.add_argument(
        "--resolution",
        type=str,
        default="640x360",
        help="Camera resolution WxH (default: 640x360).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Parse resolution
    w, h = (int(x) for x in args.resolution.split("x"))
    config = OverheadConfig(device_id=args.device, resolution=(w, h))

    # Set up graceful shutdown
    def _shutdown(signum: int, frame: object) -> None:
        logger.info("Shutdown signal received.")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Start HTTP server
    store = FrameStore()
    start_stream_server(
        store,
        port=args.port,
        fps=float(config.fps),
        json_endpoints=["target", "grip"],
        title="Armold Overhead (OAK-4 S)",
    )
    logger.info("Overhead stream on :%d", args.port)

    # Run camera loop (blocks forever, with reconnect on error)
    camera_loop(store, config)


if __name__ == "__main__":
    main()
