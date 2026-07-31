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

[servo gripper]
pin: PA1
maximum_servo_angle: 180
minimum_pulse_width: 0.0005
maximum_pulse_width: 0.0025

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
2. Compile & flash Klipper MCU firmware to BTT board (DFU)
3. Create printer.cfg with manual_stepper definitions
4. Move J5 back to Motor-7 slot
5. Test all 7 motors via Moonraker API
6. Refactor armold_controller: GrblBoard → KlipperBoard
7. Web UI unchanged (commands route through Moonraker instead of direct serial)
