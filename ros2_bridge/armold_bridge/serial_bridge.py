"""
Armold Serial Bridge - ROS 2 Node (Dual Board, 6-DOF)

Bridges ROS 2 topics to two stepper controller boards over USB serial.
Board 1 (Einsy RAMBo): Joints 0-3 via TMC2130 SPI
Board 2 (RAMPS):       Joints 4-5 via TMC2208/2209 STEP/DIR

Subscriptions:
    /enable_motors (std_msgs/Int16)         - Enable (1) or disable (0) all motors
    /stepper_goal (std_msgs/Int16MultiArray) - Target positions for joints 0-5

Publishers:
    /stepper_state (std_msgs/Int16MultiArray) - Current positions of joints 0-5

Protocol (to both boards):
    E1 / E0                        - Enable/disable motors
    G <p0> <p1> ... <pN> [delay]   - Coordinated move (4 joints on Einsy, 2 on RAMPS)
    S                              - Query state
    R / R<j>                       - Reset position counters
"""

from typing import Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int16, Int16MultiArray
import serial
import threading
import time


class BoardConnection:
    """Manages a serial connection to a single stepper controller board.

    Attributes:
        name: Human-readable board name for logging.
        port: Serial device path.
        num_joints: Number of joints controlled by this board.
        position: Current position for each joint on this board.
    """

    def __init__(self, name: str, port: str, baud: int, num_joints: int,
                 step_delay: int, logger) -> None:
        """Initialize a board connection.

        Args:
            name: Board identifier for logging.
            port: Serial device path.
            baud: Baud rate.
            num_joints: Number of stepper axes on this board.
            step_delay: Default step delay in microseconds.
            logger: ROS 2 logger instance.
        """
        self.name = name
        self.port = port
        self.baud = baud
        self.num_joints = num_joints
        self.step_delay = step_delay
        self._logger = logger
        self._ser: Optional[serial.Serial] = None
        self._lock = threading.Lock()
        self._busy = False
        self.position: list[int] = [0] * num_joints
        self.motors_enabled: bool = False
        self.connected: bool = False

    def connect(self) -> bool:
        """Establish serial connection to the board.

        Returns:
            True if connection succeeded.
        """
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=0.5)
            time.sleep(2.0)
            self._ser.reset_input_buffer()
            self.connected = True
            self._logger.info(f'{self.name}: Connected to {self.port}')
            return True
        except serial.SerialException as e:
            self._logger.warn(f'{self.name}: Failed to open {self.port}: {e}')
            self._ser = None
            self.connected = False
            return False

    def send_command(self, cmd: str, timeout: float = 5.0) -> Optional[str]:
        """Send a command and read one line response.

        Args:
            cmd: Command string (without newline).
            timeout: Read timeout.

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
            self._logger.error(f'{self.name}: Serial error: {e}')
            self._ser = None
            self.connected = False
            return None

    def enable(self, enabled: bool) -> Optional[str]:
        """Enable or disable motors on this board."""
        cmd = 'E1' if enabled else 'E0'
        with self._lock:
            response = self.send_command(cmd, timeout=2.0)
        if response and 'OK' in response:
            self.motors_enabled = enabled
        return response

    def move_coordinated(self, targets: list[int]) -> bool:
        """Send a coordinated G command with target positions.

        Args:
            targets: List of target positions (one per joint on this board).

        Returns:
            True if move succeeded.
        """
        if not self.connected or not self.motors_enabled:
            return False

        # Skip if no movement needed
        if targets == self.position:
            return True

        self._busy = True
        try:
            with self._lock:
                positions_str = ' '.join(str(t) for t in targets)
                cmd = f'G {positions_str} {self.step_delay}'

                # Timeout based on max delta
                max_delta = max(
                    abs(targets[i] - self.position[i])
                    for i in range(len(targets))
                )
                move_duration = (max_delta * self.step_delay * 2) / 1_000_000.0
                timeout = move_duration + 5.0

                response = self.send_command(cmd, timeout=timeout)

                if response and response.startswith('OK G'):
                    parts = response.split()
                    # Parse positions from response: "OK G p0 p1 p2 ..."
                    for i in range(self.num_joints):
                        if i + 2 < len(parts):
                            try:
                                self.position[i] = int(parts[i + 2])
                            except ValueError:
                                self.position[i] = targets[i]
                        else:
                            self.position[i] = targets[i]
                    return True
                else:
                    self._logger.error(
                        f'{self.name}: Move failed: {response}'
                    )
                    return False
        finally:
            self._busy = False

    def poll_state(self) -> bool:
        """Poll board for current state.

        Returns:
            True if state was successfully read.
        """
        if self._busy or not self.connected:
            return False

        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            return False

        try:
            response = self.send_command('S', timeout=1.0)
        finally:
            self._lock.release()

        if response and response.startswith('S '):
            parts = response.split()
            # Format: "S <enabled> <pos0> <pos1> ... <posN>"
            if len(parts) >= 2 + self.num_joints:
                try:
                    self.motors_enabled = (parts[1] == '1')
                    for i in range(self.num_joints):
                        self.position[i] = int(parts[2 + i])
                    return True
                except (ValueError, IndexError):
                    pass
        return False

    def close(self) -> None:
        """Disable motors and close serial connection."""
        if self._ser and self._ser.is_open:
            with self._lock:
                try:
                    self._ser.write(b'E0\n')
                    time.sleep(0.1)
                    self._ser.close()
                except serial.SerialException:
                    pass


class ArmoldSerialBridge(Node):
    """ROS 2 node bridging serial communication to two Armold stepper boards.

    Manages Board 1 (Einsy, joints 0-3) and Board 2 (RAMPS, joints 4-5).
    Splits 6-joint goal messages across boards and dispatches moves in parallel.
    """

    # Total joints across both boards
    NUM_JOINTS = 6
    # Joint split: board 1 handles [0..BOARD1_JOINTS-1], board 2 handles the rest
    BOARD1_JOINTS = 4
    BOARD2_JOINTS = 2

    def __init__(self) -> None:
        """Initialize the dual-board serial bridge node."""
        super().__init__('armold_serial_bridge')

        # Parameters
        self.declare_parameter('board1_port', '/dev/armold_einsy')
        self.declare_parameter('board2_port', '/dev/armold_ramps')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('step_delay', 30)
        self.declare_parameter('poll_rate', 2.0)
        self.declare_parameter('board2_enabled', False)  # Disabled until RAMPS is wired

        board1_port: str = self.get_parameter('board1_port').value
        board2_port: str = self.get_parameter('board2_port').value
        baud_rate: int = self.get_parameter('baud_rate').value
        step_delay: int = self.get_parameter('step_delay').value
        poll_rate: float = self.get_parameter('poll_rate').value
        self._board2_enabled: bool = self.get_parameter('board2_enabled').value

        # Board connections
        self._board1 = BoardConnection(
            'Einsy', board1_port, baud_rate, self.BOARD1_JOINTS,
            step_delay, self.get_logger()
        )
        self._board2 = BoardConnection(
            'RAMPS', board2_port, baud_rate, self.BOARD2_JOINTS,
            step_delay, self.get_logger()
        )

        # Combined state
        self._current_position: list[int] = [0] * self.NUM_JOINTS
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

        # Connect boards
        self._board1.connect()
        if self._board2_enabled:
            self._board2.connect()
        else:
            self.get_logger().info('Board 2 (RAMPS) disabled — waiting for hardware')

    def _enable_callback(self, msg: Int16) -> None:
        """Handle /enable_motors topic. Enables/disables both boards."""
        enable = msg.data == 1

        resp1 = self._board1.enable(enable)
        if self._board2_enabled and self._board2.connected:
            self._board2.enable(enable)

        self._motors_enabled = enable
        self.get_logger().info(
            f'Motors {"enabled" if enable else "disabled"}: {resp1}'
        )

    def _goal_callback(self, msg: Int16MultiArray) -> None:
        """Handle /stepper_goal topic.

        Accepts 4 or 6 joint positions. Splits across boards and sends
        coordinated G commands in parallel.
        """
        data = list(msg.data)

        # Accept 4-joint messages (Einsy only) or 6-joint (both boards)
        if len(data) < self.BOARD1_JOINTS:
            self.get_logger().warning(
                f'stepper_goal needs at least {self.BOARD1_JOINTS} values, '
                f'got {len(data)}'
            )
            return

        if not self._motors_enabled:
            self.get_logger().warning('Motors not enabled, ignoring stepper_goal')
            return

        # Split targets by board
        board1_targets = [int(data[i]) for i in range(self.BOARD1_JOINTS)]
        board2_targets = None
        if len(data) >= self.NUM_JOINTS and self._board2_enabled:
            board2_targets = [
                int(data[self.BOARD1_JOINTS + i])
                for i in range(self.BOARD2_JOINTS)
            ]

        # Dispatch moves in parallel
        if board2_targets:
            # Start board 2 in a thread, board 1 on main
            t2 = threading.Thread(
                target=self._board2.move_coordinated, args=(board2_targets,)
            )
            t2.start()
            self._board1.move_coordinated(board1_targets)
            t2.join()
        else:
            self._board1.move_coordinated(board1_targets)

        # Update combined position
        self._current_position[:self.BOARD1_JOINTS] = self._board1.position
        if self._board2_enabled and self._board2.connected:
            self._current_position[self.BOARD1_JOINTS:] = self._board2.position

    def _poll_state(self) -> None:
        """Poll both boards and publish combined state."""
        self._board1.poll_state()
        if self._board2_enabled:
            self._board2.poll_state()

        # Build combined state
        self._current_position[:self.BOARD1_JOINTS] = self._board1.position
        if self._board2_enabled and self._board2.connected:
            self._current_position[self.BOARD1_JOINTS:] = self._board2.position

        self._motors_enabled = self._board1.motors_enabled

        state_msg = Int16MultiArray()
        state_msg.data = list(self._current_position)
        self._state_pub.publish(state_msg)

    def destroy_node(self) -> None:
        """Clean up both serial connections on shutdown."""
        self._board1.close()
        if self._board2_enabled:
            self._board2.close()
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
