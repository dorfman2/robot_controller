---
inclusion: always
---

# Active Context - Current Task State

## Current Focus
Stable bridge daemon deployed and running on Pi. Firmware updated with unified halt check (StallGuard + serial E-STOP) inside stepping loop. Set Home fix applied. Validation testing phase.

## Recent Changes
- Created armold_controller/ package (single Python daemon replaces 3 ROS services)
- Implemented SerialBoard, MotionManager, WebSocket server, command queue
- Firmware updated: StallGuard DIAG check + serial E-STOP check during cruise phase
- Set Home fix: daemon resets `board._position` immediately (not just pending_target)
- Serial connect fix: fallback to direct `S` sync when READY banner not seen
- Einsy flashed with halt-enabled firmware via deploy pipeline
- Old services disabled, new `armold.service` running on Pi
- `websockets` package installed on Pi
- README.md written with full project documentation
- All unit tests passing (13/13)
- Calibration: 83,028 steps/rev (~230.6 steps/degree)

## Upcoming Changes
- Deploy to Pi and run hardware validation (Phase 6 tasks)
- Run 1-hour IK demo stress test
- Test E-STOP latency (<100ms)
- Test StallGuard collision detection on physical arm
- Test USB unplug/replug recovery
- Tune StallGuard sgt per joint after mechanical testing

## Active Decisions and Considerations
- Project name: "Armold"
- Software name: "Sweep Sync"
- Primary board: Einsy RAMBo 1.1a (4 joints)
- Secondary board: RAMPS 1.4 (joints 4-5, not yet wired)
- ROS 2 Jazzy stays installed for future MoveIt integration, but removed from motion path
- New daemon: Python 3.12, pyserial, websockets (no ROS deps in data path)
- Calibration: 83,028 steps = 360° output (through cycloidal drive)
- TMC2130: 1200mA, 16µstep+interp, SpreadCycle, 30µs cruise, 300-step ramp
- Pi: armold.local (192.168.1.136), user pi, SSH key auth
- Deploy pipeline: scripts/deploy.sh (Mac → rsync → Pi → pio flash)
