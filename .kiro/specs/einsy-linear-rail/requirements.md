# Einsy Linear Rail (Base Slide) — Requirements

## Summary

Repurpose the Einsy RAMBo 1.1a board's X-axis TMC2130 driver to power a stepper
motor on a linear rail. This slides the entire robot arm base along a track,
adding a translational degree of freedom (linear X) to the existing 4-DOF
rotational arm. The RAMPS + S42C closed-loop system continues driving J0–J3
unchanged.

---

## R1: Hardware

### Einsy RAMBo 1.1a (existing, currently unused)
- **TMC2130 X-axis driver**: SPI-controlled, 1.48A max (0.22Ω sense resistors)
- **Mode**: SpreadCycle (better dynamic torque for linear motion)
- **Microstepping**: 16 with 256 interpolation
- **Current**: 800–1200 mA RMS (tune for the specific motor)
- **Serial port (Mac)**: `/dev/cu.usbmodem1101`
- **Serial port (Pi)**: `/dev/armold_einsy` (udev symlink)
- **Baud**: 115200 (ATmega32U2 USB bridge — NOT native CDC)

### Linear Rail
- Standard NEMA 17 stepper motor (no gearbox — direct drive)
- GT2 belt + pulley or lead screw for linear-to-rotary conversion
- Steps/mm depends on pulley/screw pitch:
  - GT2 (20T pulley): 1 rev = 40mm travel → 16 microsteps × 200 steps = 3200 steps/40mm = 80 steps/mm
  - Lead screw (8mm pitch): 1 rev = 8mm travel → 3200 steps/8mm = 400 steps/mm
  - Lead screw (2mm pitch): 1 rev = 2mm travel → 3200 steps/2mm = 1600 steps/mm
- Travel length: TBD (depends on rail purchased)
- Endstops: optional (StallGuard sensorless homing may work without gearbox)

### Raspberry Pi 4 (existing)
- armold_controller daemon connects to BOTH boards:
  - `/dev/armold_ramps` (250000 baud) — rotational joints J0–J3
  - `/dev/armold_einsy` (115200 baud) — linear rail X-axis
- WebSocket server on port 9090

---

## R2: Motion Control

- Einsy firmware controls a single axis (X) for linear translation
- Uses existing TMC2130 SPI configuration (current, microstepping, SpreadCycle)
- Sinusoidal acceleration ramp (same profile as RAMPS firmware)
- Serial command protocol identical to RAMPS firmware (M, G, X, S, E, R, !)
  - Only 1 joint defined (the linear axis)
  - `M0 <steps> <dir> <delay>` — move linear axis
  - `E1/E0` — enable/disable motor
  - `S` — query state
  - `!` — E-STOP
- No gearbox: steps/mm is constant and exact (no empirical calibration needed)
- StallGuard sensorless homing is viable (no gearbox drag to cause false triggers)

### Soft Limits
- Maximum travel defined by rail length
- Home position (0) at one end of rail
- Soft limit at maximum travel length
- Example: 500mm rail → 0 to 500mm → 0 to 40,000 steps (at 80 steps/mm with GT2)

---

## R3: Coordination with RAMPS

- Pi daemon manages both boards independently
- Linear rail moves can happen simultaneously with arm joint moves
- Coordinated motion: Pi plans trajectory, sends commands to both boards
- E-STOP halts both boards simultaneously (Pi sends `!` to each)

### Motion Planning
- Simple: linear rail + arm joints move independently (point-to-point)
- Advanced: Pi coordinates rail position + arm IK for extended workspace
  - IK solver accounts for rail offset when computing tool tip position
  - URDF adds a prismatic joint at the base (Z-up → X-axis translation)

---

## R4: TMC2130 Configuration

Using existing validated settings from the Einsy firmware:

| Setting | Value | Rationale |
|---------|-------|-----------|
| Current | 800–1200 mA RMS | Tune for specific motor (no gearbox = direct load) |
| Microsteps | 16 + interpolation to 256 | Smooth linear motion |
| Mode | SpreadCycle | Dynamic torque for acceleration/deceleration |
| StallGuard | Enabled (sgt=4, tune) | Sensorless homing viable without gearbox |
| Cruise delay | 40–80 µs | Adjust for desired linear speed |
| Accel/Decel | 300 steps | Sinusoidal S-curve profile |
| Start delay | 600 µs | Conservative start |

### StallGuard Homing
- Unlike the rotational joints (where cycloidal gearbox caused false triggers),
  a direct-drive linear rail has clean back-EMF signal
- StallGuard can reliably detect end-of-travel contact
- Homing sequence: slow move toward endstop → StallGuard triggers → set position to 0
- Command: `H` (home) — new firmware command

---

## R5: Advantages

- **Extended workspace**: Arm can reach positions along the entire rail
- **Zero additional cost**: Einsy board is already owned and idle
- **Proven driver**: TMC2130 SPI with StealthChop/SpreadCycle, well understood
- **Sensorless homing**: No endstop switches needed (StallGuard works on linear)
- **Independent operation**: Rail failure doesn't affect arm (separate boards)

---

## R6: Constraints

- Einsy USB is NOT native CDC (ATmega32U2 bridge) — max reliable baud: 115200
- Only 1 axis used on the Einsy (X) — Y, Z, E0 drivers are unused
- TMC2130 max current: 1.48A (adequate for most NEMA 17 on linear rail)
- Einsy doesn't reset on USB serial open (ATmega32U2 issue) — daemon uses fallback sync
- Linear rail introduces new failure mode: belt skip / lead screw binding
- No closed-loop feedback on linear axis (open-loop, unlike S42C rotational joints)

---

## R7: Success Criteria

1. Linear rail moves smoothly across full travel range
2. Position accuracy: ±0.1mm (achievable with direct-drive stepper)
3. StallGuard homing repeatable to ±0.5mm
4. E-STOP halts both linear rail and arm joints simultaneously
5. Web UI shows linear position and provides jog controls
6. No interference between Einsy and RAMPS serial communication
7. IK solver can incorporate rail position for extended workspace
