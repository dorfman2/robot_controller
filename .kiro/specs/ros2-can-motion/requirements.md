# ROS 2 CAN Motion Control — 6 CAN Closed-Loop Joints + Step/Dir Rail — Requirements

## Goal
Re-platform Armold's motion control onto **ROS 2 Jazzy** driving a **distributed,
7-axis** system:

- **6 arm joints (J0–J5)** as **thingsbyjosh CANBUS Stepper** smart closed-loop nodes
  on a single **1 Mbit CAN bus**, reached from the Pi via **one USB-CAN adapter** →
  SocketCAN → **`ros2_socketcan`**.
- **1 linear rail** as a **UIM4247PM** integrated closed-loop stepper driven over
  **step/dir** by an **Arduino Mega** pulse generator, bridged to ROS 2 over **USB
  serial**.

The arm and rail **MUST** appear to MoveIt/`ros2_control` as one coordinated system,
with the **rail exposed as a controllable joint that is EXCLUDED from the IK chain**
(the grasp-yaw decoupling DOF — see `vision-oak4-upgrade` R10). This replaces the
centralized single-board controller (BTT Octopus / Klipper) with per-joint
distributed intelligence.

## Background (current state, 2026-08-05)
- Motion today runs on a **BTT Octopus MAX EZ (Klipper MCU)** with 7 EZ5160 drivers,
  commanded by `armold_controller` over Moonraker (see `klipper-migration`). All 7
  motors move; this spec proposes moving OFF the centralized board to distributed
  CAN nodes.
- ROS 2 Jazzy is installed on the Pi but was removed from the motion path (documented
  bridge/DDS pain in `stable-bridge`). This spec brings ROS 2 back as the motion
  framework, using `ros2_socketcan` (transport) + a protocol driver, **not** rosbridge.
- Kinematics/IK is RTB-based (`rtb-cartesian-ik`); the vision pick (`vision-oak4-upgrade`)
  already treats the **rail as the decoupling DOF** and excludes it from the IK chain.
- Joints use ~**25.95:1** cycloidal gearboxes (**230.6 steps/degree**, measured); the
  host owns all gear math.

## Hardware

| Component | Role | Interface | Qty | Key specs | Status |
|-----------|------|-----------|-----|-----------|--------|
| thingsbyjosh **CANBUS Stepper** | Arm joints J0–J5 | **CAN 1 Mbit** (11-bit ID) | **6** | ESP32-S3, TMC2209, 14-bit MT6701 encoder (single-turn), on-board trapezoidal profiler + corrective closed loop, **12–24 V (29 V max)**, 1.92 A max, daisy-chain power (12 A fuse) | **Installed on all 6 joints, verified working (manufacturer firmware, 2026-08-05)** |
| **UIM4247PM** | Linear rail | **step/dir** (pulse-direction) | 1 | Integrated closed-loop NEMA 17, built-in encoder + controller + driver, **24–48 V**, 1.7 A, 0.43 N·m | Purchased |
| **DM542TE** | Spare / open-loop axis | step/dir | 1 | Open-loop digital drive, 24–50 V, 1.0–4.2 A (no encoder) | Purchased (spare) |
| **Arduino Mega 2560** | Rail step/dir pulse generator + limit switch | USB serial ↔ Pi | 1 | ATmega2560; **not** micro-ROS capable (8 KB RAM); reuse `ramps_s42c` firmware | On hand |
| **USB-CAN adapter** | Pi ↔ CAN bus for all 6 joints | USB ↔ SocketCAN `can0` | 1 | 1 Mbit, SocketCAN/`gs_usb` class (e.g. CANable/candleLight) | **To acquire/confirm** |
| Rail home/limit switch | Rail zero reference | Mega GPIO | 1 | Step/dir gives no absolute position at boot | To add |
| Gripper servo (180° 9 g metal-gear) | Gripper open/close | **AUX1 PWM on the J5 CAN node** (50 Hz, 12-bit) | 1 | 3.3 V signal (proven with this servo), powered by existing 5 V BEC, common ground | On hand |
| 24 V / 10 A supply | Motor power | — | 1 | Powers CAN joints (≤29 V) + rail | On hand |

## Requirements

### R1 — CAN transport (single adapter, all six joints)
- The Pi **MUST** reach all 6 CANBUS Stepper joints through **one USB-CAN adapter**
  presented as a SocketCAN interface (`can0`), brought up at **1 Mbit** at boot.
- The bring-up (bitrate, `txqueuelen`, auto-start) **MUST** be persistent (systemd /
  networkd / udev), survive reboot and adapter replug, and be documented.
- Each joint **MUST** have a unique, documented **NodeID (1–6)** set on the board and
  saved to its NVM; NodeID **0** (broadcast) **MUST** be reserved for all-node
  commands (e.g. E-STOP, enable).

### R2 — CAN protocol driver (transport ≠ protocol)
- Because `ros2_socketcan` only shuttles raw `can_msgs/Frame`, an **`armold_can_driver`**
  node **MUST** encode/decode the vendor protocol: `CAN_ID = (NodeID << 6) | MsgType`,
  little-endian payloads, RTR for telemetry requests.
- The driver **MUST** support the command set needed for motion: Set Position (deg,
  double `MsgType 1` / steps, int64 `MsgType 2`), Set Velocity (`3`), Set Current (`4`),
  Enable/Disable (`5`), Emergency Stop (`6`), zero-encoder-at-boot (`8`),
  position-speed/accel/decel (`16`/`17`/`18`), and config (microsteps `11`, steps/rev
  `10`, closed-loop `13`, standstill mode `14`, report frequency `19`, save `24`).
- The driver **MUST** ingest telemetry: encoder angle deg (`MsgType 33`, double) and
  counts (`32`), velocity (`42`), voltage (`34`), StallGuard value/triggered (`36`/`37`),
  temperature (`38`), and fault (`39`) — publishing joint state and diagnostics.
- The protocol encode/decode logic **SHOULD** reuse the vendor Python reference
  (`build_can_id`, `struct` pack/unpack) rather than re-deriving it.

### R3 — Gear & unit mapping (single source of truth)
- The driver **MUST** convert between **joint space** (output degrees/radians at the
  arm joint) and **motor space** (CANBUS Stepper shaft degrees/steps) using the
  per-joint gear ratio (~**25.95:1**, **230.6 steps/deg**), configurable per joint.
- Commanded joint limits, speeds, and accelerations **MUST** be expressed in joint
  space in config and translated to motor space on send; telemetry **MUST** be
  translated back to joint space before publishing.
- Direction sign and zero offset per joint **MUST** be configurable (map to `MsgType 15`
  and homing offset), so URDF joint directions match physical motion.

### R4 — Rail axis (UIM4247PM via Arduino Mega, step/dir)
- The rail **MUST** be driven by the **UIM4247PM** (closed-loop) over step/dir from the
  **Arduino Mega**; the **DM542TE** is a documented spare (open-loop), not the primary.
- The Mega **MUST** run firmware that generates STEP/DIR/EN with an accel-limited
  profile and enforces **soft limits**, reusing the `ramps_s42c` firmware pattern
  (sinusoidal ramp + segment/serial protocol), reduced to one axis.
- The Mega **MUST** communicate with the Pi over **USB serial** with a documented,
  line-oriented protocol (target position, feed/accel, home, enable, e-stop, and
  position/limit/fault telemetry). The Mega **MUST NOT** be expected to run
  micro-ROS/ROS 2 (ATmega2560 RAM is insufficient).
- An **`armold_rail_driver`** ROS 2 node **MUST** bridge that serial protocol to the
  rail's `ros2_control` interface, converting **rail mm ↔ steps** (steps/mm calibrated).

### R5 — Position reference at power-up (park-pose zeroing; NO StallGuard homing)
- **StallGuard sensorless homing is explicitly EXCLUDED** (decision 2026-08-05):
  the validated Einsy finding is that cycloidal gearbox drag causes false triggers
  at all sensitivity levels, and driving geared joints into hard stops risks the
  3D-printed structure. `MsgType 7`/`12` **MAY** be used later for in-motion
  stall/collision *detection*, never for homing.
- Because the CANBUS Stepper encoder is **single-turn (14-bit) with software multi-turn
  that does NOT persist across power cycles**, each arm joint **MUST** establish its
  position reference at power-up via **park-pose zeroing**: the arm is placed in a
  defined **park pose** (fixture or marked rest position) before power-off; each node
  has **zero-encoder-at-boot** (`MsgType 8`) enabled and saved, so boot position = 0 at
  the park pose; the driver applies the **known park-pose joint angles** as offsets to
  produce true joint positions.
- A **manual re-reference service** **MUST** exist: operator jogs joints to the park
  pose (or a fiducial), then invokes "set reference" — covering the case where the arm
  was moved while unpowered or the park pose is in doubt.
- The system **MUST NOT** enable planning/motion until the reference is confirmed —
  operator confirmation at minimum; an automated **vision pose sanity check** (overhead
  camera vs. expected park silhouette) **SHOULD** be added as a cross-check.
- The rail **MUST** home against a **physical home/limit switch** read by the Mega
  (step/dir provides no absolute position at boot; the UIM4247PM closed loop does not
  expose absolute position to the host).
- A defined **reference/homing sequence** **MUST** be exposed as a ROS 2 service/action;
  motion planning **MUST** be blocked until the system is referenced.

### R6 — `ros2_control` hardware interfaces
- The system **MUST** present **two `ros2_control` hardware components** under one
  `controller_manager`: an **arm system interface** (6 CAN joints, position command +
  position/velocity state) and a **rail system interface** (1 step/dir joint), so the
  planner sees a single 7-DOF machine.
- Command/state interfaces **MUST** be position (rad) at minimum; velocity state
  **SHOULD** be exposed from telemetry (`MsgType 42`/`33`).
- Controllers **MUST** include a `joint_state_broadcaster` and a
  `joint_trajectory_controller` (arm) plus a position controller for the rail.

### R7 — MoveIt integration with rail as a non-IK joint
- MoveIt **MUST** plan for the arm using the **6 arm joints only** in the IK/kinematic
  group; the **rail MUST be a controllable joint EXCLUDED from the IK solver** (planning
  group split: `arm` = J0–J5, `rail` = prismatic, plus a combined `arm_on_rail` group
  for coordinated execution if needed).
- The URDF/SRDF **MUST** model the rail as a prismatic joint carrying the arm base, so
  its motion updates the arm base pose, while IK targets are solved for the arm group.
- The system **MUST** be able to command the rail explicitly (position the base) and
  then solve arm IK at that base position — matching the grasp-yaw decoupling strategy
  in `vision-oak4-upgrade` R10.

### R8 — Coordinated motion within the distributed model
- The design **MUST** account for the fact that each CANBUS Stepper node **profiles its
  own move independently** (no bus-level time-sync across nodes) and that its closed
  loop is **corrective, not a high-bandwidth servo**.
- Trajectory execution **MUST** stream `joint_trajectory_controller` setpoints to the
  nodes at a fixed update rate (small position increments) rather than relying on a
  single end-point target, so multi-joint moves stay acceptably coordinated.
- The design **MUST** verify the CAN bus/adapter has bandwidth headroom for the chosen
  update rate × 6 joints (command) + telemetry, at 1 Mbit.

### R9 — Safety, faults, and E-STOP
- A **broadcast E-STOP** (`MsgType 6`, NodeID 0) and a rail e-stop (Mega) **MUST** be
  reachable from a single ROS 2 service and wired into `controller_manager` error
  handling; a fault on any joint/rail **MUST** stop coordinated motion.
- Motors **MUST** power on **disabled** and require explicit enable; loss of CAN, USB
  serial, or the adapter **MUST** stop motion and surface a diagnostic, never continue
  blindly.
- Over-travel **MUST** be prevented by joint soft limits (driver-side clamp) and rail
  soft limits (Mega-side), independent of the planner.

### R10 — Power & electrical safety
- The **CANBUS Steppers are limited to 29 V max**; the shared motor bus **MUST NOT**
  exceed this. If the rail is ever run above 24 V (UIM4247PM supports 24–48 V), its
  supply **MUST** be separated from the CAN-joint bus. The current **24 V** rail is
  compatible with all devices.
- The CAN daisy-chain power pass-through (**12 A fuse**) and the 24 V/10 A supply budget
  **MUST** be checked against 6 joints + rail worst-case draw.
- CAN bus termination **MUST** be correct: the two DIP-switch `CAN TERM` boards at each
  end ON, all others OFF; the USB-CAN adapter end terminated appropriately.

### R11 — Migration & coexistence
- The spec **MUST** define the relationship to the existing Klipper/BTT stack
  (`klipper-migration`): whether the BTT board is retired or kept as fallback, and how
  `armold_controller`/WebSocket UI and the vision services interoperate with (or are
  replaced by) the ROS 2 stack.
- The cutover **MUST** be staged (bench bring-up per node → single joint → full arm →
  rail → MoveIt) so the robot is never left in an untested motion state.

### R12 — Engineering standards
- Python **MUST** follow project python-prefs (type hints, verbose docstrings,
  dataclasses, **no-mock** tests) and logging-standards (module logger, lazy `%`).
- Firmware and ROS packages **MUST** build cleanly; Python linting (ruff/black/isort/
  mypy) **MUST** pass. Protocol encode/decode and gear/unit math **MUST** have no-mock
  unit tests; hardware paths **SHOULD** be integration-tested against real devices.

### R13 — E-STOP gravity policy (from edge case E2)
- Per the protocol, `MsgType 6` stops the motor and leaves the driver **disabled**
  until re-enabled; these boards have **no power-off brake** (that is the CMB variant).
  On a vertical arm, a disabled J1/J2 may **collapse under gravity**.
- The post-e-stop physical behavior **MUST** be bench-characterized (including
  `Standstill Mode`, `MsgType 14`, BRAKING/STRONG_BRAKING) before the e-stop policy is
  coded.
- The system **MUST** distinguish a **soft halt** (stop motion, stay enabled and
  holding — the default for faults/watchdogs) from the **hard E-STOP** (`MsgType 6`,
  drivers disabled — reserved for true emergencies, collapse risk accepted and
  documented). Power-loss collapse **MUST** be documented as a known behavior.

### R14 — Bus robustness & rate limits (from edge cases E3/E4/E5/E10)
- Node firmware has a **5-frame RX queue**, processes **one frame per loop pass**, and
  applies no hardware acceptance filter — every node software-filters all bus traffic.
  Command + telemetry rates **MUST** be validated by a **flood test** (indexed
  setpoints, zero drops) and derated until it passes.
- The multi-turn count can slip if a wraparound is missed at high motor speed
  (`readEncoder` samples once per loop pass); a **motor speed ceiling MUST** be
  established empirically and enforced by the driver, which **MUST** also cross-check
  commanded vs. reported position and fault on divergence.
- **Broadcast (NodeID 0) MUST be restricted** to enable/disable/e-stop — never motion.
- Firmware default control type is **open loop** (`DEFAULT_CONTROL_TYPE = 0` in code,
  contradicting the protocol doc); closed loop (`MsgType 13` = 1) **MUST** be explicitly
  set and saved on every node during bring-up and verified in the driver.

### R15 — Gripper servo via the J5 CAN node's AUX PWM
- The gripper servo **MUST** be driven from the **J5 wrist node's AUX connector** in
  PWM mode (`MsgType 26`, function 6): firmware-verified **50 Hz / 12-bit**
  (`ledcAttach(pin, 50, 12)`), live duty updates on value-only re-sends. No Mega
  involvement; no new wiring run down the arm.
- Servo **signal** = AUX1 (3.3 V logic — proven with this servo on the BTT board);
  servo **power** = the existing **5 V BEC** (never the AUX 3V3 pin); grounds common.
- The driver **MUST** expose the gripper as a position interface (open/close fraction →
  duty counts ≈ 205–410 for 1–2 ms), with calibrated open/closed endpoints.
- AUX serial mode (function 1) is mutually exclusive with PWM on these pins and
  **MUST NOT** be enabled on the J5 node.
- **Fallback**: if AUX PWM proves unreliable in practice, move the servo to a Mega PWM
  pin (documented, not default).

### R16 — Pre-flight gates
- The gate tests in tasks.md **Phase 0.5 MUST** pass (or their risks be explicitly
  accepted) before Phase 2+ implementation begins: e-stop behavior (R13), flood/rate
  test (R14), wraparound speed ceiling (R14), torque/thermal at ≤1.92 A, gripper servo
  on AUX PWM (R15), and control-path latency (DDS vs. direct SocketCAN).

## Success Criteria
- `can0` comes up at 1 Mbit at boot; all 6 joints enumerate and report telemetry
  through the single adapter.
- Each arm joint establishes its reference via park-pose zeroing and holds position
  closed-loop; the rail homes on its switch; the whole system reports a valid
  `joint_states` in joint units.
- `ros2_control` + MoveIt plan and execute a coordinated arm move (6-DOF) with the rail
  commandable separately and excluded from IK.
- A broadcast E-STOP halts all joints and the rail; loss of CAN or serial stops motion
  with a diagnostic.
- A repeatable joint-space move (e.g. home → known pose → home) completes within a
  documented position tolerance on all 7 axes.

## Constraints & Open Items
- **`ros2_socketcan` is transport only** — the vendor protocol logic lives in
  `armold_can_driver`; there is no off-the-shelf driver for these boards.
- CANBUS Stepper **closed loop is corrective (anti-lost-step), not torque-servo**;
  the encoder sits on the **motor shaft, before the gearbox** — cycloidal
  backlash/lost motion remains invisible to it (multi-point desk-Z calibration in
  `vision-oak4-upgrade` R11 stays necessary). Encoder is **single-turn** → park-pose
  reference required every boot (R5).
- **Park pose/fixture** must be defined (and ideally physically indexed) — open item.
- The vendor Python reference contradicts the protocol doc for `MsgType 7`
  (direction byte vs. behaviour uint16) — treat the protocol doc + firmware source as
  ground truth, the Python lib as a starting point only.
- No **bus-level cross-node time sync**; coordination comes from streaming setpoints at
  the controller rate (R8), acceptable for point-to-point/pick, not CNC contouring.
- **USB-CAN adapter model** not yet chosen — must be SocketCAN-native (`gs_usb`/
  `slcan`) and reliable at 1 Mbit (open item).
- **IK approach**: keep RTB for Cartesian solving vs. adopt MoveIt's IK — R7 assumes
  MoveIt for planning + the rail-as-non-IK split; reconcile with `rtb-cartesian-ik`
  (open decision in design.md).
- **UIM4247PM pulse spec** (opto input mode common-anode/cathode, 5 V compatibility,
  min pulse width / max step rate) **MUST** be confirmed from its manual before wiring.
- Relationship to `mesa-linuxcnc`, `btt-grblhal-ik`, `klipper-migration`,
  `einsy-linear-rail`: this spec is the **distributed-CAN alternative**; those remain as
  evaluated/parked options.
