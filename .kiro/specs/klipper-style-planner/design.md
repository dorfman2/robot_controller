# Klipper-Style Motion Planner — Design

#[[file:requirements.md]]

## System Overview

The system splits into two distinct roles:

**Pi (Brain):** Plans trajectories, computes S-curves, optimizes junction velocities, generates step schedules, handles WebSocket clients.

**MCU (Muscle):** Executes step schedule with hardware timer precision. No math. Fires pins at timestamps.

## Pi-Side Components

### Trajectory Planner

```python
class TrajectoryPlanner:
    """Computes motion profiles and generates step schedules."""

    def __init__(self, joint_config: list[JointConfig]):
        self.joints = joint_config  # v_max, a_max, j_max per joint
        self.lookahead = MoveQueue(max_depth=20)

    def plan_move(self, current_pos, target_pos) -> list[Segment]:
        """Plan a single move with S-curve profile per joint.

        Returns list of Segments (one per ramp phase per joint).
        """
        segments = []
        for joint_idx, (start, end) in enumerate(zip(current_pos, target_pos)):
            delta = end - start
            if delta == 0:
                continue
            profile = self._compute_s_curve(joint_idx, abs(delta))
            segments.extend(self._profile_to_segments(joint_idx, delta, profile))
        return segments

    def _compute_s_curve(self, joint, distance) -> SCurveProfile:
        """Compute 7-segment S-curve for given distance and joint limits."""
        cfg = self.joints[joint]
        # Compute segment durations based on v_max, a_max, j_max
        # Handle short moves (reduce to 5 or 3 segments)
        ...

    def _profile_to_segments(self, joint, delta, profile) -> list[Segment]:
        """Convert profile into MCU segments (start_interval, end_interval, count)."""
        ...
```

### S-Curve Profile Computation

The 7-segment profile for a move of distance `D`:

```
Phase 1: Jerk up      (j = +j_max)  → acceleration increases linearly
Phase 2: Const accel  (a = a_max)   → velocity increases linearly
Phase 3: Jerk down    (j = -j_max)  → acceleration decreases to 0, velocity = v_max
Phase 4: Cruise       (v = v_max)   → constant velocity
Phase 5: Jerk down    (j = -j_max)  → deceleration increases
Phase 6: Const decel  (a = -a_max)  → velocity decreases linearly
Phase 7: Jerk up      (j = +j_max)  → deceleration decreases to 0, velocity = 0
```

Each phase maps to one MCU segment with:
- `start_interval`: µs between steps at phase start
- `end_interval`: µs between steps at phase end
- `step_count`: total steps in this phase
- `curve_type`: how MCU interpolates between start and end interval

### Lookahead and Junction Velocity

```python
class MoveQueue:
    """Buffered moves with junction velocity optimization."""

    def __init__(self, max_depth=20):
        self.moves = deque(maxlen=max_depth)

    def add_move(self, move: Move):
        self.moves.append(move)
        self._optimize_junctions()

    def _optimize_junctions(self):
        """Walk backward through queue, compute max junction velocities.

        At each junction, max velocity is limited by:
        - Cornering speed (if direction changes)
        - Deceleration distance to next junction
        - Max velocity of both adjacent moves
        """
        for i in range(len(self.moves) - 1, 0, -1):
            prev = self.moves[i-1]
            curr = self.moves[i]
            junction_v = self._compute_junction_speed(prev, curr)
            prev.exit_velocity = min(prev.exit_velocity, junction_v)
            curr.entry_velocity = min(curr.entry_velocity, junction_v)
```

This is what eliminates pauses between sequential jogs — the planner knows the next move is coming and doesn't decelerate to zero.

### Step Scheduler

```python
class StepScheduler:
    """Converts planned segments into binary commands for the MCU."""

    def __init__(self, serial_board: SerialBoard):
        self.board = serial_board
        self._mcu_clock_offset = 0  # Pi time → MCU time conversion

    def schedule_segments(self, segments: list[Segment]):
        """Encode segments as binary commands and send to MCU."""
        for seg in segments:
            mcu_time = self._pi_to_mcu_time(seg.start_time)
            cmd = struct.pack('<BbIHHHB',
                0x01,  # MOVE_SEGMENT opcode
                seg.joint | (seg.direction << 7),
                mcu_time,
                seg.step_count,
                seg.start_interval,
                seg.end_interval,
                seg.curve_type
            )
            self.board.write_raw(cmd)

    def sync_clock(self):
        """Klipper-style clock sync: measure offset and drift."""
        t1 = time.monotonic_ns()
        mcu_time = self.board.query_clock()
        t2 = time.monotonic_ns()
        rtt = t2 - t1
        self._mcu_clock_offset = mcu_time - (t1 + rtt // 2)
```

## MCU-Side Firmware

### Step Executor

The entire MCU firmware is approximately 150 lines:

```cpp
// Ring buffer of scheduled segments
struct Segment {
    uint32_t start_time;     // MCU timer ticks (62.5ns resolution)
    uint16_t step_count;     // Steps in this segment
    uint16_t start_interval; // µs at start
    uint16_t end_interval;   // µs at end
    uint8_t joint;           // Joint index (0-3)
    uint8_t direction;       // 0=forward, 1=reverse
    uint8_t curve_type;      // 0=linear, 1=sinusoidal
};

volatile Segment buffer[256];  // Ring buffer (~3KB)
volatile uint8_t buf_head = 0, buf_tail = 0;
volatile uint32_t mcu_clock = 0;  // Free-running µs counter

// Timer1 ISR — fires for each step
ISR(TIMER1_COMPA_vect) {
    // Execute current step
    // Set pin HIGH
    // Schedule pin LOW (Timer3 short delay)
    // Compute next step time from segment interval
    // If segment complete, advance to next in buffer
    // If buffer empty, stop timer (underrun protection)
}

void loop() {
    // Read serial commands into buffer
    // Report buffer level every 10ms
    // Handle E-STOP
    // Handle clock sync queries
}
```

### Interval Interpolation Within Segment

The MCU needs to smoothly transition from `start_interval` to `end_interval` over `step_count` steps. Three options:

**Linear (curve_type=0):**
```cpp
uint16_t interval = start_interval + (end_interval - start_interval) * step / step_count;
```

**Sinusoidal (curve_type=1):**
```cpp
// Lookup table: 64 entries of sin(0..π/2) scaled to 0..255
uint8_t idx = (step * 63) / step_count;
uint16_t interval = start_interval + ((end_interval - start_interval) * sin_table[idx]) >> 8;
```

**Cubic/Bézier (curve_type=2):**
```cpp
// de Casteljau with fixed-point — only if needed for ultra-smooth
```

Linear within segments is likely sufficient because the segment boundaries are already S-curve shaped (the Pi computed them). The MCU just needs to smoothly connect the dots.

## Binary Protocol

### Commands (Pi → MCU)

| Opcode | Name | Payload | Description |
|--------|------|---------|-------------|
| 0x01 | MOVE_SEGMENT | 12 bytes | Schedule a step segment |
| 0x02 | ENABLE | 1 byte (joint mask) | Enable motor drivers |
| 0x03 | DISABLE | 1 byte (joint mask) | Disable motor drivers |
| 0x04 | ESTOP | 0 bytes | Immediate halt, clear buffer |
| 0x05 | SYNC_CLOCK | 0 bytes | Request MCU clock value |
| 0x06 | QUERY_STATUS | 0 bytes | Request buffer level + position |
| 0x07 | SET_POSITION | 16 bytes (4x int32) | Override position counters |

### Responses (MCU → Pi)

| Opcode | Name | Payload | Description |
|--------|------|---------|-------------|
| 0x81 | ACK | 1 byte (cmd opcode) | Command acknowledged |
| 0x82 | STATUS | 20 bytes | Buffer level + positions + enabled |
| 0x83 | CLOCK | 4 bytes (uint32) | MCU clock value |
| 0x84 | STALL | 1 byte (joint) | StallGuard triggered (future) |
| 0x85 | UNDERRUN | 0 bytes | Buffer underrun occurred |
| 0xFF | RESET | 0 bytes | MCU reset detected |

### Bandwidth Analysis

At maximum speed (20µs/step = 50,000 steps/sec):
- Steps per joint: up to 50,000/sec
- Segments per joint: ~200/sec (each segment covers ~250 steps)
- Bytes per segment: 13
- Total bandwidth (4 joints): 4 × 200 × 13 = 10.4 KB/s
- At 115200 baud: 11.5 KB/s available — **tight but feasible**
- At 500Kbps: 50 KB/s available — comfortable
- At 1Mbps (USB CDC): 100+ KB/s — plenty of headroom

### Recommendation: Start at 115200, upgrade if needed

For the current max speed (20µs, 4 joints), 115200 baud works if segments average 250+ steps. If we push to 10µs steps, upgrade to 500Kbps or 1Mbps.

## Clock Synchronization

```
Pi                          MCU
 │                           │
 │──── SYNC_CLOCK ──────────►│
 │                           │ (read Timer1 value)
 │◄──── CLOCK(T_mcu) ───────│
 │                           │
 │  RTT = t_received - t_sent
 │  offset = T_mcu - (t_sent + RTT/2)
 │                           │
 │  (repeat every 1 second)  │
```

MCU maintains a free-running 32-bit µs counter (Timer0 overflow ISR). Pi measures offset and drift rate. All scheduled timestamps are in MCU-local time.

## E-STOP Flow (Preserved)

```
User clicks E-STOP
  → WebSocket: {"cmd": "estop"}
  → armold_controller: scheduler.estop()
  → Serial: 0x04 (ESTOP opcode, 1 byte)
  → MCU: clears ring buffer, disables motors, stops timer
  → MCU responds: STATUS with current position
  → Pi updates position, broadcasts halt to clients
  → Latency: <1ms (single byte, highest priority in MCU serial read)
```

## Comparison with Current Architecture

| Aspect | Current (MCU ramp) | Klipper-Style (Pi planner) |
|--------|-------------------|---------------------------|
| Profile quality | Linear ramp | Full S-curve / sinusoidal |
| Computation | ATmega 16MHz 8-bit | Pi ARM 1.5GHz 64-bit |
| Lookahead | None (1 move) | 10-50 moves |
| Junction velocity | Always decel to 0 | Optimized (smooth transitions) |
| Step timing | `delayMicroseconds()` | Hardware timer (< 1µs jitter) |
| Multi-axis sync | Bresenham (approx) | Independent timestamps (exact) |
| Profile changes | Reflash firmware | Edit Python config |
| IK support | None | Architecture-ready |
| Firmware complexity | ~300 lines | ~150 lines |
| Serial protocol | ASCII text | Binary (compact) |

## Phase Approach

### Phase A: Sinusoidal Lookup (Immediate, minimal change)
- Add sin table to current firmware's `rampDelay()`
- Smoother now, no architecture change
- 30 minutes of work

### Phase B: Segment-Based Protocol (Medium effort)
- Pi computes S-curve, sends segment commands (start/end interval + count)
- MCU interpolates within segments using lookup table
- Hybrid: Pi does the hard math, MCU does simple interpolation
- Keeps current ASCII serial (add `X` command for segments)
- 1-2 days of work

### Phase C: Full Klipper-Style (Major rewrite)
- Binary protocol, hardware timer, clock sync
- Ring buffer on MCU, step-precise timing
- Full lookahead on Pi
- 1-2 weeks of work

### Recommendation
Start with Phase A (immediate smoothness gain), then Phase B (Pi-side planning without MCU rewrite). Only move to Phase C if Phase B's timing precision isn't sufficient or if you need >100kHz step rates.

---

## Edge Cases & Race Conditions

### USB/Serial Bandwidth Reality

The Einsy RAMBo communication path is NOT native USB CDC:
```
Pi USB Host → ATmega32U2 (USB-to-UART bridge firmware) → Hardware UART → ATmega2560
```

- The baud rate is **real** (not virtual) — 32U2 bridges USB packets to UART at the configured baud
- Maximum reliable: **250,000 baud** (Klipper's standard for ATmega2560 boards)
- Usable throughput at 250K: ~20,000 bytes/sec after framing overhead
- Phase B segment protocol: 10.4 KB/s at max speed — **fits comfortably**
- Phase C per-step: 300 KB/s needed — **does NOT fit**, requires GPIO UART bypass or MCU upgrade
- Known bug: Prusa factory 32U2 firmware causes USB disconnections. Fix: flash community firmware

### Race Condition: Timer ISR vs Serial ISR

**Scenario:** MCU Timer1 fires step ISR. Simultaneously, UART RX interrupt fires for incoming segment data.

**Risk:** One ISR delays the other. If Timer ISR takes too long (>5µs), serial bytes lost from 64-byte FIFO.

**Mitigation:**
- Timer ISR is minimal: set pin, load next compare value, advance segment counter (<3µs)
- Serial parsing happens in `loop()`, not in ISR
- Ring buffer decouples reception from execution
- Same architecture Klipper uses successfully at 250Kbaud on ATmega2560

### Race Condition: Buffer Underrun During Python GC

**Scenario:** Python garbage collector pauses 10-50ms. No segments sent during pause. MCU buffer drains.

**Risk:** Motors stutter or halt mid-move.

**Mitigation:**
- MCU holds 500ms+ of segments (100 segments × ~5ms each)
- Pi pre-computes full moves before sending (no real-time dependency)
- Python GC is typically <10ms; with 500ms buffer this is invisible
- Optional: `gc.disable()` during critical planning sections
- MCU behavior on underrun: complete current segment, hold position, report UNDERRUN

### Race Condition: E-STOP During Timer ISR Execution

**Scenario:** E-STOP byte arrives while Timer ISR is firing steps.

**Risk:** MCU continues stepping until ISR exits and serial is checked.

**Mitigation:**
- Check serial ESTOP flag in Timer ISR every 16 steps (same as current firmware)
- Worst case latency: 16 × step_interval = 16 × 20µs = 320µs
- Alternative (Phase C): dedicated GPIO pin from Pi for hardware E-STOP (instant, no serial)

### Edge Case: Segment Boundary Velocity Discontinuity

**Scenario:** Pi sends segment N ending at 30µs interval, segment N+1 starting at 25µs interval.

**Risk:** Motor experiences sudden speed jump at boundary → vibration/jerk.

**Mitigation:**
- Planner MUST enforce: `segment[N].end_interval == segment[N+1].start_interval`
- Validation in scheduler before sending (reject mismatched segments)
- S-curve computation inherently guarantees this (adjacent phases share velocity)

### Edge Case: Multi-Joint Segment Duration Mismatch

**Scenario:** Move requires J0 to travel 90° and J1 to travel 5°. J1's segment finishes in 200ms, J0's takes 2000ms.

**Risk:** If next move starts J1 before J0 finishes, coordination breaks.

**Mitigation:**
- All joints' segments for one move phase have the SAME time duration
- Pi computes: "this phase is 500ms, J0 does 10,000 steps, J1 does 500 steps"
- Segments are time-synchronized, not step-count-synchronized
- This is how Klipper coordinates multiple axes

### Edge Case: Binary Protocol Desync

**Scenario:** A byte is lost or corrupted. MCU misinterprets next opcode as data.

**Risk:** Garbage command executed — wrong joint, wrong speed.

**Mitigation:**
- CRC-8 on every frame (1 byte overhead)
- Length-prefixed framing: `[0xAA][LEN][OPCODE][PAYLOAD...][CRC8]`
- On CRC failure: discard frame, send NACK, Pi retransmits
- MCU validates all fields (joint < NUM_JOINTS, interval >= MIN_INTERVAL)
- Phase B alternative: keep ASCII protocol with newline framing (simpler, proven)

### Edge Case: Pi Restart While MCU Has Buffered Segments

**Scenario:** Pi crashes. MCU continues executing buffered segments for 500ms. Pi restarts, reconnects.

**Risk:** Pi doesn't know MCU's current position (advanced during disconnection).

**Mitigation:**
- On reconnect: Pi sends QUERY_STATUS before any commands
- MCU responds with actual position (tracked from executed steps)
- Pi syncs internal state from response
- Buffered segments complete naturally (motor stops at end of buffer)
- No unrecoverable state possible

### Edge Case: Move Canceled Mid-Segment (E-STOP or Replan)

**Scenario:** 10 segments buffered. After 3 complete, E-STOP fires mid-segment-4.

**Risk:** Pi needs to know exactly where motor stopped (partial segment progress).

**Mitigation:**
- MCU tracks `steps_executed_in_current_segment` in Timer ISR
- On ESTOP: respond with position including partial segment
- `position = sum(completed_segments) + partial_steps_in_current`
- Pi uses this for accurate position sync after halt

### Edge Case: ATmega2560 CPU Saturation at High Step Rates

**Scenario:** 4 joints × 50,000 steps/sec = 200,000 ISR/sec. At 16MHz = 80 cycles per ISR.

**Risk:** ISR can't complete in time → missed steps, timing jitter, lockup.

**Mitigation (Phase B):**
- MCU does NOT use per-step ISR — it runs a segment interpolation loop in `loop()`
- Uses `delayMicroseconds()` for timing (same as current firmware)
- One pass through the loop handles all joints (Bresenham within segment)
- No ISR saturation because there's no ISR per step

**Mitigation (Phase C — future, with MCU upgrade):**
- Upgrade to STM32F4 or RP2040 (100+ MHz, 32-bit)
- Or: use single master timer, multiplex all joints per tick (Klipper approach)
- Or: limit simultaneous max-speed joints to 2

### Edge Case: Clock Drift (Phase C Only)

**Scenario:** Pi timestamps drift from MCU clock. Over 5-second move, 50µs error.

**Risk:** Steps fire early/late by one step interval.

**Mitigation:**
- Irrelevant for Phase B (MCU manages its own timing internally)
- Phase C: re-sync every 1 second. ATmega crystal = 16MHz ±50ppm = max 50µs drift per second
- Klipper handles this successfully with same hardware

---

## Revised Phase Recommendations

| Phase | Effort | Benefit | Bandwidth Need | MCU Requirement |
|-------|--------|---------|----------------|-----------------|
| A (sin table) | 30 min | Smoother ramp shape | Same as now | ATmega2560 ✓ |
| B (segments) | 1-2 days | S-curve + lookahead + junction velocity | 10 KB/s @ 250Kbaud ✓ | ATmega2560 ✓ |
| C (per-step) | 1-2 weeks | Hardware timer precision, 100kHz+ | 300 KB/s — needs GPIO bypass | ATmega2560 marginal, prefer STM32 |

**Phase B is the recommended endpoint for current hardware.** It gives 95% of Klipper's benefit without hitting ATmega2560 limitations.
