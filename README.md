# Armold

A six-axis robot arm controller built on commodity 3D printer electronics. Controls stepper motors through cycloidal gearboxes with sub-degree precision, coordinated multi-joint motion, and collision detection.

## Hardware

| Component | Role |
|-----------|------|
| Einsy RAMBo 1.1a | Primary controller — 4x TMC2130 (SPI), joints 0-3 |
| RAMPS 1.4 + Mega 2560 | Secondary controller — joints 4-5 (planned) |
| Raspberry Pi 4 | Motion controller daemon, WebSocket server |
| TMC2130 drivers | SpreadCycle mode, 1200mA, 16 microsteps + interpolation |
| NEMA 17 steppers | Through 20:1 micro cycloidal drives |
| 24V DC / 10A | Shared power supply |

## Specifications

- **Degrees of Freedom**: 6 (3 active, 3 pending hardware)
- **Payload Capacity**: 750g
- **Maximum Reach**: 475mm
- **Repeatability**: ±1mm
- **Resolution**: ~230 steps/degree (83,028 steps per output revolution)
- **Control Interface**: Web UI over WebSocket

## Architecture

```
Browser (Web UI) ←→ WebSocket ←→ armold_controller (Pi daemon)
                                         │
                                    Serial Threads
                                         │
                              ┌──────────┴──────────┐
                        /dev/armold_einsy      /dev/armold_ramps
                         Einsy (J0-J3)          RAMPS (J4-J5)
                              │                       │
                        TMC2130 SPI              TMC2208/2209
                              │                       │
                        Stepper Motors          Stepper Motors
                              │                       │
                        Cycloidal 20:1          Cycloidal 20:1
```

Single Python daemon on the Pi handles WebSocket connections, command queuing, and serial communication. No ROS in the motion path.

## Features

- **Coordinated multi-joint motion** — Bresenham interpolation, all joints start/stop together
- **Trapezoidal speed ramping** — smooth acceleration/deceleration (300-step ramp, 30µs cruise)
- **Web UI** — real-time jog controls, IK demo, speed profiles, motion queue display
- **Unified halt system** — user E-STOP and StallGuard collision detection share one code path
- **Collision detection** — TMC2130 StallGuard monitors motor load during moves, halts on impact
- **Auto-reconnection** — survives USB disconnect/reconnect without manual intervention
- **Position tracking** — firmware-authoritative, synced on every connect
- **Multiple speed profiles** — Slow (200µs), Medium (80µs), Max (30µs)
- **Deploy pipeline** — flash firmware from Mac via Pi over SSH

## Quick Start

### Prerequisites

- Raspberry Pi 4 running Ubuntu Server 24.04
- Einsy RAMBo 1.1a connected via USB
- PlatformIO installed on Mac and Pi
- Python 3.12 on Pi with `pyserial` and `websockets`

### Flash Firmware

```bash
# From Mac — deploys and flashes to Einsy via Pi
./scripts/deploy.sh einsy
```

### Start Controller

```bash
# On Pi
sudo systemctl start armold

# Or manually
python3 armold_controller/main.py
```

### Open Web UI

Navigate to `http://armold.local:9090` (or open `web/index.html` locally and connect to `ws://armold.local:9090`).

### Use

1. Click **Enable Motors**
2. Use jog buttons to move individual joints
3. Click **IK Demo** for a coordinated motion sequence
4. **E-STOP** immediately halts all motion

## Project Structure

```
firmware/
├── einsy/src/main.cpp      # Einsy RAMBo firmware (TMC2130 SPI, 4-axis)
├── ramps/src/main.cpp      # RAMPS firmware (basic STEP/DIR, 3-axis)
armold_controller/          # Motion control daemon (Pi)
├── main.py                 # Entry point
├── serial_board.py         # Per-board serial thread + command queue
├── motion_manager.py       # Move coordination, jog stacking, halt
├── websocket_server.py     # asyncio WebSocket + JSON protocol
web/
├── index.html              # Control UI (connects via WebSocket)
scripts/
├── deploy.sh               # Mac → Pi firmware deploy + flash
├── ik_demo.py              # Standalone IK demo (direct serial)
pi/
├── armold.service          # systemd service file
├── install_services.sh     # Service installer
platformio.ini              # Multi-environment build config
```

## Firmware Protocol

Serial at 115200 baud. Newline-terminated commands:

| Command | Description |
|---------|-------------|
| `E1` / `E0` | Enable / disable motors |
| `G <p0> <p1> <p2> <p3> [delay]` | Coordinated move to absolute positions |
| `M<j> <steps> <dir> <delay>` | Move single joint |
| `S` | Query state (returns positions) |
| `R` / `R<j>` | Reset position counters (all or single joint) |
| `C <mA>` | Set motor current (Einsy only) |
| `U <microsteps>` | Set microstepping (Einsy only) |
| `T` | Toggle StealthChop/SpreadCycle (Einsy only) |
| `I` | Driver diagnostics (Einsy only) |

## WebSocket Protocol

JSON messages over native WebSocket (port 9090):

```json
// Client → Server
{"cmd": "enable"}
{"cmd": "jog", "joint": 0, "delta": 20757}
{"cmd": "move", "target": [20757, 0, 0, 0, 0, 0]}
{"cmd": "estop"}
{"cmd": "set_speed", "delay_us": 30}

// Server → Client
{"type": "state", "enabled": true, "position": [20757, 0, 0, 0, 0, 0], "speed": 30}
{"type": "halt", "source": "collision", "joint": 1, "message": "Collision on Joint 1"}
{"type": "ack", "id": 5, "status": "ok", "position": [20757, 0, 0, 0, 0, 0]}
```

## TMC2130 Settings (Validated)

| Setting | Value | Rationale |
|---------|-------|-----------|
| Current | 1200mA RMS | ~80% of hardware max, thermal headroom |
| Microsteps | 16 + interpolation to 256 | Smooth without MCU step-rate overhead |
| Mode | SpreadCycle | Dynamic torque for rapid direction changes |
| Cruise delay | 30µs | Near max speed with 300-step ramp |
| Accel/Decel | 300 steps | Passes through resonance zone quickly |
| Start delay | 600µs | Conservative start prevents missed steps |
| StallGuard sgt | 4 | Collision sensitivity (tune per joint) |

## Joint Limits

| Joint | Range | Role |
|-------|-------|------|
| J0 (Base) | ±720° | Rotation |
| J1 (Shoulder) | ±135° | Lift |
| J2 (Elbow) | ±135° | Reach |
| J3 (Wrist Pitch) | ±100° | Not yet wired |
| J4 (Wrist Roll) | ±100° | Pending RAMPS |
| J5 (Wrist Yaw) | ±100° | Pending RAMPS |

## Development

### Flash firmware from Mac (direct USB)

```bash
export PATH="/Users/$USER/.platformio/penv/bin:$PATH"
pio run -e einsy -t upload
```

### Flash via Pi (remote)

```bash
./scripts/deploy.sh einsy
```

### SSH to Pi

```bash
ssh pi@armold.local
```

### View logs

```bash
ssh pi@armold.local "sudo journalctl -u armold -f"
```

## License

See [LICENSE](LICENSE) file.

## Author

Jeffrey Dorfman ([@dorfman2](https://github.com/dorfman2))
