# Arm Re-Calibration Plan (Hand-Eye + Desk Plane)

**Status:** planned, not yet executed (2026-08-01)
**Context:** OAK-1 Lite overhead camera + 6-DOF arm on rail; goal = pick a pen off
the desk. Blocker being addressed here: the ETS FK model's vertical geometry is
wrong by ~170 mm, so `move_cartesian` reports "unreachable / joint-limit" for
physically-fine targets, and a hand-eye homography taken high above the desk has
parallax error.

## Guiding principle
Stop trusting the model's **absolute** Z. Use the operator's physical
measurements as ground truth to pin the real desk plane, then calibrate hand-eye
near that plane. The model is deterministic/repeatable even if absolutely wrong,
so a measured `model_Z_desk` is reusable.

## Known facts
- Arm **base ≈ 94 mm above the desk**; desk is physically reachable.
- Earlier measurement: gripper center **493.7 mm (19-7/16")** above desk at
  FK-reported EE z ≈ 572 mm → implies desk at arm-z ≈ +78; base-above-desk
  implies desk at arm-z ≈ −94. ~170 mm disagreement ⇒ ETS vertical error.
- Green marker on **top** of the gripper (faces overhead camera); tracked via
  `/grip` on the detect-stream (`scripts/vision/oak_detect_stream.py`).
- Arm control via daemon WebSocket `ws://<pi>:9090` (`move_cartesian`, `jog`,
  `get_state`); helpers in `scripts/vision/ws_*.py`.
- Rail is a separate gross axis (not in IK); calibration is per rail position.

## Safety rules (apply throughout)
- Motors enabled only during the routine; **operator keeps a hand on E-STOP** and
  a ruler / paper shim handy.
- Descents are **stepped and slow**: 20 mm steps far out, shrinking to **5 mm**
  near the desk. Report model-Z after each step and **pause for the operator's
  call** before continuing.
- On IK clamp / `unreachable`: **stop**, treat as the reach limit, do not force.

## Phase 0 — Prep (no descent)
- Operator re-enables motors. Restart the detect-stream (marker + pen overlays).
- Move to a safe hover over the reachable-patch center (~X −230, Y 0, high Z);
  confirm the green marker is tracking on `/grip`.

## Phase 1 — Desk plane via touch test  [operator verifies Z]
Find the model-Z equal to the desk surface, and whether it is uniform.
- At **P1 (≈ −230, 0)**: lower in steps; near the bottom the operator calls when
  the gripper **just kisses the desk** (paper drag). Record `model_Z_desk(P1)`.
- Repeat at **P2 (≈ −250, −40)** and **P3 (≈ −250, +40)** (non-collinear).
- Interpretation:
  - Three values ~equal ⇒ constant vertical offset; desk = that Z everywhere.
  - Values differ ⇒ desk tilted/scaled in model; fit a plane `Z_desk(X,Y)`.
- Output: desk plane in model coords + **hover height = desk + 40 mm**.

## Phase 2 — Reachability map (free, from Phase 1)
- Record which (X,Y) reached the desk vs clamped ⇒ **usable pick rectangle** at
  this rail position. If too small, plan a rail move to reposition the patch.

## Phase 3 — Hand-eye XY calibration at hover height
- At hover (desk + 40), drive a grid of XY across the usable rectangle; record
  marker pixel + arm XY at each; fit **pixel → arm-XY homography**. More points
  than the first attempt, over the real pick area, near the desk (low parallax).
- Save to `/home/pi/armold_handeye.json` (H, rail_mm, z_plane, points, error).

## Phase 4 — End-to-end aim + pick test  [operator verifies]
- Operator places the pen in the rectangle. Detect pen → homography → XY → hover
  over it. Operator confirms on the stream the marker sits over the pen. Then
  descend to `Z_desk − grasp_offset` → close gripper (120°) → lift.

## Phase 5 — (optional, later) fix the model
- Use Phase 1/3 data to correct ETS link lengths/offset so commanded Cartesian Z
  matches reality. Nice-to-have; Phases 1–4 already enable a pick.

## Operator involvement points
- Phase 1: three touch checks (P1/P2/P3).
- Phase 4: final grasp verification.
Everything else is run and reported by the agent.

## Tuning knobs (adjust before/while running)
- Descent step sizes (default 20 → 5 mm), speed, hover offset (default 40 mm).
- Grid points / spacing in Phase 3.
- Grasp offset below desk plane in Phase 4 (pen diameter dependent).
