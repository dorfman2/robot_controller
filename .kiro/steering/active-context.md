---
inclusion: always
---

# Active Context - Current Task State

## Current Focus
Einsy RAMBo 1.1a firmware validated with TMC2130 SPI drivers. Speed ramping (trapezoidal acceleration) working. SpreadCycle mode active at 1200mA. Ready to swap Einsy in as primary board and wire remaining joints.

## Recent Changes
- Einsy RAMBo firmware written and flashed (4-axis, TMC2130 SPI control)
- All 4 TMC2130 drivers communicating over SPI (verified)
- Speed ramping added: 300-step accel/decel, 600µs start, 30µs cruise
- Switched to SpreadCycle mode for better dynamic torque
- Current set to 1200mA RMS via SPI (no Vref pots needed)
- +360° / -360° rotation tests passing cleanly
- Calibration confirmed: 20,757 steps = 360° output (through cycloidal drive)
- PlatformIO multi-environment build fixed (build_src_filter per env)
- Web UI with IK demo, E-STOP, degree display deployed
- ROS 2 bridge using coordinated G command for simultaneous multi-joint motion
- Full ROS 2 stack working: Mac → WebSocket → Pi → bridge → serial → Einsy → motors

## Upcoming Changes
- Complete wiring changes for Einsy RAMBo (swap from RAMPS)
- Update bridge node to support 4-joint G command for Einsy
- Sensorless homing implementation (StallGuard)
- Commit Einsy firmware after wiring verified on all joints

## Active Decisions and Considerations
- Project name: "Armold"
- Software name: "Sweep Sync"
- Primary board: **Einsy RAMBo 1.1a** (replacing RAMPS 1.4)
- ROS 2 distro: Jazzy (Pi runs Ubuntu 24.04 Noble)
- Pi IP: 192.168.1.138, hostname: armold, user: pi
- Target: six-axis robot arm control (6-DOF, 750g payload, 475mm reach)
- TMC2130 settings: 1200mA, 16µstep+interp, SpreadCycle, 30µs cruise, 300-step ramp
- Einsy serial port on Mac: `/dev/cu.usbmodem1101`
- Control interfaces planned: Wi-Fi + Bluetooth
- Frame: 3D printed with off-the-shelf hardware
