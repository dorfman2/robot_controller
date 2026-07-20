---
inclusion: always
---

# System Patterns - Technical Architecture

## Important Security Patterns
- USB serial ports on macOS use `/dev/cu.*` (non-blocking) — avoid `/dev/tty.*` for programmatic access
- Pi SSH key-only auth (password disabled after setup)
- Pi user `pi` in `dialout` group for serial port access without root

## Learnings and Project Insights
- PlatformIO `build_src_dir` is not a valid per-environment option — use `build_src_filter = -<*> +<../firmware/xxx/src/>` for multi-firmware projects
- OpenCM 9.04 lacks first-class PlatformIO board support; use `genericSTM32F103CB` or Arduino IDE with Robotis board package
- RAMPS 1.4 stepper drivers (TMC2208) are active LOW on enable pin
- Einsy RAMBo TMC2130: also active LOW enable, but controlled via SPI (no jumpers/pots needed)
- Einsy RAMBo USB shows as `/dev/cu.usbmodem1101` on macOS (ATmega32U2 chip)
- Einsy global `src_dir` in platformio.ini overrides per-env — must remove and use `build_src_filter` per env
- TMC2130 API: no `stealth()` member — use `stallguard()` for DRV_STATUS check
- TMC2130 max current with 0.22Ω sense resistors: 0.325V / 0.22 = ~1.48A RMS
- Prusa Einsy register scale: 0-63 = 0 to ~0.96A (with Prusa's LDO motors)
- SpreadCycle preferred over StealthChop for robot arms (dynamic torque > silence)
- Trapezoidal speed ramp prevents missed steps at startup and reduces resonance
- macOS serial device naming: FTDI/CP2102 adapters show as `/dev/cu.usbserial-<SERIAL_NUM>`
- PlatformIO Core 6.1.19 has no `system setup` command — use manual PATH addition
- TMC2208 bad driver diagnosis: if motor free-spins with enable asserted and 24V confirmed, swap the driver
- Ubuntu 24.04 (Noble) requires `noble-updates` in apt sources for `-dev` package dependencies to resolve
- Cloud-init only runs on first boot — editing `user-data` on an already-booted SD card has no effect
- ROS 2 Humble is for Ubuntu 22.04 only; Ubuntu 24.04 uses ROS 2 Jazzy
- Pi may get new IP after re-image — use `armold.local` (mDNS) or check ARP table
- SSH with passphrase-protected keys requires `ssh-add` before non-interactive use
- Stepper motor voltage: chopper driver limits current regardless of voltage; higher voltage = more torque at high speed (back-EMF headroom)
- 24V sufficient for NEMA 17 through 20:1 gearbox; 36-48V only needed for much higher speeds
- Calibration re-measured: 83,028 steps = 360° actual output (not 20,757 — original measurement was off by 4x)
- Int16MultiArray overflows at ±32767 steps — switched to Int32MultiArray for position values
- ROS 2 bridge fundamental issues: blocking callback thread, DDS type cache on restart, rosbridge stale connections
- New architecture: single Python daemon (asyncio + serial threads) replaces 3 ROS services
- Pi DHCP reservation: 192.168.1.136. Use armold.local (mDNS) as primary, IP as fallback
- `PartOf=` systemd directive causes rosbridge to stop when bridge stops but not restart — use `Restart=always`
- `ProtectSystem=strict` and `ReadWritePaths` in systemd cause NAMESPACE (226) errors on Pi — remove hardening directives
- Einsy RAMBo doesn't reset on USB serial open (ATmega32U2 issue) — daemon must fallback to direct `S` sync if no READY banner
- Daemon WorkingDirectory must match actual path on Pi (`/home/pi/armold_firmware` not `/home/pi/Armold`)
- StallGuard position tracking on abort: calculate from `(absDelta[j] * step / maxSteps)` to report where motor actually stopped
- set_home must reset both `_pending_target` AND `_position` on the board object (not just firmware `R` command)

## System Architecture
```
Browser (Web UI) ←── WebSocket (9090) ──→ armold_controller (Pi daemon)
                                                │
                                           Serial Threads
                                                │
                                     ┌──────────┴──────────┐
                               /dev/armold_einsy      /dev/armold_ramps
                                Einsy (J0-J3)          RAMPS (J4-J5)
```

- **Mac** (macOS, darwin/zsh): Development, PlatformIO firmware builds, direct serial testing
- **Pi 4** (Ubuntu 24.04, arm64): armold_controller daemon (asyncio + serial threads)
- **Einsy RAMBo** (ATmega2560): Motor control firmware, TMC2130 SPI, StallGuard
- **RAMPS 1.4** (ATmega2560): Secondary motor control (planned, not yet wired)

## Code Structure
- `armold_controller/` — Motion control daemon (Pi)
  - `__init__.py` — Package init, version
  - `__main__.py` — Entry point, config, signal handling, health check
  - `main.py` — Convenience entry point
  - `command.py` — Command dataclass with sequence IDs and lifecycle
  - `serial_board.py` — Per-board serial thread + command queue + ACK
  - `motion_manager.py` — Move coordination, jog stacking, halt
  - `ws_server.py` — asyncio WebSocket + JSON protocol
  - `tests/test_core.py` — Unit tests (13 tests)
- `firmware/einsy/src/main.cpp` — Einsy RAMBo firmware (TMC2130 SPI, 4-axis)
- `firmware/ramps/src/main.cpp` — RAMPS firmware (basic STEP/DIR, 3-axis)
- `web/index.html` — Control UI (native WebSocket, no roslib.js)
- `scripts/deploy.sh` — Mac → Pi firmware deploy + flash
- `scripts/deploy_controller.sh` — Mac → Pi controller deploy
- `pi/armold.service` — systemd service file (single daemon)
- `ros2_bridge/` — OLD ROS 2 bridge (archived, superseded)

## Design Patterns in Use
- Single-character serial command interface for hardware testing (minimal, no parsing overhead)
- Separate firmware per board (RAMPS vs OpenCM) compiled from same PlatformIO project
- Enable/disable safety pattern — motors start disabled, require explicit enable command
- Cloud-init for headless Pi provisioning (SSH key, hostname, user config)
- Persistent serial device naming via udev symlinks (`/dev/armold_ramps`)

## Tool Usage Patterns
- **PlatformIO CLI**: `pio run -e ramps` to build, `pio run -e ramps -t upload` to flash, `pio device monitor` for serial
- **Serial port check**: `python3 scripts/check_serial.py` to verify USB connection
- **PlatformIO path**: `export PATH="/Users/jdorfman/.platformio/penv/bin:$PATH"`
- **Pi SSH**: `ssh pi@192.168.1.138` or `ssh armold` (after config setup)
- **Pi ROS 2**: `source /opt/ros/jazzy/setup.bash` (in .bashrc on Pi)

- **`taskUpdate` EPERM workaround**: On Windows, the `taskUpdate` tool intermittently fails with `EPERM: operation not permitted, rename ... .meta.json` when Kiro's file watcher holds a read lock on the meta.json during the atomic rename. This is a timing race, not a permissions issue. **Workaround**: when `taskUpdate` fails with EPERM, fall back to editing `tasks.md` directly via `str_replace` (change `- [~]` or `- [ ]` to `- [x]` for the affected task). This bypasses the meta.json entirely and is reliable. Retry `taskUpdate` once before falling back — the lock is usually brief.

- **Preferred task execution method — kiro-cli**: ALWAYS prefer running spec tasks via the CLI agent rather than IDE-based execution. When tasks are ready to run, present the user with the exact command:
  ```
  kiro-cli chat --agent spec-executor --trust-all-tools "Execute all tasks in .kiro/specs/<spec-name>/tasks.md"
  ```
  Replace `<spec-name>` with the actual feature name. The `--trust-all-tools` flag enables autonomous execution without per-tool approval prompts. This approach is ~2.4x cheaper and ~7.6x faster than IDE Chat execution. The agent definition lives at `.kiro/agents/spec-executor.json`.
