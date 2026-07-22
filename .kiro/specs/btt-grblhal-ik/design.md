# BTT Octopus MAX EZ + grblHAL + IK — Design

#[[file:requirements.md]]

## System Overview

The architecture has two distinct layers with a clean interface between them:

**Layer 1 — Real-time motion (grblHAL on STM32H723):**
All timing-critical work. Receives G-code, executes S-curve trajectories, controls TMC5160 via SPI, fires STEP/DIR signals. The Pi never touches motor timing.

**Layer 2 — Intelligence (Python on Pi):**
IK solving, trajectory planning (joint angles → G-code), web UI, WebSocket server. Pure Python, no real-time requirements.

The interface between them is standard GRBL protocol — the most battle-tested CNC serial protocol in existence.

---

## grblHAL Configuration

### Axis Mapping
```
GRBL axis → Armold joint → Motor slot on Octopus MAX EZ
    X     →     J0 (Base)            → Motor-1
    Y     →     J1 (Shoulder)        → Motor-2
    Z     →     J2 (Elbow)           → Motor-3
    A     →     J3 (Wrist Pitch)     → Motor-4
    B     →     J4 (Wrist Roll)      → Motor-5
    C     →     J5 (Wrist Yaw)       → Motor-6
    -     →     J6 (Gripper)         → Motor-7 (future, servo or stepper)
```

### Key grblHAL Settings
```
; Steps per degree (83,028 steps/rev ÷ 360°)
$100=230.6   ; X steps/degree (J0 Base)
$101=230.6   ; Y steps/degree (J1 Shoulder)
$102=230.6   ; Z steps/degree (J2 Elbow)
$103=230.6   ; A steps/degree (J3 Wrist Pitch)
$104=230.6   ; B steps/degree (J4 Wrist Roll)
$105=230.6   ; C steps/degree (J5 Wrist Yaw)

; Max feed rates (degrees/min)
$110=1800    ; X max rate (30 deg/sec)
$111=1800    ; Y max rate
$112=1800    ; Z max rate
$113=1800    ; A max rate
$114=1800    ; B max rate
$115=1800    ; C max rate

; Acceleration (degrees/sec²)
$120=900     ; X acceleration
$121=900     ; Y acceleration
$122=900     ; Z acceleration
$123=900     ; A acceleration
$124=900     ; B acceleration
$125=900     ; C acceleration

; Soft limits — $130-$135 are TOTAL travel (full range, not half)
; e.g. ±180° = 360° total, ±90° = 180° total
$130=360     ; X max travel (J0 ±180°)
$131=180     ; Y max travel (J1 ±90°)
$132=300     ; Z max travel (J2 ±150°)
$133=240     ; A max travel (J3 ±120°)
$134=180     ; B max travel (J4 ±90°)
$135=360     ; C max travel (J5 ±180°)
$20=1        ; Soft limits enable

; Home pose (machine zero reference) — from FK simulator robot.js
; Joint angles: [J0=0°, J1=-30°, J2=70°, J3=50°, J4=0°, J5=0°]
; Place arm physically at this pose before running $H homing

; TMC5160 SPI settings (via grblHAL Trinamic plugin)
$TMC_X_CURRENT=1200  ; mA RMS
$TMC_X_MICROSTEPS=16
$TMC_X_MODE=SpreadCycle
$TMC_X_SGTHR=4       ; StallGuard threshold (tune per joint)
; (repeat for Y,Z,A,B,C)
```

### Motion Profile
grblHAL's built-in planner provides:
- S-curve acceleration (jerk-limited via `$23` jerk setting)
- Lookahead across queued moves (eliminates pause between sequential jogs)
- Constant junction velocity when direction doesn't change
- Cornering algorithm for smooth multi-axis coordination

No custom trajectory code needed — this is what grblHAL was built for.

---

## Inverse Kinematics

### Library: ikpy

```python
import ikpy.chain
import numpy as np

# Load chain from URDF.
# ikpy adds a fixed "base" link at index 0 and a fixed "end" link at the last index.
# With 6 active joints, the chain has 8 links total (base + 6 joints + end_effector).
# active_links_mask must have the same length as the number of links (8).
arm = ikpy.chain.Chain.from_urdf_file(
    "armold.urdf",
    active_links_mask=[False, True, True, True, True, True, True, False]
    #                  base   J0    J1    J2    J3    J4    J5    tip
)

# Home pose in radians (from simulator robot.js JOINTS home values)
HOME_ANGLES_DEG = [0.0, -30.0, 70.0, 50.0, 0.0, 0.0]
HOME_ANGLES_RAD = [np.radians(d) for d in HOME_ANGLES_DEG]

# Joint limits matching simulator DIMS (radians)
JOINT_LIMITS_DEG = [
    (-180, 180),   # J0 Base yaw
    (-90,  90),    # J1 Shoulder pitch
    (-150, 150),   # J2 Elbow pitch
    (-120, 120),   # J3 Wrist pitch
    (-90,  90),    # J4 Wrist yaw
    (-180, 180),   # J5 Wrist roll
]

def inverse_kinematics(
    x: float, y: float, z: float,
    roll: float = 0.0, pitch: float = 0.0, yaw: float = 0.0,
    initial_angles_deg: list[float] | None = None,
) -> list[float] | None:
    """Compute joint angles for a Cartesian target.

    Args:
        x, y, z: Target position in meters (URDF Z-up frame)
        roll, pitch, yaw: Target orientation in radians
        initial_angles_deg: Warm-start seed (degrees). Defaults to home pose.

    Returns:
        6 joint angles in degrees, or None if no solution found.
    """
    target_matrix = np.eye(4)
    target_matrix[:3, 3] = [x, y, z]
    # Orientation can be added via rotation matrix if needed

    seed_deg = initial_angles_deg if initial_angles_deg is not None else HOME_ANGLES_DEG
    # ikpy expects the full link array including fixed base/end (zeros for inactive)
    seed_rad = [0.0] + [np.radians(d) for d in seed_deg] + [0.0]

    try:
        result_rad = arm.inverse_kinematics(
            target_matrix,
            initial_position=seed_rad,
            max_iter=1000,
        )
        # Slice off the fixed base (index 0) and end (index -1)
        degrees = [np.degrees(r) for r in result_rad[1:7]]
        return clamp_to_limits(degrees)
    except Exception:
        return None  # No solution — caller should report error, not move

def clamp_to_limits(angles: list[float]) -> list[float]:
    """Enforce per-joint degree limits."""
    return [
        max(lo, min(hi, a))
        for a, (lo, hi) in zip(angles, JOINT_LIMITS_DEG)
    ]
```

### URDF Definition (armold.urdf)

Populated from the FK simulator geometry (`Armold_FK_v1/src/robot.js` DIMS).
Simulator units are proportional — scale by measuring one real link and applying the ratio.

**Simulator DIMS (relative units, need scaling to meters):**
- baseHeight: 0.35, shoulderHeight: 0.55, upperArm: 1.50, foreArm: 1.25, wristLen: 0.35, toolLen: 0.45

**Measure the physical upper arm** (shoulder to elbow, center-to-center) and set `SCALE = real_mm / 1500`.

```xml
<?xml version="1.0"?>
<!--
  Armold URDF — derived from FK simulator geometry (Armold_FK_v1/src/robot.js DIMS).
  Convention: URDF Z-up. Arm links extend along local +Z axis of each joint frame.
  Simulator used Three.js Y-up; axes are remapped here to URDF Z-up convention.

  SCALE = physical_upper_arm_mm / 150.0
  (divide by 150 because DIMS.upperArm=1.5 and URDF units are meters)
  Example: if upper arm measures 225mm → SCALE = 225/150 = 1.5 → lengths below × 1.5
-->
<robot name="armold">

  <!-- Fixed world base -->
  <link name="base_link"/>

  <!-- Joint 0: Base yaw — rotates about Z-axis (vertical) in URDF Z-up convention -->
  <joint name="joint_0" type="revolute">
    <parent link="base_link"/>
    <child link="link_0"/>
    <origin xyz="0 0 0.35"/>  <!-- baseHeight × SCALE (pedestal height) -->
    <axis xyz="0 0 1"/>       <!-- Z-axis yaw (vertical axis, URDF convention) -->
    <limit lower="-3.14159" upper="3.14159" velocity="0.524" effort="8.8"/>
    <!-- ±180° — confirm physical stop on real arm -->
  </joint>
  <link name="link_0"/>

  <!-- Joint 1: Shoulder pitch — rotates about Y-axis (left-right horizontal) -->
  <joint name="joint_1" type="revolute">
    <parent link="link_0"/>
    <child link="link_1"/>
    <origin xyz="0 0 0.55"/>  <!-- shoulderHeight × SCALE (riser above base) -->
    <axis xyz="0 1 0"/>       <!-- Y-axis pitch -->
    <limit lower="-1.5708" upper="1.5708" velocity="0.524" effort="8.8"/>
    <!-- ±90° -->
  </joint>
  <link name="link_1"/>

  <!-- Joint 2: Elbow pitch — rotates about Y-axis, offset along Z (upper arm) -->
  <joint name="joint_2" type="revolute">
    <parent link="link_1"/>
    <child link="link_2"/>
    <origin xyz="0 0 1.50"/>  <!-- upperArm × SCALE (shoulder→elbow length) -->
    <axis xyz="0 1 0"/>       <!-- Y-axis pitch -->
    <limit lower="-2.6180" upper="2.6180" velocity="0.524" effort="8.8"/>
    <!-- ±150° -->
  </joint>
  <link name="link_2"/>

  <!-- Joint 3: Wrist Pitch — rotates about Y-axis, offset along Z (forearm) -->
  <joint name="joint_3" type="revolute">
    <parent link="link_2"/>
    <child link="link_3"/>
    <origin xyz="0 0 1.25"/>  <!-- foreArm × SCALE (elbow→wrist length) -->
    <axis xyz="0 1 0"/>       <!-- Y-axis pitch -->
    <limit lower="-2.0944" upper="2.0944" velocity="0.524" effort="4.4"/>
    <!-- ±120° -->
  </joint>
  <link name="link_3"/>

  <!-- Joint 4: Wrist Yaw — rotates about Z-axis (tool twist), offset along Z -->
  <joint name="joint_4" type="revolute">
    <parent link="link_3"/>
    <child link="link_4"/>
    <origin xyz="0 0 0.35"/>  <!-- wristLen × SCALE -->
    <axis xyz="0 0 1"/>       <!-- Z-axis yaw -->
    <limit lower="-1.5708" upper="1.5708" velocity="0.524" effort="4.4"/>
    <!-- ±90° -->
  </joint>
  <link name="link_4"/>

  <!-- Joint 5: Wrist Roll — rotates about X-axis (roll about tool axis) -->
  <joint name="joint_5" type="revolute">
    <parent link="link_4"/>
    <child link="end_effector"/>
    <origin xyz="0 0 0"/>
    <axis xyz="1 0 0"/>       <!-- X-axis roll -->
    <limit lower="-3.14159" upper="3.14159" velocity="0.524" effort="4.4"/>
    <!-- ±180° -->
  </joint>
  <link name="end_effector">
    <!-- Tool tip is 0.45 × SCALE above the wrist roll joint -->
    <visual>
      <origin xyz="0 0 0.45"/>  <!-- toolLen × SCALE -->
      <geometry><sphere radius="0.02"/></geometry>
    </visual>
  </link>

</robot>
```

**Calibration procedure:**
1. Measure physical upper arm length (shoulder to elbow pivot, mm)
2. `SCALE = measured_mm / 1500.0` (1500 = simulator upperArm × 1000)
3. Multiply all `DIMS` by SCALE to get real-world meters for URDF
4. Validate FK: set joints to home pose (-30, 70, 50, 0, 0 degrees) → compare tool tip position to physical arm measurement

---

## Pi Software: armold_controller Refactor

### Key Changes from Current Architecture

| Current | New |
|---------|-----|
| Custom binary/ASCII serial protocol | Standard GRBL protocol |
| Custom firmware (race conditions) | grblHAL (proven) |
| Position tracked in daemon | Position from GRBL `?` status |
| Segment-based trajectory | G-code trajectory (grblHAL plans) |
| No IK | ikpy IK solver |

### GRBL Serial Handler

```python
class GrblBoard:
    """Manages communication with grblHAL over USB serial.

    grblHAL default baud: 115200. For faster status polling, 460800 is
    supported — set via grblHAL $Settings and match here.
    The BTT Octopus MAX EZ uses native USB (STM32 CDC), so baud rate is
    a virtual setting; 115200 is fine for all G-code workloads.
    """

    def __init__(self, port: str, baud: int = 115200):
        self._ser = serial.Serial(port, baud, timeout=1.0)
        self._lock = threading.Lock()
        self._status = GrblStatus()
        self._drain_startup()  # consume grblHAL welcome banner

    def _drain_startup(self):
        """Consume grblHAL startup message (e.g. 'GrblHAL 1.1f ...')."""
        import time
        time.sleep(0.5)
        self._ser.read(self._ser.in_waiting or 1)

    def send_gcode(self, cmd: str) -> bool:
        """Send a G-code command and wait for 'ok' or 'error:N' response.

        Do NOT reset_input_buffer before sending — that would silently
        drop any 'ok' responses already queued from prior commands.
        """
        with self._lock:
            self._ser.write(f'{cmd}\n'.encode())
            response = self._ser.readline().decode().strip()
            return response == 'ok'

    def estop(self):
        """Send real-time E-STOP '!' byte.

        Real-time commands bypass the serial lock — they are single bytes
        that grblHAL processes immediately, interrupting any running move.
        Writing a single byte is atomic at the OS level.
        """
        self._ser.write(b'!')

    def feed_hold(self):
        """Send real-time feed hold (pause mid-move)."""
        self._ser.write(b'!')

    def cycle_start(self):
        """Send real-time cycle start (resume after feed hold)."""
        self._ser.write(b'~')

    def query_status(self) -> GrblStatus:
        """Poll current state. '?' is a real-time command; no lock needed."""
        self._ser.write(b'?')
        with self._lock:
            line = self._ser.readline().decode().strip()
        return GrblStatus.parse(line)
        # Example response: <Idle,MPos:0.000,0.000,0.000,0.000,0.000,0.000>
```

### Motion Manager with IK

```python
class MotionManager:
    """Coordinates IK solving and G-code generation."""

    def __init__(self, board: GrblBoard):
        self._board = board
        self._ik_chain = load_arm_chain()
        self._current_joints = [0.0] * 6  # degrees
        self._feed_rate = 1800  # degrees/min

    def jog_joint(self, joint: int, delta_deg: float):
        """Move a single joint by delta degrees."""
        target = list(self._current_joints)
        target[joint] += delta_deg
        self._move_joints(target)

    def move_cartesian(self, x: float, y: float, z: float,
                        roll=0.0, pitch=0.0, yaw=0.0) -> bool:
        """Move end effector to Cartesian position via IK."""
        angles = inverse_kinematics(x, y, z, roll, pitch, yaw)
        if angles is None:
            return False  # No IK solution
        self._move_joints(angles)
        return True

    def _move_joints(self, target_degrees: list[float]):
        """Convert joint angles to G-code and send."""
        names = ['X', 'Y', 'Z', 'A', 'B', 'C']
        parts = [f'{n}{d:.3f}' for n, d in zip(names, target_degrees)]
        gcode = f'G1 {" ".join(parts)} F{self._feed_rate}'
        self._board.send_gcode(gcode)
        self._current_joints = list(target_degrees)
```

### Sequence Export from Simulator → G-code

The FK simulator's JSON export format (`armold-sequence.json`) can be directly converted to G-code:

```python
import json

def sequence_to_gcode(json_file: str, feedrate: float = 1800) -> list[str]:
    """Convert Armold_FK_v1 exported sequence to grblHAL G-code.

    Simulator sequence format:
    {"version": 1, "steps": [
        {"name": "Home", "angles": [0, -30, 70, 50, 0, 0],
         "gripper": 0, "duration": 1.0, "dwell": 0.2}
    ]}

    Args:
        json_file: Path to exported sequence JSON
        feedrate: Degrees/min (duration hint, grblHAL plans actual rate)

    Returns:
        List of G-code strings
    """
    with open(json_file) as f:
        data = json.load(f)

    gcode = []
    for step in data['steps']:
        a = step['angles']  # [j0, j1, j2, j3, j4, j5] in degrees
        # Map to GRBL axes: X=J0, Y=J1, Z=J2, A=J3, B=J4, C=J5
        # Feed rate from duration: degrees_moved / duration_seconds × 60
        line = f"G1 X{a[0]:.2f} Y{a[1]:.2f} Z{a[2]:.2f} A{a[3]:.2f} B{a[4]:.2f} C{a[5]:.2f} F{feedrate}"
        gcode.append(f"; {step['name']}")
        gcode.append(line)
        if step.get('dwell', 0) > 0:
            gcode.append(f"G4 P{step['dwell']:.1f}")  # Dwell in seconds

    return gcode
```

This means the simulator's **demo pick-and-place program can run directly on the physical arm** after calibration.

The existing JSON WebSocket protocol stays. New commands added:

```json
// New: Cartesian jog
{"cmd": "move_cartesian", "x": 0.3, "y": 0.0, "z": 0.2, "roll": 0, "pitch": 0, "yaw": 0}

// New: IK mode status
{"type": "state", "position": [...], "cartesian": {"x": 0.3, "y": 0.0, "z": 0.2}, ...}

// Existing (unchanged):
{"cmd": "jog", "joint": 0, "delta": 5189}
{"cmd": "estop"}
{"cmd": "enable"}
```

---

## Web UI Changes

### New Cartesian Panel
```
┌─────────────────────────────────────────────┐
│  End Effector Position          Mode: [Joint|Cartesian] │
│  X: 0.300m   Y: 0.000m   Z: 0.200m          │
│                                             │
│  Jog X: [-10cm] [-1cm] [-1mm] [+1mm] [+1cm] [+10cm]  │
│  Jog Y: ...                                 │
│  Jog Z: ...                                 │
└─────────────────────────────────────────────┘
```

Joint panels remain unchanged. Mode toggle switches between:
- **Joint mode:** existing jog buttons (degrees)
- **Cartesian mode:** new XYZ buttons (mm increments → IK → G-code)

---

## Installation Notes

### grblHAL Flashing (BTT Octopus MAX EZ)
1. Go to the grblHAL WebBuilder: **https://svn.io-engineering.com:8443/**
2. Select board: BTT Octopus MAX EZ (or closest STM32H723 variant)
3. Enable plugins: 6 axes (XYZABC), TMC5160 SPI driver, soft limits, homing, CoolStep
4. Click "Generate and download firmware" → saves a `.bin` file
5. Flash via STM32CubeProgrammer (DFU mode: hold BOOT0 button while connecting USB)
6. After flash, open serial terminal at 115200 baud → confirm `GrblHAL` startup message
7. Paste `$-settings` block from design.md to configure axes, limits, and Trinamic plugin

### Python Dependencies (Pi)
```bash
pip3 install ikpy pyserial websockets numpy
```

### udev Rule (Pi) — Persistent Serial Device Name
Create `/etc/udev/rules.d/99-armold-motion.rules`:
```
# BTT Octopus MAX EZ (STM32H723 USB CDC)
SUBSYSTEM=="tty", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="614e", \
  SYMLINK+="armold_motion", MODE="0666", GROUP="dialout"
```
Then reload: `sudo udevadm control --reload-rules && sudo udevadm trigger`

The daemon references `/dev/armold_motion` — if the VID/PID differs for your board,
run `udevadm info /dev/ttyACM0 | grep -E 'idVendor|idProduct'` after first connect.

---

## Comparison with Current Architecture

| Aspect | Current (Einsy + custom) | New (BTT + grblHAL) |
|--------|--------------------------|---------------------|
| Serial protocol | Custom (fragile) | GRBL (battle-tested) |
| Firmware | Custom C++ | grblHAL (community) |
| Trajectory planning | Custom sinusoidal | grblHAL built-in S-curve |
| Driver config | TMC2130 SPI (1.48A max) | TMC5160 SPI (4.7A max) |
| Max voltage | 46V | 56V |
| Axes | 4 (Einsy) + 2 (RAMPS, unwired) | 6 on one board |
| E-STOP | Serial (slow, fragile) | `!` byte + hardware pin |
| Homing | Disabled (gearbox false triggers) | StallGuard4 (tunable) |
| IK | None | ikpy on Pi |
| Custom code | ~2000 lines | ~300 lines |
| Maintenance | High | Low |
