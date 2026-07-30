# OAK-1 Lite Vision System — Tasks

## Phase 1: Hardware + SDK Setup
- [ ] Acquire OAK-1 Lite (auto-focus version)
- [ ] Install `depthai` on Pi: `pip3 install depthai opencv-python`
- [ ] Connect OAK-1 Lite to Pi via USB-C, verify detection: `python3 -c "import depthai; print(depthai.Device.getAllAvailableDevices())"`
- [ ] Run DepthAI demo to confirm camera streams RGB at 1080p
- [ ] Design and 3D print camera mount (fixed, eye-to-hand, ~300mm above desk, 45° tilt)
- [ ] Install camera mount above workspace

## Phase 2: Camera Calibration
- [ ] Print checkerboard calibration pattern (9×6, 25mm squares)
- [ ] Create `scripts/calibrate_intrinsic.py` — capture 20+ checkerboard images, compute camera matrix
- [ ] Run intrinsic calibration, verify reprojection error < 0.5px
- [ ] Create `scripts/calibrate_extrinsic.py` — eye-to-hand calibration (checkerboard at known desk positions)
- [ ] Measure desk surface Z height relative to arm base, record as `desk_z`
- [ ] Run extrinsic calibration, save to `config/camera_calibration.json`
- [ ] Create `scripts/verify_calibration.py` — place tool at known position, verify pixel→world accuracy ±10mm

## Phase 3: Model Training
- [ ] Create `scripts/capture_training_images.py` — save frames from OAK-1 Lite to disk
- [ ] Capture 100+ images of tools on desk (various positions, lighting, arrangements)
- [ ] Upload to Roboflow, annotate bounding boxes for 5-10 tool classes
- [ ] Train YOLOv8n: `yolo train model=yolov8n.pt data=data.yaml epochs=100 imgsz=416`
- [ ] Evaluate mAP@0.5 > 0.8 on validation set
- [ ] Export to OpenVINO: `yolo export model=best.pt format=openvino imgsz=416`
- [ ] Convert to Myriad X blob: `blobconverter` with 6 shaves
- [ ] Deploy blob to Pi: `models/tools_yolov8n.blob`
- [ ] Test on-device inference: detections stream from OAK at 10+ FPS

## Phase 4: Vision Pipeline
- [ ] Create `armold_controller/vision/pipeline.py` — DepthAI pipeline (camera → NN → detections)
- [ ] Create `armold_controller/vision/detector.py` — process detections, filter by confidence
- [ ] Create `armold_controller/vision/calibration.py` — load calibration, pixel_to_world transform
- [ ] Integrate with armold_controller main loop (asyncio-compatible)
- [ ] Verify: detected tool world coordinates match physical measurement ±10mm
- [ ] Add MJPEG stream output for web UI (`vision/stream.py`)

## Phase 5: Pick Planner
- [ ] Create `armold_controller/vision/pick_planner.py` — generate pick G-code sequence
- [ ] Implement pick sequence: pre-grasp → approach → grasp → lift → transport → release
- [ ] Add per-tool-class grasp parameters (clearance, grip angle, grasp Z offset)
- [ ] Integrate with existing MotionManager (IK → G-code → grblHAL)
- [ ] Add safety: never descend below desk_z, abort on timeout (30s)
- [ ] Test: successfully pick up a screwdriver from desk 5/5 times

## Phase 6: Web UI Integration
- [ ] Add Vision panel to web UI (live MJPEG feed with bbox overlays)
- [ ] Add detected tools list with [PICK] button per tool
- [ ] Add drop-off position configuration
- [ ] Add auto-pick mode toggle
- [ ] Wire pick button → WebSocket → pick_planner → motion execution
- [ ] Test full workflow: detect → click pick → arm grabs tool → drops at target

## Phase 7: Tuning + Robustness
- [ ] Test with different lighting conditions (daylight, lamp, dim)
- [ ] Test with overlapping/adjacent tools
- [ ] Test with tools at edge of workspace (near reach limit)
- [ ] Tune grasp parameters per tool type (servo angle, approach speed)
- [ ] Add retry logic: if pick fails (tool still detected after grasp), retry once
- [ ] Run 20-pick stress test (various tools, positions) — target 80%+ success rate
- [ ] Document calibration procedure and tool-adding workflow
