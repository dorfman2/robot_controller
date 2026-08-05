# Vision Upgrade — OAK-4 S Overhead + OAK-1 Lite Side View — Requirements

## Goal
Upgrade Armold's vision system from a single overhead OAK-1 Lite to a **two-camera**
setup: a new **OAK-4 S** as the high-resolution, on-device-AI overhead camera, and
the **relocated OAK-1 Lite** as a **side/profile camera** near desk level so the
gripper and target are visible *during* the pick. The upgrade must improve pen (and
general small-object) pick reliability: better target localization + orientation
from the OAK-4 S, and closed-loop height/grasp verification from the side view.

## Background (current state, 2026-08-03)
- Single OAK-1 Lite overhead, USB-C to the Pi, DepthAI **v3** (3.8.0) in
  `/home/pi/armold-venv`; MJPEG detect-stream service `oak-stream` on `:8091`.
- Pen detection is **classic CV** (flat-field bg subtraction + elongation) in a mat
  ROI; gripper marker is green tape (HSV), midpoint = grasp point.
- Motion/kinematics are solid: RTB IK, `move_cartesian`, and a validated
  **clean-wrist vertical descent** (J5=0, J4=−90, J1/J2/J3 free) giving a reliably
  vertical gripper. Desk plane empirically calibrated at **commanded model z≈74** at
  x=−350 (absorbs ~74 mm of droop/backlash/finger offset).
- **Known problem this upgrade must solve:** when the gripper points straight down,
  its green marker faces the desk and is **not visible to the overhead camera**, so
  overhead-only hand-eye cannot verify the final descent/grasp.

## Hardware Changes

| Component | Role | Connection | Status | Notes |
|-----------|------|-----------|--------|-------|
| OAK-4 S | Overhead (primary) | **Local network (IP); powered by USB-C supply** | Swapped in, on LAN | Single-lens 48 MP RGB (no stereo), RVC4 ~52 TOPS AI, 8 GB/128 GB, Luxonis OS, DepthAI v3. PoE+ is an *alternative* power path, not required |
| OAK-1 Lite | Side / profile | USB-C to Pi | Relocated | 13 MP mono, moved to arm-frame **≈(−600, 0, 15) mm** looking back toward the arm/desk |
| USB-C power supply (OAK-4 S) | Power for OAK-4 S | wall/USB-C | On hand | Separate from data; ~25 W-capable USB-C supply |
| Side-camera mount (3D print) | Hold OAK-1 Lite at (−600,0,15) | — | To design | Rigid, at ~desk level, aimed +X across the pick zone |
| Overhead mount (adapt) | Hold OAK-4 S | — | To adapt | Heavier/larger than OAK-1 Lite; verify FoV covers the mat |

## Requirements

### R1 — Two-camera architecture
- The system **MUST** support both cameras concurrently via **DepthAI v3**: OAK-4 S
  over **IP (local network)**, OAK-1 Lite over **USB-C**.
- The OAK-4 S **MUST** be addressed by a stable identifier (IP / mxid) and the OAK-1
  Lite by its USB mxid, so the two are never confused.
- Loss of one camera **MUST NOT** crash the other's stream/service.

### R2 — OAK-4 S overhead perception (target localization)
- The OAK-4 S **MUST** detect the target object(s) (pen first) and report, per
  detection: image-pixel center, an **orientation** (long-axis angle), and a
  confidence.
- Detection **SHOULD** run **on-device** on the RVC4 (freeing the Pi CPU); the Pi
  receives detections + a stream, not raw full-res frames for CPU inference.
- The pipeline **MUST** expose results over the existing HTTP/WS surface (extend the
  `oak-stream` service): an overlay stream + a JSON endpoint giving detection
  center, orientation, and confidence.
- The system **MUST** be able to use the 48 MP sensor's resolution (full-frame or a
  cropped ROI) to localize small objects; the working ROI **MUST** be configurable
  (as the current mat `ROI_FRAC` is).

### R3 — OAK-1 Lite side/profile perception (height + grasp verification)
- The side camera **MUST** provide a horizontal profile view of the pick zone
  (x≈−350..−490) at ~desk level, such that the **vertical gap between the gripper
  finger tips and the desk** is measurable in image pixels.
- The system **MUST** expose a side-view JSON endpoint reporting the gripper-tip
  height above the desk (px, and mm after calibration) and, when possible, the
  target's top height — enabling **closed-loop touchdown** instead of relying only
  on the model z-offset.
- The side view **SHOULD** support grasp verification: detect whether the object is
  between the gripper fingers after closing.

### R4 — Calibration (both cameras)
- Overhead: a **pixel → arm-XY homography** at the desk plane **MUST** be
  (re)calibrated for the OAK-4 S (higher resolution; new mount). The procedure
  **MUST** pair a visible gripper feature (or a placed target) at known arm-XY
  positions with its overhead pixel, at a fixed rail position and Z plane.
- Side: a **pixel → arm-(Z, Y)** mapping **MUST** be calibrated for the OAK-1 Lite
  so tip-height pixels convert to mm above the desk.
- Calibrations **MUST** persist to JSON on the Pi and **MUST** record the rail
  position / plane they are valid for.

### R5 — Pick workflow using both cameras
- The pick sequence **MUST** be: overhead detect (XY + orientation) → set gripper
  **yaw via base J0** to align fingers across the object → move over the target at a
  safe hover (clean-wrist vertical column) → **descend with side-camera gap
  feedback** to touchdown/grasp height → close gripper → **verify grasp** (side
  view) → lift.
- Gripper orientation (fingers perpendicular to the pen long axis) **MUST** be set
  by the base joint J0 (and/or arm geometry), **NOT** by fragile wrist J3/J5 near the
  J4=−90 singularity (see clean-wrist findings).
- The descent **MUST** stop at the side-camera-measured contact/grasp height or at
  the calibrated desk plane (model z≈74 fallback), whichever is safer.

### R6 — Depth strategy (monocular cameras)
- Neither camera provides stereo depth. Target **Z MUST** come from the known desk
  plane; **height/descent MUST** be refined by the side camera. The system **MAY**
  triangulate the target's 3D position from the intersection of the overhead and
  side rays as an enhancement.

### R7 — Networking & power
- The OAK-4 S is powered by a **separate USB-C supply** and communicates over the
  **local network (IP)**; the Pi **MUST** reach it by a stable address (DHCP
  reservation / mDNS / mxid). PoE+ is an optional alternative power path and is
  **NOT** required.
- The design **MUST** document the camera's network address and how DepthAI v3
  connects to it by IP.
- Because the OAK-4 S is **not on USB**, USB bandwidth **MUST** improve vs today
  (only the OAK-1 Lite and the BTT board remain on USB); the relocation **MUST NOT**
  regress either USB link (enumeration/bandwidth).

### R8 — Services & deployment
- The `oak-stream` service **MUST** be extended (or split into two services) to
  drive both cameras, restart cleanly after a camera replug/reboot, and survive the
  OAK-4 S network reconnect (the current `X_LINK_ERROR`-on-unplug behavior
  **MUST** recover on restart).
- New/changed vision code **MUST** live in the repo (`scripts/vision/` and/or a
  proper module) and deploy to the Pi via the existing base64/rsync path.

### R9 — Engineering standards
- Python **MUST** follow project python-prefs (type hints, verbose docstrings,
  dataclasses, **no-mock** tests) and logging-standards (module logger, lazy `%`).
- Linting (ruff/black/isort/mypy) **MUST** pass. Camera/hardware-dependent code
  **SHOULD** be integration-tested against the real devices where feasible.

### R10 — Grasp-yaw decoupling via the rail (from edge case C1)
- Because only the base **J0** yaws a vertical gripper cleanly (verified) and J0 also
  sets the reach azimuth, finger yaw and target XY are coupled. The system **MUST**
  treat the **linear rail as the decoupling DOF**: solve `(rail, J0, J1, J2, J3)` for
  `(X, Y, Z, finger-yaw)` with J4=−90 and J5=0 fixed.
- Wrist joints J4/J5 **MUST NOT** be used to set finger yaw (they tilt the gripper).
- When no in-limits / in-rail-travel solution achieves the required yaw, the system
  **MUST** reject the pick (or request a nudge) rather than grasp at a wrong angle.
- A kinematic study **MUST** map the achievable finger-yaw range vs target XY and
  rail travel before the pick loop relies on orientation.

### R11 — Multi-point desk-Z calibration (from edge case C2)
- The model→physical Z offset (droop + backlash + finger) varies with pose, so a
  single point (z≈74 at x=−350) is insufficient. The system **MUST** calibrate the
  Z offset at several XY across the pick zone and interpolate.
- The final descent **MUST** prefer the **side-camera gap** measurement, using the
  interpolated model-Z only as a **safety floor** (never descend past it).

### R12 — Fail-safe on stale/lost perception & faults (from cameras/state cases)
- The pick loop **MUST NOT** descend on stale or missing detections; on camera loss,
  network drop, or low confidence it **MUST** hold or lift, never guess.
- On service/daemon crash or E-STOP mid-pick, the arm **MUST** end in a defined safe
  state (hold energized or controlled lift), never a blind descent.
- Camera addressing **MUST** survive reconnects (IP reservation/mDNS + retry), and
  one camera's failure **MUST NOT** take down the other (reaffirms R1/R8).

### R13 — Reachability gating (from kinematics cases)
- Before any pick, the system **MUST** verify the target is reachable with a vertical
  clean-wrist gripper (desk reach ≈ to x=−400; larger |Y| limited) at the current or
  a commandable rail position; unreachable targets **MUST** be rejected or trigger a
  rail relocation (with recalibration), not a clamped/partial move.

## Success Criteria
- Both cameras stream concurrently; overhead reports pen center + orientation,
  side reports gripper-tip height, each on its JSON endpoint.
- Overhead homography localizes a placed pen to within **±10 mm** arm-XY.
- Side-camera-guided descent touches the desk within **±3 mm** of the intended
  height without relying solely on the model offset.
- End-to-end pen pick (detect → align yaw → descend → grasp → verify → lift)
  succeeds **≥ 8/10** on a pen lying on the mat.
- One camera failing does not take down the other.

## Constraints & Open Items
- OAK-4 S is **monocular** (no stereo depth) — do not assume a depth map.
- OAK-4 S is USB-C powered and on the local network (IP) — no PoE+ needed; the risk
  is stable network addressing (use a DHCP reservation / mDNS / mxid).
- Side camera at (−600, 0, 15) is **beyond** the arm's reach (reach to J5 ≈ 490 mm)
  — confirm it is out of the arm's swept volume and won't be struck.
- Whether to run OAK-4 S perception **on-device (Luxonis OS)** vs **host-side (Pi
  over IP)** is a design decision (see design.md); default host-side for parity with
  current code, on-device as an enhancement.
- Model choice (classic CV vs trained detector vs oriented-bbox/segmentation model)
  is a design decision; must yield object **orientation** for yaw alignment.
- Supersedes the obsolete `oak1-vision-pick` spec (DepthAI v2 / Myriad X / grblHAL).
