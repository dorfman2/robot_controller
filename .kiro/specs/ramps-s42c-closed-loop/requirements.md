# Option D: RAMPS + BTT S42C Closed-Loop Steppers — Requirements

## Summary

A low-cost closed-loop architecture using the existing RAMPS 1.4 board as a STEP/DIR
source, with BTT S42C closed-loop driver boards on each motor. The S42C provides
position feedback and stall detection without firmware changes to RAMPS — it acts as
a drop-in replacement for open-loop A4988/TMC drivers.

4 axes (J0–J3) on RAMPS via S42C in Step mode (A4988-compatible, closed-loop internal).

---

## R1: Hardware

### BTT S42C V1.1 (× 4, one per joint)
- **MCU**: STM32G031G8U6 (Cortex-M0+, 64 MHz)
- **Encoder**: TLE5012B magnetic, 14-bit resolution (16,384 counts/rev)
- **Driver**: Dual H-bridge, 22.8 kHz PWM
- **Max current**: 1650 mA @ 12V
- **No-load current**: 620 mA @ 12V
- **Microstepping**: 1, 2, 4, 8, 16, 32, 64, 128, 256 (configurable via OLED or UART)
- **Max speed**: 2000 RPM
- **Interface modes**: Step/Dir (A4988-compatible) or UART (location mode)
- **UART baud rates**: 9600, 19200, 115200, 256000
- **Display**: 0.96" OLED for parameter tuning
- **Stall detection**: Software-based, enable/disable via register 0x14
- **PID tuning**: KP, KI, KD, KV configurable (0–1024) for both Step and UART modes
- **Flash save**: Settings persist across power cycles (register 0x18)

### RAMPS 1.4 (existing hardware)
- Arduino Mega 2560
- 4 stepper driver slots (X, Y, Z, E0) → connected to S42C STEP/DIR inputs
- 24V power rail (S42C supports this; max current limited by S42C's H-bridge)
- USB serial to Pi at 250000 baud (ATmega16U2)

### Raspberry Pi 4 (existing)
- armold_controller daemon (WebSocket 9090)
- USB serial to RAMPS for Step mode commands
- Optional: direct UART to each S42C for UART location mode (Phase 2)

---

## R2: Step Mode (Phase 1 — RAMPS as controller)

- S42C operates in A4988-compatible mode (register 0x13 = 0x33)
- RAMPS generates STEP/DIR pulses; S42C handles closed-loop correction internally
- **No firmware changes** needed on RAMPS for basic operation
- S42C compensates for missed steps using its 14-bit encoder feedback
- Motor direction configurable via S42C OLED or register 0x04
- Enable pin polarity configurable via register 0x05
- STEP rising edge minimum: 40 ns
- Microstep setting on S42C must match RAMPS firmware `steps_per_unit`
  - With 20:1 cycloidal gearbox: base microstep × 200 × 20 = steps per output revolution
  - Example: 16 microsteps → 3200 steps/motor rev → 64,000 steps/output rev → ~177.8 steps/degree

### Calibration
- One-time encoder calibration required on first power-up (1–2 minutes)
- Magnet must be centered on shaft, gap > 2mm from encoder IC
- After calibration, parameters auto-save to Flash

---

## R4: Joint Configuration (4 axes)

| Joint | RAMPS Slot | Motor | Gearbox | S42C Microstep | Steps/Output Rev | Steps/Degree |
|-------|-----------|-------|---------|----------------|-----------------|--------------|
| J0 (Base) | X | NEMA 17 | 20:1 cycloidal | 16 | 64,000 | 177.8 |
| J1 (Shoulder) | Y | NEMA 17 | 20:1 cycloidal | 16 | 64,000 | 177.8 |
| J2 (Elbow) | Z | NEMA 17 | 20:1 cycloidal | 16 | 64,000 | 177.8 |
| J3 (Wrist Pitch) | E0 | NEMA 17 | 20:1 cycloidal | 16 | 64,000 | 177.8 |

Note: With the Einsy's TMC2130 at 16 microsteps + interpolation, we measured 83,028 steps = 360°.
The S42C at 16 microsteps gives 64,000 steps/rev through the same gearbox. The difference comes from
the TMC2130's 256-step interpolation. For S42C, we can use 32 microsteps (128,000 steps/output rev = 355.6 steps/deg)
to get closer, or calibrate empirically.

---

## R5: Advantages Over Current Einsy Setup

| Feature | Einsy (current) | RAMPS + S42C |
|---------|----------------|--------------|
| Position feedback | None (open-loop) | 14-bit encoder (16,384 counts/rev) |
| Missed step recovery | No (requires re-home) | Yes (automatic compensation) |
| Stall detection | TMC2130 StallGuard (unreliable with gearbox) | Software-based stall (register 0x14) |
| Max motor current | 1.48A (0.22Ω sense resistors) | 1.65A (S42C H-bridge) |
| Configuration | SPI (firmware changes) | OLED + UART (runtime) |
| Cost per axis | ~$55 (Einsy has 4 built-in) | ~$25–35 (S42C kit with motor) |
| Microstepping | Up to 256 (TMC2130) | Up to 256 (S42C) |

---

## R6: Limitations and Constraints

- S42C max 2000 RPM — not a concern for robot arm (max ~30 RPM after gearbox)
- Max 1650 mA current — sufficient for NEMA 17 through 20:1 gearbox
- S42C UART protocol is custom — useful for initial config via OLED but not used at runtime
- Each S42C needs individual calibration on first assembly
- Magnet alignment critical — must be centered, gap > 2mm
- RAMPS Mega 2560 limited to 250,000 baud USB (same constraint as Einsy)
- 24V recommended for torque headroom (S42C supports it)

---

## R7: Success Criteria

1. Zero missed steps during 1-hour continuous operation
2. Position accuracy: ±0.5° at output shaft (vs ±1° target with open-loop)
3. Stall detection triggers E-STOP within 100ms
4. S42C parameters configurable from Pi without physical access to OLED
5. Drop-in compatibility with existing armold_controller WebSocket protocol
6. No structural modifications required — S42C mounts to existing NEMA 17 motors
