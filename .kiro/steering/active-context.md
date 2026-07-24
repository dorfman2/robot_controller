---
inclusion: always
---

# Active Context - Current Task State

## Current Focus
Option D (RAMPS + BTT S42C closed-loop) spec created and firmware deployed. Integration testing in progress — J0 and J1 calibrated and confirmed at 16 microsteps, 83,028 steps = 360° (230.6 steps/degree). Soft limits implemented. Hardware physically connected and running on Pi.

## Recent Changes
- Created `.kiro/specs/ramps-s42c-closed-loop/` (requirements.md, design.md, tasks.md)
- Created `firmware/ramps_s42c/src/main.cpp` — full RAMPS firmware for S42C
- Added `[env:ramps_s42c]` to platformio.ini
- Set up passwordless SSH deploy key (`~/.ssh/armold_deploy`) for Pi access
- Compiled, deployed, and flashed firmware to RAMPS Mega 2560 on Pi
- Calibrated: 83,028 steps = 360° at 16 microsteps (gearbox ratio ~25.95:1, not 20:1)
- Added soft limits per joint (J0 ±360°, J1 ±90°, J2 ±150°, J3 ±120°)
- Tested J0: 90° forward/back — accurate ✓
- Tested J1: 45° forward/back — accurate ✓
- All joints set to 16 microsteps (uniform calibration)
- Finalized BTT grblHAL IK spec (reviewed, inconsistencies fixed, Phase 8 added)
- Updated all steering files with BTT + S42C decisions
- Committed to main: `6817ee7`

## Upcoming Changes
- Test J2 and J3
- Test E-STOP mid-move
- Test stall detection (block a motor physically)
- Run armold_controller daemon with RAMPS S42C firmware
- Test Web UI integration
- Order 4× BTT S42C V1.1 kits (if not already all connected)
- Calibrate actual steps/degree for J2 and J3 (confirm same gearbox)

## Active Decisions and Considerations
- Project name: "Armold"
- Software name: "Sweep Sync"
- **Option D architecture**: Pi → RAMPS → S42C Step mode (closed-loop internal)
- **No Phase 2 (UART mode)**: Eliminated — requires extra USB-serial adapters
- **Microstep setting**: 16 for all joints (uniform, same as Einsy)
- **Calibration**: 83,028 steps/rev = 230.6 steps/degree (empirically measured, same as Einsy)
- **Gearbox ratio**: ~25.95:1 (not 20:1 as originally assumed)
- **Soft limits**: J0 ±360°, J1 ±90°, J2 ±150°, J3 ±120°
- **S42C config per motor**: Mode=Step, Microstep=16, Current=High, Direction=Normal, Enable=Normal, Stall=Enable
- **Deploy pipeline**: `pio run -e ramps_s42c` → rsync hex → avrdude flash via `armold_deploy` key
- **Pi SSH**: `ssh -i ~/.ssh/armold_deploy pi@armold.local` (no passphrase)
- **Serial device**: `/dev/armold_ramps` → ttyUSB0, 250000 baud
- IK compatible: ikpy + URDF runs on Pi, outputs step commands to RAMPS
