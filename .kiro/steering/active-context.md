---
inclusion: always
---

# Active Context - Current Task State

## Current Focus
Raspberry Pi set up with ROS 2 Jazzy. RAMPS firmware (basic STEP/DIR, TMC2208) flashed and tested — all 3 joints confirmed working. Next step: micro-ROS agent for rostopic interface.

## Recent Changes
- Raspberry Pi 4 set up: Ubuntu 24.04 (Noble), ROS 2 Jazzy installed
- Pi accessible via SSH key auth: `ssh pi@192.168.1.138`
- All system packages updated, kernel 6.8.0-1060-raspi
- rosdep initialized, rosbridge-suite installed
- RAMPS firmware reflashed to clean STEP/DIR mode (no custom gcode)
- TMC2208 X driver was bad — swapped, all 3 joints (X/Y/Z) confirmed moving
- Motor speed testing: 200µs (fast) to 2000µs (slow) step delay range validated
- Pi setup scripts created in `pi/` directory

## Upcoming Changes
- Set up micro-ROS agent on Pi for serial bridge to Arduino Mega
- Flash Arduino Mega with micro-ROS firmware (replaces current STEP/DIR test)
- Test rostopic-based motor control from Mac → Pi → Mega
- Set up udev rules on Pi for persistent serial device naming

## Active Decisions and Considerations
- Project name: "Armold"
- Software name: "Sweep Sync"
- ROS 2 distro: **Jazzy** (not Humble — Pi runs Ubuntu 24.04 Noble)
- Pi IP: 192.168.1.138, hostname: armold, user: pi
- Target: six-axis robot arm control (6-DOF, 750g payload, 475mm reach)
- TMC2208 drivers: Vref ~1.9V, 16 microsteps (all RAMPS jumpers in)
- One TMC2208 was bad (X slot) — replaced
- Control interfaces planned: Wi-Fi + Bluetooth
- Frame: 3D printed with off-the-shelf hardware
