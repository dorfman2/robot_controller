# Klipper Migration — Tasks

## Phase 1: Klipper Host Install (Pi)
- [x] Install Klipper via KIAUH (Klipper Installation And Update Helper): `git clone https://github.com/dw-0/kiauh.git && ./kiauh/kiauh.sh`
- [x] Install Klipper (klippy service)
- [x] Install Moonraker (API server)
- [x] Skip Mainsail/Fluidd (we have our own web UI)
- [x] Verify klippy and moonraker systemd services running

## Phase 2: Katapult Bootloader + Klipper MCU Firmware (Flash Board)
- [ ] Clone Katapult: `git clone https://github.com/Arksine/katapult.git ~/katapult`
- [ ] Configure Katapult: `cd ~/katapult && make menuconfig` (STM32H723, 128KiB offset, 25MHz, USB on PA11/PA12, "Support bootloader entry on rapid double click of reset button")
- [ ] Build Katapult: `make`
- [ ] Put board in DFU mode (BOOT0 + RESET) — **LAST TIME you'll need the button**
- [ ] Flash Katapult to 0x08000000: `sudo dfu-util -a 0 -s 0x08000000:leave -D out/katapult.bin`
- [ ] Verify Katapult running: `ls /dev/serial/by-id/usb-katapult*` (LED should blink)
- [ ] Compile Klipper MCU firmware: `cd ~/klipper && make menuconfig` (STM32H723, 128KiB bootloader, 25MHz, USB PA11/PA12)
- [ ] Build Klipper: `make`
- [ ] Flash Klipper via Katapult (no button!): `python3 ~/katapult/scripts/flashtool.py -d /dev/serial/by-id/usb-katapult* -f ~/klipper/out/klipper.bin`
- [ ] Verify Klipper MCU shows up: `ls /dev/serial/by-id/usb-Klipper*`
- [ ] Record serial ID for printer.cfg
- [ ] Test future update workflow: `python3 ~/katapult/scripts/flashtool.py -d /dev/serial/by-id/usb-Klipper* -f ~/klipper/out/klipper.bin` (should work without any button press)

## Phase 3: Printer Configuration
- [ ] Create `~/printer_data/config/printer.cfg` with 7 manual steppers
- [ ] Configure stepper_x (Motor-1, rail): step_pin PC13, dir_pin PC14, enable_pin !PE6, rotation_distance=40
- [ ] Configure stepper_y (Motor-2, J0): step_pin PE4, dir_pin PE5, enable_pin !PE3, rotation_distance=13.87
- [ ] Configure stepper_z (Motor-3, J1): step_pin PE1, dir_pin PE0, enable_pin !PE2, rotation_distance=13.87
- [ ] Configure stepper_a (Motor-4, J2): step_pin PB8, dir_pin PB9, enable_pin !PB7, rotation_distance=13.87
- [ ] Configure stepper_b (Motor-5, J3): step_pin PB5, dir_pin PB4, enable_pin !PB6, rotation_distance=13.87
- [ ] Configure stepper_c (Motor-6, J4): step_pin PG15, dir_pin PB3, enable_pin !PD5, rotation_distance=13.87
- [ ] Configure stepper_u (Motor-7, J5): step_pin PD3, dir_pin PD2, enable_pin !PD4, rotation_distance=360 (direct drive)
- [ ] Configure TMC5160 SPI for all 7 steppers (cs_pins, spi_bus: spi4, run_current: 1.2)
- [ ] Configure `[servo gripper]` on pin PA1
- [ ] Configure `[virtual_sdcard]` path
- [ ] Add `REGISTER_AXES` startup macro (GCODE_AXIS registration for coordinated motion — EC1)
- [ ] Add `SET_ARM_HOME` macro (sets all stepper positions to zero)
- [ ] Set MCU serial path in printer.cfg
- [ ] Verify Klipper version supports `GCODE_AXIS` (May 2025+ required — EC9)
- [ ] Restart Klipper, verify "Ready" state

## Phase 4: Motor Testing
- [ ] Move J5 motor back to Motor-7 slot
- [ ] Run `REGISTER_AXES` macro to enable coordinated G-code motion
- [ ] Test stepper_x (rail): `G1 X50 F3000` — verify rail moves 50mm
- [ ] Test stepper_y (J0): `G1 Y30 F600` — verify base rotates 30°
- [ ] Test stepper_z (J1): `G1 Z30 F600` — verify shoulder moves
- [ ] Test stepper_a (J2): `G1 A30 F600` — verify elbow moves
- [ ] Test stepper_b (J3): `G1 B30 F600` — verify wrist pitch moves
- [ ] Test stepper_c (J4): `G1 C30 F600` — verify wrist roll moves
- [ ] Test stepper_u (J5): `G1 U90 F600` — verify wrist yaw moves (Motor-7 slot!)
- [ ] If Motor-7 fails: move J5 to Motor-8 (PA10/PA9/PA15), update printer.cfg (EC7)
- [ ] Test coordinated motion: `G1 Y45 Z-30 A70 F1200` — all 3 joints move simultaneously (EC1)
- [ ] Verify TMC5160 SPI communication: `DUMP_TMC STEPPER=manual_stepper stepper_x`
- [ ] Test gripper: `SET_SERVO SERVO=gripper ANGLE=90`
- [ ] Test E-STOP via Moonraker: `POST /printer/emergency_stop` (EC10)
- [ ] Verify all 7 motors physically move

## Phase 5: armold_controller Refactor
- [ ] Create `armold_controller/klipper_board.py` — Moonraker API client
- [ ] Implement: send_gcode(), query_status(), estop(), set_gripper()
- [ ] Implement: position polling via Moonraker WebSocket subscription
- [ ] Replace GrblBoard references with KlipperBoard
- [ ] Map joint jog commands to `MANUAL_STEPPER` G-code
- [ ] Map IK output to manual stepper moves
- [ ] Test web UI: jog, estop, gripper all working through Klipper
- [ ] Update systemd service (ensure klippy starts before armold_controller)

## Phase 6: Homing + Limits
- [ ] Configure sensorless homing for stepper_x (TMC5160 StallGuard)
- [ ] Test rail homing: `MANUAL_STEPPER STEPPER=stepper_x SET_POSITION=0` after stall
- [ ] Implement arm "set home": `SET_KINEMATIC_POSITION X=0 Y=0 Z=0` equivalent
- [ ] Add soft limits in armold_controller (Klipper manual_stepper doesn't enforce them natively)

## Phase 7: Validation
- [ ] Run all 7 motors simultaneously
- [ ] Verify position accuracy: command 90° → measure physical → confirm
- [ ] Test USB disconnect/reconnect recovery
- [ ] Run 1-hour continuous operation test
- [ ] Verify TMC5160 current/temp via `DUMP_TMC`
- [ ] Document final printer.cfg
- [ ] Update steering files with Klipper architecture
