# RTB Cartesian IK — Design

## Overview
A new `armold_controller/ik_solver.py` wraps RTB to provide FK/IK for the 6-DOF
arm. The Klipper WebSocket server gains a `move_cartesian` command that solves
IK and dispatches per-joint absolute moves through the existing `KlipperBoard`.
The web UI gains a Cartesian panel. The rail stays out of the kinematic chain.

## Kinematic Model (ETS)
Z-up base frame anchored at the rail carriage; link offsets along local Z;
built with RTB `ET`:

```
tz(base_height=70) · Rz[J0]          # base yaw
· tz(shoulder_height=48) · Ry[J1]    # shoulder pitch
· tz(upper_arm=152) · Ry[J2]         # elbow pitch
· tz(fore_arm=152) · Ry[J3]          # wrist pitch
· tz(wrist_pitch_offset=77) · Rz[J4] # wrist yaw
· tz(wrist_yaw_offset=60) · Rx[J5]   # wrist roll
· tz(tool_len=83)                    # tool tip / TCP
```

- 6 revolute joints. Zero pose points straight up (+Z).
- Horizontal reach (J0 axis → tool tip) = 152+152+77+60+83 = **524 mm**.
- FK landmarks: zero = (0,0,642); home `[0,-30,70,50,0,0]°` = (241.7,0,366.1);
  extension `[0,90,0,0,0,0]°` = (524,0,118).

## Public API (`ik_solver.py`)
- `ArmGeometry` (frozen dataclass): 7 link lengths + `estimated`;
  `horizontal_reach()`; `from_proportional_dims()` fallback.
- `MEASURED_GEOMETRY`: the real measured geometry (`estimated=False`), default.
- `EndEffectorPose` (frozen dataclass): x, y, z (mm), roll, pitch, yaw (deg).
- `CartesianTarget` (frozen dataclass): x, y, z + optional roll/pitch/yaw;
  `position_only` property; `to_se3()`.
- `IKResult` (frozen dataclass): success, reachable, joint_angles_deg[6],
  position_error_mm, orientation_error_deg, clamped, iterations, message.
- `ArmIK`:
  - `fk(joint_angles_deg) -> EndEffectorPose`
  - `solve_ik(target, seed_deg=None) -> IKResult`
  - `.ets`, `.geometry`, `.limits_deg`
- `ARM_JOINT_LIMITS_DEG`: derived from `klipper_board.DEFAULT_SOFT_LIMITS[1:7]`
  (single source of truth; index 0 = rail is skipped).

### IK algorithm
- RTB `ETS.ik_LM` (Levenberg-Marquardt) with internal random restarts
  (`ilimit=60`, `slimit=150`, `tol=1e-6`).
- `mask=[1,1,1,0,0,0]` for position-only targets; all-ones for full pose.
- `joint_limits=False` at the solver — limits enforced by this module
  (post-solve): wrap raw solution to [-180,180]°, clamp to per-joint limits,
  recompute FK, and report the residual for the clamped angles.
- Success requires solver convergence, position error ≤ 1 mm, no clamping, and
  (full-pose) orientation error ≤ 1°. On failure, return the in-limits seed
  (or home) so callers always receive a valid configuration.
- Orientation error = geodesic angle from `trace(R_target.T @ R_achieved)`.

## Controller Wiring (`ws_server_klipper.py`)
- `KlipperWebSocketServer.__init__` gains `arm_ik` (default `ArmIK()`).
- `_state_message()` augments `KlipperBoard.get_state()` with `end_effector`
  = FK of the current arm joints (`board.position[1:7]`); used at all three
  state-send sites (connect, get_state, 2 Hz broadcast).
- `move_cartesian` → `_handle_move_cartesian`:
  1. Parse x/y/z (required) + optional roll/pitch/yaw + speed.
  2. Seed IK with the current arm joints for continuity.
  3. On failure: send `{type: error, cmd, message, reachable,
     position_error_mm}` (no motion).
  4. On success: map arm index i → board index i+1 and call
     `KlipperBoard.goto_positions({i+1: angle})`; ack with joint_angles,
     end_effector, position_error_mm, orientation_error_deg.

### Joint index mapping
`ArmIK` arm joints 0..5 = J0..J5. `KlipperBoard` index 0 = rail, 1..6 = J0..J5.
So board index = arm index + 1.

## Web UI (`web/index.html`)
- "Cartesian (IK)" side panel: live Tool X/Y/Z/RPY readout (from
  `state.end_effector`); target inputs x/y/z + optional roll/pitch/yaw;
  "Use current" (fills from live pose); "Move to pose" (validates, confirm
  dialog, sends `move_cartesian` at the current speed profile).
- `handleAck` special-cases `move_cartesian` to surface residual error and
  update the pose readout.

## Deployment
- Daemon runs from `/home/pi/armold-venv` (virtualenv `--system-site-packages`)
  so RTB (+ scipy/spatialmath) is importable on top of apt numpy/pyserial/
  websockets/aiohttp. Required because `ws_server_klipper` now imports RTB and
  system python lacks it. Ubuntu 24.04 PEP-668 blocks `pip install --user`.
- `pi/armold.service` `ExecStart` = `/home/pi/armold-venv/bin/python -m
  armold_controller`.
- `scripts/deploy_controller.sh` creates the venv if missing and installs
  `pyserial websockets aiohttp roboticstoolbox-python` into it.

## Testing
- `tests/test_ik_solver.py` (15): geometry, FK landmarks, reach, IK round-trip
  (full pose + position-only), unreachable handling, limit clamping, validation.
- `tests/test_ws_move_cartesian.py` (4): real in-process WebSocket round-trip
  (no mocks) — initial EE pose, unreachable, reachable ack, missing coords.
- No mocks (python-prefs). RTB solver runs for real in every test.

## Performance (Pi 4, aarch64)
ETS build ~1.4 ms; FK ~0.001 ms; IK ~1 ms/solve (20/20 converged). No GPU; no
ikpy fallback needed.
