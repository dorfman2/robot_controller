# ROS 2 CAN Motion Control — Tasks

## Phase 0: Procurement & bench prep
- [~] Choose + acquire a **SocketCAN-native USB-CAN adapter** (R1). **RESEARCHED
      (2026-08-06): buy a CANable 2.0 (Openlight Labs) or MKS CANable 2.0 Pro
      (isolated clone) flashed with candleLight firmware** — native `gs_usb`
      SocketCAN, proven on Raspberry Pi, onboard 120 Ω terminator (the adapter is
      one bus end). Avoid STM32F103-based clones (can't run USB+CAN concurrently).
      Remaining: purchase.
- [x] Pull the **UIM4247PM manual**; record pulse-input mode, 5 V compatibility,
      **min pulse width → max step rate**, and enable/fault pins (R4). **DONE
      (2026-08-09) from `Manual_UIM344 V5.11.pdf` (+`Dimension_UIM4247PM.pdf`) in
      repo root: 9-terminal single-ended interface, opto common-ANODE (COM
      terminal) → ACTIVE-LOW signals; 5 V COM is the designed case; min pulse
      width >3 µs high+low (use 5/5 µs); ENA must be actively driven LOW to
      enable (floating = disabled); default micro-stepping 32 (6400 pulses/rev),
      UART-configurable (current, idle %, Maximum Missing Steps fault).
      Canonical pin map in design.md §4.**
- [x] Confirm 24 V/10 A budget + CAN daisy-chain **12 A fuse** vs. 6 joints + rail;
      confirm CAN bus **termination** plan (R10). **DONE (2026-08-06), computed:**
      6 joints @ run 0.8 A phase (J3 1.2 A) → supply-side ≈ ≤1 A/motor worst case
      + ~0.05 A/board electronics ≈ **6.3 A**; UIM4247PM ≤ ~1.5 A supply @ 1.7 A
      phase; gripper on existing 5 V BEC. **Worst case ≈ 8 A < 10 A supply**
      (realistic 4–5 A); first daisy link ≈ 6 A ≪ 12 A fuse. **Termination:** the
      bus ends are the **CANable adapter** (onboard 120 Ω enabled) and the **last
      board in the chain** (`CAN TERM` DIP ON); all other boards OFF. Verify with
      2×60 Ω ≈ 60 Ω across CAN_H/CAN_L, bus unpowered.
- [x] Inventory/install: 6× CANBUS Stepper **installed on all joints and verified
      working with manufacturer firmware (2026-08-05)**; UIM4247PM + DM542TE (spare) +
      Mega on hand; rail home switch to add.

## Phase 0.5: Pre-flight gate tests (R16 — pass or explicitly accept before Phase 2+)
- [ ] **E-STOP behavior (R13):** with a weighted joint holding, send `MsgType 6` —
      does it freewheel (gravity collapse) or hold? Test `Standstill Mode` (14)
      BRAKING/STRONG_BRAKING. Define the two-tier stop policy from the result.
- [ ] **Closed-loop verify (R14):** confirm `MsgType 13` = 1 is set + saved on every
      node (firmware default is OPEN loop, contradicting the docs); verify correction
      by back-driving a joint slightly and watching it recover.
- [ ] **Flood/rate test (R14):** stream indexed setpoints to 6 nodes at the target
      command rate + telemetry raised (angle 50 Hz), verify **zero dropped commands**
      (5-frame RX queues, no acceptance filter); measure `canbusload`; derate rates
      until clean.
- [ ] **Wraparound speed ceiling (R14):** sustained multi-rev moves at increasing
      speed; compare commanded vs. reported position after N revs; set + enforce the
      per-joint motor speed limit.
- [ ] **Torque/thermal:** J1-representative load at ≤1.92 A on the TMC2209 (vs. 4.7 A
      EZ5160 today); verify holding + temperature over 30 min (hold-current overheating
      precedent from Klipper Phase 4).
- [ ] **Gripper servo on AUX PWM (R15):** J5 node `MsgType 26` AUX1 function 6 —
      sweep duty ~205–410, confirm smooth servo travel + live value updates; calibrate
      open/closed endpoints.
- [ ] **Control-path latency:** setpoint→bus latency/jitter via `ros2_socketcan` topics
      vs. direct SocketCAN, on the Pi with vision services running; decide the HWIF
      transport (design §11).
- [ ] **ros2_control dry run:** `controller_manager` @ target rate with a dummy HWIF on
      the Pi 4 alongside vision services; confirm CPU/jitter headroom.

## Phase 1: CAN bus bring-up (single adapter)
- [ ] Bring up `can0` @ 1 Mbit on the Pi; make it **persistent** (systemd-networkd/
      udev), surviving reboot + replug; document (R1).
- [ ] Set unique **NodeID 1–6** on each board (SW1-on-boot), save to NVM; label boards
      to joints J0–J5; verify each enumerates on `can0` (`candump`) (R1).
- [ ] Install `ros2_socketcan`; confirm `/from_can_bus` + `/to_can_bus` shuttle raw
      frames both directions (R2).
- [ ] Measure bus load headroom with `canbusload can0@1000000` under a telemetry load
      (R8, design §2.5).

## Phase 2: CAN protocol driver (`armold_can_driver`)
- [x] Port the vendor encode/decode (`build_can_id`, `struct` pack/unpack) into a typed
      module; **no-mock unit tests** round-tripping the spec's frame examples (R2, R12).
      DONE (2026-08-06): `ros2_ws/src/armold_can_driver/armold_can_driver/protocol.py`
      — Frame dataclass, MsgType enum, command encoders, telemetry decoders, R14
      broadcast guard, R15 AUX/servo helpers. 43 no-mock tests pass; lint+mypy clean.
      **Found 2 typos in the vendor doc's worked examples** (90.0 payload actually
      encodes 88.0; "0x91" for node 2 angle is really 0xA1) — tests document both,
      IEEE-754/firmware behavior is ground truth.
- [ ] Command mapping: enable/disable/e-stop (incl. broadcast NodeID 0), set position
      (steps), position-speed/accel/decel, current, microsteps, closed-loop, report
      freq, save (R2).
- [ ] Telemetry demux: angle (`33`) + velocity (`42`) + counts (`32`) → joint state
      cache; voltage/StallGuard/temp/fault → diagnostics (R2).
- [x] **Gear/unit mapping** (joint↔motor↔steps), per-joint config (ratio, dir, offset,
      limits); no-mock conversion tests; joint-space in, motor-space out (R3, R12).
      DONE (2026-08-06): `gearing.py` — frozen `JointConfig` (ratio, dir_sign,
      park_pose_deg offset per R5, soft limits per R9), verified against measured
      calibration (360° joint = 83,028 steps; 90° = 20,757). Telemetry conversions
      deliberately not limit-checked (must report reality).
- [ ] Bench: one node — enable, config, move by joint angle, read back angle in joint
      units (real hardware) (R12).
- [ ] **Gripper interface (R15):** map open/close fraction → AUX1 duty (calibrated
      endpoints from Phase 0.5); expose via `ros2_control` gpio interface or service
      (design §6b); guard: never enable AUX serial on the J5 node.
- [ ] **Safety guards (R13/R14):** two-tier stop (soft halt = hold enabled; hard E-STOP
      = `MsgType 6`); broadcast restricted to enable/disable/e-stop; commanded-vs-
      reported divergence check with fault + soft halt.

## Phase 3: Position reference (arm — park-pose zeroing, NO StallGuard)
- [ ] Define the **park pose** (joint angles + physical fixture/markings); document
      `park_pose_deg` per joint in the params YAML (R5).
- [ ] Enable + save **zero-encoder-at-boot** (`MsgType 8`) on all 6 nodes; verify boot
      reads 0 at park and driver offsets produce true joint angles (R5).
- [ ] Implement the **startup reference flow**: compute positions → operator-confirm
      park (ROS 2 service) → unblock planning; plus the **manual re-reference service**
      (jog to park → set reference) for a disturbed arm (R5).
- [ ] Optional: **vision pose sanity check** (overhead camera vs. expected park
      silhouette) as an automated cross-check (R5).

## Phase 4: Rail axis (UIM4247PM + Mega)
- [ ] Fork `firmware/ramps_s42c` → single-axis rail firmware: serial line protocol,
      accel-ramped STEP/DIR/EN, soft limits, **switch homing**, position/limit/fault
      telemetry (R4, R5).
- [ ] Wire Mega STEP/DIR/EN → UIM4247PM opto inputs per the manual; wire home switch;
      bench-verify motion + homing (R4, R5).
- [ ] `armold_rail_driver` ROS 2 node: serial bridge, **mm↔steps** (calibrate
      `steps_per_mm`), home/e-stop services; no-mock mm↔steps tests (R4, R12).

## Phase 5: ros2_control + MoveIt
- [ ] `ArmCanSystem` `SystemInterface` (6 joints, position cmd + pos/vel state) wrapping
      `armold_can_driver` (R6).
- [ ] `RailSerialSystem` `SystemInterface` (1 prismatic joint) wrapping
      `armold_rail_driver` (R6).
- [ ] `controller_manager` config: `joint_state_broadcaster`, `arm_jtc`, `rail_pos_controller`;
      verify `read/write` @ update rate streams setpoints (R6, R8).
- [ ] URDF/SRDF: prismatic `rail` carrying the arm base; planning groups `arm` (IK) +
      `rail` (non-IK) + optional `arm_on_rail`; **rail excluded from the IK solver** (R7).
- [ ] MoveIt config; plan+execute a 6-DOF arm move with the rail commanded separately;
      confirm rail motion updates the arm base pose (R7).
- [ ] **Decide RTB vs MoveIt IK** for the `arm` group; document (design §5, §11).

## Phase 6: Safety & integration
- [ ] E-STOP service → broadcast `MsgType 6` + Mega `!`; hook `controller_manager`
      error handling; motors start disabled (R9).
- [ ] Watchdogs: stale telemetry / missing node / CAN or serial loss → stop + diagnostic
      (R9).
- [ ] Soft limits enforced on driver AND firmware, independent of MoveIt (R9).
- [ ] Repeatable home → pose → home on all 7 axes within a documented tolerance
      (success criteria).

## Phase 7: Migration & disposition (R11)
- [ ] Decide BTT Octopus/Klipper disposition: retire vs. keep as fallback; document.
- [ ] Migrate/adapt the vision pick (`vision-oak4-upgrade`) + web UI to the ROS 2 stack
      (or a thin bridge); reconcile `armold_controller` role.
- [ ] Update steering (`active-context`, `system-patterns`, `tech-context`) with the
      distributed-CAN + ROS 2 architecture, `can0` bring-up, NodeID↔joint map, and the
      rail Mega bridge.

## Cross-cutting
- [ ] python-prefs + logging-standards; ruff/black/isort/mypy clean; no-mock tests for
      all protocol + unit math (R12).
- [ ] colcon workspace under `ros2_ws/src/` (`armold_can_driver`, `armold_rail_driver`,
      `armold_hw`, `armold_moveit_config`, `armold_bringup`); deploy via existing Mac→Pi
      path; firmware via PlatformIO (design §8).

## Notes
- `ros2_socketcan` is transport only; protocol logic is `armold_can_driver`.
- CANBUS Stepper: corrective closed loop + single-turn encoder → **park-pose reference
  every boot** (StallGuard homing excluded — cycloidal drag false-triggers; R5).
- Encoder is on the **motor shaft, before the gearbox** — backlash stays invisible;
  desk-Z calibration (`vision-oak4-upgrade` R11) remains necessary.
- Gripper servo = **J5 node AUX1 PWM** (50 Hz/12-bit, verified in firmware); 5 V BEC
  power; Mega fallback only (R15).
- No cross-node bus time-sync → coordination via streamed setpoints (design §2.4/§8).
- CANBUS Steppers **max 29 V** — keep the shared bus ≤24 V; separate rail supply if >24 V.
- Rail is a **controllable, non-IK** joint (decoupling DOF) per `vision-oak4-upgrade` R10.
- Distributed-CAN alternative to `mesa-linuxcnc` / `btt-grblhal-ik` / `klipper-migration`.
