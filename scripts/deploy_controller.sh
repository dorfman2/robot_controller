#!/bin/bash
# ============================================================================
# Armold - Deploy Controller Daemon (Mac -> Pi)
# ============================================================================
# Syncs the armold_controller package to the Pi, installs dependencies,
# disables old services, and (re)starts the unified armold.service.
#
# Usage:
#   ./scripts/deploy_controller.sh
#
# Auth: uses the passphrase-less deploy key (~/.ssh/armold_deploy) and SSH
# connection multiplexing (ControlMaster) so the whole deploy authenticates
# ONCE instead of prompting on every ssh/rsync call. Override with env vars:
#   ARMOLD_SSH_KEY=/path/to/key  PI_HOST=pi@host  ./scripts/deploy_controller.sh
#
# Prerequisites:
#   - Pi accessible at armold.local
#   - Python 3 + virtualenv on Pi; passwordless sudo for user 'pi'
#   - The daemon runs from the /home/pi/armold-venv venv (created here on first
#     deploy) so the RTB IK stack is importable.
# ============================================================================

set -euo pipefail

PI_HOST="${PI_HOST:-pi@armold.local}"
PI_PROJECT_DIR="/home/pi/Armold"
SSH_KEY="${ARMOLD_SSH_KEY:-$HOME/.ssh/armold_deploy}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$SSH_KEY" ]]; then
    echo "ERROR: SSH key not found: $SSH_KEY" >&2
    echo "Set ARMOLD_SSH_KEY to your key path, or create the passphrase-less deploy key." >&2
    exit 1
fi

# One shared, multiplexed connection for every ssh/rsync below => single auth.
CONTROL_PATH="$HOME/.ssh/cm-armold-%r@%h:%p"
SSH_OPTS=(-i "$SSH_KEY"
          -o ControlMaster=auto
          -o "ControlPath=$CONTROL_PATH"
          -o ControlPersist=120
          -o StrictHostKeyChecking=accept-new)

ssh_pi() { ssh "${SSH_OPTS[@]}" "$PI_HOST" "$@"; }
cleanup() { ssh "${SSH_OPTS[@]}" -O exit "$PI_HOST" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "=== Armold Controller Deploy ==="
echo "Target: $PI_HOST:$PI_PROJECT_DIR"
echo "Key:    $SSH_KEY  (multiplexed - single auth)"
echo ""

# Establish the master connection up front (authenticates exactly once).
ssh "${SSH_OPTS[@]}" "$PI_HOST" true

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
    -e "ssh ${SSH_OPTS[*]}" \
    "$REPO_DIR/" \
    "$PI_HOST:$PI_PROJECT_DIR/"
echo "  Synced."

# --- Install dependencies ---
# Ubuntu 24.04 is PEP-668 "externally managed", so `pip install --user` is
# refused. We use a dedicated venv built with virtualenv --system-site-packages
# (reuses apt numpy/pyserial/websockets/aiohttp) and add the IK stack
# (roboticstoolbox pulls scipy/matplotlib/spatialmath as aarch64 wheels).
echo "[2/4] Installing Python dependencies into the armold venv..."
ssh_pi "
    set -e
    VENV=/home/pi/armold-venv
    if [ ! -x \"\$VENV/bin/python\" ]; then
        virtualenv --system-site-packages \"\$VENV\"
    fi
    \"\$VENV/bin/pip\" install --upgrade pip >/dev/null
    \"\$VENV/bin/pip\" install pyserial websockets aiohttp roboticstoolbox-python 2>&1 | tail -3
"

# --- Services: disable old + install/restart new (single connection) ---
echo "[3/4] Disabling old services + [4/4] installing armold.service..."
ssh_pi "
    sudo systemctl stop armold-bridge armold-rosbridge armold-watchdog 2>/dev/null || true
    sudo systemctl disable armold-bridge armold-rosbridge armold-watchdog 2>/dev/null || true
    sudo cp '$PI_PROJECT_DIR/pi/armold.service' /etc/systemd/system/armold.service
    sudo systemctl daemon-reload
    sudo systemctl enable armold
    sudo systemctl restart armold
"
echo "  Service (re)started."

echo ""
echo "=== Deploy Complete ==="
echo "Check status: ssh -i $SSH_KEY $PI_HOST 'systemctl status armold'"
echo "View logs:    ssh -i $SSH_KEY $PI_HOST 'journalctl -u armold -f'"
