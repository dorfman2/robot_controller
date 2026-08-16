# ROS 2 CAN Motion Control — Design

## 1. Architecture

```
                          Raspberry Pi 4 (Ubuntu 24.04, ROS 2 Jazzy)
 ┌──────────────────────────────────────────────────────────────────────────┐
 │  MoveIt 2  (planning: group `arm` = J0–J5;  `rail` prismatic, non-IK)      │
 │      │  FollowJointTrajectory                                             │
 │  ros2_control  controller_manager                                         │
 │      ├── joint_state_broadcaster                                          │
 │      ├── arm_jtc  (joint_trajectory_controller, 6 arm joints)             │
 │      └── rail_pos_controller (1 prismatic joint)                          │
 │             │ read()/write() @ update rate                                │
 │   ┌─────────┴───────────┐              ┌──────────────────────────────┐   │
 │   │ ArmCanSystem (HWIF) │              │ RailSerialSystem (HWIF)      │   │
 │   │  armold_can_driver  │              │  armold_rail_driver          │   │
 │   └─────────┬───────────┘              └───────────────┬──────────────┘   │
 │             │ can_msgs/Frame                           │ line protocol    │
 │      ros2_socketcan (recv/send)                        │ (pyserial)       │
 └─────────────┼──────────────────────────────────────────┼─────────────────┘
               │ SocketCAN can0 @ 1 Mbit                    │ USB serial
        ┌──────┴──────┐                              ┌──────┴───────┐
        │ USB-CAN dongle │                            │ Arduino Mega │  home/limit sw
        └──────┬──────┘                              └──────┬───────┘
        CAN bus (1 Mbit, terminated both ends)              │ STEP/DIR/EN
   ┌────┬────┬────┬────┬────┬────┐                    ┌──────┴───────┐
  N1   N2   N3   N4   N5   N6  (NodeID)                │  UIM4247PM   │ (closed-loop)
  J0   J1   J2   J3   J4   J5                          │   rail motor │
  CANBUS Stepper × 6 (ESP32-S3 + TMC2209 + encoder)    └──────────────┘
   └─ N6 (J5) AUX1 ──► gripper servo (50 Hz PWM; 5 V BEC power)
        24 V bus (≤29 V!)                                 24 V (spare: DM542TE)
```

Two hardware interfaces, one `controller_manager`, one `joint_states`. The CAN path
carries the six smart joints; the serial path carries the rail. `ros2_socketcan` and
`pyserial` are pure transport — all semantics live in the two driver nodes/HWIFs.

## 2. CAN joints — protocol driver (`armold_can_driver`)

### 2.1 Frame format (vendor protocol)
- 11-bit standard ID: `CAN_ID = (NodeID << 6) | MsgType`; `NodeID` 1–6 (0 = broadcast),
  `MsgType` 0–31 command / 32–63 telemetry. Payloads **little-endian**, ≤8 bytes. RTR=1
  requests the current value of a `MsgType`.
- Reuse the vendor reference logic (`build_can_id`, `parse_can_id`, `struct` pack/unpack
  from `python_example.py`) rather than re-deriving. It is transport-agnostic, so it
  drops onto `can_msgs/Frame` (`.id`, `.is_rtr`, `.dlc`, `.data`).

### 2.2 Command mapping (joint → CAN)
| Purpose | MsgType | Payload | Notes |
|---------|---------|---------|-------|
| Enable / disable | 5 | `uint8` 1/0 | Broadcast (NodeID 0) for all-on/all-off |
| E-STOP | 6 | any | Broadcast; re-enable via 5 |
| Set position | 1 (deg, `double`) or 2 (steps, `int64`) | motor-space | Prefer steps for determinism |
| Position speed / accel / decel | 16 / 17 / 18 | `float` (motor deg/s, deg/s²) | Set once at config; per-joint |
| Set current | 4 | `uint16` % (0–100) | Per-joint tuned (J1/J2 higher) |
| Microsteps / steps-per-rev | 11 / 10 | `uint16` | Config; affects step math |
| Closed-loop type | 13 | `int16` 1 | **Explicitly set + save on every node** — firmware default is OPEN loop (code contradicts docs) |
| Zero encoder at boot | 8 | `uint8` 1 | Park-pose reference (R5); save to NVM |
| Standstill mode | 14 | `uint16` | Bench-test for e-stop/hold policy (R13) |
| Report frequency | 19 | `uint16,uint16` Hz | Angle rate + other rate; raise angle rate for `read()` freshness, re-validate bus load |
| Save config | 24 | — | Persist per-node config to NVM |

### 2.3 Telemetry mapping (CAN → joint state)
- Periodic **Encoder Angle deg** (`MsgType 33`, `double`) at the configured rate is the
  primary position feedback; **Velocity** (`42`) for velocity state; **counts** (`32`)
  as backup. Voltage (`34`), StallGuard (`36`/`37`), temp (`38`), fault (`39`) →
  `diagnostic_msgs`.
- The driver subscribes `/from_can_bus`, demuxes by `(NodeID, MsgType)`, updates a
  per-joint state cache consumed by `read()`.

### 2.4 Command path
- `write()` publishes `can_msgs/Frame` to `/to_can_bus`. To keep coordinated motion
  acceptable (R8), the arm HWIF streams **Set Position (steps)** setpoints every
  `controller_manager` cycle; each node runs its own trapezoidal profile between
  setpoints (small increments → smooth, quasi-synchronized).

### 2.5 Bandwidth budget (sanity)
- One standard CAN data frame ≈ 44 + 8·8 + stuffing ≈ ~110–130 bits. At 1 Mbit ≈
  **>7,000 frames/s** capacity. Budget: 6 joints × 100 Hz command = 600 fps +
  telemetry (6 × angle@50 Hz = 300 + secondary ≈ 60) ≈ **~1,000 fps** → comfortably
  <15% bus load. (This headroom is the reason for the single USB-CAN adapter over the
  serial-bridge-through-a-node alternative, which is limited to ~480 text frames/s at
  115200.) Confirm empirically with `canbusload can0@1000000`.

## 3. Gear & unit mapping (`armold_can_driver` config)
- Per joint: `gear_ratio` (≈25.95), `steps_per_motor_rev` (200 × microsteps),
  `dir_sign` (±1), `home_offset_deg`, joint soft limits (rad).
- Output → motor: `motor_deg = dir_sign · joint_deg · gear_ratio`;
  `steps = motor_deg / 360 · steps_per_motor_rev`. Inverse on telemetry.
- Single source of truth in a YAML params file; the URDF joint directions/limits and
  these signs/limits **MUST** agree (verified during bring-up).

## 4. Rail axis — `armold_rail_driver` + Mega firmware
- **Mega firmware** (fork of `firmware/ramps_s42c`, one axis): serial line protocol,
  STEP/DIR/EN generation with accel-limited (sinusoidal) ramp, soft limits, a
  home/limit-switch routine, and periodic position/limit/fault reporting.
- **Canonical Mega ↔ UIM4247PM pin map (VERIFIED against `Manual_UIM344 V5.11.pdf`,
  2026-08-09). Single-ended, common-ANODE opto inputs → signals are ACTIVE-LOW:**
  COM (t3) → Mega **5 V**; STP (t5) → **D2** (LOW pulse = step); DIR (t4) → **D3**
  (LOW = CW); ENA (t6) → **D4** (**LOW = enabled — must be actively driven;
  floating = DISABLED**, unlike typical drives). Home switch = **D5** ↔ Mega GND
  (`INPUT_PULLUP`). V+ (t1)/GND (t2) from the 24 V PSU, never the Mega; no
  logic-ground tie needed (opto loop closes through the Mega pin sink).
  **Timing (manual p.6):** min pulse width **>3 µs high and low** (terminal spec
  >4 µs) → firmware uses 5 µs/5 µs (~100 kHz max step rate). **Default
  micro-stepping = 32** (6400 pulses/motor-rev), configurable 1–128 via UART
  terminals t8/t9 (also working current, idle current %, Maximum Missing Steps
  closed-loop fault). 5 V COM is the designed drive case; the 2.49 kΩ
  series-resistor note applies only to 24 V logic.
- **UART config wiring (part of the canonical map):** motor **TX (t8) → Mega RX1
  (D19)**, motor **RX (t9) → Mega TX1 (D18)** — crossed over; TTL UART, explicitly
  "NOT RS232" (manual p.16). The manual does not state the motor UART's logic
  level, so add a **1 kΩ series resistor on the Mega TX1 (D18) → t9 line** in
  case the motor side is 3.3 V. This link DOES require a logic-ground reference:
  tie a Mega GND to motor terminal t7 (GND) for the UART only. Baud/protocol are
  undocumented — initial config (micro-stepping, working/idle current, Max
  Missing Steps) is done with the vendor **CFG344 tool + USB-UART dongle**; the
  Serial1 wiring gives us the option to sniff/replay that exchange later for
  runtime fault interrogation from the Mega.
- **CFG344 tool analysis (2026-08-09, from `Config Tool - UIM344.zip`):** Qt5
  C++ Windows app (84 KB exe + Qt DLLs). **UART baud = 57600** (single baud
  constant in the binary). Config surface from UI fields: micro-stepping (MCS),
  working current, idle current %, max missing steps (Mxe), acceleration (Acr),
  velocity params (Vr0/Vr1/Vth), encoder lines/rev (LPR), serial number;
  supports UIM340 + UIM344. Wire protocol not extractable from strings —
  one-time config needs Windows (or a Wine/VM attempt); optionally sniff the
  exchange via the Mega's Serial1 tap at 57600 8N1 to learn the frames for
  runtime use.
- **Serial protocol (draft)**: `M <steps>` move-to, `F <steps/s>`/`A <steps/s²>`
  feed/accel, `H` home, `E 0|1` enable, `!` e-stop, `?` query → replies `P <steps> L
  <lim> S <state>`. Line-oriented, 115200 8N1, ACK per command (reuse the segment/ACK
  style already proven on RAMPS/Einsy).
- **`armold_rail_driver`** ROS 2 node: converts rail **mm ↔ steps** (`steps_per_mm`
  calibrated), presents the rail `ros2_control` interface, and maps home/e-stop to
  services.
- **Rail calibration (MEASURED, smoke test 2026-08-15, factory drive defaults):**
  **steps_per_mm = 160** (6400 steps = 40.0 mm exactly; 32 microsteps × 200 steps ×
  20T GT2 @ 2 mm pitch = 40 mm/rev). **CW = toward the endstop** (homing direction).
  Verified **100 mm/s (16 kHz) with zero accel ramp, no missed steps** — with the
  sinusoidal ramp, cruise ≥100 mm/s with margin. Mid-move endstop stop verified.
  Factory UIM4247PM config is sufficient — CFG344/Windows session NOT required.
- **Mega resets on every serial-port open** (auto-reset via DTR): rate/enable state
  reverts to defaults and **the rail loses holding torque at reconnect** —
  `armold_rail_driver` MUST re-enable, restore config, and re-verify position after
  every connect, and never assume state persists across port opens.

## 5. ros2_control & MoveIt (R6, R7)
- **Two `SystemInterface` plugins**: `ArmCanSystem` (6 joints) and `RailSerialSystem`
  (1 joint). One `ros2_control` URDF tag block per interface; both loaded by one
  `controller_manager`.
- **Controllers**: `joint_state_broadcaster`, `arm_jtc`
  (`joint_trajectory_controller`, position; claims J0–J5), `rail_pos_controller`
  (position; claims `rail`).
- **URDF/SRDF**: prismatic `rail` joint carries `base_link` of the arm; MoveIt planning
  groups: `arm` (J0–J5, has IK) and `rail` (prismatic, **no IK kinematics solver**),
  plus optional `arm_on_rail` for joined execution. IK targets solve for `arm` at the
  current/commanded rail position — the rail is positioned explicitly (decoupling DOF),
  never by the arm IK solver (matches `vision-oak4-upgrade` R10).
- **IK choice (open):** either keep **RTB** (`rtb-cartesian-ik`) as the Cartesian solver
  and use ROS 2 only for hardware I/O + trajectory streaming, or adopt **MoveIt's IK**
  (KDL/TRAC-IK) for the `arm` group. Default: MoveIt for planning/execution; RTB
  retained for the vision pick's clean-wrist analytic solves until parity is proven.

## 6. Position reference & startup (R5) — park-pose zeroing, NO StallGuard
- **StallGuard homing excluded** (decision 2026-08-05): cycloidal drag falsely
  triggers at all sensitivities (validated on Einsy/TMC2130; same physical cause
  applies to SG4), and hard-stop homing through 25.95:1 gearing risks the printed
  structure. `MsgType 7`/`12` reserved for optional in-motion collision detection.
- **Arm**: **park-pose zeroing.** Each node has `MsgType 8` (zero-encoder-at-boot)
  enabled + saved. Operating procedure: park the arm at the defined **park pose**
  before power-off → at boot every node reads 0 at park → the driver adds the known
  park-pose joint angles (`park_pose_deg` per joint in the params YAML) to produce
  true joint positions. No motion needed to reference.
- **Trust but verify**: reference is only valid if the arm actually was at park.
  Startup flow: driver computes joint positions → operator confirms park (ROS 2
  service) → optional vision cross-check (overhead camera vs. expected park
  silhouette) → planning unblocked. If the arm was disturbed while off, the operator
  jogs to park (or a fiducial) and calls the **re-reference service**, which re-zeros
  (`MsgType 8` re-apply or driver-side offset reset).
- **Rail**: switch-based home routine in the Mega; report homed state.
- **Why every boot**: `readEncoder()` tracks multi-turn only in RAM
  (`revolutions` resets on power cycle) over a single-turn 14-bit encoder; through the
  ~25.95:1 gearbox the absolute joint angle at boot is unknown without a reference.

## 6b. Gripper (R15)
- Servo signal → **J5 node AUX1**, configured PWM (`MsgType 26`: AUX1 function 6,
  value = duty counts). Firmware-verified: `ledcAttach(AUX1, 50, 12)` = 50 Hz /
  12-bit; value-only re-sends do a live `ledcWrite` (no mode churn).
- Duty math: 20 ms period / 4095 counts → 1 ms ≈ 205, 1.5 ms ≈ 307, 2 ms ≈ 410.
  Driver maps gripper fraction [0..1] → calibrated `[duty_open, duty_closed]`.
- Power from the existing 5 V BEC (AUX 3V3 pin cannot source servo current), common
  ground. 3.3 V signal proven with this servo (ran on BTT 3.3 V PA1).
- Exposed as a small `ros2_control` gpio/position interface or a plain service on
  `armold_can_driver` (decide at implementation; the pick orchestrator only needs
  open/close/fraction).
- Do **NOT** enable AUX serial (function 1) on the J5 node — mutually exclusive with
  PWM. Fallback if unreliable: Mega PWM pin (documented, not default).

## 7. Safety (R9, R10, R13, R14)
- **Two-tier stop (R13):** default fault/watchdog response is a **soft halt** — stop
  motion but keep drivers enabled and holding (no gravity collapse). **Hard E-STOP**
  (ROS 2 service → broadcast `MsgType 6` + Mega `!`) disables drivers; with no brakes,
  J1/J2 may fall — reserved for true emergencies. Bench-characterize `MsgType 6` and
  `Standstill Mode` (14) behavior before coding the policy. Hook both tiers into
  `controller_manager` on_error. Motors start disabled (enable-on-boot off, `MsgType
  20`).
- **Broadcast restriction (R14):** the driver refuses NodeID-0 frames except
  enable/disable/e-stop — a broadcast Set Position would lunge all six joints at once.
- **Divergence check (R14):** driver cross-checks commanded vs. encoder-reported
  position each cycle; fault + soft halt on divergence beyond a per-joint bound
  (catches multi-turn slip and lost-command drift).
- Watchdogs: `armold_can_driver` flags stale telemetry / missing nodes; `ros2_socketcan`
  or USB-serial loss → stop + diagnostic. Soft limits clamp on both driver and firmware
  independent of MoveIt.
- Electrical: single 24 V bus for CAN joints (**never >29 V**); if rail goes >24 V,
  separate supply. Verify termination (end boards `CAN TERM` ON + adapter end); check
  12 A daisy-chain fuse and 24 V/10 A budget vs. worst-case.

## 8. Deployment & packaging
- New ROS 2 workspace on the Pi (colcon) with packages: `armold_can_driver`,
  `armold_rail_driver`, `armold_hw` (ros2_control plugins), `armold_moveit_config`,
  `armold_bringup` (launch + `can0` up + params). Repo layout mirrors under
  `ros2_ws/src/` (replaces the parked `ros2_bridge/`).
- `can0` bring-up via systemd-networkd/udev at 1 Mbit; documented and persistent.
- Deploy via the existing Mac→Pi path (`scripts/deploy_*`); firmware via PlatformIO to
  the Mega.

## 9. Testing (R12, no-mock)
- **Unit (host, no hardware, no mock):** frame encode/decode round-trip vs. the vendor
  spec examples (e.g. Set Position deg Node 3 → `0xC1` + payload); gear/unit conversions
  (joint↔motor↔steps) with property-style checks; rail mm↔steps.
- **Integration (real devices):** single node on the bench — enumerate, enable, home,
  move, read telemetry; then 6-joint bus; then rail; then `ros2_control` `read/write`;
  then a MoveIt plan+execute. `canbusload` to confirm bus headroom.

## 10. Staged cutover (R11)
1. Bench-bring-up one CANBUS Stepper (set NodeID, config, home, move) via `can0`.
2. `armold_can_driver` + one joint through `ros2_control`.
3. All 6 joints on the bus; homing sequence; `joint_states` sane.
4. Rail: Mega firmware + `armold_rail_driver` + switch homing.
5. `ros2_control` both HWIFs; MoveIt config; coordinated plan/execute.
6. Decide BTT/Klipper disposition (retire vs. fallback) and migrate the vision pick +
   web UI onto the ROS 2 stack.

## 11. Open decisions
- USB-CAN adapter model (SocketCAN-native, reliable @1 Mbit).
- **RESOLVED (2026-08-09) — wireless access = Pi as gateway (option 1).** No radio
  on the motion nodes (keeps verified manufacturer firmware + avoids WiFi/step-gen
  jitter on the same die). The Pi (LAN/SSH/WebSocket) + CANable is the wireless
  path for bench gates and control. Research notes: all CANBUS-Stepper forks are
  0 ahead (no community wireless mod); the vendor's **PD-Stepper repo**
  (`joshr120/PD-Stepper`: `PD_Stepper_Web_Server.ino`, ESPHome YAMLs, ESP-NOW)
  is the proven port source if a dedicated ESP32+CAN wireless bench tap is ever
  wanted. Sweep Sync (sweepsync.app) is closed-source; treat as an optional
  cloud UI client, never required for motion.
- RTB vs. MoveIt IK for the `arm` group (Section 5).
- Control-path transport: HWIF via `ros2_socketcan` topics vs. **C++ HWIF opening
  SocketCAN directly** (keep `ros2_socketcan` for tooling) — decide from the latency
  gate test.
- Whether the WebSocket UI / `armold_controller` stays (as a ROS 2 client) or is
  replaced by RViz/MoveIt + a thin bridge.
- Node↔joint physical order on the daisy chain and reference/park pose definition
  (park fixture design — from geometry).
- Rail steps/mm and UIM4247PM pulse electrical spec (from its manual).
- Gripper exposure: `ros2_control` gpio interface vs. plain service (design §6b).
