"""Provision one CANBUS Stepper board after a stock-V0.11 flash.

Run ON THE PI with the USB cable attached to the freshly flashed board:
    /home/pi/armold-venv/bin/python /home/pi/provision_node.py <target_node_id>

Assumes the fresh board boots with the default NodeID 1 and no other ID-1
node is on the bus (J1 is parked at ID 7 during the campaign).

Steps: set NodeID -> closed-loop ON -> enable-on-boot OFF -> save -> verify
the version reply and angle stream on the new ID.
"""

from __future__ import annotations

import struct
import sys
import time

import serial

PORT = "/dev/armold_can_bridge"


def frame(node: int, msg: int, payload: bytes = b"", rtr: int = 0) -> bytes:
    """Build one serial-bridge line for the vendor frame format."""
    can_id = (node << 6) | msg
    return f"{can_id:X} {rtr} {payload.hex().upper().ljust(16, '0')}\n".encode()


def drain(s: serial.Serial, wait: float = 0.6) -> str:
    """Collect pending serial output after a short settle."""
    time.sleep(wait)
    return s.read(s.in_waiting or 0).decode(errors="replace")


def main() -> int:
    """Provision the board; return 0 on success."""
    target = int(sys.argv[1])
    if not 1 <= target <= 6:
        print(f"target must be 1-6, got {target}")
        return 1

    s = serial.Serial(PORT, 115200, timeout=1, write_timeout=3)
    time.sleep(2.5)
    s.reset_input_buffer()

    # 0. SAFETY FIRST: disable this board's driver immediately (stock default
    #    is enable-on-boot ON). Targeted at default ID 1, never broadcast
    #    (broadcast would drop holding torque on the other joints).
    s.write(frame(1, 5, b"\x00"))
    drain(s, 0.4)
    print("driver disabled (default-ID 1)")

    # 1. Set NodeID (addressed to default ID 1)
    s.write(frame(1, 25, struct.pack("<H", target)))
    out = drain(s)
    if f"Node ID set to: {target}" not in out:
        print(f"FAIL: no ID confirmation. Output: {out[-300:]}")
        return 1
    print(f"node id -> {target}")

    # 2. enable-on-boot OFF, 3. save  (at the NEW id).
    #    Closed-loop is deliberately NOT enabled here: with the direction map
    #    unset, an inverted encoder sense makes the loop a positive-feedback
    #    RUNAWAY (observed on J1, 2026-08-15). Closed-loop is enabled later,
    #    per joint, in bench Gate 1 after a direction-sense check.
    s.write(frame(target, 20, b"\x00"))
    drain(s, 0.3)
    s.write(frame(target, 24))
    out = drain(s, 1.0)
    print("save:", "OK" if "Saved" in out else f"NOT CONFIRMED: {out[-200:]}")

    # 5. Verify: version RTR + angle stream on the new ID
    s.reset_input_buffer()
    s.write(frame(target, 40, rtr=1))
    time.sleep(1.5)
    lines = s.read(s.in_waiting or 0).decode(errors="replace").splitlines()
    version = None
    angle_seen = False
    for line in lines:
        parts = line.split()
        if len(parts) != 3:
            continue
        try:
            cid = int(parts[0], 16)
        except ValueError:
            continue
        if cid == (target << 6) | 40:
            version = struct.unpack("<f", bytes.fromhex(parts[2])[:4])[0]
        if cid == (target << 6) | 33:
            angle_seen = True
    print(f"version: {version}  angle stream: {angle_seen}")
    ok = version is not None and abs(version - 0.11) < 0.005 and angle_seen
    print("PROVISION", "OK" if ok else "FAILED")
    s.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
