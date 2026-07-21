# Armold Motion Controller Architecture Analysis

## Date: July 2026
## Author: Jeffrey Dorfman

---

## Problem Statement

The custom Python daemon (`armold_controller`) communicating with the Einsy RAMBo over USB serial has proven unreliable. Root causes:

- Serial protocol race conditions (response collisions, timeouts)
- Position state desync between Pi and firmware after crashes
- E-STOP triggering false positives (StallGuard incompatible with cycloidal gearbox at all sensitivity levels)
- USB serial bandwidth limitations (ATmega32U2 bridge, max 250Kbaud)
- No real-time guarantees on the Pi (Python GC pauses, asyncio scheduling)
- Blocking serial I/O in the motion path causing cascade failures

**The fundamental issue:** Custom firmware + custom serial protocol + custom daemon = too many untested integration points.

---

## Current Hardware

| Component | Role | Status |
|-----------|------|--------|
| Einsy RAMBo 1.1a | Motor controller (4x TMC2130 SPI) | Working, but serial interface fragile |
| RAMPS 1.4 + Mega 2560 | Secondary controller (joints 4-5) | Not yet wired |
| Raspberry Pi 4 (4GB) | Daemon host, web server | Working |
| NEMA 17 steppers | 5x motors through 20:1 cycloidal drives | Working |
| 24V / 10A PSU | Power | Working |
| TMC2130 (Einsy onboard) | Stepper drivers (SPI controlled) | Working |

## Current Software

| Layer | Implementation | Issue |
|-------|----------------|-------|
| Web UI | Native WebSocket + JSON | Works well |
| Daemon | Python asyncio + serial threads | Crashes, race conditions |
| Firmware | Custom C++ (ATmega2560) | Serial protocol fragile |
| IK | None | Not yet implemented |
| Trajectory planning | Sinusoidal ramp + segment protocol | Works but brittle |

---

## Options Evaluated

### Option A: grblHAL on BTT Octopus MAX EZ

**Concept:** Replace all custom firmware with proven CNC motion control firmware. Pi just sends G-code.

```
Pi (Web UI + IK) → USB Serial → BTT Octopus MAX EZ (grblHAL) → STEP/DIR → TMC2209 → Motors
```

**Hardware:**
- BTT Octopus MAX EZ (~$55) — STM32H723 ARM Cortex-M7, 550MHz, 10 driver slots
- BTT EZ2209 drivers × 7 (~$49) — Plug-in, UART pre-routed on board
- USB-C to Pi (native, not a UART bridge)

**Software:**
- grblHAL firmware (proven, millions of installs across CNC community)
- Pi sends standard G-code over serial (`G1 X90 Y45 F1000`)
- Response is simple: `ok` or `error:N`
- S-curve acceleration built into grblHAL
- Trinamic plugin handles StallGuard/sensorless homing
- Up to 6 axes natively (8 with STM32F7 fork)

**Pros:**
- Eliminates all custom serial protocol issues
- G-code is battle-tested (decades of CNC use)
- Built-in trajectory planning, lookahead, jerk limiting
- StallGuard handled by firmware's Trinamic plugin
- No custom firmware to maintain
- Native USB (not UART bridge) — no baud rate limitation
- Hardware E-STOP pin (not serial)

**Cons:**
- New board + drivers purchase (~$110)
- grblHAL max 6 axes on ESP32, need STM32 for 7+
- No native IK (need Pi-side solver feeding G-code)
- Learning curve for grblHAL configuration

**Cost:** ~$110
**Effort:** 1-2 days to configure + integrate
**Reliability:** High (proven firmware, simple protocol)

---

### Option B: Mesa 7i96S + LinuxCNC

**Concept:** Industrial-grade FPGA step generator with real-time Linux motion control, including built-in 6-axis IK via `genserkins`.

```
Pi (LinuxCNC + PREEMPT_RT) → Ethernet → Mesa 7i96S (FPGA) → STEP/DIR → Drivers → Motors
```

**Hardware:**
- Mesa 7i96S (~$240) — FPGA Ethernet controller, 5 axes step/dir
- For 7 axes: Mesa 7i96S + Mesa 7i74 expansion (~$400 total)
- Keep existing TMC2130 drivers (or add external drivers)

**Software:**
- LinuxCNC (25+ years of industrial use)
- `genserkins` — built-in 6-axis DH-parameter inverse kinematics
- Full trajectory planning with jerk limiting and lookahead
- Real-time kernel (PREEMPT_RT) for deterministic timing
- HAL (Hardware Abstraction Layer) for I/O routing
- Web UI options: Probe Basic, or custom via Python API

**Pros:**
- Industrial reliability — used in real machine shops
- Built-in IK (`genserkins` — just define DH parameters)
- FPGA generates steps at MHz precision — zero jitter
- Ethernet communication — no USB/serial issues
- E-STOP is hardware relay (instant, not software)
- Full closed-loop support if you add encoders later
- Handles 6+ axes natively

**Cons:**
- Expensive controller (~$240-400)
- Requires PREEMPT_RT kernel on Pi (custom kernel build)
- Steeper learning curve (HAL configuration, INI files)
- No native web UI (need custom frontend or use Probe Basic)
- Overkill for 750g payload arm

**Cost:** ~$240-400
**Effort:** 3-5 days to configure + kernel setup
**Reliability:** Very high (FPGA timing, industrial-proven)

---

### Option C: Keep Einsy + Fix Serial Issues (Current Path)

**Concept:** Improve the existing custom daemon and firmware. Add IK as a Pi-side library. Fix the identified serial reliability issues.

```
Pi (Web UI + IK + Daemon) → USB Serial (250Kbaud) → Einsy RAMBo (Custom Firmware) → TMC2130 → Motors
```

**Hardware:** No changes needed.

**Software fixes applied/planned:**
- ✅ Sinusoidal S-curve ramp (eliminates jerk)
- ✅ Segment protocol (Pi plans, MCU interpolates)
- ✅ Serial E-STOP removed from stepping loop (false trigger fix)
- ✅ StallGuard disabled (incompatible with gearbox)
- ✅ Position sync on reconnect
- ✅ Firmware reset detection
- 🔲 Add IK library (ikpy or Pinocchio) on Pi
- 🔲 Improve serial robustness (CRC framing, better error recovery)
- 🔲 Add RAMPS as second board for joints 4-5

**Future upgrade path to Option A or B:**
- IK code stays the same (just changes output from serial commands to G-code)
- Web UI stays the same (already decoupled from hardware)
- Only the hardware interface layer changes

**Pros:**
- No hardware purchase needed
- Familiar codebase
- Incremental improvement
- IK integration straightforward (Python library on Pi)
- Web UI already working

**Cons:**
- Serial reliability issues persist (250Kbaud limit, ATmega32U2 bridge quirks)
- No hardware E-STOP (serial only)
- Custom firmware maintenance burden
- StallGuard unusable (gearbox incompatibility)
- Open-loop only (no encoder support on Einsy without significant rework)

**Cost:** $0
**Effort:** Ongoing maintenance + 1 day for IK integration
**Reliability:** Medium (improved but fundamentally limited by serial architecture)

---

## IK Integration (All Options)

Regardless of motion controller choice, IK lives on the Pi:

### Recommended Library: ikpy (simplest) or Pinocchio (fastest)

**ikpy** — Pure Python, 100 lines to solve:
```python
import ikpy
chain = ikpy.chain.Chain.from_urdf_file("armold.urdf")
joint_angles = chain.inverse_kinematics(target_position, target_orientation)
```

**Pinocchio** — C++ with Python bindings, microsecond solves:
```python
import pinochio as pin
model = pin.buildModelFromUrdf("armold.urdf")
data = model.createData()
q = pin.computeFrameIK(model, data, frame_id, target_SE3, q_init)
```

### IK Output → Motion Controller

| Option | IK Output | How It's Sent |
|--------|-----------|---------------|
| A (grblHAL) | Joint angles → G-code | `G1 A90 B45 C30 F1000\n` |
| B (LinuxCNC) | Joint angles via genserkins | HAL pins (automatic) |
| C (Current) | Joint angles → step targets | `G 20757 10378 6919 0 30\n` |

The IK computation is identical in all cases. Only the delivery mechanism changes.

---

## ROS 2 Integration (Future)

ROS 2 Jazzy is already installed on the Pi. Future integration path:

```
Mac (RViz visualization, MoveIt planning) ← WiFi/DDS → Pi (ROS 2 nodes)
                                                              │
                                                    ros2_control
                                                              │
                                              Hardware driver (G-code or HAL)
                                                              │
                                              Motion controller (grblHAL/Mesa/Einsy)
```

- **MoveIt** handles collision avoidance, complex path planning
- **ros2_control** provides hardware abstraction
- **Pi 4** can run MoveIt (2-5s per plan, acceptable for pick-and-place)
- **Not used for real-time motor control** — that stays on dedicated hardware
- **RViz runs on Mac** (needs GPU, Pi can't handle 3D rendering)

---

## Comparison Matrix

| Criteria | Option A (grblHAL) | Option B (Mesa/LinuxCNC) | Option C (Current) |
|----------|--------------------|--------------------------|--------------------|
| **Reliability** | High | Very High | Medium |
| **Cost** | ~$110 | ~$240-400 | $0 |
| **Setup effort** | 1-2 days | 3-5 days | 0 (already running) |
| **IK support** | Pi-side library | Built-in (genserkins) | Pi-side library |
| **Max axes** | 6-8 | 6+ (expandable) | 4 (Einsy) + 2 (RAMPS) |
| **Step precision** | <1µs (STM32 timer) | <100ns (FPGA) | ~5-20µs (software loop) |
| **E-STOP** | Hardware pin | Hardware relay | Serial (slow) |
| **Closed-loop support** | Via STEP/DIR to CL drivers | Full encoder feedback | Not practical |
| **Communication** | USB native (no baud limit) | Ethernet (no serial issues) | USB serial (250Kbaud, fragile) |
| **Web UI** | Custom (keep existing) | Probe Basic or custom | Existing (working) |
| **Firmware maintenance** | None (community maintained) | None (community maintained) | Ongoing (custom) |
| **StallGuard/Homing** | grblHAL Trinamic plugin | HAL + Mesa I/O | Broken (gearbox false triggers) |
| **Trajectory planning** | Built-in S-curve + lookahead | Full jerk-limited + lookahead | Custom sinusoidal ramp |
| **Community** | Large CNC community | Large CNC/industrial community | Just us |
| **Future-proofing** | Good (standard G-code) | Excellent (industrial standard) | Limited |

---

## Recommended Path

### Now: Option C (fix what we have)
- Add IK via ikpy/Pinocchio
- Continue improving serial robustness
- Complete RAMPS wiring for joints 4-5
- Run the arm, characterize limitations

### Next (when serial issues block progress): Option A (grblHAL)
- Order BTT Octopus MAX EZ + EZ2209 drivers ($110)
- Flash grblHAL, configure for 6-7 axes
- Pi sends G-code — eliminates all custom serial protocol
- Keep web UI, add IK, done
- **This solves the reliability problem permanently for ~$110**

### Future (if you want industrial precision): Option B (Mesa + LinuxCNC)
- For closed-loop operation with encoders
- For sub-microsecond step timing
- For built-in IK via genserkins
- When the arm moves from prototype to production tool

---

## Motor Recommendations (for future closed-loop upgrade)

### Keep Existing Open-Loop Motors (Option C now, Option A later)
Your current NEMA 17 motors through 20:1 cycloidal drives produce enough torque. Open-loop is fine when the motion controller is reliable.

### Future Closed-Loop Options

| Approach | Cost (7 axes) | Body Length | Fits Current Frame? |
|----------|---------------|-------------|---------------------|
| Existing motors + external encoders on output shaft | ~$105 | No change | ✓ Yes |
| JMC iHSS42 integrated (motor+encoder+driver) | ~$525 | 60mm | Maybe (needs testing) |
| UIROBOT UIM4247PM integrated | ~$553 | 92mm | ❌ No (too long) |
| StepperOnline ISD02 (no encoder, open loop) | ~$250 | 69.5mm | ❌ No |

**Recommendation:** When you want closed-loop, add magnetic encoders (AS5047P, ~$15 each) to the output shafts of the cycloidal drives. This measures actual arm position (after the gearbox), which is more useful than motor-side encoder. Works with Mesa 7i96S for LinuxCNC closed-loop PID.

---

## Calibration Reference

| Parameter | Value |
|-----------|-------|
| Steps/output revolution | 83,028 |
| Steps/degree | ~230.6 |
| Gear ratio | 20:1 cycloidal |
| Motor steps/rev | 200 (1.8°) |
| Microstepping | 16 (with interpolation to 256) |
| Max step rate (current) | 50,000 steps/sec (20µs) |
| Max output speed | ~0.6 rev/sec (36 RPM) |
| Cruise delay | 20µs |
| Accel/decel | 300 steps (sinusoidal) |
| Start delay | 600µs |

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-19 | Disable StallGuard (sgt=63, diag1_stall=false) | Cycloidal gearbox causes false triggers at all sensitivity levels |
| 2026-07-19 | Remove serial E-STOP from stepping loop | False positives from stray serial data |
| 2026-07-19 | Switch to SpreadCycle mode | Better dynamic torque for robot arm vs StealthChop |
| 2026-07-19 | Calibration: 83,028 steps = 360° | Empirical measurement (was incorrectly 20,757) |
| 2026-07-19 | Max baud 250,000 (not 1Mbps) | Einsy uses ATmega32U2 UART bridge, not native CDC |
| 2026-07-20 | Pursuing Option C now, Option A/B later | Minimize cost, maximize learning before hardware upgrade |
