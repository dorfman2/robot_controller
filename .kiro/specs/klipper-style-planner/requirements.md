# Klipper-Style Motion Planner — Requirements

## Problem Statement
The current firmware computes motion profiles (trapezoidal ramp) on the ATmega2560 at 16MHz with 8-bit integer math. This limits profile quality to simple linear ramps, prevents lookahead across multiple moves, and makes trajectory changes require reflashing firmware. The Pi 4's 1.5GHz ARM Cortex-A72 is underutilized — it only dispatches high-level commands to the MCU.

## Goal
Move all motion computation (trajectory planning, S-curve profiles, multi-move lookahead, inverse kinematics) to the Raspberry Pi. The MCU becomes a precision step-timing executor — it fires GPIO pins at exact timestamps using hardware timers, performing zero math.

## Inspiration
Klipper firmware (https://github.com/klipper3d/klipper) uses this architecture for 3D printers, achieving higher print speeds and smoother motion than firmware-only solutions (Marlin). The same principles apply to robot arm control with these additions:
- Joint-space trajectory planning (not just Cartesian XYZ)
- Variable-speed S-curve profiles per joint per move
- Multi-move lookahead with junction velocity optimization
- Future: inverse kinematics computed in the planning loop

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              Raspberry Pi 4 (armold_controller)      │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  WebSocket   │  │  Trajectory  │  │  Step     │ │
│  │  Server      │  │  Planner     │  │  Scheduler│ │
│  │              │  │  (S-curve,   │  │  (serial  │ │
│  │              │  │   lookahead, │  │   batches) │ │
│  │              │  │   IK)        │  │           │ │
│  └──────────────┘  └──────┬───────┘  └─────┬─────┘ │
│                            │                │        │
└────────────────────────────┼────────────────┼────────┘
                             │                │
                    joint targets      step schedule
                                              │
                             USB Serial (1Mbps+, binary protocol)
                                              │
┌─────────────────────────────────────────────┼────────┐
│              Einsy RAMBo (MCU)              │        │
│                                              ▼        │
│  ┌─────────────────────────────────────────────────┐ │
│  │  Step Executor                                   │ │
│  │  - Ring buffer of (timestamp, joint, direction)  │ │
│  │  - Hardware timer fires steps at exact µs        │ │
│  │  - Reports buffer fill level to Pi               │ │
│  │  - E-STOP: immediate motor disable              │ │
│  └─────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

## Requirements

### R1: Pi-Side Trajectory Planner
- Compute full motion profile for each move: S-curve (7-segment) or sinusoidal
- Support configurable jerk limit (`j_max`), max acceleration (`a_max`), max velocity (`v_max`) per joint
- Multi-move lookahead buffer (10-50 moves)
- Junction velocity optimization (don't decelerate to zero between sequential moves)
- Generate a list of (timestamp, joint, direction) step events per move
- All computation in Python (with numpy/scipy for heavy math) or C extension
- Profile generation must stay ahead of execution by ≥100ms (buffer headroom)

### R2: Step Scheduler
- Convert trajectory planner output into batched serial commands
- Binary protocol: compact representation to minimize serial bandwidth
- Command format: "Execute N steps on joint J, starting at time T, with interval profile [compressed]"
- Segment-based commands (not per-step) to reduce serial traffic
- Monitor MCU buffer fill level; pause planning if buffer is full
- Handle E-STOP: send immediate halt, clear pending schedule

### R3: MCU Step Executor Firmware
- Minimal firmware: receive step schedule, execute via hardware timer
- 16-bit Timer1 or Timer3 on ATmega2560 (62.5ns resolution at 16MHz)
- Ring buffer: store ≥500ms of upcoming steps (~25,000 steps at max speed)
- Execute steps at precise timestamps (jitter < 1µs)
- Report buffer fill level to Pi every 10ms
- E-STOP: hardware pin check + serial command, immediate motor disable
- Clock synchronization with Pi (Klipper-style sync protocol)
- No motion math, no ramp computation, no G-code parsing on MCU

### R4: Communication Protocol (Pi ↔ MCU)
- Serial via ATmega32U2 USB-to-UART bridge (NOT native USB CDC)
- **Maximum reliable baud: 250,000** (ATmega32U2 bridge limits to 500Kbps theoretical, 250K practical)
- The "baud rate doesn't matter for CDC" claim does NOT apply — the 32U2→2560 link is real UART
- Known Prusa Einsy 32U2 firmware bug causes USB disconnections — flash community firmware (PrusaOwners/mk3-32u2-firmware)
- Segment-based commands to reduce bandwidth:
  ```
  MOVE_SEGMENT:
    joint: u8
    direction: u8
    start_time: u32 (µs from sync epoch)
    step_count: u16
    start_interval: u16 (µs between steps at segment start)
    end_interval: u16 (µs between steps at segment end)
    curve_type: u8 (0=linear, 1=sinusoidal, 2=cubic)
  ```
  Total: 13 bytes per segment. One move = ~4-8 segments per joint = ~50-100 bytes per move.
- Bandwidth at 250Kbaud (25,000 bytes/sec usable after framing):
  - At max speed: 4 joints × 200 segments/sec × 13 bytes = 10.4 KB/s — **fits within 250Kbaud**
  - Per-step scheduling would NOT fit (50K steps/sec × 6 bytes = 300KB/s) — Phase C requires MCU upgrade or GPIO UART bypass
- Commands: MOVE_SEGMENT, ENABLE, DISABLE, SYNC_CLOCK, QUERY_STATUS, ESTOP
- Responses: ACK, STATUS (buffer level, position, enabled), STALL, RESET
- Frame format: `[LEN][OPCODE][PAYLOAD...][CRC8]` with 0xAA sync preamble
- On CRC failure: discard frame, send NACK, Pi retransmits
- Alternative for Phase C: bypass 32U2 entirely (Pi GPIO UART → ATmega2560 UART1 direct, as Klipper recommends for Einsy)

### R5: Clock Synchronization
- Pi and MCU clocks drift relative to each other
- Klipper protocol: Pi sends periodic clock queries, measures round-trip time
- MCU reports its local timer value; Pi calculates offset and drift rate
- All step timestamps are in MCU-local time (Pi converts before sending)
- Re-sync every 1 second; drift < 1µs per sync interval at 16MHz crystal

### R6: S-Curve Motion Profile (Pi-side)
- 7-segment profile: jerk-up, constant-accel, jerk-down, cruise, jerk-down, constant-decel, jerk-up
- Parameters per joint: `v_max`, `a_max`, `j_max`
- Short moves: auto-reduce to 5 or 3 segments (skip cruise, skip constant-accel)
- Output: list of segments with start/end intervals (MCU interpolates within segment)
- Configurable: switch between sinusoidal, linear, and cubic profiles at runtime

### R7: Lookahead and Junction Velocity
- Buffer upcoming moves and compute optimal velocity at each junction
- At a junction between Move A and Move B:
  - If direction doesn't change: maintain velocity (no decel-to-zero)
  - If direction changes: decelerate to zero then accelerate
  - If angle between moves is small: reduce velocity proportionally
- This eliminates the pause between sequential jog commands
- Lookahead depth: configurable (default 10 moves)

### R8: Inverse Kinematics (Future-Ready)
- Architecture supports IK in the planning loop:
  - WebSocket receives Cartesian target (x, y, z, roll, pitch, yaw)
  - Planner computes joint targets via IK
  - Steps generated per joint as normal
- Not implemented in this spec but the pipeline supports it without architectural changes

### R9: E-STOP (Preserved)
- Same behavior as current: immediate motor disable
- Pi sends ESTOP command (1 byte, highest priority)
- MCU clears step buffer, disables all motors, responds with current position
- Latency: <1ms (MCU checks serial between every step or every N steps)
- StallGuard: disabled for now (gearbox incompatibility), re-evaluate at slower homing speeds

### R10: Backward Compatibility
- WebSocket JSON protocol unchanged (web UI doesn't need to know about the internal architecture)
- `jog`, `move`, `estop`, `enable`, `disable` commands work the same
- Position reporting still firmware-authoritative (MCU tracks steps executed)
- Speed profiles configurable via WebSocket (`set_speed` now selects profile + max velocity)

### R11: Performance Targets
- Step rate: up to 50,000 steps/sec per joint (20µs minimum interval) — Phase B
- Step rate: up to 100,000 total steps/sec across all joints — Phase C (ATmega2560 limit)
- **NOT 200,000+ steps/sec** — ATmega2560 at 16MHz cannot service per-step ISR for 4 joints at 20µs (only 80 cycles per ISR)
- Phase B avoids this: MCU interpolates within segments in its own timing loop
- Phase C at max speed: limit to 2 joints simultaneous at 20µs, or 4 joints at 40µs
- Jitter: < 1µs (hardware timer) — Phase C only; Phase B uses delayMicroseconds (5-10µs jitter acceptable)
- Profile computation: < 5ms per move (Pi has 100ms+ buffer)
- Serial latency: < 2ms per command round-trip at 250Kbaud
- Buffer underrun protection: MCU holds 500ms+ of segments (≥100 segments in ring buffer)
- GC pause tolerance: Python GC typically <10ms; 500ms buffer makes this invisible

## Constraints
- ATmega2560 @ 16MHz (same Einsy RAMBo hardware)
- **USB serial via ATmega32U2 bridge — real UART, NOT native CDC**
- Maximum reliable baud: 250,000 (not 1Mbps as previously assumed)
- Known Prusa 32U2 firmware bug — flash community fix (PrusaOwners/mk3-32u2-firmware)
- Python 3.12 on Pi (numpy available for math)
- 8KB RAM on MCU (ring buffer ~100 segments at 13 bytes = 1.3KB, plus execution state)
- Must support 4 joints simultaneously (Einsy) + 2 joints on RAMPS (future)
- 24V supply, same stepper motors and cycloidal drives
- Phase C (per-step ISR) requires MCU upgrade (STM32/RP2040) OR GPIO UART bypass of 32U2

## Migration Path
1. Implement sinusoidal lookup table on MCU as immediate improvement (interim)
2. Build Pi-side planner with segment-based protocol (Phase B — **recommended stopping point for ATmega**)
3. Rewrite MCU firmware as step executor (binary protocol, hardware timer) — only with MCU upgrade
4. Implement clock sync
5. Add lookahead and junction velocity
6. Validate with stress testing
7. Add IK (future spec)

## Success Criteria
- Visibly smoother motion compared to linear ramp (S-curve)
- No pause between sequential jog commands (lookahead)
- Step timing jitter < 1µs (measured with oscilloscope)
- Zero buffer underruns during 1-hour IK demo
- E-STOP < 1ms
- Same or better max speed as current (20µs cruise)
