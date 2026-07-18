# Armold - Raspberry Pi Setup

## Hardware
- Raspberry Pi 4 (4GB or 8GB RAM)
- microSD card (32GB+, Class 10 or better)
- USB-C power supply (5V, 3A)
- Ethernet cable or Wi-Fi connection

## OS Installation

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Select OS: **Other general-purpose OS → Ubuntu → Ubuntu Server 22.04 LTS (64-bit)**
3. Click the gear icon for OS Customisation:
   - Hostname: `armold`
   - Enable SSH (password authentication)
   - Username: `ubuntu` (or your preference)
   - Configure Wi-Fi (SSID + password)
   - Set locale/timezone
4. Flash to SD card and boot the Pi

## First Boot

```bash
# SSH in from your Mac
ssh ubuntu@armold.local

# Copy the setup script to the Pi
scp pi/setup_ros2.sh ubuntu@armold.local:~/

# Run setup (~20-30 min)
bash ~/setup_ros2.sh

# Reboot
sudo reboot
```

## After Reboot

```bash
# Verify ROS 2
ros2 --version

# Plug Arduino Mega into Pi USB
# Verify serial device exists
ls -la /dev/armold_ramps

# Start micro-ROS agent
ros2 run micro_ros_agent micro_ros_agent serial --dev /dev/armold_ramps -b 115200
```

## Network Topology

```
Mac (development) ←── Wi-Fi ──→ Pi (ROS 2) ←── USB ──→ Arduino Mega (firmware)
                                                              │
                                                        RAMPS 1.4 + TMC2208
                                                              │
                                                     Stepper Motors (J0-J2)
```

## Controlling from Mac

Install ROS 2 on Mac (via Docker or native) or use the rosbridge websocket:

```bash
# On Pi, rosbridge is installed - start it:
ros2 launch rosbridge_server rosbridge_websocket_launch.xml

# From Mac, connect via websocket to ws://armold.local:9090
# Or install ROS 2 in Docker on Mac for native topic access
```

## ROS 2 Topics (Target Interface)

| Topic | Type | Description |
|-------|------|-------------|
| `/enable_motors` | std_msgs/Int16 | Enable (1) / disable (0) all motors |
| `/stepper_goal` | std_msgs/Int16MultiArray | Target positions for joints 0, 1, 2 |
| `/stepper_state` | std_msgs/Int16MultiArray | Current positions (feedback) |
| `/servo_goal` | std_msgs/Int16MultiArray | Target positions for joints 3, 4, 5 |
| `/servo_state` | std_msgs/Int32MultiArray | Current servo positions + gripper |
| `/gripper_goal` | std_msgs/Int16 | Gripper position (0-1023) |
