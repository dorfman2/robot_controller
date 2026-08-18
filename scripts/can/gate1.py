"""Gate 1 runner for CANBUS Stepper joints (ros2-can-motion bench gate).

Runs the per-joint Gate-1 phases over the J1 USB bridge, with the lessons
from J6 baked in (sane params before motion, harness spin before direction,
position-mode target for the hold test, RTR read-back instead of trusting
console echoes).

Usage (on the Pi):
    gate1.py <node> spin        # sane params + slow velocity spin; reports delta
    gate1.py <node> dir <0|1>   # set direction map, then verification spin
    gate1.py <node> finalize    # closed-loop ON + save + RTR verify + hold target
    gate1.py <node> hold        # re-issue position-mode hold at current angle
    gate1.py <node> disable     # disable driver
    gate1.py <node> status      # RTR: angle, closedLoop, mapDirection, enableOnBoot

Pass criteria per joint: spin smooth (no stall buzz), positive delta for a
positive command after `dir` is settled, config verified saved, back-drive
returns to the held target.
"""

from __future__ import annotations

import os
import struct
import sys
import time

import serial

PORT = "/dev/armold_can_bridge"
SPIN_DPS = 30.0  # motor deg/s for the harness/direction spin
SPIN_SECS = 4.0
POS_SPEED = 120.0  # motor deg/s (stock default 2000 stalls geared joints)
ACCEL = 200.0
# Geared joints stall at 40% (J5); shoulder needs 85% (J2). Override per joint:
#   GATE1_CURRENT=85 gate1.py 2 dir 1
CURRENT_PCT = int(os.environ.get("GATE1_CURRENT", "70"))


def open_port() -> serial.Serial:
    """Open the bridge port and wait out the settle time."""
    s = serial.Serial(PORT, 115200, timeout=1, write_timeout=3)
    time.sleep(2.5)
    return s


def frame(node: int, msg: int, payload: bytes = b"", rtr: int = 0) -> bytes:
    """Build one vendor serial-bridge line."""
    can_id = (node << 6) | msg
    return f"{can_id:X} {rtr} {payload.hex().upper().ljust(16, '0')}\n".encode()


def rtr_value(s: serial.Serial, node: int, msg: int, fmt: str) -> float | int | None:
    """RTR-request one value from a node and decode it."""
    s.reset_input_buffer()
    s.write(frame(node, msg, rtr=1))
    time.sleep(0.9)
    for line in s.read(s.in_waiting or 0).decode(errors="replace").splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        try:
            cid = int(parts[0], 16)
        except ValueError:
            continue
        if cid == (node << 6) | msg:
            return struct.unpack(fmt, bytes.fromhex(parts[2])[: struct.calcsize(fmt)])[
                0
            ]
    return None


def angle(s: serial.Serial, node: int) -> float | None:
    """Read the node's encoder angle in motor degrees."""
    val = rtr_value(s, node, 33, "<d")
    return float(val) if val is not None else None


def apply_params(s: serial.Serial, node: int) -> None:
    """Send sane motion parameters (stock defaults stall geared joints)."""
    s.write(frame(node, 16, struct.pack("<f", POS_SPEED)))
    time.sleep(0.2)
    s.write(frame(node, 17, struct.pack("<f", ACCEL)))
    time.sleep(0.2)
    s.write(frame(node, 18, struct.pack("<f", ACCEL)))
    time.sleep(0.2)
    s.write(frame(node, 4, struct.pack("<H", CURRENT_PCT)))
    time.sleep(0.2)


def spin(s: serial.Serial, node: int) -> None:
    """Slow velocity spin: harness health + direction sense in one pass."""
    apply_params(s, node)
    before = angle(s, node)
    print(f"baseline: {before:+.3f} motor deg")
    s.write(frame(node, 5, b"\x01"))
    time.sleep(0.4)
    s.write(frame(node, 3, struct.pack("<f", SPIN_DPS)))
    time.sleep(SPIN_SECS)
    s.write(frame(node, 3, struct.pack("<f", 0.0)))
    time.sleep(0.6)
    after = angle(s, node)
    s.write(frame(node, 5, b"\x00"))
    if before is None or after is None:
        print("VERDICT: INCONCLUSIVE — angle RTR dropped; re-run spin")
        return
    delta = after - before
    expected = SPIN_DPS * SPIN_SECS
    print(f"after:    {after:+.3f}   delta: {delta:+.3f} (|expected| ~{expected:.0f})")
    if abs(delta) < expected * 0.5:
        print("VERDICT: STALL/BUZZ — check the coil harness (AABB vs ABAB loom)")
    elif delta > 0:
        print("VERDICT: smooth + direction CORRECT — run finalize")
    else:
        print("VERDICT: smooth but INVERTED — run: dir 1  (then finalize)")


def set_dir(s: serial.Serial, node: int, inverted: int) -> None:
    """Set the direction map, then re-run the verification spin."""
    s.write(frame(node, 15, bytes([inverted])))
    time.sleep(0.4)
    print(f"mapDirection set to {inverted}; verification spin:")
    spin(s, node)


def finalize(s: serial.Serial, node: int) -> None:
    """Enable closed loop, save, verify via RTR, set a hold target."""
    s.write(frame(node, 13, struct.pack("<h", 1)))
    time.sleep(0.4)
    s.write(frame(node, 24))
    time.sleep(1.0)
    cl = rtr_value(s, node, 13, "<h")
    md = rtr_value(s, node, 15, "<B")
    eb = rtr_value(s, node, 20, "<B")
    print(f"verify: closedLoop={cl} mapDirection={md} enableOnBoot={eb}")
    if cl != 1 or eb != 0:
        print("CONFIG NOT AS EXPECTED — do not proceed to hold test")
        return
    hold(s, node)


def hold(s: serial.Serial, node: int) -> None:
    """Enable and set a position-mode hold target at the current angle."""
    a = angle(s, node)
    s.write(frame(node, 5, b"\x01"))
    time.sleep(0.3)
    s.write(frame(node, 1, struct.pack("<d", a)))
    time.sleep(0.4)
    print(f"HOLD target set at {a:+.3f} motor deg — back-drive the joint now")
    print("(node left ENABLED; run disable when done)")


def status(s: serial.Serial, node: int) -> None:
    """Print the node's key state via RTR."""
    print(f"angle:        {angle(s, node)}")
    print(f"closedLoop:   {rtr_value(s, node, 13, '<h')}")
    print(f"mapDirection: {rtr_value(s, node, 15, '<B')}")
    print(f"enableOnBoot: {rtr_value(s, node, 20, '<B')}")


def main() -> None:
    """Dispatch the requested phase."""
    node = int(sys.argv[1])
    cmd = sys.argv[2]
    s = open_port()
    if cmd == "spin":
        spin(s, node)
    elif cmd == "dir":
        set_dir(s, node, int(sys.argv[3]))
    elif cmd == "finalize":
        finalize(s, node)
    elif cmd == "hold":
        hold(s, node)
    elif cmd == "disable":
        s.write(frame(node, 5, b"\x00"))
        time.sleep(0.3)
        print(f"node {node} disabled")
    elif cmd == "status":
        status(s, node)
    else:
        print(f"unknown command: {cmd}")
    s.close()


if __name__ == "__main__":
    main()
