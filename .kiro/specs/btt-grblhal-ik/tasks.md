# BTT Octopus MAX EZ + grblHAL + IK — Tasks

## Phase 1: Hardware Procurement
- [ ] Order BTT Octopus MAX EZ V1.0
- [ ] Order 7× BTT EZ5160 RGB drivers
- [ ] Order USB-C cable (board to Pi)
- [ ] Confirm EZ5160 drivers fit EZ sockets on Octopus MAX EZ

## Phase 2: grblHAL Setup
- [ ] Flash grblHAL via grblHAL WebBuilder (BTT Octopus MAX EZ profile, 6 axes, TMC5160 SPI)
- [ ] Connect board to Pi via USB-C, verify serial port appears (/dev/ttyACM0 or similar)
- [ ] Set udev rule for persistent naming: `/dev/armold_motion`
- [ ] Configure steps/degree: $100-$105 = 230.6
- [ ] Configure max feed rates and acceleration: $110-$125
- [ ] Configure joint soft limits: $130-$135
- [ ] Configure TMC5160 via Trinamic plugin settings
- [ ] Verify: send `G1 X90 F1800` → joint 0 rotates 90°
- [ ] Verify: send `G1 X90 Y45 Z30 F1800` → all 3 joints move simultaneously
- [ ] Test E-STOP: `!` byte stops mid-move instantly
- [ ] Test GRBL status polling: `?` returns position

## Phase 3: IK Setup
- [ ] Install ikpy: `pip3 install ikpy numpy`
- [ ] Measure actual arm link lengths (base height, upper arm, forearm, wrist segments)
- [ ] Create armold.urdf with measured DH parameters
- [ ] Validate FK: given known joint angles → check end-effector position matches physical measurement
- [ ] Validate IK: give a reachable target → solve → move arm → confirm position
- [ ] Test joint limit enforcement in IK solver
- [ ] Test unreachable target returns None gracefully (no movement, error to client)
- [ ] Benchmark IK solve time on Pi (target: <50ms)

## Phase 4: armold_controller Refactor
- [ ] Replace serial_board.py with GrblBoard class (GRBL protocol)
- [ ] Replace motion_manager.py with MotionManager + IK integration
- [ ] Add GRBL status polling (2Hz), broadcast position to WebSocket clients
- [ ] Add E-STOP: sends `!` byte immediately (no lock, no queue)
- [ ] Add homing command handler
- [ ] Add speed profile: map Slow/Medium/Max to GRBL feed rates
- [ ] Add move_cartesian command: IK solve → G-code → send
- [ ] Update armold.service WorkingDirectory and restart
- [ ] Run existing unit tests, fix any failures

## Phase 5: Web UI Update
- [ ] Add Cartesian position display (XYZ + roll/pitch/yaw from FK)
- [ ] Add Cartesian jog panel (±1mm, ±10mm, ±100mm per axis)
- [ ] Add mode toggle (Joint / Cartesian)
- [ ] Update E-STOP to send estop command (maps to GRBL `!`)
- [ ] Update speed toggle to send set_speed (maps to GRBL feed rate)
- [ ] Update IK demo to use move_cartesian commands instead of joint targets

## Phase 6: Tuning + Validation
- [ ] Tune TMC5160 StallGuard per joint (sgt threshold for reliable homing)
- [ ] Run sensorless homing on J0, J1, J2
- [ ] Run 1-hour IK demo stress test (no crashes, no position desyncs)
- [ ] Test USB unplug/replug recovery
- [ ] Test E-STOP latency (<10ms)
- [ ] Verify Cartesian accuracy: command position → measure actual → compare
- [ ] Document final grblHAL $-settings in docs/

## Phase 7: Finalize
- [ ] Update motion-controller-analysis.md with Option A results
- [ ] Update steering files with new architecture
- [ ] Commit all changes to main
- [ ] Update README with new hardware and stack

## Phase 8: Simulator Integration (Armold_FK_v1 as UI Frontend)

The FK simulator at https://github.com/LeeWhite187/Armold_FK_v1 has a 3D arm model,
a step sequencer with pose interpolation, pick-and-place demo, and JSON export — making
it a ready-made planning UI for the physical arm. This phase integrates it.

### 8a: URDF Validation Against Simulator
- [ ] Run `npm install && npm run dev` in `Armold_FK_v1/` to launch simulator locally
- [ ] Set arm to home pose [0, -30, 70, 50, 0, 0] in simulator — note tool tip XYZ in browser console (`window.__armold.robot.getTipWorld()`)
- [ ] Compute FK via ikpy at the same angles — compare tool tip XYZ to simulator output
- [ ] Acceptable tolerance: <5% difference before SCALE calibration, <1% after physical measurement
- [ ] If FK matches: URDF joint axes are correct. If not: check axis direction signs in armold.urdf

### 8b: Link Length Calibration
- [ ] Measure physical upper arm length (shoulder pivot to elbow pivot, center-to-center) in mm
- [ ] Compute `SCALE = measured_mm / 150.0` (simulator DIMS.upperArm = 1.5, URDF units = meters)
- [ ] Update all link lengths in armold.urdf by multiplying simulator DIMS by SCALE:
  - baseHeight: `0.35 × SCALE`
  - shoulderHeight: `0.55 × SCALE`
  - upperArm: `1.50 × SCALE`
  - foreArm: `1.25 × SCALE`
  - wristLen: `0.35 × SCALE`
  - toolLen: `0.45 × SCALE`
- [ ] Re-run FK validation — confirm <1% error against physical measurement

### 8c: Sequence Export → G-code Pipeline
- [ ] Create `scripts/sequence_to_gcode.py` using the converter in design.md
- [ ] Export the simulator's built-in demo pick-and-place sequence as JSON (`File → Export JSON`)
- [ ] Run: `python3 scripts/sequence_to_gcode.py demo.json` → inspect generated G-code
- [ ] Verify home step produces `G1 X0.00 Y-30.00 Z70.00 A50.00 B0.00 C0.00 F1800`
- [ ] Test end-to-end: load generated G-code into armold_controller → run on physical arm

### 8d: Live Simulator → Physical Arm Bridge (Optional)
- [ ] Add "Send to Arm" button to simulator UI that POSTs the current sequence JSON to Pi WebSocket
- [ ] Pi daemon receives sequence JSON, calls `sequence_to_gcode()`, queues moves to grblHAL
- [ ] Add real-time position feedback: daemon broadcasts joint angles → simulator updates 3D display
  - WebSocket message: `{"type": "state", "joints": [0, -30, 70, 50, 0, 0]}`
  - Simulator: `window.__armold.robot.setAngles(angles.map(d => d * Math.PI/180))`
- [ ] This makes the simulator a live mirror of the physical arm position

### 8e: Simulator as Default Planning UI
- [ ] Build simulator for production: `npm run build` in `Armold_FK_v1/`
- [ ] Copy `dist/` output to Pi: `rsync -az Armold_FK_v1/dist/ pi@armold.local:~/armold_firmware/web/simulator/`
- [ ] Serve from armold_controller's web server at `/simulator/`
- [ ] Update web/index.html to link to simulator UI from main control panel

## Future (Option B Migration — Mesa + LinuxCNC)
- [ ] When closed-loop encoders are added, evaluate Mesa 7i92 + 7i76 + 7i78
- [ ] Your 6× StepperOnline TE drivers connect directly to Mesa STEP/DIR outputs
- [ ] IK code (ikpy + URDF) stays the same — only hardware interface changes
