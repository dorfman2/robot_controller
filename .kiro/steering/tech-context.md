---
inclusion: always
---

# Tech Context - Target Environment and Stack

## Core Requirements
- Python 3.12 (Pi), Python 3.10+ (Mac development)
- ROS 2 Jazzy (on Raspberry Pi 4, Ubuntu 24.04 Noble) — installed but removed from motion path
- USB serial access to Einsy RAMBo (current) and BTT Octopus MAX EZ (next-gen)
- PlatformIO for firmware development (on Mac)
- 24V DC, 10A power supply (upgradeable to 48V with EZ5160 drivers)
- Wi-Fi and Bluetooth connectivity for control interface

## Core Dependencies
### ROS 2 (Pi)
- `ros-jazzy-ros-base` — ROS 2 core runtime
- `ros-jazzy-rosbridge-suite` — WebSocket bridge for Mac → Pi communication
- `python3-colcon-common-extensions` — ROS 2 build tool
- `python3-rosdep` — Dependency management
- `micro-ROS agent` (planned) — Serial bridge between Pi and Arduino Mega

### Firmware (Arduino Mega)
- `TMCStepper` (v0.7.3) — TMC2208 UART driver control library
- `Stepper` (v1.1.3) — Arduino stepper motor library
- `Dynamixel2Arduino` (v0.7.0) — Robotis Dynamixel Protocol 2.0 servo control

### Legacy (from original robot_controller, to be migrated)
- `rospy`, `roslib`, `std_msgs`, `rosserial_python`, `catkin`

### Next-Gen Stack (BTT grblHAL + IK — spec complete, awaiting hardware)
- `ikpy` — Inverse kinematics solver (URDF → joint angles)
- `numpy` — Numerical computation for IK
- `pyserial` — GRBL serial communication (standard protocol)
- `websockets` — WebSocket server (existing, stays)
- **grblHAL** — 6-axis motion controller firmware (community-maintained, proven)
- **BTT Octopus MAX EZ V1.0** — STM32H723 board, 10 EZ driver slots, native USB
- **BTT EZ5160 RGB × 7** — TMC5160-TA drivers, 4.7A RMS, 8-56V, SPI, 50mΩ sense

### FK Simulator (Armold_FK_v1 — third-party reference)
- **Repository**: https://github.com/LeeWhite187/Armold_FK_v1
- **Stack**: Vite + Three.js (static client-side build, no backend)
- **Source**: `src/robot.js` (6-DOF arm FK), `src/sequencer.js` (step interpolation), `src/ui.js` (controls)
- **DIMS** (proportional units): baseHeight=0.35, shoulderHeight=0.55, upperArm=1.50, foreArm=1.25, wristLen=0.35, toolLen=0.45
- **Joint axes**: J0 Y-yaw, J1 X-pitch, J2 X-pitch, J3 X-pitch, J4 Z-yaw, J5 Y-roll
- **Home pose**: [0°, -30°, 70°, 50°, 0°, 0°]
- **Sequence JSON format**: `{"version":1, "steps":[{"name":"...", "angles":[deg×6], "gripper":0-1, "duration":s, "dwell":s}]}`
- **Integration planned**: digital twin / planning UI for physical arm (Phase 8 of BTT spec)

## Technologies, Libraries, and Protocols
- **ROS 2 Jazzy** — Current LTS middleware (Ubuntu 24.04, supported through 2029)
- **micro-ROS** (planned) — ROS 2 on microcontrollers, replaces rosserial
- **rosbridge** — WebSocket bridge for cross-machine ROS 2 communication
- **PlatformIO** — Embedded development ecosystem for firmware compilation, upload, and monitoring
- **TMC2208** — Trinamic stepper driver with StealthChop, UART config, 16 microsteps default
- **RAMPS 1.4** — 3D printer control board repurposed for stepper motor control (Arduino Mega 2560)
- **OpenCM 9.04** — Robotis controller board for Dynamixel smart servos (STM32F103CB MCU)
- **Dynamixel Protocol 2.0** — Serial communication protocol for Robotis smart servos (1Mbps bus)
- **Dynamixel XL430-W250** — Smart servo motors (joints 3, 4), range 0–4095, position/velocity feedback
- **Dynamixel XL-320** — Smaller smart servo (joint 5 + gripper), range 0–1023
- **Stepper motors** — Open-loop position control for joints 0, 1, 2 (NEMA 17)
- **USB Serial (115200 baud)** — Communication link between Pi and motor controllers
- **Arduino framework** — Used by both RAMPS (AVR) and OpenCM (STM32) firmware

## Raspberry Pi Configuration
- **Model**: Raspberry Pi 4
- **OS**: Ubuntu Server 24.04 LTS (Noble) arm64
- **Kernel**: 6.8.0-1060-raspi
- **ROS 2**: Jazzy Jalisco (installed, but being removed from motion path)
- **IP**: 192.168.1.136 (DHCP reservation)
- **mDNS**: armold.local
- **Hostname**: armold
- **User**: pi (SSH key auth, sudo NOPASSWD, dialout group)
- **SSH**: `ssh pi@armold.local` (ed25519 key, passphrase-protected)
- **PlatformIO**: installed at /home/pi/.local/bin (v6.1.19)
- **Serial devices**: /dev/armold_einsy (udev symlink from ttyACM0)

## Component Relationships and Dependencies
- `scripts/example.py` → legacy ROS 1 control script (to be migrated)
- `launch/rosserial.launch` → legacy ROS 1 launch (to be replaced by micro-ROS)
- `platformio.ini` → PlatformIO project config with two environments:
  - `env:ramps` — Arduino Mega 2560, atmelavr platform, TMCStepper + Stepper libraries
  - `env:opencm` — Generic STM32F103CB, ststm32 platform, Dynamixel2Arduino library
- `firmware/ramps/src/main.cpp` — Stepper motor test (basic STEP/DIR, TMC2208)
  - RAMPS pin map: J0(54,55,38), J1(60,61,56), J2(46,48,62)
- `firmware/opencm/src/main.cpp` — Dynamixel servo test (serial command interface)
  - Servo IDs: Joint3=1, Joint4=2, Joint5=3, Gripper=4
  - DXL bus: Serial1, direction pin 28, 1Mbps
- `pi/setup_ros2.sh` — Pi ROS 2 install script
- `pi/setup_ssh.sh` — SSH key setup script (run from Mac)
- `pi/README.md` — Pi setup documentation

## ROS Topics (Interface Contract)
- `/enable_motors` (std_msgs/Int16) — Enable (1) or disable (0) all motors
- `/stepper_goal` (std_msgs/Int16MultiArray) — Target positions for joints 0, 1, 2
- `/stepper_state` (std_msgs/Int16MultiArray) — Current positions of stepper joints
- `/servo_goal` (std_msgs/Int16MultiArray) — Target positions for joints 3, 4, 5
- `/servo_state` (std_msgs/Int32MultiArray) — Current positions of servo joints + gripper
- `/gripper_goal` (std_msgs/Int16) — Gripper position command (0–1023)

## Key Technical Decisions
- **ROS 2 Jazzy over Humble** — Pi image is Ubuntu 24.04 (Noble), Jazzy is the matching LTS
- **Einsy RAMBo 1.1a as current controller** — 4x TMC2130 via SPI, running on Pi now
- **BTT Octopus MAX EZ as next-gen controller** — STM32H723, 10 EZ slots, grblHAL, ordered pending
- **BTT EZ5160 over EZ2209** — 4.7A vs 2.0A, 56V support, SPI mode, StallGuard4 more reliable
- **grblHAL over custom firmware** — eliminates serial race conditions, proven G-code protocol
- **ikpy over Pinocchio** — simpler setup, pure Python, 7-50ms solve, URDF support
- **Option C now, Option A when hardware arrives** — zero spend while waiting
- Mixed motor architecture: steppers for base joints (high torque), smart servos for wrist (closed-loop)
- USB serial at 115200 baud for Einsy; BTT Octopus MAX EZ uses native USB (virtual baud)
- PlatformIO for firmware development — unified build/upload/monitor across both boards
- PlatformIO Core installed at `/Users/jdorfman/.platformio/penv/bin` (v6.1.19)
- Einsy serial port (Mac): `/dev/cu.usbmodem1101`
- Pi serial device (current): `/dev/armold_einsy` (udev symlink)
- Pi serial device (future BTT): `/dev/armold_motion` (udev symlink, VID 1d50 PID 614e)
- GRBL axis mapping: X=J0 (Base), Y=J1 (Shoulder), Z=J2 (Elbow), A=J3 (Wrist Pitch), B=J4 (Wrist Roll), C=J5 (Wrist Yaw)
- grblHAL steps/degree: 230.6 ($100-$105), soft limits full-range ($130=360, $131=180, $132=300, $133=240, $134=180, $135=360)
- URDF convention: Z-up, Z-axis base yaw, Y-axis pitch joints, link offsets along Z

## Armold_FK_v1 Simulator Joint Definitions (from robot.js)

| Joint | Name | Axis (Three.js Y-up) | URDF Axis (Z-up) | Limits | Home |
|-------|------|----------------------|------------------|--------|------|
| J0 | Base | Y-yaw | Z-yaw (`0 0 1`) | ±180° | 0° |
| J1 | Shoulder | X-pitch | Y-pitch (`0 1 0`) | ±90° | -30° |
| J2 | Elbow | X-pitch | Y-pitch (`0 1 0`) | ±150° | 70° |
| J3 | Wrist Pitch | X-pitch | Y-pitch (`0 1 0`) | ±120° | 50° |
| J4 | Wrist Yaw | Z-yaw | Z-yaw (`0 0 1`) | ±90° | 0° |
| J5 | Wrist Roll | Y-roll | X-roll (`1 0 0`) | ±180° | 0° |

## Einsy RAMBo TMC2130 Tuned Settings (Validated)

| Setting | Value | Rationale |
|---------|-------|-----------|
| Current | 1200mA RMS | ~80% of hardware max (1.48A), thermal headroom |
| Microsteps | 16 + interpolation to 256 | Smooth without MCU overhead |
| Mode | SpreadCycle | Better dynamic torque for rapid direction changes |
| Supply | 24V | Sufficient for current speeds; 36-48V for more high-speed torque later |
| Cruise delay | 20µs | Max speed with sinusoidal ramp |
| Accel/Decel | 300 steps | Sinusoidal S-curve profile, passes through resonance zone quickly |
| Start delay | 600µs | Conservative start prevents missed steps |
| Ramp shape | Sinusoidal (64-entry cosine table) | Zero jerk at transitions, smoother than linear |
| StallGuard | Disabled (sgt=63) | Cycloidal gearbox drag causes false triggers at all sensitivity levels |

### Hardware Notes
- Einsy sense resistors: 0.22Ω → max I_rms = 0.325V / 0.22Ω ≈ 1.48A
- TMC2130 supports 5-46V supply
- SPI controls: current, microstepping, mode, StallGuard sensitivity (all runtime-configurable)
- StallGuard sensorless homing available on DIAG pins (PK2, PK7, PK6, PK3) — future use at slower speeds
- SpreadCycle preferred over StealthChop for robot arm (dynamic response > silence)
- 20:1 cycloidal drive on all joints → calibrated to 83,028 steps/output revolution (~230.6 steps/degree)
- USB serial via ATmega32U2 bridge — max reliable baud: 250,000 (NOT native CDC)
- Segment protocol (`X` command) allows Pi-side trajectory planning with MCU interpolation
