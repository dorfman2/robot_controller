# Klipper-Style Motion Planner — Tasks

## Phase A: Sinusoidal Lookup Table (Immediate Improvement)
- [x] Generate 64-entry sinusoidal delay table (half-cosine: START_DELAY → CRUISE_DELAY)
- [x] Replace linear `rampDelay()` with table lookup in firmware
- [x] Verify builds and flash
- [ ] Test smoothness improvement on arm
- [ ] Update cruise delay constants if needed

## Phase B: Pi-Side Trajectory Planner (Segment Protocol)
- [x] Design S-curve profile computation (7-segment, per joint)
- [x] Implement `TrajectoryPlanner` class in armold_controller
- [x] Implement segment-based serial command (`X joint steps start_interval end_interval curve_type`)
- [x] Update MCU firmware to handle `X` command (interpolate within segment)
- [x] Implement junction velocity optimization (lookahead queue)
- [ ] Test: sequential jogs without pause between moves
- [ ] Test: IK demo with S-curve profiles
- [ ] Measure smoothness improvement vs Phase A

## Phase C: Full Binary Protocol + Hardware Timer (Future)
- [ ] Design binary serial protocol (opcodes, framing, CRC)
- [ ] Implement MCU ring buffer for step segments
- [ ] Implement hardware Timer1 ISR for step execution
- [ ] Implement clock synchronization protocol
- [ ] Implement buffer fill monitoring + underrun protection
- [ ] Rewrite Pi-side scheduler for binary protocol
- [ ] Implement per-step timestamp scheduling (if needed beyond segment interpolation)
- [ ] Validate: 100kHz step rate, <1µs jitter
- [ ] Stress test: 1-hour continuous motion

## Phase D: Inverse Kinematics Integration (Future Spec)
- [ ] Define arm geometry (DH parameters, link lengths)
- [ ] Implement forward kinematics
- [ ] Implement inverse kinematics (analytical or numerical)
- [ ] Add Cartesian target command to WebSocket protocol
- [ ] Integrate IK into trajectory planner pipeline
- [ ] Test: Cartesian space jogging from web UI
