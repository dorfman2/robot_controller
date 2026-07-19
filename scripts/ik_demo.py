#!/usr/bin/env python3
"""
Armold - Inverse Kinematics Demo

Demonstrates coordinated 3-joint movement using the G command.
Moves all joints simultaneously through a series of poses that simulate
a simple pick-and-place motion.

Joint Limits:
    Joint 0 (Base):     ±360° (±20,757 steps)
    Joint 1 (Shoulder): ±100° (±5,770 steps)
    Joint 2 (Elbow):    ±100° (±5,770 steps)

Calibration: 20,757 steps = 360°, ~57.7 steps/degree

Usage:
    python3 ik_demo.py [serial_port]

    Default port: /dev/armold_ramps (Pi) or /dev/cu.usbserial-AL03LVPB (Mac)
"""

import serial
import time
import sys
import math
from dataclasses import dataclass
from typing import Optional


# --- Calibration ---
STEPS_PER_REV: int = 20757
STEPS_PER_DEGREE: float = STEPS_PER_REV / 360.0  # ~57.66

# --- Joint Limits (degrees) ---
JOINT_LIMITS: list[tuple[float, float]] = [
    (-360.0, 360.0),   # Joint 0 (Base)
    (-100.0, 100.0),   # Joint 1 (Shoulder)
    (-100.0, 100.0),   # Joint 2 (Elbow)
]

# --- Motion Parameters ---
STEP_DELAY_US: int = 150  # Fast coordinated moves


@dataclass
class Pose:
    """A joint-space pose for the robot arm.

    Attributes:
        j0: Joint 0 angle in degrees.
        j1: Joint 1 angle in degrees.
        j2: Joint 2 angle in degrees.
        label: Human-readable description of this pose.
    """
    j0: float
    j1: float
    j2: float
    label: str = ""


def degrees_to_steps(degrees: float) -> int:
    """Convert degrees to microsteps.

    Args:
        degrees: Angle in degrees.

    Returns:
        Equivalent position in microsteps.
    """
    return int(round(degrees * STEPS_PER_DEGREE))


def clamp_pose(pose: Pose) -> Pose:
    """Clamp a pose to joint limits.

    Args:
        pose: The desired pose.

    Returns:
        A new pose with angles clamped to valid ranges.
    """
    j0 = max(JOINT_LIMITS[0][0], min(JOINT_LIMITS[0][1], pose.j0))
    j1 = max(JOINT_LIMITS[1][0], min(JOINT_LIMITS[1][1], pose.j1))
    j2 = max(JOINT_LIMITS[2][0], min(JOINT_LIMITS[2][1], pose.j2))
    return Pose(j0, j1, j2, pose.label)


def send_command(ser: serial.Serial, cmd: str, timeout: float = 30.0) -> Optional[str]:
    """Send a command to the Arduino and wait for response.

    Args:
        ser: Serial connection.
        cmd: Command string.
        timeout: Maximum wait time.

    Returns:
        Response string or None.
    """
    ser.reset_input_buffer()
    ser.write(f'{cmd}\n'.encode())
    ser.timeout = timeout
    response = ser.readline().decode('utf-8', errors='replace').strip()
    return response if response else None


def move_to_pose(ser: serial.Serial, pose: Pose) -> bool:
    """Move the arm to a pose using coordinated motion.

    Args:
        ser: Serial connection.
        pose: Target pose in degrees.

    Returns:
        True if move succeeded.
    """
    pose = clamp_pose(pose)
    s0 = degrees_to_steps(pose.j0)
    s1 = degrees_to_steps(pose.j1)
    s2 = degrees_to_steps(pose.j2)

    cmd = f'G {s0} {s1} {s2} {STEP_DELAY_US}'

    label = f' ({pose.label})' if pose.label else ''
    print(f'  Moving to [{pose.j0:.1f}, {pose.j1:.1f}, {pose.j2:.1f}]{label}')
    print(f'    Steps: [{s0}, {s1}, {s2}]')

    response = send_command(ser, cmd, timeout=60.0)

    if response and response.startswith('OK G'):
        print(f'    OK: {response}')
        return True
    else:
        print(f'    FAILED: {response}')
        return False


def run_demo(ser: serial.Serial) -> None:
    """Run the IK demonstration sequence.

    Moves through a series of poses simulating a pick-and-place operation
    with all joints moving simultaneously.

    Args:
        ser: Serial connection to the Arduino.
    """
    # Define motion sequence (degrees)
    sequence: list[Pose] = [
        Pose(0, 0, 0, "Home"),
        Pose(0, -45, -30, "Reach down"),
        Pose(0, -60, -60, "Pick position"),
        Pose(0, -30, -20, "Lift"),
        Pose(90, -30, -20, "Rotate to place"),
        Pose(90, -50, -40, "Lower to place"),
        Pose(90, -30, -20, "Retract"),
        Pose(0, 0, 0, "Home"),
        Pose(-45, 30, 50, "Look up left"),
        Pose(45, 30, 50, "Look up right"),
        Pose(0, 0, 0, "Home"),
        Pose(0, -80, -80, "Deep reach"),
        Pose(180, -80, -80, "Sweep 180"),
        Pose(180, 0, 0, "Upright far"),
        Pose(0, 0, 0, "Home"),
    ]

    print('\n=== Armold IK Demo ===')
    print(f'Joint limits: J0=±360°, J1=±100°, J2=±100°')
    print(f'Step delay: {STEP_DELAY_US} us')
    print(f'Poses: {len(sequence)}')
    print()

    for i, pose in enumerate(sequence):
        print(f'[{i + 1}/{len(sequence)}]')
        success = move_to_pose(ser, pose)
        if not success:
            print('  Motion failed, stopping demo.')
            break
        time.sleep(0.5)  # Brief pause between poses

    print('\n=== Demo Complete ===')


def main() -> None:
    """Entry point for the IK demo."""
    port = sys.argv[1] if len(sys.argv) > 1 else '/dev/armold_ramps'

    print(f'Connecting to {port}...')
    ser = serial.Serial(port, 115200, timeout=2)
    time.sleep(2)
    ser.read(1024)  # Flush startup

    # Enable motors
    response = send_command(ser, 'E1')
    print(f'Enable motors: {response}')

    if not response or 'OK' not in response:
        print('Failed to enable motors. Check connection.')
        ser.close()
        return

    # Reset positions to zero
    send_command(ser, 'R')
    print('Position reset to home (0, 0, 0)')

    try:
        run_demo(ser)
    except KeyboardInterrupt:
        print('\nInterrupted by user.')
    finally:
        # Return home and disable
        print('Returning home...')
        send_command(ser, 'G 0 0 0 200', timeout=60.0)
        time.sleep(1)
        send_command(ser, 'E0')
        print('Motors disabled.')
        ser.close()


if __name__ == '__main__':
    main()
