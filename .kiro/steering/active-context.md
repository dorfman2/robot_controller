---
inclusion: always
---

# Active Context - Current Task State

## Current Focus
Stable bridge daemon deployed and running on Pi. Firmware updated with sinusoidal S-curve ramp (Phase A) and segment protocol (Phase B). Trajectory planning now on Pi with junction velocity optimization. Validation testing phase.

## Recent Changes
- Created armold_controller/ package (single Python daemon replaces 3 ROS services)
- Implemented SerialBoard, MotionManager, WebSocket server, command queue
- Firmware updated: sinusoidal cosine lookup table replaces linear ramp
- Firmware updated: segment command `X` for Pi-planned moves with interpolation
- Pi-side TrajectoryPlanner: S-curve profiles, junction velocity optimization, lookahead
- StallGuard disabled (sgt=63, false triggers with cycloidal gearbox)
- Serial E-STOP check in stepping loop (works mid-move)
- Set Home fix: daemon resets `board._position` immediately (not just pending_target)
- Serial connect fix: fallback to direct `S` sync when READY banner not seen
- Einsy flashed with halt-enabled firmware via deploy pipeline
- Old services disabled, new `armold.service` running on Pi
- `websockets` package installed on Pi
- README.md written with full project documentation
- All unit tests passing (13/13)
- Calibration: 83,028 steps/rev (~230.6 steps/degree)
- Max speed increased to 20µs step delay

## Upcoming Changes
- Run 1-hour IK demo stress test
- Test E-STOP latency (<100ms)
- Test USB unplug/replug recovery
- Tune StallGuard sgt per joint after mechanical testing (currently disabled)
- Phase C (full binary protocol + hardware timer) — future, needs MCU upgrade
- Sensorless homing (future spec)

## Active Decisions and Considerations
- Project name: "Armold"
- Software name: "Sweep Sync"
- Architecture: single Python daemon (`armold_controller`) with Pi-side trajectory planning
- Motion profile: sinusoidal S-curve (cosine lookup table on MCU, full S-curve from Pi segments)
- Primary board: Einsy RAMBo 1.1a (4 joints, TMC2130 SPI)
- Secondary board: RAMPS 1.4 (joints 4-5, not yet wired)
- ROS 2 Jazzy stays installed for future MoveIt integration, but removed from motion path
- Calibration: 83,028 steps = 360° output (~230.6 steps/degree)
- TMC2130: 1200mA, 16µstep+interp, SpreadCycle, 20µs cruise, sinusoidal 300-step ramp
- StallGuard: disabled (sgt=63) — cycloidal gearbox causes false triggers
- Serial: 250Kbaud max (ATmega32U2 bridge, NOT native CDC)
- Pi: armold.local (192.168.1.136), user pi, armold.service
- Daemon path on Pi: /home/pi/armold_firmware/armold_controller
- WebSocket: port 9090, JSON protocol
- Deploy: `./scripts/deploy.sh einsy` (firmware) + rsync armold_controller/ (daemon)
