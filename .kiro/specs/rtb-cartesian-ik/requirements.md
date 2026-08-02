# RTB Cartesian IK — Requirements

## Goal
Give the Armold 6-DOF arm Cartesian (tool-tip) motion via inverse kinematics,
using the Robotics Toolbox for Python (RTB). The user specifies a tool-tip pose
(X/Y/Z, optional roll/pitch/yaw) and the controller solves joint angles and
drives the six arm joints through the existing Klipper/Moonraker path. The
linear rail is commanded separately as a gross-positioning axis and is NOT part
of the kinematic chain.

## Background
The motion base (Klipper on the BTT Octopus MAX EZ, 7 EZ5160 drivers, web UI,
waypoints, soft limits) is complete and validated. The next capability is
movement planning: converting a desired end-effector pose into joint angles.

## Library Decision
- **Chosen: Robotics Toolbox for Python (RTB)** — pure-Python install, prebuilt
  aarch64 wheels, ETS model building (no URDF authoring), fast LM IK (~1 ms on
  the Pi), good FK/pose tooling via spatialmath.
- **Rejected**: ikpy (kept as the step-down fallback — weaker redundancy /
  collision handling), Trac-IK (best redundant solver but heavy KDL/NLopt
  build), Pinocchio/Pink (overkill, heavy install), pytorch_kinematics
  (GPU-oriented, pointless on the Pi).

## Requirements

### R1 — Arm-only kinematic model
- The system **MUST** model exactly the six rotary joints (J0..J5) and **MUST
  NOT** include the linear rail in the IK chain.
- The model **MUST** be built from an RTB ETS (Elementary Transform Sequence),
  not a hand-authored URDF or DH table.
- Joint axes **MUST** be: J0 yaw about Z, J1/J2/J3 pitch about Y, J4 yaw about
  Z, J5 roll about X (Z-up base frame; zero pose points straight up).

### R2 — Real geometry
- Link lengths **MUST** use the measured physical values (mm): base→J0 70,
  J0→J1 48, J1→J2 152, J2→J3 152, J3→J4 77, J4→J5 60, J5→tip 83.
- The geometry **MUST** carry an `estimated` flag; the proportional-estimate
  path is retained only as a fallback.

### R3 — Forward kinematics
- The system **MUST** provide FK: six joint angles (degrees) → tool-tip pose
  (X/Y/Z mm + roll/pitch/yaw degrees, XYZ intrinsic).

### R4 — Inverse kinematics
- The system **MUST** solve IK for a Cartesian target and return six joint
  angles in degrees.
- Position-only targets (orientation omitted) **MUST** be supported by masking
  orientation error.
- Solutions **MUST** be clamped to the per-joint soft limits, which **MUST** be
  the same limits used by the motion controller (single source of truth).
- Unreachable or limit-violating targets **MUST** fail safely: no motion is
  commanded and the caller receives a diagnostic; the returned joint angles
  **MUST** remain within limits (fall back to the seed pose).

### R5 — WebSocket command
- The system **MUST** accept a `move_cartesian` command
  (`{cmd, x, y, z, [roll], [pitch], [yaw], [speed]}`) and drive arm joints 1..6.
- The system **MUST** broadcast the current end-effector FK pose in the state
  message so the UI can display tool position live.
- On success the ack **MUST** include the solved joint angles, achieved pose,
  and residual position/orientation error.

### R6 — Web UI
- The web UI **MUST** provide a Cartesian panel: live tool X/Y/Z/RPY readout,
  target inputs, "use current", and a "move to pose" action with a confirmation
  prompt (all six joints move; the rail stays put).

### R7 — Pi deployability
- RTB **MUST** install and run on the Pi 4 (aarch64, Python 3.12).
- The daemon **MUST** run from an environment where RTB is importable.

### R8 — Engineering standards
- Python **MUST** follow the project python-prefs (type hints, verbose
  docstrings, dataclasses, no-mock tests) and logging-standards (module logger,
  lazy % formatting). Linting (ruff/black/isort/mypy) **MUST** pass.

## Open Items
- **J4/J5 axis labels** (yaw vs roll) are disputed between the FK simulator and
  the Klipper config. The kinematic order (J4 about Z, J5 about X) is correct
  regardless; only the human-facing label needs confirmation on the physical
  arm.
- No trajectory smoothing / path planning yet (point-to-point per-joint move,
  no collision checking). Candidate: `ruckig`.
