# Dual Board 6-DOF Control — Tasks

## Phase 1: RAMPS Firmware for Joints 4-5
- [ ] Update RAMPS firmware to 2-axis mode (X=Joint4, Y=Joint5)
- [ ] Add speed ramping (same profile as Einsy: 300-step, 30µs cruise)
- [ ] Add coordinated G command (2-axis version)
- [ ] Install TMC2208 or TMC2209 drivers in RAMPS X and Y slots
- [ ] Flash and test joints 4 and 5 individually
- [ ] Test coordinated G command on RAMPS

## Phase 2: Pi Dual Serial Integration
- [ ] Connect both boards to Pi USB
- [ ] Set up udev rules: `/dev/armold_einsy`, `/dev/armold_ramps`
- [ ] Update ROS 2 bridge node for dual serial connections
- [ ] Implement joint routing (0-3 → Einsy, 4-5 → RAMPS)
- [ ] Implement parallel G command dispatch (both boards simultaneously)
- [ ] Test 6-joint `/stepper_goal` message end-to-end

## Phase 3: Web UI & Demo (6-DOF)
- [ ] Extend web UI from 3 to 6 joint panels
- [ ] Update IK demo for 6-DOF coordinated motion
- [ ] E-STOP disables both boards
- [ ] Add per-joint calibration if needed
- [ ] Test full system: Mac → WebSocket → Pi → both boards → 6 motors

## Phase 4: Finalize
- [ ] Commit all changes
- [ ] Update steering files with dual-board architecture
- [ ] Document wiring: Einsy (J0-J3) + RAMPS (J4-J5) + Pi USB connections
