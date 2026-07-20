# Stable Motion Control Bridge — Requirements

## Problem Statement
The current ROS 2 bridge architecture is unreliable due to fundamental design conflicts:
- ROS 2 single-threaded executor blocks on serial I/O (5-10s moves)
- DDS type caching causes stale connections after crashes
- rosbridge adds a fragile intermediary layer
- Position state desyncs between bridge and firmware on restarts
- E-STOP cannot interrupt a blocking serial call
- Multiple service dependencies create cascading failure modes

## Goal
Replace the current 3-service stack (armold-bridge + rosbridge + watchdog) with a single, self-contained motion controller daemon that is inherently stable and responsive.

## Architecture Decision: Custom Daemon (No ROS 2 in the data path)

### Rationale
- ROS 2 is designed for distributed multi-node systems, not a single Pi talking serial to one board
- rosbridge adds 120MB of memory overhead for WebSocket routing we can do in 50 lines
- DDS discovery/type negotiation causes the majority of our crash recovery issues
- PAROL6 (similar robot arm) uses direct serial + command queue + WebSocket — no ROS

### New Architecture
```
Web UI (browser) ←→ WebSocket ←→ armold_controller (single daemon on Pi)
                                         │
                                    Serial Thread
                                         │
                              ┌──────────┴──────────┐
                        /dev/armold_einsy      /dev/armold_ramps
                         (Joints 0-3)           (Joints 4-5)
```

One process. One WebSocket. One serial thread per board. No ROS in the motion path.

## Requirements

### R1: Single Process Daemon
- One Python process (`armold_controller`) handles everything
- Starts on boot via systemd (single service file)
- No dependency on ROS 2, rosbridge, or DDS
- Graceful shutdown on SIGTERM/SIGINT
- Auto-reconnects serial on USB disconnect/reconnect

### R2: Dedicated Serial Thread (per board)
- Each board gets its own thread with exclusive serial port access
- Commands are submitted to a thread-safe queue
- Responses are paired with their originating request via sequence numbers
- Serial thread NEVER blocks the main event loop or WebSocket
- Timeout per command = estimated move duration + margin

### R3: Command Queue with Acknowledgment
- All commands (enable, move, state query) go through a FIFO queue
- Each command gets a unique sequence ID
- Bridge tracks: submitted → sent → acknowledged (OK) or failed
- E-STOP bypasses the queue entirely (direct serial write, interrupts any pending)
- Queue can be cleared without affecting in-flight commands

### R4: Immediate E-STOP
- E-STOP writes `E0\n` directly to the serial port (no queue, no lock wait)
- Clears the command queue
- Firmware disables motors immediately regardless of mid-move state
- Response time: <50ms from button press to motor disable
- Works even if a move is in progress (serial is full-duplex at the OS level)

### R4b: Sensorless E-STOP (StallGuard Collision Detection)
- TMC2130 StallGuard monitors motor load during cruise phase of moves
- DIAG pin HIGH triggers immediate motor halt in firmware (no serial round-trip)
- Firmware sends `STALL <joint>` notification to daemon
- Daemon clears queue, disables motors, broadcasts stall event to all clients
- False triggers suppressed: only active during cruise phase (not accel/decel)
- Sensitivity configurable per joint (sgt register, default=4)
- Requires SpreadCycle mode (StallGuard unreliable in StealthChop)
- User must manually re-enable after stall (no auto-recovery)
- Future: same hardware used for sensorless homing (separate feature)

### R5: Built-in WebSocket Server
- Native WebSocket server (aiohttp or websockets library)
- JSON message protocol (simple, debuggable, no ROS type system)
- Supports multiple simultaneous clients
- Auto-reconnects on client disconnect without affecting motor state
- Port 9090 (same as rosbridge was, web UI unchanged in URL)

### R6: JSON Protocol
```json
// Client → Server
{"cmd": "enable"}
{"cmd": "disable"}
{"cmd": "move", "target": [j0, j1, j2, j3, j4, j5]}
{"cmd": "jog", "joint": 0, "delta": 20757}
{"cmd": "home", "joint": 1}
{"cmd": "set_speed", "delay_us": 30}
{"cmd": "set_home"}
{"cmd": "go_home"}
{"cmd": "estop"}
{"cmd": "get_state"}

// Server → Client
{"type": "state", "enabled": true, "position": [0, 0, 0, 0, 0, 0], "speed": 30}
{"type": "ack", "id": 5, "status": "ok", "position": [20757, 0, 0, 0, 0, 0]}
{"type": "ack", "id": 5, "status": "error", "message": "serial timeout"}
{"type": "queue", "pending": 3, "moving": true}
{"type": "estop", "message": "motors disabled"}
```

### R7: Position State Management
- Position is authoritative from firmware responses (not estimated)
- On connect/reconnect, sync position from firmware `S` command
- State broadcast to all WebSocket clients at 2-5Hz (configurable)
- No optimistic updates that can desync — server is the single source of truth

### R8: Move Coordination
- Multi-joint moves use the firmware's `G` command (already coordinated)
- Jog commands calculate absolute target from current position + delta
- Dual-board moves dispatched to both serial threads simultaneously
- Move completion detected by serial response (not time estimation)

### R9: Speed Profiles
- Server maintains current speed setting (delay_us)
- Speed changes take effect on next move (not mid-move)
- Predefined profiles: slow (200µs), medium (80µs), max (30µs)
- Custom delay_us supported (clamped to firmware min/max)

### R10: Resilience
- Serial disconnect: mark board as disconnected, reject moves, attempt reconnect every 2s
- Serial timeout: mark command as failed, notify client, continue queue
- Client disconnect: no effect on motor state (motors stay enabled/moving)
- Process crash: systemd restarts, position synced from firmware on reconnect
- No state that can't be recovered from the firmware itself

### R11: Observability
- Structured logging (JSON to stdout, captured by journald)
- Log levels: ERROR (action required), WARN (recoverable), INFO (state changes), DEBUG (serial traffic)
- Metrics endpoint: uptime, commands processed, errors, queue depth
- Health check endpoint for external monitoring

### R12: Web UI Compatibility
- Web UI only needs to change the message format (roslib → native WebSocket JSON)
- Same URL (ws://armold.local:9090)
- Same functional behavior (jog, demo, e-stop, queue display)
- Position updates arrive as server broadcasts (not polling from client)

## Constraints
- Python 3.12 (already on Pi)
- Dependencies: `pyserial`, `websockets` (or `aiohttp`) — no ROS 2 packages
- Must handle Int32 position values (up to ±2B steps)
- Firmware protocol unchanged (E, M, G, S, R commands)
- 24V power, 115200 baud serial, same Einsy + RAMPS hardware

## Migration Path
1. Build and test `armold_controller` alongside existing bridge
2. Update web UI to use JSON WebSocket protocol
3. Disable old services (armold-bridge, armold-rosbridge, armold-watchdog)
4. Enable new single service
5. Remove ROS 2 bridge code (keep ROS 2 installed for future MoveIt integration)

## Success Criteria
- Zero crashes over 1 hour of continuous IK demo cycling
- E-STOP response < 100ms under all conditions
- No position desync after 100+ moves
- Survives USB unplug/replug without manual intervention
- Single `sudo systemctl restart armold` recovers from any state
