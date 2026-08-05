"""
Side camera stream service (OAK-1 Lite).

Connects to the OAK-1 Lite over USB (by deviceId), provides a profile view
of the pick zone for gripper-tip height measurement and grasp verification.

Endpoints:
    http://armold.local:8092/         — HTML page with embedded stream.
    http://armold.local:8092/stream   — MJPEG multipart stream (overlay).
    http://armold.local:8092/gap      — JSON: gripper-tip gap above desk (px/mm).

Usage (on Pi, in armold-venv):
    python scripts/vision/side_stream.py
    python scripts/vision/side_stream.py --device 19443010A113177E00

Systemd:
    sudo systemctl start oak-side

References:
    R1 (two-camera architecture), R3 (side/profile perception), R8 (services).
"""

import argparse
import logging
import signal
import sys
import time

import cv2
import depthai as dai
import numpy as np
from camera_config import OAK1_DEVICE_ID, SIDE_PORT, SideConfig
from detectors import detect_green_marker, detect_gripper_tip, verify_grasp
from stream_server import FrameStore, start_stream_server

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Overlay drawing
# ---------------------------------------------------------------------------


def draw_side_overlay(
    frame: np.ndarray,
    tip_det: dict | None,
    green: dict | None,
) -> np.ndarray:
    """Draw side-view detection overlays on the frame (in-place).

    Args:
        frame: BGR image to annotate.
        tip_det: Gripper-tip detection dict (tip_y_px, desk_y_px, gap_px).
        green: Green marker detection dict, or None.

    Returns:
        The annotated frame (same object, modified in-place).
    """
    _h, w = frame.shape[:2]

    if tip_det:
        tip_y = int(tip_det["tip_y_px"])
        desk_y = int(tip_det["desk_y_px"])
        gap = tip_det["gap_px"]

        # Desk line (green)
        cv2.line(frame, (0, desk_y), (w, desk_y), (0, 200, 0), 1)
        cv2.putText(
            frame,
            "desk",
            (5, desk_y - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (0, 200, 0),
            1,
        )

        # Gripper tip line (red)
        cv2.line(frame, (0, tip_y), (w, tip_y), (0, 0, 255), 1)
        cv2.putText(
            frame,
            f"tip (gap={gap:.0f}px)",
            (5, tip_y - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (0, 0, 255),
            1,
        )

        # Gap arrow
        mid_x = w // 2
        cv2.arrowedLine(frame, (mid_x, tip_y), (mid_x, desk_y), (255, 255, 0), 1)

        # Gap label
        gap_label = f"{gap:.0f}px"
        if tip_det.get("gap_mm") is not None:
            gap_label += f" / {tip_det['gap_mm']:.1f}mm"
        cv2.putText(
            frame,
            gap_label,
            (mid_x + 5, (tip_y + desk_y) // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (255, 255, 0),
            1,
        )

    # Green marker (if visible from side)
    if green:
        for fx, fy in green["fingers"]:
            cv2.circle(frame, (int(fx), int(fy)), 4, (255, 0, 255), 2)
        gx, gy = green["center"]
        cv2.drawMarker(
            frame,
            (int(gx), int(gy)),
            (0, 255, 255),
            cv2.MARKER_CROSS,
            12,
            1,
        )

    return frame


# ---------------------------------------------------------------------------
# Camera loop
# ---------------------------------------------------------------------------


def camera_loop(store: FrameStore, config: SideConfig) -> None:
    """Run the OAK-1 Lite camera pipeline for side-view height detection.

    Connects to the OAK-1 Lite by its USB deviceId, captures frames, runs
    gripper-tip height detection and optional green-marker detection, draws
    overlays, and pushes results to the FrameStore.

    This function runs indefinitely. On camera disconnect (X_LINK_ERROR),
    it logs the error and retries after a delay.

    Args:
        store: FrameStore to publish JPEG frames and JSON detections.
        config: SideConfig with device address, resolution, thresholds.
    """
    while True:
        try:
            logger.info(
                "Connecting to OAK-1 Lite (deviceId=%s, %dx%d @ %dfps)...",
                config.device_id,
                config.resolution[0],
                config.resolution[1],
                config.fps,
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
                logger.info("OAK-1 Lite side pipeline running.")

                while pipeline.isRunning():
                    in_frame = q.get()
                    if in_frame is None:
                        continue
                    frame = in_frame.getCvFrame()

                    # Detect gripper tip height
                    tip_result = detect_gripper_tip(frame, roi_frac=config.roi_frac)

                    # Detect green marker (may be visible from side)
                    green = detect_green_marker(frame)
                    green_data: dict | None = None
                    if green is not None:
                        green_data = {
                            "center": list(green.center_px),
                            "n": green.num_blobs,
                            "fingers": [[fx, fy] for fx, fy in green.fingers],
                        }

                    # Grasp verification
                    grasp = verify_grasp(frame)
                    grasp_data: dict = {
                        "object_present": grasp.object_present,
                        "confidence": round(grasp.confidence, 3),
                        "object_width_px": round(grasp.object_width_px, 1),
                    }
                    store.put_json("grasp", grasp_data)

                    # Publish JSON
                    gap_data: dict = {}
                    tip_overlay: dict | None = None
                    if tip_result is not None:
                        gap_data = {
                            "tip_y_px": tip_result.tip_y_px,
                            "desk_y_px": tip_result.desk_y_px,
                            "gap_px": tip_result.gap_px,
                            "gap_mm": tip_result.gap_mm,
                        }
                        tip_overlay = gap_data
                    store.put_json("gap", gap_data)

                    # Draw overlay and encode JPEG
                    draw_side_overlay(frame, tip_overlay, green_data)
                    ok, buf = cv2.imencode(
                        ".jpg",
                        frame,
                        [cv2.IMWRITE_JPEG_QUALITY, config.jpeg_quality],
                    )
                    if ok:
                        store.put_frame(buf.tobytes())

        except Exception as exc:  # noqa: BLE001 - camera loop must retry, not die
            logger.error("OAK-1 Lite camera error: %s. Retrying in 3s...", exc)
            time.sleep(3.0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the side camera stream service.

    Connects to the OAK-1 Lite, starts the HTTP server on SIDE_PORT,
    and runs the detection loop indefinitely.
    """
    parser = argparse.ArgumentParser(
        description="Side OAK-1 Lite stream + gripper-tip height service."
    )
    parser.add_argument(
        "--device",
        type=str,
        default=OAK1_DEVICE_ID,
        help=f"OAK-1 Lite deviceId (default: {OAK1_DEVICE_ID}).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=SIDE_PORT,
        help=f"HTTP port (default: {SIDE_PORT}).",
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
    config = SideConfig(device_id=args.device, resolution=(w, h))

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
        json_endpoints=["gap", "grasp"],
        title="Armold Side (OAK-1 Lite)",
    )
    logger.info("Side stream on :%d", args.port)

    # Run camera loop (blocks forever, with reconnect on error)
    camera_loop(store, config)


if __name__ == "__main__":
    main()
