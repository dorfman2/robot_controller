# Option D: RAMPS + BTT S42C Closed-Loop Steppers — Design

#[[file:requirements.md]]

## System Overview

Pi sends commands to RAMPS via USB serial. RAMPS generates STEP/DIR pulses.
S42C receives pulses and drives the motor with closed-loop correction. The S42C
acts as an intelligent drop-in for A4988 — no RAMPS firmware changes needed beyond
`steps_per_unit` calibration. IK runs on the Pi (ikpy), converts Cartesian targets
to joint angles, then to step counts sent through the existing segment protocol.

---

## Architecture Diagram

```
Browser (Web UI)
    ↕ WebSocket (9090)
armold_controller (Pi daemon)
    ├── SerialBoard (USB serial to RAMPS, 250000 baud)
    ├── MotionManager (trajectory planning, sinusoidal ramp)
    ├── IK solver (ikpy — Cartesian → joint angles)
    └── WebSocket server
            ↕ USB (/dev/armold_ramps)
Arduino Mega 2560 (RAMPS 1.4)
    ├── Custom firmware (STEP/DIR generation, segment protocol)
    └── 4× STEP/DIR outputs
            ↕ STEP/DIR wires
BTT S42C × 4 (closed-loop driver boards)
    ├── TLE5012B encoder (14-bit, magnetic)
    ├── PID loop (compensates missed steps internally)
    ├── Stall detection
    └── Dual H-bridge motor driver
            ↕ Motor wires (4-pin)
NEMA 17 × 4 → 20:1 Cycloidal → Joints J0–J3
```

---

## RAMPS Firmware Design

The existing Einsy firmware is nearly compatible. Key differences:

| Setting | Einsy (current) | RAMPS + S42C |
|---------|----------------|--------------|
| Driver type | TMC2130 SPI | A4988-compatible (STEP/DIR only) |
| Enable logic | Active LOW (SPI) | Active LOW (hardware pin) |
| Microstepping | 16 (SPI config) | 16 (S42C OLED/UART config) |
| StallGuard | SPI register | S42C internal (not readable from RAMPS) |
| Current control | SPI register | S42C OLED/UART (register 0x02) |

Firmware simplification:
- Remove all TMC2130 SPI code
- Remove StallGuard/stallguard threshold logic
- Keep: sinusoidal ramp, segment protocol, STEP/DIR generation
- Keep: E-STOP via serial `!` byte
- Add: status reporting of commanded position (S42C tracks actual position internally)

### S42C Configuration (per motor)

Set via OLED menu on each S42C during initial setup:

```
Mode:       Step Mode (0x33)
Microstep:  16 (or 32 for higher resolution)
Current:    High (or Very High for joints under load)
Direction:  Normal (flip per joint if needed)
Enable Pin: Normal (active LOW, matches RAMPS)
Stall:      Enable
Save:       Flash
```

### Calibration Procedure

1. Power on S42C with motor connected (no load on gearbox)
2. Navigate OLED: Home → Calibration → Confirm (long press KEY0)
3. Motor rotates through full range for encoder mapping (~1–2 minutes)
4. Calibration auto-saves to Flash
5. Repeat for each S42C unit
6. Verify: OLED Home screen shows stable angle reading when motor shaft is rotated

### Wiring

```
RAMPS X-axis header → S42C #1 (J0 Base)
  Pin 1: STEP  → S42C STEP input
  Pin 2: DIR   → S42C DIR input
  Pin 3: EN    → S42C EN input
  Pin 4: GND   → S42C GND

RAMPS Y-axis header → S42C #2 (J1 Shoulder)
RAMPS Z-axis header → S42C #3 (J2 Elbow)
RAMPS E0-axis header → S42C #4 (J3 Wrist Pitch)

Power: 24V PSU → S42C VM input (all 4 in parallel)
Motor: S42C motor output → NEMA 17 (4-wire, check phase order)
```

---

## IK Integration

IK runs on the Pi identically to the BTT grblHAL spec. The pipeline is:

```
Target XYZ → ikpy (URDF chain) → joint angles (degrees) → steps → RAMPS segment protocol → S42C → motor
```

The existing URDF (`armold.urdf`), ikpy chain, home pose, and joint limits all apply unchanged.
The only difference from grblHAL is the output format: instead of G-code (`G1 X0 Y-30 Z70 ...`),
the Pi sends step-based segment commands to RAMPS.

```python
def ik_to_steps(target_xyz, current_joints):
    """IK solve → convert to RAMPS step commands."""
    angles = inverse_kinematics(target_xyz[0], target_xyz[1], target_xyz[2])
    if angles is None:
        return None  # No solution — don't move

    steps = []
    for i, deg in enumerate(angles[:4]):  # 4 axes only
        step_count = int(deg * STEPS_PER_DEGREE)
        steps.append(step_count)

    return steps  # Send via segment protocol to RAMPS
```

**4-DOF IK constraint**: With joints J0–J3, the arm has 4 degrees of freedom
(base yaw + 3 pitch joints). This is sufficient for:
- Reaching any XYZ position within the workspace
- Controlling tool pitch angle
- Pick-and-place operations

Full 6-DOF orientation control requires adding J4 (wrist yaw) and J5 (wrist roll) later.

---

## Comparison with Other Options

| Aspect | Option C (Einsy) | Option D (RAMPS+S42C) | Option A (BTT+grblHAL) |
|--------|-----------------|----------------------|------------------------|
| Position feedback | None | 14-bit per motor | None (open-loop) |
| Missed step recovery | No | Yes (automatic) | No |
| Stall detection | TMC2130 (unreliable) | S42C internal | TMC5160 StallGuard4 |
| IK support | Yes (Pi-side) | Yes (Pi-side) | Yes (Pi-side) |
| Motion planning | Pi (sinusoidal) | Pi (sinusoidal) | grblHAL (S-curve) |
| Multi-axis coordination | Custom segment | Custom segment | Built-in G-code |
| Max axes | 4 (Einsy) | 4 (RAMPS) | 6 (Octopus MAX EZ) |
| Cost (new hardware) | $0 (existing) | ~$100-140 (4× S42C) | ~$145-165 (BTT + drivers) |
| Extra hardware needed | None | None (uses existing RAMPS) | New board + drivers |

---

## Key Design Decisions

1. **Step mode only**: No UART mode, no extra USB-serial adapters needed.
   S42C adds closed-loop correction silently behind the RAMPS STEP/DIR interface.

2. **S42C behaves like A4988**: The existing RAMPS firmware architecture
   (sinusoidal ramp, segment protocol) works unchanged. S42C corrects internally.

3. **Stall detection replaces StallGuard**: The S42C's encoder-based stall detection
   should work through the cycloidal gearbox (unlike TMC2130 StallGuard which failed
   due to gearbox drag). The encoder sees actual shaft position, not back-EMF.

4. **14-bit encoder through 20:1 gearbox**: Output resolution = 16,384 × 20 = 327,680
   counts per output revolution = 910 counts per degree. Far exceeds our ±1mm target.

5. **IK on Pi**: Same ikpy + URDF approach as grblHAL spec. Output goes to RAMPS
   step commands instead of G-code. 4-DOF IK for position + pitch orientation.

6. **24V supply**: Same PSU as current setup. S42C's 1650mA max is adequate for
   NEMA 17 motors through cycloidal gearboxes.
