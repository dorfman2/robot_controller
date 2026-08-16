# Phase 0.5 Bench Gate Procedures (R16)

Operator procedures for the pre-flight gates. **No CAN adapter needed**: every
CANBUS Stepper node is a USB↔CAN bridge — plug USB-C into ANY node and it
forwards frames to the whole chain (and runs commands addressed to itself).

**Wireless option (decided 2026-08-09):** connect that USB-C to the **Pi** and
run everything over SSH (`ssh -i ~/.ssh/armold_deploy pi@armold.local`, then
miniterm on the node's `/dev/ttyACM*`). Once the CANable arrives, the same
gates run wirelessly through `can0` with no cable swapping.

**Serial link:** 115200 8N1. Frame format: `<CAN_ID_hex> <RTR> <payload_16hex>\n`.
Connect with `screen /dev/cu.usbmodem* 115200` (Mac) or
`python3 -m serial.tools.miniterm /dev/ttyACM0 115200` (Pi). Telemetry from all
nodes streams back on the same link.

All command strings below were generated and verified by
`armold_can_driver.protocol` (43 passing tests). Node 1 (`4x` IDs) is the
example bench node — recompute IDs for other nodes as `(NodeID<<6)|MsgType`.
Node 6 = J5/gripper (`19A` = AUX).

⚠ Before ANY motion: know where the joint is, keep the E-STOP line ready in a
second terminal, start at low current (`44 0 2800000000000000` = 40%).

---

## Gate 1 — Closed-loop verify (R14) — do FIRST, per node
Firmware default is **open loop** (code contradicts the docs). Per node (IDs
shown for node 1):

1. Set closed loop: `4D 0 0100000000000000`
2. Save to NVM: `58 0 0000000000000000`
3. Power-cycle the node, then verify it stuck — read angle: `61 1 0000000000000000`
4. Enable (`45 0 0100000000000000`), command hold at current position, then
   gently back-drive the joint by hand a few degrees and release.

**PASS:** joint actively returns to the commanded position after back-drive
(on all 6 nodes, after a power cycle).

## Gate 2 — E-STOP behavior (R13) — decides the stop policy
With a weighted joint (J1 or J2) enabled and holding, gravity loading it:

1. Baseline: send broadcast E-STOP `6 0 0000000000000000` → **observe: does
   the joint hold or fall?** (Expect fall: driver disabled, no brake.)
2. Re-enable (`5 0 0100000000000000`), re-position. Set standstill BRAKING
   `4E 0 0200000000000000`, then disable node (`45 0 0000000000000000`) →
   observe hold/fall.
3. Repeat with STRONG_BRAKING `4E 0 0300000000000000`.
4. Restore NORMAL `4E 0 0000000000000000`.

**Record:** hold/fall for each mode. **Outcome:** defines soft-halt vs hard
E-STOP tiers in the driver (R13). Support the arm during this test.

## Gate 3 — Wraparound speed ceiling (R14)
Multi-turn counting can slip if the encoder wraps >½ motor rev between loop
passes. Per representative node:

1. Read angle → record. `61 1 0000000000000000`
2. Set position-speed 360 deg/s: `50 0 0000B44300000000`
3. Command +3600 deg (10 motor revs): `41 0 000000000020AC40`, wait, then back
   to 0: `41 0 0000000000000000`
4. Read angle → **must match the recorded start within ~1 deg.**
5. Raise speed (e.g. 1800 deg/s: `50 0 0000E14400000000`) and repeat until the
   returned position slips by ≥ a motor rev (~13.9 joint deg) or motion stalls.

**Record:** highest clean speed per joint. Driver will enforce ~70% of it.

## Gate 4 — Telemetry/flood rate check (R14, partial without adapter)
Node RX queues are 5 frames; every node sees all traffic.

1. Raise angle telemetry to 50 Hz on ALL nodes (per node; node 1 shown):
   `53 0 3200050000000000`
2. With all 6 streaming, command interleaved small moves to two nodes rapidly
   (~20 commands/s alternating) and watch for missed moves or garbled replies.
3. Restore 10/1 Hz: `53 0 0A00010000000000`

**PASS (provisional):** no missed commands/garbling at 50 Hz × 6 + command
bursts. NOTE: the USB-serial bridge (~480 frames/s) can't saturate the bus —
the definitive 100 Hz × 6 flood test repeats after the CANable arrives.

## Gate 5 — Torque/thermal at ≤1.92 A
On J1 (worst gravity load): current 40% (`44 0 2800000000000000`, ≈0.77 A),
enable, hold + slow moves under load for 30 min. Check board temp via
telemetry (MsgType 38 streams automatically) and by touch.
**PASS:** no missed positions, board <70 °C. If torque is marginal, step to
50–60% and re-check thermals (hold-current overheating precedent from Klipper).

## Gate 6 — Gripper servo on AUX PWM (R15) — node 6 (J5)
Servo signal → AUX1, servo power → 5 V BEC, grounds common.

1. Center (1.5 ms): `19A 0 0600330100000000`
2. Sweep: 1.0 ms `19A 0 0600CD0000000000` ↔ 2.0 ms `19A 0 06009A0100000000`
3. Step in small increments between 205–410 counts; confirm smooth, live
   updates (firmware does `ledcWrite` on every value re-send).
4. Off/high-Z: `19A 0 0000000000000000`

**Record:** duty counts at physical gripper-open and gripper-closed →
`duty_open`/`duty_closed` for the driver config. Never enable AUX serial on
this node.

## Gate 7 — Zero-at-boot / park-pose reference (R5)
Per node: enable `48 0 0100000000000000`, save `58 0 ...`, move the joint,
power-cycle, read angle → **must read 0.0 at the powered-on pose.** Then
confirm procedure: park arm → power-cycle → all nodes read ~0.

---

## Results
| Gate | Result | Date | Notes |
|------|--------|------|-------|
| 1 closed-loop ×6 | | | |
| 2 e-stop policy | | | hold/fall per mode |
| 3 speed ceiling | | | per joint |
| 4 rates (bridge) | | | redo on CANable |
| 5 torque/thermal | | | |
| 6 gripper duty | | | duty_open= duty_closed= |
| 7 zero-at-boot | | | |

Remaining gates needing hardware not yet on hand: definitive CAN flood +
control-path latency + ros2_control dry run (after the CANable 2.0 arrives).
