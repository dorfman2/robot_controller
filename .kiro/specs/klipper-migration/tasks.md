# Klipper Migration — Tasks

## Phase 1: Klipper Host Install (Pi)
- [ ] Install Klipper via KIAUH (Klipper Installation And Update Helper): `git clone https://github.com/dw-0/kiauh.git && ./kiauh/kiauh.sh`
- [ ] Install Klipper (klippy service)
- [ ] Install Moonraker (API server)
- [ ] Skip Mainsail/Fluidd (we have our own web UI)
- [ ] Verify klippy and moonraker systemd services running

## Phase 2: Klipper MCU Firmware (Flash Board)
- [ ] Compile Klipper MCU firmware: `cd ~/klipper && make menuconfig` (STM32H723, 128KiB bootloader, 25MHz, USB PA11/PA12)
- [ ] Run `make` to build `klipper.bin`
- [ ] Put board in DFU mode (BOOT0 + RESET — grblHAL `$DFU` won't work after first flash)
- [ ] Flash: `make flash FLASH_DEVICE=0483:df11` (or `dfu-util -a 0 -s 0x08020000:leave -D out/klipper.bin`)
- [ ] Verify MCU shows up: `ls /dev/serial/by-id/usb-Klipper*`
- [ ] Record serial ID for printer.cfg

## Phase 3: Printer Configuration
- [ ] Create `~/printer_data/config/printer.cfg` with 7 manual steppers
- [ ] Configure stepper_x (Motor-1, rail): step_pin PC13, dir_pin PC14, enable_pin !PE6, 80 steps/mm
- [ ] Configure stepper_y (Motor-2, J0): step_pin PE4, dir_pin PE5, enable_pin !PE3, 230.6 steps/°
- [ ] Configure stepper_z (Motor-3, J1): step_pin PE1, dir_pin PE0, enable_pin !PE2, 230.6 steps/°
- [ ] Configure stepper_a (Motor-4, J2): step_pin PB8, dir_pin PB9, enable_pin !PB7, 230.6 steps/°
- [ ] Configure stepper_b (Motor-5, J3): step_pin PB5, dir_pin PB4, enable_pin !PB6, 230.6 steps/°
- [ ] Configure stepper_c (Motor-6, J4): step_pin PG15, dir_pin PB3, enable_pin !PD5, 230.6 steps/°
- [ ] Configure stepper_u (Motor-7, J5): step_pin PD3, dir_pin PD2, enable_pin !PD4, 8.889 steps/° (direct drive)
- [ ] Configure TMC5160 SPI for all 7 steppers (cs_pins, spi_bus: spi4, run_current: 1.2)
- [ ] Configure `[servo gripper]` on pin PA1
- [ ] Configure `[virtual_sdcard]` path
- [ ] Set MCU serial path in printer.cfg
- [ ] Restart Klipper, verify "Ready" state

## Phase 4: Motor Testing
- [ ] Move J5 motor back to Motor-7 slot
- [ ] Test stepper_x (rail): `MANUAL_STEPPER STEPPER=stepper_x MOVE=50 SPEED=50`
- [ ] Test stepper_y (J0): `MANUAL_STEPPER STEPPER=stepper_y MOVE=30 SPEED=10`
- [ ] Test stepper_z (J1): `MANUAL_STEPPER STEPPER=stepper_z MOVE=30 SPEED=10`
- [ ] Test stepper_a (J2): `MANUAL_STEPPER STEPPER=stepper_a MOVE=30 SPEED=10`
- [ ] Test stepper_b (J3): `MANUAL_STEPPER STEPPER=stepper_b MOVE=30 SPEED=10`
- [ ] Test stepper_c (J4): `MANUAL_STEPPER STEPPER=stepper_c MOVE=30 SPEED=10`
- [ ] Test stepper_u (J5): `MANUAL_STEPPER STEPPER=stepper_u MOVE=90 SPEED=10`
- [ ] Verify TMC5160 SPI communication: `DUMP_TMC STEPPER=stepper_x`
- [ ] Test gripper: `SET_SERVO SERVO=gripper ANGLE=90`
- [ ] Test E-STOP via Moonraker API
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
