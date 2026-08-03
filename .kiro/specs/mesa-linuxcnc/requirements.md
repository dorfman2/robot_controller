# Mesa + LinuxCNC — Alternative Path Requirements

## Goal
Industrial-grade alternative using Mesa FPGA + LinuxCNC for deterministic real-time control. Uses 6x DM542TE drivers already owned. Upgrade path if Klipper proves insufficient.

## Hardware Selection (Revised 2026-08-02 — PCI/PCIe path)

The control PC has a free expansion slot, so a plug-in FPGA card replaces the
previously-planned Ethernet 7i96S + 7i74 combo. This is cheaper (~$300 vs ~$400),
removes the Ethernet dependency (no network stack in the servo path), and still
satisfies all requirements: 7 step/dir axes with a spare, isolated field I/O for
limits + E-stop, and encoder inputs for the future closed-loop upgrade.

### FIRST: confirm the physical slot type
Mesa splits the FPGA card by bus (otherwise identical — same FPGA, two DB25
ports, same daughter cards, same LinuxCNC driver):
- **5i25** — conventional **PCI** (32-bit legacy PCI slot), ~$89
- **6i25** — **PCIe x1** (one-lane PCI Express), ~$89

Modern x86 boxes usually have PCIe x1 and often no true PCI. Inspect the slot
before ordering, then pick the matching kit suffix: `-6I25` (PCIe) or `-5I25` (PCI).
Note: the `5i25T`/`6i25` variants require LinuxCNC 2.9.2 or newer.

### Selected: FPGA card + 7i76U + 7i85S (two daughter cards on one FPGA card)
The 5i25/6i25 exposes two DB25 ports, so two daughter cards run on one card.

- DM542TE stepper drivers x6 (OWNED) — 4.2A peak, step/dir/enable, 20-50V
- 1x additional DM542TE for the rail (~$20)
- **7I76U-6I25 Plug-N-Go kit** (6i25 PCIe + 7i76U daughter card) — ~$228
  - 7i76U: 5 step/dir (5V single-ended, drives DM542TE opto inputs directly)
    + 48 isolated field I/O + spindle encoder + isolated analog spindle
- **7I85S daughter card** (standalone, on the FPGA card's 2nd DB25 port) — ~$69
  - 8 differential step/dir + 4 encoder inputs + 1 RS-422 channel
- DB25 ribbon cable for the 2nd port — ~$5-10
- Dedicated x86 PC (available)
- Limit switch(es) for rail homing (wired to 7i76 isolated field inputs)

Estimated interface cost: ~$300-310 (add ~$20 for the 7th DM542TE)

For a PCI (not PCIe) machine, substitute the **7I76U-5I25T kit (~$208)** for the
6i25 kit above; the 7i85S and everything else are unchanged.

### Axis → hardware mapping
| Axis | Motor | Step/Dir source | Notes |
|------|-------|-----------------|-------|
| Rail | NEMA 17 | 7i76 ch 1 | limit switch → 7i76 isolated input |
| J0 Base | NEMA 17 | 7i76 ch 2 | |
| J1 Shoulder | NEMA 17 | 7i76 ch 3 | |
| J2 Elbow | NEMA 17 | 7i76 ch 4 | |
| J3 Wrist Pitch | NEMA 17 | 7i76 ch 5 | |
| J4 Wrist Roll | NEMA 17 | 7i85S ch 1 (differential) | encoder-ready |
| J5 Wrist Yaw | NEMA 17 | 7i85S ch 2 (differential) | encoder-ready |

7i85S leaves 6 spare step/dir channels and 4 encoder inputs for the future
closed-loop upgrade. E-stop chain and gripper/relay outputs use the 7i76's
remaining isolated field I/O.

### Firmware caveat (verify before ordering)
Running 7i76 + 7i85S together requires a matching FPGA bitfile. Mesa ships combo
firmwares for the 5i25/6i25 (e.g. 7i76x2, 7i76+7i85s); the pin file is selectable
in the LinuxCNC HAL config. Confirm the `5i25_7i76_7i85s` (or `6i25_...`) bitfile
exists in the hostmot2 firmware package, or is buildable, before purchase.

### Alternatives considered
- **7I85S-6I25 kit alone (~$178)** — cheapest, encoder-ready, 8 differential
  step/dir (7 used) + 4 encoders on one card. Rejected as primary: no isolated
  field I/O, so limits/E-stop would run off raw 5V GPIO on the 2nd port
  (non-isolated) or need an added breakout.
- **7I76U-6I25 kit + 2nd 7I76U (~$347)** — 10 step/dir + 96 isolated I/O, uses
  the guaranteed-stock `5i25_7i76x2` firmware. Rejected: costs more and drops the
  encoder inputs the closed-loop roadmap wants.

## Architecture
```
PC (Debian 12 + PREEMPT_RT + LinuxCNC)
    ├── genserkins (6-DOF IK, native C, <1ms)
    ├── Trajectory planner (1ms servo loop)
    ├── armold_controller (Web UI, same interface)
    └── Vision (OAK-1 Lite)
        ↕ PCIe x1 (6i25) / PCI (5i25) — deterministic DMA, no network stack
Mesa 6i25/5i25 FPGA card (two DB25 ports)
    ├── 7i76U  → 5 step/dir + 48 isolated field I/O (limits, E-stop, gripper)
    └── 7i85S  → 2 step/dir (differential) + 4 encoder inputs (future closed-loop)
        ↕ Step/Dir/Enable (5V single-ended / RS-422 differential)
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
