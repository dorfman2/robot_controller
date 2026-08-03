# Mesa + LinuxCNC — Alternative Path Requirements

## Goal
Industrial-grade alternative using Mesa FPGA + LinuxCNC for deterministic real-time control. Uses 6x DM542TE drivers already owned. Upgrade path if Klipper proves insufficient.

## Hardware (Partially Owned)
- DM542TE stepper drivers x6 (OWNED) — 4.2A peak, step/dir/enable, 20-50V
- Mesa 7i96S (~$240) — FPGA Ethernet, 5-axis step/dir
- Mesa 7i74 (~$160) — SPI expansion for axes 6+7
- 1x additional DM542TE for rail (~$20)
- Dedicated x86 PC (available)
- Limit switches for rail homing

Estimated cost: ~$420

## Architecture
```
PC (Debian 12 + PREEMPT_RT + LinuxCNC)
    ├── genserkins (6-DOF IK, native C, <1ms)
    ├── Trajectory planner (1ms servo loop)
    ├── armold_controller (Web UI, same interface)
    └── Vision (OAK-1 Lite)
        ↕ Ethernet (deterministic)
Mesa 7i96S + 7i74 (FPGA, 7-axis step/dir)
        ↕ Step/Dir/Enable (5V)
DM542TE x7 (external drivers, DIP switch config)
        ↕ Motor coils
NEMA 17 x7 → Cycloidal/GT2 → Joints + Rail
```

## Key Advantages Over Klipper
- Hard real-time (1ms servo loop vs best-effort)
- 10MHz+ step rate (FPGA vs ~100kHz MCU)
- Native IK in control loop (genserkins, <1ms vs ikpy 7-50ms)
- Full trajectory planner (proven CNC, not GCODE_AXIS workaround)
- Encoder-ready for closed-loop (future)
- E-STOP <1ms (FPGA digital input vs ~50ms Moonraker API)

## When to Switch
- Klipper coordinated motion is jerky or poorly synchronized
- Need <1ms control loop for dynamic applications
- Adding encoders for closed-loop control
- Vision pick-and-place needs tighter timing

## DM542TE Config
- Microstep: 16 (3200 pulses/rev, matches calibration)
- Current: ~1.5A RMS most, ~2.5A J3
- Wiring: Mesa step/dir/enable → DM542TE opto inputs (common-cathode)
- Input voltage: 24V (upgradeable to 48V)
