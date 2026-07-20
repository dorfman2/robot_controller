#!/usr/bin/env python3
"""
Armold - Inverse Kinematics Demo (4-axis, Einsy RAMBo)

Demonstrates coordinated 4-joint movement using the G command on the Einsy.
Moves all joints simultaneously through a series of poses that simulate
a pick-and-place motion.

Joint Limits:
    Joint 0 (Base):        ±360°
    Joint 1 (Shoulder):    ±180°
    Joint 2 (Elbow):       ±180°
    Joint 3 (Wrist Pitch): ±100°

Calibration: 83,028 steps = 360°, ~230.6 steps/degree

Usage:
    python3 ik_demo.py [serial_port]

    Default port: /dev/armold_einsy
"""

import serial
import time
import sys
from dataclasses import dataclass
from typing import Optional


# --- Calibration ---
STEPS_PER_REV: int = 83028
STEPS_PER_DEGREE: float = STEPS_PER_REV / 360.0  # ~230.6

# --- Number of joints on Einsy ---
NUM_JOINTS: int = 4

# --- Joint Limits (degrees) ---
JOINT_LIMITS: list[tuple[float, float]] = [
    (-360.0, 360.0),   # Joint 0 (Base)
    (-180.0, 180.0),   # Joint 1 (Shoulder)
    (-180.0, 180.0),   # Joint 2 (Elbow)
    (-100.0, 100.0),   # Joint 3 (Wrist Pitch)
]

# --- Motion Parameters ---
STEP_DELAY_US: int = 30  # Cruise speed (matches firmware default)


@dataclass
class Pose:
    """A joint-space pose for the robot arm.

    Attributes:
        joints: List of joint angles in degrees.
        label: Human-readable description of this pose.
    """
    joints: list[float]
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
    clamped = []
    for i, angle in enumerate(pose.joints):
        lo, hi = JOINT_LIMITS[i]
        clamped.append(max(lo, min(hi, angle)))
    return Pose(clamped, pose.label)


def send_command(ser: serial.Serial, cmd: str, timeout: float = 60.0) -> Optional[str]:
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
    steps = [degrees_to_steps(a) for a in pose.joints]

    steps_str = ' '.join(str(s) for s in steps)
    cmd = f'G {steps_str} {STEP_DELAY_US}'

    angles_str = ', '.join(f'{a:.1f}' for a in pose.joints)
    label = f' ({pose.label})' if pose.label else ''
    print(f'  Moving to [{angles_str}]{label}')
    print(f'    Steps: {steps}')

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
    # Define motion sequence: [J0_base, J1_shoulder, J2_elbow, J3_wrist]
    sequence: list[Pose] = [
        Pose([0, 0, 0, 0], "Home"),
        Pose([0, -135, -105, -30], "Reach down"),
        Pose([0, -165, -165, -45], "Pick position"),
        Pose([0, -105, -85, -20], "Lift"),
        Pose([90, -105, -85, -20], "Rotate to place"),
        Pose([90, -145, -125, -35], "Lower to place"),
        Pose([90, -105, -85, -20], "Retract"),
        Pose([0, 0, 0, 0], "Home"),
        Pose([-45, 105, 135, 45], "Look up left"),
        Pose([45, 105, 135, 45], "Look up right"),
        Pose([0, 0, 0, 0], "Home"),
    ]

    print('\n=== Armold IK Demo (4-axis) ===')
    print(f'Calibration: {STEPS_PER_REV} steps/rev ({STEPS_PER_DEGREE:.1f} steps/deg)')
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
    port = sys.argv[1] if len(sys.argv) > 1 else '/dev/armold_einsy'

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
    print('Position reset to home (0, 0, 0, 0)')

    try:
        run_demo(ser)
    except KeyboardInterrupt:
        print('\nInterrupted by user.')
    finally:
        # Return home and disable
        print('Returning home...')
        send_command(ser, f'G 0 0 0 0 {STEP_DELAY_US}', timeout=60.0)
        time.sleep(1)
        send_command(ser, 'E0')
        print('Motors disabled.')
        ser.close()


if __name__ == '__main__':
    main()
