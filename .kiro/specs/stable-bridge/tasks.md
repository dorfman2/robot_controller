# Stable Motion Control Bridge — Tasks

## Phase 1: Core Daemon
- [x] Create `armold_controller/` package structure
- [x] Implement SerialBoard class (thread-safe serial with command queue + ACK)
- [x] Implement accumulation buffer for partial serial reads
- [x] Implement CommandQueue with sequence IDs and status tracking
- [x] Implement E-STOP bypass (direct write, queue clear, flag)
- [x] Implement position sync on connect/reconnect
- [x] Implement auto-reconnect on serial disconnect (flush queue, notify)
- [x] Implement firmware reset detection (READY banner monitoring)
- [x] Implement jog stacking with pending_target (virtual position)
- [x] Unit test: queue ordering, ACK pairing, E-STOP interrupt, jog stacking

## Phase 2: WebSocket Server
- [x] Implement asyncio WebSocket server (port 9090)
- [x] Define JSON message protocol (cmd/ack/state/queue messages)
- [x] Implement state broadcast (2Hz to all connected clients)
- [x] Implement multi-client support (connect/disconnect doesn't affect state)
- [x] Handle malformed messages gracefully (log + ignore)

## Phase 3: Motion Logic
- [x] Implement move command (absolute target, dispatched to correct board)
- [x] Implement jog command (delta from pending_target, not current position)
- [x] Implement dual-board parallel dispatch with partial failure handling
- [x] Implement speed profiles (slow/medium/max)
- [x] Implement set_home (reset firmware counters)
- [x] Implement go_home (move to 0,0,0,0,0,0)
- [x] Implement StallGuard collision detection (parse STALL response, broadcast, halt)
- [x] Handle queue-during-disconnect (immediate flush + client notification)

## Phase 4: Systemd Service
- [x] Create armold.service (single service, replaces 3 old services)
- [x] Configure: auto-restart, after=network.target, WorkingDirectory
- [x] Add structured logging (JSON stdout → journald)
- [x] Add health check (simple HTTP or file-based)

## Phase 5: Web UI Update
- [x] Replace roslib.js with native WebSocket
- [x] Implement JSON message send/receive
- [x] Position updates from server broadcast (no polling)
- [x] Queue status from server broadcast
- [x] E-STOP sends JSON directly (no ROS topic)
- [x] Verify: jog, demo, speed toggle, enable/disable, e-stop

## Phase 6: Deploy & Validate
- [x] Deploy to Pi, disable old services
- [ ] Run 1-hour IK demo stress test
- [ ] Test E-STOP mid-move (must respond <100ms)
- [ ] Test StallGuard collision detection (physically stall a motor)
- [ ] Test USB unplug/replug recovery
- [ ] Test multiple browser clients simultaneously
- [ ] Test jog stacking (rapid clicks queue correctly)
- [ ] Test firmware reset recovery (unplug/replug Einsy USB)
- [ ] Commit and update memory

## Cleanup
- [x] Remove armold-bridge.service, armold-rosbridge.service, armold-watchdog.service
- [x] Archive old ros2_bridge/ code (keep for reference)
- [x] Update steering files with new architecture
