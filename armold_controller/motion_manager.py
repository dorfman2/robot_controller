"""
MotionManager — Orchestrates multi-board moves and jog stacking.

Coordinates commands across multiple SerialBoard instances, manages
speed profiles, and handles the unified halt system (user E-STOP and
StallGuard collision detection).
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from armold_controller.command import Command, CommandStatus
from armold_controller.serial_board import SerialBoard

logger = logging.getLogger(__name__)

# Joint name constants
JOINT_NAMES: list[str] = [
    "Base",
    "Shoulder",
    "Elbow",
    "Wrist Pitch",
    "Wrist Roll",
    "Wrist Yaw",
]

# Total joints across all boards
NUM_JOINTS: int = 6


class MotionManager:
    """Orchestrates motion commands across multiple boards.

    Manages jog stacking via pending_target, speed profiles,
    and unified halt handling for all halt sources.

    Attributes:
        boards: Dictionary of board name -> SerialBoard instance.
        step_delay: Current step delay in microseconds.
        min_delay: Minimum allowed step delay.
        max_delay: Maximum allowed step delay.
    """

    def __init__(
        self,
        boards: dict[str, SerialBoard],
        step_delay: int = 30,
        min_delay: int = 30,
        max_delay: int = 5000,
    ) -> None:
        """Initialize the motion manager.

        Args:
            boards: Dictionary of board name -> SerialBoard instance.
            step_delay: Default step delay in microseconds.
            min_delay: Minimum allowed step delay.
            max_delay: Maximum allowed step delay.
        """
        self.boards = boards
        self.step_delay = step_delay
        self.min_delay = min_delay
        self.max_delay = max_delay

        # Combined state across all boards
        self._enabled: bool = False
        self._has_pending: bool = False

        # Broadcast callback (set by WebSocket server)
        self._broadcast_fn: Optional[Callable[[dict[str, Any]], None]] = None

        # Register halt callbacks on boards
        for name, board in self.boards.items():
            board.set_halt_callback(
                lambda source, joint, n=name: self._on_board_halt(
                    n, source, joint
                )
            )

    def set_broadcast(self, fn: Callable[[dict[str, Any]], None]) -> None:
        """Set the broadcast function for sending messages to all clients.

        Args:
            fn: Callable that broadcasts a dict message to all WebSocket clients.
        """
        self._broadcast_fn = fn

    @property
    def enabled(self) -> bool:
        """Whether motors are enabled.

        Returns:
            True if motors are enabled.
        """
        return self._enabled

    def get_state(self) -> dict[str, Any]:
        """Build the full state dict for broadcasting.

        Returns:
            State dictionary matching the WebSocket protocol.
        """
        position = [0] * NUM_JOINTS
        pending_target = [0] * NUM_JOINTS
        connected: dict[str, bool] = {}
        position_certain = True
        queue_depth = 0
        moving = False

        offset = 0
        for name, board in self.boards.items():
            connected[name] = board.connected
            for i in range(board.num_joints):
                if offset + i < NUM_JOINTS:
                    position[offset + i] = board.position[i]
                    pending_target[offset + i] = board.pending_target[i]
            if not board.position_certain:
                position_certain = False
            queue_depth += board.queue_depth
            if board.moving:
                moving = True
            offset += board.num_joints

        return {
            "type": "state",
            "enabled": self._enabled,
            "position": position,
            "pending_target": pending_target,
            "speed": self.step_delay,
            "connected": connected,
            "position_certain": position_certain,
            "queue_depth": queue_depth,
            "moving": moving,
        }

    def enable(self) -> None:
        """Enable motors on all connected boards."""
        for name, board in self.boards.items():
            if board.connected:
                cmd = Command(payload="E1", timeout=2.0)
                board.submit(cmd)
        self._enabled = True
        logger.info("Motors enabled")

    def disable(self) -> None:
        """Disable motors on all connected boards."""
        for name, board in self.boards.items():
            if board.connected:
                cmd = Command(payload="E0", timeout=2.0)
                board.submit(cmd)
        self._enabled = False
        logger.info("Motors disabled")

    def estop(self) -> None:
        """Emergency stop all boards. Bypasses queue."""
        for name, board in self.boards.items():
            board.estop()
        self._enabled = False
        self._has_pending = False
        self.halt(source="user", joint=None)

    def move_absolute(
        self,
        target: list[int],
        callback: Optional[Callable[[int, Optional[str], CommandStatus], None]] = None,
    ) -> int:
        """Queue a coordinated move to absolute target position.

        Splits the 6-joint target across boards and dispatches G commands.

        Args:
            target: List of 6 absolute target positions.
            callback: Optional completion callback.

        Returns:
            Command sequence ID (of the primary board command).
        """
        if len(target) < NUM_JOINTS:
            target = target + [0] * (NUM_JOINTS - len(target))

        # Update pending target
        offset = 0
        cmd_id = 0
        for name, board in self.boards.items():
            board_target = target[offset: offset + board.num_joints]
            board.set_pending_target(board_target)

            # Build G command
            positions_str = " ".join(str(t) for t in board_target)
            payload = f"G {positions_str} {self.step_delay}"

            # Calculate timeout from max delta
            current = board.position
            max_delta = max(
                abs(board_target[i] - current[i])
                for i in range(board.num_joints)
            )
            move_duration = (max_delta * self.step_delay * 2) / 1_000_000.0
            timeout = move_duration + 10.0

            cmd = Command(
                payload=payload, timeout=timeout, callback=callback
            )
            cmd_id = cmd.id
            board.submit(cmd)
            offset += board.num_joints

        self._has_pending = True
        return cmd_id

    def jog(
        self,
        joint: int,
        delta: int,
        callback: Optional[Callable[[int, Optional[str], CommandStatus], None]] = None,
    ) -> int:
        """Jog a single joint by delta steps from pending_target.

        Calculates absolute target from pending_target (not current
        position) to support jog stacking.

        Args:
            joint: Joint index (0-5).
            delta: Steps to move (positive or negative).
            callback: Optional completion callback.

        Returns:
            Command sequence ID.
        """
        # Get current pending target across all boards
        full_target = [0] * NUM_JOINTS
        offset = 0
        for name, board in self.boards.items():
            for i in range(board.num_joints):
                if offset + i < NUM_JOINTS:
                    full_target[offset + i] = board.pending_target[i]
            offset += board.num_joints

        # Apply delta
        if 0 <= joint < NUM_JOINTS:
            full_target[joint] += delta

        return self.move_absolute(full_target, callback=callback)

    def set_speed(self, delay_us: int) -> None:
        """Set step delay for subsequent moves.

        Args:
            delay_us: Step delay in microseconds, clamped to min/max.
        """
        self.step_delay = max(self.min_delay, min(self.max_delay, delay_us))
        logger.info("Speed set to %d us", self.step_delay)

    def set_home(self) -> None:
        """Reset firmware position counters to zero on all boards."""
        for name, board in self.boards.items():
            if board.connected:
                cmd = Command(payload="R", timeout=2.0)
                board.submit(cmd)
                board.set_pending_target([0] * board.num_joints)
                # Also reset internal position tracking immediately
                board._position = [0] * board.num_joints
                board._position_certain = True
        self._has_pending = False
        logger.info("Home position set")

    def go_home(
        self,
        callback: Optional[Callable[[int, Optional[str], CommandStatus], None]] = None,
    ) -> int:
        """Move all joints to position [0, 0, 0, 0, 0, 0].

        Args:
            callback: Optional completion callback.

        Returns:
            Command sequence ID.
        """
        return self.move_absolute([0] * NUM_JOINTS, callback=callback)

    def halt(self, source: str, joint: Optional[int] = None) -> None:
        """Unified halt handler. Called by serial thread on any halt.

        Broadcasts halt message to all connected WebSocket clients.

        Args:
            source: 'user' or 'collision'.
            joint: Affected joint index, or None for user E-STOP.
        """
        self._has_pending = False
        self._enabled = False

        if source == "collision" and joint is not None:
            joint_name = JOINT_NAMES[joint] if joint < len(JOINT_NAMES) else f"Joint {joint}"
            message = f"Collision detected on Joint {joint} ({joint_name})"
        else:
            message = "E-STOP activated"

        self._broadcast({
            "type": "halt",
            "source": source,
            "joint": joint,
            "position": self.get_state()["position"],
            "message": message,
        })
        logger.warning("HALT: %s", message)

    def _on_board_halt(
        self, board_name: str, source: str, joint: Optional[int]
    ) -> None:
        """Callback from a board's serial thread on halt detection.

        Translates board-local joint index to global joint index.

        Args:
            board_name: Name of the board that triggered halt.
            source: 'user' or 'collision'.
            joint: Board-local joint index, or None.
        """
        # Translate to global joint index
        global_joint = joint
        if joint is not None:
            offset = 0
            for name, board in self.boards.items():
                if name == board_name:
                    global_joint = offset + joint
                    break
                offset += board.num_joints

        self.halt(source=source, joint=global_joint)

    def _broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast a message to all connected clients.

        Args:
            message: Dict to broadcast as JSON.
        """
        if self._broadcast_fn is not None:
            self._broadcast_fn(message)
