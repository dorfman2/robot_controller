---
inclusion: always
---

# Project Context - Big Picture View

## Project Owner
- Jeffrey Dorfman (GitHub: dorfman2)

## Project Purpose
"Armold" — A six-axis robot arm controller. Based on the dorfman2/robot_controller codebase which uses ROS, RAMPS 1.4 (stepper motors), and OpenCM 9.04 (Dynamixel servos) to control a Niryo-style robot arm. The companion software is called "Sweep Sync".

## Arm Specifications
- **Degrees of Freedom**: 6-DOF (6-axis movement)
- **Payload Capacity**: 750g
- **Maximum Reach**: 475mm (18.7 inches)
- **Repeatability**: ±1mm
- **Power Supply**: 24V DC, 10A
- **Control Interface**: Wi-Fi, Bluetooth
- **Software**: Sweep Sync
- **Materials**: 3D printed frame, off-the-shelf hardware

## Current Development Status
- Initial codebase cloned from dorfman2/robot_controller
- ROS catkin package structure in place
- Example Python control script functional (scripts/example.py)
- Launch file for rosserial configured (launch/rosserial.launch)
- udev rules for USB device access included (99-robot.rules)
- **Hardware status**: Waiting for electronic boards to arrive
- **Current phase**: Basic motor testing with robot_controller software via simple interface

## Key Features Designed
- Six-axis joint control (3 stepper motors + 2 XL430-W250 servos + 1 XL-320 servo)
- Gripper control via Dynamixel XL-320
- ROS topic-based motor enable/disable
- ROS topic-based position commands for steppers and servos
- State feedback via subscriber callbacks
- Python scripting interface for continuous movement
- Wi-Fi and Bluetooth control interfaces (future)

## Architecture Overview
The system uses a ROS (Kinetic) catkin workspace. A Raspberry Pi (or desktop) connects to two microcontroller boards via USB serial:
1. **RAMPS 1.4** — drives 3 stepper motors (joints 0, 1, 2) via Arduino firmware
2. **OpenCM 9.04** — drives Dynamixel smart servos (joints 3, 4, 5) and gripper

Communication flows through rosserial_python nodes bridging serial to ROS topics. The Python RobotArm class publishes commands and subscribes to state feedback.

Physical construction is 3D printed frame with off-the-shelf hardware components. Power is supplied via 24V DC at 10A.

## Next Development Priorities
- Build a basic motor testing interface (immediate — while waiting for boards)
- Modernize the Python control interface (type hints, logging, dataclasses)
- Add safety limits and joint range validation
- Implement Wi-Fi/Bluetooth control interface
- Implement inverse kinematics for end-effector positioning
- Evaluate ROS 2 migration path

## Technical Challenges
- ROS Kinetic is EOL; migration to ROS 2 (Humble/Iron) is a consideration
- Serial communication reliability over USB
- Stepper motor position accuracy without encoders
- Coordinating mixed motor types (steppers vs smart servos) for smooth trajectories
- Wi-Fi/Bluetooth latency for real-time control
