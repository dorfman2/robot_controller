# Option D: RAMPS + BTT S42C Closed-Loop Steppers — Tasks

## Phase 1: Hardware Assembly & S42C Setup

- [ ] Order 4× BTT S42C V1.1 kits (include NEMA 17 motor + magnet + adapter plate)
- [ ] Verify magnet alignment on each motor shaft (centered, gap > 2mm from encoder IC)
- [ ] Mount S42C boards onto motors (check adapter plate orientation per manual)
- [ ] Wire S42C STEP/DIR/EN inputs to RAMPS X, Y, Z, E0 headers
- [ ] Connect 24V power to all S42C VM inputs (parallel from PSU)
- [ ] Connect motor phase wires from S42C outputs to NEMA 17 (verify wire order)
- [ ] Power on each S42C individually — confirm OLED displays home screen

## Phase 2: S42C Calibration

- [ ] Calibrate S42C #1 (J0 Base): OLED → Calibration → Confirm → wait 1-2 min
- [ ] Calibrate S42C #2 (J1 Shoulder): same procedure
- [ ] Calibrate S42C #3 (J2 Elbow): same procedure
- [ ] Calibrate S42C #4 (J3 Wrist Pitch): same procedure
- [ ] Verify calibration: manually rotate each motor shaft — OLED angle tracks smoothly
- [ ] Set parameters on each S42C via OLED:
  - Mode: Step Mode
  - Microstep: 16 (or 32 — decide based on resolution needs)
  - Current: High (or Very High for shoulder/elbow)
  - Direction: Normal (flip per joint if rotation is inverted)
  - Enable Pin: Normal
  - Stall: Enable
  - Save Setting → Flash

## Phase 3: RAMPS Firmware Adaptation

- [x] Fork existing Einsy firmware → new `firmware/ramps_s42c/` directory
- [x] Remove all TMC2130 SPI initialization code
- [x] Remove StallGuard logic (S42C handles stall internally)
- [x] Remove current setting code (S42C manages current internally)
- [x] Keep: sinusoidal ramp profile, segment protocol, serial command interface
- [x] Keep: E-STOP via serial `!` byte (disables STEP output immediately)
- [x] Update `steps_per_degree` constant:
  - 16 microsteps: `(16 × 200 × 20) / 360 = 177.8 steps/degree`
  - 32 microsteps: `(32 × 200 × 20) / 360 = 355.6 steps/degree`
- [x] Update enable pin logic: active LOW on RAMPS D38 (X), D56 (Y), D62 (Z), D24 (E0)
- [x] Add STEP/DIR pin definitions for RAMPS 1.4:
  - X: STEP=54, DIR=55, EN=38
  - Y: STEP=60, DIR=61, EN=56
  - Z: STEP=46, DIR=48, EN=62
  - E0: STEP=26, DIR=28, EN=24
- [x] Compile with PlatformIO: `pio run -e ramps_s42c`
- [x] Flash to Mega 2560: `pio run -e ramps_s42c -t upload`

## Phase 4: Integration Testing (Step Mode)

- [x] Connect RAMPS to Pi via USB — verify `/dev/armold_ramps` udev symlink
- [x] Send single-joint jog command from Pi → confirm motor moves with S42C closed-loop
- [x] Verify direction: positive command = expected rotation direction for each joint
- [x] Verify position tracking: command 360° → confirm output shaft completes one revolution
- [x] Calibrate actual steps/degree: command known angles, measure with protractor
  - Actual gearbox ratio: ~25.95:1 (83,028 steps = 360° at 16 microsteps)
- [x] Test multi-joint simultaneous movement
- [x] Test E-STOP: send `!` mid-move → confirm all motors halt instantly
- [x] Test stall detection: physically block a motor → verify S42C OLED shows stall
  - RESULT: S42C detects stall internally but cannot signal back to RAMPS in Step mode
  - Stall-based E-STOP not possible without UART monitoring hardware
  - Soft limits are the primary over-travel protection in this architecture
- [ ] Run existing armold_controller daemon → confirm WebSocket commands work
- [ ] Test Web UI: jog buttons, enable/disable, set home, E-STOP

## Phase 5: Stall → E-STOP Integration

- [ ] Determine how to detect S42C stall from Pi side:
  - Option A: Wire S42C stall output (if available) to RAMPS input pin → firmware reads
  - Option B: Connect S42C UART TX to Pi for monitoring (read register 0x95 position)
  - Option C: Detect stall by position timeout in armold_controller
- [ ] Implement chosen stall detection method
- [ ] On stall detection: trigger E-STOP (send `!` to RAMPS + disable motors)
- [ ] Test: block motor during jog → E-STOP fires within 100ms
- [ ] Add stall status to WebSocket state broadcast

## Phase 6: Finalize & Document

- [ ] Update armold.service with correct serial device paths
- [ ] Deploy to Pi: `rsync -az armold_controller/ pi@armold.local:~/armold_firmware/armold_controller/`
- [ ] Run full integration test via Web UI
- [ ] Update steering files with Option D architecture
- [ ] Document S42C parameters per joint (microstep, current, PID values)
- [ ] Document calibration procedure for future motor swaps
- [ ] Update motion-controller-analysis.md with Option D results
- [ ] Commit to main branch

## Future Considerations

- [ ] Evaluate S42C for joints 4-5 (wrist roll/yaw) — currently Dynamixel servos
- [ ] Investigate S42C firmware updates (community GitHub repo)
- [ ] Consider S42C V1.1 "metal protective cover" for thermal management under load
- [ ] Add IK demo using ikpy (4-DOF: position + pitch orientation)
- [ ] Integrate FK simulator (Armold_FK_v1) as planning UI
