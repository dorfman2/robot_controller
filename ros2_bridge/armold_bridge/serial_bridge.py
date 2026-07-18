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
    E1 / E0                       - Enable/disable motors
    M<joint> <steps> <dir> <delay> - Move joint by steps
    S                             - Query state
    R                             - Reset position counters
"""

import logging
from typing import Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int16, Int16MultiArray
import serial
import threading
import time

logger = logging.getLogger(__name__)


class ArmoldSerialBridge(Node):
    """ROS 2 node bridging serial communication to the Armold stepper controller.

    Subscribes to motor control topics and translates commands into serial
    protocol messages for the Arduino Mega running RAMPS firmware.

    Attributes:
        serial_port: Path to the serial device.
        baud_rate: Serial communication baud rate.
        step_delay: Default step delay in microseconds for motor moves.
    """

    def __init__(self) -> None:
        """Initialize the serial bridge node."""
        super().__init__('armold_serial_bridge')

        # Parameters
        self.declare_parameter('serial_port', '/dev/armold_ramps')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('step_delay', 800)
        self.declare_parameter('poll_rate', 5.0)  # Hz for state polling

        self.serial_port: str = self.get_parameter('serial_port').value
        self.baud_rate: int = self.get_parameter('baud_rate').value
        self.step_delay: int = self.get_parameter('step_delay').value
        poll_rate: float = self.get_parameter('poll_rate').value

        # Serial connection
        self._ser: Optional[serial.Serial] = None
        self._serial_lock = threading.Lock()
        self._current_position: list[int] = [0, 0, 0]
        self._target_position: list[int] = [0, 0, 0]
        self._motors_enabled: bool = False

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
        """Establish serial connection to the Arduino Mega.

        Retries connection every 2 seconds if the device is not available.
        """
        try:
            self._ser = serial.Serial(
                self.serial_port, self.baud_rate, timeout=1.0
            )
            time.sleep(2.0)  # Wait for Arduino reset
            # Flush startup messages
            self._ser.read(2048)
            self.get_logger().info(
                f'Connected to {self.serial_port} at {self.baud_rate} baud'
            )
        except serial.SerialException as e:
            self.get_logger().error(
                f'Failed to open {self.serial_port}: {e}. Will retry...'
            )
            self._ser = None
            # Retry timer
            self.create_timer(2.0, self._retry_connect)

    def _retry_connect(self) -> None:
        """Retry serial connection."""
        if self._ser is not None:
            return
        self._connect_serial()

    def _send_command(self, cmd: str) -> Optional[str]:
        """Send a command to the Arduino and return the response.

        Args:
            cmd: Command string (without newline).

        Returns:
            Response string from Arduino, or None if communication failed.
        """
        if self._ser is None:
            return None

        with self._serial_lock:
            try:
                self._ser.write(f'{cmd}\n'.encode())
                response = self._ser.readline().decode('utf-8', errors='replace').strip()
                return response
            except serial.SerialException as e:
                self.get_logger().error(f'Serial error: {e}')
                self._ser = None
                return None

    def _enable_callback(self, msg: Int16) -> None:
        """Handle /enable_motors topic.

        Args:
            msg: Int16 message. 1 = enable, 0 = disable.
        """
        enable = msg.data == 1
        cmd = 'E1' if enable else 'E0'
        response = self._send_command(cmd)
        if response:
            self._motors_enabled = enable
            self.get_logger().info(f'Motors {"enabled" if enable else "disabled"}: {response}')

    def _goal_callback(self, msg: Int16MultiArray) -> None:
        """Handle /stepper_goal topic.

        Accepts target positions for joints 0, 1, 2 as microstep counts.
        Calculates delta from current position and sends move commands.

        Args:
            msg: Int16MultiArray with 3 elements (target positions).
        """
        if len(msg.data) < 3:
            self.get_logger().warning(f'stepper_goal needs 3 values, got {len(msg.data)}')
            return

        if not self._motors_enabled:
            self.get_logger().warning('Motors not enabled, ignoring stepper_goal')
            return

        for joint in range(3):
            target = int(msg.data[joint])
            current = self._current_position[joint]
            delta = target - current

            if delta == 0:
                continue

            steps = abs(delta)
            direction = 0 if delta > 0 else 1  # 0 = forward, 1 = reverse

            cmd = f'M{joint} {steps} {direction} {self.step_delay}'
            response = self._send_command(cmd)

            if response and response.startswith('OK'):
                self._current_position[joint] = target
                self.get_logger().debug(
                    f'Joint {joint} moved to {target}: {response}'
                )
            else:
                self.get_logger().error(
                    f'Move failed joint {joint}: {response}'
                )

        self._target_position = list(msg.data[:3])

    def _poll_state(self) -> None:
        """Poll the Arduino for current state and publish to /stepper_state."""
        response = self._send_command('S')
        if response and response.startswith('S'):
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
                        self._current_position[2]
                    ]
                    self._state_pub.publish(state_msg)
                except (ValueError, IndexError) as e:
                    self.get_logger().debug(f'Parse error on state: {e}')

    def destroy_node(self) -> None:
        """Clean up serial connection on shutdown."""
        if self._ser and self._ser.is_open:
            self._send_command('E0')  # Disable motors on shutdown
            self._ser.close()
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
