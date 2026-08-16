# Pi Re-provision Plan — Ubuntu 24.04 headless + ROS 2 Jazzy (2026-08-09)

Recovery plan for reflashing the Pi (executed 2026-08-15 onto a **Raspberry Pi 5, 2 GB** — hardware swap from the Pi 4). **Nothing critical is lost**: configs
(`printer.cfg`, services) live in this repo, the pen dataset is on the Mac
(`pen_dataset/`, 120 imgs), and labels/packaging regenerate from
`autolabel_pen.py`. udev rules + venv are recreated below.

Architecture note: the 6 CAN joint boards are now installed, so the fresh Pi
targets the **ROS 2 + CAN stack** (`ros2-can-motion` spec). Klipper/Moonraker
are NOT reinstalled unless the BTT fallback is explicitly wanted
(`pi/config_klipper.json` + KIAUH would restore it).

## Phase A — Flash (Mac, Raspberry Pi Imager)
- [ ] Image: **Ubuntu Server 24.04.x LTS (64-bit)** (Jazzy's matching LTS).
- [ ] Imager settings (⚠ cloud-init runs on FIRST BOOT ONLY — set these
      before booting, not after):
  - hostname: `armold`
  - user: `pi` + your password
  - SSH: enabled, key auth — add BOTH public keys:
    - personal key (`~/.ssh/id_ed25519.pub`)
    - deploy key (`~/.ssh/armold_deploy.pub`)
  - WiFi only if desired — wired Ethernet is what the DHCP reservation expects.
- [ ] Boot. DHCP reservation should hand it **192.168.1.136** again.
      `ping 192.168.1.136`, then `ssh pi@192.168.1.136`.

## Phase B — Base system (SSH in)
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y avahi-daemon git rsync avrdude python3-venv python3-pip \
    can-utils net-tools
sudo usermod -aG dialout pi
echo 'pi ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/010-pi-nopasswd
```
- [ ] Verify `armold.local` resolves from the Mac (avahi).
- [ ] Mac-side: `ssh armold` should work again (`pi/ssh_config_entry`).

## Phase C — udev serial rules (recreate — these were Pi-only)
`/etc/udev/rules.d/99-armold.rules`:
```
# Einsy RAMBo (ATmega32U2) — legacy, only if still connected
SUBSYSTEM=="tty", ATTRS{idVendor}=="2c99", SYMLINK+="armold_einsy"
# BTT Octopus MAX EZ running Klipper (only for BTT fallback)
SUBSYSTEM=="tty", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="614e", SYMLINK+="armold_motion"
# Arduino Mega 2560 — rail axis (UIM4247PM pulse generator)
SUBSYSTEM=="tty", ATTRS{idVendor}=="2341", ATTRS{idProduct}=="0042", SYMLINK+="armold_rail"
# CH340 clone Mega fallback (comment out if it collides with other CH340s)
# SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="armold_rail"
```
```bash
sudo udevadm control --reload-rules && sudo udevadm trigger
```
- [ ] Plug in the Mega → `/dev/armold_rail` appears (check real VID with
      `udevadm info -q property /dev/ttyACM0 | grep ID_VENDOR_ID`; genuine
      Mega = 2341:0042, CH340 clone = 1a86:7523 → adjust rule).

## Phase D — ROS 2 Jazzy
```bash
sudo add-apt-repository universe -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=arm64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu noble main" | \
    sudo tee /etc/apt/sources.list.d/ros2.list
sudo apt update
sudo apt install -y ros-jazzy-ros-base python3-colcon-common-extensions \
    python3-rosdep ros-jazzy-ros2-socketcan ros-jazzy-ros2-control \
    ros-jazzy-ros2-controllers
echo 'source /opt/ros/jazzy/setup.bash' >> ~/.bashrc
sudo rosdep init && rosdep update
```
- [ ] `ros2 doctor` clean (enough).

## Phase E — CAN bus (pre-stage; activates when the CANable arrives)
`/etc/systemd/network/80-can0.network`:
```
[Match]
Name=can0
[CAN]
BitRate=1M
```
```bash
sudo systemctl enable systemd-networkd
```
- [ ] After CANable arrives: plug in → `ip link show can0` UP at 1 Mbit;
      `candump can0` shows node telemetry.

## Phase F — Python venv + vision
```bash
python3 -m venv /home/pi/armold-venv
/home/pi/armold-venv/bin/pip install depthai opencv-python numpy websockets \
    pyserial roboticstoolbox-python spatialmath-python
```
- [ ] Mac: `scripts/deploy_vision.sh` (repopulates `/home/pi/vision/`).
- [ ] Mac: `scripts/deploy_controller.sh` (daemon, if keeping the WebSocket UI
      during the ROS 2 transition).
- [ ] Pi: `bash /home/pi/… /install_services.sh` — installs `armold.service`,
      `oak-overhead.service`, `oak-side.service` from `pi/`.
- [ ] Verify streams: `http://armold.local:8091/stream` (OAK-4 S, IP
      192.168.1.138) and `:8092/stream` (OAK-1 Lite side cam).
- [ ] Optional: re-upload the dataset when needed —
      `rsync -a pen_dataset/ pi@armold.local:/home/pi/pen_dataset/`; regenerate
      labels with `autolabel_pen.py` (labels/pen_yolo were disposable).

## Phase G — Rail smoke test (the task that was interrupted)
```bash
# Mac: build + push hex
export PATH="/Users/jdorfman/.platformio/penv/bin:$PATH"
pio run -e rail_smoke
rsync -e "ssh -i ~/.ssh/armold_deploy" .pio/build/rail_smoke/firmware.hex \
    pi@armold.local:/tmp/rail_smoke.hex
# Pi: flash (apt avrdude)
avrdude -p atmega2560 -c wiring -P /dev/armold_rail -b 115200 -D \
    -U flash:w:/tmp/rail_smoke.hex:i
# Pi: interactive test (wireless from the Mac, per option-1 decision)
python3 -m serial.tools.miniterm /dev/armold_rail 115200
```
- [x] Test 1: endstop NC check (motor power OFF): `?` → closed(ok); press →
      TRIGGERED; unplug a switch wire → TRIGGERED. **PASSED 2026-08-15 —
      fail-safe proven (wire break reads as stop).**
- [x] Test 2: enable/disable — `e` locks the shaft (operator-confirmed), port
      auto-reset releases it (spins free). **PASSED 2026-08-15.** Finding: Mega
      auto-resets on serial open → ENA drops to disabled on every reconnect;
      the future armold_rail_driver MUST re-enable (and re-verify position)
      after each connect, and the rail loses holding torque at reconnect.
- [x] Test 3: travel calibration — 6400 steps = **40.0 mm exactly** →
      **steps_per_mm = 160**; confirms factory 32 microsteps (6400 pulses/rev)
      and a 20T GT2 pulley (40 mm/rev). CW = toward the endstop (homing
      direction). **PASSED 2026-08-15.**
- [x] Test 4: direction reversal — CCW 6400 returns exactly to the reference
      mark (±40 mm round trip). **PASSED 2026-08-15.**
- [x] Test 5: speed ramp — out-and-back pairs at 2k/4k/8k/16k Hz, all 6400
      steps delivered, carriage back on the mark, clean travel. **16 kHz =
      100 mm/s with ZERO accel ramp, no missed steps.** With the real
      firmware's sinusoidal ramp, ≥100 mm/s is a safe cruising speed.
      **PASSED 2026-08-15.**
- [x] Test 6: mid-move endstop — long jog stopped instantly on switch press
      ("STOP: endstop triggered mid-move", 15417/32000 steps). **PASSED
      2026-08-15. SMOKE TEST COMPLETE — rail hardware signed off; factory
      UIM4247PM defaults are fine (no CFG344/Windows needed for bring-up).**
      Gotcha (self-inflicted): port reopen resets the Mega to default rate —
      don't re-send rate modifiers assuming prior state.

## Phase H — Verify checklist
- [ ] `ssh armold` (key), `armold.local` mDNS, IP 192.168.1.136
- [ ] `/dev/armold_rail` symlink survives replug
- [ ] ROS 2: `ros2 topic list` works
- [ ] Vision services running + streams reachable
- [ ] Rail smoke test passed
- [ ] Update steering (`tech-context` Pi section) with anything that changed

## Explicitly NOT restored (decisions)
- **Klipper + Moonraker + KIAUH** — superseded by the CAN joint boards; BTT
  is fallback-only (ros2-can-motion Phase 7 decision pending).
- **PlatformIO on the Pi** — plain `avrdude` (apt) is all the Mega needs.
- **rosbridge / old ros2_bridge** — archived, replaced by the daemon and the
  upcoming ros2_control stack.
