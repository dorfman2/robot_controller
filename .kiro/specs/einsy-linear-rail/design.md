# Einsy Linear Rail (Base Slide) — Design

#[[file:requirements.md]]

## Architecture

```
Browser (Web UI)
    ↕ WebSocket (9090)
armold_controller (Pi daemon)
    ├── SerialBoard "ramps" (4 rotational joints, S42C closed-loop)
    │       ↕ USB 250000 baud (/dev/armold_ramps)
    │   RAMPS Mega 2560 → STEP/DIR → S42C → Motors → Joints J0–J3
    │
    └── SerialBoard "einsy" (1 linear axis)
            ↕ USB 115200 baud (/dev/armold_einsy)
        Einsy RAMBo 1.1a (ATmega2560 + 4× TMC2130)
            └── X-axis TMC2130 → NEMA 17 → Belt/Screw → Linear Rail
```

---

## Einsy Firmware (Single-Axis Linear)

Simplified fork of the existing Einsy firmware. Strips Y/Z/E axes, keeps X only.
Retains TMC2130 SPI initialization and StallGuard for homing.

### Key Differences from Rotational Firmware

| Aspect | Rotational (RAMPS+S42C) | Linear (Einsy) |
|--------|------------------------|----------------|
| Axes | 4 (J0–J3) | 1 (linear X) |
| Driver | S42C (STEP/DIR only) | TMC2130 (SPI configured) |
| Gearbox | 25.95:1 cycloidal | None (direct drive) |
| Units | Steps → degrees | Steps → millimeters |
| Feedback | S42C encoder (internal) | None (open-loop) |
| Homing | Not available | StallGuard sensorless |
| StallGuard | Disabled (gearbox drag) | Enabled (clean signal) |
| Current control | S42C OLED | TMC2130 SPI register |

### Pin Map (Einsy RAMBo X-axis)

```
X_STEP_PIN   = 37
X_DIR_PIN    = 49
X_ENABLE_PIN = 29
X_CS_PIN     = 41   // TMC2130 SPI chip select
X_DIAG_PIN   = PK2  // StallGuard interrupt (PCINT18)
```

### TMC2130 Initialization

```cpp
void initTMC2130() {
    // Global config: SpreadCycle mode
    driver.GCONF(0x00000000);  // spreadCycle, no stealthChop

    // Current: ~1000mA RMS (register value depends on sense resistors)
    // Einsy: 0.22Ω → irun=20 gives ~1.0A RMS
    driver.IHOLD_IRUN(/*ihold=*/8, /*irun=*/20, /*iholddelay=*/6);

    // Microstepping: 16 with interpolation to 256
    driver.CHOPCONF(/*mres=*/4, /*intpol=*/1, /*toff=*/3, /*hstrt=*/4, /*hend=*/1);

    // StallGuard threshold (tune for linear rail)
    driver.COOLCONF(/*sgt=*/4);  // Sensitivity: lower = more sensitive
    driver.TCOOLTHRS(0x000001F4);  // Enable StallGuard above this velocity

    // Enable DIAG1 output for stall detection
    driver.GCONF(driver.GCONF() | (1 << 7));  // diag1_stall = 1
}
```

### Homing Sequence

```cpp
void homeLinear() {
    // Move slowly toward endstop until StallGuard triggers
    setDirection(TOWARD_HOME);
    enableStallDetection();

    while (!stallDetected()) {
        singleStep(HOMING_DELAY);  // Slow speed for reliable detection
    }

    disableStallDetection();
    position = 0;  // Set home
    Serial.println("OK H 0");
}
```

### Serial Protocol (same as RAMPS, 1 axis)

```
E1 / E0          - Enable/disable motor
M0 <steps> <dir> <delay> - Move linear axis
S                - Query state: "S <enabled> <position>"
R                - Reset position to 0
H                - Home (StallGuard sensorless)
!                - E-STOP (halt immediately)
?                - Help
```

---

## Pi Daemon Configuration

```json
{
    "boards": {
        "ramps": {
            "port": "/dev/armold_ramps",
            "baud": 250000,
            "num_joints": 4,
            "enabled": true
        },
        "einsy": {
            "port": "/dev/armold_einsy",
            "baud": 115200,
            "num_joints": 1,
            "enabled": true
        }
    }
}
```

### Joint Mapping

The daemon presents 5 axes to the Web UI:
- Joints 0–3: Rotational (on RAMPS board)
- Joint 4: Linear rail (on Einsy board)

```python
# In motion_manager.py
NUM_JOINTS = 5

# Board mapping:
# boards["ramps"] handles joints 0-3 (offset=0)
# boards["einsy"] handles joint 4 (offset=4)
```

---

## Web UI Updates

### Linear Rail Panel

```
┌─────────────────────────────────────────────────┐
│  Linear Rail (X-axis) [Einsy TMC2130]           │
│  Position: 12500 steps (156.3mm)                │
│                                                 │
│  Jog: [-100mm] [-10mm] [-1mm] [+1mm] [+10mm] [+100mm]  │
│  [Home]                                         │
└─────────────────────────────────────────────────┘
```

- Shows position in both steps and millimeters
- Jog buttons in mm increments (converted to steps by UI)
- Home button triggers StallGuard homing sequence
- E-STOP halts both boards

### Steps/mm Configuration

The Web UI needs a `STEPS_PER_MM` constant. This depends on the mechanical setup:
- GT2 belt, 20T pulley: 80 steps/mm
- 8mm lead screw: 400 steps/mm
- 2mm lead screw: 1600 steps/mm

Set in a config constant in the HTML (user-adjustable).

---

## IK Integration (Future)

The linear rail adds a prismatic joint to the kinematic chain:

```xml
<!-- In armold.urdf — add before joint_0 -->
<joint name="joint_linear" type="prismatic">
    <parent link="world"/>
    <child link="rail_carriage"/>
    <origin xyz="0 0 0"/>
    <axis xyz="1 0 0"/>  <!-- Translation along X -->
    <limit lower="0" upper="0.5" velocity="0.1" effort="10"/>
    <!-- upper = rail length in meters (e.g., 500mm = 0.5) -->
</joint>
<link name="rail_carriage"/>

<!-- joint_0 (base yaw) parent changes from base_link to rail_carriage -->
<joint name="joint_0" type="revolute">
    <parent link="rail_carriage"/>
    ...
```

The IK solver now has 5 DOF: 1 translational + 4 rotational.
This extends the reachable workspace from a sphere to a cylinder.

---

## Comparison: System Before and After

| Feature | Before (RAMPS only) | After (RAMPS + Einsy) |
|---------|---------------------|----------------------|
| DOF | 4 rotational | 4 rotational + 1 linear |
| Workspace | Sphere (radius = arm reach) | Cylinder (arm reach × rail length) |
| Boards | 1 (RAMPS) | 2 (RAMPS + Einsy) |
| Homing | None | StallGuard on linear axis |
| Position feedback | S42C (rotational only) | S42C (rotational) + open-loop (linear) |
| E-STOP | Single board | Dual-board simultaneous |
