"""
Unit tests for KlipperBoard soft-limit clamping.

Klipper's ``manual_stepper`` does not enforce position limits, so
``armold_controller`` clamps every target in software. These tests exercise
the real clamping implementation directly (no mocking, no network): the
``KlipperBoard`` constructor does not open any connection, and
``clamp_target`` is a pure synchronous function.

Run standalone: ``python -m armold_controller.tests.test_soft_limits``
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".")

from armold_controller.klipper_board import (
    DEFAULT_SOFT_LIMITS,
    NUM_JOINTS,
    JointLimit,
    KlipperBoard,
)


def test_default_limits_wellformed() -> None:
    """Verify DEFAULT_SOFT_LIMITS has one valid entry per joint."""
    assert len(DEFAULT_SOFT_LIMITS) == NUM_JOINTS
    for i, limit in enumerate(DEFAULT_SOFT_LIMITS):
        assert limit.minimum < limit.maximum, f"joint {i} min !< max"
    # Rail (index 0) is 0..406 mm of usable travel.
    assert DEFAULT_SOFT_LIMITS[0] == JointLimit(0.0, 406.0, "mm")
    print("PASS: test_default_limits_wellformed")


def test_clamp_within_limits_unchanged() -> None:
    """A target inside the range is returned unchanged and not flagged."""
    board = KlipperBoard()
    clamped, was_clamped = board.clamp_target(1, 90.0)  # J0 base, +/-180
    assert clamped == 90.0
    assert was_clamped is False
    print("PASS: test_clamp_within_limits_unchanged")


def test_clamp_above_maximum() -> None:
    """A target above the maximum is clamped down and flagged."""
    board = KlipperBoard()
    clamped, was_clamped = board.clamp_target(2, 200.0)  # J1 shoulder, +/-90
    assert clamped == 90.0
    assert was_clamped is True
    print("PASS: test_clamp_above_maximum")


def test_clamp_below_minimum() -> None:
    """A target below the minimum is clamped up and flagged."""
    board = KlipperBoard()
    clamped, was_clamped = board.clamp_target(4, -500.0)  # J3 pitch, +/-120
    assert clamped == -120.0
    assert was_clamped is True
    print("PASS: test_clamp_below_minimum")


def test_clamp_rail_range() -> None:
    """Rail clamps to 0..406 mm (16 in usable travel)."""
    board = KlipperBoard()
    assert board.clamp_target(0, -5.0) == (0.0, True)
    assert board.clamp_target(0, 500.0) == (406.0, True)
    assert board.clamp_target(0, 200.0) == (200.0, False)
    print("PASS: test_clamp_rail_range")


def test_clamp_all_joint_boundaries() -> None:
    """Exact boundary values are allowed (not flagged) for every joint."""
    board = KlipperBoard()
    for joint, limit in enumerate(DEFAULT_SOFT_LIMITS):
        lo, lo_flag = board.clamp_target(joint, limit.minimum)
        hi, hi_flag = board.clamp_target(joint, limit.maximum)
        assert lo == limit.minimum and lo_flag is False, f"joint {joint} min"
        assert hi == limit.maximum and hi_flag is False, f"joint {joint} max"
    print("PASS: test_clamp_all_joint_boundaries")


def test_custom_soft_limits_accepted() -> None:
    """Custom soft limits override the defaults."""
    custom = [JointLimit(-1.0, 1.0) for _ in range(NUM_JOINTS)]
    board = KlipperBoard(soft_limits=custom)
    assert board.clamp_target(3, 5.0) == (1.0, True)
    assert board.clamp_target(3, 0.5) == (0.5, False)
    print("PASS: test_custom_soft_limits_accepted")


def test_wrong_length_soft_limits_rejected() -> None:
    """Providing the wrong number of limits raises ValueError."""
    try:
        KlipperBoard(soft_limits=[JointLimit(-1.0, 1.0)])
    except ValueError:
        print("PASS: test_wrong_length_soft_limits_rejected")
        return
    raise AssertionError("expected ValueError for wrong-length soft_limits")


def main() -> None:
    """Run all soft-limit tests and report a summary."""
    tests = [
        test_default_limits_wellformed,
        test_clamp_within_limits_unchanged,
        test_clamp_above_maximum,
        test_clamp_below_minimum,
        test_clamp_rail_range,
        test_clamp_all_joint_boundaries,
        test_custom_soft_limits_accepted,
        test_wrong_length_soft_limits_rejected,
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
        except Exception as e:  # noqa: BLE001 - test harness reports all errors
            print(f"ERROR: {test_fn.__name__}: {e}")
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
