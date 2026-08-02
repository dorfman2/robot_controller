# RTB Cartesian IK — Tasks

## Phase 1: Prototype & Model
- [x] Create Mac venv (Python 3.12) and `pip install roboticstoolbox-python`; confirm imports (rtb 1.3.1, numpy, scipy, spatialmath).
- [x] Build and validate the ETS 6-DOF model (FK sane, reach correct, IK round-trip). Prototype since folded into `ik_solver.py`.

## Phase 2: IK Module
- [x] Create `armold_controller/ik_solver.py`: `ArmGeometry`, `EndEffectorPose`, `CartesianTarget`, `IKResult`, `ArmIK` (fk/solve_ik), `ARM_JOINT_LIMITS_DEG` derived from `klipper_board.DEFAULT_SOFT_LIMITS`.
- [x] Post-solve limit clamping + unreachable/limit-violation handling with safe seed fallback.
- [x] `tests/test_ik_solver.py` — real (no-mock) unit tests.
- [x] Lint clean: ruff, black, isort (black profile), mypy. Added `pyproject.toml` ([tool.mypy] overrides for untyped libs; [tool.isort] profile=black).

## Phase 3: Real Geometry
- [x] Receive measured link lengths (2026-07-31) and replace the proportional estimate with `MEASURED_GEOMETRY` (default, `estimated=False`).
- [x] Add the J4→J5 segment (`wrist_yaw_offset`) — `ArmGeometry` now has 7 length fields; ETS updated.
- [x] Add `horizontal_reach()`; rename spec reach to `SPEC_MAX_REACH_MM` (reference only). Update tests + FK landmarks.

## Phase 4: Controller Wiring
- [x] `ws_server_klipper.py`: `arm_ik` on the server; `_state_message()` adds `end_effector` FK to state; `move_cartesian` → `_handle_move_cartesian` → `KlipperBoard.goto_positions` (arm idx i → board idx i+1).
- [x] Success ack (joint_angles, end_effector, errors) / failure error (reachable, position_error_mm).
- [x] `tests/test_ws_move_cartesian.py` — real in-process WebSocket round-trip (no mocks).

## Phase 5: Web UI
- [x] "Cartesian (IK)" panel: live Tool X/Y/Z/RPY readout, target inputs, "Use current", "Move to pose" (confirm dialog).
- [x] `handleAck` surfaces move_cartesian residual error + updates pose readout.

## Phase 6: Pi Verification & Deploy Prep
- [x] Verify RTB installs (aarch64 wheels) and runs on the Pi 4; benchmark FK/IK (~1 ms/solve). No ikpy fallback needed.
- [x] Create `/home/pi/armold-venv` (`virtualenv --system-site-packages`); confirm all daemon deps resolve.
- [x] Point `pi/armold.service` `ExecStart` at the venv python.
- [x] Update `scripts/deploy_controller.sh` to create/use the venv and install `roboticstoolbox-python` (PEP-668-safe).

## Phase 7: Documentation
- [x] Update steering: `tech-context.md` (IK stack, measured lengths, venv, transferable patterns), `system-patterns.md` (learnings, code structure, IK data flow), `active-context.md` (current focus).
- [x] Write this spec (requirements, design, tasks).

## Pending (user action)
- [ ] Deploy: run `./scripts/deploy_controller.sh` (pushes new code + venv service), or manually rsync + `sudo systemctl restart armold`. (Blocked from agent by deploy guardrails.)
- [ ] Live-test `move_cartesian` on the real arm — start with position-only targets near home; watch `position_error_mm` in the UI/log.
- [ ] Confirm J4/J5 axis labels (yaw vs roll) on the physical arm.

## Future
- [ ] Trajectory smoothing (candidate: `ruckig`, jerk-limited) — current move is point-to-point per-joint, no path/collision planning.
- [ ] Vision-driven targets (OAK-1 Lite) feeding `move_cartesian`.
