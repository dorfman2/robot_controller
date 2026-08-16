"""Joint-space <-> motor-space <-> microstep conversions for Armold joints.

Single source of truth for the gear/unit mapping (spec R3): commands come in
as joint-space degrees (output side of the cycloidal gearbox), get converted
to motor-space degrees/steps for the CANBUS Stepper nodes, and telemetry is
converted back. Each joint carries its own gear ratio, direction sign,
park-pose offset (spec R5: motor zero is defined at the park pose), and soft
limits enforced here independently of the planner (spec R9).

Measured Armold constants: 83,028 microsteps per output revolution at 16
microsteps (~230.6 steps/joint-degree, gear ratio ~25.946).

Example:
    >>> cfg = JointConfig(name="j0", node_id=1, gear_ratio=25.94625,
    ...                   steps_per_motor_rev=3200, park_pose_deg=0.0,
    ...                   limit_min_deg=-180.0, limit_max_deg=180.0)
    >>> cfg.joint_deg_to_steps(90.0)
    20757
"""

from __future__ import annotations

from dataclasses import dataclass

#: Measured: 83,028 microsteps = 360 deg of joint output at 16 microsteps.
ARMOLD_STEPS_PER_OUTPUT_REV: int = 83_028
#: 200 full steps x 16 microsteps (all boards set to 16, uniform calibration).
ARMOLD_STEPS_PER_MOTOR_REV: int = 3_200
#: Empirical cycloidal ratio: 83,028 / 3,200 = 25.94625 (NOT the nominal 20:1).
ARMOLD_GEAR_RATIO: float = ARMOLD_STEPS_PER_OUTPUT_REV / ARMOLD_STEPS_PER_MOTOR_REV


class JointLimitError(ValueError):
    """Raised when a commanded joint position violates the soft limits."""


@dataclass(frozen=True)
class JointConfig:
    """Static configuration for one arm joint on the CAN bus.

    Attributes:
        name: Joint name as it appears in the URDF (e.g. ``"j0"``).
        node_id: CANBUS Stepper NodeID (1-31) driving this joint.
        gear_ratio: Gearbox reduction, motor revs per joint rev (>0).
        steps_per_motor_rev: Microsteps per motor revolution
            (full steps x microstep setting; 3200 for 200 x 16).
        park_pose_deg: Joint angle (deg) at the park pose. The node's encoder
            reads 0 at park (zero-at-boot, spec R5), so this is the offset
            between motor zero and joint zero.
        limit_min_deg: Minimum allowed joint angle (deg), inclusive.
        limit_max_deg: Maximum allowed joint angle (deg), inclusive.
        dir_sign: +1 if positive motor rotation is positive joint rotation,
            -1 if inverted. Kept host-side so node config stays uniform.
    """

    name: str
    node_id: int
    gear_ratio: float
    steps_per_motor_rev: int
    park_pose_deg: float
    limit_min_deg: float
    limit_max_deg: float
    dir_sign: int = 1

    def __post_init__(self) -> None:
        """Validate configuration invariants.

        Raises:
            ValueError: If the ratio/steps are non-positive, dir_sign is not
                +/-1, or the limit window is empty or excludes the park pose.
        """
        if self.gear_ratio <= 0:
            raise ValueError(
                f"{self.name}: gear_ratio must be > 0, got {self.gear_ratio}"
            )
        if self.steps_per_motor_rev <= 0:
            raise ValueError(
                f"{self.name}: steps_per_motor_rev must be > 0, got {self.steps_per_motor_rev}"
            )
        if self.dir_sign not in (1, -1):
            raise ValueError(
                f"{self.name}: dir_sign must be +1 or -1, got {self.dir_sign}"
            )
        if self.limit_min_deg >= self.limit_max_deg:
            raise ValueError(
                f"{self.name}: empty limit window "
                f"[{self.limit_min_deg}, {self.limit_max_deg}]"
            )
        if not self.limit_min_deg <= self.park_pose_deg <= self.limit_max_deg:
            raise ValueError(
                f"{self.name}: park pose {self.park_pose_deg} deg outside limits "
                f"[{self.limit_min_deg}, {self.limit_max_deg}]"
            )

    # -- joint -> motor ----------------------------------------------------

    def joint_deg_to_motor_deg(self, joint_deg: float) -> float:
        """Convert a joint angle to motor-shaft degrees (limit-checked).

        Args:
            joint_deg: Absolute joint angle in degrees.

        Returns:
            Motor-shaft angle in degrees relative to the park-pose zero.

        Raises:
            JointLimitError: If ``joint_deg`` violates the soft limits.
        """
        if not self.limit_min_deg <= joint_deg <= self.limit_max_deg:
            raise JointLimitError(
                f"{self.name}: {joint_deg} deg outside "
                f"[{self.limit_min_deg}, {self.limit_max_deg}]"
            )
        return self.dir_sign * (joint_deg - self.park_pose_deg) * self.gear_ratio

    def joint_deg_to_steps(self, joint_deg: float) -> int:
        """Convert a joint angle to absolute motor microsteps (limit-checked).

        Args:
            joint_deg: Absolute joint angle in degrees.

        Returns:
            Rounded microstep target for ``MsgType.SET_POSITION_STEPS``.

        Raises:
            JointLimitError: If ``joint_deg`` violates the soft limits.
        """
        motor_deg = self.joint_deg_to_motor_deg(joint_deg)
        return round(motor_deg / 360.0 * self.steps_per_motor_rev)

    def joint_speed_to_motor_speed(self, joint_deg_per_sec: float) -> float:
        """Convert a joint-space speed to motor deg/s (sign-preserving).

        Args:
            joint_deg_per_sec: Joint speed in deg/s (may be negative).

        Returns:
            Motor-shaft speed in deg/s (magnitude scaled by the gear ratio).
        """
        return joint_deg_per_sec * self.gear_ratio

    # -- motor -> joint ----------------------------------------------------

    def motor_deg_to_joint_deg(self, motor_deg: float) -> float:
        """Convert motor-shaft degrees (telemetry) back to a joint angle.

        Args:
            motor_deg: Motor-shaft angle in degrees (park-pose zero).

        Returns:
            Absolute joint angle in degrees. NOT limit-checked: telemetry must
            report reality even if the joint is out of bounds.
        """
        return self.park_pose_deg + self.dir_sign * motor_deg / self.gear_ratio

    def steps_to_joint_deg(self, steps: int) -> float:
        """Convert motor microsteps (telemetry) back to a joint angle.

        Args:
            steps: Absolute motor microsteps (park-pose zero).

        Returns:
            Absolute joint angle in degrees (not limit-checked).
        """
        motor_deg = steps / self.steps_per_motor_rev * 360.0
        return self.motor_deg_to_joint_deg(motor_deg)
