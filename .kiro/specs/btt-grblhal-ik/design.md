# BTT Octopus MAX EZ + grblHAL + IK — Design (7-Axis)

#[[file:requirements.md]]

## System Overview

Two distinct layers with a clean interface:

**Layer 1 — Real-time motion (grblHAL on STM32H723):**
All timing-critical work. Receives G-code, executes S-curve trajectories, controls TMC5160 via SPI, fires STEP/DIR signals. The Pi never touches motor timing.

**Layer 2 — Intelligence (Python on Pi):**
IK solving, trajectory planning (joint angles → G-code), web UI, WebSocket server. Pure Python, no real-time requirements.

Interface: standard GRBL protocol over native USB CDC.

---

## Local PlatformIO Build (replaces WebBuilder)

### Repository: dresco/STM32H7xx

The grblHAL STM32H7 driver lives at https://github.com/dresco/STM32H7xx and has
first-class PlatformIO support with board-specific environments already defined.

### Setup

```bash
# Clone grblHAL STM32H7 driver (includes board maps, startup code, PlatformIO config)
cd /Users/jdorfman/Code
git clone --recursive https://github.com/dresco/STM32H7xx.git grblHAL-STM32H7xx
cd grblHAL-STM32H7xx

# Build for BTT Octopus MAX with TMC5160 (existing 6-axis environment)
pio run -e btt_octopus_max_h723_tmc5160

# Output: .pio/build/btt_octopus_max_h723_tmc5160/firmware.bin
```

### Customization for 7-Axis (Our Build)

The stock environment (`btt_octopus_max_h723_tmc5160`) only builds 3 axes (XYZ) with
3 ABC motors for a total of 6. We need 7 axes (XYZABCU).

**Add a new PlatformIO environment** in `platformio.ini`:

```ini
# BTT Octopus Max (H723) — 7-axis Armold robot arm build
[env:btt_octopus_max_armold_7axis]
board = generic_stm32h723ze
board_build.ldscript = STM32H723ZETX_FLASH.ld
build_flags = ${common.build_flags}
              ${usb_h723.build_flags}
              ${sdcard.build_flags}
  -D BOARD_BTT_OCTOPUS_MAX
  -D HSE_VALUE=25000000
  -D TRINAMIC_ENABLE=5160
  -D EEPROM_ENABLE=32
  -D N_AXIS=7
  -D PWM_SERVO_ENABLE=1
  -D SPINDLE0_ENABLE=SPINDLE_NONE
lib_deps = ${common_h723.lib_deps}
           ${usb_h723.lib_deps}
           ${sdcard.lib_deps}
           motors
           trinamic
           eeprom
lib_extra_dirs = ${common.lib_extra_dirs}
                 ${usb_h723.lib_extra_dirs}
                 ${sdcard.lib_extra_dirs}
upload_protocol = dfu
```

### Board Map Patch (Motor-7 / U-axis)

The stock `boards/btt_octopus_max_map.h` only defines 6 motors (Motor-1 through Motor-6).
The board has 10 physical EZ sockets. We add Motor-7 pins for the U axis.

**Patch to `boards/btt_octopus_max_map.h`:**

```c
// Change the error guard from 3 to 4:
#if N_ABC_MOTORS > 4
#error "Octopus MAX board map is configured for 7 motors max (Armold 7-axis)."
#endif

// Add after the M5 (Motor-6) block:
#if N_ABC_MOTORS > 3
#define M6_AVAILABLE                        // Motor-7
#define M6_STEP_PORT                GPIOD
#define M6_STEP_PIN                 3
#define M6_DIRECTION_PORT           GPIOD
#define M6_DIRECTION_PIN            2
#define M6_LIMIT_PORT               GPIOF   // If limit switch needed, assign available pin
#define M6_LIMIT_PIN                10      // FWS pin repurposed (or use DIAG from TMC)
#define M6_ENABLE_PORT              GPIOD
#define M6_ENABLE_PIN               4
#endif

// Add SPI CS pin for Motor-7 TMC5160:
#ifdef M6_AVAILABLE
#define MOTOR_CSM6_PORT             GPIOD
#define MOTOR_CSM6_PIN              7
#endif
```

**Motor-7 physical pins (from BTT schematic):**
- STEP: PD3 (pin 117)
- DIR: PD2 (pin 116)
- EN: PD4 (pin 118)
- CS/UART: PD7 (pin 123)

### Build and Flash Workflow

```bash
# Build 7-axis firmware
cd /Users/jdorfman/Code/grblHAL-STM32H7xx
pio run -e btt_octopus_max_armold_7axis

# Copy to Pi
scp .pio/build/btt_octopus_max_armold_7axis/firmware.bin \
    pi@armold.local:/tmp/firmware.bin

# --- Option A: Remote flash via $DFU (no button press) ---
# Requires Bootloader Entry plugin in running firmware (already present)
ssh pi@armold.local "echo '\$DFU' > /dev/armold_motion && sleep 2 && \
    sudo dfu-util -a 0 -s 0x08000000:leave -D /tmp/firmware.bin"

# --- Option B: Manual DFU (fallback if firmware is bricked) ---
# Put board in DFU mode (BOOT0 + RESET)
ssh pi@armold.local "sudo dfu-util -a 0 -s 0x08000000:leave -D /tmp/firmware.bin"

# Verify after reboot:
# $I should show [AXS:7:XYZABCU]
```

---

## 7-Axis Mapping

```
GRBL axis → Motor Slot → Armold Joint → Physical Hardware
    X     →   Motor-1   →   Linear Rail    → NEMA 17, GT2 20T, 350mm travel
    Y     →   Motor-2   →   J0 (Base)      → NEMA 17, ~25.95:1 cycloidal
    Z     →   Motor-3   →   J1 (Shoulder)  → NEMA 17, ~25.95:1 cycloidal
    A     →   Motor-4   →   J2 (Elbow)     → NEMA 17, ~25.95:1 cycloidal
    B     →   Motor-5   →   J3 (Wrist Pitch) → NEMA 17, ~25.95:1 cycloidal
    C     →   Motor-6   →   J4 (Wrist Roll)  → NEMA 17, ~25.95:1 cycloidal
    U     →   Motor-7   →   J5 (Wrist Yaw)   → NEMA 17, ~25.95:1 cycloidal
```

### Key grblHAL Settings (7-Axis)

```gcode
; --- Steps per unit ---
$100=80.0      ; X steps/mm (linear rail: GT2 2mm pitch, 20T, 16µstep = 200*16/(2*20))
$101=230.6     ; Y steps/degree (J0 Base: 83028/360)
$102=230.6     ; Z steps/degree (J1 Shoulder)
$103=230.6     ; A steps/degree (J2 Elbow)
$104=230.6     ; B steps/degree (J3 Wrist Pitch)
$105=230.6     ; C steps/degree (J4 Wrist Roll)
$106=230.6     ; U steps/degree (J5 Wrist Yaw)

; --- Max feed rates ---
$110=5000      ; X mm/min (linear rail)
$111=1800      ; Y deg/min (J0, 30°/sec)
$112=1800      ; Z deg/min (J1)
$113=1800      ; A deg/min (J2)
$114=1800      ; B deg/min (J3)
$115=1800      ; C deg/min (J4)
$116=1800      ; U deg/min (J5)

; --- Acceleration ---
$120=500       ; X mm/sec² (linear rail)
$121=900       ; Y deg/sec² (J0)
$122=900       ; Z deg/sec² (J1)
$123=900       ; A deg/sec² (J2)
$124=900       ; B deg/sec² (J3)
$125=900       ; C deg/sec² (J4)
$126=900       ; U deg/sec² (J5)

; --- Soft limits (TOTAL travel) ---
$20=1          ; Soft limits enable
$130=350       ; X max travel (350mm rail)
$131=360       ; Y max travel (J0 ±180°)
$132=180       ; Z max travel (J1 ±90°)
$133=300       ; A max travel (J2 ±150°)
$134=240       ; B max travel (J3 ±120°)
$135=180       ; C max travel (J4 ±90°)
$136=360       ; U max travel (J5 ±180°)

; --- Homing ---
; Only X (linear rail) uses sensorless homing
$22=1          ; Homing enable
$44=1          ; Homing cycle 0: X axis only (bitmask bit0=X=1)
$45=0          ; No homing cycle 1
$46=0          ; No homing cycle 2

; --- Rotary axis designation ---
; $376 bitmask: bit3=A, bit4=B, bit5=C, bit6=U
; A+B+C+U = 8+16+32+64 = 120
; But Y and Z are also rotary in our case (arm joints mapped there)
; Y+Z+A+B+C+U = 2+4+8+16+32+64 = 126
$376=126       ; All arm axes are rotary (Y,Z,A,B,C,U)

; --- TMC5160 settings (via Trinamic plugin) ---
; Current: 1200mA RMS for all axes
; Microsteps: 16 (with 256 interpolation)
; Mode: SpreadCycle (mode 0)
```

---

## Inverse Kinematics

### Library: ikpy

The IK chain covers only the 6-DOF arm (J0–J5, mapped to GRBL Y–U).
The linear rail (X) is NOT part of the IK chain — it's controlled independently.

```python
import ikpy.chain
import numpy as np

# Load chain from URDF (6 arm joints only, no linear rail)
arm = ikpy.chain.Chain.from_urdf_file(
    "armold.urdf",
    active_links_mask=[False, True, True, True, True, True, True, False]
    #                  base   J0    J1    J2    J3    J4    J5    tip
)

# Home pose in degrees (from Armold_FK_v1 simulator)
HOME_ANGLES_DEG = [0.0, -30.0, 70.0, 50.0, 0.0, 0.0]

# Joint limits (degrees)
JOINT_LIMITS_DEG = [
    (-180, 180),   # J0 Base yaw
    (-90,  90),    # J1 Shoulder pitch
    (-150, 150),   # J2 Elbow pitch
    (-120, 120),   # J3 Wrist pitch
    (-90,  90),    # J4 Wrist roll
    (-180, 180),   # J5 Wrist yaw
]

def inverse_kinematics(x, y, z, roll=0.0, pitch=0.0, yaw=0.0,
                        initial_angles_deg=None):
    """Compute 6 joint angles for a Cartesian target.

    Returns list of 6 degrees, or None if unreachable.
    """
    target_matrix = np.eye(4)
    target_matrix[:3, 3] = [x, y, z]

    seed_deg = initial_angles_deg or HOME_ANGLES_DEG
    seed_rad = [0.0] + [np.radians(d) for d in seed_deg] + [0.0]

    try:
        result_rad = arm.inverse_kinematics(
            target_matrix, initial_position=seed_rad, max_iter=1000
        )
        degrees = [np.degrees(r) for r in result_rad[1:7]]
        return clamp_to_limits(degrees)
    except Exception:
        return None

def clamp_to_limits(angles):
    return [max(lo, min(hi, a))
            for a, (lo, hi) in zip(angles, JOINT_LIMITS_DEG)]
```

### URDF (armold.urdf)

Same as previous spec — defines the 6 arm joints in Z-up convention.
Linear rail is omitted from URDF (it's a separate workspace positioner, not an arm link).
Geometry from Armold_FK_v1 simulator DIMS, scaled to meters by physical measurement.

---

## Pi Software: armold_controller (GrblBoard)

### G-code Generation (7-Axis)

The key difference from 6-axis: arm joints map to Y,Z,A,B,C,U instead of X,Y,Z,A,B,C.

```python
# Axis letter mapping for arm joints
ARM_AXES = ['Y', 'Z', 'A', 'B', 'C', 'U']  # J0-J5
RAIL_AXIS = 'X'

def joints_to_gcode(target_degrees: list[float], feedrate: float = 1800) -> str:
    """Convert 6 joint angles to G-code (arm only, no rail)."""
    parts = [f'{ax}{deg:.3f}' for ax, deg in zip(ARM_AXES, target_degrees)]
    return f'G1 {" ".join(parts)} F{feedrate}'

def rail_to_gcode(position_mm: float, feedrate: float = 5000) -> str:
    """Move linear rail to absolute position."""
    return f'G1 X{position_mm:.2f} F{feedrate}'

def combined_gcode(rail_mm: float, joints_deg: list[float], feedrate: float = 1800) -> str:
    """Move rail + arm simultaneously."""
    parts = [f'X{rail_mm:.2f}']
    parts += [f'{ax}{deg:.3f}' for ax, deg in zip(ARM_AXES, joints_deg)]
    return f'G1 {" ".join(parts)} F{feedrate}'
```

### GrblBoard Class

```python
import serial
import threading
import time
from dataclasses import dataclass

@dataclass
class GrblStatus:
    state: str = 'Unknown'
    mpos: list = None  # [X, Y, Z, A, B, C, U] — 7 values

    @classmethod
    def parse(cls, line: str):
        """Parse grblHAL status response.
        Example: <Idle|MPos:175.000,0.000,-30.000,70.000,50.000,0.000,0.000|...>
        """
        if not line.startswith('<'):
            return cls()
        line = line.strip('<>')
        parts = line.split('|')
        state = parts[0]
        mpos = None
        for p in parts[1:]:
            if p.startswith('MPos:'):
                mpos = [float(v) for v in p[5:].split(',')]
        return cls(state=state, mpos=mpos)


class GrblBoard:
    """Single-board GRBL serial interface for 7-axis BTT Octopus MAX EZ."""

    def __init__(self, port: str = '/dev/armold_motion', baud: int = 115200):
        self._ser = serial.Serial(port, baud, timeout=1.0)
        self._lock = threading.Lock()
        self._drain_startup()

    def _drain_startup(self):
        """Consume grblHAL welcome banner."""
        time.sleep(0.5)
        self._ser.read(self._ser.in_waiting or 1)

    def send_gcode(self, cmd: str) -> bool:
        """Send G-code, wait for 'ok' or 'error:N'. Returns True on ok."""
        with self._lock:
            self._ser.write(f'{cmd}\n'.encode())
            response = self._ser.readline().decode().strip()
            return response == 'ok'

    def estop(self):
        """Send real-time E-STOP '!' — bypasses lock, single byte, immediate."""
        self._ser.write(b'!')

    def cycle_start(self):
        """Resume after feed hold."""
        self._ser.write(b'~')

    def query_status(self) -> GrblStatus:
        """Poll position via '?' real-time command."""
        self._ser.write(b'?')
        with self._lock:
            line = self._ser.readline().decode().strip()
        return GrblStatus.parse(line)

    def unlock(self) -> bool:
        """Clear alarm state."""
        return self.send_gcode('$X')

    def home(self, axis: str = None) -> bool:
        """Home all axes or a specific axis."""
        cmd = f'$H{axis}' if axis else '$H'
        return self.send_gcode(cmd)

    def set_gripper(self, angle: int) -> bool:
        """Set gripper servo angle (0-180). Uses grblHAL M280 PWM servo."""
        angle = max(0, min(180, angle))
        return self.send_gcode(f'M280 P0 S{angle}')
```

### Motion Manager with IK

```python
class MotionManager:
    """Coordinates IK, joint jog, rail control, and G-code generation."""

    def __init__(self, board: GrblBoard):
        self._board = board
        self._ik_chain = load_arm_chain()
        self._feed_rate = 1800  # degrees/min for arm
        self._rail_feed = 5000  # mm/min for rail

    def jog_joint(self, joint: int, delta_deg: float):
        """Jog a single arm joint (0-5) by delta degrees."""
        status = self._board.query_status()
        if status.mpos is None:
            return False
        # mpos[0]=rail, mpos[1:7]=arm joints
        current_joints = status.mpos[1:7]
        current_joints[joint] += delta_deg
        gcode = joints_to_gcode(current_joints, self._feed_rate)
        return self._board.send_gcode(gcode)

    def jog_rail(self, delta_mm: float):
        """Jog linear rail by delta mm."""
        status = self._board.query_status()
        if status.mpos is None:
            return False
        new_pos = status.mpos[0] + delta_mm
        gcode = rail_to_gcode(new_pos, self._rail_feed)
        return self._board.send_gcode(gcode)

    def move_cartesian(self, x, y, z, roll=0.0, pitch=0.0, yaw=0.0):
        """IK solve → G-code → send. Returns False if unreachable."""
        angles = inverse_kinematics(x, y, z, roll, pitch, yaw)
        if angles is None:
            return False
        gcode = joints_to_gcode(angles, self._feed_rate)
        return self._board.send_gcode(gcode)

    def home_rail(self):
        """Home linear rail via StallGuard, then center at 175mm."""
        self._board.home('X')
        time.sleep(2)
        self._board.send_gcode('G1 X175 F3000')

    def set_arm_home(self):
        """Set current arm position as zero (manual home).
        User must physically place arm at home pose first.
        """
        self._board.send_gcode('G10 L20 P1 Y0 Z0 A0 B0 C0 U0')
```

### Daemon Startup Sequence (Edge Case Aware)

```python
async def startup(board: GrblBoard):
    """Initialize grblHAL after power cycle or daemon restart.

    Handles: EC3 (soft limits need position), EC7 (stale position),
    EC8 (response validation).
    """
    # 1. Query state — board may be in Alarm after power cycle
    status = board.query_status()

    if status.state == 'Alarm':
        # Unlock alarm (required before any movement)
        board.unlock()  # $X
        await asyncio.sleep(0.5)

    # 2. Home linear rail (only axis with StallGuard)
    board.home('X')
    await asyncio.sleep(5)  # Wait for homing to complete

    # 3. Center rail at 175mm
    board.send_gcode('G1 X175 F3000')
    await asyncio.sleep(3)

    # 4. Set arm position to zero (user must have placed arm at home pose)
    # This satisfies soft limit requirement for known position
    board.send_gcode('G10 L20 P1 Y0 Z0 A0 B0 C0 U0')

    # 5. Verify all 7 axes report position
    status = board.query_status()
    if status.mpos is None or len(status.mpos) != 7:
        raise RuntimeError(f"Expected 7-axis MPos, got: {status.mpos}")

    # 6. Enable soft limits now that position is known
    board.send_gcode('$20=1')
```

### USB Disconnect Recovery (EC6)

```python
async def reconnect_loop(board: GrblBoard):
    """Monitor serial connection health. On disconnect, attempt reconnect."""
    while True:
        try:
            status = board.query_status()
            if status.state == 'Unknown':
                raise serial.SerialException("No response")
        except (serial.SerialException, OSError):
            logger.warning("USB connection lost, attempting reconnect...")
            await asyncio.sleep(2)
            try:
                board.reconnect()
                # After reconnect, check if motion is still running
                status = board.query_status()
                if status.state == 'Run':
                    board.estop()  # Stop any buffered motion
                    logger.warning("Stopped residual motion after reconnect")
            except Exception as e:
                logger.error(f"Reconnect failed: {e}")
                continue
        await asyncio.sleep(0.5)
```

### Sequence Export → G-code (Updated for 7-Axis)

```python
def sequence_to_gcode(json_file: str, feedrate: float = 1800) -> list[str]:
    """Convert Armold_FK_v1 sequence JSON to 7-axis G-code.

    Simulator angles map to GRBL axes Y,Z,A,B,C,U (not X—that's rail).
    """
    import json
    with open(json_file) as f:
        data = json.load(f)

    gcode = []
    for step in data['steps']:
        a = step['angles']  # [j0, j1, j2, j3, j4, j5]
        line = f"G1 Y{a[0]:.2f} Z{a[1]:.2f} A{a[2]:.2f} B{a[3]:.2f} C{a[4]:.2f} U{a[5]:.2f} F{feedrate}"
        gcode.append(f"; {step['name']}")
        gcode.append(line)
        if step.get('dwell', 0) > 0:
            gcode.append(f"G4 P{step['dwell']:.1f}")
    return gcode
```

---

## WebSocket Protocol (Updated)

```json
// Joint jog (arm)
{"cmd": "jog", "joint": 0, "delta": 5.0}

// Rail jog
{"cmd": "jog_rail", "delta": 10.0}

// Cartesian move (IK)
{"cmd": "move_cartesian", "x": 0.3, "y": 0.0, "z": 0.2}

// Home
{"cmd": "home_rail"}
{"cmd": "set_arm_home"}

// E-STOP
{"cmd": "estop"}

// Gripper
{"cmd": "gripper", "angle": 90}

// Set feed rate
{"cmd": "set_speed", "profile": "fast"}  // slow=600, medium=1200, fast=1800

// State broadcast (2Hz from daemon)
{"type": "state",
 "grbl_state": "Idle",
 "rail_mm": 175.0,
 "joints_deg": [0.0, -30.0, 70.0, 50.0, 0.0, 0.0],
 "cartesian": {"x": 0.3, "y": 0.0, "z": 0.2}}
```

---

## Web UI Changes

### Updated Layout
```
┌──────────────────────────────────────────────────────────┐
│  [E-STOP]              Armold — Sweep Sync               │
├──────────────────────────────────────────────────────────┤
│  Linear Rail: [HOME] ◄━━━━━━━━━━●━━━━━━━━━━► 350mm      │
│  Position: 175.0mm    [-50] [-10] [+10] [+50]           │
├──────────────────────────────────────────────────────────┤
│  Mode: [Joint] [Cartesian]    Speed: [Slow][Med][Fast]  │
├──────────────────────────────────────────────────────────┤
│  Joint Jog:                                              │
│  J0 Base:      [-10°] [-1°] [+1°] [+10°]  current: 0°  │
│  J1 Shoulder:  [-10°] [-1°] [+1°] [+10°]  current:-30° │
│  J2 Elbow:     [-10°] [-1°] [+1°] [+10°]  current: 70° │
│  J3 Wrist P:   [-10°] [-1°] [+1°] [+10°]  current: 50° │
│  J4 Wrist R:   [-10°] [-1°] [+1°] [+10°]  current: 0°  │
│  J5 Wrist Y:   [-10°] [-1°] [+1°] [+10°]  current: 0°  │
├──────────────────────────────────────────────────────────┤
│  Cartesian Jog (IK mode):                               │
│  X: [-100mm][-10mm][-1mm][+1mm][+10mm][+100mm]         │
│  Y: ...                                                  │
│  Z: ...                                                  │
│  End Effector: X=300mm Y=0mm Z=200mm                    │
└──────────────────────────────────────────────────────────┘
```

---

## udev Rule (Updated VID/PID)

```bash
# /etc/udev/rules.d/99-armold-motion.rules
# BTT Octopus MAX EZ running grblHAL (STM32 CDC, actual VID:PID from lsusb)
SUBSYSTEM=="tty", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="5740", \
  SYMLINK+="armold_motion", MODE="0666", GROUP="dialout"
```

---

## Consolidation Plan (Retire Einsy + RAMPS)

1. Move linear rail motor from Einsy Motor-X to BTT Motor-1 (GRBL X axis)
2. Move arm motors from RAMPS to BTT Motor-2 through Motor-7 (GRBL Y–U)
3. Remove Einsy and RAMPS physically
4. Remove udev rules for `/dev/armold_einsy` and `/dev/armold_ramps`
5. Stop old multi-board daemon; deploy new single-board GrblBoard daemon
6. Single service file, single serial port, single board

---

## Comparison with Current Architecture

| Aspect | Current (Einsy + RAMPS) | New (BTT 7-axis grblHAL) |
|--------|-------------------------|--------------------------|
| Boards | 2 (Einsy + RAMPS) | 1 (BTT Octopus MAX EZ) |
| Serial ports | 2 (/dev/armold_einsy, _ramps) | 1 (/dev/armold_motion) |
| Firmware | 2 custom (C++, AVR) | 1 community (grblHAL, STM32) |
| Build tool | PlatformIO (AVR) | PlatformIO (STM32, same toolchain) |
| Protocol | Custom binary/ASCII | Standard GRBL G-code |
| Trajectory | Custom sinusoidal ramp | grblHAL S-curve + lookahead |
| Drivers | TMC2130 (1.48A) + S42C | TMC5160 (4.7A) × 7 |
| IK | None | ikpy on Pi |
| Linear rail | Separate board | Integrated (X axis) |
| E-STOP | Serial byte + enable pin | `!` byte + hardware pin |
| Custom code | ~2000 lines firmware + daemon | ~300 lines daemon |
| Maintenance | High (2 boards, 2 protocols) | Low (1 board, standard protocol) |
