---
inclusion: always
---

# Active Context - Current Task State

## Current Focus
BTT Octopus MAX EZ grblHAL 7-axis spec complete (requirements, design, tasks rewritten). Phase 1 (hardware setup) done — board flashed with 3-axis grblHAL, verified running. Phase 2 next: local PlatformIO build of 7-axis firmware from dresco/STM32H7xx. OAK-1 Lite vision pick-and-place spec also created.

## Recent Changes
- Rewrote `.kiro/specs/btt-grblhal-ik/` for 7-axis (XYZABCU) mapping
  - X = linear rail (80 steps/mm, 350mm, GT2 20T)
  - Y–U = arm joints J0–J5 (230.6 steps/°, 25.95:1 gearbox)
  - Gripper: 180° servo via M280 P0 S<angle> (PWM_SERVO_ENABLE)
- Local PlatformIO build replaces WebBuilder (dresco/STM32H7xx repo)
- Board map patch needed: Motor-7 (PD3/PD2/PD4/PD7) for U axis
- Build flags: `-D N_AXIS=7 -D PWM_SERVO_ENABLE=1 -D SPINDLE0_ENABLE=SPINDLE_NONE`
- Documented 10 edge cases (EC1–EC10) with mitigations
- `$DFU` command available for remote flash (no BOOT0 button needed)
- StallGuard only on X (linear rail); arm uses manual set-zero (G10 L20)
- SPI confirmed as correct interface for TMC5160/EZ5160 (UART not beneficial)
- Created OAK-1 Lite vision spec: `.kiro/specs/oak1-vision-pick/`
- All committed to `feature/btt-grblhal-ik` branch

## Upcoming Changes
- Phase 2: Clone dresco/STM32H7xx, add 7-axis env, patch board map, build, flash
- Phase 3: Wire motors to BTT, configure grblHAL settings ($100-$136, $376, TMC)
- Phase 4: IK setup (ikpy, URDF, calibration)
- Phase 5: Refactor armold_controller to single GrblBoard class
- Future: OAK-1 Lite vision integration (after grblHAL stack is stable)

## Active Decisions and Considerations
- Project name: "Armold"
- Software name: "Sweep Sync"
- **7-axis architecture**: Pi → BTT Octopus MAX EZ (grblHAL) → 7 EZ5160 → 7 motors
- **Axis mapping**: X=rail, Y=J0 Base, Z=J1 Shoulder, A=J2 Elbow, B=J3 Wrist Pitch, C=J4 Wrist Roll, U=J5 Wrist Yaw
- **Gripper**: 180° servo on FAN4 (PA1/AUXOUTPUT0), powered by separate 5V BEC
- **$376=126**: Y/Z/A/B/C/U all flagged rotary (U and Y/Z won't auto-detect)
- **StallGuard**: only X axis (rail) — arm joints home via manual set-zero
- **Flash method**: `$DFU` for routine updates; BOOT0 only for brick recovery
- **SPI over UART** for TMC5160: pre-routed hardware SPI4, tested path, no bus contention (SD card unused)
- **Consolidation**: Einsy + RAMPS retired, single board, single serial port
- **VID:PID**: 0483:5740 (STM Virtual COM Port) — udev rule for /dev/armold_motion
- **Deploy key**: `~/.ssh/armold_deploy` (ed25519, no passphrase)
- **OAK-1 Lite**: monocular vision, eye-to-hand fixed mount, YOLOv8n on Myriad X, known desk plane for depth
