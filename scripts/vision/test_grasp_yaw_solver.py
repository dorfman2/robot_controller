"""
No-mock tests for :mod:`grasp_yaw_solver`.

Every test exercises the REAL :class:`armold_controller.ik_solver.ArmIK` and the
real solver — no mocks, per project python-prefs. Run standalone:

    PYTHONPATH=/Users/jdorfman/Code/Armold \
        .venv/bin/python scripts/vision/test_grasp_yaw_solver.py

or under pytest:

    PYTHONPATH=/Users/jdorfman/Code/Armold .venv/bin/pytest \
        scripts/vision/test_grasp_yaw_solver.py
"""

from __future__ import annotations

from armold_controller.ik_solver import ArmIK
from scripts.vision.grasp_yaw_solver import (
    RAIL_MAX,
    approach_axis,
    is_yaw_graspable,
    map_yaw_window,
    required_finger_yaw,
    solve_grasp_yaw,
)

# Built once; the tests only read from it.
IK = ArmIK()


def test_finger_yaw_zero_is_on_axis() -> None:
    """finger_yaw=0 at an on-axis target needs rail~0 and J0~0, vertical."""
    s = solve_grasp_yaw(IK, -350.0, 0.0, 100.0, 0.0)
    assert s.success, s.failure_reason
    assert abs(s.rail_mm) < 5.0, f"rail {s.rail_mm}"
    assert abs(s.joint_angles_deg[0]) < 1.0, f"J0 {s.joint_angles_deg[0]}"
    assert s.position_error_mm < 2.0
    assert s.tilt_deg < 3.0


def test_positive_yaw_uses_rail_and_is_vertical() -> None:
    """A +30 deg finger yaw is achieved via a positive rail offset, J0=-30."""
    s = solve_grasp_yaw(IK, -350.0, 0.0, 100.0, 30.0)
    assert s.success, s.failure_reason
    assert 0.0 < s.rail_mm <= RAIL_MAX, f"rail {s.rail_mm}"
    assert abs(s.joint_angles_deg[0] - (-30.0)) < 1.0, f"J0 {s.joint_angles_deg[0]}"
    assert s.finger_yaw_deg == 30.0
    ax = approach_axis(IK, s.joint_angles_deg)
    assert ax[2] < -0.98, f"approach not vertical: {ax}"


def test_negative_yaw_off_rail_travel_fails() -> None:
    """At Y=0 a -30 deg yaw needs a negative rail (out of travel) -> reject."""
    s = solve_grasp_yaw(IK, -350.0, 0.0, 100.0, -30.0)
    assert not s.success
    assert "rail" in s.failure_reason.lower(), s.failure_reason


def test_fk_roundtrip_matches_target_in_base_frame() -> None:
    """FK of the solved config reaches (X, Y-rail, Z) in the base frame."""
    s = solve_grasp_yaw(IK, -350.0, 0.0, 100.0, 25.0)
    assert s.success, s.failure_reason
    p = IK.fk(s.joint_angles_deg)
    assert abs(p.x - (-350.0)) < 2.0, f"x {p.x}"
    assert abs(p.y - (0.0 - s.rail_mm)) < 2.0, f"y {p.y} vs {-s.rail_mm}"
    assert abs(p.z - 100.0) < 2.0, f"z {p.z}"


def test_j0_limit_rejected() -> None:
    """A yaw that drives J0 out of [-180,180] fails cleanly (no motion)."""
    s = solve_grasp_yaw(IK, -350.0, 0.0, 100.0, 200.0)
    assert not s.success
    assert "J0" in s.failure_reason


def test_yaw_window_nonempty_and_self_consistent() -> None:
    """The mapped window is non-empty, in-range, and every entry re-solves."""
    w = map_yaw_window(IK, -350.0, 0.0, 100.0)
    assert w.achievable_yaws_deg, "expected a non-empty yaw window"
    assert w.min_yaw_deg >= -90.0 and w.max_yaw_deg <= 90.0
    for yaw in w.achievable_yaws_deg:
        assert solve_grasp_yaw(IK, -350.0, 0.0, 100.0, yaw).success


def test_offset_target_widens_window() -> None:
    """A +Y target shifts the window to include some negative yaw."""
    w = map_yaw_window(IK, -300.0, 50.0, 100.0)
    assert w.achievable_yaws_deg
    assert w.min_yaw_deg < w.max_yaw_deg


def test_required_finger_yaw_wraps_into_pm90() -> None:
    """Pen angle -> finger yaw maps into [-90, 90] with expected values."""
    assert abs(required_finger_yaw(0.0)) < 1e-9
    assert abs(required_finger_yaw(100.0) - (-80.0)) < 1e-9
    assert abs(required_finger_yaw(-100.0) - 80.0) < 1e-9
    for angle in range(-180, 181, 10):
        r = required_finger_yaw(float(angle))
        assert -90.0 <= r <= 90.0 + 1e-9


def test_is_yaw_graspable_returns_solution() -> None:
    """is_yaw_graspable returns a bool and the attempted solution."""
    ok, sol = is_yaw_graspable(IK, -350.0, 0.0, 100.0, 0.0)
    assert isinstance(ok, bool)
    assert sol.finger_yaw_deg == required_finger_yaw(0.0)


def _run_all() -> int:
    """Run every ``test_*`` in this module; return the failure count."""
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return failures


if __name__ == "__main__":
    import sys

    sys.exit(1 if _run_all() else 0)
