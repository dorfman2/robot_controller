# Klipper Migration — Requirements

## Goal
Replace grblHAL with Klipper firmware on the BTT Octopus MAX EZ. Klipper is proven to work on all 10 motor slots of this exact board. The Pi runs Klipper's host software which handles motion planning, while the MCU (STM32H723) acts as a real-time step pulse generator. This solves the Motor-7/8 pin issue we hit with grblHAL.

## Why Switch
- grblHAL board map only reliably drives Motor-1 through Motor-6 on this board
- Motor-7 (PD3/PD2/PD4) and Motor-8 (PA10/PA9/PA15) don't produce physical motor movement despite correct pin definitions
- Klipper has a community-maintained config for the BTT Octopus MAX EZ with all 10 motor slots defined and proven working
- Klipper handles TMC5160 SPI natively (grblHAL's Trinamic plugin couldn't communicate on this board)
- Klipper runs the motion planner on the Pi (more CPU power for trajectory planning, IK integration)

## Architecture

```
Browser (Web UI)
    ↕ WebSocket (port 9090)
Raspberry Pi 4
    ├── Klipper Host (klippy) — motion planning, G-code parsing, TMC driver config
    ├── armold_controller daemon — IK solver, web UI, WebSocket, pick planner
    ├── Klipper API (Unix socket) — send G-code, read position
    └── Vision pipeline (OAK-1 Lite, future)
            ↕ USB-C (/dev/armold_motion)
BTT Octopus MAX EZ (Klipper MCU firmware)
    ├── Real-time step pulse generation (all 10 motor slots available)
    ├── TMC5160 SPI configuration (native, proven on this board)
    ├── Endstop/probe pin reading
    └── PWM output (gripper servo)
            ↕ STEP/DIR
EZ5160 × 7 → NEMA 17 × 7 → Joints + Rail
```

## Key Difference from grblHAL
- **grblHAL**: MCU does everything (G-code parsing, motion planning, step generation)
- **Klipper**: Pi does G-code parsing + motion planning, MCU only generates step pulses at precise timing
- **Interface**: armold_controller talks to Klipper via its API (Unix socket or virtual serial), NOT directly to the MCU

## 7-Axis Mapping (Unchanged)

| Motor Slot | Klipper Stepper | Joint | Purpose |
|------------|-----------------|-------|---------|
| Motor-1 | stepper_x | — | Linear rail (80 steps/mm) |
| Motor-2 | stepper_y | J0 | Base yaw (230.6 steps/°) |
| Motor-3 | stepper_z | J1 | Shoulder pitch (230.6 steps/°) |
| Motor-4 | stepper_a | J2 | Elbow pitch (230.6 steps/°) |
| Motor-5 | stepper_b | J3 | Wrist pitch (230.6 steps/°) |
| Motor-6 | stepper_c | J4 | Wrist roll (230.6 steps/°) |
| Motor-7 | stepper_u | J5 | Wrist yaw (8.889 steps/°, direct drive) |

## Requirements

### R1: Klipper MCU Firmware
- Compile Klipper for STM32H723 with 128KiB bootloader, 25MHz crystal, USB (PA11/PA12)
- Flash via DFU (board already in known state, `$DFU` won't work from grblHAL after switch — use BOOT0)
- Verify Klipper MCU connects: `ls /dev/serial/by-id/usb-Klipper*`

### R2: Klipper Host (klippy)
- Install Klipper on Pi (klippy Python service)
- Install Moonraker (API server — exposes Klipper over HTTP/WebSocket)
- Do NOT install Mainsail/Fluidd (we have our own web UI)
- Klipper service managed by systemd

### R3: Printer Configuration (printer.cfg)
- Define all 7 steppers with correct pins from BTT Octopus MAX EZ reference config
- Define TMC5160 SPI for all 7 drivers (cs_pin, spi_bus: spi4, run_current: 1.2A)
- Define PWM servo output for gripper (pin PA1)
- Use `[manual_stepper]` for all axes (robot arm, not Cartesian printer)
- Set rotation_distance based on steps/unit (rail: mm, joints: degrees)
- Endstop only on X (rail StallGuard) — other axes use manual homing

### R4: armold_controller Integration
- Replace GrblBoard class with KlipperBoard class
- Communicate via Moonraker API (HTTP POST G-code, WebSocket for status)
- Or use Klipper's virtual serial port (`/tmp/printer`) for G-code streaming
- Position polling: subscribe to Moonraker WebSocket for toolhead position updates
- E-STOP: Moonraker `POST /printer/emergency_stop`
- Gripper: `SET_SERVO SERVO=gripper ANGLE=<0-180>` (Klipper native)

### R5: TMC5160 Configuration
- All 7 drivers configured via Klipper's native TMC5160 support
- SPI bus: spi4 (hardware, shared with SD card — SD card not used)
- run_current: 1.2A (arm joints), adjustable per stepper
- stealthchop_threshold: 0 (SpreadCycle always — dynamic torque)
- StallGuard: enabled on stepper_x only (linear rail homing)

### R6: Homing
- Linear rail (stepper_x): sensorless homing via TMC5160 StallGuard
- Arm joints: `SET_KINEMATIC_POSITION` to define current position as zero (manual home)
- No physical limit switches on arm joints

### R7: Gripper Servo
- Type: 9g metal gear servo, 180° range, 5V operating voltage, 3-wire (signal/VCC/GND)
- Klipper `[servo gripper]` section with pin PA1 (FAN4 header on Octopus MAX EZ)
- Signal wire: PA1 (3.3V logic from MCU, within servo input spec)
- Power: separate 5V BEC from 24V rail (board 5V can't supply stall current ~1A)
- GND: shared between BEC and board (common ground)
- Commands: `SET_SERVO SERVO=gripper ANGLE=90`
- Mapped to WebSocket command `{"cmd": "gripper", "angle": 90}`
- S0 = closed, S180 = fully open (calibrate per physical gripper geometry)

### R8: Web UI (Keep Existing)
- armold_controller continues to serve the web UI on port 9090
- All WebSocket commands stay the same (jog, estop, gripper, etc.)
- Backend switches from direct serial to Moonraker API
- User experience unchanged

### R9: E-STOP
- Moonraker API: `POST /printer/emergency_stop`
- Klipper immediately halts all steppers
- To recover: `FIRMWARE_RESTART` via Moonraker API
- Web UI E-STOP button → WebSocket → daemon → Moonraker → MCU halt

## Success Criteria
- All 7 motors move independently (including Motor-7 slot)
- TMC5160 SPI communication works (no "could not communicate" errors)
- Position reporting accurate from Klipper toolhead status
- E-STOP halts all motors < 10ms
- Gripper servo responds to angle commands
- Linear rail sensorless homing works
- armold_controller web UI functions identically to before
- 1-hour stability test with no disconnects or position drift

## Hardware Changes
- None — same board, same wiring, same drivers
- Just reflash MCU firmware from grblHAL to Klipper
- J5 motor moves BACK to Motor-7 slot (PD3/PD2/PD4) — Klipper proven to work there

## Jumper Configuration — No Changes Required

| Jumper | Current Setting | Klipper Needs | Change? |
|--------|----------------|---------------|---------|
| VUSB | Bridged | Same (DFU flash) | No |
| Driver voltage | VBB (24V) | Same | No |
| DIAG Motor-1 | Installed | Same (StallGuard on X) | No |
| DIAG Motor-2–7 | Not installed | Same | No |
| E-STOP (PF13→GND) | Bridged | Optional (Klipper doesn't use this pin by default) | No |
| SPI/UART | None | Same (firmware-controlled) | No |

## Edge Cases and Mitigations

### EC1: Coordinated Multi-Axis Motion
`MANUAL_STEPPER ... MOVE=` commands execute sequentially (one axis at a time). A robot arm
NEEDS coordinated motion (move J0 + J1 + J2 simultaneously).
**Mitigation**: Klipper added `GCODE_AXIS` registration in May 2025. After
`MANUAL_STEPPER STEPPER=stepper_y GCODE_AXIS=Y`, standard `G1 Y90 Z30 A45` moves all
axes simultaneously with full motion planning. Use the Multi-Axis Framework (MAF) or
native axis registration at startup.

### EC2: DFU Flash Address with 128K Bootloader
With `128KiB bootloader` in Klipper menuconfig, firmware expects to live at `0x08020000`.
Flashing to wrong address = board won't boot.
**Mitigation**: Either:
- Flash to `0x08020000`: `dfu-util -a 0 -s 0x08020000:leave -D out/klipper.bin`
- Or compile without bootloader offset and flash to `0x08000000`
The BTT SD card bootloader lives in the first 128K — preserve it if you want SD card updates as backup.

### EC3: Klipper + armold_controller Port Conflict
Both services could try to own the serial port simultaneously.
**Mitigation**: armold_controller NEVER opens the serial port directly. It talks exclusively
to Moonraker (HTTP localhost:7125). Only klippy owns the MCU serial connection.

### EC4: Moonraker Required
Without Moonraker, armold_controller has no API to send commands.
**Mitigation**: Install Moonraker alongside Klipper. It wraps klippy's internal API into
HTTP/WebSocket endpoints. This is a hard dependency.

### EC5: rotation_distance for Degree-Based Axes
Klipper uses `rotation_distance` (distance per motor revolution), not steps/unit.
**Mitigation**:
- Geared joints: `rotation_distance = 360 / 25.95 = 13.87` (degrees per motor rev after gearbox)
- Direct drive (J5): `rotation_distance = 360` (1 motor rev = 360°)
- Rail (X): `rotation_distance = 40` (mm per rev, GT2 2mm pitch × 20 teeth)

### EC6: SPI4 Bus Shared with SD Card
TMC5160 SPI and the physical SD card slot share SPI4.
**Mitigation**: Don't use physical SD card. Klipper's `[virtual_sdcard]` reads from Pi
filesystem. No bus contention since SD card CS stays deasserted.

### EC7: Motor-7 Might Work in Klipper
grblHAL failed on Motor-7, but Klipper's MCU firmware is fundamentally different (receives
pre-computed step schedules, fires pins at exact timing). The pin definitions are in the
official Klipper config for this board.
**Mitigation**: Test Motor-7 first after flash. If it still fails (hardware issue), fall
back to Motor-8 (PA10/PA9/PA15) which is also in the reference config.

### EC8: Remote Firmware Updates (Katapult Bootloader)
grblHAL's `$DFU` command is gone after switching. With Katapult installed as a persistent
bootloader at `0x08000000`, all future Klipper updates are fully automated:
`python3 ~/katapult/scripts/flashtool.py -d /dev/serial/by-id/usb-Klipper... -f ~/klipper/out/klipper.bin`
Klipper tells MCU to reboot into Katapult, Katapult accepts new firmware over USB, MCU reboots
into new Klipper. No button press, no DFU mode, no USB re-enumeration.
**BOOT0 button only needed ONCE** (initial Katapult flash). Keep accessible for brick recovery.
> **⚠️ Reality (2026-07-31): this buttonless path does NOT work on the current Katapult build.**
> See EC11. Katapult installs and boots Klipper fine, but its flash-WRITE routine faults on this
> H723 version, so `flashtool.py` cannot deliver updates. Until resolved, the working update
> path is ROM DFU (BOOT0+RESET) + `dfu-util`.

### EC9: Klipper Version Requirement
`GCODE_AXIS` for manual_stepper was added May 2025. Older versions lack coordinated motion.
**Mitigation**: Install latest Klipper from git main branch. KIAUH pulls latest by default.
Verify after install: `MANUAL_STEPPER STEPPER=stepper_y GCODE_AXIS=Y` must not error.

### EC10: E-STOP Latency via Moonraker
Path: armold_controller → HTTP POST → Moonraker → klippy → MCU. More hops than grblHAL's
single `!` byte over direct serial.
**Mitigation**: Still < 50ms total (all localhost). For time-critical safety, wire a physical
E-STOP button directly to an MCU input pin (Klipper handles it in firmware). Or write to
klippy's Unix socket (`/tmp/printer`) for lower latency than HTTP.

### EC11: Katapult H723 Flash-Write Regression (discovered 2026-07-31)
Katapult `v0.0.1-113-gec59b9b` installs and boots correctly on the Octopus MAX EZ (STM32H723),
but its MCU-side flash-WRITE routine faults during the 128KiB app-sector erase: `flashtool.py`
connects, reports `Application Start: 0x8020000`, then fails on the first block with
`Error sending command [SEND_BLOCK] to Device` / `Flash write failed, flash address 0x8020000`,
and the board drops off USB (MCU fault — not merely a client timeout; our flashtool already has
the Jul-2025 timeout increase). Matches upstream issue #128 (STM32H723). The community-cited
"good" commit `3e23332` (Feb 2024) predates Katapult's H7 flash support (`88e208a`), so it is
not a valid downgrade target here.
**Impact**: Buttonless updates via Katapult (EC8) are unavailable on this build.
**Mitigation (in effect)**: Flash Klipper via ROM DFU to the app offset, preserving Katapult:
`sudo dfu-util -a 0 -s 0x08020000:leave -D ~/klipper/out/klipper.bin` (dfu-util erases the target
sector first, so partial bytes from a failed Katapult write are cleaned up). Katapult stays at
`0x08000000` as the boot/jump stage (that part works). Boot chain verified:
reset → Katapult → Klipper @0x8020000 → klippy `ready`.
**Decision (2026-07-31)**: accepted the ROM DFU workflow (one BOOT0+RESET per update) and dropped
the buttonless requirement. Not bisecting Katapult. See the Firmware Update Runbook in
`tasks.md` Phase 2. (If buttonless is ever revisited: bisect Katapult between `88e208a` H7-flash-add
and HEAD, candidates around `94e4255` "sync stm32h7 from Klipper".)
