# Klipper Migration — Tasks

## Phase 1: Klipper Host Install (Pi)
- [x] Install Klipper via KIAUH (Klipper Installation And Update Helper): `git clone https://github.com/dw-0/kiauh.git && ./kiauh/kiauh.sh`
- [x] Install Klipper (klippy service)
- [x] Install Moonraker (API server)
- [x] Skip Mainsail/Fluidd (we have our own web UI)
- [x] Verify klippy and moonraker systemd services running

## Phase 2: Katapult Bootloader + Klipper MCU Firmware (Flash Board)
> **Outcome (2026-07-31):** Katapult is installed and boots Klipper correctly. Klipper had to be
> flashed via ROM DFU (not via Katapult) because Katapult's flash-WRITE routine faults on this
> H723 build (see EC11 / issue #128). Buttonless-update-via-Katapult was NOT achieved; the reliable
> update path remains ROM DFU (BOOT0+RESET) + `dfu-util`.

- [x] Clone Katapult: `git clone https://github.com/Arksine/katapult.git ~/katapult` (already cloned, v0.0.1-113-gec59b9b)
- [x] Configure Katapult for **STM32H723** — regenerated `.config` via `make olddefconfig` (prior attempt was mis-built for stm32f103xe — root cause of the original failure): MACH_STM32H723, `STM32_FLASH_START_20000` (128KiB → app @0x8020000), 25MHz crystal, USB PA11/PA12, USBSERIAL, `ENABLE_DOUBLE_RESET`
- [x] Build Katapult: `make` → `out/katapult.bin` (5668 B); ELF verified `.text`@0x08000000
- [x] Put board in DFU mode (BOOT0 + RESET) → ROM DFU `0483:df11`
- [x] Flash Katapult to 0x08000000: `sudo dfu-util -a 0 -s 0x08000000:mass-erase:force:leave -D out/katapult.bin` (**`mass-erase` requires the `:force` modifier**; the `Error during download get_status` on `:leave` is benign)
- [x] Verify Katapult running: enumerated as `1d50:6177` / `usb-katapult_stm32h723xx_380009001151313531383332-if00`
- [x] Compile Klipper MCU firmware for **128KiB bootloader**: flipped `CONFIG_STM32_FLASH_START_0000` → `_20000` (app @0x8020000); kept 520MHz, 25MHz ref, USB, VID/PID 1d50:614e
- [x] Build Klipper: `make` → `out/klipper.bin` (44428 B); ELF verified `.text`@0x08020000
- [~] ~~Flash Klipper via Katapult (no button!)~~ — **FAILED**: `flashtool.py` connects to Katapult but `SEND_BLOCK` faults the MCU during the 128KiB app-sector erase (Katapult drops off USB). Known Katapult H723 flash regression (issue #128). Community fix commit `3e23332` predates H7 flash support, so not usable here.
- [x] Flash Klipper via **ROM DFU** instead (Option A, preserves Katapult @0x08000000): `sudo dfu-util -a 0 -s 0x08020000:leave -D out/klipper.bin`
- [x] Verify Klipper MCU shows up: `1d50:614e` / `usb-Klipper_stm32h723xx_380009001151313531383332-if00`
- [x] Record serial ID for printer.cfg: `usb-Klipper_stm32h723xx_380009001151313531383332-if00` (unchanged — no printer.cfg edit needed)
- [x] Verify boot chain: reset → Katapult → Klipper @0x8020000 → Moonraker `/printer/info` reports `state: ready`
- [x] **Buttonless updates — DECIDED (2026-07-31): keep the ROM DFU workflow.** Not pursuing the Katapult flash-write fix. Firmware updates use BOOT0+RESET → ROM DFU → `dfu-util` (runbook below). Katapult stays installed as the boot/jump stage.

### Firmware Update Runbook (ROM DFU — sanctioned method)
```bash
# On the Pi. Rebuild Klipper if needed (must keep 128KiB offset):
cd ~/klipper && make            # -> out/klipper.bin, linked @0x08020000
sudo systemctl stop klipper     # release the serial port
# Put board in ROM DFU: hold BOOT0, tap RESET, release BOOT0  (verify: lsusb | grep 0483:df11)
sudo dfu-util -a 0 -s 0x08020000:leave -D ~/klipper/out/klipper.bin
# (benign 'Error during download get_status' on :leave = board reset)
sudo systemctl start klipper
curl -s http://localhost:7125/printer/info   # expect state: ready
```
> Flash Klipper to **0x08020000** (NOT 0x08000000) so Katapult at 0x08000000 is preserved.

## Phase 3: Printer Configuration
- [x] Create `~/printer_data/config/printer.cfg` with 7 manual steppers
- [x] Configure stepper_x (Motor-1, rail): step_pin PC13, dir_pin PC14, enable_pin !PE6, rotation_distance=40
- [x] Configure stepper_y (Motor-2, J0): step_pin PE4, dir_pin PE5, enable_pin !PE3, rotation_distance=13.87
- [x] Configure stepper_z (Motor-3, J1): step_pin PE1, dir_pin PE0, enable_pin !PE2, rotation_distance=13.87
- [x] Configure stepper_a (Motor-4, J2): step_pin PB8, dir_pin PB9, enable_pin !PB7, rotation_distance=13.87
- [x] Configure stepper_b (Motor-5, J3): step_pin PB5, dir_pin PB4, enable_pin !PB6, rotation_distance=13.87
- [x] Configure stepper_c (Motor-6, J4): step_pin PG15, dir_pin PB3, enable_pin !PD5, rotation_distance=13.87
- [x] Configure stepper_u (Motor-7, J5): step_pin PD3, dir_pin PD2, enable_pin !PD4, rotation_distance=360 (direct drive)
- [x] Configure TMC5160 SPI for all 7 steppers (cs_pins, spi_bus: spi4, run_current: 1.2)
- [x] Configure `[servo gripper]` on pin PA1 (signal only — 5V power from separate BEC, shared GND)
- [x] Configure `[virtual_sdcard]` path
- [x] Add `REGISTER_AXES` startup macro (GCODE_AXIS registration for coordinated motion — EC1)
- [x] Add `SET_ARM_HOME` macro (sets all stepper positions to zero)
- [x] Set MCU serial path in printer.cfg
- [x] Verify Klipper version supports `GCODE_AXIS` (May 2025+ required — EC9)
- [x] Restart Klipper, verify "Ready" state

## Phase 4: Motor Testing  ✅ ALL PASS (2026-07-31)
> Verified live over Moonraker (`POST /printer/gcode/script`), user watching the arm. Individual
> joints tested via `MANUAL_STEPPER` (bidirectional sweep + return to zero); coordinated motion via
> `REGISTER_AXES` + `G1`. Correct axis letters are **W A B C D H U** (NOT X/Y/Z — reserved). Correct
> `DUMP_TMC` name is bare (e.g. `stepper_x`), not `manual_stepper stepper_x`.

- [x] J5 confirmed in Motor-7 slot (`PD3/PD2/PD4`)
- [x] Verify TMC5160 SPI: `DUMP_TMC STEPPER=stepper_x` → full register read (IOIN version=0x30, CHOPCONF 16usteps). All 7 init'd (klippy Ready).
- [x] Test each stepper individually (`MANUAL_STEPPER STEPPER=<n> SET_POSITION=0` then `MOVE=±N SPEED=n`) — all moved **both directions** + returned:
  - [x] stepper_x (rail, mm) · stepper_y (J0 base) · stepper_z (J1 shoulder) · stepper_a (J2 elbow) · stepper_b (J3 wrist pitch, 1.2A) · stepper_c (J4 wrist roll)
  - [x] **stepper_u (J5 wrist yaw, Motor-7)** — WORKS under Klipper (this is the slot that never moved under grblHAL) → Motor-8 fallback (EC7) NOT needed
- [x] `REGISTER_AXES` — all 7 GCODE_AXIS letters registered cleanly (W A B C D H U). The older "only A/B/C/U work" note was wrong; the real rule is just avoid Klipper-reserved letters (X Y Z E F N).
- [x] Coordinated motion: `G90` + `G1 A20 H15 U25 F900` → base/roll/yaw moved **simultaneously** and arrived together; returned to 0 (EC1 satisfied for rotary joints)
  - Caveat: do NOT mix the rail (`W`, mm) with degree axes in one `G1` — `F` becomes a blended mm+deg vector → unpredictable speed. Command the rail separately.
- [x] Test gripper: `SET_SERVO SERVO=gripper ANGLE=n` — **60° = OPEN, 120° = CLOSED**, clean travel
- [x] Test E-STOP: `POST /printer/emergency_stop` → klippy `shutdown`; recover via `POST /printer/firmware_restart` → `ready` (EC10). Note: firmware_restart clears GCODE_AXIS regs → re-run `REGISTER_AXES`.
- [x] All 7 motors + gripper physically verified
- [x] Added `[fan_generic motor_fan]` on **PF8** (FAN5) for board/motor cooling — PA1/FAN4 was unavailable (gripper servo). Control: `SET_FAN_SPEED FAN=motor_fan SPEED=0..1`. (First fan unit was DOA; replaced.)

## Phase 5: armold_controller Refactor
- [x] Create `armold_controller/klipper_board.py` — Moonraker API client
- [x] Implement: send_gcode(), query_status(), estop(), set_gripper()
- [x] Implement: position polling via Moonraker WebSocket subscription
- [x] Replace GrblBoard references with KlipperBoard
- [x] Map joint jog commands to `MANUAL_STEPPER` G-code
- [x] Map IK output to manual stepper moves
- [x] Test web UI: jog, estop, gripper all working through Klipper
- [x] Update systemd service (ensure klippy starts before armold_controller)

## Phase 6: Homing + Limits
> **Outcome (2026-08-01):** Soft limits implemented in `armold_controller`. StallGuard sensorless
> homing **abandoned** on the rail (belt skips before the motor stalls — no usable `SGT` window);
> **manual homing** adopted instead. Two incidental config fixes made along the way (both keepers).

- [~] ~~Configure sensorless homing for stepper_x (TMC5160 StallGuard)~~ — configured and tuned
  extensively, then **abandoned**. Config left in place but dormant. Findings:
  - `diag1_pin: ^!PF0` required (pull-up + invert); bare `PF0` read TRIGGERED at rest and blocked the move.
  - Config **ordering** matters: `[tmc5160 manual_stepper stepper_x]` must appear **before**
    `[manual_stepper stepper_x]` (manual_stepper resolves `endstop_pin` at init, before the tmc
    section registers the `tmc5160_stepper_x:virtual_endstop` chip → "Unknown pin chip name").
  - `SGT` scan (TMC5160: −64 = most sensitive, +63 = least) at 15 and 40 mm/s: `sgt ≤ 11` trips
    **early** (free-motion signal), `sgt ≥ 12` **belt-skips** with no trigger. **No usable window** —
    the belt slips before the rotor stalls, so StallGuard never sees a distinct load spike.
  - Two spurious MCU USB disconnects occurred during tuning (recovered via `firmware_restart`).
- [x] **`dir_pin: !PC14`** (FIX) — rail direction was inverted; now negative = home.
- [x] **`sense_resistor: 0.050`** (FIX) — was omitted, so Klipper used its 0.075 default while the
  EZ5160 is a 50 mΩ driver → actual current was ~1.5× labeled. Now correctly 0.8 A at `run_current: 0.800`.
- [x] **Manual rail homing** adopted: `RELEASE_RAIL` (de-energize) → push carriage to home end →
  `SET_RAIL_HOME` (`SET_POSITION=0`). Rail homed at 0.
- [x] Arm "set home": existing `SET_ARM_HOME` macro zeros all joints (`MANUAL_STEPPER SET_POSITION=0`).
- [x] **Soft limits in `armold_controller`** (`klipper_board.py`): `JointLimit` dataclass +
  `DEFAULT_SOFT_LIMITS` (rail 0–406 mm; J0 ±180, J1 ±90, J2 ±150, J3 ±120, J4 ±90, J5 ±180);
  `clamp_target()` applied in `jog_joint`/`move_coordinated` with warning logs; also fixed jog to be
  properly relative. 8 new unit tests (no mocks) pass. **Not yet deployed to Pi** (see below).
- [x] Deploy `armold_controller` to Pi + integration-test — deployed to `/home/pi/armold-venv`,
  runs via `armold.service` (WS 9090); soft limits + jog/move/move_cartesian validated live on
  hardware across subsequent sessions.

## Phase 7: Validation  ✅ (2026-08-01, 1-hour soak deferred)
- [x] Verify TMC5160 current/temp via `DUMP_TMC` — found sense_resistor missing (Klipper 0.075 default vs EZ5160's 50mOhm → ~1.5× over-current). **Fixed: `sense_resistor: 0.050` on all 7.** GLOBALSCALER now uniform (45 @0.8A, 67 @J3 1.2A). No `otpw`/`ot` flags.
- [x] **Per-joint current tuned** (all at 0.050 sense): rail(x) 0.8/0.3 · base(y) 0.8/0.3 · **shoulder(z) 1.0/1.0** · elbow(a) 0.9/0.3 · J3 pitch(b) 1.2/0.75 · roll(c) 0.8/0.3 · yaw(u) 0.8/0.3. Shoulder needed 1.0 A run+hold to lift the fully-extended arm (0.8 A stalled); validated smooth ±50° from vertical.
- [x] Run all 7 motors simultaneously — concurrent `MANUAL_STEPPER SYNC=0` at 30°/20 mm, all 7 confirmed moving together, no faults.
- [x] Verify position accuracy: base commanded 90° → measured ~90° physical → **calibration confirmed** (`rotation_distance: 13.87`, 230.6 steps/°).
- [x] Test USB disconnect/reconnect recovery — unplug → klippy `shutdown`; MCU re-enumerates (stable by-id path); `FIRMWARE_RESTART` → `ready` (often needs 2 attempts); daemon auto-reconnects (WS 9090). **Recovery is not hands-off** — see follow-up.
- [x] Document final printer.cfg — copied to `pi/printer.cfg` (version-controlled reference).
- [x] Update steering files with Klipper architecture — system-patterns.md / active-context.md updated.
- [ ] (Deferred) 1-hour continuous operation test.
- [ ] (Follow-up) Watchdog to auto-issue `FIRMWARE_RESTART` on MCU shutdown for unattended recovery.
- [ ] (Follow-up) Loaded test for elbow (J2 @0.9 A) and consider raising hold current on other lift joints (only shoulder is at high hold).
