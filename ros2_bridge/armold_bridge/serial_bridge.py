"""
Armold Serial Bridge - ROS 2 Node

Bridges ROS 2 topics to the Arduino Mega running RAMPS stepper firmware
over USB serial. Translates topic messages into the Armold serial protocol.

Subscriptions:
    /enable_motors (std_msgs/Int16)         - Enable (1) or disable (0) motors
    /stepper_goal (std_msgs/Int16MultiArray) - Target positions for joints 0, 1, 2

Publishers:
    /stepper_state (std_msgs/Int16MultiArray) - Current positions of joints 0, 1, 2

Protocol (to Arduino):
    E1 / E0                        - Enable/disable motors
    M<joint> <steps> <dir> <delay> - Move joint by steps
    S                              - Query state
    R / R<j>                       - Reset position counters
"""

from typing import Optional
from collections import deque

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int16, Int16MultiArray
import serial
import threading
import time


class ArmoldSerialBridge(Node):
    """ROS 2 node bridging serial communication to the Armold stepper controller.

    Uses a single serial command thread to serialize all communication with the
    Arduino. Commands are queued and executed sequentially, preventing any race
    conditions between polling and move commands.
    """

    def __init__(self) -> None:
        """Initialize the serial bridge node."""
        super().__init__('armold_serial_bridge')

        # Parameters
        self.declare_parameter('serial_port', '/dev/armold_ramps')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('step_delay', 200)
        self.declare_parameter('poll_rate', 2.0)

        self.serial_port: str = self.get_parameter('serial_port').value
        self.baud_rate: int = self.get_parameter('baud_rate').value
        self.step_delay: int = self.get_parameter('step_delay').value
        poll_rate: float = self.get_parameter('poll_rate').value

        # Serial connection
        self._ser: Optional[serial.Serial] = None
        self._serial_lock = threading.Lock()

        # State
        self._current_position: list[int] = [0, 0, 0]
        self._motors_enabled: bool = False
        self._busy: bool = False  # True during a move

        # Subscribers
        self._enable_sub = self.create_subscription(
            Int16, '/enable_motors', self._enable_callback, 10
        )
        self._goal_sub = self.create_subscription(
            Int16MultiArray, '/stepper_goal', self._goal_callback, 10
        )

        # Publishers
        self._state_pub = self.create_publisher(
            Int16MultiArray, '/stepper_state', 10
        )

        # Timer for state polling
        self._poll_timer = self.create_timer(1.0 / poll_rate, self._poll_state)

        # Connect to serial
        self._connect_serial()

    def _connect_serial(self) -> None:
        """Establish serial connection to the Arduino Mega."""
        try:
            self._ser = serial.Serial(
                self.serial_port, self.baud_rate, timeout=0.5
            )
            time.sleep(2.0)  # Wait for Arduino reset
            self._ser.reset_input_buffer()
            self.get_logger().info(
                f'Connected to {self.serial_port} at {self.baud_rate} baud'
            )
        except serial.SerialException as e:
            self.get_logger().error(
                f'Failed to open {self.serial_port}: {e}. Will retry...'
            )
            self._ser = None
            self.create_timer(2.0, self._retry_connect)

    def _retry_connect(self) -> None:
        """Retry serial connection."""
        if self._ser is not None:
            return
        self._connect_serial()

    def _serial_command(self, cmd: str, timeout: float = 5.0) -> Optional[str]:
        """Send a command and read one line response.

        This is the only method that touches the serial port. All callers
        must hold _serial_lock or be guaranteed exclusive access.

        Args:
            cmd: Command string (without newline).
            timeout: Read timeout for the response.

        Returns:
            Response string, or None on error.
        """
        if self._ser is None:
            return None
        try:
            self._ser.reset_input_buffer()
            self._ser.write(f'{cmd}\n'.encode())
            self._ser.timeout = timeout
            line = self._ser.readline().decode('utf-8', errors='replace').strip()
            return line if line else None
        except serial.SerialException as e:
            self.get_logger().error(f'Serial error: {e}')
            self._ser = None
            return None

    def _enable_callback(self, msg: Int16) -> None:
        """Handle /enable_motors topic."""
        enable = msg.data == 1
        cmd = 'E1' if enable else 'E0'

        with self._serial_lock:
            response = self._serial_command(cmd, timeout=2.0)

        if response and 'OK' in response:
            self._motors_enabled = enable
            self.get_logger().info(
                f'Motors {"enabled" if enable else "disabled"}: {response}'
            )
        elif response:
            self.get_logger().warning(f'Enable unexpected response: {response}')

    def _goal_callback(self, msg: Int16MultiArray) -> None:
        """Handle /stepper_goal topic.

        Uses the G command for coordinated simultaneous movement of all joints.
        """
        if len(msg.data) < 3:
            self.get_logger().warning(
                f'stepper_goal needs 3 values, got {len(msg.data)}'
            )
            return

        if not self._motors_enabled:
            self.get_logger().warning('Motors not enabled, ignoring stepper_goal')
            return

        targets = [int(msg.data[0]), int(msg.data[1]), int(msg.data[2])]

        # Skip if no movement needed
        if targets == self._current_position:
            return

        self._busy = True
        try:
            with self._serial_lock:
                cmd = f'G {targets[0]} {targets[1]} {targets[2]} {self.step_delay}'

                # Timeout: based on max delta across all joints
                max_delta = max(
                    abs(targets[i] - self._current_position[i]) for i in range(3)
                )
                move_duration = (max_delta * self.step_delay * 2) / 1_000_000.0
                timeout = move_duration + 5.0

                response = self._serial_command(cmd, timeout=timeout)

                if response and response.startswith('OK G'):
                    parts = response.split()
                    if len(parts) >= 4:
                        try:
                            self._current_position[0] = int(parts[2])
                            self._current_position[1] = int(parts[3])
                            self._current_position[2] = int(parts[4])
                        except (ValueError, IndexError):
                            self._current_position = targets
                    else:
                        self._current_position = targets
                else:
                    self.get_logger().error(f'Move failed: {response}')
        finally:
            self._busy = False

    def _poll_state(self) -> None:
        """Poll Arduino state and publish to /stepper_state.

        Skips if a move is in progress or lock is held.
        """
        if self._busy:
            return

        acquired = self._serial_lock.acquire(blocking=False)
        if not acquired:
            return

        try:
            response = self._serial_command('S', timeout=1.0)
        finally:
            self._serial_lock.release()

        if response and response.startswith('S '):
            parts = response.split()
            if len(parts) >= 5:
                try:
                    self._motors_enabled = (parts[1] == '1')
                    self._current_position[0] = int(parts[2])
                    self._current_position[1] = int(parts[3])
                    self._current_position[2] = int(parts[4])

                    state_msg = Int16MultiArray()
                    state_msg.data = [
                        self._current_position[0],
                        self._current_position[1],
                        self._current_position[2],
                    ]
                    self._state_pub.publish(state_msg)
                except (ValueError, IndexError) as e:
                    self.get_logger().debug(f'Parse error: {e}')

    def destroy_node(self) -> None:
        """Clean up serial connection on shutdown."""
        if self._ser and self._ser.is_open:
            with self._serial_lock:
                try:
                    self._ser.write(b'E0\n')
                    time.sleep(0.1)
                    self._ser.close()
                except serial.SerialException:
                    pass
        super().destroy_node()


def main(args=None) -> None:
    """Entry point for the armold_serial_bridge node."""
    rclpy.init(args=args)
    node = ArmoldSerialBridge()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
