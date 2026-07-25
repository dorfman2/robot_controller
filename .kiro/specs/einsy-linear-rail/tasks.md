# Einsy Linear Rail (Base Slide) — Tasks

## Phase 1: Mechanical Setup

- [ ] Acquire linear rail (length TBD — 300mm, 500mm, or 1000mm)
- [ ] Acquire GT2 belt + 20T pulley OR lead screw + nut
- [ ] Mount NEMA 17 stepper to rail carriage
- [ ] Mount robot arm base plate to rail carriage
- [ ] Connect motor to Einsy X-axis stepper output
- [ ] Verify rail slides freely by hand (no binding)
- [ ] Measure and record travel length (mm)
- [ ] Calculate and record steps/mm based on drive mechanism

## Phase 2: Einsy Firmware (Single-Axis Linear)

- [x] Create `firmware/einsy_linear/src/main.cpp`
- [x] Add `[env:einsy_linear]` to platformio.ini
- [x] Implement TMC2130 SPI initialization (X-axis only)
  - SpreadCycle mode, 16 microsteps + interpolation
  - Current: 1000 mA RMS (irun=20 on 0.22Ω sense resistors)
  - StallGuard: sgt=4, diag1_stall enabled
- [x] Implement single-axis motion with sinusoidal ramp
- [x] Implement serial command protocol (E, M, S, R, !, ?)
- [x] Implement soft limits (0 to max_travel in steps)
- [x] Implement StallGuard homing command (H)
  - Slow move toward home end
  - StallGuard DIAG1 triggers → stop → set position to 0
- [x] Implement E-STOP: check `!` byte every step
- [x] Add steps_per_mm constant (configurable via `#define`)
- [x] Report position in steps (daemon converts to mm)
- [x] Compile: `pio run -e einsy_linear`
- [x] Flash to Einsy (via Pi): avrdude to `/dev/armold_einsy`
- [x] Verify boot banner: `ARMOLD EINSY_LINEAR 1.0`

## Phase 3: Pi Daemon Integration

- [x] Update `config.json`: enable Einsy board (1 joint, 115200 baud)
- [ ] Verify daemon connects to both RAMPS and Einsy simultaneously
- [ ] Verify jog on linear axis (joint 4) via WebSocket
- [ ] Verify jog on rotational joints (0–3) still works
- [ ] Verify E-STOP halts both boards simultaneously
- [ ] Test: move linear + rotate arm concurrently (no serial conflicts)

## Phase 4: Web UI Integration

- [x] Add linear rail panel to Web UI (position in steps + mm)
- [x] Add jog buttons for linear axis (±1mm, ±10mm, ±100mm)
- [x] Add Home button (sends `H` command to Einsy)
- [x] Add steps/mm config input (GT2=80, leadscrew=400, etc.)
- [x] Show linear position alongside rotational joint positions
- [x] E-STOP button halts both boards

## Phase 5: StallGuard Tuning & Homing

- [ ] Test StallGuard at slow speed (200µs delay) — does it trigger at end of rail?
- [ ] Tune sgt threshold: increase if false triggers, decrease if not detecting
- [ ] Verify homing repeatability: home 10 times, measure variance (target: ±0.5mm)
- [ ] Test StallGuard at different speeds — find reliable homing speed
- [ ] Add homing offset if needed (back off N steps after trigger)

## Phase 6: Finalize

- [ ] Run full integration test: home rail → IK demo with arm at different rail positions
- [ ] Document steps/mm for the chosen drive mechanism
- [ ] Document StallGuard tuning values
- [ ] Update steering files with linear rail architecture
- [ ] Commit to main
