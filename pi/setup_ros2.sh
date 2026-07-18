#!/bin/bash
# ============================================================================
# Armold - Raspberry Pi ROS 2 Humble Setup Script
# ============================================================================
# Target: Raspberry Pi 4 (4GB+ RAM) running Ubuntu Server 22.04 LTS (64-bit)
#
# Prerequisites:
#   1. Flash Ubuntu Server 22.04 LTS (64-bit) using Raspberry Pi Imager
#   2. Set hostname to 'armold', enable SSH, configure Wi-Fi in Imager
#   3. Boot Pi, SSH in: ssh ubuntu@armold.local
#   4. Run this script: bash setup_ros2.sh
#
# What this installs:
#   - ROS 2 Jazzy (ros-jazzy-ros-base)
#   - micro-ROS agent (serial bridge to Arduino Mega)
#   - Python dependencies for robot control
#   - udev rules for USB serial devices
#
# Duration: ~20-30 minutes on Pi 4 with decent internet
# ============================================================================

set -e

echo "============================================"
echo "  Armold - ROS 2 Jazzy Setup"
echo "  Target: Raspberry Pi 4 + Ubuntu 22.04"
echo "============================================"
echo ""

# --- System Update ---
echo "[1/7] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# --- Locale Setup ---
echo "[2/7] Setting up locale..."
sudo apt install -y locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# --- Add ROS 2 Repository ---
echo "[3/7] Adding ROS 2 apt repository..."
sudo apt install -y software-properties-common curl
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update

# --- Install ROS 2 Humble ---
echo "[4/7] Installing ROS 2 Jazzy (ros-base + dev tools)..."
sudo apt install -y \
    ros-jazzy-ros-base \
    ros-jazzy-rosbridge-suite \
    python3-argcomplete \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-pip \
    build-essential \
    cmake \
    git

# --- Initialize rosdep ---
echo "[5/7] Initializing rosdep..."
sudo rosdep init 2>/dev/null || true
rosdep update

# --- Install micro-ROS Agent ---
echo "[6/7] Installing micro-ROS agent..."
source /opt/ros/jazzy/setup.bash

# Create workspace for micro-ROS agent
mkdir -p ~/microros_ws/src
cd ~/microros_ws/src

git clone -b jazzy https://github.com/micro-ROS/micro_ros_setup.git
cd ~/microros_ws
colcon build
source install/local_setup.bash

# Create and build the agent
ros2 run micro_ros_setup create_agent_ws.sh
ros2 run micro_ros_setup build_agent.sh

# --- Setup USB serial access ---
echo "[7/7] Configuring USB serial access..."

# Add user to dialout group for serial port access
sudo usermod -a -G dialout $USER

# Install udev rules for the Arduino Mega and TMC2208
sudo tee /etc/udev/rules.d/99-armold.rules > /dev/null << 'EOF'
# Armold Robot Arm - USB Serial Devices
# Arduino Mega 2560 (RAMPS 1.4 + TMC2208 steppers)
ATTRS{idVendor}=="2341", ATTRS{idProduct}=="0042", SYMLINK+="armold_ramps", MODE:="0666"
ATTRS{idVendor}=="2341", ATTRS{idProduct}=="0010", SYMLINK+="armold_ramps", MODE:="0666"
# CH340 USB-Serial (common Arduino clones)
ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="armold_ramps", MODE:="0666"
# FTDI USB-Serial
ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", SYMLINK+="armold_ramps", MODE:="0666"
# CP2102 USB-Serial
ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", SYMLINK+="armold_ramps", MODE:="0666"
# OpenCM 9.04 (Robotis)
ATTRS{idVendor}=="fff1", ATTRS{idProduct}=="ff48", SYMLINK+="armold_opencm", MODE:="0666"
ATTRS{idVendor}=="0483", ATTRS{idProduct}=="5740", SYMLINK+="armold_opencm", MODE:="0666"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger

# --- Shell Configuration ---
echo "" >> ~/.bashrc
echo "# ROS 2 Jazzy" >> ~/.bashrc
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
echo "source ~/microros_ws/install/local_setup.bash" >> ~/.bashrc
echo "export ROS_DOMAIN_ID=0" >> ~/.bashrc
echo "# Armold robot arm" >> ~/.bashrc
echo "export ARMOLD_SERIAL_PORT=/dev/armold_ramps" >> ~/.bashrc

echo ""
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Reboot: sudo reboot"
echo "  2. Plug Arduino Mega into Pi USB port"
echo "  3. Verify device: ls -la /dev/armold_ramps"
echo "  4. Start micro-ROS agent:"
echo "     ros2 run micro_ros_agent micro_ros_agent serial --dev /dev/armold_ramps -b 115200"
echo "  5. From your Mac, publish to topics:"
echo "     ros2 topic pub /stepper_goal std_msgs/msg/Int16MultiArray \"{data: [100, 200, 300]}\""
echo ""
echo "NOTE: Log out and back in (or reboot) for group changes to take effect."
