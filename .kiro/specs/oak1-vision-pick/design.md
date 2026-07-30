# OAK-1 Lite Vision System — Design

#[[file:requirements.md]]

## System Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    DETECTION PHASE                           │
│                                                             │
│  OAK-1 Lite                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────┐    │
│  │ IMX214   │───▶│ YOLOv8n blob │───▶│ Detections     │    │
│  │ 13MP RGB │    │ (Myriad X)   │    │ (bbox, class)  │    │
│  └──────────┘    └──────────────┘    └───────┬────────┘    │
│                                              │              │
└──────────────────────────────────────────────┼──────────────┘
                                               │ USB
                                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    PLANNING PHASE (Pi)                       │
│                                                             │
│  ┌────────────────┐    ┌──────────────┐    ┌────────────┐  │
│  │ Pixel→World    │───▶│ Pick Planner │───▶│ G-code     │  │
│  │ Transform      │    │ (sequence)   │    │ Generator  │  │
│  └────────────────┘    └──────────────┘    └─────┬──────┘  │
│                                                  │          │
└──────────────────────────────────────────────────┼──────────┘
                                                   │ USB Serial
                                                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    EXECUTION PHASE                           │
│                                                             │
│  BTT Octopus MAX EZ (grblHAL)                              │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────┐    │
│  │ G-code   │───▶│ Motion       │───▶│ Pick + Grip    │    │
│  │ Receiver │    │ (7-axis)     │    │ (M280 servo)   │    │
│  └──────────┘    └──────────────┘    └────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Camera Mount Design

```
Side view:

          ┌──────┐  OAK-1 Lite
          │ cam  │  (looking down at ~45°)
          └──┬───┘
             │  mount arm (3D printed)
             │  ~300mm above desk
             │
    ─────────┼─────────────── desk surface ────────
             │
         ┌───┴───┐
         │ arm   │  robot arm base
         │ base  │
         └───────┘
```

- Camera mounted ~300mm above desk, ~200mm behind arm base
- 45° downward tilt covers ~400×400mm workspace area
- Fixed mount — never moves (eye-to-hand configuration)
- Auto-focus set to desk distance (~400mm focal distance)

---

## DepthAI Pipeline

```python
import depthai as dai
import numpy as np

def create_pipeline(model_path: str, confidence: float = 0.6):
    """Create OAK-1 Lite detection pipeline.
    
    All NN inference runs on Myriad X VPU — Pi CPU is free.
    """
    pipeline = dai.Pipeline()

    # Color camera (source)
    cam = pipeline.create(dai.node.ColorCamera)
    cam.setPreviewSize(416, 416)  # YOLOv8 input size
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam.setInterleaved(False)
    cam.setFps(15)

    # Neural network (YOLOv8n on Myriad X)
    nn = pipeline.create(dai.node.YoloDetectionNetwork)
    nn.setBlobPath(model_path)
    nn.setConfidenceThreshold(confidence)
    nn.setNumClasses(10)  # number of tool classes
    nn.setCoordinateSize(4)
    nn.setAnchors([])  # YOLOv8 is anchor-free
    nn.setAnchorMasks({})
    nn.setIouThreshold(0.5)
    nn.input.setBlocking(False)
    nn.input.setQueueSize(1)

    # Link camera → NN
    cam.preview.link(nn.input)

    # Outputs to host (Pi)
    xout_nn = pipeline.create(dai.node.XLinkOut)
    xout_nn.setStreamName("detections")
    nn.out.link(xout_nn.input)

    # Full-res frame for web UI
    xout_rgb = pipeline.create(dai.node.XLinkOut)
    xout_rgb.setStreamName("rgb")
    cam.video.link(xout_rgb.input)

    return pipeline
```

---

## Coordinate Transform: Pixel → World

### Calibration Data Structure

```python
@dataclass
class CameraCalibration:
    """Stores camera intrinsic + extrinsic calibration."""
    # Intrinsic (from checkerboard calibration)
    camera_matrix: np.ndarray   # 3×3 (fx, fy, cx, cy)
    dist_coeffs: np.ndarray     # distortion coefficients

    # Extrinsic: camera frame → arm base frame
    # Computed via eye-to-hand calibration (PnP with known points)
    R: np.ndarray               # 3×3 rotation matrix
    t: np.ndarray               # 3×1 translation vector

    # Workspace plane height (arm base frame Z coordinate of desk)
    desk_z: float               # meters, e.g. -0.05 (5cm below arm base)
```

### Pixel to World Conversion

```python
def pixel_to_world(u: float, v: float, calib: CameraCalibration) -> tuple[float, float, float]:
    """Convert pixel coordinates to arm-base-frame world coordinates.
    
    Assumes object is on the desk plane (known Z = calib.desk_z).
    Uses ray-plane intersection.
    
    Args:
        u, v: pixel coordinates (center of bounding box)
        calib: camera calibration data
        
    Returns:
        (x, y, z) in arm base frame (meters)
    """
    # Undistort pixel
    pts = np.array([[[u, v]]], dtype=np.float32)
    pts_undist = cv2.undistortPoints(pts, calib.camera_matrix, calib.dist_coeffs)
    
    # Normalized camera coordinates
    x_norm = pts_undist[0, 0, 0]
    y_norm = pts_undist[0, 0, 1]
    
    # Ray direction in camera frame
    ray_cam = np.array([x_norm, y_norm, 1.0])
    
    # Transform ray to world frame
    ray_world = calib.R.T @ ray_cam
    cam_origin_world = -calib.R.T @ calib.t.flatten()
    
    # Intersect ray with desk plane (z = desk_z)
    # cam_origin + t * ray_direction = point where z = desk_z
    t_param = (calib.desk_z - cam_origin_world[2]) / ray_world[2]
    
    world_point = cam_origin_world + t_param * ray_world
    
    return float(world_point[0]), float(world_point[1]), float(calib.desk_z)
```

---

## Pick Planner

```python
from dataclasses import dataclass

@dataclass
class ToolDetection:
    class_name: str
    confidence: float
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2 pixels
    world_pos: tuple[float, float, float]  # x, y, z in arm frame (meters)
    angle: float  # estimated orientation from bbox aspect ratio (degrees)

# Grasp approach parameters (tunable per tool type)
GRASP_PARAMS = {
    "screwdriver": {"clearance_mm": 50, "grasp_z_offset_mm": 8, "grip_angle": 60},
    "hex_key":     {"clearance_mm": 40, "grasp_z_offset_mm": 5, "grip_angle": 70},
    "pliers":      {"clearance_mm": 60, "grasp_z_offset_mm": 15, "grip_angle": 45},
    "wrench":      {"clearance_mm": 50, "grasp_z_offset_mm": 10, "grip_angle": 55},
    "pen":         {"clearance_mm": 40, "grasp_z_offset_mm": 5, "grip_angle": 75},
    "default":     {"clearance_mm": 50, "grasp_z_offset_mm": 10, "grip_angle": 60},
}

def plan_pick(detection: ToolDetection, drop_pos: tuple[float, float, float]) -> list[str]:
    """Generate G-code sequence to pick up a detected tool.
    
    Returns list of G-code commands for the full pick-and-place sequence.
    """
    params = GRASP_PARAMS.get(detection.class_name, GRASP_PARAMS["default"])
    
    x, y, z = detection.world_pos
    clearance = params["clearance_mm"]
    grasp_offset = params["grasp_z_offset_mm"]
    grip_angle = params["grip_angle"]
    
    # Convert world XY (meters) to arm joint angles via IK
    # Note: z in arm frame is the desk surface; approach from above
    pre_grasp_z = z + clearance / 1000.0  # meters above desk
    grasp_z = z + grasp_offset / 1000.0   # actual grasp height
    lift_z = z + 0.08                     # 80mm lift
    
    # IK for each waypoint
    pre_grasp_joints = inverse_kinematics(x, y, pre_grasp_z)
    grasp_joints = inverse_kinematics(x, y, grasp_z)
    lift_joints = inverse_kinematics(x, y, lift_z)
    drop_joints = inverse_kinematics(*drop_pos)
    
    if any(j is None for j in [pre_grasp_joints, grasp_joints, lift_joints, drop_joints]):
        return []  # Unreachable — abort
    
    gcode = []
    
    # 1. Open gripper
    gcode.append("M280 P0 S180")  # full open
    
    # 2. Move to pre-grasp (above tool)
    gcode.append(joints_to_gcode(pre_grasp_joints, feedrate=1200))
    
    # 3. Descend to grasp height
    gcode.append(joints_to_gcode(grasp_joints, feedrate=600))
    
    # 4. Close gripper
    gcode.append(f"M280 P0 S{grip_angle}")
    gcode.append("G4 P0.5")  # dwell 500ms for servo
    
    # 5. Lift
    gcode.append(joints_to_gcode(lift_joints, feedrate=800))
    
    # 6. Move to drop position
    gcode.append(joints_to_gcode(drop_joints, feedrate=1200))
    
    # 7. Release
    gcode.append("M280 P0 S180")  # open
    gcode.append("G4 P0.3")
    
    return gcode
```

---

## Model Training Pipeline

### Dataset Collection
```bash
# Capture images from OAK-1 Lite
python3 scripts/capture_training_images.py --output dataset/raw/ --count 100

# Images saved as 1080p JPEGs with various tool arrangements
```

### Annotation
- Upload to [Roboflow](https://roboflow.com) or use CVAT locally
- Label bounding boxes for each tool class
- Export in YOLOv8 format (txt files with normalized coordinates)

### Training
```bash
# On dev machine (Mac with GPU, or cloud)
pip install ultralytics

# Train YOLOv8 nano
yolo train model=yolov8n.pt data=dataset/data.yaml epochs=100 imgsz=416 batch=16

# Export to OpenVINO IR
yolo export model=runs/detect/train/weights/best.pt format=openvino imgsz=416
```

### Convert to Myriad X Blob
```bash
# Use blobconverter (Luxonis tool)
pip install blobconverter

python3 -c "
import blobconverter
blob_path = blobconverter.from_openvino(
    xml='runs/detect/train/weights/best_openvino_model/best.xml',
    bin='runs/detect/train/weights/best_openvino_model/best.bin',
    shaves=6,  # Myriad X compute shaves (6 for OAK-1 Lite)
    output_dir='models/'
)
print(f'Blob saved to: {blob_path}')
"
```

### Deploy to Pi
```bash
scp models/best.blob pi@armold.local:~/armold_firmware/models/tools_yolov8n.blob
```

---

## Calibration Procedure

### Step 1: Intrinsic Calibration
```bash
# Print a checkerboard (9×6 inner corners, 25mm squares)
# Take 20+ images from different angles with OAK-1 Lite

python3 scripts/calibrate_intrinsic.py \
    --images calibration/intrinsic/ \
    --pattern 9x6 \
    --square_size 25 \
    --output config/camera_calibration.json
```

### Step 2: Eye-to-Hand Extrinsic Calibration
```bash
# Place checkerboard at known positions on desk
# For each position:
#   1. Record the camera image (detects checkerboard corners)
#   2. Record the known world coordinates of the pattern
# Solve for camera-to-arm-base transform

python3 scripts/calibrate_extrinsic.py \
    --images calibration/extrinsic/ \
    --intrinsics config/camera_calibration.json \
    --desk_height -0.05 \
    --output config/camera_calibration.json
```

### Step 3: Verify Calibration
```bash
# Place a tool at a known measured position
# Run detection → check if reported world position matches measured position
# Acceptable error: ±10mm

python3 scripts/verify_calibration.py --target-x 0.2 --target-y 0.1
```

---

## Web UI Integration

### New Panel: Vision
```
┌──────────────────────────────────────────────────────────┐
│  Vision                                    [Auto-Pick: OFF] │
├──────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐ │
│  │                                                     │ │
│  │         Live camera feed (MJPEG)                    │ │
│  │         + bounding box overlays                     │ │
│  │         + class labels + confidence                 │ │
│  │                                                     │ │
│  │    [screwdriver 92%]  ┌────┐                       │ │
│  │                       │    │ [hex key 87%]         │ │
│  │    ┌──────────┐       └────┘                       │ │
│  │    └──────────┘                                     │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  Detected Tools:                                         │
│  • screwdriver (92%) — X: 210mm Y: 85mm    [PICK]       │
│  • hex key (87%)     — X: 140mm Y: -50mm   [PICK]       │
│                                                          │
│  Drop-off: [X: 0] [Y: 200] [Z: 50]  [Set Current]     │
└──────────────────────────────────────────────────────────┘
```

---

## File Structure

```
armold_controller/
├── vision/
│   ├── __init__.py
│   ├── pipeline.py          # DepthAI pipeline setup
│   ├── detector.py          # Detection processing + NMS
│   ├── calibration.py       # Camera calibration data + transforms
│   ├── pick_planner.py      # Pick sequence generation
│   └── stream.py            # MJPEG stream server for web UI
├── models/
│   └── tools_yolov8n.blob   # Compiled model for Myriad X
├── config/
│   └── camera_calibration.json
└── scripts/
    ├── capture_training_images.py
    ├── calibrate_intrinsic.py
    ├── calibrate_extrinsic.py
    └── verify_calibration.py
```
