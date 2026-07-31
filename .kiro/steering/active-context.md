---
inclusion: always
---

# Active Context - Current Task State

## Current Focus
Klipper migration Phase 4 (motor testing) in progress. All 7 motors confirmed moving in Klipper — including Motor-7 (J5) which failed in grblHAL. TMC5160 SPI also working. Hit overheating issue due to high hold current — fixed in printer.cfg. Waiting for motors to cool before continuing.

## Recent Changes
- Flashed Klipper MCU firmware to BTT Octopus MAX EZ (v0.13.0-718, STM32H723@520MHz)
- Katapult bootloader attempt failed (USB enumeration issue on H723 — deferred)
- Klipper flashed directly to 0x08000000 (no bootloader offset)
- Klipper + Moonraker installed on Pi via KIAUH, services running
- printer.cfg created with 7 manual steppers + TMC5160 SPI + servo gripper
- armold_controller refactored with KlipperBoard class (Moonraker API)
- All 7 motors tested and confirmed moving (including Motor-7!)
- Motor current tuned: run=0.800A (J3=1.200A), hold=0.300A (J3=0.750A)
- Committed to `feature/btt-grblhal-ik` branch

## Upcoming Changes
- Continue Phase 4: re-test motors with reduced current (after cooldown)
- Test coordinated motion (GCODE_AXIS for A/B/C/U, MANUAL_STEPPER for X/Y/Z)
- Test gripper servo
- Test TMC5160 status: `DUMP_TMC`
- Phase 6: StallGuard homing on rail, soft limits in daemon
- Future: OAK-1 Lite vision integration (after Klipper stack is stable)

## Active Decisions and Considerations
- Project name: "Armold"
- Software name: "Sweep Sync"
- **Klipper over grblHAL**: grblHAL Motor-7/8 pins didn't produce physical movement; Klipper works on all slots
- **7-axis architecture**: Pi (klippy + armold_controller) → BTT Octopus MAX EZ (Klipper MCU) → 7 EZ5160 → 7 motors
- **Axis mapping**: X=rail, Y=J0 Base, Z=J1 Shoulder, A=J2 Elbow, B=J3 Wrist Pitch, C=J4 Wrist Roll, U=J5 Wrist Yaw
- **Gripper**: 180° 9g metal gear servo on PA1 (FAN4), powered by separate 5V BEC
- **Motor current**: run=0.800A all except J3=1.200A; hold=0.300A all except J3=0.750A
- **StallGuard**: only X axis (rail) — arm joints home via SET_POSITION=0
- **Flash method**: DFU (Katapult deferred due to H723 USB issue); Klipper's flash_usb.py for future updates
- **SPI for TMC5160**: confirmed working in Klipper (failed in grblHAL on this board)
- **Consolidation**: Einsy + RAMPS retired, single board, single serial port
- **VID:PID**: 1d50:614e (OpenMoko/Klipper)
- **Klipper serial ID**: usb-Klipper_stm32h723xx_380009001151313531383332-if00
- **Moonraker API**: localhost:7125 for all armold_controller communication
- **GCODE_AXIS**: only A/B/C/U (X/Y/Z reserved by Klipper). Coordinated motion via G1 A.. B.. C.. U..
- **Deploy key**: `~/.ssh/armold_deploy` (ed25519, no passphrase)
- **OAK-1 Lite**: monocular vision, eye-to-hand fixed mount, YOLOv8n on Myriad X, known desk plane for depth
