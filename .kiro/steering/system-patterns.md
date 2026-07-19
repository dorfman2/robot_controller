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

## System Architecture
```
Mac (dev) ←── Wi-Fi ──→ Pi 4 (ROS 2 Jazzy) ←── USB ──→ Arduino Mega 2560
                                                              │
                                                        RAMPS 1.4 + TMC2208
                                                              │
                                                     Stepper Motors (J0-J2)
```

- **Mac** (macOS, darwin/zsh): Development, PlatformIO firmware builds, direct serial testing
- **Pi 4** (Ubuntu 24.04, arm64): ROS 2 runtime, micro-ROS agent, topic routing
- **Arduino Mega** (ATmega2560): Motor control firmware, STEP/DIR + TMC2208

## Code Structure
- `firmware/ramps/src/main.cpp` — Stepper motor test firmware (basic STEP/DIR, TMC2208)
- `firmware/opencm/src/main.cpp` — Dynamixel servo test firmware (serial commands)
- `scripts/example.py` — Original ROS 1 robot control (legacy, to be migrated)
- `scripts/check_serial.py` — Serial port connectivity checker
- `scripts/rotate_x_10.py` — Motor test: 10-degree rotation
- `scripts/enable_hold.py` — Motor test: enable and hold for torque check
- `pi/setup_ros2.sh` — ROS 2 install script for Pi
- `pi/setup_ssh.sh` — SSH key setup script (run from Mac)
- `pi/README.md` — Pi setup documentation
- `pi/ssh_config_entry` — SSH config snippet for ~/.ssh/config
- `platformio.ini` — PlatformIO build config (ramps + opencm environments)

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
