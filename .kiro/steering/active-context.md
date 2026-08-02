---
inclusion: always
---

# Active Context - Current Task State

## Current Focus
**OAK-1 Lite vision → pen pick (in progress, 2026-08-01). PAUSED for a break.** Approach LOCKED: DepthAI **v3** (3.8.0) + classic-CV pen detection + green gripper marker for hand-eye calibration → `move_cartesian`. Done: camera works on Pi (v3 aarch64 wheels), live MJPEG detect-stream with pen + gripper-marker overlays, `move_cartesian` VALIDATED on real hardware (position_error ~0.0006 mm), first hand-eye homography captured. **BLOCKER discovered: reachability.** Reaching down toward the desk exceeds joint limits at extended X — `move_cartesian` to (-250,0,350) returned "joint-limit clamping out of range", (-275,*) and (-300,*) unreachable. Must map the reachable low-Z region (probe closer-in X: -150/-180/-210) to confirm the arm can even reach the desk plane (z≈78 mm). Desk plane pinned: gripper center measured 19-7/16" (493.7 mm) above desk at EE z≈572 → **desk surface ≈ z=78 mm in arm frame**. First homography was at z=572 (494 mm above desk) → overfit (only 4 of 9 grid points valid) + parallax risk; recalibrate near desk once reachability is solved.

## Prior Focus (RTB Cartesian IK — DONE)
**Cartesian IK integration (RTB) — deployed and live (2026-07-31).** `armold_controller/ik_solver.py` (RTB 6-DOF arm; rail excluded), `move_cartesian` WS command + end-effector FK broadcast, web UI Cartesian panel. Real link lengths in `MEASURED_GEOMETRY`. RTB on Pi in `/home/pi/armold-venv`; `pi/armold.service` runs from that venv. DEPLOYED via `./scripts/deploy_controller.sh` — daemon live, `ArmIK initialised: 6 joints, reach ~524 mm`, and `move_cartesian` confirmed working on hardware. Tests green (ik 15, ws 4, soft-limits 8, waypoints 8).

## Older Focus
Klipper migration COMPLETE through Phase 7 validation (2026-08-01). All validated: 7 motors (individual + concurrent), gripper (60 open/120 closed), coordinated G1, E-STOP, position accuracy (90°=90°), USB recovery. Currents recalibrated to EZ5160's 0.050 sense_resistor on all 7; per-joint run/hold tuned (shoulder 1.0/1.0 to lift extended arm; elbow 0.9; J3 1.2/0.75; rest 0.8/0.3). Soft limits live in armold_controller (deployed, daemon active, WS 9090). Homing is MANUAL (StallGuard abandoned — belt skips). Final config saved to repo pi/printer.cfg. Bootloader: Katapult installed (boot only, flash-write broken EC11; updates via ROM DFU). Open follow-ups: 1-hour soak test, MCU-shutdown auto-restart watchdog, loaded elbow test / higher hold on lift joints. Next major area: OAK-1 Lite vision integration (after this stable base).

## Recent Changes
- **OAK-1 Lite vision started (2026-08-01)**: DepthAI **v3** (3.8.0) + opencv-python-headless installed into `/home/pi/armold-venv` (aarch64 wheels). udev rule `/etc/udev/rules.d/80-movidius.rules` (idVendor 03e7, MODE 0666). Camera on a USB2 bus (HIGH speed); 720p uncompressed crashes on teardown → stream at 640x360. Live MJPEG detect-stream `/home/pi/oak_detect_stream.py` run as transient unit `oak-stream` (`sudo systemd-run --unit=oak-stream --collect ...`); serves `:8091` `/` (index), `/stream` (mjpeg), `/grip` (JSON grasp pixel). Pen detector = flat-field bg subtraction + elongation filter (works for dark Sharpie on dark mat). Gripper marker = green tape, HSV (35,70,50)-(90,255,255), two-finger midpoint = grasp center. `move_cartesian` validated on hardware. First hand-eye homography saved to `/home/pi/armold_handeye.json`. Prototype scripts saved to repo `scripts/vision/`.
- **RTB Cartesian IK deployed (2026-07-31)**: `armold_controller/ik_solver.py` (ArmIK: fk/solve_ik, dataclasses ArmGeometry/CartesianTarget/EndEffectorPose/IKResult). `move_cartesian` WS command + EE FK broadcast. Web UI "Cartesian (IK)" panel. Deployed to Pi; daemon runs from `/home/pi/armold-venv`. Spec: `.kiro/specs/rtb-cartesian-ik/`.
- **Klipper migration validated through Phase 7 (2026-08-01)**: motors (individual + all-7 concurrent), gripper, coordinated G1, E-STOP, 90°=90° position accuracy, USB disconnect recovery — all confirmed.
- **Current recalibration**: found EZ5160 sense_resistor missing (Klipper 0.075 default vs 50mOhm actual → ~1.5x over-current); set `sense_resistor: 0.050` on all 7. Per-joint run/hold retuned: shoulder(z) 1.0/1.0 (needed to lift extended arm), elbow(a) 0.9/0.3, J3(b) 1.2/0.75, rest 0.8/0.3.
- **Soft limits** implemented in armold_controller/klipper_board.py (JointLimit + clamp_target, 8 tests) and **deployed** to Pi (daemon active, WS 9090). Fixed jog to be relative.
- **Homing = MANUAL** (RELEASE_RAIL → push to home end → SET_RAIL_HOME). StallGuard sensorless abandoned (belt skips before rotor stalls — no usable SGT window). Fixes kept: dir_pin !PC14, sense 0.050.
- **Katapult installed** @0x08000000 (boot/jump only — flash-write broken on this H723 build, EC11/issue #128). Klipper @0x8020000. Updates via ROM DFU. Prior "failure" was a mis-built F103 config.
- Final validated config saved to repo `pi/printer.cfg`.

## Upcoming Changes
- **RESUME HERE (vision): fix FK model + desk Z, then reachability**. NEW FACT (user, 2026-08-01): the arm **base is ~94 mm above the desk**, and the desk is physically reachable. This CONTRADICTS the model: FK said gripper z≈572 when it was measured 493.7 mm above desk (→ desk at arm-z≈+78), but base-94-above-desk → desk at arm-z≈−94. ~170 mm disagreement ⇒ **the ETS vertical geometry is wrong**, which is why `move_cartesian` reported "unreachable/joint-limit" for physically-fine targets. **Full staged plan written: `docs/hand-eye-calibration-plan.md`** (Phase 0 prep → Phase 1 desk-plane touch test [operator verifies Z at P1/P2/P3] → Phase 2 reachability map → Phase 3 hand-eye homography at hover height → Phase 4 end-to-end aim+pick [operator verifies] → Phase 5 optional model fix). Principle: don't trust model absolute Z; operator touch-measures the real desk plane, calibrate hand-eye near it. Safety: stepped slow descents (20→5 mm), E-STOP + ruler, stop on IK clamp. Awaiting operator "go" (motors on, ruler + E-STOP ready).
- **Recalibrate hand-eye near the desk plane** (not z=572) once a reachable low-Z is found — reduces parallax; collect more points over a larger valid area (first run had only 4).
- **Pick strategy**: detect pen → homography → arm XY; align gripper marker over pen at a safe hover height (both visible), then descend straight down (blind — marker/pen occluded, that's fine) → close (120°) → lift. Losing the marker during the final descent is expected/acceptable.
- **Confirm J4/J5 axis labels** on the physical arm (yaw vs roll) — only the human label is unresolved; the kinematic order (Rz then Rx) is correct either way.
- (Follow-up) Trajectory smoothing for Cartesian moves — candidate `ruckig` (jerk-limited); current goto is point-to-point per-joint (no path planning / no collision checking).
- **OAK-1 Lite vision integration** — next major area now that the motion base is stable
- (Follow-up) Motor ramping smoothness — try microsteps 16→32 (+interpolate), chopper tuning (TOFF/TBL/HEND/HSTRT), and/or lower jog/goto accel. manual_stepper is trapezoidal (no S-curve).
- (Follow-up) Gripper mechanical action not fully smooth — HARDWARE, user to address later
- (Follow-up) Watchdog to auto-issue `FIRMWARE_RESTART` on MCU shutdown (USB recovery not hands-off — needs restart, often ×2)
- (Follow-up) 1-hour continuous soak test (deferred from Phase 7)
- (Optional) Add OPEN_GRIPPER (50°)/CLOSE_GRIPPER (120°) macros to printer.cfg
- Done: hold currents raised to 1.0 on J0/J2/J3/J4/J5 for firmer holding (elbow loaded test still worthwhile)

## Active Decisions and Considerations
- Project name: "Armold"
- Software name: "Sweep Sync"
- **Klipper over grblHAL**: grblHAL Motor-7/8 pins didn't produce physical movement; Klipper works on all slots
- **7-axis architecture**: Pi (klippy + armold_controller) → BTT Octopus MAX EZ (Klipper MCU) → 7 EZ5160 → 7 motors
- **Axis mapping**: X=rail, Y=J0 Base, Z=J1 Shoulder, A=J2 Elbow, B=J3 Wrist Pitch, C=J4 Wrist Roll, U=J5 Wrist Yaw
- **Gripper**: 180° 9g metal gear servo on PA1 (FAN4), powered by separate 5V BEC. **50°=OPEN, 120°=CLOSED** (recalibrated after re-centering the servo horn; UI slider limited to 50-120). `SET_SERVO SERVO=gripper ANGLE=n`
- **Cooling fan**: `[fan_generic motor_fan]` on **PF8** (FAN5); PA1/FAN4 taken by gripper. `SET_FAN_SPEED FAN=motor_fan SPEED=0..1`. Set VF5 jumper to fan voltage.
- **Motor current (validated, all sense_resistor 0.050)**: rail(x) 0.8/0.3 · base(y) 0.8/0.3 · shoulder(z) **1.5/1.1** · elbow(a) **1.2/1.0** · J3 pitch(b) **0.5/0.3** · roll(c) **0.5/0.3** · yaw(u) **0.5/0.3** (run/hold A). Wrist joints J3-J5 dropped to 0.5/0.3 (2026-08-01, light load, reduce heat) — applied live via SET_TMC_CURRENT + persisted in printer.cfg. Shoulder/elbow higher to lift the extended arm; J1 shoulder 1.5/1.1. Rail 0.8/0.3.
- **Homing = MANUAL**: StallGuard sensorless abandoned (belt skips before rotor stalls). Rail: RELEASE_RAIL → push to home (neg) end → SET_RAIL_HOME. Arm joints: SET_ARM_HOME. StallGuard config on stepper_x left dormant (diag1_pin ^!PF0, driver_SGT 20, virtual_endstop).
- **Flash method — DECIDED**: ROM DFU is the sanctioned update workflow (BOOT0+RESET → `sudo dfu-util -a0 -s 0x08020000:leave -D ~/klipper/out/klipper.bin`). Katapult stays installed @0x08000000 as the boot/jump stage. Buttonless-via-Katapult (EC11) is NOT being pursued (flash-write broken on this build). Runbook in klipper-migration/tasks.md Phase 2.
- **SPI for TMC5160**: confirmed working in Klipper (failed in grblHAL on this board)
- **Consolidation**: Einsy + RAMPS retired, single board, single serial port
- **VID:PID**: 1d50:614e (OpenMoko/Klipper)
- **Klipper serial ID**: usb-Klipper_stm32h723xx_380009001151313531383332-if00
- **Moonraker API**: localhost:7125 for all armold_controller communication
- **GCODE_AXIS (CORRECTED)**: all 7 register fine using non-reserved letters **W A B C D H U** (stepper_x=W, y=A, z=B, a=C, b=D, c=H, u=U). Only X/Y/Z/E/F/N are reserved. Coordinated motion via `REGISTER_AXES` then `G1 A.. B.. C.. D.. H.. U..`. Don't mix rail W(mm) with degree axes in one G1 (blended F speed). firmware_restart clears the registration → re-run REGISTER_AXES.
- **Deploy key**: `~/.ssh/armold_deploy` (ed25519, no passphrase)
- **IK library = Robotics Toolbox for Python (RTB)**: chosen over ikpy (fallback, weaker redundancy), Trac-IK (heavy KDL/NLopt build), Pinocchio/Pink (overkill), pytorch_kinematics (GPU-pointless on Pi). RTB installs from aarch64 wheels on the Pi, ~1 ms/IK solve. Model built via ETS (no URDF authoring).
- **Rail architecture = separate gross-positioning axis**: the 6-DOF arm IK excludes the rail (board joint 0). Rejected rail-in-chain 7-DOF redundant IK (needs nullspace resolution).
- **IK units/frames**: arm base frame Z-up anchored at the rail carriage; mm + degrees at the module boundary; ArmIK models arm joints 0..5 = J0..J5, mapping to KlipperBoard indices 1..6 (index 0 = rail).
- **armold venv**: daemon runs from `/home/pi/armold-venv` (virtualenv --system-site-packages) so RTB is importable; PEP-668 blocks `pip install --user` on Ubuntu 24.04.
- **OAK-1 Lite**: monocular vision, eye-to-hand fixed (overhead) mount, known desk plane for depth
- **Vision SDK = DepthAI v3 (3.8.0)** (NOT v2 — v2 code in old oak1-vision-pick spec is obsolete). v3 camera API: `pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)` → `cam.requestOutput((w,h), dai.ImgFrame.Type.BGR888i, fps=..)` → `out.createOutputQueue()`; `pipeline.start()`; `q.get().getCvFrame()`. Runs in armold-venv (system-site-packages). Camera on USB2 → keep resolution modest (640x360 stream; 720p uncompressed crashes device on teardown).
- **Pen detection = classic CV** (no training): flat-field background subtraction (`absdiff(gray, big-Gaussian-blur)`) + Otsu + elongation filter in a mat ROI. Robust for dark pen on dark mat. NN/trained-YOLO is the documented fallback (v3 has DetectionNetwork/model-zoo/nn_archive).
- **Gripper marker = green tape on TOP of gripper facing camera** (finger-tip tape occludes when edge-on). HSV green (35,70,50)-(90,255,255). Detect two finger blobs → midpoint = grasp point. LIGHTING-SENSITIVE: bright lights desaturate green below the S threshold (turn bright lights off, or widen range later).
- **Hand-eye calibration = motion-based homography** (pixel→arm-XY): jog/`move_cartesian` to a grid, pair grasp-marker pixel with achieved EE (X,Y), `cv2.findHomography`. Valid only at the calibrated rail position + Z plane. Marker needed only for calibration/alignment, NOT during grasp (final descent is blind/open-loop).
- **Desk plane ≈ z=78 mm in arm base frame** (gripper center 493.7 mm above desk when EE z≈572). Grasp Z ≈ desk + a few mm.
- **REACHABILITY (open problem)**: reaching down/out toward the desk exceeds joint limits at extended X (e.g. (-250,0,350) clamps; (-275,*)/(-300,*) unreachable at z=572). Reaching the desk likely needs closer-in X and/or moving the rail. Must be resolved before a pick is possible.
