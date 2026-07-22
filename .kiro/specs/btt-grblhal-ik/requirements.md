# BTT Octopus MAX EZ + grblHAL + Inverse Kinematics — Requirements

## Goal
Replace the Einsy RAMBo + custom firmware + custom serial daemon with a proven, reliable motion control stack. The BTT Octopus MAX EZ running grblHAL handles all real-time motor control. The Raspberry Pi handles inverse kinematics, trajectory planning, web UI, and sends standard G-code over USB. Zero custom firmware to maintain.

## Hardware BOM

| Component | Qty | Purpose | Notes |
|-----------|-----|---------|-------|
| BTT Octopus MAX EZ V1.0 | 1 | Motion controller | STM32H723, 10 EZ driver slots |
| BTT EZ5160 RGB | 7 | Stepper drivers (SPI) | TMC5160, 4.7A RMS, 8-56V, 50mΩ sense |
| USB-C cable (board to Pi) | 1 | Communication | Native USB, no UART bridge |
| Raspberry Pi 4 | 1 (owned) | IK + web server | Running Ubuntu 24.04 |
| NEMA 17 steppers × 5-7 | 5+ (owned) | Motors | Through 20:1 cycloidal drives |
| 24V DC / 10A PSU | 1 (owned) | Power | Upgradeable to 48V with EZ5160 |

**Estimated cost:** ~$145-165 (board + 7 drivers + cable)

## Architecture

```
Browser (Web UI)
    ↕ WebSocket (port 9090)
Raspberry Pi 4
    ├── IK Solver (ikpy) — Cartesian target → joint angles
    ├── Trajectory Planner — joint angles → G-code
    ├── Web Server — serves UI, handles WebSocket
    └── grblHAL Sender — sends G-code, reads status
            ↕ USB-C (native, no UART bridge)
BTT Octopus MAX EZ (grblHAL)
    ├── 6-axis coordinated motion (X,Y,Z,A,B,C = J0-J5)
    ├── TMC5160 SPI — current, microstepping, StallGuard, CoolStep
    ├── S-curve + lookahead trajectory planning (built-in)
    ├── Hardware E-STOP pin (instant, no serial)
    └── Sensorless homing via StallGuard
            ↕ STEP/DIR (5V signals)
EZ5160 Drivers × 7
            ↕ Motor coils
NEMA 17 Steppers → 20:1 Cycloidal Drives → Robot Joints
```

## Requirements

### R1: Motion Controller (grblHAL on BTT Octopus MAX EZ)
- Flash grblHAL firmware via STM32CubeProgrammer or DFU
- Configure 6 rotary axes: X=J0 (Base), Y=J1 (Shoulder), Z=J2 (Elbow), A=J3 (Wrist Pitch), B=J4 (Wrist Roll), C=J5 (Wrist Yaw)
- All 6 axes coordinated natively (one G1 command moves all simultaneously)
- Built-in S-curve acceleration with lookahead
- TMC5160 via SPI (onboard traces, no extra wiring)
- Hardware E-STOP pin connected to Pi GPIO or physical button
- Sensorless homing (StallGuard4) per axis

### R2: TMC5160 Driver Configuration
- Interface: SPI (pre-routed on Octopus MAX EZ, set via firmware)
- Current: 1200mA RMS (80% of motor rated current, adjustable)
- Mode: SpreadCycle for dynamic torque during moves
- Microstepping: 16 (with 256 interpolation)
- StallGuard sensitivity: tuned per joint after mechanical testing
- CoolStep enabled: reduces current when load is light (efficiency)
- All configured via grblHAL Trinamic plugin settings (`$TMC...`)

### R3: G-code Protocol (Pi → grblHAL)
- Standard GRBL protocol: `G1 X<deg> Y<deg> Z<deg> A<deg> B<deg> C<deg> F<feedrate>\n`
- Response: `ok\n` on success, `error:N\n` on failure
- Real-time E-STOP: `!` byte (no newline, interrupts mid-move instantly)
- Feed hold: `~` to resume
- Status query: `?` returns `<Idle|Run,MPos:0.000,...,WPos:0.000,...>`
- Homing: `$H` (all axes) or `$HX` (single axis)
- Steps/degree: configure `$100`-`$105` = 230.6 steps/degree (83,028 steps/rev ÷ 360)
- Feed rate units: degrees/min

### R4: Axis Calibration
- All joints use same calibration: 83,028 steps/rev = 230.6 steps/degree
- GRBL treats rotation as linear (degrees = "mm")
- Set `$100`=`$101`=`$102`=`$103`=`$104`=`$105`= **230.6**
- GRBL `$130`-`$135` are **total travel** (full range), not half-range
- Joint limits (total travel = 2 × one-side limit):
  - J0 (X): `$130=360` (±180°, confirm physical stop)
  - J1 (Y): `$131=180` (±90°, from simulator)
  - J2 (Z): `$132=300` (±150°, from simulator)
  - J3 (A): `$133=240` (±120°, from simulator; not yet wired)
  - J4 (B): `$134=180` (±90°, from simulator; not yet wired)
  - J5 (C): `$135=360` (±180°, from simulator; not yet wired)
- Home pose (machine zero reference): `[0°, -30°, 70°, 50°, 0°, 0°]`
  - Derived from FK simulator home angles in `robot.js`
  - Physical arm must be manually placed at this pose before homing

### R5: Inverse Kinematics (Pi-side, ikpy)
- Library: **ikpy** (pure Python, 7ms-50ms solve, URDF support)
- Define Armold kinematic chain via URDF file
- DH parameters from physical arm measurements and FK simulator geometry:
  - Link lengths from `Armold_FK_v1/src/robot.js` DIMS (scale by measuring upper arm)
  - Joint axes match simulator: Y-axis base yaw, X-axis shoulder/elbow/wrist pitch, Z-axis wrist yaw, Y-axis wrist roll
- FK: given joint angles → compute end-effector position (for visualization)
- IK: given target XYZ + orientation → compute joint angles
- Output: 6 joint angles (degrees) → converted to G-code
- Fallback: if IK has no solution, return error to client (no movement)
- Joint limit enforcement in IK solver (clamp solutions to simulator-defined limits):
  - J0: ±180°, J1: ±90°, J2: ±150°, J3: ±120°, J4: ±90°, J5: ±180°

### R6: Web UI
- Keep existing Armold web interface (already working)
- Add Cartesian jogging panel (X, Y, Z buttons in addition to joint buttons)
- Add IK mode toggle: joint-space jog vs Cartesian jog
- Cartesian jog: click target position → IK solve → G-code → motion
- Display both joint angles AND end-effector XYZ position
- Speed profiles (Slow/Medium/Max) map to GRBL feed rate `F` values
- E-STOP sends `!` directly over WebSocket → Pi → GRBL serial

### R7: Pi Software Stack
- Language: Python 3.12 (existing)
- IK: `ikpy` library
- GRBL communication: `pyserial` (simple readline/write, no custom protocol)
- WebSocket server: `websockets` (existing)
- State: poll GRBL status (`?`) at 2Hz, broadcast to all clients
- No ROS in the data path (keep ROS 2 installed for future MoveIt)

### R8: Wiring
- BTT Octopus MAX EZ → Pi: USB-C cable (power + data)
- EZ5160 drivers: plug into EZ sockets (pinless, no bend risk)
- SPI configured in firmware (no jumpers needed)
- STEP/DIR outputs (5V) → TE Series drivers (if using external drivers on joints 3-6)
- OR: EZ5160 drivers handle motor current directly (plug motors to driver outputs)
- E-STOP button: normally-closed to Octopus MAX EZ E-STOP header

### R9: E-STOP
- Physical button: hardware E-STOP pin on Octopus MAX EZ (immediate, no software)
- Software E-STOP: Pi sends `!` over USB serial (<1ms latency)
- Both paths disable stepper enable pins immediately (hardware, not firmware)
- Web UI E-STOP button → WebSocket → Pi → `!` to GRBL

### R10: Sensorless Homing (StallGuard4)
- Configure via grblHAL Trinamic plugin
- Set per-axis StallGuard threshold after mechanical testing
- Home each joint sequentially via `$HX`, `$HY` etc.
- TMC5160 SG4 is more reliable than SG2 through gearbox loads
- Homing speed: slow (configurable via `$24` homing seek rate)
- Position reset to zero on stall detection

## Success Criteria
- All 6 joints move simultaneously from a single G-code command
- IK solve + G-code send + motion start < 100ms from web UI button click
- E-STOP < 10ms from button click to motor disable
- No serial timeouts or position desyncs during 1-hour IK demo
- Sensorless homing works reliably on at least J0, J1, J2
- Position state never desyncs (GRBL is authoritative)
