# Vision Upgrade — OAK-4 S Overhead + OAK-1 Lite Side View — Design

## Overview
Two fixed monocular cameras with complementary roles:
- **OAK-4 S (overhead):** high-resolution, on-device-AI target finder — *where* the
  pen is in the desk plane and *which way it points*.
- **OAK-1 Lite (side, ≈(−813,0,33)):** low-angle profile — *how far* the gripper is
  above the desk and *whether the grasp succeeded*.

Together they cover the two things a single overhead monocular camera can't do well:
precise orientation for grasp alignment, and vertical (Z) feedback during the blind
final descent (the marker-occlusion problem).

```
                 OAK-4 S (overhead, network/IP; USB-C power)  OAK-1 Lite (USB-C)
                 48MP RGB, RVC4 ~52 TOPS on-device AI        13MP mono, side profile
                        |  detections (px, angle, conf)            |  gripper-tip height px
                        v  + overlay stream                        v  + grasp verify
   ┌──────────────────────────────────────────────────────────────────────────┐
   │ Raspberry Pi 4  —  vision service(s) (DepthAI v3)                          │
   │   overhead: pixel→arm-XY homography + orientation                          │
   │   side:     pixel→arm-(Z,Y); gripper-tip gap; grasp check                  │
   │   pick orchestrator → armold_controller (WS 9090)                          │
   └──────────────────────────────────────────────────────────────────────────┘
                        |  move_cartesian / clean-wrist column / J0 yaw / gripper
                        v
             Klipper (BTT Octopus MAX EZ) → 7 EZ5160 → arm + gripper
```

## OAK-4 S Capability Analysis (how it improves the arm)
The OAK-4 S is **monocular** (single 48 MP RGB, no stereo), so it does **not** add a
depth map. Its value is **compute + resolution + standalone AI** (RVC4, ~52 TOPS,
8 GB/128 GB, Luxonis OS). Mapped to concrete arm improvements:

1. **On-device inference frees the Pi.** Heavy detection/segmentation runs on the
   RVC4, not the Pi CPU — the Pi keeps headroom for IK, motion, and the pick loop.
   (OAK-1 Lite's Myriad X could only run small nets and competed for USB bandwidth.)
2. **Object orientation → correct grasp yaw.** Run an **oriented-bounding-box** or
   **segmentation** model to get the pen's long-axis angle so the fingers close
   *across* the pen. **Caveat (verified, see Edge Cases C1):** only the base **J0**
   yaws a vertical gripper cleanly, and J0 also sets the reach azimuth — so yaw and
   target XY are coupled. The **linear rail** is the decoupling DOF: coordinate
   rail + J0 to reach the target XY *and* choose the finger yaw. Wrist joints
   (J4/J5) tilt rather than yaw when vertical, so they are NOT used for yaw.
3. **48 MP resolution → sub-pixel small-object localization.** Detect a thin pen
   precisely over the whole mat; crop/zoom digitally for fine XY. Tighter homography
   → better pick accuracy (helps hit the ±10 mm target).
4. **Instance segmentation → real grasp point.** A pen mask gives the true centroid
   and principal axis (not just a bbox center), and disambiguates clutter/overlap.
5. **On-device tracking (ObjectTracker).** Stable IDs across frames for multiple
   objects and for confirming a detection is persistent before committing a pick.
6. **Higher FPS + low latency → visual servoing (future).** Real-time XY correction
   of the gripper over the target during approach, rather than one open-loop move
   after homography.
7. **Better sensor/HDR → lighting robustness.** Reduces the green-marker
   desaturation and shadow problems seen under bright lights.
8. **Model Zoo / `nn_archive` (DepthAI v3).** Deploy pretrained detectors quickly and
   swap in a fine-tuned pen/tool model without host-side conversion pain.

**Adopted now:** #1 (on-device detect), #2 (orientation→J0 yaw), #3 (hi-res XY).
**Adopted next:** #4 (segmentation grasp point), #5 (tracking).
**Future:** #6 (visual servoing), leveraging the side camera for Z.

## On-device Model (RVC4) — status & custom pen-model path
**Verified (2026-08-04):** on-device inference runs on the OAK-4 S RVC4 via
DepthAI v3 — stock `yolov6-nano` (HubAI zoo) auto-downloaded + compiled for RVC4,
ran ~29 FPS on-device, and the Pi received only `ImgDetections` (it detected the
in-scene monitor/keyboard). Code: `on_device_detect.py` (`build_detection_network`
+ `parse_detections`); proof script: `oak4_nn_test.py`. Model formats: a HubAI
zoo slug or a local `nn_archive` (`.tar`) — **`.blob` is RVC2/Myriad only, not
RVC4.**

**COCO has no "pen" class**, so pen detection needs a custom-trained model. Path:
1. **Dataset** — capture pen/tool images from the OAK-4 overhead view over the mat
   (varied pose/lighting/clutter); annotate boxes (or oriented boxes for grasp
   yaw) in Roboflow.
2. **Train** — YOLOv6/YOLOv8 (ultralytics, dev machine) or Roboflow RF-DETR.
3. **Convert** — HubAI ModelConverter → RVC4 `nn_archive` (`.tar`) (Colab or CLI).
4. **Deploy** — put the archive on the Pi (or publish to HubAI), set
   `on_device_detect.MODEL_SLUG` to the slug/path, restart `oak-overhead`; the
   service then switches from host-side classic-CV to on-device NN.
5. **Orientation for grasp yaw** — use an oriented-bbox model, OR run the existing
   `_long_axis_angle_deg` on the NN's cropped detection to recover the long axis.

Until the custom model exists, the overhead service uses the **host-side
classic-CV** pen detector (`detectors.detect_pen`), which is validated and works
for the current pick.

## Camera Roles & Geometry
- **Overhead OAK-4 S:** looks down at the mat. Image → **arm XY** via a desk-plane
  homography (same method as today, higher res). Provides target XY + orientation.
- **Side OAK-1 Lite at ≈(−813, 0, 33) mm looking +X** (measured: 32" from rail
  center, 1 5/16" above desk): its image vertical axis ≈ arm
  **Z** (height), horizontal axis ≈ arm **Y**; depth-into-image ≈ arm **X**. So it
  directly measures **gripper-tip height above the desk** and Y-alignment — exactly
  the Z feedback the overhead view lacks during a straight-down descent. It cannot
  resolve X (depth); X comes from the overhead camera. (Confirm (−813,0,33) is
  outside the arm's swept volume; reach to J5 ≈ 490 mm, tool tip to ≈ −491 mm.)

## Calibration
- **Overhead pixel→arm-XY homography:** drive the arm to a grid of known arm-XY at a
  fixed hover Z + rail position; at each point pair a detectable gripper feature (or
  a placed fiducial) with its overhead pixel; `cv2.findHomography`. Persist to
  `~/armold_handeye_overhead.json` with rail/plane metadata.
- **Side pixel→arm-(Z,Y):** step the gripper to known heights (using the calibrated
  clean-wrist column, e.g. z=74/100/150/200) at fixed X,Y; record tip pixel-row per
  height → linear/affine fit px→mm. Persist to `~/armold_sideview.json`.
- Both are **plane/rail-specific**; re-run if the rail moves or a camera is moved.

## Depth Strategy
- Target **Z**: known desk plane (grasp at desk + pen radius).
- **Descent height**: refined live by the side camera (tip-to-desk gap), with the
  model z≈74 as fallback/safety floor.
- **Optional 3D**: intersect the overhead ray (XY) and side ray (Z) for a full 3D
  target fix; useful if objects aren't flat on the desk.

## Pick Workflow
1. **Detect** (overhead): pen center (px) + long-axis angle + confidence; reject
   below threshold; require a persistent/tracked detection.
2. **Localize**: homography → arm (X, Y) at the desk plane.
3. **Align yaw**: solve **rail + J0** together so the gripper reaches the target XY
   *and* the fingers are perpendicular to the pen long axis (wrist stays clean:
   J4=−90, J5=0). If no (rail, J0) solution gives a graspable yaw within limits,
   reject or nudge (see Edge Cases C1).
4. **Hover**: clean-wrist vertical column to (X, Y) at a safe hover Z (both marker
   and target visible to the side camera).
5. **Descend**: step down the clean-wrist column; use **side-camera gap** to stop at
   grasp height (fallback: model z≈74). Overhead may be occluded by the arm — that's
   fine; side view drives this phase.
6. **Grasp**: close gripper (servo 120°).
7. **Verify** (side): object present between fingers; if not, retry/abort.
8. **Lift** and transport.

## Integration with `armold_controller`
- Reuse: `move_cartesian`, the **clean-wrist column** generator
  (`scripts/vision/clean_column.py`), `col_move`-style joint commands, gripper
  servo, `ws_state`/`ws_enable`/`ws_disable` helpers.
- **New**: a pick orchestrator that consumes both cameras' JSON, computes J0 yaw +
  target XY, and sequences the moves. Gripper yaw via J0; height via side camera.
- **Code TODO dependency**: a daemon `goto_joints` command + startup position read
  would remove the `col_move`-via-Moonraker desync; recommend landing it so the pick
  loop keeps the daemon in sync (tracked in active-context).

## Networking & Power
- OAK-4 S: **powered by a separate USB-C supply**, **data over the local network
  (IP)**. Camera is on the LAN with a stable address (DHCP reservation / mDNS /
  mxid); DepthAI v3 connects **by IP**. **PoE+ not required** (optional alternative
  power). Document the camera's address.
- OAK-1 Lite: USB-C to Pi (unchanged link, relocated mount). BTT board stays on USB.
  Net USB load *drops* vs today (OAK-4 is off USB entirely — power via USB-C supply,
  data via network).
- Optional: run OAK-4 S perception **on-device (Luxonis OS)** and have the Pi consume
  results over IP — reduces Pi load further; default to host-side pipeline first for
  parity, promote to on-device once stable.

## Software & Dependencies
- `depthai` v3 (already on Pi) — both OAK and OAK4 devices.
- `opencv-python(-headless)`, `numpy` — homography, side fit, overlays.
- Model: start with the current classic-CV detector adapted to OAK-4 frames to get
  running, then move to an **oriented-bbox/segmentation** model (Model Zoo or a
  fine-tuned pen/tool model) for orientation + robust localization.
- Services: extend `oak-stream` (systemd) into overhead + side producers, each with
  `/stream` (overlay) and a JSON endpoint (`/target` overhead, `/gap` side).

## Testing
- No-mock unit tests for the geometry math: homography apply, side px→mm fit, pen
  angle → J0 yaw mapping (pure functions, real numbers).
- Integration: both cameras enumerated concurrently; endpoints return well-formed
  JSON; calibration round-trips (known arm-XY → pixel → arm-XY within tolerance).
- Hardware bring-up checklist for USB-C power + network/IP addressing.

## Risks
- **Network reachability/addressing**: OAK-4 S is on the LAN (USB-C powered); a
  changing DHCP IP breaks DepthAI addressing → use a reservation/mDNS/mxid. (No PoE+
  dependency.)
- **Side-camera occlusion/lighting**: gripper may self-occlude the tip at some poses;
  validate the (−813,0,33) angle covers the pick zone.
- **On-device vs host-side** parity: DepthAI v3 API differences for OAK4; validate
  the chosen models compile/run on RVC4.
- **Mount rigidity**: any camera shift invalidates calibration; mounts must be rigid
  and their calibrations easy to re-run.

## Edge Cases & Mitigations

### C1 — Grasp-yaw controllability (VERIFIED against the RTB model)
At a clean vertical config `[0,−32.88,107.45,−50.32,−90,0]` (approach straight down),
perturbing single joints by +10°:

| joint | Δtilt (approach) | Δfinger-yaw | ΔEE position |
|-------|------------------|-------------|--------------|
| J0 (base) | **0°** (stays vertical) | **−10°** (clean yaw) | +5, **+61**, 0 mm |
| J4 | +10° (tilts) | 0° | ~0 |
| J5 | +10° (tilts) | 0° | ~0 |

**Finding:** only **J0 yaws the vertical gripper cleanly**, and it simultaneously
moves the arm (~61 mm/10° here) because J0 sets the reach azimuth. Wrist J4/J5
**tilt** instead of yawing. So finger yaw and target XY are **coupled** on the
6-DOF arm at a fixed rail position.
**Mitigation:** treat the **rail as the decoupling DOF** — solve `(rail, J0, J1,
J2, J3)` for the 4 constraints `(X, Y, Z, finger-yaw)` (J4=−90, J5=0 fixed).
Coordinating the rail with J0 lets the arm reach the target XY across a range of
J0 values, i.e. a range of achievable finger yaws. Where no in-limits/in-travel
solution exists, restrict picks to a graspable yaw window or nudge the pen. A
dedicated kinematic study (tasks Phase 5a) must map the graspable yaw range vs
target XY and rail travel before the pick loop relies on orientation.

**C1 investigation result (quantified, `scripts/vision/grasp_yaw_investigate.py`):**
reach azimuth = **180° − J0** (clean), finger-yaw = −J0. Solving `rail + J0`
correctly (fix J0, choose the rail position that puts the target on that azimuth,
then check the planar reach) gives:
- **Rail ⟂ reach (base-Y): a usable but NARROW, ASYMMETRIC window** — ≈ **+10°..+40°**
  at (−350,0,100), ≈ −5°..+40° off-center, ≈ +5°..+30° at far reach (~30–45° wide,
  biased positive because the rail travels 0→406 mm one way from home).
- **Rail ∥ reach (base-X): essentially NO yaw control** for on-axis targets (0° only).

**Implications:** (a) the generated `grasp_yaw_solver.py` "only 0° works" was a
**bug** (it never fixes J0 and sweeps the rail along X), not the true limit; (b)
grasp-yaw is **controllable but limited** — arbitrary pen angles are NOT graspable
at a fixed target. **Rail axis CONFIRMED ⟂ to the reach (base-Y) — the favorable
case**, so the usable-but-narrow window above applies (NOT the dead ∥ case). The
window center shifts with the target's Y and the rail working position: at target
Y=0 with rail home at one end it is one-sided (≈+10..+40°); a +Y target (e.g.
−300,+50) widens it (≈−5..+40°). Widen further by centering rail travel (shift
both ways), repositioning the base per target, or a **nudge/reject** policy for
out-of-window angles. `grasp_yaw_solver.py` needs a rewrite (fix J0 + correct rail
geometry).

### C2 — Desk plane is a single calibrated point, not a plane
z≈74 was measured only at x=−350; droop+backlash vary with pose, so the
model→physical Z offset differs across the mat. **Mitigation:** calibrate the
z-offset at a small XY grid and interpolate; always prefer the **side-camera gap**
for the final descent, with the interpolated model-z as a safety floor.

### C3 — Side camera cannot resolve X (depth)
At (−813,0,33) looking +X, the image collapses arm-X: objects at different X
project onto the same column, and the px→mm height scale changes with X.
**Mitigation:** take X only from the overhead camera; calibrate side px→mm **as a
function of X**, and only trust the tip-height reading at the known target X.

### Other edge cases (by subsystem)

**Cameras / connectivity**
- OAK-4 S network drop mid-pick → detections freeze. Loop **MUST NOT descend on
  stale detections**; on loss, hold/lift.
- Slow RVC4 boot; DHCP IP change breaks addressing → require reservation/mDNS +
  retry (no crash). RVC4 thermal throttling under sustained inference.
- OAK-1 Lite USB re-enumeration (`X_LINK_ERROR`) + USB contention with the BTT
  board; service must recover on replug. No cross-device frame sync (IP vs USB).

**Perception**
- No detection / target out of ROI / arm occludes target before XY is locked
  (finalize XY *before* the arm occludes it).
- Multiple candidates + false positives (shadows, cables, rail, the gripper, barrel
  glare) → require a persistent/tracked detection + selection priority.
- Orientation degeneracies: 180° long-axis ambiguity (ok for symmetric grasp),
  near-circular projection (pen end-on) → orientation undefined, skip; merged blobs
  when objects touch → wrong axis.
- Contrast/lighting: classic-CV assumes dark pen on dark mat; bright light
  desaturates the green marker; moving-arm shadows.

**Kinematics / motion**
- Reachability: vertical-gripper desk reach only to ~x=−400 (x=−450→z≥55,
  −480→z≥75); targets beyond or at large |Y| need a rail move (invalidates
  calibration) → loop must detect and reject/relocate.
- J4=−90 sits at the exact soft limit (daemon jog-to-exact-limit bug) → avoid the
  daemon jog path (col_move / −89 / the `goto_joints` fix).
- Desync: mixing `col_move` (Moonraker-direct) with daemon moves corrupts tracked
  position → land `goto_joints` + startup position read (dependency).
- Clean-wrist columns are per-X → regenerate + reachability-check per pick XY.

**Grasp / manipulation**
- Cylindrical pen rolls when nudged; grasp-verify false positives; over-descent into
  the desk if the side gap fails (keep a hard model-z floor); slip during lift; pen
  diameter vs 50–120° gripper range.

**State / operational**
- Service/daemon crash mid-pick → define safe-state-on-failure (hold energized or
  controlled lift). Redeploy resets daemon position → re-home. Someone moves the
  mat/pen mid-sequence; immovable objects in the ROI. E-STOP during descent +
  recovery. Confirm the side camera at (−813,0,33) is outside the swept volume and
  the arm doesn't self-occlude the tip at the grasp pose.
