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
- Klipper `[servo gripper]` section with pin PA1
- Commands: `SET_SERVO SERVO=gripper ANGLE=90`
- Mapped to WebSocket command `{"cmd": "gripper", "angle": 90}`

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
