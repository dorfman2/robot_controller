#!/usr/bin/env python3
"""Armold - Inverse Kinematics Demo (4-axis, RAMPS + BTT S42C).

Demonstrates coordinated 4-joint movement using the G command on RAMPS.
Moves all joints simultaneously through a series of poses that simulate
a pick-and-place motion within the physical joint limits.

Joint Limits (firmware soft limits):
    Joint 0 (Base):        ±360°
    Joint 1 (Shoulder):    ±90°
    Joint 2 (Elbow):       ±150°
    Joint 3 (Wrist Pitch): ±120°

Calibration: 83,028 steps = 360°, ~230.6 steps/degree
Hardware: RAMPS 1.4 + BTT S42C V1.1 closed-loop drivers (16 microsteps)

Usage:
    python3 ik_demo.py [serial_port]

    Default port: /dev/armold_ramps
"""

import logging
import serial
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# --- Calibration ---
STEPS_PER_REV: int = 83028
STEPS_PER_DEGREE: float = STEPS_PER_REV / 360.0  # ~230.6

# --- Number of joints ---
NUM_JOINTS: int = 4

# --- Joint Limits (degrees) — must match firmware soft limits ---
JOINT_LIMITS: list[tuple[float, float]] = [
    (-360.0, 360.0),   # Joint 0 (Base)
    (-90.0, 90.0),     # Joint 1 (Shoulder)
    (-150.0, 150.0),   # Joint 2 (Elbow)
    (-120.0, 120.0),   # Joint 3 (Wrist Pitch)
]

# --- Motion Parameters ---
STEP_DELAY_US: int = 60  # Cruise speed (microseconds per half-step)
DWELL_TIME: float = 0.8  # Pause between poses (seconds)


@dataclass
class Pose:
    """A joint-space pose for the robot arm.

    Attributes:
        joints: List of joint angles in degrees for [J0, J1, J2, J3].
        label: Human-readable description of this pose.
    """

    joints: list[float] = field(default_factory=list)
    label: str = ""


def degrees_to_steps(degrees: float) -> int:
    """Convert degrees to microsteps.

    Args:
        degrees: Angle in degrees.

    Returns:
        Equivalent position in microsteps.
    """
    return int(round(degrees * STEPS_PER_DEGREE))


def validate_pose(pose: Pose) -> list[str]:
    """Validate a pose against joint limits.

    Args:
        pose: The pose to validate.

    Returns:
        List of violation descriptions. Empty list if pose is valid.
    """
    violations: list[str] = []
    for i, angle in enumerate(pose.joints):
        lo, hi = JOINT_LIMITS[i]
        if angle < lo or angle > hi:
            violations.append(
                f"J{i}: {angle:.1f}° exceeds limit [{lo:.0f}°, {hi:.0f}°]"
            )
    return violations


def clamp_pose(pose: Pose) -> Pose:
    """Clamp a pose to joint limits.

    Args:
        pose: The desired pose.

    Returns:
        A new pose with angles clamped to valid ranges.
    """
    clamped: list[float] = []
    for i, angle in enumerate(pose.joints):
        lo, hi = JOINT_LIMITS[i]
        clamped.append(max(lo, min(hi, angle)))
    return Pose(clamped, pose.label)


def send_command(
    ser: serial.Serial, cmd: str, timeout: float = 60.0
) -> Optional[str]:
    """Send a command to the Arduino and wait for response.

    Args:
        ser: Serial connection.
        cmd: Command string (without newline).
        timeout: Maximum wait time in seconds.

    Returns:
        Response string or None if timeout.
    """
    ser.reset_input_buffer()
    ser.write(f"{cmd}\n".encode())
    ser.timeout = timeout
    response = ser.readline().decode("utf-8", errors="replace").strip()
    return response if response else None


def move_to_pose(ser: serial.Serial, pose: Pose) -> bool:
    """Move the arm to a pose using coordinated motion.

    Validates the pose against joint limits before sending. If any joint
    exceeds limits, the pose is clamped and a warning is logged.

    Args:
        ser: Serial connection to RAMPS.
        pose: Target pose in degrees.

    Returns:
        True if move succeeded, False otherwise.
    """
    violations = validate_pose(pose)
    if violations:
        for v in violations:
            logger.warning("Pose '%s' limit violation: %s", pose.label, v)
        pose = clamp_pose(pose)

    steps = [degrees_to_steps(a) for a in pose.joints]
    steps_str = " ".join(str(s) for s in steps)
    cmd = f"G {steps_str} {STEP_DELAY_US}"

    angles_str = ", ".join(f"{a:.1f}" for a in pose.joints)
    label = f" ({pose.label})" if pose.label else ""
    print(f"  Moving to [{angles_str}]{label}")
    print(f"    Steps: {steps}")

    response = send_command(ser, cmd, timeout=60.0)

    if response and response.startswith("OK G"):
        print(f"    OK: {response}")
        return True
    else:
        logger.error("Move failed for pose '%s': %s", pose.label, response)
        return False


def build_sequence() -> list[Pose]:
    """Build the pick-and-place demonstration sequence.

    All poses are designed to stay within the firmware soft limits:
        J0: ±360°, J1: ±90°, J2: ±150°, J3: ±120°

    Returns:
        List of Pose objects defining the motion sequence.
    """
    return [
        Pose([0, 0, 0, 0], "Home"),
        # --- Pick sequence ---
        Pose([0, -45, -60, -30], "Approach"),
        Pose([0, -70, -90, -50], "Reach down"),
        Pose([0, -85, -120, -70], "Pick position"),
        Pose([0, -50, -60, -30], "Lift with object"),
        # --- Place sequence ---
        Pose([90, -50, -60, -30], "Rotate to place"),
        Pose([90, -75, -100, -55], "Lower to place"),
        Pose([90, -50, -60, -30], "Retract from place"),
        # --- Return ---
        Pose([45, -20, -30, -10], "Mid transit"),
        Pose([0, 0, 0, 0], "Home"),
        # --- Demonstration poses ---
        Pose([-60, -30, 45, 20], "Look left-up"),
        Pose([60, -30, 45, 20], "Look right-up"),
        Pose([0, 45, 90, 60], "Reach forward-up"),
        Pose([0, -45, -90, -60], "Reach forward-down"),
        Pose([0, 0, 0, 0], "Home"),
    ]


def run_demo(ser: serial.Serial) -> None:
    """Run the IK demonstration sequence.

    Moves through a series of poses simulating a pick-and-place operation
    with all joints moving simultaneously via coordinated G commands.

    Args:
        ser: Serial connection to the RAMPS board.
    """
    sequence = build_sequence()

    # Validate all poses before running
    print("\n=== Armold IK Demo (4-axis, RAMPS + S42C) ===")
    print(f"Calibration: {STEPS_PER_REV} steps/rev ({STEPS_PER_DEGREE:.1f} steps/deg)")
    print(f"Step delay: {STEP_DELAY_US} µs")
    print(f"Dwell: {DWELL_TIME} s between poses")
    print(f"Poses: {len(sequence)}")
    print(f"Limits: J0=±360° J1=±90° J2=±150° J3=±120°")
    print()

    all_valid = True
    for pose in sequence:
        violations = validate_pose(pose)
        if violations:
            all_valid = False
            for v in violations:
                logger.error("Pre-check: pose '%s' — %s", pose.label, v)

    if not all_valid:
        logger.error("Sequence has limit violations. Aborting.")
        return

    print("All poses validated within limits.\n")

    for i, pose in enumerate(sequence):
        print(f"[{i + 1}/{len(sequence)}]")
        success = move_to_pose(ser, pose)
        if not success:
            print("  Motion failed, stopping demo.")
            break
        time.sleep(DWELL_TIME)

    print("\n=== Demo Complete ===")


def main() -> None:
    """Entry point for the IK demo.

    Connects to the RAMPS board, enables motors, runs the demonstration
    sequence, then returns home and disables motors.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/armold_ramps"
    baud = 250000

    print(f"Connecting to {port} at {baud} baud...")
    ser = serial.Serial(port, baud, timeout=2)
    time.sleep(2)
    ser.read(1024)  # Flush startup banner

    # Enable motors
    response = send_command(ser, "E1")
    print(f"Enable motors: {response}")

    if not response or "OK" not in response:
        logger.error("Failed to enable motors. Check connection.")
        ser.close()
        return

    # Reset positions to zero
    send_command(ser, "R")
    print("Position reset to home (0, 0, 0, 0)\n")

    try:
        run_demo(ser)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        # Return home and disable
        print("Returning home...")
        send_command(ser, f"G 0 0 0 0 {STEP_DELAY_US}", timeout=60.0)
        time.sleep(1)
        send_command(ser, "E0")
        print("Motors disabled.")
        ser.close()


if __name__ == "__main__":
    main()
