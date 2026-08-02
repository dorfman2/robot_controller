#!/usr/bin/env bash
# Flash grblHAL firmware to BTT Octopus MAX EZ via DFU
#
# Usage:
#   ./scripts/flash_grblhal.sh <firmware.bin>
#
# Prerequisites:
#   1. dfu-util installed: sudo apt-get install dfu-util
#   2. Board in DFU mode: hold BOOT0 button, press RESET, release BOOT0
#   3. Firmware .bin downloaded from grblHAL WebBuilder:
#      https://svn.io-engineering.com:8443/
#      Settings: BTT Octopus MAX EZ, 6 axes (XYZABC), TMC5160 SPI,
#                soft limits, homing, Trinamic plugin
#
# Run on Pi: ssh pi@armold.local
#   sudo ./scripts/flash_grblhal.sh /tmp/grblhal_octopus.bin

set -euo pipefail

BIN_FILE="${1:-}"

if [ -z "$BIN_FILE" ]; then
    echo "Usage: $0 <firmware.bin>"
    echo ""
    echo "Steps:"
    echo "  1. Download .bin from https://svn.io-engineering.com:8443/"
    echo "     Board: BTT Octopus MAX EZ (STM32H723)"
    echo "     Plugins: 6 axes (XYZABC), TMC5160 SPI, soft limits, homing"
    echo "  2. Put board in DFU mode:"
    echo "     - Hold BOOT0 button"
    echo "     - Press and release RESET button"
    echo "     - Release BOOT0 button"
    echo "  3. Verify DFU device: dfu-util -l"
    echo "  4. Run: sudo $0 <path-to-firmware.bin>"
    exit 1
fi

if [ ! -f "$BIN_FILE" ]; then
    echo "ERROR: File not found: $BIN_FILE"
    exit 1
fi

echo "=== grblHAL Flash Tool for BTT Octopus MAX EZ ==="
echo ""

# Check if board is in DFU mode
echo "[1/3] Checking for DFU device..."
DFU_DEVICES=$(dfu-util -l 2>&1)
if echo "$DFU_DEVICES" | grep -q "0483:df11"; then
    echo "  ✓ STM32 DFU device found (0483:df11)"
else
    echo "  ✗ No STM32 DFU device found!"
    echo ""
    echo "  Put the board in DFU mode:"
    echo "    1. Hold BOOT0 button"
    echo "    2. Press and release RESET button"
    echo "    3. Release BOOT0 button"
    echo ""
    echo "  Then run this script again."
    exit 1
fi

echo ""
echo "[2/3] Flashing: $BIN_FILE"
echo "  Target: STM32H723 internal flash @ 0x08000000"
echo ""

dfu-util -a 0 -d 0483:df11 -s 0x08000000:leave -D "$BIN_FILE"

echo ""
echo "[3/3] Flash complete!"
echo ""
echo "  The board should reboot automatically."
echo "  Verify grblHAL is running:"
echo "    python3 -c \"import serial,time; s=serial.Serial('/dev/ttyACM0',115200,timeout=2); time.sleep(2); s.write(b'\\\\n'); time.sleep(0.5); print(s.read(s.in_waiting).decode())\""
echo ""
echo "  Expected output: 'GrblHAL 1.1f [...]' or similar banner"
