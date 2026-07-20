"""
Command object for the motion control queue.

Each command represents a single serial instruction to be sent to a board,
with sequence ID for ACK pairing, timeout, and callback for completion
notification.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class CommandStatus(Enum):
    """Lifecycle status of a queued command.

    Transitions: queued -> sent -> ok | error | timeout | estop | stall
    """

    QUEUED = "queued"
    SENT = "sent"
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    ESTOP = "estop"
    STALL = "stall"


# Type alias for command completion callbacks
CompletionCallback = Callable[[int, Optional[str], CommandStatus], None]

# Module-level sequence counter
_sequence_counter: int = 0


def _next_sequence_id() -> int:
    """Generate the next unique sequence ID.

    Returns:
        Monotonically increasing integer ID.
    """
    global _sequence_counter
    _sequence_counter += 1
    return _sequence_counter


@dataclass
class Command:
    """A serial command queued for execution on a board.

    Attributes:
        payload: Raw serial string to send (e.g., 'G 20757 0 0 0 30').
        timeout: Max seconds to wait for response.
        callback: Called with (id, response, status) on completion.
        id: Unique sequence number for ACK pairing.
        status: Current lifecycle status.
        created_at: Timestamp when command was created.
        sent_at: Timestamp when command was sent to serial port.
        completed_at: Timestamp when command received response or timed out.
        response: Raw response string from firmware.
    """

    payload: str
    timeout: float = 10.0
    callback: Optional[CompletionCallback] = None
    id: int = field(default_factory=_next_sequence_id)
    status: CommandStatus = field(default=CommandStatus.QUEUED)
    created_at: float = field(default_factory=time.time)
    sent_at: Optional[float] = None
    completed_at: Optional[float] = None
    response: Optional[str] = None

    def complete(self, response: Optional[str], status: CommandStatus) -> None:
        """Mark this command as completed with a given status.

        Invokes the callback if one was provided.

        Args:
            response: Raw response string from firmware, or None.
            status: Final status for this command.
        """
        self.response = response
        self.status = status
        self.completed_at = time.time()
        if self.callback is not None:
            self.callback(self.id, response, status)

    def mark_sent(self) -> None:
        """Mark this command as sent to the serial port."""
        self.status = CommandStatus.SENT
        self.sent_at = time.time()

    @property
    def elapsed(self) -> float:
        """Time elapsed since command was sent, or 0 if not yet sent.

        Returns:
            Seconds since send, or 0.0.
        """
        if self.sent_at is None:
            return 0.0
        return time.time() - self.sent_at

    @property
    def is_terminal(self) -> bool:
        """Whether this command has reached a terminal (final) status.

        Returns:
            True if status is ok, error, timeout, estop, or stall.
        """
        return self.status in (
            CommandStatus.OK,
            CommandStatus.ERROR,
            CommandStatus.TIMEOUT,
            CommandStatus.ESTOP,
            CommandStatus.STALL,
        )
