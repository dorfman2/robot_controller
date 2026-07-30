# OAK-1 Lite Vision System — Tool Pick-and-Place Requirements

## Goal
Integrate a Luxonis OAK-1 Lite camera with Armold to detect tools on a desk and autonomously pick them up using the robot arm and gripper. The system identifies tools via on-device neural inference, estimates their 3D position relative to the arm, plans a grasp, and executes the pick.

## Hardware

| Component | Qty | Status | Notes |
|-----------|-----|--------|-------|
| OAK-1 Lite (AF) | 1 | To acquire | 13MP IMX214, Myriad X VPU, USB-C, auto-focus |
| USB-C cable (camera to Pi) | 1 | To acquire | Short cable, camera near arm base |
| Camera mount (3D printed) | 1 | To design | Fixed "eye-to-hand" mount above workspace |

## Architecture

```
OAK-1 Lite (USB-C to Pi)
    ├── On-device: YOLOv8n inference (tool detection + bounding boxes)
    └── Streams: detections + RGB frames to Pi

Raspberry Pi 4
    ├── Vision Pipeline (depthai) — receives detections from OAK
    ├── Pixel→World Transform — converts 2D bbox to 3D workspace coordinates
    ├── Pick Planner — determines approach vector, pre-grasp, grasp, lift sequence
    ├── armold_controller — sends G-code to grblHAL (existing)
    └── Web UI — live camera feed, detected tools overlay, pick button

BTT Octopus MAX EZ (grblHAL)
    └── Executes pick motion (arm joints + gripper)
```

## Camera Mounting Strategy: Eye-to-Hand (Fixed)

The OAK-1 Lite is mounted at a fixed position above the workspace (not on the arm).
This simplifies calibration — the camera-to-world transform is constant.

- **Mount position**: Above and behind the arm base, looking down at ~45° angle
- **Field of view**: Covers the desk workspace (~400mm × 400mm area)
- **Advantages**: No cable routing through joints, no vibration blur, full workspace view
- **Disadvantage**: Arm may occlude objects (mitigated by taking image before moving)

## Depth Estimation (Monocular Camera)

The OAK-1 Lite has no stereo depth. Strategies for estimating Z (height/distance):

### Primary: Known Workspace Plane
- Desk surface is a known flat plane at a fixed Z height relative to the arm base
- All tools rest on the desk → Z is constant (desk surface height)
- Only need to estimate X, Y from the camera image
- Calibration: measure desk height once, hardcode as `DESK_Z`

### Secondary: Object Size Prior
- If the detected tool has a known real-world size (e.g., screwdriver = 200mm long)
- Compare apparent size in pixels to real size → estimate distance
- Useful for tools not flat on the desk (e.g., standing upright)

### Tertiary: Multi-View (Future)
- Move arm out of the way, take image → detect tools
- Move camera or arm to a second viewpoint → triangulate
- Overkill for flat desk scenario, but available if needed

## Requirements

### R1: Object Detection (On-Device)
- Model: YOLOv8n (nano) or equivalent, converted to OpenVINO .blob format
- Classes: common desk tools (screwdriver, pliers, wrench, hex key, tape measure, pen, etc.)
- Training: fine-tune on custom dataset of YOUR tools on YOUR desk (50-100 images)
- Inference: runs entirely on OAK-1 Lite Myriad X VPU (Pi CPU free for IK/motion)
- Output: bounding boxes + class labels + confidence scores
- Frame rate: 10-15 FPS detection (sufficient for static scene)
- Minimum confidence threshold: 0.6 (configurable)

### R2: Camera Calibration
- Intrinsic calibration: use checkerboard pattern, compute camera matrix + distortion coefficients
- Extrinsic calibration (eye-to-hand): determine fixed transform from camera frame to arm base frame
- Calibration procedure:
  1. Print checkerboard, place at known positions on desk
  2. Record camera images + known world coordinates
  3. Solve PnP → compute camera-to-world homography
- Store calibration as `config/camera_calibration.json`
- Re-calibrate if camera is moved

### R3: Pixel-to-World Coordinate Transform
- Given: bounding box center (u, v) in image pixels
- Given: known desk plane Z height
- Compute: (X, Y, Z) in arm base coordinate frame
- Method: inverse projection using camera intrinsics + extrinsic transform
- Accuracy target: ±10mm (sufficient for gripper approach)

### R4: Pick Planning
- Input: tool position (X, Y, Z) + tool orientation (from bbox aspect ratio or model)
- Output: sequence of arm poses (G-code commands)
- Pick sequence:
  1. **Pre-grasp**: move above tool (Z + 50mm clearance), gripper open
  2. **Approach**: descend to grasp height (Z + tool_height/2)
  3. **Grasp**: close gripper (M280 P0 S<close_angle>)
  4. **Lift**: raise Z + 80mm
  5. **Transport**: move to drop-off position (configurable)
  6. **Release**: open gripper, retract
- Collision avoidance: basic — don't descend below desk plane
- Approach vector: vertical (straight down) for flat tools

### R5: Training Pipeline
- Dataset collection: capture images from OAK-1 Lite at desk with tools in various positions
- Annotation: use Roboflow or CVAT for bounding box labeling
- Training: YOLOv8n on local machine or Roboflow cloud
- Export: convert to OpenVINO IR → compile to .blob for Myriad X
- Iteration: retrain when new tools are added to the set

### R6: Web UI Integration
- Live camera feed in browser (MJPEG stream from Pi, or WebSocket frames)
- Overlay: bounding boxes + class labels on detected tools
- Click-to-pick: user clicks a detected tool → system plans and executes pick
- Auto-pick mode: system picks tools in priority order without user input
- Status display: current detection results, arm state, pick progress

### R7: DepthAI Pipeline (Pi-side)
- Library: `depthai` Python package
- Pipeline stages:
  1. ColorCamera (13MP, scaled to 416×416 for NN)
  2. NeuralNetwork (YOLOv8n .blob, on Myriad X)
  3. Detection output → Pi for coordinate transform
  4. Full-resolution frame → Pi for web UI stream
- Camera runs continuously; picks triggered by user or auto mode
- Myriad X handles all NN compute (Pi CPU usage: minimal)

### R8: Safety
- Never descend below desk plane height (hard-coded Z limit)
- If detection confidence < threshold, skip (don't guess)
- Arm must be clear of workspace before taking detection image
- E-STOP still works during pick sequence (grblHAL `!`)
- Timeout: if pick sequence takes > 30s, abort and retract

### R9: Dependencies
- `depthai` (Luxonis SDK, Python)
- `opencv-python` (image processing, calibration)
- `numpy` (coordinate transforms)
- `ultralytics` (YOLOv8 training, only on dev machine — not on Pi)
- `blobconverter` (convert ONNX/IR to .blob for Myriad X)
- Existing: `armold_controller`, `ikpy`, `websockets`

## Success Criteria
- Detects at least 5 different tool types on desk with >80% accuracy
- Picks up a flat tool (screwdriver, hex key) from desk surface successfully 8/10 times
- End-to-end latency: detection → pick start < 2 seconds
- No false picks (confidence threshold prevents grabbing wrong object)
- Camera feed visible in web UI with overlaid detections
- System works with desk lighting variations (daytime, lamp, overhead)

## Constraints
- OAK-1 Lite is monocular — no native depth map
- Workspace is a known flat desk surface (simplifies depth problem)
- Tools must be reachable by arm (within 475mm reach envelope)
- Camera must have clear line of sight to desk (arm retracts before imaging)
- Pi 4 has limited USB bandwidth — camera + BTT board share USB bus
