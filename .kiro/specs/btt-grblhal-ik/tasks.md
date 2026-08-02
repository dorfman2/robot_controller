# BTT Octopus MAX EZ + grblHAL + IK — Tasks (7-Axis)

## Phase 1: Hardware Setup
- [x] Order BTT Octopus MAX EZ V1.0
- [x] Order 7× BTT EZ5160 RGB drivers
- [x] Order USB-C cable (board to Pi)
- [x] Install EZ5160 drivers in EZ sockets
- [x] Connect board to Pi via USB-C
- [x] Bridge VUSB jumper for USB-powered DFU flashing
- [x] Verify board enters DFU mode (BOOT0 + RESET)
- [x] Flash initial grblHAL firmware via dfu-util (3-axis build, confirmed working)
- [x] Verify serial port appears: `/dev/ttyACM0` (VID `0483` PID `5740`)
- [x] Verify grblHAL responds: `GrblHAL 1.1f`, STM32H723@480MHz, Trinamic plugin loaded

## Phase 2: 7-Axis Firmware Build (Local PlatformIO)
- [x] Clone grblHAL STM32H7 driver: `git clone --recursive https://github.com/dresco/STM32H7xx.git`
- [x] Add `[env:btt_octopus_max_armold_7axis]` to platformio.ini with `-D N_AXIS=7 -D PWM_SERVO_ENABLE=1 -D SPINDLE0_ENABLE=SPINDLE_NONE` (EC5)
- [x] Patch `boards/btt_octopus_max_map.h`: raise motor limit to 7, add M6 (Motor-7: PD3/PD2/PD4/PD7)
- [x] Build: `pio run -e btt_octopus_max_armold_7axis` — verify compiles clean
- [x] Copy firmware.bin to Pi: `scp .pio/build/.../firmware.bin pi@armold.local:/tmp/firmware.bin`
- [x] Put board in DFU mode (BOOT0 + RESET)
- [x] Flash: `ssh pi@armold.local "sudo dfu-util -a 0 -s 0x08000000:leave -D /tmp/firmware.bin"`
- [x] Verify: `$I` shows `[AXS:7:XYZABCU]` and `[PLUGIN:Trinamic]`
- [x] Verify: `[PLUGIN:Bootloader Entry]` present (enables `$DFU` for future flashes without BOOT0)

## Phase 3: Configuration + Motor Wiring
- [x] Set udev rule for `/dev/armold_motion` (VID `0483`, PID `5740`)
- [ ] Move linear rail motor from Einsy to BTT Motor-1 (X axis)
- [ ] Move arm motors from RAMPS to BTT Motor-2 through Motor-7 (Y–U)
- [ ] Wire 180° gripper servo to FAN4 header (PA1 — AUXOUTPUT0, PWM capable)
- [ ] Power gripper servo from separate 5V BEC, not board 5V rail (EC10: stall current too high)
- [ ] Configure steps/unit: `$100=80` (rail mm), `$101-$106=230.6` (arm degrees)
- [ ] Configure feed rates: `$110=5000` (rail), `$111-$116=1800` (arm)
- [ ] Configure acceleration: `$120=500` (rail), `$121-$126=900` (arm)
- [ ] Configure soft limits: `$20=1`, `$130=350`, `$131=360`, `$132=180`, `$133=300`, `$134=240`, `$135=180`, `$136=360`
- [ ] Configure rotary axes: `$376=126` — required, U/Y/Z won't auto-detect as rotary (EC1)
- [ ] Configure homing: `$22=1`, `$44=1` (X only), `$45=0`, `$46=0`
- [ ] Configure TMC5160 current/microsteps/mode via Trinamic plugin settings
- [ ] Test: `$X` to unlock, `G1 Y90 F1800` → base rotates 90°
- [ ] Test: `G1 Y90 Z-30 A70 F1800` → 3 arm joints move simultaneously
- [ ] Test: `G1 X175 F5000` → rail moves to center
- [ ] Test: `M280 P0 S90` → gripper servo moves to 90°
- [ ] Test E-STOP: `!` stops mid-move instantly
- [ ] Test status polling: `?` returns 7-axis MPos

## Phase 4: IK Setup
- [ ] Install ikpy on Pi: `pip3 install ikpy numpy`
- [ ] Measure physical arm link lengths (upper arm center-to-center)
- [ ] Create `armold.urdf` with scaled dimensions from FK simulator
- [ ] Validate FK: set joints to home [0, -30, 70, 50, 0, 0] → compare tool tip to physical
- [ ] Validate IK: give reachable target → solve → move arm → confirm position
- [ ] Test joint limit enforcement in solver
- [ ] Test unreachable target returns None (no movement, error to client)
- [ ] Benchmark IK solve time on Pi (target: <50ms)

## Phase 5: armold_controller Refactor
- [ ] Replace multi-board serial code with single GrblBoard class
- [ ] Implement MotionManager with jog_joint, jog_rail, move_cartesian, home_rail, home_arm
- [ ] Add gripper command handler (M280 pass-through)
- [ ] Add GRBL status polling (2Hz `?`), broadcast 7-axis position to WebSocket clients
- [ ] Add E-STOP handler: sends `!` immediately
- [ ] Add speed profile: map Slow/Medium/Fast to feed rates
- [ ] Add sequence_to_gcode converter (simulator JSON → G-code with Y-U axes)
- [ ] Implement startup sequence: unlock → home rail → center → set arm zero → enable soft limits (EC3)
- [ ] Implement USB disconnect detection and auto-reconnect with motion stop (EC6)
- [ ] Validate 7-axis MPos length in status parser, log/skip malformed responses (EC8)
- [ ] After E-STOP, always re-query `?` before allowing new commands (EC7)
- [ ] Send rail and arm moves as separate G-code by default (EC2 mixed units)
- [ ] Update config.json: single board, `/dev/armold_motion`, 115200
- [ ] Update armold.service: remove multi-board references
- [ ] Remove old Einsy/RAMPS udev rules
- [ ] Run unit tests, fix failures

## Phase 6: Web UI Update
- [ ] Rename joint axes in UI to match new mapping (J0–J5 → Y,Z,A,B,C,U)
- [ ] Add linear rail panel: position display, jog ±10mm/±50mm, home button
- [ ] Add gripper control: slider (0–180°) or open/close buttons
- [ ] Add Cartesian jog panel (±1mm, ±10mm, ±100mm per XYZ)
- [ ] Add mode toggle (Joint / Cartesian)
- [ ] Display end-effector position (from FK calculation)
- [ ] Update E-STOP to send estop command
- [ ] Update speed toggle
- [ ] Test full UI workflow: connect → unlock → home rail → set arm home → jog → gripper

## Phase 7: Tuning + Validation
- [ ] Tune TMC5160 StallGuard4 for linear rail (X axis only)
- [ ] Run sensorless homing on rail: fast approach + slow verify + center at 175mm
- [ ] Verify arm "set home" works: jog to known pose → `G10 L20 P1 Y0 Z0 A0 B0 C0 U0`
- [ ] Run 1-hour IK demo stress test (no crashes, no desyncs)
- [ ] Test USB unplug/replug recovery
- [ ] Test E-STOP latency (<10ms)
- [ ] Verify Cartesian accuracy: command → measure → compare
- [ ] Test `$DFU` remote flash workflow (no BOOT0 button)
- [ ] Document final grblHAL `$$` settings in docs/

## Phase 8: Simulator Integration (Armold_FK_v1)
- [ ] Run simulator locally: `npm install && npm run dev` in Armold_FK_v1/
- [ ] Validate FK output matches ikpy at home pose [0, -30, 70, 50, 0, 0]
- [ ] Calibrate URDF link lengths from physical measurement (SCALE factor)
- [ ] Create `scripts/sequence_to_gcode.py` (converts simulator JSON → 7-axis G-code)
- [ ] Export demo sequence from simulator, convert, verify G-code output
- [ ] Test end-to-end: sequence JSON → G-code → armold_controller → physical arm
- [ ] Add "Send to Arm" button in simulator (POST sequence to Pi WebSocket)
- [ ] Add live position feedback: daemon → WebSocket → simulator 3D display
- [ ] Build simulator for production: `npm run build`
- [ ] Deploy dist/ to Pi, serve at `/simulator/` from armold_controller

## Phase 9: Finalize
- [ ] Remove Einsy + RAMPS hardware physically
- [ ] Update docs/btt-octopus-grblhal-flash.md with 7-axis local build instructions
- [ ] Update steering files with final architecture
- [ ] Update README with new hardware stack
- [ ] Commit all changes to main
