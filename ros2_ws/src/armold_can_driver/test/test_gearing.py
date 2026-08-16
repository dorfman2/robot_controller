"""No-mock unit tests for the joint<->motor gear/unit mapping.

Ground truth: Armold's measured calibration — 83,028 microsteps per output
revolution at 16 microsteps (230.6 steps/joint-degree, ratio 25.94625).

Run:
    python -m unittest discover -s test -v
"""

from __future__ import annotations

import unittest

from armold_can_driver.gearing import (
    ARMOLD_GEAR_RATIO,
    ARMOLD_STEPS_PER_MOTOR_REV,
    ARMOLD_STEPS_PER_OUTPUT_REV,
    JointConfig,
    JointLimitError,
)


def make_joint(**overrides: object) -> JointConfig:
    """Build a JointConfig with Armold's measured defaults.

    Args:
        **overrides: Field overrides applied on top of the defaults.

    Returns:
        A validated JointConfig.
    """
    params: dict = {
        "name": "j0",
        "node_id": 1,
        "gear_ratio": ARMOLD_GEAR_RATIO,
        "steps_per_motor_rev": ARMOLD_STEPS_PER_MOTOR_REV,
        "park_pose_deg": 0.0,
        "limit_min_deg": -180.0,
        "limit_max_deg": 180.0,
        "dir_sign": 1,
    }
    params.update(overrides)
    return JointConfig(**params)


class TestMeasuredCalibration(unittest.TestCase):
    """Conversions must reproduce the measured Armold numbers."""

    def test_full_output_rev_is_measured_steps(self) -> None:
        """360 joint degrees -> exactly 83,028 microsteps (measured)."""
        joint = make_joint(limit_max_deg=360.0)
        self.assertEqual(joint.joint_deg_to_steps(360.0), ARMOLD_STEPS_PER_OUTPUT_REV)

    def test_steps_per_degree(self) -> None:
        """One joint degree is ~230.6 microsteps."""
        joint = make_joint()
        self.assertEqual(joint.joint_deg_to_steps(1.0), 231)  # round(230.63)
        self.assertAlmostEqual(ARMOLD_STEPS_PER_OUTPUT_REV / 360.0, 230.63, places=2)

    def test_ninety_degrees(self) -> None:
        """90 joint degrees -> 20,757 microsteps (quarter of 83,028)."""
        joint = make_joint()
        self.assertEqual(joint.joint_deg_to_steps(90.0), 20_757)


class TestRoundTrip(unittest.TestCase):
    """joint -> steps -> joint must return within a microstep of the input."""

    def test_round_trip_across_range(self) -> None:
        """Round-trip error stays under one microstep across the range."""
        joint = make_joint()
        one_step_deg = 360.0 / (joint.gear_ratio * joint.steps_per_motor_rev)
        for deg in (-180.0, -90.0, -1.234, 0.0, 0.001, 45.5, 90.0, 179.999):
            steps = joint.joint_deg_to_steps(deg)
            back = joint.steps_to_joint_deg(steps)
            self.assertAlmostEqual(back, deg, delta=one_step_deg)

    def test_round_trip_with_offset_and_inversion(self) -> None:
        """Park offset and dir_sign both survive the round trip."""
        joint = make_joint(park_pose_deg=-30.0, dir_sign=-1, limit_min_deg=-120.0)
        for deg in (-120.0, -30.0, 0.0, 55.5, 180.0):
            steps = joint.joint_deg_to_steps(deg)
            back = joint.steps_to_joint_deg(steps)
            self.assertAlmostEqual(back, deg, places=2)

    def test_park_pose_is_motor_zero(self) -> None:
        """At the park pose the motor target is exactly zero (R5)."""
        joint = make_joint(park_pose_deg=70.0)
        self.assertEqual(joint.joint_deg_to_steps(70.0), 0)
        self.assertAlmostEqual(joint.steps_to_joint_deg(0), 70.0)


class TestDirectionAndSpeed(unittest.TestCase):
    """Direction sign and speed scaling."""

    def test_dir_sign_inverts_motor_target(self) -> None:
        """dir_sign=-1 mirrors the motor command."""
        normal = make_joint(dir_sign=1)
        inverted = make_joint(dir_sign=-1)
        self.assertEqual(
            normal.joint_deg_to_steps(45.0), -inverted.joint_deg_to_steps(45.0)
        )

    def test_speed_scales_by_ratio(self) -> None:
        """10 joint-deg/s -> ~259.5 motor-deg/s at the measured ratio."""
        joint = make_joint()
        self.assertAlmostEqual(
            joint.joint_speed_to_motor_speed(10.0), 259.4625, places=3
        )

    def test_speed_preserves_sign(self) -> None:
        """Negative joint speed stays negative in motor space."""
        joint = make_joint()
        self.assertLess(joint.joint_speed_to_motor_speed(-5.0), 0.0)


class TestLimits(unittest.TestCase):
    """Soft limits enforced on command, never on telemetry."""

    def test_command_beyond_limits_raises(self) -> None:
        """Commands outside the window raise JointLimitError (R9)."""
        joint = make_joint(limit_min_deg=-90.0, limit_max_deg=90.0)
        with self.assertRaises(JointLimitError):
            joint.joint_deg_to_steps(90.001)
        with self.assertRaises(JointLimitError):
            joint.joint_deg_to_motor_deg(-90.001)

    def test_limits_inclusive(self) -> None:
        """The limit endpoints themselves are commandable."""
        joint = make_joint(limit_min_deg=-90.0, limit_max_deg=90.0)
        joint.joint_deg_to_steps(90.0)
        joint.joint_deg_to_steps(-90.0)

    def test_telemetry_not_limit_checked(self) -> None:
        """Out-of-bounds telemetry still reports reality."""
        joint = make_joint(limit_min_deg=-90.0, limit_max_deg=90.0)
        big_steps = joint.steps_per_motor_rev * 30  # way past +90 deg
        self.assertGreater(joint.steps_to_joint_deg(big_steps), 90.0)


class TestConfigValidation(unittest.TestCase):
    """JointConfig invariants."""

    def test_bad_ratio_rejected(self) -> None:
        """Non-positive gear ratio is invalid."""
        with self.assertRaises(ValueError):
            make_joint(gear_ratio=0.0)

    def test_bad_dir_sign_rejected(self) -> None:
        """dir_sign must be exactly +1 or -1."""
        with self.assertRaises(ValueError):
            make_joint(dir_sign=2)

    def test_empty_limit_window_rejected(self) -> None:
        """min >= max is invalid."""
        with self.assertRaises(ValueError):
            make_joint(limit_min_deg=10.0, limit_max_deg=-10.0)

    def test_park_outside_limits_rejected(self) -> None:
        """The park pose must be commandable within the limits (R5)."""
        with self.assertRaises(ValueError):
            make_joint(park_pose_deg=170.0, limit_min_deg=-90.0, limit_max_deg=90.0)


if __name__ == "__main__":
    unittest.main()
