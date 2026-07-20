# Stable Motion Control Bridge — Design

#[[file:requirements.md]]

## Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   armold_controller                       │
│                   (single Python process)                 │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │  WebSocket   │    │   Motion     │    │  State    │ │
│  │   Server     │◄──►│   Manager    │◄──►│  Store    │ │
│  │  (asyncio)   │    │              │    │           │ │
│  └──────────────┘    └──────┬───────┘    └───────────┘ │
│                              │                           │
│                     ┌────────┴────────┐                  │
│                     │  Command Queue  │                  │
│                     └────────┬────────┘                  │
│                              │                           │
│               ┌──────────────┴──────────────┐            │
│               │                             │            │
│  ┌────────────▼────────────┐  ┌─────────────▼─────────┐ │
│  │   SerialBoard (Einsy)   │  │  SerialBoard (RAMPS)  │ │
│  │   Thread + Queue        │  │  Thread + Queue       │ │
│  │   /dev/armold_einsy     │  │  /dev/armold_ramps    │ │
│  └─────────────────────────┘  └───────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## SerialBoard Class

Runs in its own thread. Only this thread touches the serial port. See `_execute()` for the unified halt detection that handles both user E-STOP and StallGuard collisions in one code path.

Key state fields:
- `_position`: actual firmware-confirmed position
- `_pending_target`: virtual position for jog stacking
- `_estop_requested`: flag checked between every queue item
- `_position_certain`: False after timeout, disconnect, or stall
- `_read_buffer`: accumulation buffer for partial serial reads

## Command Object

Each command has:
- `id`: unique sequence number for ACK pairing
- `payload`: raw serial string (e.g., `G 20757 0 0 0 30`)
- `timeout`: max wait for response (calculated from move duration)
- `callback`: called with `(id, response, status)` on completion
- `status`: `queued` → `sent` → `ok` | `error` | `timeout` | `estop` | `stall`

## Motion Manager

Orchestrates multi-board moves and jog stacking:
- `jog(joint, delta)`: calculates target from `pending_target` (not actual position)
- `move_absolute(target)`: queues coordinated G command
- `halt(source, joint)`: unified halt handler for all stop sources

## WebSocket Protocol

All messages are JSON. No binary framing, no ROS types.

### Client → Server
| Message | Fields | Description |
|---------|--------|-------------|
| enable | — | Enable motors |
| disable | — | Disable motors |
| move | target: [6 ints] | Absolute position move |
| jog | joint: int, delta: int | Relative move (stacks on pending) |
| estop | — | Emergency stop |
| set_speed | delay_us: int | Change speed |
| set_home | — | Zero position counters |
| go_home | — | Move to [0,0,0,0,0,0] |
| get_state | — | Request immediate state |

### Server → Client (broadcast)
| Message | Fields | Description |
|---------|--------|-------------|
| state | enabled, position, pending_target, speed, connected, position_certain, queue_depth, moving | Periodic (2Hz) |
| ack | id, status, position?, message? | Command acknowledgment |
| halt | source, joint?, position, message | Unified halt notification |
| error | message | Protocol/validation error |
| reset | board, message | Firmware reset detected |
| queue_cleared | board, reason, dropped | Queue flushed on reconnect |

## State Management

### Position Truth Hierarchy
1. **Actual position**: updated ONLY from firmware responses (`OK G`, `S`, `ERR STALL`)
2. **Pending target**: updated when a move is queued (for jog stacking)
3. **No optimistic updates in the broadcast** — clients always see actual firmware-confirmed position

### State Broadcast
```json
{
    "type": "state",
    "enabled": true,
    "position": [20757, 0, 0, 0, 0, 0],
    "pending_target": [41514, 0, 0, 0, 0, 0],
    "speed": 30,
    "connected": {"einsy": true, "ramps": false},
    "position_certain": true,
    "queue_depth": 2,
    "moving": true
}
```

### Position Sync Points
- On initial serial connect (after READY banner)
- On reconnect after disconnect
- After firmware reset detection
- After `set_home` (R command response)
- NEVER during normal move operation (no polling)

---

## Unified Halt System (E-STOP + StallGuard)

All emergency stops — user-initiated or collision-detected — use one code path through the entire stack: firmware, daemon, protocol, and UI. Two trigger sources, one handler.

### Trigger Sources

| Source | Where Detected | Serial Response |
|--------|---------------|-----------------|
| User (web UI button) | Firmware receives `E0\n` mid-move | `OK E0` |
| Collision (StallGuard) | Firmware DIAG pin HIGH during cruise | `ERR STALL <joint>` |

### Firmware: Single Halt Check Block

One `if` block inside the Bresenham stepping loop handles both sources. Only runs during cruise phase (avoids false StallGuard triggers during accel/decel):

```cpp
// Inside moveCoordinated(), every 16 steps during cruise phase:
if (step > ACCEL_STEPS && step < (maxSteps - DECEL_STEPS) && step % 16 == 0) {

    // Check 1: StallGuard collision (DIAG pins)
    for (uint8_t i = 0; i < NUM_JOINTS; i++) {
        if (digitalRead(diagPins[i]) == HIGH) {
            setMotorsEnabled(false);
            Serial.print(F("ERR STALL "));
            Serial.println(i);
            return;  // Abort move
        }
    }

    // Check 2: User E-STOP (serial command)
    if (Serial.available()) {
        char c = Serial.peek();
        if (c == 'E') {
            String cmd = Serial.readStringUntil('\n');
            setMotorsEnabled(false);
            Serial.println(F("OK E0"));
            return;  // Abort move
        }
    }
}
```

**15 lines of firmware code handles both halt sources.** Both exit the same way: motors disabled, move aborted, response sent.

### StallGuard Configuration (TMC2130 SPI)

Set once during `setup()`:
```cpp
drv.TCOOLTHRS(0xFFFFF);    // Enable StallGuard at all speeds
drv.sgt(4);                 // Sensitivity (0=most sensitive, 63=least)
drv.diag1_stall(true);      // Route StallGuard result to DIAG1 pin
```

- Only reliable in SpreadCycle mode (our default)
- Only checked during cruise phase (not accel/decel where inertia causes false triggers)
- sgt=4 is the starting value — tune per joint after mechanical testing

### Daemon: Single `_handle_halt()` Method

The serial thread detects halt from the response string and calls one handler:

```python
def _execute(self, cmd):
    response = self._send_raw(cmd.payload, timeout=cmd.timeout)

    # Detect halt (both sources produce responses parsed here)
    if response and response.startswith('ERR STALL'):
        joint = int(response.split()[2])
        self._handle_halt(source='collision', joint=joint)
        cmd.complete(response, 'stall')
        return

    if response == 'OK E0' and cmd.payload.startswith('G'):
        # Move was interrupted by user E-STOP
        self._handle_halt(source='user', joint=None)
        cmd.complete(response, 'estop')
        return

    # ... normal response handling ...

def _handle_halt(self, source, joint):
    """Unified halt handler. Same logic for user and collision."""
    self._enabled = False
    if source == 'collision':
        self._position_certain = False
    # Queue is cleared by estop() which was already called (for user source)
    # or needs to be cleared now (for collision source)
    while not self._command_queue.empty():
        try:
            queued_cmd = self._command_queue.get_nowait()
            queued_cmd.complete(None, 'estop')
        except queue.Empty:
            break
```

### Motion Manager: Single Broadcast

```python
def halt(self, source, joint=None):
    """Called by serial thread on any halt. Broadcasts to all clients."""
    self._has_pending = False
    self._pending_target = list(self._position)

    JOINT_NAMES = ['Base', 'Shoulder', 'Elbow', 'Wrist Pitch', 'Wrist Roll', 'Wrist Yaw']
    if source == 'collision':
        message = f'Collision detected on Joint {joint} ({JOINT_NAMES[joint]})'
    else:
        message = 'E-STOP activated'

    self._broadcast({
        "type": "halt",
        "source": source,
        "joint": joint,
        "position": self._position,
        "message": message
    })
```

### WebSocket: One Message Type

```json
{"type": "halt", "source": "user", "joint": null, "position": [...], "message": "E-STOP activated"}
{"type": "halt", "source": "collision", "joint": 1, "position": [...], "message": "Collision detected on Joint 1 (Shoulder)"}
```

### Web UI: One Handler

```javascript
function handleHalt(msg) {
    motorsEnabled = false;
    motionQueue.length = 0;
    renderQueue();
    updateMotorButton(false);

    // Visual feedback — flash affected joint (or header for user E-STOP)
    const el = msg.joint !== null
        ? document.getElementById('joint-' + msg.joint + '-panel')
        : document.querySelector('.status-bar');
    el.classList.add('halt-flash');
    setTimeout(() => el.classList.remove('halt-flash'), 2000);

    showAlert(msg.message);
}
```

### User-Initiated E-STOP Flow (Detailed)

```
Browser click "E-STOP"
  → WebSocket: {"cmd": "estop"}
  → Motion Manager: calls board.estop() on all boards
  → board.estop():
      1. Sets _estop_requested = True (flag for serial thread)
      2. Writes E0\n directly to serial port (immediate, no queue)
      3. Clears command queue (all pending get status='estop')
  → Serial thread (on next iteration OR when readline returns):
      - Sees _estop_requested flag
      - Calls _do_estop(): writes E0\n again (redundant safety)
      - Resets flag
  → Firmware (when it processes E0\n):
      - If mid-move: caught by the serial check in stepping loop → abort + OK E0
      - If idle: immediate → OK E0
  → Motion Manager broadcasts: {"type": "halt", "source": "user", ...}
  → Total latency: <50ms for idle, <100ms for mid-move (checked every 16 steps)
```

### Collision E-STOP Flow (Detailed)

```
Motor hits physical obstacle
  → TMC2130 StallGuard detects excessive load
  → DIAG1 pin goes HIGH
  → Firmware stepping loop checks DIAG (during cruise, every 16 steps)
  → Firmware:
      1. Calls setMotorsEnabled(false) — immediate stop
      2. Sends "ERR STALL <joint>\n" over serial
      3. Returns from move function (aborts remaining steps)
  → Serial thread reads "ERR STALL 1"
  → Calls _handle_halt(source='collision', joint=1)
  → Clears queue, marks position_certain=False
  → Motion Manager broadcasts: {"type": "halt", "source": "collision", "joint": 1, ...}
  → Web UI flashes Joint 1 red, shows collision alert
  → Total latency: <2ms from stall to motor disable (firmware-level, no serial round-trip)
```

### Recovery After Any Halt

Same for both sources:
1. User inspects arm / removes obstruction
2. Clicks "Enable Motors" in web UI
3. Client sends `{"cmd": "enable"}`
4. Daemon sends `E1\n` to firmware, syncs position with `S` command
5. `position_certain` set back to True
6. Normal operation resumes

### False Trigger Prevention

StallGuard is unreliable during:
- Acceleration (inertia looks like load)
- Deceleration (back-EMF)
- StealthChop mode (use SpreadCycle)
- Direction reversals

Mitigation: **only check DIAG during cruise phase** (step > ACCEL_STEPS && step < maxSteps - DECEL_STEPS). This is built into the single check block above — zero additional code needed.

### Future: Sensorless Homing

Same DIAG pin hardware, different usage:
- Slower speed (400µs delay for reliable detection)
- Per-joint sgt sensitivity (tuned for homing load)
- Specific homing direction per joint
- Position set to 0 on stall (success, not error)
- Separate `home` command — NOT part of halt logic

Planned for a future spec after mechanical testing determines per-joint parameters.

---

## Reconnection Strategy

```
Serial disconnect detected (OSError on write/read)
    → Mark board as disconnected
    → Mark position_certain = False
    → Flush command queue (fail all pending with 'disconnect')
    → Notify clients: {"type": "queue_cleared", "board": "einsy", "reason": "disconnect", "dropped": N}
    → Start reconnect loop (every 2 seconds):
        1. Check if device file exists (/dev/armold_einsy)
        2. Attempt serial open
        3. Wait for READY banner (up to 10s)
        4. Send S command to sync position
        5. If success: mark connected, position_certain = True
        6. Notify clients via state broadcast
        7. Resume command processing
    → Commands submitted during disconnect get immediate error ACK
```

### Post-Reconnect Safety
All queued commands are flushed on disconnect (not reconnect). Client must re-submit from the new synced position.

## Firmware Reset Detection

Serial thread monitors for unexpected `READY` or `ARMOLD EINSY` in responses:
- Power glitch → AVR reset
- Watchdog timeout
- USB re-enumeration + DTR toggle

On detection: assume position [0,0,0,0], disable motors, broadcast reset, require user re-enable.

## Dual-Board Move Coordination

Both boards get G commands simultaneously via their own serial threads. If one fails:
```json
{"type": "ack", "id": 7, "status": "partial", "detail": {"einsy": "ok", "ramps": "timeout"}}
```
No rollback. Failed board marked `position_certain = false`.

## Invalid Message Handling

Per-message try/except at the WebSocket protocol level. Malformed messages from one client never affect others or motor state. Error response sent only to the offending client.

## WebSocket Keep-Alive During Long Moves

State broadcasts (2Hz) run independently of serial I/O. Queue status updates sent on every change. No silence period that could trigger browser disconnect timeout.

---

## Compared to Current Architecture

| Aspect | Current (ROS 2) | New (Custom Daemon) |
|--------|-----------------|---------------------|
| Processes | 3 (bridge + rosbridge + watchdog) | 1 |
| Memory | ~230MB | ~30MB |
| Dependencies | ROS 2, rosbridge, pyserial | pyserial, websockets |
| E-STOP latency | 100ms-10s (blocked by lock) | <50ms user, <2ms collision |
| Collision detection | None | StallGuard (firmware-level, no serial trip) |
| Halt code paths | N/A | 1 unified path (user + collision) |
| Crash recovery | cascading restarts, DDS cache | single restart, position sync |
| Position truth | estimated by UI, desyncs | firmware-authoritative, never estimated |
| Jog stacking | broken (race conditions) | virtual pending_target |
| Serial safety | single lock, blocking | dedicated thread, accumulation buffer |
| Reconnection | manual restart required | automatic, queue flushed, clients notified |
| Multi-client | rosbridge handles, fragile | native asyncio, independent |
