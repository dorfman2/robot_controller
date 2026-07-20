#!/bin/bash
# ============================================================================
# Armold - Deploy Controller Daemon (Mac → Pi)
# ============================================================================
# Syncs the armold_controller package to the Pi, installs dependencies,
# disables old services, and enables the new unified service.
#
# Usage:
#   ./scripts/deploy_controller.sh
#
# Prerequisites:
#   - Pi accessible at armold.local
#   - Python 3.12 on Pi with pip
# ============================================================================

set -e

PI_HOST="pi@armold.local"
PI_PROJECT_DIR="/home/pi/Armold"

echo "=== Armold Controller Deploy ==="
echo "Target: $PI_HOST:$PI_PROJECT_DIR"
echo ""

# --- Sync controller code to Pi ---
echo "[1/4] Syncing controller to Pi..."
rsync -az --delete \
    --include='armold_controller/***' \
    --include='pi/armold.service' \
    --exclude='.*' \
    --exclude='.pio' \
    --exclude='firmware' \
    --exclude='scripts' \
    --exclude='web' \
    --exclude='ros2_bridge' \
    --exclude='launch' \
    --exclude='src' \
    --exclude='node_modules' \
    /Users/jdorfman/Code/Armold/ \
    "$PI_HOST:$PI_PROJECT_DIR/"

echo "  Synced."

# --- Install dependencies ---
echo "[2/4] Installing Python dependencies..."
ssh "$PI_HOST" "pip3 install --user pyserial websockets 2>&1 | tail -3"

# --- Disable old services ---
echo "[3/4] Disabling old services..."
ssh "$PI_HOST" "sudo systemctl stop armold-bridge armold-rosbridge armold-watchdog 2>/dev/null || true"
ssh "$PI_HOST" "sudo systemctl disable armold-bridge armold-rosbridge armold-watchdog 2>/dev/null || true"
echo "  Old services disabled."

# --- Install and start new service ---
echo "[4/4] Installing new armold.service..."
ssh "$PI_HOST" "sudo cp $PI_PROJECT_DIR/pi/armold.service /etc/systemd/system/armold.service"
ssh "$PI_HOST" "sudo systemctl daemon-reload"
ssh "$PI_HOST" "sudo systemctl enable armold"
ssh "$PI_HOST" "sudo systemctl restart armold"
echo "  Service started."

echo ""
echo "=== Deploy Complete ==="
echo "Check status: ssh $PI_HOST 'sudo systemctl status armold'"
echo "View logs:    ssh $PI_HOST 'sudo journalctl -u armold -f'"
