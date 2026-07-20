"""
Unit tests for the TrajectoryPlanner S-curve computation and lookahead queue.

Tests cover: profile generation, segment counts, step conservation,
short moves, multi-joint coordination, junction velocity optimization,
and interval validity.
"""

import sys

sys.path.insert(0, ".")

from armold_controller.trajectory_planner import (
    CurveType,
    JointConfig,
    Move,
    MoveQueue,
    SCurveProfile,
    Segment,
    TrajectoryPlanner,
)


def test_single_joint_full_profile() -> None:
    """Verify 7-segment profile for a long single-joint move."""
    planner = TrajectoryPlanner(num_joints=4)
    segments = planner.plan_move([0, 0, 0, 0], [20757, 0, 0, 0])

    # Should produce 7 segments (full S-curve)
    assert len(segments) == 7, f"Expected 7 segments, got {len(segments)}"

    # All segments on joint 0
    for s in segments:
        assert s.joint == 0
        assert s.direction is True

    # Total steps must equal requested distance
    total_steps = sum(s.step_count for s in segments)
    assert total_steps == 20757, f"Expected 20757 steps, got {total_steps}"

    print("PASS: test_single_joint_full_profile")


def test_step_conservation() -> None:
    """Verify step counts are exactly conserved for various distances."""
    planner = TrajectoryPlanner(num_joints=4)

    test_distances = [10, 50, 100, 500, 1000, 5000, 20757, 83028]
    for dist in test_distances:
        segments = planner.plan_move([0, 0, 0, 0], [dist, 0, 0, 0])
        total = sum(s.step_count for s in segments)
        assert total == dist, (
            f"Distance {dist}: expected {dist} steps, got {total}"
        )

    print("PASS: test_step_conservation")


def test_short_move_reduced_segments() -> None:
    """Verify short moves produce fewer segments (3 or 5)."""
    planner = TrajectoryPlanner(num_joints=4)

    # Very short move (100 steps) — should reduce to fewer segments
    segments = planner.plan_move([0, 0, 0, 0], [100, 0, 0, 0])
    non_zero = [s for s in segments if s.step_count > 0]
    assert len(non_zero) <= 7, f"Too many segments: {len(non_zero)}"
    assert len(non_zero) >= 2, f"Need at least 2 segments, got {len(non_zero)}"

    total = sum(s.step_count for s in segments)
    assert total == 100, f"Expected 100 steps, got {total}"

    print("PASS: test_short_move_reduced_segments")


def test_negative_direction() -> None:
    """Verify negative deltas produce reverse direction segments."""
    planner = TrajectoryPlanner(num_joints=4)
    segments = planner.plan_move([10000, 0, 0, 0], [5000, 0, 0, 0])

    for s in segments:
        assert s.direction is False, f"Expected reverse direction, got forward"

    total = sum(s.step_count for s in segments)
    assert total == 5000, f"Expected 5000 steps, got {total}"

    print("PASS: test_negative_direction")


def test_multi_joint_coordination() -> None:
    """Verify multi-joint moves produce segments for all moving joints."""
    planner = TrajectoryPlanner(num_joints=4)
    segments = planner.plan_move([0, 0, 0, 0], [20757, 5000, -10000, 0])

    # Check each moving joint has segments
    joints_with_segments = set(s.joint for s in segments)
    assert 0 in joints_with_segments, "Joint 0 should have segments"
    assert 1 in joints_with_segments, "Joint 1 should have segments"
    assert 2 in joints_with_segments, "Joint 2 should have segments"
    assert 3 not in joints_with_segments, "Joint 3 should NOT have segments"

    # Verify step counts per joint
    for j, expected in [(0, 20757), (1, 5000), (2, 10000)]:
        j_steps = sum(s.step_count for s in segments if s.joint == j)
        assert j_steps == expected, (
            f"Joint {j}: expected {expected} steps, got {j_steps}"
        )

    # Joint 2 should be reverse direction
    j2_segs = [s for s in segments if s.joint == 2]
    for s in j2_segs:
        assert s.direction is False

    print("PASS: test_multi_joint_coordination")


def test_interval_validity() -> None:
    """Verify all segment intervals are within valid MCU range."""
    planner = TrajectoryPlanner(num_joints=4)
    segments = planner.plan_move([0, 0, 0, 0], [20757, 0, 0, 0])

    for s in segments:
        assert 20 <= s.start_interval <= 5000, (
            f"start_interval {s.start_interval} out of range [20, 5000]"
        )
        assert 20 <= s.end_interval <= 5000, (
            f"end_interval {s.end_interval} out of range [20, 5000]"
        )

    print("PASS: test_interval_validity")


def test_cruise_segment_constant_speed() -> None:
    """Verify cruise segment has equal start and end intervals."""
    planner = TrajectoryPlanner(num_joints=4)
    segments = planner.plan_move([0, 0, 0, 0], [20757, 0, 0, 0])

    # For a 7-segment profile, segment index 3 is cruise
    if len(segments) == 7:
        cruise = segments[3]
        assert cruise.start_interval == cruise.end_interval, (
            f"Cruise segment intervals differ: "
            f"{cruise.start_interval} vs {cruise.end_interval}"
        )

    print("PASS: test_cruise_segment_constant_speed")


def test_curve_type_sinusoidal() -> None:
    """Verify segments use sinusoidal curve type."""
    planner = TrajectoryPlanner(num_joints=4)
    segments = planner.plan_move([0, 0, 0, 0], [20757, 0, 0, 0])

    for s in segments:
        assert s.curve_type == CurveType.SINUSOIDAL, (
            f"Expected SINUSOIDAL, got {s.curve_type}"
        )

    print("PASS: test_curve_type_sinusoidal")


def test_zero_move_no_segments() -> None:
    """Verify no segments are generated for zero-distance moves."""
    planner = TrajectoryPlanner(num_joints=4)
    segments = planner.plan_move([100, 200, 300, 400], [100, 200, 300, 400])

    assert len(segments) == 0, f"Expected 0 segments, got {len(segments)}"

    print("PASS: test_zero_move_no_segments")


def test_move_queue_basic() -> None:
    """Verify MoveQueue buffers moves and returns ready moves."""
    queue = MoveQueue(max_depth=10)

    move1 = Move(target=[1000, 0, 0, 0], delta=[1000, 0, 0, 0],
                 entry_velocity=33333.0, exit_velocity=33333.0)
    move2 = Move(target=[2000, 0, 0, 0], delta=[1000, 0, 0, 0],
                 entry_velocity=33333.0, exit_velocity=33333.0)

    # First move should be buffered (no ready move yet)
    result = queue.add_move(move1)
    assert result is None, "First move should be buffered"
    assert queue.depth == 1

    # Second move should release the first
    result = queue.add_move(move2)
    assert result is not None, "Second move should release first"
    assert result.target == [1000, 0, 0, 0]
    assert queue.depth == 1

    print("PASS: test_move_queue_basic")


def test_move_queue_direction_reversal() -> None:
    """Verify junction velocity is zero when direction reverses."""
    queue = MoveQueue(max_depth=10)

    # Move forward
    move1 = Move(target=[1000, 0, 0, 0], delta=[1000, 0, 0, 0],
                 entry_velocity=33333.0, exit_velocity=33333.0)
    # Move backward (direction reversal on joint 0)
    move2 = Move(target=[500, 0, 0, 0], delta=[-500, 0, 0, 0],
                 entry_velocity=33333.0, exit_velocity=33333.0)

    queue.add_move(move1)
    ready = queue.add_move(move2)

    # On direction reversal, exit velocity of move1 should be 0
    assert ready is not None
    assert ready.exit_velocity == 0.0, (
        f"Expected 0.0 exit velocity on reversal, got {ready.exit_velocity}"
    )

    print("PASS: test_move_queue_direction_reversal")


def test_move_queue_same_direction() -> None:
    """Verify junction velocity is maintained when direction is same."""
    queue = MoveQueue(max_depth=10)

    # Both moves in same direction
    move1 = Move(target=[1000, 0, 0, 0], delta=[1000, 0, 0, 0],
                 entry_velocity=33333.0, exit_velocity=33333.0)
    move2 = Move(target=[2000, 0, 0, 0], delta=[1000, 0, 0, 0],
                 entry_velocity=33333.0, exit_velocity=33333.0)

    queue.add_move(move1)
    ready = queue.add_move(move2)

    assert ready is not None
    # Same direction, same axis — junction velocity should be > 0
    assert ready.exit_velocity > 0, (
        f"Expected positive junction velocity, got {ready.exit_velocity}"
    )

    print("PASS: test_move_queue_same_direction")


def test_move_queue_flush() -> None:
    """Verify flush returns all remaining moves with exit_velocity=0."""
    queue = MoveQueue(max_depth=10)

    move1 = Move(target=[1000, 0, 0, 0], delta=[1000, 0, 0, 0],
                 entry_velocity=33333.0, exit_velocity=33333.0)

    queue.add_move(move1)
    remaining = queue.flush()

    assert len(remaining) == 1
    assert remaining[0].exit_velocity == 0.0, (
        f"Last move after flush should have exit_velocity=0, "
        f"got {remaining[0].exit_velocity}"
    )
    assert queue.depth == 0

    print("PASS: test_move_queue_flush")


def test_velocity_to_interval() -> None:
    """Verify velocity-to-interval conversion."""
    # 33333 steps/sec = 30µs interval
    interval = TrajectoryPlanner._velocity_to_interval(33333.0)
    assert interval == 30, f"Expected 30µs, got {interval}µs"

    # 0 velocity = max interval
    interval = TrajectoryPlanner._velocity_to_interval(0.0)
    assert interval == 5000, f"Expected 5000µs, got {interval}µs"

    # Very high velocity = min interval
    interval = TrajectoryPlanner._velocity_to_interval(1000000.0)
    assert interval == 20, f"Expected 20µs, got {interval}µs"

    print("PASS: test_velocity_to_interval")


def test_joint_config_defaults() -> None:
    """Verify JointConfig defaults match project constants."""
    cfg = JointConfig()
    assert cfg.v_max == 33333.0, f"Expected v_max 33333, got {cfg.v_max}"
    assert cfg.steps_per_degree == 230.6

    # v_max of 33333 steps/sec = 30µs interval (matches cruise delay)
    interval = int(1_000_000 / cfg.v_max)
    assert interval == 30, f"Expected 30µs at v_max, got {interval}µs"

    print("PASS: test_joint_config_defaults")


def main() -> None:
    """Run all trajectory planner tests."""
    tests = [
        test_single_joint_full_profile,
        test_step_conservation,
        test_short_move_reduced_segments,
        test_negative_direction,
        test_multi_joint_coordination,
        test_interval_validity,
        test_cruise_segment_constant_speed,
        test_curve_type_sinusoidal,
        test_zero_move_no_segments,
        test_move_queue_basic,
        test_move_queue_direction_reversal,
        test_move_queue_same_direction,
        test_move_queue_flush,
        test_velocity_to_interval,
        test_joint_config_defaults,
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
