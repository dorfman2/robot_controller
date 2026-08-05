# Vision Upgrade — OAK-4 S Overhead + OAK-1 Lite Side View — Tasks

## Phase 0: Hardware & Infra Bring-up
- [x] Power the OAK-4 S from its **USB-C supply**; confirm boot (solid status light)
      and that it joins the **local network**; record its address and set a **DHCP
      reservation / mDNS / mxid** so DepthAI addressing is stable (R1, R7).
      (OAK-4 S at 192.168.1.138 / deviceId 4119377180.)
- [x] Verify DepthAI v3 on the Pi enumerates the OAK-4 S by IP and the OAK-1
      Lite by USB deviceId **at the same time** (R1). (Streams operator-confirmed.)
- [x] Design/print the **side-camera mount**; fix the OAK-1 Lite at arm-frame
      **≈(−813, 0, 33) mm** (measured: 32" from rail center, 1 5/16" above desk),
      aimed +X across the pick zone; verified outside the arm's swept volume
      (R3, constraints).
- [x] Adapt the **overhead mount** for the OAK-4 S; confirm FoV covers the mat (R2).

## Phase 1: Dual-camera Plumbing (DepthAI v3)
- [x] Two producers (`overhead_stream.py`, `side_stream.py`) + shared threaded
      server (`stream_server.py`, `camera_config.py`) addressing each device
      explicitly (OAK-4 S by IP, OAK-1 Lite by USB deviceId) (R1, R8).
- [x] Split into `oak-overhead.service` (:8091) + `oak-side.service` (:8092),
      each with `/stream` + JSON endpoints; `Restart=always`; independent — one
      camera failing does not kill the other (R1, R8).
- [x] Concurrent operation + recovery confirmed: streams functional together;
      operator-confirmed **unplug recovery passed for both cameras**. NOTE: the
      MJPEG browser view stutters/drops (cosmetic) — added client-side
      auto-reconnect; the machine path uses the threaded JSON endpoints, which
      are decoupled from `/stream` and unaffected.

## Phase 2: OAK-4 S Overhead Perception
- [x] OAK-4 S RGB pipeline in DepthAI v3 (`overhead_stream.py`), streaming with a
      configurable mat ROI; deployed + operator-confirmed FoV over the mat (R2).
- [x] Classic-CV pen detector (`detectors.detect_pen`) → center + angle +
      confidence on `/target` (JSON) + overlay stream. Verified on a REAL frame
      (red pen on the mat detected: center (334,131), long-axis 82°, conf 85) (R2).
- [~] Move detection **on-device** on the RVC4 (free the Pi CPU) — INFRA PROVEN:
      `on_device_detect.py` builds a DetectionNetwork that runs on-camera
      (verified with stock yolov6-nano @ ~29 FPS; the Pi receives only
      detections — `oak4_nn_test.py`). REMAINING: a custom-trained **pen** model
      (`nn_archive`) — COCO has no pen class. Until then the overhead service
      uses host-side classic-CV (R2, capability #1). See design.md "On-device
      Model (RVC4)" for the dataset→train→convert→deploy path.
- [x] **Object orientation** output — `detect_pen` now returns the true long-axis
      angle (corrected from the ambiguous `minAreaRect` angle via a version-robust
      corner-based computation `_long_axis_angle_deg`); 5 no-mock tests in
      `test_detectors.py` verify it against synthetic pens (R2, capability #2).

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
