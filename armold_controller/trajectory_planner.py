"""
TrajectoryPlanner — S-curve motion profile computation for Armold.

Computes 7-segment S-curve profiles per joint, generates segment lists
for the MCU to interpolate, and optimizes junction velocities across
sequential moves via a lookahead queue.

Architecture:
    WebSocket command → MotionManager → TrajectoryPlanner → Segments → SerialBoard

Each move is decomposed into up to 7 phases per joint:
    1. Jerk up (acceleration increases)
    2. Constant acceleration
    3. Jerk down (acceleration decreases to zero, velocity reaches v_max)
    4. Cruise (constant velocity)
    5. Jerk down (deceleration increases)
    6. Constant deceleration
    7. Jerk up (deceleration decreases to zero, velocity reaches zero)

Short moves automatically reduce to 5 or 3 segments when distance
is insufficient to reach full speed.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

logger = logging.getLogger(__name__)


class CurveType(IntEnum):
    """Interpolation method for MCU within a segment.

    Determines how the MCU transitions from start_interval to end_interval
    over the step_count steps in a segment.

    Attributes:
        LINEAR: Linear interpolation (constant acceleration within segment).
        SINUSOIDAL: Half-cosine interpolation (smooth ease-in/out within segment).
    """

    LINEAR = 0
    SINUSOIDAL = 1


@dataclass
class JointConfig:
    """Per-joint motion limits for trajectory planning.

    All values are in steps and microseconds to match firmware units directly.

    Attributes:
        v_max: Maximum velocity in steps/second.
        a_max: Maximum acceleration in steps/second².
        j_max: Maximum jerk in steps/second³.
        steps_per_degree: Steps per degree of output rotation.
    """

    v_max: float = 33333.0       # steps/sec (corresponds to 30µs interval)
    a_max: float = 100000.0      # steps/sec² (smooth but responsive)
    j_max: float = 1000000.0     # steps/sec³ (limits jerk for smoothness)
    steps_per_degree: float = 230.6  # 83028 steps / 360°


@dataclass
class Segment:
    """A single motion segment sent to the MCU for execution.

    The MCU interpolates from start_interval to end_interval over
    step_count steps using the specified curve_type. Multiple segments
    compose a complete motion profile for one joint.

    Attributes:
        joint: Joint index (0-3 for Einsy, 4-5 for RAMPS).
        direction: Movement direction (True=forward/positive, False=reverse).
        step_count: Number of steps in this segment.
        start_interval: Microseconds between steps at segment start.
        end_interval: Microseconds between steps at segment end.
        curve_type: Interpolation method (LINEAR or SINUSOIDAL).
    """

    joint: int
    direction: bool
    step_count: int
    start_interval: int
    end_interval: int
    curve_type: CurveType = CurveType.LINEAR


@dataclass
class SCurveProfile:
    """Computed S-curve profile for a single joint move.

    Contains the durations and step counts for each of the 7 phases.
    Phases with zero duration are skipped (short moves).

    Attributes:
        phases: List of 7 (duration_s, step_count) tuples.
        v_peak: Actual peak velocity reached (steps/sec).
        a_peak: Actual peak acceleration reached (steps/sec²).
        total_steps: Total steps across all phases.
        total_time: Total time in seconds.
    """

    phases: list[tuple[float, int]] = field(default_factory=list)
    v_peak: float = 0.0
    a_peak: float = 0.0
    total_steps: int = 0
    total_time: float = 0.0


@dataclass
class Move:
    """A queued move with entry/exit velocity constraints.

    Used by the lookahead queue to optimize junction velocities
    between sequential moves.

    Attributes:
        target: Absolute target positions for all joints.
        delta: Signed step deltas per joint.
        entry_velocity: Maximum entry velocity (steps/sec, per master joint).
        exit_velocity: Maximum exit velocity (steps/sec, per master joint).
        segments: Computed segments for this move (filled after planning).
    """

    target: list[int]
    delta: list[int] = field(default_factory=list)
    entry_velocity: float = 0.0
    exit_velocity: float = 0.0
    segments: list[Segment] = field(default_factory=list)


class MoveQueue:
    """Buffered moves with junction velocity optimization.

    Implements backward-pass lookahead to compute optimal junction
    velocities between sequential moves. This eliminates unnecessary
    deceleration-to-zero between moves that continue in the same direction.

    Attributes:
        max_depth: Maximum number of moves in the lookahead buffer.
    """

    def __init__(self, max_depth: int = 20) -> None:
        """Initialize the move queue.

        Args:
            max_depth: Maximum lookahead depth.
        """
        self.max_depth = max_depth
        self._moves: deque[Move] = deque(maxlen=max_depth)

    @property
    def depth(self) -> int:
        """Number of moves currently in the queue.

        Returns:
            Current queue depth.
        """
        return len(self._moves)

    def add_move(self, move: Move) -> Optional[Move]:
        """Add a move and optimize junctions. Returns a ready move if available.

        A move is 'ready' when a subsequent move has been added (so its
        exit velocity is determined) or when the queue is full.

        Args:
            move: Move to add to the queue.

        Returns:
            The oldest move if it's ready for execution, or None.
        """
        self._moves.append(move)
        self._optimize_junctions()

        # Return the oldest move if we have at least 2 in queue
        if len(self._moves) >= 2:
            return self._moves.popleft()
        return None

    def flush(self) -> list[Move]:
        """Flush all remaining moves (e.g., when no more moves are coming).

        Sets exit_velocity=0 on the last move and returns all.

        Returns:
            List of all remaining moves in order.
        """
        if self._moves:
            self._moves[-1].exit_velocity = 0.0
        result = list(self._moves)
        self._moves.clear()
        return result

    def clear(self) -> None:
        """Clear all buffered moves (e.g., on E-STOP)."""
        self._moves.clear()

    def _optimize_junctions(self) -> None:
        """Backward pass: compute max junction velocities.

        At each junction between consecutive moves, the velocity is limited by:
        - Direction change (must decel to zero if direction reverses on any joint)
        - Cornering factor (proportional to direction similarity)
        - Max velocity of both adjacent moves
        """
        if len(self._moves) < 2:
            return

        for i in range(len(self._moves) - 1, 0, -1):
            prev_move = self._moves[i - 1]
            curr_move = self._moves[i]
            junction_v = self._compute_junction_speed(prev_move, curr_move)
            prev_move.exit_velocity = min(prev_move.exit_velocity, junction_v)
            curr_move.entry_velocity = min(curr_move.entry_velocity, junction_v)

    def _compute_junction_speed(self, prev: Move, curr: Move) -> float:
        """Compute maximum junction velocity between two moves.

        If any joint reverses direction, junction velocity is zero.
        If all joints continue in the same direction, junction velocity
        is the minimum of both moves' peak velocities scaled by a
        cornering factor.

        Args:
            prev: Previous move.
            curr: Current move.

        Returns:
            Maximum junction velocity in steps/sec.
        """
        # Check for direction reversal on any joint
        for i in range(min(len(prev.delta), len(curr.delta))):
            if prev.delta[i] == 0 or curr.delta[i] == 0:
                continue
            # Sign change means direction reversal
            if (prev.delta[i] > 0) != (curr.delta[i] > 0):
                return 0.0

        # No reversal: allow junction at reduced speed
        # Use cosine similarity of direction vectors as cornering factor
        dot = 0.0
        mag_prev = 0.0
        mag_curr = 0.0
        for i in range(min(len(prev.delta), len(curr.delta))):
            dot += prev.delta[i] * curr.delta[i]
            mag_prev += prev.delta[i] ** 2
            mag_curr += curr.delta[i] ** 2

        if mag_prev == 0 or mag_curr == 0:
            return 0.0

        cos_angle = dot / (math.sqrt(mag_prev) * math.sqrt(mag_curr))
        # Clamp to [0, 1] — negative means reversal (caught above)
        cornering_factor = max(0.0, min(1.0, cos_angle))

        # Junction velocity is limited by the slower of the two moves
        v_limit = min(prev.exit_velocity, curr.entry_velocity)
        return v_limit * cornering_factor


# Minimum interval the MCU can reliably execute (µs)
MIN_INTERVAL_US: int = 20
# Maximum interval (effectively stopped)
MAX_INTERVAL_US: int = 5000


class TrajectoryPlanner:
    """Computes S-curve motion profiles and generates MCU segments.

    Handles the full pipeline from move request to segment list:
    1. Compute per-joint S-curve profile (7-segment or reduced)
    2. Convert profile phases into MCU-compatible Segment objects
    3. Manage lookahead queue for junction velocity optimization

    Attributes:
        joints: Per-joint configuration (velocity, acceleration, jerk limits).
        lookahead: MoveQueue for junction velocity optimization.
        num_joints: Number of joints this planner handles.
    """

    def __init__(
        self,
        joint_configs: Optional[list[JointConfig]] = None,
        num_joints: int = 4,
        lookahead_depth: int = 20,
    ) -> None:
        """Initialize the trajectory planner.

        Args:
            joint_configs: Per-joint motion limits. If None, uses defaults.
            num_joints: Number of joints to plan for.
            lookahead_depth: Maximum moves in the lookahead buffer.
        """
        self.num_joints = num_joints
        if joint_configs is None:
            self.joints = [JointConfig() for _ in range(num_joints)]
        else:
            self.joints = joint_configs
        self.lookahead = MoveQueue(max_depth=lookahead_depth)

    def plan_move(
        self,
        current_pos: list[int],
        target_pos: list[int],
    ) -> list[Segment]:
        """Plan a single move with S-curve profile per joint.

        Computes independent profiles for each joint that needs to move,
        then time-synchronizes them so all joints finish together.

        Args:
            current_pos: Current position for each joint (steps).
            target_pos: Target position for each joint (steps).

        Returns:
            List of Segments for all joints composing this move.
        """
        deltas = [
            target_pos[i] - current_pos[i]
            for i in range(min(len(current_pos), len(target_pos)))
        ]

        # Find the master joint (longest travel time, not just distance)
        master_time = 0.0
        joint_profiles: list[Optional[SCurveProfile]] = [None] * len(deltas)

        for j, delta in enumerate(deltas):
            if delta == 0:
                continue
            cfg = self.joints[j] if j < len(self.joints) else JointConfig()
            profile = self._compute_s_curve(cfg, abs(delta))
            joint_profiles[j] = profile
            if profile.total_time > master_time:
                master_time = profile.total_time

        if master_time == 0.0:
            return []

        # Generate segments for each joint, scaled to master time
        all_segments: list[Segment] = []
        for j, delta in enumerate(deltas):
            if delta == 0:
                continue
            profile = joint_profiles[j]
            if profile is None:
                continue

            direction = delta > 0
            segments = self._profile_to_segments(
                joint=j,
                direction=direction,
                abs_delta=abs(delta),
                profile=profile,
                target_time=master_time,
            )
            all_segments.extend(segments)

        return all_segments

    def _compute_s_curve(
        self, cfg: JointConfig, distance: int
    ) -> SCurveProfile:
        """Compute 7-segment S-curve profile for a given distance.

        Handles three cases:
        - Full profile: enough distance for all 7 phases
        - Reduced (5-segment): no cruise phase
        - Minimal (3-segment): no constant-accel phase either

        The profile ensures continuous acceleration (no jerk discontinuity)
        by using symmetric jerk phases.

        Args:
            cfg: Joint configuration with velocity/acceleration/jerk limits.
            distance: Absolute distance in steps.

        Returns:
            Computed SCurveProfile with phase durations and step counts.
        """
        v_max = cfg.v_max
        a_max = cfg.a_max
        j_max = cfg.j_max

        # Time to reach a_max at j_max (jerk phase duration)
        t_j = a_max / j_max

        # Velocity gained during one jerk phase
        v_jerk = 0.5 * j_max * t_j * t_j  # = a_max² / (2*j_max)

        # Time at constant acceleration to reach v_max
        # v_max = 2 * v_jerk + a_max * t_a
        # where t_a is the constant-accel duration
        v_remaining = v_max - 2.0 * v_jerk
        if v_remaining > 0:
            t_a = v_remaining / a_max
        else:
            # Can't reach a_max before hitting v_max — reduce t_j
            t_j = math.sqrt(v_max / j_max)
            t_a = 0.0
            v_jerk = 0.5 * j_max * t_j * t_j

        # Distance consumed by accel and decel (symmetric)
        # Accel distance: jerk-up + const-accel + jerk-down
        d_jerk_up = (1.0 / 6.0) * j_max * t_j**3
        d_const_accel = v_jerk * t_a + 0.5 * a_max * t_a**2
        v_after_accel = v_jerk + a_max * t_a
        d_jerk_down = v_after_accel * t_j + 0.5 * a_max * t_j**2 - (1.0 / 6.0) * j_max * t_j**3
        d_accel = d_jerk_up + d_const_accel + d_jerk_down
        d_decel = d_accel  # Symmetric

        # Distance available for cruise
        d_cruise = distance - d_accel - d_decel

        if d_cruise < 0:
            # Not enough distance to reach v_max — reduce peak velocity
            # Binary search for achievable v_peak
            v_peak = self._find_peak_velocity(cfg, distance)
            return self._build_reduced_profile(cfg, distance, v_peak)

        # Full 7-segment profile
        v_peak = v_max
        t_cruise = d_cruise / v_peak if v_peak > 0 else 0.0

        # Build phase list: (duration_seconds, step_count)
        phases: list[tuple[float, int]] = []

        # Phase 1: Jerk up
        steps_p1 = max(1, round(d_jerk_up))
        phases.append((t_j, steps_p1))

        # Phase 2: Constant acceleration
        steps_p2 = max(0, round(d_const_accel))
        phases.append((t_a, steps_p2))

        # Phase 3: Jerk down (accel → 0)
        steps_p3 = max(1, round(d_jerk_down))
        phases.append((t_j, steps_p3))

        # Phase 4: Cruise
        steps_p4 = max(0, round(d_cruise))
        phases.append((t_cruise, steps_p4))

        # Phase 5: Jerk down (decel increases) — mirror of phase 3
        phases.append((t_j, steps_p3))

        # Phase 6: Constant deceleration — mirror of phase 2
        phases.append((t_a, steps_p2))

        # Phase 7: Jerk up (decel → 0) — mirror of phase 1
        phases.append((t_j, steps_p1))

        # Reconcile rounding: adjust cruise phase steps
        total_assigned = sum(p[1] for p in phases)
        diff = distance - total_assigned
        # Apply correction to cruise phase (index 3)
        steps_p4_corrected = max(0, steps_p4 + diff)
        phases[3] = (t_cruise, steps_p4_corrected)

        total_time = sum(p[0] for p in phases)
        total_steps = sum(p[1] for p in phases)

        return SCurveProfile(
            phases=phases,
            v_peak=v_peak,
            a_peak=a_max,
            total_steps=total_steps,
            total_time=total_time,
        )

    def _find_peak_velocity(
        self, cfg: JointConfig, distance: int
    ) -> float:
        """Binary search for achievable peak velocity given distance constraint.

        When the move distance is too short to reach v_max, finds the
        highest velocity achievable while still having room to decelerate.

        Args:
            cfg: Joint configuration.
            distance: Available distance in steps.

        Returns:
            Peak velocity in steps/sec that fits within the distance.
        """
        v_low = 0.0
        v_high = cfg.v_max
        j_max = cfg.j_max
        a_max = cfg.a_max

        for _ in range(50):  # Convergence in ~50 iterations
            v_mid = (v_low + v_high) / 2.0
            d_needed = self._distance_for_velocity(v_mid, a_max, j_max)
            if d_needed <= distance:
                v_low = v_mid
            else:
                v_high = v_mid
            if (v_high - v_low) < 1.0:  # 1 step/sec precision
                break

        return v_low

    def _distance_for_velocity(
        self, v_target: float, a_max: float, j_max: float
    ) -> float:
        """Compute minimum distance to accelerate to v_target and decelerate to 0.

        Used by the binary search to find achievable peak velocity.

        Args:
            v_target: Target peak velocity (steps/sec).
            a_max: Maximum acceleration (steps/sec²).
            j_max: Maximum jerk (steps/sec³).

        Returns:
            Total distance in steps for accel + decel (no cruise).
        """
        # Time for jerk phase
        t_j = min(a_max / j_max, math.sqrt(v_target / j_max))

        # Velocity from jerk phases alone
        v_jerk = 0.5 * j_max * t_j * t_j

        # If jerk phases alone exceed v_target, no constant-accel phase
        if 2.0 * v_jerk >= v_target:
            t_j = math.sqrt(v_target / j_max)
            # Distance for accel = 2 * jerk phase distance (triangular)
            d_accel = (2.0 / 3.0) * j_max * t_j**3
        else:
            # Constant accel time
            t_a = (v_target - 2.0 * v_jerk) / a_max
            d_jerk_up = (1.0 / 6.0) * j_max * t_j**3
            d_const_accel = v_jerk * t_a + 0.5 * a_max * t_a**2
            v_after = v_jerk + a_max * t_a
            d_jerk_down = v_after * t_j + 0.5 * a_max * t_j**2 - (1.0 / 6.0) * j_max * t_j**3
            d_accel = d_jerk_up + d_const_accel + d_jerk_down

        # Symmetric decel
        return 2.0 * d_accel

    def _build_reduced_profile(
        self, cfg: JointConfig, distance: int, v_peak: float
    ) -> SCurveProfile:
        """Build a reduced S-curve profile (3 or 5 segments) for short moves.

        When distance is too short for full 7-segment profile, this builds
        a profile without a cruise phase and possibly without constant
        acceleration phases.

        Args:
            cfg: Joint configuration.
            distance: Total distance in steps.
            v_peak: Achievable peak velocity.

        Returns:
            Reduced SCurveProfile.
        """
        j_max = cfg.j_max
        a_max = cfg.a_max

        t_j = min(a_max / j_max, math.sqrt(v_peak / j_max))
        v_jerk = 0.5 * j_max * t_j * t_j

        phases: list[tuple[float, int]] = []

        if 2.0 * v_jerk >= v_peak:
            # 3-segment profile: jerk-up, jerk-down (accel), then mirror
            # Only jerk phases, no constant acceleration
            t_j_actual = math.sqrt(v_peak / j_max)
            d_jerk = (1.0 / 6.0) * j_max * t_j_actual**3

            # 3 accel phases become just the jerk portions
            steps_jerk = max(1, round(d_jerk))
            half_steps = distance // 2
            mid_steps = distance - 2 * half_steps

            # Phase 1: Jerk up (accel)
            phases.append((t_j_actual, half_steps))
            # Phase 2: No constant accel
            phases.append((0.0, 0))
            # Phase 3: Jerk down (accel → 0)
            phases.append((t_j_actual, mid_steps if mid_steps > 0 else 0))
            # Phase 4: No cruise
            phases.append((0.0, 0))
            # Phase 5: Jerk down (decel)
            phases.append((t_j_actual, 0))
            # Phase 6: No constant decel
            phases.append((0.0, 0))
            # Phase 7: Jerk up (decel → 0)
            phases.append((t_j_actual, half_steps))

            # Rebalance steps for 3-segment: accel ramp, decel ramp
            total_assigned = sum(p[1] for p in phases)
            if total_assigned != distance:
                phases[0] = (phases[0][0], distance // 2)
                phases[6] = (phases[6][0], distance - distance // 2)
                # Zero out middle phases
                for idx in [1, 2, 3, 4, 5]:
                    phases[idx] = (phases[idx][0], 0)

        else:
            # 5-segment profile: has constant accel but no cruise
            t_a = (v_peak - 2.0 * v_jerk) / a_max
            d_jerk_up = (1.0 / 6.0) * j_max * t_j**3
            d_const_accel = v_jerk * t_a + 0.5 * a_max * t_a**2
            v_after = v_jerk + a_max * t_a
            d_jerk_down = v_after * t_j + 0.5 * a_max * t_j**2 - (1.0 / 6.0) * j_max * t_j**3

            steps_p1 = max(1, round(d_jerk_up))
            steps_p2 = max(0, round(d_const_accel))
            steps_p3 = max(1, round(d_jerk_down))

            # Phase 1: Jerk up
            phases.append((t_j, steps_p1))
            # Phase 2: Constant accel
            phases.append((t_a, steps_p2))
            # Phase 3: Jerk down
            phases.append((t_j, steps_p3))
            # Phase 4: No cruise
            phases.append((0.0, 0))
            # Phase 5: Mirror of phase 3
            phases.append((t_j, steps_p3))
            # Phase 6: Mirror of phase 2
            phases.append((t_a, steps_p2))
            # Phase 7: Mirror of phase 1
            phases.append((t_j, steps_p1))

            # Reconcile rounding
            total_assigned = sum(p[1] for p in phases)
            diff = distance - total_assigned
            # Distribute correction across phases
            if diff != 0 and steps_p2 > 0:
                phases[1] = (t_a, max(0, steps_p2 + diff // 2))
                phases[5] = (t_a, max(0, steps_p2 + diff - diff // 2))

        total_time = sum(p[0] for p in phases)
        total_steps = sum(p[1] for p in phases)

        return SCurveProfile(
            phases=phases,
            v_peak=v_peak,
            a_peak=min(a_max, j_max * t_j),
            total_steps=total_steps,
            total_time=total_time,
        )

    def _profile_to_segments(
        self,
        joint: int,
        direction: bool,
        abs_delta: int,
        profile: SCurveProfile,
        target_time: float,
    ) -> list[Segment]:
        """Convert an S-curve profile into MCU segments.

        Each non-zero phase becomes one Segment with start/end intervals
        computed from the velocity at phase boundaries.

        If this joint's profile is shorter than target_time, segments are
        time-stretched proportionally to synchronize with the master joint.

        Args:
            joint: Joint index.
            direction: True for positive, False for negative.
            abs_delta: Absolute step count for this joint.
            profile: Computed S-curve profile.
            target_time: Total time this move should take (from master joint).

        Returns:
            List of Segment objects for this joint.
        """
        if profile.total_time <= 0 or profile.total_steps <= 0:
            return []

        # Time stretch factor for synchronization
        stretch = target_time / profile.total_time if profile.total_time > 0 else 1.0

        segments: list[Segment] = []
        # Compute velocity at each phase boundary
        # Phase velocities (approximate from profile shape):
        #   Start of move: v=0
        #   End of phase 1 (jerk up): v ≈ v_peak * fraction
        #   End of phase 3: v = v_peak
        #   Phase 4 cruise: v = v_peak
        #   End of phase 7: v = 0
        v_peak = profile.v_peak / stretch  # Adjusted for time stretch

        # Simplified velocity at phase boundaries
        # Phase boundaries: 0, v1, v2, v_peak, v_peak, v5, v6, 0
        phase_end_velocities = self._compute_phase_velocities(profile, stretch)

        v_prev = 0.0
        for idx, (duration, step_count) in enumerate(profile.phases):
            if step_count <= 0 or duration <= 0:
                v_prev = phase_end_velocities[idx]
                continue

            v_end = phase_end_velocities[idx]
            actual_duration = duration * stretch

            # Convert velocities to intervals (µs between steps)
            start_interval = self._velocity_to_interval(v_prev)
            end_interval = self._velocity_to_interval(v_end)

            segments.append(Segment(
                joint=joint,
                direction=direction,
                step_count=step_count,
                start_interval=start_interval,
                end_interval=end_interval,
                curve_type=CurveType.SINUSOIDAL,
            ))

            v_prev = v_end

        return segments

    def _compute_phase_velocities(
        self, profile: SCurveProfile, stretch: float
    ) -> list[float]:
        """Compute velocity at the end of each S-curve phase.

        Uses the symmetric structure of the 7-segment profile:
        - Phases 1-3 accelerate to v_peak
        - Phase 4 maintains v_peak
        - Phases 5-7 decelerate to 0

        Args:
            profile: The S-curve profile.
            stretch: Time stretch factor.

        Returns:
            List of 7 velocities (one per phase end).
        """
        v_peak = profile.v_peak / stretch

        # Approximate velocity distribution based on phase step ratios
        total_accel_steps = sum(
            profile.phases[i][1] for i in range(3)
        )

        if total_accel_steps <= 0:
            return [v_peak] * 7

        # Phase 1 end velocity (after jerk-up)
        p1_steps = profile.phases[0][1]
        p2_steps = profile.phases[1][1]
        p3_steps = profile.phases[2][1]

        # Approximate: velocity grows quadratically in jerk phase,
        # linearly in const-accel phase
        v1 = v_peak * (p1_steps / total_accel_steps) * 0.5 if total_accel_steps > 0 else 0
        v2 = v1 + v_peak * (p2_steps / total_accel_steps) if total_accel_steps > 0 else v_peak * 0.5
        v3 = v_peak  # End of accel = peak

        # Symmetric decel
        v5 = v2  # Mirror of v2
        v6 = v1  # Mirror of v1
        v7 = 0.0

        return [v1, v2, v3, v_peak, v5, v6, v7]

    @staticmethod
    def _velocity_to_interval(velocity: float) -> int:
        """Convert velocity (steps/sec) to step interval (microseconds).

        Args:
            velocity: Velocity in steps per second.

        Returns:
            Interval in microseconds, clamped to [MIN_INTERVAL_US, MAX_INTERVAL_US].
        """
        if velocity <= 0:
            return MAX_INTERVAL_US
        interval = int(1_000_000.0 / velocity)
        return max(MIN_INTERVAL_US, min(MAX_INTERVAL_US, interval))

    def plan_move_with_lookahead(
        self,
        current_pos: list[int],
        target_pos: list[int],
    ) -> Optional[list[Segment]]:
        """Plan a move through the lookahead queue for junction optimization.

        Adds the move to the lookahead buffer and returns segments for
        the oldest ready move (if one is available). Call flush_lookahead()
        when no more moves are expected to get remaining segments.

        Args:
            current_pos: Current position for each joint (steps).
            target_pos: Target position for each joint (steps).

        Returns:
            Segments for the oldest ready move, or None if buffering.
        """
        deltas = [
            target_pos[i] - current_pos[i]
            for i in range(min(len(current_pos), len(target_pos)))
        ]

        # Determine max velocity for this move (based on longest joint)
        max_v = 0.0
        for j, d in enumerate(deltas):
            if d != 0:
                cfg = self.joints[j] if j < len(self.joints) else JointConfig()
                max_v = max(max_v, cfg.v_max)

        move = Move(
            target=list(target_pos),
            delta=deltas,
            entry_velocity=max_v,
            exit_velocity=max_v,
        )

        ready_move = self.lookahead.add_move(move)
        if ready_move is not None:
            # Plan the ready move using its entry/exit velocities
            return self._plan_move_with_velocities(current_pos, ready_move)
        return None

    def flush_lookahead(self, current_pos: list[int]) -> list[list[Segment]]:
        """Flush all remaining moves from the lookahead queue.

        Called when no more moves are expected (e.g., end of sequence,
        timeout waiting for next jog). The last move decelerates to zero.

        Args:
            current_pos: Current position for planning reference.

        Returns:
            List of segment lists, one per flushed move.
        """
        remaining_moves = self.lookahead.flush()
        all_segments: list[list[Segment]] = []
        pos = list(current_pos)

        for move in remaining_moves:
            segments = self._plan_move_with_velocities(pos, move)
            all_segments.append(segments)
            pos = move.target

        return all_segments

    def _plan_move_with_velocities(
        self, current_pos: list[int], move: Move
    ) -> list[Segment]:
        """Plan segments for a move respecting entry/exit velocity constraints.

        When entry_velocity > 0, the first segment starts at the entry speed
        instead of zero. When exit_velocity > 0, the last segment ends at
        exit speed instead of zero (for smooth junction with next move).

        Args:
            current_pos: Starting position.
            move: Move with entry/exit velocity constraints.

        Returns:
            List of segments for this move.
        """
        # For now, use the standard plan_move which always starts/stops at zero.
        # Junction velocity integration modifies the first/last segment intervals.
        segments = self.plan_move(current_pos, move.target)

        if not segments:
            return segments

        # Apply entry velocity: modify first segment's start_interval
        if move.entry_velocity > 0:
            entry_interval = self._velocity_to_interval(move.entry_velocity)
            for seg in segments:
                # Only modify the first segment per joint
                if seg.start_interval > entry_interval:
                    seg.start_interval = entry_interval
                break  # Only first segment

        # Apply exit velocity: modify last segment's end_interval
        if move.exit_velocity > 0:
            exit_interval = self._velocity_to_interval(move.exit_velocity)
            for seg in reversed(segments):
                if seg.end_interval > exit_interval:
                    seg.end_interval = exit_interval
                break  # Only last segment

        return segments
