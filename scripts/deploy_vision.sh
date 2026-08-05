#!/usr/bin/env bash
# Deploy vision modules to the Pi and install/restart systemd services.
#
# Usage (from repo root on Mac):
#   ./scripts/deploy_vision.sh
#
# What it does:
#   1. rsync vision scripts to /home/pi/vision/ on the Pi
#   2. Install systemd service files (oak-overhead, oak-side)
#   3. Stop the old transient oak-stream unit (if running)
#   4. Reload systemd, enable and start both camera services
#
# Prerequisites:
#   - SSH key at ~/.ssh/armold_deploy
#   - Pi reachable at armold.local
#   - armold-venv with depthai+opencv already on the Pi

set -euo pipefail

SSH="ssh -i ~/.ssh/armold_deploy pi@armold.local"
RSYNC="rsync -avz --delete -e 'ssh -i $HOME/.ssh/armold_deploy'"
REMOTE_DIR="/home/pi/vision"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Deploying Armold Vision ==="
echo "Source: ${SCRIPT_DIR}/scripts/vision/"
echo "Target: pi@armold.local:${REMOTE_DIR}/"
echo

# 1. Deploy vision scripts
echo "[1/4] Syncing vision scripts..."
eval $RSYNC "${SCRIPT_DIR}/scripts/vision/" "pi@armold.local:${REMOTE_DIR}/" \
    --exclude='__pycache__' \
    --exclude='*.pyc'
echo "  Done."

# 2. Deploy systemd service files
echo "[2/4] Installing systemd services..."
for svc in oak-overhead oak-side; do
    scp -i ~/.ssh/armold_deploy "${SCRIPT_DIR}/pi/${svc}.service" pi@armold.local:/tmp/${svc}.service
    $SSH "sudo mv /tmp/${svc}.service /etc/systemd/system/${svc}.service && sudo chmod 644 /etc/systemd/system/${svc}.service"
done
echo "  Done."

# 3. Stop old transient oak-stream if running
echo "[3/4] Stopping old oak-stream (if running)..."
$SSH "sudo systemctl stop oak-stream 2>/dev/null || true"
echo "  Done."

# 4. Reload and start services
echo "[4/4] Enabling and starting services..."
$SSH "sudo systemctl daemon-reload"
$SSH "sudo systemctl enable oak-overhead oak-side"
$SSH "sudo systemctl restart oak-overhead"
$SSH "sudo systemctl restart oak-side"

# Check status
echo
echo "=== Service Status ==="
$SSH "systemctl is-active oak-overhead; systemctl is-active oak-side" || true
echo
echo "Endpoints:"
echo "  Overhead: http://armold.local:8091/ (stream + /target + /grip)"
echo "  Side:     http://armold.local:8092/ (stream + /gap)"
echo
echo "=== Deploy Complete ==="
