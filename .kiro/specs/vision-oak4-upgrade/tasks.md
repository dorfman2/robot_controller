# Vision Upgrade — OAK-4 S Overhead + OAK-1 Lite Side View — Tasks

## Phase 0: Hardware & Infra Bring-up
- [ ] Power the OAK-4 S from its **USB-C supply**; confirm boot (solid status light)
      and that it joins the **local network**; record its address and set a **DHCP
      reservation / mDNS / mxid** so DepthAI addressing is stable (R1, R7).
- [ ] Verify DepthAI v3 on the Pi enumerates the OAK-4 S by IP/mxid and the OAK-1
      Lite by USB mxid **at the same time** (R1).
- [ ] Design/print the **side-camera mount**; fix the OAK-1 Lite at arm-frame
      ≈(−600, 0, 15) aimed +X across the pick zone; verify it's outside the arm's
      swept volume (R3, constraints).
- [ ] Adapt the **overhead mount** for the OAK-4 S; confirm FoV covers the mat (R2).

## Phase 1: Dual-camera Plumbing (DepthAI v3)
- [ ] Refactor `oak_detect_stream.py` into two producers (overhead + side) or a
      shared module addressing each device explicitly (R1, R8).
- [ ] Extend/split the `oak-stream` systemd service so each camera has `/stream` +
      a JSON endpoint; clean restart after replug/network reconnect; one camera failing
      must not kill the other (R1, R8).
- [ ] Confirm concurrent operation and recovery (USB replug; OAK-4 S network bounce).

## Phase 2: OAK-4 S Overhead Perception
- [ ] Bring up an OAK-4 S RGB pipeline in DepthAI v3; stream at a Pi-friendly
      resolution with a configurable working ROI (like `ROI_FRAC`) (R2).
- [ ] Port the classic-CV pen detector to OAK-4 frames to get an initial
      center+angle+confidence on `/target` (JSON) + overlay stream (R2).
- [ ] Move detection **on-device** on the RVC4 (free the Pi CPU); Pi consumes
      detections, not raw frames for inference (R2, capability #1).
- [ ] Add **object orientation** output (oriented bbox or segmentation principal
      axis) — required for yaw alignment (R2, capability #2).

## Phase 3: Overhead Calibration (pixel → arm-XY) + desk-Z map
- [ ] Calibration routine: drive a grid of known arm-XY at fixed hover Z + rail;
      pair a detectable gripper feature (or placed fiducial) with overhead pixels;
      `cv2.findHomography`; persist `~/armold_handeye_overhead.json` with rail/plane
      metadata (R4).
- [ ] Validate: known arm-XY → pixel → arm-XY within **±10 mm** (success criteria).
- [ ] **Multi-point desk-Z calibration (R11, edge case C2):** touch the vertical
      clean-wrist gripper to the desk at several XY across the pick zone; record the
      commanded model-Z at contact; fit/interpolate a Z-offset(X,Y) surface; persist
      it. Single-point z≈74 is insufficient.

## Phase 4: Side Camera Perception + Calibration
- [ ] Side pipeline: detect the **gripper-tip height above desk** (px) and target
      top height when visible; expose `/gap` JSON (R3).
- [ ] Calibrate side **pixel → arm-(Z, Y)**: step the clean-wrist column to known
      heights (z=74/100/150/200) at fixed X,Y; fit px→mm; persist
      `~/armold_sideview.json` (R4). **Calibrate the scale as a function of X**
      (edge case C3 — the side view can't resolve depth; scale changes with X).
- [ ] Grasp-verification check: object present between fingers after close (R3).

## Phase 5a: Grasp-yaw kinematic study (edge case C1 / R10) — BLOCKER for orientation
- [ ] Confirmed against the RTB model: only **J0** yaws a vertical gripper cleanly
      (J4/J5 tilt); J0 also moves the arm → yaw and XY are coupled.
- [ ] Implement a **`(rail, J0, J1, J2, J3)` solver** for `(X, Y, Z, finger-yaw)`
      with J4=−90, J5=0 fixed (rail as the decoupling DOF) — pure function +
      no-mock test.
- [ ] **Map the achievable finger-yaw range vs target XY and rail travel**; produce
      a "graspable yaw window" the pick loop can query. Decide reject-vs-nudge policy
      for out-of-window pen angles (R10).

## Phase 5: Pick Orchestrator (both cameras)
- [ ] **Reachability gate (R13, edge case)**: verify target reachable with a vertical
      clean-wrist gripper at the current/commandable rail position; else reject or
      relocate the rail (+recalibrate) — no clamped/partial moves.
- [ ] Orchestrator: overhead detect (persistent/tracked) → homography XY → solve
      `(rail, J0, ...)` for XY + grasp yaw → clean-wrist hover → **side-camera-guided
      descent** to grasp height (fallback = interpolated model-Z floor) → close →
      side-view **grasp verify** → lift (R5, R6).
- [ ] **Fail-safe (R12)**: never descend on stale/lost/low-confidence detections;
      on camera/network loss, daemon crash, or E-STOP mid-pick, end in a defined
      safe state (hold or controlled lift); camera addressing survives reconnects.
- [ ] Hard **desk-Z floor** independent of the side camera; timeout + retract.
- [ ] End-to-end pen pick **≥ 8/10** on the mat (success criteria).

## Phase 6: Enhancements (after end-to-end works)
- [ ] Segmentation-based grasp point + clutter handling (capability #4).
- [ ] On-device object **tracking** / persistent IDs (capability #5).
- [ ] **Visual servoing**: live XY correction during approach using OAK-4 S + side Z
      (capability #6).
- [ ] Consider running OAK-4 S perception fully **on-device (Luxonis OS)**, Pi
      consumes results over IP (design: networking).

## Cross-cutting
- [ ] Land the daemon **`goto_joints`** command + **startup position read** so the
      pick loop stays synced (removes the `col_move`-via-Moonraker desync; tracked in
      active-context). (Dependency for a clean orchestrator.)
- [ ] python-prefs + logging-standards; ruff/black/isort/mypy clean; no-mock tests
      for all geometry math (R9).
- [ ] Deploy vision code from the repo to the Pi via the existing base64/rsync path;
      keep repo and `/home/pi` copies in sync (R8).
- [ ] Update steering (`active-context`, `tech-context`, `system-patterns`) with the
      two-camera architecture, USB-C power + network infra, and calibration files.

## Notes
- Supersedes the obsolete `oak1-vision-pick` spec (DepthAI v2 / Myriad X / grblHAL).
- OAK-4 S is monocular (no stereo depth); depth = desk plane + side-camera height.
