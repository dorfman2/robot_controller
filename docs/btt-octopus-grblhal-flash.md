# BTT Octopus MAX EZ — grblHAL Flash Guide

## Prerequisites

- BTT Octopus MAX EZ V1.0 board
- 7× EZ5160 RGB drivers installed in EZ sockets
- USB-C cable (board to computer or Pi)
- STM32CubeProgrammer installed (for DFU flashing)
  - Download: https://www.st.com/en/development-tools/stm32cubeprog.html
  - Or on Mac: `brew install stm32cubeprogrammer`

---

## Step 1: Download grblHAL Firmware

1. Go to **grblHAL WebBuilder**: https://svn.io-engineering.com:8443/
2. Select settings:
   - **Processor**: STM32H7xx
   - **Board**: BTT Octopus Max (or closest STM32H723 variant)
   - **Axes**: 6 (XYZABC)
   - **Trinamic driver**: TMC5160 (SPI mode)
   - **Plugins**: Enable:
     - Soft limits
     - Homing
     - Trinamic SPI driver support
     - CoolStep (optional)
3. Click **"Generate and download firmware"**
4. Save the `.bin` file (e.g., `grblHAL_BTT_OctopusMax.bin`)

---

## Step 2: Put Board in DFU Mode

1. **Power off** the board (disconnect 24V and USB)
2. Locate the **BOOT0** button on the Octopus MAX EZ
3. **Hold BOOT0** button down
4. While holding BOOT0, connect USB-C cable to computer
5. **Release BOOT0** after 2 seconds
6. The board is now in DFU mode (STM32 bootloader active)

### Verify DFU Mode

**Mac:**
```bash
system_profiler SPUSBDataType | grep -A5 "DFU"
```
Should show: `STM32 BOOTLOADER` or `DFU in FS Mode`

**Linux (Pi):**
```bash
lsusb | grep DFU
# or
dfu-util -l
```
Should show: `0483:df11 STMicroelectronics STM Device in DFU Mode`

---

## Step 3: Flash Firmware

### Option A: STM32CubeProgrammer (GUI — recommended for first flash)

1. Open STM32CubeProgrammer
2. Select **USB** connection (top-right dropdown)
3. Click **Connect**
4. Go to **Download** tab (left sidebar, arrow icon)
5. Browse to the `.bin` file from Step 1
6. Start address: `0x08000000`
7. Click **Start Programming**
8. Wait for "Download verified successfully"
9. Disconnect USB, remove BOOT0 jumper/button hold

### Option B: dfu-util (command line)

```bash
# Install if needed:
# Mac: brew install dfu-util
# Linux: sudo apt install dfu-util

# Flash:
dfu-util -a 0 -s 0x08000000:leave -D grblHAL_BTT_OctopusMax.bin
```

### Option C: From Pi (if board connected to Pi via USB)

```bash
ssh pi@armold.local

# Copy .bin to Pi first:
# scp grblHAL_BTT_OctopusMax.bin pi@armold.local:/tmp/

# Flash via dfu-util:
sudo dfu-util -a 0 -s 0x08000000:leave -D /tmp/grblHAL_BTT_OctopusMax.bin
```

---

## Step 4: Verify Flash

1. Disconnect and reconnect USB-C (normal mode, no BOOT0)
2. Board should enumerate as a serial device:
   - Mac: `/dev/cu.usbmodemXXXX`
   - Pi: `/dev/ttyACM0` or `/dev/ttyACM1`
3. Connect at 115200 baud:

```bash
# Mac:
screen /dev/cu.usbmodem* 115200

# Pi:
picocom /dev/ttyACM0 -b 115200
```

4. You should see the grblHAL startup message:
```
GrblHAL 1.1f ['$' for help]
```

5. Type `$$` to see all settings
6. Type `$I` to verify build info (should mention TMC5160, 6 axes)

---

## Step 5: Configure grblHAL Settings

After flashing, paste these settings via serial terminal:

```gcode
; Steps per degree (83,028 steps/rev ÷ 360°)
$100=230.6
$101=230.6
$102=230.6
$103=230.6
$104=230.6
$105=230.6

; Max feed rates (degrees/min)
$110=1800
$111=1800
$112=1800
$113=1800
$114=1800
$115=1800

; Acceleration (degrees/sec²)
$120=900
$121=900
$122=900
$123=900
$124=900
$125=900

; Soft limits — TOTAL travel (full range, not half)
$130=360
$131=180
$132=300
$133=240
$134=180
$135=360
$20=1

; Home pose reference: [0°, -30°, 70°, 50°, 0°, 0°]
; Place arm at this pose before running $H

; TMC5160 SPI settings (via Trinamic plugin)
$TMC_X_CURRENT=1200
$TMC_X_MICROSTEPS=16
$TMC_X_MODE=0
$TMC_Y_CURRENT=1200
$TMC_Y_MICROSTEPS=16
$TMC_Y_MODE=0
$TMC_Z_CURRENT=1200
$TMC_Z_MICROSTEPS=16
$TMC_Z_MODE=0
$TMC_A_CURRENT=1200
$TMC_A_MICROSTEPS=16
$TMC_A_MODE=0
$TMC_B_CURRENT=1200
$TMC_B_MICROSTEPS=16
$TMC_B_MODE=0
$TMC_C_CURRENT=1200
$TMC_C_MICROSTEPS=16
$TMC_C_MODE=0
```

---

## Step 6: Set Up udev Rule on Pi

Create `/etc/udev/rules.d/99-armold-motion.rules`:

```bash
sudo bash -c 'cat > /etc/udev/rules.d/99-armold-motion.rules << EOF
# BTT Octopus MAX EZ (STM32H723 USB CDC)
SUBSYSTEM=="tty", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="614e", \
  SYMLINK+="armold_motion", MODE="0666", GROUP="dialout"
EOF'

sudo udevadm control --reload-rules && sudo udevadm trigger
```

**Note**: VID/PID may differ. After connecting, run:
```bash
udevadm info /dev/ttyACM0 | grep -E 'idVendor|idProduct'
```
And update the rule accordingly.

---

## Step 7: Verify Communication

```bash
# Quick test from Pi:
echo '?' > /dev/armold_motion
cat /dev/armold_motion
# Should return: <Idle,MPos:0.000,0.000,0.000,0.000,0.000,0.000,...>

# Or use Python:
python3 -c "
import serial, time
ser = serial.Serial('/dev/armold_motion', 115200, timeout=1)
time.sleep(1)
ser.write(b'?\n')
time.sleep(0.5)
print(ser.read(ser.in_waiting).decode())
ser.close()
"
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No DFU device detected | Verify BOOT0 held during USB connect |
| "Error connecting to device" | Try different USB-C cable (data, not charge-only) |
| No serial port after flash | Board still in DFU mode — disconnect, reconnect without BOOT0 |
| `$$` returns nothing | Wrong baud rate — try 115200, or board didn't flash properly |
| TMC5160 not detected | Check EZ5160 driver orientation in socket |
| VID/PID different than expected | Run `lsusb` or `udevadm info` to find actual IDs |

---

## GRBL Axis Mapping

```
GRBL axis → Armold joint
    X     →     J0 (Base)
    Y     →     J1 (Shoulder)
    Z     →     J2 (Elbow)
    A     →     J3 (Wrist Pitch)
    B     →     J4 (Wrist Roll)
    C     →     J5 (Wrist Yaw)
```

## Quick Test Commands

```gcode
G1 X90 F1800          ; Rotate base 90°
G1 X0 Y-30 Z70 F1800  ; Move to home pose (shoulder, elbow)
!                      ; E-STOP (single byte, no newline)
~                      ; Resume after E-STOP
?                      ; Query position
$H                     ; Home all axes
```
