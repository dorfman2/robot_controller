#!/bin/bash
# Install Armold systemd services on the Pi
# Usage: scp pi/install_services.sh pi@armold.local:~/ && ssh pi@armold.local "bash install_services.sh"

set -e

echo "Installing Armold systemd services..."

# Copy service files
sudo cp ~/armold-bridge.service /etc/systemd/system/
sudo cp ~/armold-rosbridge.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable armold-bridge.service
sudo systemctl enable armold-rosbridge.service

# Start services now
sudo systemctl start armold-bridge.service
sudo systemctl start armold-rosbridge.service

echo "Services installed and started."
echo ""
echo "Status:"
sudo systemctl status armold-bridge.service --no-pager -l | head -5
echo ""
sudo systemctl status armold-rosbridge.service --no-pager -l | head -5
echo ""
echo "Commands:"
echo "  sudo systemctl status armold-bridge"
echo "  sudo systemctl status armold-rosbridge"
echo "  sudo journalctl -u armold-bridge -f"
echo "  sudo journalctl -u armold-rosbridge -f"
