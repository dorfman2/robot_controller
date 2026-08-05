"""
OAK-4 S bring-up verification script.

Run on the Pi to:
1. Enumerate ALL DepthAI devices (USB + network).
2. Confirm the OAK-4 S is reachable on the local network by IP.
3. Confirm the OAK-1 Lite is still reachable by USB deviceId.
4. Capture a test frame from each to verify pipelines work concurrently.
5. Print addressing info and persist to ~/armold_cameras.json.

Usage (on Pi, in armold-venv):
    python scripts/vision/oak4s_bringup.py
    python scripts/vision/oak4s_bringup.py --oak4-ip 192.168.1.138
    python scripts/vision/oak4s_bringup.py --save-frames

References:
    R1 (two-camera architecture), R7 (networking & power)

DepthAI v3 API notes:
    - DeviceInfo has: deviceId, name, protocol, platform, state, status
    - Device(DeviceInfo) or Device(nameOrDeviceId: str) connects to a device
    - Pipeline(defaultDevice: Device) targets a specific device
    - OAK-4 S: protocol=X_LINK_TCP_IP, platform=X_LINK_RVC4, name=<IP>
    - OAK-1 Lite: protocol=X_LINK_USB_VSC, platform=X_LINK_MYRIAD_X
"""

import argparse
import json
import logging
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import cv2
    import depthai as dai
except ImportError as exc:
    logger.error("Missing dependency: %s. Run from armold-venv on the Pi.", exc.name)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Known device identifiers (update after first discovery)
# ---------------------------------------------------------------------------
OAK4S_IP = "192.168.1.138"
OAK1_DEVICE_ID = "19443010A113177E00"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CameraInfo:
    """Discovered camera identification and status.

    Attributes:
        name: Human label (e.g. 'OAK-4 S overhead', 'OAK-1 Lite side').
        device_id: DepthAI deviceId (stable per device).
        protocol: Connection protocol string.
        ip: IP address if network-connected, else None.
        platform: Platform string (e.g. 'X_LINK_RVC4', 'X_LINK_MYRIAD_X').
        state: Device state string from DepthAI.
        frame_captured: Whether a test frame was successfully captured.
        frame_shape: Shape tuple (H, W, C) of the captured frame, or None.
        frame_mean: Mean pixel value of captured frame.
        depthai_version: DepthAI library version string.
    """

    name: str
    device_id: str
    protocol: str
    ip: str | None = None
    platform: str = ""
    state: str = ""
    frame_captured: bool = False
    frame_shape: tuple[int, ...] | None = None
    frame_mean: float | None = None
    depthai_version: str = field(default_factory=lambda: dai.__version__)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_all_devices() -> list[dai.DeviceInfo]:
    """Enumerate all DepthAI devices visible on USB and the local network.

    Returns:
        List of DeviceInfo objects. May be empty if no devices found.
    """
    devices = dai.Device.getAllAvailableDevices()
    logger.info("Found %d DepthAI device(s) total.", len(devices))
    return devices


def print_device_table(devices: list[dai.DeviceInfo]) -> None:
    """Print a human-readable table of all discovered devices.

    Args:
        devices: List of DeviceInfo from discovery.
    """
    if not devices:
        print("\n  (no devices found)\n")
        return

    print(
        f"\n{'#':<3} {'Name':<20} {'DeviceId':<22} {'State':<16} "
        f"{'Protocol':<22} {'Platform'}"
    )
    print("-" * 110)
    for i, dev in enumerate(devices):
        print(
            f"{i:<3} {dev.name:<20} {dev.deviceId:<22} "
            f"{dev.state!s:<16} {dev.protocol!s:<22} "
            f"{dev.platform!s}"
        )
    print()


def identify_oak4s(
    devices: list[dai.DeviceInfo], ip: str | None = None
) -> dai.DeviceInfo | None:
    """Identify the OAK-4 S in the device list (RVC4, TCP_IP).

    Args:
        devices: List from discovery.
        ip: Known IP to match against device name field.

    Returns:
        Matching DeviceInfo or None.
    """
    for dev in devices:
        # RVC4 platform is the definitive indicator for OAK-4 S
        if "RVC4" in str(dev.platform):
            return dev
        # Fallback: match by IP in the name field
        if ip and ip == dev.name:
            return dev
    return None


def identify_oak1(
    devices: list[dai.DeviceInfo],
    device_id: str | None = None,
    exclude_dev: dai.DeviceInfo | None = None,
) -> dai.DeviceInfo | None:
    """Identify the OAK-1 Lite in the device list (MYRIAD_X, USB).

    Args:
        devices: List from discovery.
        device_id: Known deviceId to match.
        exclude_dev: A DeviceInfo to exclude (e.g. the already-identified OAK-4 S).

    Returns:
        Matching DeviceInfo or None.
    """
    for dev in devices:
        if exclude_dev is not None and dev.deviceId == exclude_dev.deviceId:
            continue
        if device_id and dev.deviceId == device_id:
            return dev
        if "MYRIAD" in str(dev.platform) and "USB" in str(dev.protocol):
            return dev
    return None


# ---------------------------------------------------------------------------
# Frame capture test
# ---------------------------------------------------------------------------


def capture_test_frame(
    name_or_id: str,
    resolution: tuple[int, int] = (640, 360),
    timeout_s: float = 10.0,
    save_path: str | None = None,
) -> tuple[tuple[int, ...], float] | None:
    """Open a pipeline on a device, capture one frame, return shape and mean.

    Uses DepthAI v3 API: Device(nameOrDeviceId) → Pipeline(device).

    Args:
        name_or_id: Device IP address or deviceId string.
        resolution: (width, height) for the output stream.
        timeout_s: Max seconds to wait for a frame.
        save_path: If given, save the captured frame as JPEG.

    Returns:
        Tuple of (shape, mean_pixel_value) on success, or None on failure.
    """
    try:
        info = dai.DeviceInfo(name_or_id)
        device = dai.Device(info)

        with dai.Pipeline(device) as pipeline:
            cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
            out = cam.requestOutput(resolution, dai.ImgFrame.Type.BGR888i, fps=15)
            q = out.createOutputQueue(maxSize=4, blocking=False)
            pipeline.start()

            # Let auto-exposure settle for a couple frames
            t0 = time.time()
            frame = None
            frame_count = 0
            while time.time() - t0 < timeout_s:
                in_frame = q.tryGet()
                if in_frame is not None:
                    frame = in_frame.getCvFrame()
                    frame_count += 1
                    # Take the 3rd frame for AE settling
                    if frame_count >= 3:
                        break
                time.sleep(0.03)

            if frame is None:
                logger.warning("No frame received within %.1fs.", timeout_s)
                return None

            shape = tuple(frame.shape)
            mean_val = float(frame.mean())
            logger.info("Captured frame: shape=%s, mean=%.1f", shape, mean_val)

            if save_path:
                cv2.imwrite(save_path, frame)
                logger.info("Saved test frame to %s", save_path)

            return (shape, mean_val)

    except Exception as exc:  # noqa: BLE001 - device I/O errors are reported, not fatal
        logger.error("Frame capture failed for %s: %s", name_or_id, exc)
        return None


# ---------------------------------------------------------------------------
# Concurrent capture test
# ---------------------------------------------------------------------------


def test_concurrent_capture(
    oak4_id: str, oak1_id: str, save_frames: bool = False
) -> dict[str, tuple[tuple[int, ...], float] | None]:
    """Test that both cameras can capture frames simultaneously.

    Args:
        oak4_id: OAK-4 S IP or deviceId.
        oak1_id: OAK-1 Lite deviceId.
        save_frames: Whether to save test frames.

    Returns:
        Dict mapping camera name to capture result (or None on failure).
    """
    results: dict[str, tuple[tuple[int, ...], float] | None] = {}
    lock = threading.Lock()

    def _capture(name: str, dev_id: str) -> None:
        save_path = (
            f"/tmp/oak_bringup_{name.replace(' ', '_')}.jpg" if save_frames else None
        )
        result = capture_test_frame(dev_id, save_path=save_path)
        with lock:
            results[name] = result

    t1 = threading.Thread(target=_capture, args=("OAK-4 S overhead", oak4_id))
    t2 = threading.Thread(target=_capture, args=("OAK-1 Lite side", oak1_id))

    t0 = time.time()
    t1.start()
    t2.start()
    t1.join(timeout=20)
    t2.join(timeout=20)
    elapsed = time.time() - t0

    logger.info("Concurrent capture completed in %.1fs", elapsed)
    return results


# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------

CONFIG_PATH = Path.home() / "armold_cameras.json"


def persist_camera_config(cameras: list[CameraInfo]) -> None:
    """Save discovered camera info to ~/armold_cameras.json.

    This file is consumed by the dual-camera stream services to address
    each device by its stable identifier.

    Args:
        cameras: List of CameraInfo dataclass instances.
    """
    data = {
        "cameras": [asdict(c) for c in cameras],
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "depthai_version": dai.__version__,
        "notes": {
            "oak4s": "OAK-4 S addressed by IP over local network (TCP_IP, RVC4)",
            "oak1": "OAK-1 Lite addressed by deviceId over USB (MYRIAD_X)",
            "api": "DepthAI v3: dai.DeviceInfo(name_or_id) → dai.Device(info) → "
            "dai.Pipeline(device)",
        },
    }
    CONFIG_PATH.write_text(json.dumps(data, indent=2, default=str))
    logger.info("Camera config persisted to %s", CONFIG_PATH)
    print(f"\nConfig saved: {CONFIG_PATH}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the OAK-4 S bring-up verification.

    Discovers all devices, identifies the OAK-4 S (network/RVC4) and
    OAK-1 Lite (USB/MYRIAD_X), captures test frames concurrently,
    and persists addressing info to ~/armold_cameras.json.
    """
    parser = argparse.ArgumentParser(
        description="OAK-4 S bring-up: discover, verify, persist camera config."
    )
    parser.add_argument(
        "--oak4-ip",
        type=str,
        default=OAK4S_IP,
        help=f"IP of the OAK-4 S on the LAN (default: {OAK4S_IP}).",
    )
    parser.add_argument(
        "--oak1-id",
        type=str,
        default=OAK1_DEVICE_ID,
        help=f"deviceId of the OAK-1 Lite (default: {OAK1_DEVICE_ID}).",
    )
    parser.add_argument(
        "--save-frames",
        action="store_true",
        help="Save test frames as JPEG to /tmp/.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    print(f"DepthAI version: {dai.__version__}")
    print("=" * 60)
    print("Phase 0: OAK-4 S + OAK-1 Lite Bring-up Verification")
    print("=" * 60)

    # Step 1: Discover all devices
    print("\n[1/4] Discovering DepthAI devices (USB + network)...")
    devices = discover_all_devices()
    print_device_table(devices)

    if not devices:
        print(
            "ERROR: No DepthAI devices found.\n"
            "  - Is the OAK-4 S powered (USB-C supply) and on the network?\n"
            "  - Is the OAK-1 Lite plugged into the Pi's USB?\n"
            "  - Check: lsusb | grep 03e7\n"
            f"  - Check: ping {args.oak4_ip}\n"
        )
        sys.exit(1)

    # Step 2: Identify each camera
    print("[2/4] Identifying cameras...")
    oak4_dev = identify_oak4s(devices, ip=args.oak4_ip)
    oak1_dev = identify_oak1(devices, device_id=args.oak1_id, exclude_dev=oak4_dev)

    cameras: list[CameraInfo] = []

    if oak4_dev is not None:
        oak4_ip = oak4_dev.name if "." in oak4_dev.name else args.oak4_ip
        print(
            f"  OAK-4 S: name={oak4_dev.name}, deviceId={oak4_dev.deviceId}, "
            f"platform={oak4_dev.platform}"
        )
        cameras.append(
            CameraInfo(
                name="OAK-4 S overhead",
                device_id=oak4_dev.deviceId or oak4_ip,
                protocol=str(oak4_dev.protocol),
                ip=oak4_ip,
                platform=str(oak4_dev.platform),
                state=str(oak4_dev.state),
            )
        )
    else:
        print(f"  WARNING: OAK-4 S not found. Expected at IP {args.oak4_ip}.")

    if oak1_dev is not None:
        print(
            f"  OAK-1 Lite: name={oak1_dev.name}, deviceId={oak1_dev.deviceId}, "
            f"platform={oak1_dev.platform}"
        )
        cameras.append(
            CameraInfo(
                name="OAK-1 Lite side",
                device_id=oak1_dev.deviceId,
                protocol=str(oak1_dev.protocol),
                platform=str(oak1_dev.platform),
                state=str(oak1_dev.state),
            )
        )
    else:
        print(f"  WARNING: OAK-1 Lite not found. Expected deviceId={args.oak1_id}.")

    # Step 3: Concurrent capture test (tests both individual AND simultaneous)
    print("\n[3/4] Concurrent capture test (both cameras simultaneously)...")
    if oak4_dev and oak1_dev:
        oak4_id = oak4_dev.name if "." in oak4_dev.name else args.oak4_ip
        oak1_id = oak1_dev.deviceId
        concurrent_results = test_concurrent_capture(
            oak4_id, oak1_id, save_frames=args.save_frames
        )
        all_concurrent_ok = True
        for name, result in concurrent_results.items():
            if result is not None:
                print(f"  [PASS] {name}: shape={result[0]}, mean={result[1]:.1f}")
                # Update CameraInfo with results
                for cam in cameras:
                    if cam.name == name:
                        cam.frame_captured = True
                        cam.frame_shape = result[0]
                        cam.frame_mean = result[1]
            else:
                print(f"  [FAIL] {name}")
                all_concurrent_ok = False
        if all_concurrent_ok:
            print("  ✓ Concurrent operation confirmed.")
        else:
            print("  ✗ Concurrent test failed.")
    else:
        print("  SKIPPED (need both cameras identified)")
        all_concurrent_ok = False

    # Step 4: Summary and persist
    print("\n[4/4] Summary")
    print("-" * 60)
    all_ok = True
    for cam in cameras:
        status = "PASS" if cam.frame_captured else "FAIL"
        if not cam.frame_captured:
            all_ok = False
        ident = cam.ip or cam.device_id
        print(f"  {cam.name:<20} id={ident:<22} [{status}]")

    if len(cameras) < 2:
        all_ok = False

    persist_camera_config(cameras)

    print("\n" + "=" * 60)
    if all_ok and all_concurrent_ok:
        print("✓ PASS — Both cameras operational and concurrent.")
        print("\nCamera addressing (for services/config):")
        for cam in cameras:
            if cam.ip:
                print(f"  {cam.name}: dai.DeviceInfo('{cam.ip}')")
            else:
                print(f"  {cam.name}: dai.DeviceInfo('{cam.device_id}')")
        print(f"\nConfig: {CONFIG_PATH}")
        print("\nRecommended next steps:")
        print(f"  1. Set DHCP reservation: {args.oak4_ip} → OAK-4 S MAC")
        print(f"  2. Test: ping {args.oak4_ip} (verify stable after reboot)")
        print("  3. Proceed to Phase 1 (dual-camera plumbing)")
    else:
        print("✗ INCOMPLETE — See warnings above.")

    sys.exit(0 if (all_ok and all_concurrent_ok) else 1)


if __name__ == "__main__":
    main()
