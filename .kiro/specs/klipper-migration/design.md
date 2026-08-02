# Klipper Migration — Design

#[[file:requirements.md]]

## How Klipper Works (vs grblHAL)

```
grblHAL approach:
    Pi → G-code → MCU (parses, plans, steps)

Klipper approach:
    Pi (klippy) → plans motion → sends precise step timing → MCU (just fires pins at exact times)
```

Klipper splits the work: the Pi's CPU handles all G-code parsing and motion planning (acceleration, cornering, lookahead). The MCU receives pre-computed step schedules and fires STEP/DIR pins with microsecond precision. This is why Klipper works reliably with all motor slots — the MCU firmware is generic and just needs correct pin definitions.

---

## Software Stack on Pi

```
┌─────────────────────────────────────────────────────────┐
│ Raspberry Pi 4                                          │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ armold_      │  │ Klipper      │  │ Moonraker    │ │
│  │ controller   │──│ (klippy)     │──│ (API server) │ │
│  │ (web UI,     │  │ (motion      │  │ (HTTP/WS)    │ │
│  │  IK, vision) │  │  planning)   │  │              │ │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘ │
│         │                  │                            │
│         │ Moonraker API    │ USB Serial                 │
│         │ (localhost:7125) │ (/dev/serial/by-id/...)    │
│         ▼                  ▼                            │
│                    ┌──────────────┐                     │
│                    │ BTT Octopus  │                     │
│                    │ MAX EZ (MCU) │                     │
│                    └──────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

---

## KlipperBoard Class

```python
import aiohttp
import asyncio
import json

class KlipperBoard:
    """Interface to Klipper via Moonraker API."""

    def __init__(self, moonraker_url: str = "http://localhost:7125"):
        self._url = moonraker_url
        self._session = None

    async def connect(self):
        self._session = aiohttp.ClientSession()

    async def send_gcode(self, cmd: str) -> bool:
        """Send G-code command via Moonraker."""
        async with self._session.post(
            f"{self._url}/printer/gcode/script",
            json={"script": cmd}
        ) as resp:
            return resp.status == 200

    async def estop(self):
        """Emergency stop — halts all steppers immediately."""
        async with self._session.post(
            f"{self._url}/printer/emergency_stop"
        ) as resp:
            return resp.status == 200

    async def firmware_restart(self):
        """Restart MCU after E-STOP."""
        async with self._session.post(
            f"{self._url}/printer/firmware_restart"
        ) as resp:
            return resp.status == 200

    async def query_status(self) -> dict:
        """Get current printer status including stepper positions."""
        async with self._session.get(
            f"{self._url}/printer/objects/query",
            params={"manual_stepper stepper_x": None,
                    "manual_stepper stepper_y": None,
                    "manual_stepper stepper_z": None,
                    "manual_stepper stepper_a": None,
                    "manual_stepper stepper_b": None,
                    "manual_stepper stepper_c": None,
                    "manual_stepper stepper_u": None}
        ) as resp:
            return await resp.json()

    async def set_gripper(self, angle: int):
        """Set gripper servo angle (0-180)."""
        angle = max(0, min(180, angle))
        await self.send_gcode(f"SET_SERVO SERVO=gripper ANGLE={angle}")

    async def jog_stepper(self, stepper: str, distance: float, speed: float):
        """Move a manual stepper by a relative distance."""
        await self.send_gcode(
            f"MANUAL_STEPPER STEPPER={stepper} MOVE={distance} SPEED={speed} ACCEL=300"
        )

    async def set_stepper_position(self, stepper: str, position: float = 0):
        """Set current position of a stepper (manual home)."""
        await self.send_gcode(
            f"MANUAL_STEPPER STEPPER={stepper} SET_POSITION={position}"
        )

    async def close(self):
        if self._session:
            await self._session.close()
```

---

## Klipper printer.cfg (Robot Arm)

```ini
[mcu]
serial: /dev/serial/by-id/usb-Klipper_stm32h723xx_XXXXXXXXXXXX-if00

[printer]
kinematics: none  # We use manual_stepper, not a standard kinematics model
max_velocity: 300
max_accel: 3000

# ============ STEPPERS ============

# Motor-1: Linear Rail (X)
[manual_stepper stepper_x]
step_pin: PC13
dir_pin: PC14
enable_pin: !PE6
microsteps: 16
rotation_distance: 40  # GT2 20T: 2mm pitch * 20 teeth = 40mm per rev
velocity: 80
accel: 500

# Motor-2: J0 Base (Y)
[manual_stepper stepper_y]
step_pin: PE4
dir_pin: PE5
enable_pin: !PE3
microsteps: 16
rotation_distance: 13.87  # 360° / 25.95 gear ratio = 13.87° per motor rev
velocity: 30
accel: 900

# Motor-3: J1 Shoulder (Z)
[manual_stepper stepper_z]
step_pin: PE1
dir_pin: PE0
enable_pin: !PE2
microsteps: 16
rotation_distance: 13.87
velocity: 30
accel: 900

# Motor-4: J2 Elbow (A)
[manual_stepper stepper_a]
step_pin: PB8
dir_pin: PB9
enable_pin: !PB7
microsteps: 16
rotation_distance: 13.87
velocity: 30
accel: 900

# Motor-5: J3 Wrist Pitch (B)
[manual_stepper stepper_b]
step_pin: PB5
dir_pin: PB4
enable_pin: !PB6
microsteps: 16
rotation_distance: 13.87
velocity: 30
accel: 900

# Motor-6: J4 Wrist Roll (C)
[manual_stepper stepper_c]
step_pin: PG15
dir_pin: PB3
enable_pin: !PD5
microsteps: 16
rotation_distance: 13.87
velocity: 30
accel: 900

# Motor-7: J5 Wrist Yaw (U) — DIRECT DRIVE, no gearbox
[manual_stepper stepper_u]
step_pin: PD3
dir_pin: PD2
enable_pin: !PD4
microsteps: 16
rotation_distance: 360  # Direct drive: 1 motor rev = 360°
velocity: 60
accel: 900

# ============ TMC5160 SPI ============

[tmc5160 manual_stepper stepper_x]
cs_pin: PG14
spi_bus: spi4
run_current: 1.200
stealthchop_threshold: 0

[tmc5160 manual_stepper stepper_y]
cs_pin: PG13
spi_bus: spi4
run_current: 1.200
stealthchop_threshold: 0

[tmc5160 manual_stepper stepper_z]
cs_pin: PG12
spi_bus: spi4
run_current: 1.200
stealthchop_threshold: 0

[tmc5160 manual_stepper stepper_a]
cs_pin: PG11
spi_bus: spi4
run_current: 1.200
stealthchop_threshold: 0

[tmc5160 manual_stepper stepper_b]
cs_pin: PG10
spi_bus: spi4
run_current: 1.200
stealthchop_threshold: 0

[tmc5160 manual_stepper stepper_c]
cs_pin: PG9
spi_bus: spi4
run_current: 1.200
stealthchop_threshold: 0

[tmc5160 manual_stepper stepper_u]
cs_pin: PD7
spi_bus: spi4
run_current: 1.200
stealthchop_threshold: 0

# ============ GRIPPER SERVO ============
# 9g metal gear servo, 180°, 5V
# Signal wire → PA1 (FAN4 header signal pin)
# Power → separate 5V BEC (NOT board 5V — stall current too high)
# GND → shared with board GND

[servo gripper]
pin: PA1
maximum_servo_angle: 180
minimum_pulse_width: 0.0005
maximum_pulse_width: 0.0025
# 0.5ms = 0°, 2.5ms = 180° (standard servo timing)

# ============ MISC ============

[virtual_sdcard]
path: ~/printer_data/gcodes

[pause_resume]

[gcode_macro SET_ARM_HOME]
description: Set all arm joints to zero (manual home)
gcode:
  MANUAL_STEPPER STEPPER=stepper_x SET_POSITION=0
  MANUAL_STEPPER STEPPER=stepper_y SET_POSITION=0
  MANUAL_STEPPER STEPPER=stepper_z SET_POSITION=0
  MANUAL_STEPPER STEPPER=stepper_a SET_POSITION=0
  MANUAL_STEPPER STEPPER=stepper_b SET_POSITION=0
  MANUAL_STEPPER STEPPER=stepper_c SET_POSITION=0
  MANUAL_STEPPER STEPPER=stepper_u SET_POSITION=0
```

---

## Motion Command Mapping

| armold_controller command | Klipper G-code |
|---------------------------|----------------|
| `jog(joint=0, delta=5)` | `MANUAL_STEPPER STEPPER=stepper_y MOVE=5 SPEED=10` |
| `jog_rail(delta=10)` | `MANUAL_STEPPER STEPPER=stepper_x MOVE=10 SPEED=50` |
| `gripper(angle=90)` | `SET_SERVO SERVO=gripper ANGLE=90` |
| `estop` | `POST /printer/emergency_stop` |
| `set_arm_home` | `SET_ARM_HOME` (macro) |
| `home_rail` | Sensorless homing sequence on stepper_x |

---

## Moonraker API Endpoints Used

| Action | Method | Endpoint |
|--------|--------|----------|
| Send G-code | POST | `/printer/gcode/script` |
| Emergency stop | POST | `/printer/emergency_stop` |
| Firmware restart | POST | `/printer/firmware_restart` |
| Query objects | GET | `/printer/objects/query?...` |
| Subscribe status | WebSocket | `/websocket` |
| Server info | GET | `/server/info` |

---

## Migration Steps Summary

1. Install Klipper + Moonraker on Pi (alongside armold_controller)
2. Build & flash Katapult bootloader via DFU (BOOT0 — **last time ever**)
3. Flash Klipper MCU via Katapult (no button needed)
4. Create printer.cfg with manual_stepper definitions
5. Register G-code axes at startup for coordinated motion (MAF / GCODE_AXIS)
6. Move J5 back to Motor-7 slot
7. Test all 7 motors via Moonraker API
8. Refactor armold_controller: GrblBoard → KlipperBoard
9. Web UI unchanged (commands route through Moonraker instead of direct serial)

---

## Flash Workflow (as-built, 2026-07-31)

> The original plan was buttonless updates via Katapult's `flashtool.py`. That path is broken on
> this Katapult build for the H723 (flash-write faults — see requirements EC11 / issue #128).
> **Sanctioned workflow: ROM DFU + `dfu-util`.** Katapult is installed at `0x08000000` and used
> only as the boot/jump stage (that works reliably).

### Initial Setup (one-time)
```bash
# 1. Build Katapult for H723 (verify CONFIG_MCU=stm32h723xx before building!)
cd ~/katapult && make olddefconfig && make    # -> out/katapult.bin (.text @0x08000000)

# 2. Enter ROM DFU (BOOT0 + RESET), then flash Katapult:
sudo dfu-util -a 0 -s 0x08000000:mass-erase:force:leave -D out/katapult.bin
#   note: mass-erase REQUIRES :force ; 'get_status' error on :leave is benign

# 3. Build Klipper with 128KiB bootloader offset (app @0x08020000):
cd ~/klipper && make                          # -> out/klipper.bin (.text @0x08020000)

# 4. Enter ROM DFU again, flash Klipper ABOVE Katapult:
sudo dfu-util -a 0 -s 0x08020000:leave -D out/klipper.bin
```

### Future Updates (ROM DFU — one BOOT0+RESET per update)
```bash
cd ~/klipper && make
sudo systemctl stop klipper
# Enter ROM DFU: hold BOOT0, tap RESET, release BOOT0  (verify: lsusb | grep 0483:df11)
sudo dfu-util -a 0 -s 0x08020000:leave -D out/klipper.bin
sudo systemctl start klipper
curl -s http://localhost:7125/printer/info    # expect state: ready
```

### Memory Layout
```
0x08000000 ┌──────────────────┐
           │  Katapult (~6KB)  │ ← boot/jump stage (flash-write broken on this build; EC11)
0x08020000 ├──────────────────┤
           │  Klipper MCU      │ ← application firmware; flash here via ROM DFU (0x08020000)
           │  (~44KB)          │
0x08040000 └──────────────────┘   (Klipper occupies the 0x08020000 128KiB sector)
```

---

## Coordinated Multi-Axis Motion (Critical)

Plain `MANUAL_STEPPER` commands move one axis at a time. For a robot arm, we need
simultaneous coordinated motion. Klipper (May 2025+) supports this via `GCODE_AXIS`:

```ini
# In printer.cfg or startup macro — register axes for G-code control
[gcode_macro REGISTER_AXES]
description: Register manual steppers as G-code axes for coordinated motion
gcode:
  MANUAL_STEPPER STEPPER=stepper_x GCODE_AXIS=X
  MANUAL_STEPPER STEPPER=stepper_y GCODE_AXIS=Y
  MANUAL_STEPPER STEPPER=stepper_z GCODE_AXIS=Z
  MANUAL_STEPPER STEPPER=stepper_a GCODE_AXIS=A
  MANUAL_STEPPER STEPPER=stepper_b GCODE_AXIS=B
  MANUAL_STEPPER STEPPER=stepper_c GCODE_AXIS=C
  MANUAL_STEPPER STEPPER=stepper_u GCODE_AXIS=U
```

After running `REGISTER_AXES`, standard G-code works:

```gcode
; Coordinated move — all joints move simultaneously
G1 Y90 Z-30 A70 B50 F1800

; Rail + arm simultaneous
G1 X175 Y45 F1800

; This is identical to how grblHAL worked — the armold_controller code stays the same!
```

This means the axis letter mapping and G-code generation in armold_controller is
**unchanged from the grblHAL design**:
- `G1 Y<deg> Z<deg> A<deg> B<deg> C<deg> U<deg> F<rate>` for arm joints
- `G1 X<mm> F<rate>` for linear rail
- `SET_SERVO SERVO=gripper ANGLE=<0-180>` for gripper (replaces `M280 P0 S<angle>`)
