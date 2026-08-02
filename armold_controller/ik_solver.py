"""
ik_solver — Inverse and forward kinematics for the Armold 6-DOF arm.

This module wraps the Robotics Toolbox for Python (RTB) to provide forward
kinematics (FK) and inverse kinematics (IK) for the six rotary joints of the
Armold arm (J0..J5). The linear rail is deliberately excluded: it is commanded
separately as a gross-positioning axis, so the kinematic chain modelled here is
the arm alone, anchored at the rail carriage.

Coordinate convention:
    * Right-handed, Z-up base frame anchored at the arm's mounting point on the
      rail carriage. Units are millimetres for translation, degrees for joint
      angles at this module's public boundary (radians internally for RTB).
    * At the zero pose the arm points straight up along +Z.
    * Joint axes (matching the Armold_FK_v1 reference simulator):
        J0 base yaw about Z, J1/J2/J3 pitch about Y, J4 wrist yaw about Z,
        J5 wrist roll about X.

Geometry provenance:
    The default geometry (:data:`MEASURED_GEOMETRY`) uses REAL physical link
    lengths measured from the arm (mm): base->J0 70, J0->J1 48, J1->J2 152,
    J2->J3 152, J3->J4 77, J4->J5 60, J5->tip 83. A proportional-estimate
    fallback (:meth:`ArmGeometry.from_proportional_dims`) is retained for
    reference. Remaining OPEN ITEM: the J4/J5 axis *labels* (yaw vs roll) are
    disputed between the FK simulator and the Klipper config; the kinematic
    *order* used here (Z then X) follows the FK simulator and is what matters
    numerically — only the human-facing label is unresolved.

Example:
    >>> ik = ArmIK()
    >>> pose = ik.fk([0.0, -30.0, 70.0, 50.0, 0.0, 0.0])
    >>> result = ik.solve_ik(CartesianTarget(x=pose.x, y=pose.y, z=pose.z))
    >>> result.success
    True
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from roboticstoolbox import ET, ETS
from spatialmath import SE3

from armold_controller.klipper_board import DEFAULT_SOFT_LIMITS

logger = logging.getLogger(__name__)

# Number of rotary joints modelled by the IK chain (rail excluded).
NUM_ARM_JOINTS: int = 6

# --- Proportional DIMS from the Armold_FK_v1 reference sim (unitless) ------
_DIMS_BASE_HEIGHT: float = 0.35
_DIMS_SHOULDER_HEIGHT: float = 0.55
_DIMS_UPPER_ARM: float = 1.50
_DIMS_FORE_ARM: float = 1.25
_DIMS_WRIST_LEN: float = 0.35
_DIMS_TOOL_LEN: float = 0.45

# Armold spec sheet value for maximum reach. Retained as a reference only; the
# real measured geometry yields a slightly larger tool-tip reach (see
# MEASURED_GEOMETRY / ArmGeometry.horizontal_reach).
SPEC_MAX_REACH_MM: float = 475.0

# Home pose (degrees) for J0..J5, matching the FK simulator's rest pose.
HOME_POSE_DEG: tuple[float, float, float, float, float, float] = (
    0.0,
    -30.0,
    70.0,
    50.0,
    0.0,
    0.0,
)


@dataclass(frozen=True)
class ArmGeometry:
    """Link lengths (millimetres) defining the Armold arm kinematic chain.

    Each field is a translation along the local Z axis between successive
    joints, matching the ETS built by :class:`ArmIK`.

    The wrist is modelled as three physically distinct segments (J3->J4,
    J4->J5, J5->tip) rather than a single lumped offset, matching the real
    arm's construction.

    Attributes:
        base_height: Fixed offset from the mounting frame up to the J0 base
            yaw axis (mm).
        shoulder_height: Offset from the J0 axis up to the J1 shoulder pitch
            axis (mm).
        upper_arm: Length of the upper-arm segment, J1 to J2 (mm).
        fore_arm: Length of the forearm segment, J2 to J3 (mm).
        wrist_pitch_offset: Offset from the J3 wrist-pitch axis to the J4
            wrist-yaw axis (mm).
        wrist_yaw_offset: Offset from the J4 wrist-yaw axis to the J5
            wrist-roll axis (mm).
        tool_len: Offset from the J5 wrist-roll axis to the tool tip / TCP
            (gripper tip) (mm).
        estimated: True when the lengths are proportional estimates rather
            than real physical measurements. Purely informational.
    """

    base_height: float
    shoulder_height: float
    upper_arm: float
    fore_arm: float
    wrist_pitch_offset: float
    wrist_yaw_offset: float
    tool_len: float
    estimated: bool = True

    def horizontal_reach(self) -> float:
        """Maximum horizontal reach from the J0 yaw axis to the tool tip.

        Computed as the sum of every segment distal to the shoulder pitch axis
        (upper arm through tool), which is the horizontal extent when the
        shoulder is pitched 90 degrees and the remaining pitch joints are zero.

        Returns:
            Reach in millimetres.
        """
        return (
            self.upper_arm
            + self.fore_arm
            + self.wrist_pitch_offset
            + self.wrist_yaw_offset
            + self.tool_len
        )

    @classmethod
    def from_proportional_dims(
        cls, max_reach_mm: float = SPEC_MAX_REACH_MM
    ) -> ArmGeometry:
        """Build fallback geometry by scaling the Armold_FK_v1 proportional DIMS.

        Retained for reference only; :data:`MEASURED_GEOMETRY` (real
        measurements) is the default used by :class:`ArmIK`. The FK simulator
        modelled a single lumped wrist segment, so ``wrist_yaw_offset`` is set
        to zero here (J4 and J5 coincident) and the simulator's wrist length
        maps to ``wrist_pitch_offset``. The scale factor is chosen so the
        horizontal reach equals ``max_reach_mm``.

        Args:
            max_reach_mm: Target horizontal reach in millimetres.

        Returns:
            An :class:`ArmGeometry` with ``estimated=True``.

        Raises:
            ValueError: If ``max_reach_mm`` is not positive.
        """
        if max_reach_mm <= 0.0:
            raise ValueError(f"max_reach_mm must be positive, got {max_reach_mm}")
        reach_units = (
            _DIMS_UPPER_ARM + _DIMS_FORE_ARM + _DIMS_WRIST_LEN + _DIMS_TOOL_LEN
        )
        scale = max_reach_mm / reach_units
        return cls(
            base_height=_DIMS_BASE_HEIGHT * scale,
            shoulder_height=_DIMS_SHOULDER_HEIGHT * scale,
            upper_arm=_DIMS_UPPER_ARM * scale,
            fore_arm=_DIMS_FORE_ARM * scale,
            wrist_pitch_offset=_DIMS_WRIST_LEN * scale,
            wrist_yaw_offset=0.0,
            tool_len=_DIMS_TOOL_LEN * scale,
            estimated=True,
        )


# Real physical link lengths (mm) measured from the arm on 2026-07-31.
# This is the default geometry used by ArmIK.
MEASURED_GEOMETRY: ArmGeometry = ArmGeometry(
    base_height=70.0,  # base of arm -> J0
    shoulder_height=48.0,  # J0 -> J1
    upper_arm=152.0,  # J1 -> J2
    fore_arm=152.0,  # J2 -> J3
    wrist_pitch_offset=77.0,  # J3 -> J4
    wrist_yaw_offset=60.0,  # J4 -> J5
    tool_len=83.0,  # J5 -> gripper tip
    estimated=False,
)


def _default_arm_limits_deg() -> tuple[tuple[float, float], ...]:
    """Derive the six arm joint limits (degrees) from the board soft limits.

    Uses ``klipper_board.DEFAULT_SOFT_LIMITS`` indices 1..6 (skipping index 0,
    the rail) so the IK joint ranges stay the single-source-of-truth aligned
    with the motion controller's clamping.

    Returns:
        A tuple of six ``(minimum, maximum)`` degree pairs for J0..J5.
    """
    arm_limits = DEFAULT_SOFT_LIMITS[1 : 1 + NUM_ARM_JOINTS]
    return tuple((lim.minimum, lim.maximum) for lim in arm_limits)


# Default arm joint limits (degrees) for J0..J5, aligned with KlipperBoard.
ARM_JOINT_LIMITS_DEG: tuple[tuple[float, float], ...] = _default_arm_limits_deg()


@dataclass(frozen=True)
class EndEffectorPose:
    """Cartesian pose of the tool tip in the arm base frame.

    Attributes:
        x: Tool-tip X position (mm).
        y: Tool-tip Y position (mm).
        z: Tool-tip Z position (mm).
        roll: Rotation about X (degrees), XYZ intrinsic convention.
        pitch: Rotation about Y (degrees), XYZ intrinsic convention.
        yaw: Rotation about Z (degrees), XYZ intrinsic convention.
    """

    x: float
    y: float
    z: float
    roll: float
    pitch: float
    yaw: float

    def as_xyz(self) -> tuple[float, float, float]:
        """Return the position component as an ``(x, y, z)`` tuple (mm)."""
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class CartesianTarget:
    """A requested Cartesian goal for the tool tip.

    Orientation is optional: when ``roll``/``pitch``/``yaw`` are all ``None``
    the target is position-only and the solver is free to choose any reachable
    orientation (the orientation error is not minimised).

    Attributes:
        x: Target X position (mm).
        y: Target Y position (mm).
        z: Target Z position (mm).
        roll: Optional target roll about X (degrees).
        pitch: Optional target pitch about Y (degrees).
        yaw: Optional target yaw about Z (degrees).
    """

    x: float
    y: float
    z: float
    roll: float | None = None
    pitch: float | None = None
    yaw: float | None = None

    @property
    def position_only(self) -> bool:
        """Whether this target constrains position only (orientation free).

        Returns:
            True if all three orientation components are ``None``.
        """
        return self.roll is None and self.pitch is None and self.yaw is None

    def to_se3(self) -> SE3:
        """Convert the target to an ``SE3`` homogeneous transform (mm).

        For a position-only target the orientation is set to identity; callers
        are expected to mask out orientation error in that case.

        Returns:
            The target pose as an :class:`spatialmath.SE3`.
        """
        translation = SE3(self.x, self.y, self.z)
        if self.position_only:
            return translation
        rpy = [
            self.roll if self.roll is not None else 0.0,
            self.pitch if self.pitch is not None else 0.0,
            self.yaw if self.yaw is not None else 0.0,
        ]
        return translation * SE3.RPY(rpy, unit="deg", order="xyz")


@dataclass(frozen=True)
class IKResult:
    """Outcome of an inverse-kinematics solve.

    Attributes:
        success: True when a solution was found that reaches the target
            within tolerance AND lies within the joint limits.
        reachable: True when the solver converged to the target within
            tolerance, before joint-limit clamping was considered.
        joint_angles_deg: The six solved joint angles (degrees, J0..J5),
            clamped to the joint limits. Always length ``NUM_ARM_JOINTS``.
        position_error_mm: Euclidean tool-tip position error (mm) between the
            target and the FK of ``joint_angles_deg``.
        orientation_error_deg: Orientation error (degrees) between the target
            and achieved pose; ``0.0`` for position-only targets.
        clamped: True if any joint angle was clamped to its limit, meaning the
            raw IK solution violated a joint range.
        iterations: Number of solver iterations performed.
        message: Human-readable status/diagnostic string.
    """

    success: bool
    reachable: bool
    joint_angles_deg: list[float]
    position_error_mm: float
    orientation_error_deg: float
    clamped: bool
    iterations: int
    message: str


class ArmIK:
    """Forward/inverse kinematics engine for the Armold 6-DOF arm.

    Builds an RTB Elementary Transform Sequence (ETS) from an
    :class:`ArmGeometry` and exposes FK and IK operations in engineering units
    (millimetres and degrees). The linear rail is not part of this chain.

    The IK uses RTB's Levenberg-Marquardt solver (``ETS.ik_LM``) which performs
    internal random restarts for robustness. Joint limits are enforced by this
    class (post-solve clamping plus validation) rather than delegated to the
    solver, keeping the limit policy identical to the rest of the controller.

    Attributes:
        geometry: The link-length geometry used to build the chain.
        limits_deg: Per-joint ``(min, max)`` limits in degrees for J0..J5.
        ets: The assembled Robotics Toolbox ETS (six revolute joints).
    """

    # Position convergence tolerance (mm) for declaring a target reached.
    POSITION_TOLERANCE_MM: float = 1.0
    # Orientation convergence tolerance (degrees) for full-pose targets.
    ORIENTATION_TOLERANCE_DEG: float = 1.0
    # LM solver residual tolerance (on the pose error norm).
    _SOLVER_TOL: float = 1e-6
    # LM solver iteration and search (random-restart) limits.
    _SOLVER_ILIMIT: int = 60
    _SOLVER_SLIMIT: int = 150

    def __init__(
        self,
        geometry: ArmGeometry | None = None,
        limits_deg: tuple[tuple[float, float], ...] | None = None,
    ) -> None:
        """Initialise the kinematics engine.

        Args:
            geometry: Link-length geometry. Defaults to
                :data:`MEASURED_GEOMETRY` (real physical measurements).
            limits_deg: Six ``(min, max)`` degree pairs for J0..J5. Defaults to
                :data:`ARM_JOINT_LIMITS_DEG`.

        Raises:
            ValueError: If ``limits_deg`` is provided with a length other than
                :data:`NUM_ARM_JOINTS`.
        """
        self.geometry: ArmGeometry = (
            geometry if geometry is not None else MEASURED_GEOMETRY
        )

        if limits_deg is None:
            self.limits_deg: tuple[tuple[float, float], ...] = ARM_JOINT_LIMITS_DEG
        else:
            if len(limits_deg) != NUM_ARM_JOINTS:
                raise ValueError(
                    f"limits_deg must have exactly {NUM_ARM_JOINTS} entries, "
                    f"got {len(limits_deg)}"
                )
            self.limits_deg = tuple(limits_deg)

        self.ets: ETS = self._build_ets(self.geometry)
        if self.geometry.estimated:
            logger.warning(
                "ArmIK using ESTIMATED proportional link lengths; "
                "replace with real measurements."
            )
        logger.info(
            "ArmIK initialised: %d joints, tool-tip reach ~%.0f mm",
            self.ets.n,
            self.geometry.horizontal_reach(),
        )

    @staticmethod
    def _build_ets(geometry: ArmGeometry) -> ETS:
        """Assemble the six-joint ETS from a geometry.

        Args:
            geometry: The link-length geometry.

        Returns:
            The assembled ETS with exactly ``NUM_ARM_JOINTS`` revolute joints.
        """
        ets = (
            ET.tz(geometry.base_height)
            * ET.Rz()  # J0 base yaw
            * ET.tz(geometry.shoulder_height)
            * ET.Ry()  # J1 shoulder pitch
            * ET.tz(geometry.upper_arm)
            * ET.Ry()  # J2 elbow pitch
            * ET.tz(geometry.fore_arm)
            * ET.Ry()  # J3 wrist pitch
            * ET.tz(geometry.wrist_pitch_offset)
            * ET.Rz()  # J4 wrist yaw
            * ET.tz(geometry.wrist_yaw_offset)
            * ET.Rx()  # J5 wrist roll
            * ET.tz(geometry.tool_len)
        )
        return ets

    def fk(self, joint_angles_deg: list[float]) -> EndEffectorPose:
        """Compute the tool-tip pose for a set of joint angles.

        Args:
            joint_angles_deg: Six joint angles (degrees, J0..J5).

        Returns:
            The tool-tip :class:`EndEffectorPose` in the arm base frame.

        Raises:
            ValueError: If ``joint_angles_deg`` does not have exactly
                :data:`NUM_ARM_JOINTS` elements.
        """
        if len(joint_angles_deg) != NUM_ARM_JOINTS:
            raise ValueError(
                f"joint_angles_deg must have exactly {NUM_ARM_JOINTS} elements, "
                f"got {len(joint_angles_deg)}"
            )
        q = np.deg2rad(np.asarray(joint_angles_deg, dtype=float))
        pose = SE3(self.ets.eval(q), check=False)
        x, y, z = (float(v) for v in pose.t)
        roll, pitch, yaw = (float(v) for v in pose.rpy(unit="deg", order="xyz"))
        return EndEffectorPose(x=x, y=y, z=z, roll=roll, pitch=pitch, yaw=yaw)

    def solve_ik(
        self,
        target: CartesianTarget,
        seed_deg: list[float] | None = None,
    ) -> IKResult:
        """Solve inverse kinematics for a Cartesian target.

        Uses RTB's Levenberg-Marquardt solver seeded at ``seed_deg`` (or the
        home pose). For position-only targets the orientation error is masked
        out. The raw solution is wrapped into ``[-180, 180]`` degrees, clamped
        to the joint limits, and the achieved pose is recomputed via FK so the
        reported errors reflect the angles actually returned.

        Args:
            target: The Cartesian goal for the tool tip.
            seed_deg: Optional initial guess (six joint angles, degrees). When
                omitted the home pose is used, which biases the solver toward a
                natural, human-expected configuration.

        Returns:
            An :class:`IKResult` describing the solve outcome. On failure the
            joint angles fall back to the seed (or home) pose so callers always
            receive a valid, in-limits configuration.

        Raises:
            ValueError: If ``seed_deg`` is provided with a length other than
                :data:`NUM_ARM_JOINTS`.
        """
        if seed_deg is not None and len(seed_deg) != NUM_ARM_JOINTS:
            raise ValueError(
                f"seed_deg must have exactly {NUM_ARM_JOINTS} elements, "
                f"got {len(seed_deg)}"
            )

        seed = list(seed_deg) if seed_deg is not None else list(HOME_POSE_DEG)
        q0 = np.deg2rad(np.asarray(seed, dtype=float))
        target_se3 = target.to_se3()

        # Mask: position-only targets ignore orientation error.
        mask = (
            np.array([1.0, 1.0, 1.0, 0.0, 0.0, 0.0])
            if target.position_only
            else np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        )

        q_sol, solver_success, iterations, _searches, _residual = self.ets.ik_LM(
            target_se3,
            q0=q0,
            ilimit=self._SOLVER_ILIMIT,
            slimit=self._SOLVER_SLIMIT,
            tol=self._SOLVER_TOL,
            mask=mask,
            joint_limits=False,
        )

        # Wrap to [-180, 180] deg, then clamp to per-joint limits.
        raw_deg = np.rad2deg(np.asarray(q_sol, dtype=float))
        wrapped_deg = ((raw_deg + 180.0) % 360.0) - 180.0
        clamped_deg, clamped = self._clamp_to_limits(wrapped_deg)

        # Recompute achieved pose from the clamped angles.
        achieved = self.fk(clamped_deg.tolist())
        position_error = self._position_error(target, achieved)
        orientation_error = self._orientation_error(target, achieved)

        reachable = bool(solver_success) and (
            position_error <= self.POSITION_TOLERANCE_MM
        )
        within_orientation = (
            target.position_only or orientation_error <= self.ORIENTATION_TOLERANCE_DEG
        )
        success = reachable and (not clamped) and within_orientation

        if success:
            message = "solved"
        elif not solver_success:
            message = "solver did not converge (target likely unreachable)"
        elif clamped:
            message = "solution required joint-limit clamping (out of range)"
        elif position_error > self.POSITION_TOLERANCE_MM:
            message = f"target out of reach (position error {position_error:.1f} mm)"
        else:
            message = f"orientation not reached (error {orientation_error:.1f} deg)"

        if not success:
            logger.warning(
                "IK solve unsuccessful for target (%.1f, %.1f, %.1f): %s",
                target.x,
                target.y,
                target.z,
                message,
            )
            # Fall back to a safe, in-limits configuration (the seed).
            safe_deg, _ = self._clamp_to_limits(np.asarray(seed, dtype=float))
            return IKResult(
                success=False,
                reachable=reachable,
                joint_angles_deg=safe_deg.tolist(),
                position_error_mm=position_error,
                orientation_error_deg=orientation_error,
                clamped=clamped,
                iterations=int(iterations),
                message=message,
            )

        return IKResult(
            success=True,
            reachable=True,
            joint_angles_deg=clamped_deg.tolist(),
            position_error_mm=position_error,
            orientation_error_deg=orientation_error,
            clamped=False,
            iterations=int(iterations),
            message=message,
        )

    def _clamp_to_limits(self, angles_deg: np.ndarray) -> tuple[np.ndarray, bool]:
        """Clamp joint angles to the configured per-joint limits.

        Args:
            angles_deg: Array of six joint angles (degrees).

        Returns:
            A tuple ``(clamped, was_clamped)`` where ``clamped`` is the
            limit-constrained array and ``was_clamped`` is True if any element
            changed by more than a numerical tolerance.
        """
        clamped = np.array(angles_deg, dtype=float)
        for i, (lo, hi) in enumerate(self.limits_deg):
            clamped[i] = min(hi, max(lo, clamped[i]))
        was_clamped = bool(np.any(np.abs(clamped - angles_deg) > 1e-6))
        return clamped, was_clamped

    @staticmethod
    def _position_error(target: CartesianTarget, achieved: EndEffectorPose) -> float:
        """Euclidean tool-tip position error between target and achieved pose.

        Args:
            target: The requested Cartesian target.
            achieved: The achieved end-effector pose.

        Returns:
            Position error magnitude in millimetres.
        """
        dx = target.x - achieved.x
        dy = target.y - achieved.y
        dz = target.z - achieved.z
        return float(np.sqrt(dx * dx + dy * dy + dz * dz))

    @staticmethod
    def _orientation_error(target: CartesianTarget, achieved: EndEffectorPose) -> float:
        """Orientation error (degrees) between target and achieved pose.

        Computes the geodesic angle between the target and achieved rotations.
        Returns ``0.0`` for position-only targets (orientation unconstrained).

        Args:
            target: The requested Cartesian target.
            achieved: The achieved end-effector pose.

        Returns:
            Orientation error in degrees (``0.0`` when position-only).
        """
        if target.position_only:
            return 0.0
        target_rot = SE3.RPY(
            [target.roll or 0.0, target.pitch or 0.0, target.yaw or 0.0],
            unit="deg",
            order="xyz",
        )
        achieved_rot = SE3.RPY(
            [achieved.roll, achieved.pitch, achieved.yaw],
            unit="deg",
            order="xyz",
        )
        # Relative rotation angle via the trace of R_err.
        r_err = target_rot.R.T @ achieved_rot.R
        cos_angle = (np.trace(r_err) - 1.0) / 2.0
        cos_angle = float(np.clip(cos_angle, -1.0, 1.0))
        return float(np.degrees(np.arccos(cos_angle)))
