"""
Armold vision package — dual-camera perception for the robot arm.

Modules:
    camera_config   — Device addressing, ROI, thresholds.
    detectors       — Pure-function detection algorithms (pen, marker, tip).
    stream_server   — Shared MJPEG HTTP server infrastructure.
    overhead_stream — OAK-4 S overhead service (pen + marker detection).
    side_stream     — OAK-1 Lite side service (gripper-tip height).
    oak4s_bringup   — Hardware bring-up verification (Phase 0).
"""
