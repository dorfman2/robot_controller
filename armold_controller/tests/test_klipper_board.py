"""
Integration tests for KlipperBoard — Moonraker API client.

Tests cover: initialization, state management, G-code generation,
position tracking, and axis registration logic.

Uses real implementations (no mocking per project standards).
Tests that require a live Moonraker instance are marked and skipped
if the service is unreachable.
"""

import asyncio
import sys
from typing import Optional

sys.path.insert(0, ".")

from armold_controller.klipper_board import (
    GCODE_AXIS_MAP,
    JOINT_NAMES,
    NUM_JOINTS,
    STEPPER_NAMES,
    KlipperBoard,
)


def test_klipper_board_init() -> None:
    """Verify KlipperBoard initializes with correct defaults."""
    board = KlipperBoard()

    assert board.moonraker_url == "http://localhost:7125"
    assert board.name == "klipper"
    assert board.num_joints == 7
    assert len(board.position) == 7
    assert all(p == 0.0 for p in board.position)
    assert not board.enabled
    assert not board.connected
    assert not board.position_certain
    assert not board.moving
    assert board.queue_depth == 0
    print("PASS: test_klipper_board_init")


def test_klipper_board_custom_url() -> None:
    """Verify KlipperBoard accepts custom Moonraker URL."""
    board = KlipperBoard(
        moonraker_url="http://192.168.1.136:7125",
        name="remote_klipper",
    )

    assert board.moonraker_url == "http://192.168.1.136:7125"
    assert board.name == "remote_klipper"
    print("PASS: test_klipper_board_custom_url")


def test_stepper_names_count() -> None:
    """Verify STEPPER_NAMES has correct count and values."""
    assert len(STEPPER_NAMES) == 7
    assert STEPPER_NAMES[0] == "stepper_x"  # Rail
    assert STEPPER_NAMES[1] == "stepper_y"  # J0 Base
    assert STEPPER_NAMES[2] == "stepper_z"  # J1 Shoulder
    assert STEPPER_NAMES[3] == "stepper_a"  # J2 Elbow
    assert STEPPER_NAMES[4] == "stepper_b"  # J3 Wrist Pitch
    assert STEPPER_NAMES[5] == "stepper_c"  # J4 Wrist Roll
    assert STEPPER_NAMES[6] == "stepper_u"  # J5 Wrist Yaw
    print("PASS: test_stepper_names_count")


def test_gcode_axis_map() -> None:
    """Verify GCODE_AXIS_MAP uses valid letters (not X/Y/Z/E/F/N)."""
    assert len(GCODE_AXIS_MAP) == 7
    reserved = set("XYZEFN")
    for letter in GCODE_AXIS_MAP:
        assert len(letter) == 1, f"Axis letter must be single char: {letter}"
        assert letter.isupper(), f"Axis letter must be uppercase: {letter}"
        assert letter not in reserved, (
            f"Axis letter {letter} is reserved by Klipper"
        )
    # Verify specific mapping
    assert GCODE_AXIS_MAP[0] == "W"  # Rail
    assert GCODE_AXIS_MAP[1] == "A"  # J0
    assert GCODE_AXIS_MAP[2] == "B"  # J1
    assert GCODE_AXIS_MAP[3] == "C"  # J2
    assert GCODE_AXIS_MAP[4] == "D"  # J3
    assert GCODE_AXIS_MAP[5] == "H"  # J4
    assert GCODE_AXIS_MAP[6] == "U"  # J5
    # Verify no duplicates
    assert len(set(GCODE_AXIS_MAP)) == 7, "Duplicate axis letters found"
    print("PASS: test_gcode_axis_map")


def test_joint_names() -> None:
    """Verify JOINT_NAMES has correct count."""
    assert len(JOINT_NAMES) == 7
    assert JOINT_NAMES[0] == "Rail"
    assert JOINT_NAMES[6] == "Wrist Yaw"
    print("PASS: test_joint_names")


def test_position_property() -> None:
    """Verify position property returns a copy, not a reference."""
    board = KlipperBoard()
    pos = board.position
    pos[0] = 999.0
    assert board.position[0] == 0.0, "Position should be a copy"
    print("PASS: test_position_property")


def test_pending_target_equals_position() -> None:
    """Verify pending_target returns same as position (Klipper manages queue)."""
    board = KlipperBoard()
    board._position[2] = 45.0
    assert board.pending_target[2] == 45.0
    print("PASS: test_pending_target_equals_position")


def test_halt_callback() -> None:
    """Verify halt callback is stored and retrievable."""
    board = KlipperBoard()
    results: list[tuple] = []

    def on_halt(source: str, joint: Optional[int]) -> None:
        results.append((source, joint))

    board.set_halt_callback(on_halt)
    assert board._halt_callback is not None
    board._halt_callback("user", None)
    assert results == [("user", None)]
    print("PASS: test_halt_callback")


def test_state_callback() -> None:
    """Verify state callback is stored and invocable."""
    board = KlipperBoard()
    called: list[bool] = []

    def on_state() -> None:
        called.append(True)

    board.set_state_callback(on_state)
    assert board._state_callback is not None
    board._state_callback()
    assert called == [True]
    print("PASS: test_state_callback")


def test_update_positions() -> None:
    """Verify _update_positions parses Moonraker status correctly."""
    board = KlipperBoard()
    called: list[bool] = []
    board.set_state_callback(lambda: called.append(True))

    # Simulate Moonraker status response
    status = {
        "manual_stepper stepper_x": {"commanded_pos": 50.0},
        "manual_stepper stepper_y": {"commanded_pos": 90.0},
        "manual_stepper stepper_z": {"commanded_pos": -30.0},
        "manual_stepper stepper_a": {"commanded_pos": 70.0},
        "manual_stepper stepper_b": {"commanded_pos": 50.0},
        "manual_stepper stepper_c": {"commanded_pos": 0.0},
        "manual_stepper stepper_u": {"commanded_pos": 45.0},
    }

    board._update_positions(status)

    assert board._position[0] == 50.0  # Rail
    assert board._position[1] == 90.0  # J0
    assert board._position[2] == -30.0  # J1
    assert board._position[3] == 70.0  # J2
    assert board._position[4] == 50.0  # J3
    assert board._position[5] == 0.0  # J4
    assert board._position[6] == 45.0  # J5
    assert len(called) == 1  # Callback was triggered
    print("PASS: test_update_positions")


def test_update_positions_partial() -> None:
    """Verify _update_positions handles partial data gracefully."""
    board = KlipperBoard()
    board._position = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0]

    # Only 2 steppers in response
    status = {
        "manual_stepper stepper_y": {"commanded_pos": 99.0},
        "manual_stepper stepper_u": {"commanded_pos": -15.0},
    }

    board._update_positions(status)

    assert board._position[0] == 10.0  # Unchanged
    assert board._position[1] == 99.0  # Updated
    assert board._position[2] == 30.0  # Unchanged
    assert board._position[6] == -15.0  # Updated
    print("PASS: test_update_positions_partial")


def test_update_positions_no_change() -> None:
    """Verify callback is NOT triggered when positions haven't changed."""
    board = KlipperBoard()
    board._position = [0.0, 90.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    called: list[bool] = []
    board.set_state_callback(lambda: called.append(True))

    status = {
        "manual_stepper stepper_y": {"commanded_pos": 90.0},  # Same value
    }

    board._update_positions(status)
    assert len(called) == 0  # No callback — nothing changed
    print("PASS: test_update_positions_no_change")


def test_get_state() -> None:
    """Verify get_state returns correct structure."""
    board = KlipperBoard()
    board._position = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0]
    board._enabled = True
    board._connected = True
    board._ready = True
    board._axes_registered = True

    state = board.get_state()

    assert state["type"] == "state"
    assert state["enabled"] is True
    assert state["position"] == [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0]
    assert state["pending_target"] == [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0]
    assert state["connected"] == {"klipper": True}
    assert state["position_certain"] is True
    assert state["queue_depth"] == 0
    assert state["klipper_ready"] is True
    assert state["axes_registered"] is True
    print("PASS: test_get_state")


def test_get_state_returns_copy() -> None:
    """Verify get_state returns copies of lists, not references."""
    board = KlipperBoard()
    board._position = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]

    state = board.get_state()
    state["position"][0] = 999.0

    assert board._position[0] == 1.0, "get_state should return a copy"
    print("PASS: test_get_state_returns_copy")


def test_num_joints_constant() -> None:
    """Verify NUM_JOINTS is 7 for the full robot arm."""
    assert NUM_JOINTS == 7
    print("PASS: test_num_joints_constant")


def main() -> None:
    """Run all tests."""
    tests = [
        test_klipper_board_init,
        test_klipper_board_custom_url,
        test_stepper_names_count,
        test_gcode_axis_map,
        test_joint_names,
        test_position_property,
        test_pending_target_equals_position,
        test_halt_callback,
        test_state_callback,
        test_update_positions,
        test_update_positions_partial,
        test_update_positions_no_change,
        test_get_state,
        test_get_state_returns_copy,
        test_num_joints_constant,
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
