#!/bin/bash
# ============================================================================
# Armold - SSH Setup (run from your Mac)
# ============================================================================
# This script:
#   1. Adds the Pi SSH config to ~/.ssh/config
#   2. Copies your ed25519 public key to the Pi
#   3. Hardens SSH on the Pi (disable password auth, root login)
#
# Prerequisites:
#   - Pi is booted and reachable at armold.local
#   - You can log in with: ssh ubuntu@armold.local (password auth)
#
# Usage: bash pi/setup_ssh.sh
# ============================================================================

set -e

PI_HOST="armold.local"
PI_USER="pi"
SSH_CONFIG="$HOME/.ssh/config"
PUB_KEY="$HOME/.ssh/id_ed25519.pub"

echo "============================================"
echo "  Armold - SSH Setup"
echo "============================================"
echo ""

# --- Check prerequisites ---
if [ ! -f "$PUB_KEY" ]; then
    echo "ERROR: No ed25519 key found at $PUB_KEY"
    echo "Generate one: ssh-keygen -t ed25519"
    exit 1
fi

# --- Add SSH config entry ---
echo "[1/3] Adding SSH config entry..."
if grep -q "Host armold" "$SSH_CONFIG" 2>/dev/null; then
    echo "  Already exists in $SSH_CONFIG, skipping."
else
    echo "" >> "$SSH_CONFIG"
    cat << 'EOF' >> "$SSH_CONFIG"

# Armold Robot Arm - Raspberry Pi
Host armold
    HostName armold.local
    User pi
    IdentityFile ~/.ssh/id_ed25519
    ForwardAgent yes
    StrictHostKeyChecking accept-new
EOF
    echo "  Added to $SSH_CONFIG"
fi

# --- Copy SSH key to Pi ---
echo "[2/3] Copying SSH key to Pi..."
echo "  You may be prompted for the Pi's password (default: whatever you set in Imager)"
ssh-copy-id -i "$PUB_KEY" "${PI_USER}@${PI_HOST}"

# --- Harden SSH on Pi ---
echo "[3/3] Hardening SSH on Pi (disable password auth)..."
ssh "${PI_USER}@${PI_HOST}" << 'REMOTE'
    # Disable password authentication
    sudo sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
    sudo sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
    sudo sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config

    # Restart SSH
    sudo systemctl restart sshd
    echo "SSH hardened: password auth disabled, key-only access."
REMOTE

echo ""
echo "============================================"
echo "  Done! Connect with:"
echo "    ssh armold"
echo "============================================"
