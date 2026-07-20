"""
Unit tests for armold_controller core components.

Tests cover: queue ordering, ACK pairing, E-STOP interrupt, and jog stacking.
Uses real implementations (no mocking per project standards).
"""

import queue
import sys
import time
from typing import Optional

sys.path.insert(0, ".")

from armold_controller.command import Command, CommandStatus, _next_sequence_id
from armold_controller.motion_manager import MotionManager
from armold_controller.serial_board import SerialBoard


def test_command_sequence_ids() -> None:
    """Verify commands get unique monotonically increasing IDs."""
    cmd1 = Command(payload="E1")
    cmd2 = Command(payload="G 100 0 0 0 30")
    cmd3 = Command(payload="S")

    assert cmd2.id > cmd1.id, f"cmd2.id ({cmd2.id}) should be > cmd1.id ({cmd1.id})"
    assert cmd3.id > cmd2.id, f"cmd3.id ({cmd3.id}) should be > cmd2.id ({cmd2.id})"
    print("PASS: test_command_sequence_ids")


def test_command_lifecycle() -> None:
    """Verify command status transitions from queued -> sent -> ok."""
    cmd = Command(payload="E1", timeout=5.0)

    assert cmd.status == CommandStatus.QUEUED
    assert cmd.sent_at is None
    assert not cmd.is_terminal

    cmd.mark_sent()
    assert cmd.status == CommandStatus.SENT
    assert cmd.sent_at is not None
    assert not cmd.is_terminal

    cmd.complete("OK E1", CommandStatus.OK)
    assert cmd.status == CommandStatus.OK
    assert cmd.completed_at is not None
    assert cmd.response == "OK E1"
    assert cmd.is_terminal
    print("PASS: test_command_lifecycle")


def test_command_callback() -> None:
    """Verify completion callback is invoked with correct args."""
    results: list = []

    def on_complete(cmd_id: int, response: Optional[str], status: CommandStatus) -> None:
        results.append((cmd_id, response, status))

    cmd = Command(payload="G 100 0 0 0 30", callback=on_complete)
    cmd.complete("OK G 100 0 0 0", CommandStatus.OK)

    assert len(results) == 1
    assert results[0][0] == cmd.id
    assert results[0][1] == "OK G 100 0 0 0"
    assert results[0][2] == CommandStatus.OK
    print("PASS: test_command_callback")


def test_queue_ordering() -> None:
    """Verify commands are processed in FIFO order."""
    q: queue.Queue[Command] = queue.Queue()
    cmds = [Command(payload=f"M{i} 100 0 80") for i in range(5)]

    for cmd in cmds:
        q.put(cmd)

    extracted = []
    while not q.empty():
        extracted.append(q.get_nowait())

    for i, cmd in enumerate(extracted):
        assert cmd.payload == f"M{i} 100 0 80", (
            f"Expected M{i}, got {cmd.payload}"
        )
    print("PASS: test_queue_ordering")


def test_estop_clears_queue() -> None:
    """Verify E-STOP flushes all queued commands with ESTOP status."""
    board = SerialBoard(name="test", port="/dev/null", num_joints=4)

    # Manually push commands into the queue (don't start the thread)
    cmds = [Command(payload=f"G {i} 0 0 0 30") for i in range(5)]
    for cmd in cmds:
        board._command_queue.put(cmd)

    assert board._command_queue.qsize() == 5

    # Trigger E-STOP (estop() calls _flush_queue)
    board._flush_queue(CommandStatus.ESTOP)

    assert board._command_queue.qsize() == 0
    for cmd in cmds:
        assert cmd.status == CommandStatus.ESTOP
        assert cmd.is_terminal
    print("PASS: test_estop_clears_queue")


def test_estop_flag() -> None:
    """Verify E-STOP sets the flag correctly."""
    board = SerialBoard(name="test", port="/dev/null", num_joints=4)
    assert not board._estop_requested

    board.estop()
    assert board._estop_requested
    print("PASS: test_estop_flag")


def test_jog_stacking() -> None:
    """Verify jog stacking uses pending_target, not current position."""
    # Create a board with known position
    board = SerialBoard(name="einsy", port="/dev/null", num_joints=4)
    board._position = [0, 0, 0, 0]
    board._pending_target = [0, 0, 0, 0]
    board._connected = True
    board._enabled = True

    # Create motion manager
    mm = MotionManager(boards={"einsy": board}, step_delay=30)

    # First jog: joint 0, +1000 steps
    # (We can't actually send since serial is /dev/null, but we can
    # verify the pending_target is updated correctly)
    mm.jog(joint=0, delta=1000)

    # After first jog, pending_target should be [1000, 0, 0, 0, ...]
    assert board.pending_target[0] == 1000, (
        f"Expected 1000, got {board.pending_target[0]}"
    )

    # Second jog: joint 0, +500 steps (should stack on 1000)
    mm.jog(joint=0, delta=500)
    assert board.pending_target[0] == 1500, (
        f"Expected 1500, got {board.pending_target[0]}"
    )

    # Third jog: joint 1, +200 steps
    mm.jog(joint=1, delta=200)
    assert board.pending_target[1] == 200, (
        f"Expected 200, got {board.pending_target[1]}"
    )
    # Joint 0 still stacked
    assert board.pending_target[0] == 1500, (
        f"Expected 1500, got {board.pending_target[0]}"
    )
    print("PASS: test_jog_stacking")


def test_jog_negative() -> None:
    """Verify jog works with negative deltas."""
    board = SerialBoard(name="einsy", port="/dev/null", num_joints=4)
    board._position = [5000, 0, 0, 0]
    board._pending_target = [5000, 0, 0, 0]
    board._connected = True
    board._enabled = True

    mm = MotionManager(boards={"einsy": board}, step_delay=30)

    mm.jog(joint=0, delta=-2000)
    assert board.pending_target[0] == 3000, (
        f"Expected 3000, got {board.pending_target[0]}"
    )
    print("PASS: test_jog_negative")


def test_speed_profiles() -> None:
    """Verify speed clamping works correctly."""
    board = SerialBoard(name="einsy", port="/dev/null", num_joints=4)
    mm = MotionManager(
        boards={"einsy": board}, step_delay=80, min_delay=30, max_delay=5000
    )

    assert mm.step_delay == 80

    mm.set_speed(30)
    assert mm.step_delay == 30

    mm.set_speed(10)  # Below min
    assert mm.step_delay == 30

    mm.set_speed(10000)  # Above max
    assert mm.step_delay == 5000

    mm.set_speed(200)
    assert mm.step_delay == 200
    print("PASS: test_speed_profiles")


def test_position_parse() -> None:
    """Verify position parsing from firmware response."""
    board = SerialBoard(name="einsy", port="/dev/null", num_joints=4)
    board._position = [0, 0, 0, 0]

    board._parse_position_response("OK G 20757 -1000 500 0")
    assert board._position == [20757, -1000, 500, 0]
    assert board._pending_target == [20757, -1000, 500, 0]
    print("PASS: test_position_parse")


def test_state_parse() -> None:
    """Verify state parsing from firmware S response."""
    board = SerialBoard(name="einsy", port="/dev/null", num_joints=4)
    board._position = [0, 0, 0, 0]

    board._parse_state_response("S 1 100 200 300 400")
    assert board._enabled is True
    assert board._position == [100, 200, 300, 400]
    assert board._pending_target == [100, 200, 300, 400]
    print("PASS: test_state_parse")


def test_motion_manager_state() -> None:
    """Verify MotionManager assembles state across boards."""
    einsy = SerialBoard(name="einsy", port="/dev/null", num_joints=4)
    einsy._position = [100, 200, 300, 400]
    einsy._pending_target = [100, 200, 300, 400]
    einsy._connected = True
    einsy._position_certain = True

    ramps = SerialBoard(name="ramps", port="/dev/null", num_joints=2)
    ramps._position = [500, 600]
    ramps._pending_target = [500, 600]
    ramps._connected = True
    ramps._position_certain = True

    mm = MotionManager(boards={"einsy": einsy, "ramps": ramps})
    mm._enabled = True

    state = mm.get_state()
    assert state["position"] == [100, 200, 300, 400, 500, 600]
    assert state["pending_target"] == [100, 200, 300, 400, 500, 600]
    assert state["enabled"] is True
    assert state["connected"] == {"einsy": True, "ramps": True}
    assert state["position_certain"] is True
    print("PASS: test_motion_manager_state")


def test_halt_callback() -> None:
    """Verify halt callback triggers on board halt."""
    halt_events: list[tuple[str, int | None]] = []

    board = SerialBoard(name="einsy", port="/dev/null", num_joints=4)
    board._connected = True

    mm = MotionManager(boards={"einsy": board})
    mm._enabled = True

    # Capture broadcasts
    broadcasts: list[dict] = []
    mm.set_broadcast(lambda msg: broadcasts.append(msg))

    # Simulate collision on joint 1
    board._handle_halt(source="collision", joint=1)

    assert not mm._enabled
    assert len(broadcasts) == 1
    assert broadcasts[0]["type"] == "halt"
    assert broadcasts[0]["source"] == "collision"
    assert broadcasts[0]["joint"] == 1
    assert "Shoulder" in broadcasts[0]["message"]
    print("PASS: test_halt_callback")


def main() -> None:
    """Run all tests."""
    tests = [
        test_command_sequence_ids,
        test_command_lifecycle,
        test_command_callback,
        test_queue_ordering,
        test_estop_clears_queue,
        test_estop_flag,
        test_jog_stacking,
        test_jog_negative,
        test_speed_profiles,
        test_position_parse,
        test_state_parse,
        test_motion_manager_state,
        test_halt_callback,
    ]

    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test_fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test_fn.__name__}: {e}")
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
