# Dual Board 6-DOF Control — Requirements

## Goal
Control all 6 joints of the Armold robot arm using two stepper controller boards connected to the Raspberry Pi.

## Hardware
- **Board 1**: Einsy RAMBo 1.1a
  - 4x TMC2130 (SPI), ATmega2560
  - Joints 0-3 (Base, Shoulder, Elbow, Wrist Pitch)
  - Full SPI control: current, microstepping, StallGuard, mode switching
- **Board 2**: RAMPS 1.4 + Arduino Mega 2560
  - Removable drivers (TMC2208 or TMC2209 recommended)
  - Joints 4-5 (Wrist Roll, Wrist Yaw)
  - STEP/DIR/EN interface (UART optional with TMC2208)
- **Discarded**: Creality 1284P board (downgrade from RAMPS, soldered A4988s, kept as spare)

## Requirements

### R1: Einsy Firmware (Board 1 — Joints 0-3)
- Already validated and working
- 4-axis coordinated G command
- TMC2130 SPI: 1200mA, 16µstep+interp, SpreadCycle
- Trapezoidal speed ramp: 300-step accel/decel, 600µs start, 30µs cruise
- Sensorless homing via StallGuard (DIAG pins)

### R2: RAMPS Firmware (Board 2 — Joints 4-5)
- Armold protocol (same as Einsy: E, M, G, S, R commands)
- 2-axis coordinated G command (joints indexed as 0 and 1 locally, mapped to 4-5 globally)
- Same speed ramp profile as Einsy
- TMC2208/2209 drivers in X and Y slots
- Only X and Y motor outputs used (Z and E unused)

### R3: Raspberry Pi Dual Serial
- Pi connects to both boards via USB serial
- udev rules for persistent naming:
  - `/dev/armold_einsy` (Board 1, ATmega32U2 USB)
  - `/dev/armold_ramps` (Board 2, FTDI/CH340 USB)
- Both connections at 115200 baud

### R4: ROS 2 Bridge (Dual Board)
- Single bridge node manages both serial connections
- Accepts `/stepper_goal` with 6 joint positions [j0, j1, j2, j3, j4, j5]
- Splits command:
  - Joints 0-3 → G command to Einsy
  - Joints 4-5 → G command to RAMPS
- Sends both G commands in parallel (threaded) for simultaneous motion
- Publishes `/stepper_state` with all 6 positions
- `/enable_motors` enables/disables both boards

### R5: Coordinated Motion
- Both boards execute their moves simultaneously
- Trapezoidal ramp on both ensures smooth start/stop
- Bridge calculates appropriate timeout per board based on max delta

### R6: Web UI (6-DOF)
- 6 joint panels with jog controls and degree display
- IK demo updated for 6-joint coordinated motion
- E-STOP disables both boards
- Joint limits: J0=±360°, J1-J5=±100° (adjustable after mechanical testing)
- Calibration: 20,757 steps/revolution on all joints (same cycloidal drives)

### R7: Speed Settings (Both Boards)
| Setting | Value |
|---------|-------|
| Current | 1200mA RMS |
| Microsteps | 16 + interpolation to 256 |
| Mode | SpreadCycle |
| Supply | 24V DC |
| Cruise delay | 30µs |
| Accel/Decel | 300 steps |
| Start delay | 600µs |

## Constraints
- Einsy: ATmega2560, TMC2130 SPI, 4 axes max
- RAMPS: ATmega2560, removable drivers, 5 axes available (using 2)
- 20:1 cycloidal drives on all joints
- 24V DC shared power supply (10A)
- Both boards use same serial protocol for code reuse

## Architecture

```
Mac (Web UI) → WebSocket → Pi (ROS 2 Jazzy)
                              ├── armold_bridge node
                              │     ├── /dev/armold_einsy → Einsy (J0-J3)
                              │     └── /dev/armold_ramps → RAMPS (J4-J5)
                              └── rosbridge_server (port 9090)
```
