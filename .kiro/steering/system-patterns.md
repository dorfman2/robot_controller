---
inclusion: always
---

# System Patterns - Technical Architecture

## Important Security Patterns
- USB serial ports on macOS use `/dev/cu.*` (non-blocking) — avoid `/dev/tty.*` for programmatic access
- Pi SSH key-only auth (password disabled after setup)
- Pi user `pi` in `dialout` group for serial port access without root

## Learnings and Project Insights
- **RTB `ETS.eval(q)` returns a raw 4x4 numpy ndarray, NOT an SE3** — extract translation via `T[:3,3]` or wrap `SE3(T, check=False)` (no `.t` on the ndarray).
- **RTB `ETS.ik_LM(Tep, q0=...)` returns a 5-tuple** `(q_sol, success, iterations, searches, residual)`; use `mask=[1,1,1,0,0,0]` for position-only targets. Build joints with `ET.Rz()/Ry()/Rx()` (no arg = joint var) and links with `ET.tz(len)`.
- **RTB on the Pi 4 (aarch64) is fast**: FK ~0.001 ms, IK ~1 ms/solve — no GPU needed, no ikpy fallback required. Installs from prebuilt manylinux aarch64 wheels (no compilation); `rtb-data` wheel is ~116 MB (main download cost).
- **PEP-668 on Ubuntu 24.04**: `pip install --user` is refused ("externally-managed-environment"). Use a venv; if `python3-venv`/ensurepip is missing, `virtualenv --system-site-packages` works (that's how klippy-env/moonraker-env were built). `--system-site-packages` reuses apt numpy/pyserial/websockets/aiohttp so only the IK stack is added.
- **A venv shadows only within itself**: RTB pulls numpy 2.5.1 into the venv over the apt numpy 1.26.4 — no system impact because the venv's site-packages take precedence for that interpreter only.
- **IK↔board joint index offset**: `ik_solver` models arm joints 0..5 = J0..J5; KlipperBoard uses index 0 = rail, so board index = arm index + 1. Map with `{i+1: angle for i, angle in enumerate(result.joint_angles_deg)}`.
- **spatialmath RPY convention** pinned to `order="xyz"`, `unit="deg"` at the IK boundary; orientation error computed as the geodesic angle from `trace(R_target.T @ R_achieved)`.
- **DepthAI v3 (3.8.0) camera API** (major change from v2): `cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)`; `out = cam.requestOutput((w,h), dai.ImgFrame.Type.BGR888i, fps=15)`; `q = out.createOutputQueue()`; `with dai.Pipeline() as pipeline: ... pipeline.start(); q.get().getCvFrame()`. `DeviceInfo` has no `getMxId()` in v3.
- **OAK-1 Lite over USB2**: 720p uncompressed (BGR888i) crashes the device on teardown ("Device has crashed"); the frame before teardown is still valid. Use 640x360 for streaming. Move to USB3 port/cable for more headroom.
- **Green-marker detection is lighting-sensitive**: bright lights overexpose the tape (V high, S drops) so it falls out of the HSV green range → detection fails while brightness reads fine. Diagnose by sampling blob HSV with a loose range; fix by softer lighting or widening/lowering the S floor.
- **Overhead-camera marker placement**: put fiducial tape on the TOP of the end-effector (faces camera in any pose). Finger-tip tape gets occluded/edge-on when the arm folds to reach — invisible from above.
- **Hand-eye homography overfits with few points**: 4 points fit an 8-DOF homography almost exactly (tiny reprojection error is meaningless). Need many points over the actual working area, calibrated at the target Z plane (parallax makes a high-Z calibration wrong for objects on the desk unless perfectly nadir).
- **Reaching down/out hits joint limits**: this arm can't reach far-out + low-Z targets (IK returns "joint-limit clamping out of range"). Desk reachability is a small patch per rail position; the rail must reposition the patch. Verify reachability before planning pick moves.
- **SSH persistent process on the Pi**: `sudo systemd-run --unit=NAME --collect --setenv=PYTHONUNBUFFERED=1 VENV/bin/python script.py` reliably backgrounds a long-running process (prints "Running as unit:"). `nohup ... &` / `setsid ... &` and combining a background launch with a trailing pipe over SSH silently drop output / exit 255. Run the bare `systemd-run` on its own line; verify separately with `systemctl is-active` + `curl`. Stop with `sudo systemctl stop NAME`.
- **Grab one JPEG from an MJPEG stream**: read bytes until you find `\xff\xd8` … `\xff\xd9`. Always pull snapshots to UNIQUE local filenames — the IDE image viewer caches by path and shows a stale image for a reused name.
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
- **Katapult on STM32H723 — CORRECTED (2026-07-31)**: the earlier "USB enumeration fails / jumped to empty 0x08020000" failure was NOT a USB config issue — the leftover `~/katapult/.config` had been built for `stm32f103xe` (72MHz, 0x10000 flash, app@0x08002000). An F103 binary DFU'd to an H723 cannot init clocks/USB → no enumeration + crash. **Always verify `CONFIG_MCU`/`CONFIG_MACH_*` in `.config` before building.**
- **Katapult H723 correct config**: `make olddefconfig` from a fragment with `CONFIG_MACH_STM32H723=y`, `CONFIG_STM32_FLASH_START_20000=y` (128KiB → app@0x8020000), `CONFIG_STM32_CLOCK_REF_25M=y`, `CONFIG_STM32_USB_PA11_PA12=y`, `CONFIG_ENABLE_DOUBLE_RESET=y`. Verify `CONFIG_FLASH_APPLICATION_ADDRESS=0x8020000`. Katapult enumerates as `1d50:6177`.
- **DFU flash to STM32H723 (Octopus MAX EZ)**: needs `sudo` (`pi` hits `LIBUSB_ERROR_ACCESS` on `0483:df11` — no udev rule). ROM DFU alt=0 layout: `@Internal Flash /0x08000000/8*128Kg` (eight 128KiB sectors). Enter via BOOT0+RESET. `mass-erase` **requires the `:force` modifier**: `sudo dfu-util -a 0 -s 0x08000000:mass-erase:force:leave -D out/katapult.bin`. The `Error during download get_status` on `:leave` is benign (board resets).
- **Katapult flash-WRITE broken on v0.0.1-113-gec59b9b (H723) — issue #128 (EC11)**: Katapult boots/jumps fine but `flashtool.py` faults the MCU on the first `SEND_BLOCK` during the 128KiB app-sector erase (`Flash write failed, flash address 0x8020000`, board drops off USB). Not a client timeout (Jul-2025 timeout fix already present). Community "good" commit `3e23332` predates H7 flash support so is not a valid downgrade. **Workaround in use**: flash Klipper via ROM DFU to the app offset, preserving Katapult: `sudo dfu-util -a 0 -s 0x08020000:leave -D ~/klipper/out/klipper.bin` (dfu-util erases the target sector first). Boot chain then works: reset → Katapult@0x08000000 → Klipper@0x08020000 → klippy `ready`.
- **Klipper 128KiB-bootloader rebuild**: to run above Katapult, flip `CONFIG_STM32_FLASH_START_0000` → `_20000` (app@0x8020000); keep `CLOCK_FREQ=520000000`, 25MHz ref, USBSERIAL, VID/PID 1d50:614e. `make olddefconfig` + verify `.text`@0x08020000 via `arm-none-eabi-objdump -h out/klipper.elf`. Serial ID is unchanged (tied to chipid), so printer.cfg needs no edit.
- **Klipper MCU on BTT Octopus MAX EZ**: must use `CONFIG_CLOCK_FREQ=520000000` (not 400MHz). Flash size is `0x40000`. `CONFIG_STM32_FLASH_START_0000` for no bootloader. USB enumerates as VID `1d50` PID `614e`.
- **Klipper serial ID**: `usb-Klipper_stm32h723xx_380009001151313531383332-if00`
- **Klipper config path mismatch**: klippy looks for `/home/pi/printer.cfg` but KIAUH installs to `~/printer_data/config/printer.cfg` — fixed with symlink
- **Klipper `flash_usb.py`**: pulse DTR at 1200 baud to enter bootloader, then dfu-util. Requires `CONFIG_HAVE_BOOTLOADER_REQUEST=y` (already set). CAVEAT: with Katapult now installed at 0x08000000, a reset lands in Katapult, not the ROM DFU — so this does not cleanly bypass Katapult. Treat buttonless updates as unresolved until EC11 (Katapult flash-write) is fixed; use BOOT0+RESET → ROM DFU meanwhile.
- **Klipper Phase 4 partial success**: all 7 motors moved via `MANUAL_STEPPER MOVE=` commands (including Motor-7/J5 which failed in grblHAL!) — TMC5160 SPI working in Klipper
- **Motor overheating at idle**: 1.2A hold current too high for NEMA 17. Fixed with `hold_current: 0.300` (J3 at 0.750 due to load). Run current 0.800A for most, 1.200A for J3 only.
- **Klipper GCODE_AXIS (CORRECTED 2026-07-31)**: earlier claim "only A/B/C/U work" was WRONG. All 7 manual_steppers register fine to non-reserved letters **W A B C D H U** (only X/Y/Z/E/F/N are reserved). Registration confirmed by the toolhead/gcode_move position vector expanding to include all axes. Once registered, `MANUAL_STEPPER MOVE=` fails for that stepper — must use `G1` (two modes mutually exclusive). `FIRMWARE_RESTART` clears GCODE_AXIS regs → re-run `REGISTER_AXES`. Do NOT mix rail `W` (mm) with degree axes in one `G1` — `F` becomes a blended mm+deg vector (unpredictable speed); command the rail separately.
- **Phase 4 motor testing — ALL PASS (2026-07-31)**: via Moonraker `POST /printer/gcode/script`. All 7 steppers move bidirectionally (MANUAL_STEPPER SET_POSITION=0 then MOVE=±N SPEED=n), INCLUDING **stepper_u/J5 on Motor-7** (the grblHAL failure — Motor-8 fallback not needed). Coordinated `G90`+`G1 A20 H15 U25 F900` = simultaneous multi-joint motion. Gripper servo (PA1): **50°=open, 120°=closed** (recalibrated after re-centering the servo horn; UI slider limited to 50-120). Earlier attempts overheated the servo stalling against the stops until the horn was re-seated. E-STOP: `POST /printer/emergency_stop`→`shutdown`, `POST /printer/firmware_restart`→`ready`. DUMP_TMC uses bare stepper name (`stepper_x`). Capture gcode responses via `GET /server/gcode_store?count=N`.
- **Cooling fan**: `[fan_generic motor_fan]` on PF8 (FAN5); PA1/FAN4 unavailable (gripper). `SET_FAN_SPEED FAN=motor_fan SPEED=0..1`. FAN5 voltage set by VF5 jumper — mismatch makes fan spin slow/not at all (Klipper still drives 100% duty at SPEED=1).
- **EZ5160 sense_resistor = 0.050 (CRITICAL)**: Klipper's tmc5160 default is 0.075, but the BTT EZ5160 is a 50mOhm driver. Omitting `sense_resistor: 0.050` makes actual current ~1.5x the labeled `run_current` AND miscalibrates StallGuard's SG_RESULT. Set it explicitly on every `[tmc5160 ...]` section.
- **StallGuard sensorless homing NOT viable on the belt rail (2026-08-01)**: the belt skips on the pulley before the motor rotor stalls, so StallGuard never sees a load spike distinct from free-motion noise. Full scan (even with correct sense_resistor, gentle accel, and 40mm/s): `driver_SGT <= 11` false-trips during the move, `>= 12` belt-skips with no trigger — no usable window. TMC5160 SGT polarity: **-64 = most sensitive, +63 = least**. Adopted MANUAL homing instead.
- **Klipper manual_stepper + TMC virtual endstop config ORDERING**: `[tmc5160 manual_stepper X]` MUST come before `[manual_stepper X]` in printer.cfg — manual_stepper resolves `endstop_pin` at init (stepper.LookupRail) before the tmc section registers the `tmc5160_X:virtual_endstop` chip (chip name = tmc.py: name_parts[0]_name_parts[-1] = `tmc5160_stepper_x`). Regular kinematic steppers avoid this (load late with toolhead).
- **TMC5160 sensorless diag pin polarity**: use `diag1_pin: ^!PF0` (pull-up + invert) so the virtual endstop reads `open` at rest; bare `PF0` read TRIGGERED at rest and blocked the homing move at 0 distance. (The virtual_endstop pin itself can't take ^/! — only the raw diag pin can.)
- **Manual rail homing macros** (StallGuard abandoned): `RELEASE_RAIL` (`MANUAL_STEPPER STEPPER=stepper_x ENABLE=0`) → push carriage to home (negative) end → `SET_RAIL_HOME` (`SET_POSITION=0`). Rail dir inverted (`dir_pin: !PC14`) so negative = home.
- **armold_controller soft limits** (`klipper_board.py`): Klipper manual_stepper does NOT enforce position limits — armold_controller must. `JointLimit` dataclass + `DEFAULT_SOFT_LIMITS` (rail 0-406mm; J0 ±180, J1 ±90, J2 ±150, J3 ±120, J4 ±90, J5 ±180); `clamp_target()` applied in jog_joint/move_coordinated. Also fixed jog to be relative (current+delta) since MANUAL_STEPPER MOVE is absolute.
- **armold.service `200/CHDIR`**: service WorkingDirectory `/home/pi/Armold` didn't exist (daemon never fully deployed) → auto-restart loop. `scripts/deploy_controller.sh` rsyncs to `/home/pi/Armold` and will create it. We drove Klipper directly via Moonraker HTTP all of Phase 4-6, bypassing the daemon. Deployed 2026-08-01: daemon active, WS 9090 up.
- **Phase 7 validation PASSED (2026-08-01)**: (1) `DUMP_TMC` current/temp check found the EZ5160 sense_resistor bug → fixed `sense_resistor: 0.050` on ALL 7 (GLOBALSCALER uniform 45@0.8A / 67@J3 1.2A; no otpw/ot). (2) Per-joint currents (run/hold): rail 0.8/0.3, base 0.8/0.3, **shoulder(z) 1.4/1.1**, elbow(a) 0.9/0.3, J3 pitch(b) 1.2/0.75, roll 0.8/0.3, yaw 0.8/0.3 — shoulder tuned up (0.8A stalled at full extension; 1.0A ok to ±50°; 1.2A lifted 90° at FULL extension; raised to 1.4A run for margin). Monitor shoulder temp on long runs (1.4A is near NEMA17 rating). (3) All 7 move concurrently (MANUAL_STEPPER SYNC=0). (4) Position accuracy: base 90° cmd = 90° measured (rotation_distance 13.87 confirmed). (5) USB unplug → klippy shutdown → FIRMWARE_RESTART (often ×2) → ready; NOT hands-off (recommend watchdog auto-restart). Final validated config saved to repo `pi/printer.cfg`.
- **Klipper SYNC=0 for concurrent manual_stepper motion**: `MANUAL_STEPPER STEPPER=x MOVE=n SPEED=s SYNC=0` returns without waiting, so issuing all 7 back-to-back runs them concurrently. Use this for multi-joint motion instead of one mixed-unit G1 (rail mm + degree axes blends the F feedrate). Add `G4 P<ms>` dwell to wait for completion before the return batch.
- **Klipper `MANUAL_STEPPER` SPEED parameter**: units are mm/s (or deg/s for rotary), not mm/min like G-code F values
- **Direct joint-space move bypassing the daemon IK (2026-08-03)**: to command exact absolute joint angles without the daemon's Cartesian IK, POST concurrent `MANUAL_STEPPER STEPPER=<name> MOVE=<deg> SPEED=<s> ACCEL=300 SYNC=0` (one per joint) to Moonraker `/printer/gcode/script`. `MOVE=` is absolute in degrees (arm) / mm (rail); the manual_stepper keeps its absolute reference between moves. Bypasses IK seed fragility but DESYNCS the daemon's internally-tracked `_position` (daemon does not read Klipper position). Helper: `scripts/vision/col_move.py`. Moonraker `objects/query` returns `{}` for `manual_stepper <name>` (commanded_pos not published) — cannot read position back that way.
- **RTB `ik_LM` is seed-sensitive at the reach edge (2026-08-03)**: from a "wrong-branch" seed (e.g. a tilted wrist config) the LM solver won't converge to a different valid IK branch (e.g. a vertical-gripper solution) even with random restarts (slimit=150); a home-pose seed does converge. Pattern for a robust trajectory: solve the FIRST waypoint home-seeded, then WARM-START each subsequent waypoint from the previous solution → a continuous joint column with small per-step deltas. Execute the column as direct joint moves (see above) rather than per-waypoint Cartesian IK on the arm.
- **`SYNC=0` concurrent moves are NOT a straight joint-space line**: each joint ramps at the same SPEED (deg/s) and shorter moves finish first, so the tool path is time-parameterised, not linearly interpolated. To check clearance before a move near a surface, simulate `position_j(t) = start_j + sign·min(SPEED·t, |Δ_j|)` and evaluate FK tip-Z over t (see `scripts/vision/path_safety.py`).
- **Straight-down gripper orientation (this arm)**: the tool long axis is the EE-frame **+Y** (ETS ends with `ty(+81)`), so "gripper points straight down" ⇔ EE +Y aligned with world **−Z**. A vertical gripper has one FREE DOF (spin about vertical / finger-opening direction) — sweep it to find an in-limits, genuinely-vertical (approach axis z<−0.98) solution. A commanded rpy that merely "looks down" (e.g. pitch −60) can be ~30° off vertical; verify with the FK rotation column, not by eye. Helpers: `explore_straightdown.py`, `find_vertical.py`, `vertical_column.py`.
- **Grab a single JPEG from an MJPEG stream** without a client lib: read a chunk of the `multipart/x-mixed-replace` stream and slice between the JPEG SOI/EOI markers — `a=data.find(b"\xff\xd8"); b=data.find(b"\xff\xd9",a); frame=data[a:b+2]`. Useful for pulling one detect-overlay frame off `:8091/stream` to inspect the ROI.
- **Tuning the detect-stream ROI**: `ROI_FRAC=(x0,y0,x1,y1)` fractions in `oak_detect_stream.py`; frame is **640×360**. Color-segmenting a muted blue-gray mat via HSV is unreliable (spills into dark tools/background) — place the ROI by eye against a grabbed frame instead. The deployed `/home/pi/oak_detect_stream.py` can diverge from the repo copy — pull-edit-push to keep `scripts/vision/oak_detect_stream.py` in sync.

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

### Cartesian IK data flow (RTB — integrated 2026-07-31)
```
Web UI (Cartesian panel)
  → {cmd: move_cartesian, x,y,z, [roll,pitch,yaw], speed}  (WebSocket 9090)
    → ws_server_klipper._handle_move_cartesian
      → ArmIK.solve_ik(CartesianTarget, seed=current arm joints)   # ik_solver.py, RTB ETS.ik_LM
        → clamp to joint limits, recompute FK, report errors
      → KlipperBoard.goto_positions({board_idx: angle})   # arm idx i -> board idx i+1 (0=rail)
  ← state broadcast augmented with end_effector FK pose (2 Hz)
```
- Rail (board joint 0) is NOT in the IK chain — commanded separately as a gross-positioning axis.
- Point-to-point per-joint move (no path planning / no collision checking) — caller ensures the straight-line joint interpolation is safe.
- Daemon runs from `/home/pi/armold-venv` so RTB is importable (see tech-context).

## Code Structure
- `armold_controller/` — Motion control daemon (Pi)
  - `__init__.py` — Package init, version
  - `__main__.py` — Entry point, config, signal handling, health check
  - `main.py` — Convenience entry point
  - `command.py` — Command dataclass with sequence IDs and lifecycle
  - `serial_board.py` — Per-board serial thread + command queue + ACK
  - `motion_manager.py` — Move coordination, jog stacking, halt
  - `klipper_board.py` — Moonraker API client (KlipperBoard: goto_positions, jog, soft-limit clamp)
  - `ws_server.py` — asyncio WebSocket + JSON protocol (serial backend)
  - `ws_server_klipper.py` — asyncio WebSocket + JSON protocol (Klipper backend; move_cartesian, waypoints, EE FK broadcast)
  - `ik_solver.py` — RTB 6-DOF arm FK/IK (ArmIK, ArmGeometry, CartesianTarget, IKResult); rail excluded
  - `waypoints.py` — Named arm-pose store (save/goto/delete)
  - `tests/` — Unit/integration tests (test_ik_solver 15, test_ws_move_cartesian 4, test_soft_limits 8, test_waypoints 8, test_core, test_klipper_board, test_trajectory_planner)
- `firmware/einsy/src/main.cpp` — Einsy RAMBo firmware (TMC2130 SPI, 4-axis)
- `firmware/ramps/src/main.cpp` — RAMPS firmware (basic STEP/DIR, 3-axis)
- `firmware/ramps_s42c/src/main.cpp` — RAMPS 1.4 firmware for S42C (STEP/DIR, soft limits, sinusoidal ramp)
- `web/index.html` — Control UI (native WebSocket, no roslib.js)
- `scripts/deploy.sh` — Mac → Pi firmware deploy + flash
- `scripts/deploy_controller.sh` — Mac → Pi controller deploy
- `pi/armold.service` — systemd service file (single daemon)
- `ros2_bridge/` — OLD ROS 2 bridge (archived, superseded)
- `.kiro/specs/rtb-cartesian-ik/` — RTB Cartesian IK spec (requirements, design, tasks) — CURRENT
- `.kiro/specs/btt-grblhal-ik/` — BTT + grblHAL + IK spec (requirements, design, tasks) — superseded by Klipper
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
