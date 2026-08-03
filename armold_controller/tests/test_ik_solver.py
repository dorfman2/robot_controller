"""
Unit tests for the Armold inverse/forward kinematics engine.

These tests exercise the real RTB-backed :class:`ArmIK` implementation with no
mocking: FK and IK run against the actual Robotics Toolbox solver. They verify
model structure, forward-kinematics landmarks (zero pose, home pose, reach),
IK round-trips (full pose and position-only), unreachable-target handling,
joint-limit clamping, and input validation.

Run standalone: ``.venv/bin/python -m armold_controller.tests.test_ik_solver``
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".")

import numpy as np

from armold_controller.ik_solver import (
    ARM_JOINT_LIMITS_DEG,
    HOME_POSE_DEG,
    MEASURED_GEOMETRY,
    NUM_ARM_JOINTS,
    SPEC_MAX_REACH_MM,
    ArmGeometry,
    ArmIK,
    CartesianTarget,
)
from armold_controller.klipper_board import DEFAULT_SOFT_LIMITS


def test_geometry_from_proportional_dims() -> None:
    """Scaled fallback geometry reaches the spec value and is flagged estimated."""
    geo = ArmGeometry.from_proportional_dims()
    # from_proportional_dims scales the along-arm segments (wrist_yaw=0) so that
    # upper+fore+wrist_pitch+tool matches the spec reach.
    along_arm = geo.upper_arm + geo.fore_arm + geo.wrist_pitch_offset + geo.tool_len
    assert abs(along_arm - SPEC_MAX_REACH_MM) < 1e-6, f"along_arm {along_arm}"
    assert geo.estimated is True
    # The proportional (single-segment wrist) fallback sets J4->J5 to zero.
    assert geo.wrist_yaw_offset == 0.0
    for name in (
        "base_height",
        "shoulder_height",
        "upper_arm",
        "fore_arm",
        "wrist_pitch_offset",
        "tool_len",
    ):
        assert getattr(geo, name) > 0.0, f"{name} must be positive"
    print("PASS: test_geometry_from_proportional_dims")


def test_measured_geometry_is_default() -> None:
    """The default ArmIK geometry is the real measured (non-estimated) one."""
    ik = ArmIK()
    assert ik.geometry is MEASURED_GEOMETRY
    assert ik.geometry.estimated is False
    assert ik.geometry.base_height == 165.5
    assert ik.geometry.shoulder_height == 63.5
    assert ik.geometry.upper_arm == 171.0
    assert ik.geometry.fore_arm == 171.0
    assert ik.geometry.wrist_pitch_offset == 86.0
    assert ik.geometry.wrist_yaw_offset == 62.0
    assert ik.geometry.tool_len == 81.0
    assert abs(ik.geometry.horizontal_reach() - 490.0) < 1e-6
    print("PASS: test_measured_geometry_is_default")


def test_geometry_rejects_nonpositive_reach() -> None:
    """A non-positive target reach raises ValueError."""
    try:
        ArmGeometry.from_proportional_dims(0.0)
    except ValueError:
        print("PASS: test_geometry_rejects_nonpositive_reach")
        return
    raise AssertionError("expected ValueError for non-positive reach")


def test_arm_limits_track_board_limits() -> None:
    """IK arm limits are derived from board soft limits (indices 1..6)."""
    assert len(ARM_JOINT_LIMITS_DEG) == NUM_ARM_JOINTS
    for i, (lo, hi) in enumerate(ARM_JOINT_LIMITS_DEG):
        board_limit = DEFAULT_SOFT_LIMITS[i + 1]
        assert lo == board_limit.minimum, f"joint {i} min mismatch"
        assert hi == board_limit.maximum, f"joint {i} max mismatch"
    print("PASS: test_arm_limits_track_board_limits")


def test_ets_has_six_joints() -> None:
    """The assembled ETS has exactly six revolute joints."""
    ik = ArmIK()
    assert ik.ets.n == NUM_ARM_JOINTS
    print("PASS: test_ets_has_six_joints")


def test_fk_zero_pose_points_up() -> None:
    """At the zero pose the tool tip is on the +Z axis (x=y=0)."""
    ik = ArmIK()
    pose = ik.fk([0.0] * NUM_ARM_JOINTS)
    geo = ik.geometry
    # Arm (up to J5) points straight up; the tool points sideways +Y, so the
    # tip is offset +tool_len in Y and does not add to Z.
    expected_z = (
        geo.base_height
        + geo.shoulder_height
        + geo.upper_arm
        + geo.fore_arm
        + geo.wrist_pitch_offset
        + geo.wrist_yaw_offset
    )
    assert abs(pose.x) < 1e-3, f"x {pose.x} != 0"
    assert abs(pose.y - geo.tool_len) < 1e-3, f"y {pose.y} != {geo.tool_len}"
    assert abs(pose.z - expected_z) < 1e-3, f"z {pose.z} != {expected_z}"
    print("PASS: test_fk_zero_pose_points_up")


def test_fk_home_pose_landmark() -> None:
    """Home-pose FK matches the measured-geometry landmark (~242, 0, 366)."""
    ik = ArmIK()
    pose = ik.fk(list(HOME_POSE_DEG))
    assert abs(pose.x - (-327.9)) < 1.0, f"x {pose.x}"
    assert abs(pose.y - 81.0) < 1.0, f"y {pose.y}"
    assert abs(pose.z - 219.2) < 1.0, f"z {pose.z}"
    print("PASS: test_fk_home_pose_landmark")


def test_fk_wrong_length_raises() -> None:
    """FK with the wrong number of joint angles raises ValueError."""
    ik = ArmIK()
    try:
        ik.fk([0.0, 0.0, 0.0])
    except ValueError:
        print("PASS: test_fk_wrong_length_raises")
        return
    raise AssertionError("expected ValueError for wrong-length FK input")


def test_max_reach_horizontal() -> None:
    """Shoulder pitched 90 deg, arm straight: reach matches horizontal_reach()."""
    ik = ArmIK()
    pose = ik.fk([0.0, 90.0, 0.0, 0.0, 0.0, 0.0])
    horizontal = float(np.hypot(pose.x, pose.y))
    # Tip hypot includes the perpendicular tool offset (+Y): sqrt(reach^2+tool^2).
    reach = ik.geometry.horizontal_reach()
    expected = (reach**2 + ik.geometry.tool_len**2) ** 0.5
    assert abs(horizontal - expected) < 1.0, f"reach {horizontal} != {expected}"
    print("PASS: test_max_reach_horizontal")


def test_ik_round_trip_full_pose() -> None:
    """Full-pose IK recovers a pose generated by FK within tolerance."""
    ik = ArmIK()
    q_true = [20.0, -20.0, 60.0, 30.0, -15.0, 45.0]
    pose = ik.fk(q_true)
    target = CartesianTarget(
        x=pose.x,
        y=pose.y,
        z=pose.z,
        roll=pose.roll,
        pitch=pose.pitch,
        yaw=pose.yaw,
    )
    result = ik.solve_ik(target)
    assert result.success is True, f"IK failed: {result.message}"
    assert result.position_error_mm <= ik.POSITION_TOLERANCE_MM
    assert result.orientation_error_deg <= ik.ORIENTATION_TOLERANCE_DEG
    # Verify the returned angles actually reproduce the target pose.
    check = ik.fk(result.joint_angles_deg)
    assert abs(check.x - pose.x) < 1.0
    assert abs(check.y - pose.y) < 1.0
    assert abs(check.z - pose.z) < 1.0
    print("PASS: test_ik_round_trip_full_pose")


def test_ik_position_only() -> None:
    """Position-only IK reaches the target point, orientation unconstrained."""
    ik = ArmIK()
    pose = ik.fk([10.0, -25.0, 55.0, 40.0, 20.0, -30.0])
    target = CartesianTarget(x=pose.x, y=pose.y, z=pose.z)
    assert target.position_only is True
    result = ik.solve_ik(target)
    assert result.success is True, f"IK failed: {result.message}"
    assert result.position_error_mm <= ik.POSITION_TOLERANCE_MM
    assert result.orientation_error_deg == 0.0
    print("PASS: test_ik_position_only")


def test_ik_unreachable_target() -> None:
    """A target well outside the workspace fails and returns in-limits angles."""
    ik = ArmIK()
    target = CartesianTarget(x=2000.0, y=0.0, z=0.0)
    result = ik.solve_ik(target)
    assert result.success is False
    assert result.reachable is False
    assert len(result.joint_angles_deg) == NUM_ARM_JOINTS
    # Fallback angles must still be within limits.
    for angle, (lo, hi) in zip(result.joint_angles_deg, ik.limits_deg):
        assert lo <= angle <= hi, f"fallback angle {angle} out of [{lo},{hi}]"
    print("PASS: test_ik_unreachable_target")


def test_ik_solution_within_limits() -> None:
    """Any successful solution lies within the joint limits."""
    ik = ArmIK()
    pose = ik.fk([170.0, -80.0, 100.0, 90.0, 60.0, 120.0])
    target = CartesianTarget(x=pose.x, y=pose.y, z=pose.z)
    result = ik.solve_ik(target)
    for angle, (lo, hi) in zip(result.joint_angles_deg, ik.limits_deg):
        assert lo - 1e-6 <= angle <= hi + 1e-6, f"angle {angle} out of range"
    print("PASS: test_ik_solution_within_limits")


def test_ik_seed_wrong_length_raises() -> None:
    """A seed with the wrong length raises ValueError."""
    ik = ArmIK()
    target = CartesianTarget(x=100.0, y=0.0, z=400.0)
    try:
        ik.solve_ik(target, seed_deg=[0.0, 0.0])
    except ValueError:
        print("PASS: test_ik_seed_wrong_length_raises")
        return
    raise AssertionError("expected ValueError for wrong-length seed")


def test_cartesian_target_to_se3_position() -> None:
    """A position-only target produces an SE3 with matching translation."""
    target = CartesianTarget(x=100.0, y=-50.0, z=300.0)
    t = target.to_se3()
    assert abs(t.t[0] - 100.0) < 1e-9
    assert abs(t.t[1] - (-50.0)) < 1e-9
    assert abs(t.t[2] - 300.0) < 1e-9
    print("PASS: test_cartesian_target_to_se3_position")


def main() -> None:
    """Run all IK solver tests and report a summary."""
    tests = [
        test_geometry_from_proportional_dims,
        test_measured_geometry_is_default,
        test_geometry_rejects_nonpositive_reach,
        test_arm_limits_track_board_limits,
        test_ets_has_six_joints,
        test_fk_zero_pose_points_up,
        test_fk_home_pose_landmark,
        test_fk_wrong_length_raises,
        test_max_reach_horizontal,
        test_ik_round_trip_full_pose,
        test_ik_position_only,
        test_ik_unreachable_target,
        test_ik_solution_within_limits,
        test_ik_seed_wrong_length_raises,
        test_cartesian_target_to_se3_position,
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
