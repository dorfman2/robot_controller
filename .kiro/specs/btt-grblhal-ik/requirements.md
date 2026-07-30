# BTT Octopus MAX EZ + grblHAL + IK — Requirements (7-Axis)

## Goal
Replace all custom firmware and serial protocols with a single BTT Octopus MAX EZ running grblHAL. One board controls 7 axes: a linear rail (X) plus a 6-DOF robot arm (Y–U). The Raspberry Pi handles inverse kinematics, trajectory planning, web UI, and sends standard G-code over USB. Zero custom firmware to maintain.

## Hardware (All Procured)

| Component | Qty | Status | Notes |
|-----------|-----|--------|-------|
| BTT Octopus MAX EZ V1.0 | 1 | Installed | STM32H723, 10 EZ driver slots, grblHAL flashed |
| BTT EZ5160 RGB | 7 | Installed | TMC5160-TA, 4.7A RMS, 8-56V, SPI, 50mΩ sense |
| USB-C cable (board to Pi) | 1 | Connected | Native USB CDC (VID `0483` PID `5740`) |
| Raspberry Pi 4 | 1 | Running | Ubuntu 24.04, armold_controller daemon |
| NEMA 17 steppers × 7 | 7 | Wired | Through ~25.95:1 cycloidal drives (6 arm) + GT2 belt (rail) |
| 24V DC / 10A PSU | 1 | Running | Upgradeable to 48V with EZ5160 support |
| Linear rail (GT2 belt, 20T pulley) | 1 | Installed | 350mm travel, currently on Einsy |

## Architecture

```
Browser (Web UI + FK Simulator)
    ↕ WebSocket (port 9090)
Raspberry Pi 4
    ├── IK Solver (ikpy) — Cartesian target → joint angles
    ├── Trajectory Planner — joint angles → G-code
    ├── Web Server — serves UI, handles WebSocket
    └── grblHAL Sender — sends G-code, reads status
            ↕ USB-C native (/dev/armold_motion, VID 0483 PID 5740)
BTT Octopus MAX EZ (grblHAL, STM32H723 @ 480MHz)
    ├── 7-axis coordinated motion (X=rail, Y-U=arm joints)
    ├── TMC5160 SPI — current, microstepping, StallGuard4, CoolStep
    ├── S-curve + lookahead trajectory planning (built-in)
    ├── Hardware E-STOP pin (instant, no serial)
    └── Sensorless homing via StallGuard4
            ↕ STEP/DIR (5V signals)
EZ5160 Drivers × 7
            ↕ Motor coils
Motor-0: NEMA 17 → GT2 20T → Linear Rail (350mm)
Motor-1–6: NEMA 17 → 25.95:1 Cycloidal → Robot Joints 0–5
```

## 7-Axis Mapping

| GRBL Axis | Joint | Motor Slot | Purpose | Steps/unit | Travel |
|-----------|-------|------------|---------|-----------|--------|
| X | — | Motor-1 | Linear rail | 80 steps/mm (GT2 20T, 16µstep) | 350mm |
| Y | J0 | Motor-2 | Base yaw | 230.6 steps/° (25.95:1, 16µstep) | ±180° |
| Z | J1 | Motor-3 | Shoulder pitch | 230.6 steps/° | ±90° |
| A | J2 | Motor-4 | Elbow pitch | 230.6 steps/° | ±150° |
| B | J3 | Motor-5 | Wrist pitch | 230.6 steps/° | ±120° |
| C | J4 | Motor-6 | Wrist roll | 230.6 steps/° | ±90° |
| U | J5 | Motor-7 | Wrist yaw | 230.6 steps/° | ±180° |

## Gripper

| Component | Connection | Control |
|-----------|-----------|---------|
| 180° hobby servo | PWM auxiliary output (FAN port on Octopus MAX EZ) | M280 P0 S<angle> |

- Standard 180° servo, 5V signal, powered from board 5V rail
- Controlled via grblHAL `M280` command (PWM servo plugin)
- S0 = closed, S180 = fully open (or calibrate per physical gripper)
- WebSocket command: `{"cmd": "gripper", "angle": 90}`

**Key difference from previous spec**: X is reserved for the linear rail (mm units), arm joints start at Y. This means all arm G-code uses Y/Z/A/B/C/U instead of X/Y/Z/A/B/C.

## Requirements

### R1: grblHAL Firmware (7-Axis Build)
- Build from grblHAL WebBuilder (https://svn.io-engineering.com:8443/)
- Board: BTT Octopus MAX EZ (STM32H723)
- Axes: 7 (XYZABCU)
- Plugins: TMC5160 SPI, soft limits, homing, Trinamic driver support
- Flash via DFU: `sudo dfu-util -a 0 -s 0x08000000:leave -D /tmp/firmware.bin`
- DFU entry: Hold BOOT0, press RESET, release after 5s
- VUSB jumper: bridged for USB-only power during DFU (no 24V needed)
- After flash: verify `$I` shows `[AXS:7:XYZABCU]`

### R2: Axis Calibration
- **X (linear rail)**: 80 steps/mm (GT2 2mm pitch, 20T pulley, 16 microsteps = 200×16/(2×20) = 80)
- **Y–U (arm joints)**: 230.6 steps/degree (83,028 steps/rev ÷ 360°, gearbox ~25.95:1)
- X uses mm units; Y–U use degree units (grblHAL treats all as "mm" internally)
- Soft limits ($20=1):
  - $130=350 (X: 350mm rail travel)
  - $131=360 (Y/J0: ±180°)
  - $132=180 (Z/J1: ±90°)
  - $133=300 (A/J2: ±150°)
  - $134=240 (B/J3: ±120°)
  - $135=180 (C/J4: ±90°)
  - $136=360 (U/J5: ±180°)

### R3: TMC5160 Driver Configuration
- Interface: SPI (pre-routed on Octopus MAX EZ)
- Current: 1200mA RMS (arm joints), adjustable per-axis
- Mode: SpreadCycle (dynamic torque for direction changes)
- Microstepping: 16 (with 256 interpolation)
- StallGuard4 sensitivity: tuned per joint after mechanical testing
- CoolStep: enabled for current reduction under light load
- All configured via grblHAL Trinamic plugin settings

### R4: G-code Protocol (Pi → grblHAL)
- Linear rail move: `G1 X175.0 F5000` (mm, mm/min)
- Arm move: `G1 Y0 Z-30 A70 B50 C0 U0 F1800` (degrees, deg/min)
- Combined: `G1 X175 Y90 Z-30 A70 B50 C0 U0 F1800` (rail + arm simultaneous)
- Response: `ok\n` on success, `error:N\n` on failure
- Real-time E-STOP: `!` byte (no newline, interrupts mid-move instantly)
- Feed hold/resume: `!` / `~`
- Status query: `?` → `<Idle|MPos:X,Y,Z,A,B,C,U|...>`
- Homing: `$H` (all axes) or `$HX` (linear rail only) or `$HY` (J0 only)
- Unlock alarm: `$X`

### R5: Inverse Kinematics (Pi-side)
- Library: ikpy (pure Python, 7–50ms solve, URDF support)
- URDF defines 6 arm joints (J0–J5) — linear rail is NOT part of IK chain
- IK inputs: XYZ position + orientation → outputs 6 joint angles (degrees)
- Linear rail position is independent — set by user or planning layer
- Joint limits enforced in IK solver (matches R2 soft limits for Y–U)
- Home pose: [J0=0°, J1=-30°, J2=70°, J3=50°, J4=0°, J5=0°]
- FK: given joint angles → compute end-effector position (for display)
- If IK fails (unreachable): return error to client, no movement

### R6: Web UI
- Keep existing joint jog panel (updated for new axis mapping)
- Add linear rail panel (position slider, ±10mm/±50mm jog, home button)
- Add Cartesian jog panel (XYZ ±1mm/±10mm/±100mm)
- Add IK mode toggle: joint-space vs Cartesian
- Display: joint angles, end-effector XYZ, rail position
- Speed profiles: Slow/Medium/Max → GRBL feed rate F values
- E-STOP sends `!` directly over WebSocket → Pi → GRBL serial

### R7: Pi Software Stack
- Python 3.12
- IK: ikpy + numpy
- Serial: pyserial (simple readline/write, standard GRBL protocol)
- WebSocket: websockets (existing)
- Status polling: `?` at 2Hz, broadcast to all clients
- No ROS in the motion data path
- Single daemon process (asyncio + serial thread)

### R8: Sensorless Homing (StallGuard4 — Linear Rail Only)
- Linear rail (X): home to one end via StallGuard4, set position = 0, center at 175mm
- Multi-pass homing for reliability (fast approach + slow verify, proven on Einsy rail)
- Homing speed: configurable via $24 (seek) and $25 (feed)
- Arm joints (Y–U): NO sensorless homing — gearbox drag causes false triggers
- Arm home: manual "jog to known pose, set zero" via `G10 L20 P1 Y0 Z0 A0 B0 C0 U0`
- Only X axis configured for homing cycle (`$44=1`, X axis bit only)

### R9: E-STOP
- Physical button: hardware E-STOP pin on Octopus MAX EZ header (immediate)
- Software E-STOP: Pi sends `!` over USB serial (<1ms latency)
- Both paths disable stepper enable pins immediately
- Web UI E-STOP button → WebSocket → Pi → `!` to GRBL
- After E-STOP: `$X` to unlock, or power cycle

### R10: Gripper (PWM Servo)
- 180° hobby servo attached to end effector
- Controlled via grblHAL PWM servo plugin (`PWM_SERVO_ENABLE=1`)
- Command: `M280 P0 S<angle>` where angle is 0–180
- Connected to a PWM-capable auxiliary output (FAN4 header = PA1, already mapped as AUXOUTPUT0)
- 5V signal from board, servo powered from 5V rail or separate BEC
- Web UI: gripper slider (0–180°) or open/close buttons
- Sequence JSON: `"gripper"` field (0.0=closed, 1.0=open) maps to servo angle

### R11: Consolidation (Retire Einsy + RAMPS)
- All 7 axes move to BTT Octopus MAX EZ
- Einsy RAMBo: retired (linear rail motor physically moved to BTT Motor-0)
- RAMPS 1.4: retired (arm motors physically moved to BTT Motor-1 through Motor-6)
- armold_controller daemon: refactored from multi-board to single GrblBoard
- udev rules: only `/dev/armold_motion` needed (remove armold_einsy, armold_ramps)
- systemd service: simplified (one serial port, one daemon)

## Success Criteria
- 7-axis firmware verified: `$I` shows `[AXS:7:XYZABCU]`
- Linear rail homes and centers at 175mm
- All 6 arm joints move from a single G-code command (`G1 Y.. Z.. A.. B.. C.. U.. F1800`)
- Rail + arm move simultaneously (`G1 X175 Y90 F1800`)
- IK solve + G-code send + motion start < 100ms from web UI click
- E-STOP < 10ms from button click to motor disable
- No serial timeouts or position desyncs during 1-hour continuous operation
- Sensorless homing works reliably on linear rail (X axis)
- Arm joints home via manual set-zero (`G10 L20`)
- Position state never desyncs (grblHAL is authoritative via `?` polling)

## Edge Cases and Mitigations

### EC1: U-Axis Not Auto-Detected as Rotary
grblHAL's `IS_ROTARY_LETTER()` only matches A, B, C. The U axis (and Y/Z which are arm joints)
won't auto-flag as rotary. **Must** set `$376=126` explicitly (bitmask Y+Z+A+B+C+U = 2+4+8+16+32+64).
Without this, feed rate calculations and soft limits behave incorrectly for degrees-based axes.

### EC2: Mixed Units in Combined Moves (mm + degrees)
A combined command like `G1 X175 Y90 F1800` mixes mm (rail) and degrees (arm). grblHAL applies
F as the vector feed rate across all axes, scaling speeds proportionally. The rail may move
disproportionately slow/fast relative to arm joints.
**Mitigation**: Send rail and arm moves as separate G-code commands unless true coordinated
motion is specifically needed. The daemon should default to independent moves.

### EC3: Soft Limits Require Known Position
grblHAL won't enable soft limits until position is known (homed or set). After power cycle,
any move returns `error:9` until the machine is either homed or position is manually set.
**Mitigation**: On startup, daemon sends `$X` (unlock alarm), then either:
- `$HX` to home rail, followed by
- `G10 L20 P1 Y0 Z0 A0 B0 C0 U0` to set arm position (user places arm at home pose)
- Or `$20=0` during initial testing (soft limits off)

### EC4: $DFU Flash Failure = Bricked Board
If `$DFU` is sent and the flash operation fails mid-write (USB disconnect, Pi crash),
the board has no firmware — only recoverable via physical BOOT0 button.
**Mitigation**: Verify firmware.bin integrity (size check) before flashing. Keep BOOT0
physically accessible. Consider 128K bootloader linker script for future builds.

### EC5: AUXOUTPUT0 Pin Conflict (Spindle vs Servo)
The board map assigns PA1 (FAN4) as both spindle PWM and AUXOUTPUT0. If spindle is
enabled (default), it conflicts with the gripper servo.
**Mitigation**: Add `-D SPINDLE0_ENABLE=SPINDLE_NONE` to build flags. Robot arm has no spindle.

### EC6: USB Disconnect During Motion
If USB-C disconnects mid-move, the board continues executing buffered G-code with no
way to stop it remotely (arm could collide with objects).
**Mitigation**: 
- Hardware E-STOP button (always works regardless of USB state)
- Short, strain-relieved USB-C cable
- Daemon reconnection logic: on reconnect, query `?`, send `!` if still moving
- Consider `$392` (comm watchdog) if grblHAL supports auto-stop on connection loss

### EC7: Position After E-STOP
After `!` (feed hold), grblHAL decelerates and stops. Position is valid but different from
the commanded target. The daemon's cached position may be stale.
**Mitigation**: Always query `?` after E-STOP to get actual MPos. Never trust cached
position — grblHAL is the single source of truth.

### EC8: 7-Axis Status Response Parsing
With 7 axes, `?` returns 7 MPos values. The status parser must handle exactly 7 floats.
If fewer are returned (firmware misconfiguration), the daemon could crash.
**Mitigation**: Validate `len(mpos) == 7` in the parser. Log and skip malformed responses.

### EC9: SD Card Bootloader Erased by DFU
DFU flash to 0x08000000 overwrites the factory BTT bootloader. SD card firmware
update method no longer works after first DFU flash.
**Mitigation**: Not critical — `$DFU` is the primary update path. BOOT0 is the fallback.
If SD card boot is ever needed, rebuild with 128K bootloader offset linker script.

### EC10: Gripper Servo Power
The 5V rail on the Octopus MAX EZ may not supply enough current for a servo under
load (typical hobby servo draws 500mA–1A stall).
**Mitigation**: Use a separate 5V BEC powered from the 24V rail to supply the servo.
Only the signal wire connects to the board's PWM output.
