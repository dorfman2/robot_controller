"""
SerialBoard — Thread-safe serial communication with a single motor controller board.

Runs a dedicated thread for exclusive serial port access. Commands are
submitted to a thread-safe queue and responses are paired with their
originating request via sequence numbers. Supports auto-reconnect,
accumulation buffer for partial reads, and E-STOP bypass.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Optional

from armold_controller.command import Command, CommandStatus

logger = logging.getLogger(__name__)


class SerialBoard:
    """Manages a serial connection to a single stepper controller board.

    Only the dedicated serial thread touches the serial port. External
    callers submit commands via the thread-safe queue or trigger E-STOP
    via direct write.

    Attributes:
        name: Human-readable board name for logging.
        port: Serial device path (e.g., '/dev/armold_einsy').
        baud: Baud rate (default 115200).
        num_joints: Number of joints controlled by this board.
    """

    RECONNECT_INTERVAL: float = 2.0
    READY_TIMEOUT: float = 10.0
    READ_TIMEOUT: float = 0.1

    def __init__(
        self,
        name: str,
        port: str,
        baud: int = 115200,
        num_joints: int = 4,
    ) -> None:
        """Initialize board connection (does not connect yet).

        Args:
            name: Board identifier for logging.
            port: Serial device path.
            baud: Baud rate.
            num_joints: Number of stepper axes on this board.
        """
        self.name = name
        self.port = port
        self.baud = baud
        self.num_joints = num_joints

        # State
        self._position: list[int] = [0] * num_joints
        self._pending_target: list[int] = [0] * num_joints
        self._enabled: bool = False
        self._connected: bool = False
        self._position_certain: bool = False
        self._estop_requested: bool = False
        self._moving: bool = False

        # Serial port (only touched by serial thread)
        self._ser: Optional[object] = None
        self._read_buffer: str = ""

        # Command queue
        self._command_queue: queue.Queue[Command] = queue.Queue()

        # Thread control
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Callbacks for motion manager
        self._halt_callback: Optional[object] = None
        self._state_callback: Optional[object] = None

    @property
    def position(self) -> list[int]:
        """Current firmware-confirmed position.

        Returns:
            List of joint positions.
        """
        return list(self._position)

    @property
    def pending_target(self) -> list[int]:
        """Virtual position for jog stacking.

        Returns:
            List of pending target positions.
        """
        return list(self._pending_target)

    @property
    def enabled(self) -> bool:
        """Whether motors are currently enabled.

        Returns:
            True if motors enabled.
        """
        return self._enabled

    @property
    def connected(self) -> bool:
        """Whether serial port is connected and ready.

        Returns:
            True if connected.
        """
        return self._connected

    @property
    def position_certain(self) -> bool:
        """Whether position is confirmed accurate.

        Returns:
            True if position is certain.
        """
        return self._position_certain

    @property
    def moving(self) -> bool:
        """Whether a move is currently in progress.

        Returns:
            True if board is executing a move command.
        """
        return self._moving

    @property
    def queue_depth(self) -> int:
        """Number of commands waiting in the queue.

        Returns:
            Queue size.
        """
        return self._command_queue.qsize()

    def set_halt_callback(self, callback: object) -> None:
        """Set callback for halt events (E-STOP / StallGuard).

        Args:
            callback: Callable(source: str, joint: Optional[int])
        """
        self._halt_callback = callback

    def set_state_callback(self, callback: object) -> None:
        """Set callback for state change events.

        Args:
            callback: Callable()
        """
        self._state_callback = callback

    def start(self) -> None:
        """Start the serial thread. Begins connection attempts."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name=f"serial-{self.name}", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the serial thread and close connection."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._close()

    def submit(self, cmd: Command) -> None:
        """Submit a command to the execution queue.

        Args:
            cmd: Command to queue for execution.
        """
        if not self._connected:
            cmd.complete(None, CommandStatus.ERROR)
            return
        self._command_queue.put(cmd)

    def estop(self) -> None:
        """Trigger emergency stop. Bypasses queue, writes directly.

        Sets the estop flag, clears the queue, and writes E0 directly
        to the serial port for immediate motor disable.
        """
        self._estop_requested = True
        self._flush_queue(CommandStatus.ESTOP)
        # Direct serial write (bypasses queue)
        self._direct_write("E0\n")

    def set_pending_target(self, target: list[int]) -> None:
        """Update the pending target for jog stacking.

        Args:
            target: New pending target positions.
        """
        self._pending_target = list(target)

    def _run(self) -> None:
        """Serial thread main loop. Connects, processes queue, reconnects."""
        while not self._stop_event.is_set():
            if not self._connected:
                self._attempt_connect()
                if not self._connected:
                    self._stop_event.wait(self.RECONNECT_INTERVAL)
                    continue

            # Check E-STOP flag
            if self._estop_requested:
                self._do_estop()
                continue

            # Process next command from queue
            try:
                cmd = self._command_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # Re-check E-STOP before executing
            if self._estop_requested:
                cmd.complete(None, CommandStatus.ESTOP)
                self._do_estop()
                continue

            self._execute(cmd)

    def _attempt_connect(self) -> None:
        """Try to open serial port and wait for READY banner."""
        import os

        if not os.path.exists(self.port):
            return

        try:
            import serial as pyserial

            self._ser = pyserial.Serial(
                self.port, self.baud, timeout=self.READ_TIMEOUT
            )
            time.sleep(2.0)  # Wait for Arduino reset
            self._ser.reset_input_buffer()
            self._read_buffer = ""

            # Wait for READY banner
            deadline = time.time() + self.READY_TIMEOUT
            while time.time() < deadline and not self._stop_event.is_set():
                line = self._read_line()
                if line and "READY" in line:
                    self._connected = True
                    logger.info(
                        "%s: Connected to %s", self.name, self.port
                    )
                    # Sync position
                    self._sync_position()
                    return

            logger.warning(
                "%s: No READY banner within %ss, trying direct sync...",
                self.name,
                self.READY_TIMEOUT,
            )
            # Firmware may already be running (no reset on connect)
            # Try direct state query
            self._ser.reset_input_buffer()
            self._read_buffer = ""
            self._sync_position()
            if self._position_certain:
                self._connected = True
                logger.info(
                    "%s: Connected to %s (no reset, direct sync)",
                    self.name,
                    self.port,
                )
                return
            self._close()

        except Exception as e:
            logger.error("%s: Connection failed: %s", self.name, e)
            self._close()

    def _sync_position(self) -> None:
        """Send S command and parse position from firmware response."""
        self._write("S\n")
        deadline = time.time() + 2.0
        while time.time() < deadline:
            line = self._read_line()
            if line and line.startswith("S "):
                parts = line.split()
                if len(parts) >= 2 + self.num_joints:
                    try:
                        self._enabled = parts[1] == "1"
                        for i in range(self.num_joints):
                            self._position[i] = int(parts[2 + i])
                        self._pending_target = list(self._position)
                        self._position_certain = True
                        logger.info(
                            "%s: Synced position: %s",
                            self.name,
                            self._position,
                        )
                        return
                    except (ValueError, IndexError):
                        pass
        logger.warning("%s: Position sync failed", self.name)
        self._position_certain = False

    def _execute(self, cmd: Command) -> None:
        """Execute a single command: send, wait for response, handle result.

        Args:
            cmd: Command to execute.
        """
        cmd.mark_sent()
        self._moving = cmd.payload.startswith("G")

        try:
            self._write(cmd.payload + "\n")
        except Exception as e:
            logger.error("%s: Write failed: %s", self.name, e)
            cmd.complete(None, CommandStatus.ERROR)
            self._handle_disconnect()
            return

        # Wait for response
        response = self._wait_response(cmd.timeout)

        if response is None:
            cmd.complete(None, CommandStatus.TIMEOUT)
            logger.warning(
                "%s: Timeout on cmd %d: %s",
                self.name,
                cmd.id,
                cmd.payload,
            )
            self._moving = False
            return

        # Check for halt conditions
        if response.startswith("ERR STALL"):
            joint = None
            parts = response.split()
            if len(parts) >= 3:
                try:
                    joint = int(parts[2])
                except ValueError:
                    pass
            self._handle_halt(source="collision", joint=joint)
            cmd.complete(response, CommandStatus.STALL)
            self._moving = False
            return

        if response == "OK E0" and cmd.payload.startswith("G"):
            # Move was interrupted by user E-STOP
            self._handle_halt(source="user", joint=None)
            cmd.complete(response, CommandStatus.ESTOP)
            self._moving = False
            return

        # Parse normal responses
        if response.startswith("OK G"):
            self._parse_position_response(response)
            cmd.complete(response, CommandStatus.OK)
        elif response.startswith("OK"):
            cmd.complete(response, CommandStatus.OK)
        elif response.startswith("ERR"):
            cmd.complete(response, CommandStatus.ERROR)
        elif response.startswith("S "):
            self._parse_state_response(response)
            cmd.complete(response, CommandStatus.OK)
        else:
            cmd.complete(response, CommandStatus.OK)

        self._moving = False

    def _parse_position_response(self, response: str) -> None:
        """Parse position from OK G response.

        Format: 'OK G p0 p1 p2 p3'

        Args:
            response: Raw response string.
        """
        parts = response.split()
        for i in range(self.num_joints):
            if i + 2 < len(parts):
                try:
                    self._position[i] = int(parts[i + 2])
                except ValueError:
                    pass
        self._pending_target = list(self._position)

    def _parse_state_response(self, response: str) -> None:
        """Parse state from S response.

        Format: 'S <enabled> <pos0> <pos1> ... <posN>'

        Args:
            response: Raw response string.
        """
        parts = response.split()
        if len(parts) >= 2 + self.num_joints:
            try:
                self._enabled = parts[1] == "1"
                for i in range(self.num_joints):
                    self._position[i] = int(parts[2 + i])
                self._pending_target = list(self._position)
            except (ValueError, IndexError):
                pass

    def _handle_halt(self, source: str, joint: Optional[int]) -> None:
        """Unified halt handler for user E-STOP and StallGuard collision.

        Args:
            source: 'user' or 'collision'.
            joint: Affected joint index, or None for user E-STOP.
        """
        self._enabled = False
        self._moving = False
        if source == "collision":
            self._position_certain = False
        self._flush_queue(CommandStatus.ESTOP)
        if self._halt_callback is not None:
            self._halt_callback(source, joint)

    def _handle_disconnect(self) -> None:
        """Handle serial disconnection. Flush queue, mark disconnected."""
        self._connected = False
        self._position_certain = False
        self._moving = False
        dropped = self._flush_queue(CommandStatus.ERROR)
        self._close()
        logger.warning(
            "%s: Disconnected, dropped %d queued commands",
            self.name,
            dropped,
        )

    def _do_estop(self) -> None:
        """Process E-STOP flag: write E0, reset flag."""
        self._direct_write("E0\n")
        self._estop_requested = False
        self._enabled = False
        self._moving = False

    def _flush_queue(self, status: CommandStatus) -> int:
        """Drain the command queue, completing all with given status.

        Args:
            status: Status to assign to all flushed commands.

        Returns:
            Number of commands flushed.
        """
        count = 0
        while not self._command_queue.empty():
            try:
                cmd = self._command_queue.get_nowait()
                cmd.complete(None, status)
                count += 1
            except queue.Empty:
                break
        return count

    def _direct_write(self, data: str) -> None:
        """Write directly to serial port (bypasses queue). For E-STOP only.

        Args:
            data: String to write.
        """
        if self._ser is not None:
            try:
                self._ser.write(data.encode())
            except Exception:
                pass

    def _write(self, data: str) -> None:
        """Write to serial port (called only from serial thread).

        Args:
            data: String to write.

        Raises:
            Exception: On serial write failure.
        """
        if self._ser is None:
            raise IOError("Serial port not open")
        self._ser.write(data.encode())

    def _read_line(self) -> Optional[str]:
        """Read a complete line from serial with accumulation buffer.

        Returns:
            Complete line (stripped) or None if no complete line available.
        """
        if self._ser is None:
            return None

        try:
            data = self._ser.read(256)
            if data:
                self._read_buffer += data.decode("utf-8", errors="replace")
        except Exception:
            self._handle_disconnect()
            return None

        # Check for complete line
        newline_idx = self._read_buffer.find("\n")
        if newline_idx >= 0:
            line = self._read_buffer[:newline_idx].strip()
            self._read_buffer = self._read_buffer[newline_idx + 1:]
            # Check for firmware reset
            if "READY" in line and self._connected:
                self._handle_firmware_reset()
            return line if line else None
        return None

    def _wait_response(self, timeout: float) -> Optional[str]:
        """Wait for a response line within timeout.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            Response line, or None on timeout.
        """
        deadline = time.time() + timeout
        while time.time() < deadline and not self._stop_event.is_set():
            if self._estop_requested:
                return None
            line = self._read_line()
            if line is not None:
                return line
        return None

    def _handle_firmware_reset(self) -> None:
        """Handle unexpected firmware reset (READY banner mid-operation)."""
        logger.warning(
            "%s: Firmware reset detected", self.name
        )
        self._position = [0] * self.num_joints
        self._pending_target = [0] * self.num_joints
        self._enabled = False
        self._position_certain = False
        self._moving = False
        self._flush_queue(CommandStatus.ERROR)

    def _close(self) -> None:
        """Close the serial port."""
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None
        self._connected = False
