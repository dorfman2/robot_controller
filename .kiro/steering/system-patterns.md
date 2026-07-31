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
- **Gearbox ratio is ~25.95:1** (not 20:1) — measured empirically: 83,028 / (16 × 200) = 25.946
- **All S42C boards set to 16 microsteps** — uniform calibration, 230.6 steps/degree across all joints
- **S42C at 32 microsteps gives 75° when 90° expected** — because firmware assumed 20:1 gearbox; fixed by using empirical calibration
- **S42C closed-loop confirmed working**: position correction transparent, motor returns to exact start position
- **Soft limits prevent over-travel**: firmware clamps step count before execution, per-joint configurable
- **Deploy key for Pi**: `~/.ssh/armold_deploy` (ed25519, no passphrase) — use with `ssh -i ~/.ssh/armold_deploy pi@armold.local`
- **avrdude path on Pi**: `/home/pi/.platformio/packages/tool-avrdude/bin/avrdude` with conf at `/home/pi/.platformio/packages/tool-avrdude/avrdude.conf`
- **RAMPS serial on Pi**: `/dev/armold_ramps` → ttyUSB0 (udev symlink)
- **Flash command**: `rsync hex to /tmp/ then avrdude -p atmega2560 -c wiring -P /dev/armold_ramps -b 115200 -D -U flash:w:/tmp/ramps_s42c.hex:i`
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
- **grblHAL soft limits ($130-$135) use full range** not half-range (±180° = $130=360, not 180)
- **grblHAL real-time commands** (`!`, `~`, `?`) are single bytes that bypass the serial lock and interrupt mid-move
- **Never call `reset_input_buffer()` before G-code sends** — drops queued `ok` responses from prior commands
- **grblHAL WebBuilder URL**: `https://svn.io-engineering.com:8443/` (NOT build.grbl.org)
- **BTT Octopus MAX EZ uses native USB (STM32 CDC)** — baud rate is virtual; 115200 is fine
- **URDF for ikpy**: must include base_link (fixed) and end_effector link; `active_links_mask` has 8 elements for 6 active joints
- **Three.js Y-up → URDF Z-up mapping**: Y→Z for vertical axes, X stays X for pitch, adjust wrist roll accordingly
- **Armold_FK_v1 is a third-party reference** (LeeWhite187) — NOT built by Jeffrey; used for geometry extraction and as a digital twin UI
- **BTT Octopus MAX EZ grblHAL**: VID `0483` PID `5740` (STM32 Virtual COM Port)
- **grblHAL `$DFU` command**: enters DFU mode from running firmware — no BOOT0 button needed for reflash
- **grblHAL Bootloader Entry plugin**: present in current flash (`[PLUGIN:Bootloader Entry v0.02]`)
- **dfu-util `:leave` error on success**: "Error during download get_status" at end is normal (board resets)
- **BTT Octopus MAX EZ VUSB jumper**: must be bridged for USB-only power during DFU
- **DFU entry without button**: `echo '$DFU' > /dev/armold_motion && sleep 2 && sudo dfu-util ...`
- **grblHAL N_AXIS=7**: requires board map patch — stock `btt_octopus_max_map.h` only defines 6 motors
- **Motor-7 pins on BTT Octopus MAX EZ**: STEP=PD3, DIR=PD2, EN=PD4, CS/UART=PD7
- **grblHAL $376 (rotary axes)**: must be set explicitly — `IS_ROTARY_LETTER()` only checks A/B/C, misses U/Y/Z
- **Mixed mm+degree feed rate**: combined G-code (`G1 X175 Y90 F1800`) scales F as vector — send separately for predictable speed
- **Soft limits require known position**: `error:9` until homed or position set via `G10 L20`
- **TMC5160 on BTT Octopus MAX: SPI (not UART)** — pre-routed hardware SPI4, each driver has CS pin on GPIO G14-G9+D7
- **OAK-1 Lite**: monocular 13MP (IMX214), Myriad X VPU, no stereo depth, USB-C, 2.5W, auto-focus
- **DepthAI Python SDK**: `pip3 install depthai` — runs on Pi 4, controls OAK pipeline
- **Katapult bootloader on STM32H723**: USB enumeration fails after flash — board doesn't show up. Likely CONFIG issue with USB HS-in-FS mode on H723. Katapult compiled and flashed but jumped to empty 0x08020000 and crashed. Double-click reset didn't recover. Workaround: flash Klipper directly to 0x08000000 without Katapult. Revisit later with correct H723 USB config.
- **Klipper MCU on BTT Octopus MAX EZ**: must use `CONFIG_CLOCK_FREQ=520000000` (not 400MHz). Flash size is `0x40000`. `CONFIG_STM32_FLASH_START_0000` for no bootloader. USB enumerates as VID `1d50` PID `614e`.
- **Klipper serial ID**: `usb-Klipper_stm32h723xx_380009001151313531383332-if00`
- **Klipper config path mismatch**: klippy looks for `/home/pi/printer.cfg` but KIAUH installs to `~/printer_data/config/printer.cfg` — fixed with symlink
- **Klipper `flash_usb.py`**: alternative to Katapult for future updates — pulse DTR at 1200 baud to enter bootloader, then dfu-util. Requires `CONFIG_HAVE_BOOTLOADER_REQUEST=y` in Klipper build (already set).
- **Klipper Phase 4 partial success**: all 7 motors moved via `MANUAL_STEPPER MOVE=` commands (including Motor-7/J5 which failed in grblHAL!) — TMC5160 SPI working in Klipper
- **Motor overheating at idle**: 1.2A hold current too high for NEMA 17. Fixed with `hold_current: 0.300` (J3 at 0.750 due to load). Run current 0.800A for most, 1.200A for J3 only.
- **Klipper GCODE_AXIS limitation**: X/Y/Z axes can't be registered (reserved for kinematics). Only A/B/C/U work. Once registered, `MANUAL_STEPPER MOVE=` fails — must use `G1` instead. Two modes are mutually exclusive.
- **Klipper `MANUAL_STEPPER` SPEED parameter**: units are mm/s (or deg/s for rotary), not mm/min like G-code F values

## System Architecture

### Current (Einsy — running)
```
Browser (Web UI) ←── WebSocket (9090) ──→ armold_controller (Pi daemon)
                                                │
                                           Serial Threads
                                                │
                                     ┌──────────┴──────────┐
                               /dev/armold_einsy      /dev/armold_ramps
                                Einsy (J0-J3)          RAMPS (J4-J5)
```

### Next-Gen (BTT grblHAL — spec complete, awaiting hardware)
```
Browser (Web UI + FK Simulator)
    ↕ WebSocket (9090)
armold_controller (Pi daemon)
    ├── ikpy IK solver (Cartesian → joint angles)
    ├── GrblBoard (GRBL serial protocol, G-code sender)
    ├── Status poller (2Hz, `?` → broadcast)
    ├── Sequence → G-code converter
    └── Vision pipeline (OAK-1 Lite, future)
            ↕ USB-C native (/dev/armold_motion)
BTT Octopus MAX EZ (grblHAL, STM32H723 @ 480MHz)
    ├── 7-axis XYZABCU coordinated motion
    ├── TMC5160 SPI (via EZ5160 drivers)
    ├── S-curve + lookahead (built-in)
    ├── Hardware E-STOP pin
    ├── StallGuard4 (X axis / linear rail only)
    └── PWM servo (gripper, M280)
            ↕ STEP/DIR
EZ5160 × 7 → NEMA 17 × 7 → Cycloidal/GT2 → Joints + Rail
```    ├── GrblBoard (GRBL serial protocol, G-code sender)
    ├── Status poller (2Hz, `?` → broadcast)
    └── Sequence → G-code converter
            ↕ USB-C native (/dev/armold_motion)
BTT Octopus MAX EZ (grblHAL, STM32H723)
    ├── 6-axis XYZABC coordinated motion
    ├── TMC5160 SPI (via EZ5160 drivers)
    ├── S-curve + lookahead (built-in)
    └── Hardware E-STOP pin
            ↕ STEP/DIR
EZ5160 × 7 → NEMA 17 × 6 → 20:1 Cycloidal → Joints
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
- `firmware/ramps_s42c/src/main.cpp` — RAMPS 1.4 firmware for S42C (STEP/DIR, soft limits, sinusoidal ramp)
- `web/index.html` — Control UI (native WebSocket, no roslib.js)
- `scripts/deploy.sh` — Mac → Pi firmware deploy + flash
- `scripts/deploy_controller.sh` — Mac → Pi controller deploy
- `pi/armold.service` — systemd service file (single daemon)
- `ros2_bridge/` — OLD ROS 2 bridge (archived, superseded)
- `.kiro/specs/btt-grblhal-ik/` — BTT + grblHAL + IK spec (requirements, design, tasks)
- `.kiro/specs/ramps-s42c-closed-loop/` — RAMPS + S42C closed-loop spec (requirements, design, tasks)
- `docs/motion-controller-analysis.md` — Hardware options comparison (A/B/C/D/E + Mesa)

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
