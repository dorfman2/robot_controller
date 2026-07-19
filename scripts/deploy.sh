#!/bin/bash
# ============================================================================
# Armold - Deploy & Flash Pipeline (Mac → Pi → Board)
# ============================================================================
# Syncs firmware source to the Pi and flashes the target board remotely.
#
# Usage:
#   ./scripts/deploy.sh [environment]
#
# Environments:
#   einsy   - Flash Einsy RAMBo (default)
#   ramps   - Flash RAMPS board
#
# Prerequisites:
#   - Pi accessible at armold.local
#   - PlatformIO installed on Pi
#   - Board connected to Pi USB
# ============================================================================

set -e

ENV="${1:-einsy}"
PI_HOST="pi@armold.local"
PI_PROJECT_DIR="/home/pi/armold_firmware"

echo "=== Armold Deploy & Flash ==="
echo "Environment: $ENV"
echo "Target: $PI_HOST:$PI_PROJECT_DIR"
echo ""

# --- Sync project files to Pi ---
echo "[1/3] Syncing firmware to Pi..."
rsync -az --delete \
    --include='platformio.ini' \
    --include='firmware/***' \
    --include='src/***' \
    --exclude='.*' \
    --exclude='.pio' \
    --exclude='node_modules' \
    --exclude='scripts' \
    --exclude='web' \
    --exclude='ros2_bridge' \
    --exclude='pi' \
    --exclude='launch' \
    /Users/jdorfman/Code/Armold/ \
    "$PI_HOST:$PI_PROJECT_DIR/"

echo "  Synced."

# --- Build & Flash on Pi ---
echo "[2/3] Building firmware ($ENV)..."
ssh "$PI_HOST" "cd $PI_PROJECT_DIR && export PATH=\$PATH:/home/pi/.local/bin && pio run -e $ENV 2>&1 | tail -5"

echo "[3/3] Flashing..."
ssh "$PI_HOST" "cd $PI_PROJECT_DIR && export PATH=\$PATH:/home/pi/.local/bin && pio run -e $ENV -t upload 2>&1 | tail -5"

echo ""
echo "=== Done ==="
