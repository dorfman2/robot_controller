"""
Armold Controller — Stable Motion Control Daemon.

Single-process daemon that replaces the ROS 2 bridge stack
(armold-bridge + rosbridge + watchdog) with a self-contained motion
controller. Communicates with Einsy RAMBo and RAMPS boards over USB
serial and exposes a WebSocket JSON API for the web UI.

Architecture:
    Web UI (browser) <-> WebSocket <-> armold_controller (this daemon)
                                             |
                                        Serial Thread(s)
                                             |
                                  +----------+----------+
                            /dev/armold_einsy      /dev/armold_ramps
                             (Joints 0-3)           (Joints 4-5)

Dependencies: pyserial, websockets
"""

__version__ = "0.1.0"
