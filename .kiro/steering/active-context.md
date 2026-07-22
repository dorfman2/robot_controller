---
inclusion: always
---

# Active Context - Current Task State

## Current Focus
BTT grblHAL + IK spec fully reviewed and finalized. All inconsistencies fixed, simulator integration phase added. Ready for hardware procurement. Current Einsy system still running on Pi for day-to-day use.

## Recent Changes
- Reviewed and finalized `.kiro/specs/btt-grblhal-ik/` (requirements.md, design.md, tasks.md)
- Fixed joint limits to match FK simulator DIMS (±180/90/150/120/90/180)
- Fixed GRBL soft limits — clarified full-range vs half-range ($130=360 for ±180°)
- Corrected URDF to proper Z-up convention (Z-axis base yaw, Y-axis pitch joints, Z offsets for vertical links)
- Fixed ikpy code: active_links_mask documented (8 elements for 6 joints), seed uses home pose, limits corrected
- Fixed GrblBoard: removed `reset_input_buffer`, unlocked estop, added startup drain
- Corrected grblHAL WebBuilder URL to `https://svn.io-engineering.com:8443/`
- Added udev rule example for `/dev/armold_motion` persistent naming
- Added home pose `[0, -30, 70, 50, 0, 0]` as machine zero reference (from FK simulator)
- Added Phase 8: Simulator Integration (5 sub-phases: FK validation, calibration, sequence→G-code, live bridge, production deploy)
- Cloned and analyzed `Armold_FK_v1` FK simulator (LeeWhite187/Armold_FK_v1)

## Upcoming Changes
- Order BTT Octopus MAX EZ + 7× EZ5160 drivers (~$145-165 total)
- Measure physical link lengths → compute SCALE factor for URDF
- Validate FK between ikpy URDF and simulator at home pose
- Phase 1-8 of BTT spec (blocked on hardware arrival)
- Current Einsy system stays running in parallel (Option C)

## Active Decisions and Considerations
- Project name: "Armold"
- Software name: "Sweep Sync"
- **Next-gen architecture**: BTT Octopus MAX EZ + grblHAL + ikpy (spec complete)
- **Current architecture**: Einsy + custom firmware + armold_controller (still running)
- BTT EZ5160 chosen over EZ2209 (4.7A vs 2.0A, SPI, StallGuard4)
- grblHAL chosen over custom firmware (eliminates serial race conditions)
- ikpy chosen over Pinocchio (simpler, pure Python, adequate speed)
- FK simulator (Armold_FK_v1) will become planning UI + digital twin
- Simulator DIMS define arm geometry (proportional units, need SCALE from physical measurement)
- Home pose: `[0°, -30°, 70°, 50°, 0°, 0°]` (simulator default = machine zero)
- URDF uses Z-up convention (remapped from simulator Three.js Y-up)
- grblHAL: 6 axes XYZABC mapped to J0-J5, standard G-code protocol
- Pi: armold.local (192.168.1.136), WebSocket 9090, Python 3.12
- Deploy (future): `rsync -az armold_controller/ pi@armold.local:~/armold_firmware/armold_controller/`
