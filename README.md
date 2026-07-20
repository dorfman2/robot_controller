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
                                  ┌──────┴───────┐
                                  │  Trajectory  │
                                  │  Planner     │
                                  │  (S-curve,   │
                                  │   lookahead) │
                                  └──────┬───────┘
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

Single Python daemon on the Pi handles trajectory planning (S-curve profiles, junction velocity optimization, lookahead), WebSocket connections, and serial communication. The MCU executes segment commands with sinusoidal interpolation — no trajectory math on the ATmega.

## Features

- **Coordinated multi-joint motion** — Bresenham interpolation, all joints start/stop together
- **Sinusoidal S-curve acceleration** — cosine-shaped ramp via lookup table, eliminates jerk at transitions
- **Pi-side trajectory planner** — S-curve profiles computed on Pi, segment commands sent to MCU
- **Junction velocity optimization** — lookahead across moves, no deceleration-to-zero between sequential jogs
- **Trapezoidal speed ramping** — fallback profile (300-step ramp, 20µs cruise)
- **Web UI** — real-time jog controls, IK demo, speed profiles, motion queue display
- **Unified halt system** — user E-STOP and serial interrupt share one code path in firmware
- **Auto-reconnection** — survives USB disconnect/reconnect without manual intervention
- **Position tracking** — firmware-authoritative, synced on every connect
- **Multiple speed profiles** — Slow (200µs), Medium (80µs), Max (20µs)
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
├── einsy/src/main.cpp      # Einsy RAMBo firmware (TMC2130 SPI, sinusoidal ramp, segment protocol)
├── ramps/src/main.cpp      # RAMPS firmware (basic STEP/DIR, 3-axis)
armold_controller/          # Motion control daemon (Pi)
├── __init__.py             # Package init, version
├── __main__.py             # Entry point, config, signal handling, health check
├── main.py                 # Convenience entry point
├── command.py              # Command dataclass with sequence IDs and lifecycle
├── serial_board.py         # Per-board serial thread + command queue + ACK
├── motion_manager.py       # Move coordination, jog stacking, halt, trajectory planner
├── ws_server.py            # asyncio WebSocket + JSON protocol
├── tests/test_core.py      # Unit tests (13 tests)
web/
├── index.html              # Control UI (native WebSocket, no roslib.js)
scripts/
├── deploy.sh               # Mac → Pi firmware deploy + flash
├── deploy_controller.sh    # Mac → Pi controller deploy
├── ik_demo.py              # Standalone IK demo (direct serial)
├── check_serial.py         # Serial port diagnostic
├── serial_read_port.py     # Serial read utility
├── einsy_cmd.py            # Direct command utility
├── reset_zero.py           # Position reset utility
pi/
├── armold.service          # systemd service file (single daemon)
├── install_services.sh     # Service installer
├── setup_ssh.sh            # SSH key setup (Mac → Pi)
├── ssh_config_entry        # SSH config reference
├── README.md               # Pi setup documentation
platformio.ini              # Multi-environment build config
.kiro/specs/
├── stable-bridge/          # Daemon architecture spec (implemented)
├── klipper-style-planner/  # Trajectory planner spec (Phase A+B implemented)
```

## Firmware Protocol

Serial at 115200 baud. Newline-terminated commands:

| Command | Description |
|---------|-------------|
| `E1` / `E0` | Enable / disable motors |
| `G <p0> <p1> <p2> <p3> [delay]` | Coordinated move to absolute positions |
| `X <joint> <steps> <start_int> <end_int> <curve>` | Segment move (Pi-planned, sinusoidal interpolation) |
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
| Cruise delay | 20µs | Max speed with sinusoidal ramp |
| Accel/Decel | 300 steps | Sinusoidal profile, passes through resonance quickly |
| Start delay | 600µs | Conservative start prevents missed steps |
| StallGuard | Disabled (sgt=63) | False triggers from cycloidal gearbox drag |
| Ramp shape | Sinusoidal (cos lookup table) | Zero jerk at transitions |

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
