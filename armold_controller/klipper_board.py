"""
KlipperBoard — Moonraker API client for Klipper-based motion control.

Replaces the SerialBoard class for Klipper-based setups. Communicates
exclusively with Moonraker (HTTP/WebSocket) on localhost — never opens
the MCU serial port directly. Klippy owns the serial connection.

Architecture:
    armold_controller (this module)
        → Moonraker HTTP (localhost:7125) for G-code commands
        → Moonraker WebSocket (localhost:7125/websocket) for status subscriptions
            → Klippy (motion planning)
                → BTT Octopus MAX EZ MCU (step pulse generation)

GCODE_AXIS mapping (Klipper reserves X/Y/Z/E/F/N):
    W = Linear Rail (stepper_x, Motor-1)
    A = J0 Base (stepper_y, Motor-2)
    B = J1 Shoulder (stepper_z, Motor-3)
    C = J2 Elbow (stepper_a, Motor-4)
    D = J3 Wrist Pitch (stepper_b, Motor-5)
    H = J4 Wrist Roll (stepper_c, Motor-6)
    U = J5 Wrist Yaw (stepper_u, Motor-7)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

logger = logging.getLogger(__name__)

# Stepper names in Klipper config order
STEPPER_NAMES: list[str] = [
    "stepper_x",  # Rail
    "stepper_y",  # J0 Base
    "stepper_z",  # J1 Shoulder
    "stepper_a",  # J2 Elbow
    "stepper_b",  # J3 Wrist Pitch
    "stepper_c",  # J4 Wrist Roll
    "stepper_u",  # J5 Wrist Yaw
]

# GCODE_AXIS letter for each stepper (used in coordinated G1 moves)
GCODE_AXIS_MAP: list[str] = ["W", "A", "B", "C", "D", "H", "U"]

# Joint names for human-readable messages
JOINT_NAMES: list[str] = [
    "Rail",
    "Base",
    "Shoulder",
    "Elbow",
    "Wrist Pitch",
    "Wrist Roll",
    "Wrist Yaw",
]

# Number of joints (7-axis system)
NUM_JOINTS: int = 7


@dataclass(frozen=True)
class JointLimit:
    """Soft motion limit for a single joint or the linear rail.

    Represents the inclusive minimum and maximum commanded position
    allowed for one axis. Klipper's ``manual_stepper`` does not enforce
    position limits natively, so ``armold_controller`` clamps every
    target to these bounds before dispatching motion.

    Attributes:
        minimum: Lowest allowed commanded position (mm for the rail,
            degrees for rotary joints).
        maximum: Highest allowed commanded position (same units).
        units: Unit label used only for logging/diagnostics ("mm"/"deg").
    """

    minimum: float
    maximum: float
    units: str = "deg"


# Per-joint soft limits, index-aligned with STEPPER_NAMES / joint indices.
#   index 0 = rail: 0..406 mm (16 in usable travel; homed to the near end).
#   indices 1-6 = arm joints, symmetric about the arm-home zero. Rotary
#   ranges match the arm's validated full-travel calibration
#   (J0 +/-180, J1 +/-90, J2 +/-150, J3 +/-120, J4 +/-90, J5 +/-180).
DEFAULT_SOFT_LIMITS: tuple[JointLimit, ...] = (
    JointLimit(0.0, 406.0, "mm"),   # 0 Rail (16 in usable)
    JointLimit(-180.0, 180.0),      # 1 J0 Base
    JointLimit(-90.0, 90.0),        # 2 J1 Shoulder
    JointLimit(-150.0, 150.0),      # 3 J2 Elbow
    JointLimit(-120.0, 120.0),      # 4 J3 Wrist Pitch
    JointLimit(-90.0, 90.0),        # 5 J4 Wrist Roll
    JointLimit(-180.0, 180.0),      # 6 J5 Wrist Yaw
)


class KlipperBoard:
    """Interface to Klipper motion controller via Moonraker API.

    Provides async methods for sending G-code, querying status, E-STOP,
    gripper control, and position polling via WebSocket subscription.

    All communication goes through Moonraker's HTTP API or WebSocket.
    The MCU serial port is exclusively owned by klippy.

    Attributes:
        moonraker_url: Base URL for Moonraker HTTP API.
        num_joints: Number of controlled joints (7).
        name: Board identifier for logging.
    """

    POLL_INTERVAL: float = 0.5
    RECONNECT_INTERVAL: float = 3.0
    REQUEST_TIMEOUT: float = 10.0

    def __init__(
        self,
        moonraker_url: str = "http://localhost:7125",
        name: str = "klipper",
        soft_limits: Optional[Sequence[JointLimit]] = None,
    ) -> None:
        """Initialize KlipperBoard (does not connect yet).

        Args:
            moonraker_url: Base URL for Moonraker HTTP API.
            name: Board identifier for logging.
            soft_limits: Optional per-joint soft limits, index-aligned with
                the joint indices (0=rail, 1..6=J0..J5). Must contain exactly
                ``NUM_JOINTS`` entries. Defaults to ``DEFAULT_SOFT_LIMITS``.

        Raises:
            ValueError: If ``soft_limits`` is provided but does not contain
                exactly ``NUM_JOINTS`` entries.
        """
        self.moonraker_url = moonraker_url.rstrip("/")
        self.name = name
        self.num_joints = NUM_JOINTS

        if soft_limits is None:
            self._soft_limits: tuple[JointLimit, ...] = DEFAULT_SOFT_LIMITS
        else:
            limits = tuple(soft_limits)
            if len(limits) != NUM_JOINTS:
                raise ValueError(
                    f"soft_limits must have exactly {NUM_JOINTS} entries, "
                    f"got {len(limits)}"
                )
            self._soft_limits = limits

        # State
        self._position: list[float] = [0.0] * NUM_JOINTS
        self._enabled: bool = False
        self._connected: bool = False
        self._ready: bool = False
        self._moving: bool = False
        self._axes_registered: bool = False
        self._gripper_angle: Optional[int] = None  # last commanded servo angle

        # HTTP session (aiohttp)
        self._session: Optional[Any] = None

        # WebSocket for status subscription
        self._ws: Optional[Any] = None
        self._ws_task: Optional[asyncio.Task[None]] = None
        self._poll_task: Optional[asyncio.Task[None]] = None

        # Callbacks
        self._state_callback: Optional[Callable[[], None]] = None
        self._halt_callback: Optional[Callable[[str, Optional[int]], None]] = None

    @property
    def position(self) -> list[float]:
        """Current position for all joints (degrees for arm, mm for rail).

        Returns:
            List of 7 position values.
        """
        return list(self._position)

    @property
    def pending_target(self) -> list[float]:
        """Pending target position (same as position for Klipper — no queue).

        Returns:
            List of 7 position values.
        """
        return list(self._position)

    @property
    def enabled(self) -> bool:
        """Whether motors are currently enabled.

        Returns:
            True if Klipper is in ready state.
        """
        return self._enabled

    @property
    def connected(self) -> bool:
        """Whether Moonraker API is reachable and Klipper is connected.

        Returns:
            True if connected.
        """
        return self._connected

    @property
    def position_certain(self) -> bool:
        """Whether position is confirmed accurate.

        Returns:
            True if Klipper is ready and position is known.
        """
        return self._ready

    @property
    def moving(self) -> bool:
        """Whether a move is currently in progress.

        Returns:
            True if Klipper reports toolhead is moving.
        """
        return self._moving

    @property
    def queue_depth(self) -> int:
        """Queue depth (always 0 — Klipper manages its own queue).

        Returns:
            0 (Klipper handles queueing internally).
        """
        return 0

    def set_halt_callback(self, callback: Callable[[str, Optional[int]], None]) -> None:
        """Set callback for halt events (E-STOP).

        Args:
            callback: Callable(source: str, joint: Optional[int]).
        """
        self._halt_callback = callback

    def set_state_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for state change events.

        Args:
            callback: Callable() invoked when position updates.
        """
        self._state_callback = callback

    async def connect(self) -> None:
        """Connect to Moonraker API and start status polling.

        Creates an aiohttp session and starts the background polling task.
        """
        try:
            import aiohttp
        except ImportError as e:
            logger.error(
                "aiohttp package not installed. Install with: pip install aiohttp"
            )
            raise ImportError(
                "aiohttp required for KlipperBoard. "
                "Install with: pip install aiohttp"
            ) from e

        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT)
        )

        # Start polling task
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("%s: Connecting to Moonraker at %s", self.name, self.moonraker_url)

    async def disconnect(self) -> None:
        """Disconnect from Moonraker and stop polling."""
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        if self._session is not None:
            await self._session.close()
            self._session = None

        self._connected = False
        self._ready = False
        logger.info("%s: Disconnected from Moonraker", self.name)

    async def send_gcode(self, cmd: str) -> bool:
        """Send a G-code command via Moonraker.

        Args:
            cmd: G-code string (e.g., 'G1 A90 B-30 F1200').

        Returns:
            True if command was accepted, False on error.
        """
        if self._session is None:
            logger.warning("%s: Cannot send G-code — not connected", self.name)
            return False

        try:
            async with self._session.post(
                f"{self.moonraker_url}/printer/gcode/script",
                json={"script": cmd},
            ) as resp:
                if resp.status == 200:
                    logger.debug("%s: G-code sent: %s", self.name, cmd)
                    return True
                body = await resp.text()
                logger.warning(
                    "%s: G-code failed (HTTP %d): %s — cmd: %s",
                    self.name,
                    resp.status,
                    body,
                    cmd,
                )
                return False
        except Exception as e:
            logger.error("%s: G-code send error: %s — cmd: %s", self.name, e, cmd)
            self._connected = False
            return False

    async def estop(self) -> bool:
        """Emergency stop — halts all steppers immediately.

        Sends POST to Moonraker's emergency_stop endpoint.
        After E-STOP, firmware_restart() is needed to recover.

        Returns:
            True if E-STOP was sent successfully.
        """
        if self._session is None:
            return False

        try:
            async with self._session.post(
                f"{self.moonraker_url}/printer/emergency_stop"
            ) as resp:
                success = resp.status == 200
                if success:
                    self._enabled = False
                    self._moving = False
                    logger.warning("%s: E-STOP triggered", self.name)
                    if self._halt_callback is not None:
                        self._halt_callback("user", None)
                return success
        except Exception as e:
            logger.error("%s: E-STOP failed: %s", self.name, e)
            return False

    async def firmware_restart(self) -> bool:
        """Restart MCU firmware after E-STOP.

        Required to recover from emergency stop state.

        Returns:
            True if restart command was accepted.
        """
        if self._session is None:
            return False

        try:
            async with self._session.post(
                f"{self.moonraker_url}/printer/firmware_restart"
            ) as resp:
                success = resp.status == 200
                if success:
                    logger.info("%s: Firmware restart initiated", self.name)
                return success
        except Exception as e:
            logger.error("%s: Firmware restart failed: %s", self.name, e)
            return False

    async def query_status(self) -> Optional[dict[str, Any]]:
        """Get current printer status including stepper positions.

        Queries Moonraker for manual_stepper objects and extracts
        commanded_pos from each stepper.

        Returns:
            Status dict with positions, or None on error.
        """
        if self._session is None:
            return None

        # Build query parameters for all manual steppers
        params: dict[str, str] = {}
        for stepper in STEPPER_NAMES:
            params[f"manual_stepper {stepper}"] = "commanded_pos"

        try:
            async with self._session.get(
                f"{self.moonraker_url}/printer/objects/query",
                params=params,
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data.get("result", {}).get("status", {})
        except Exception as e:
            logger.debug("%s: Status query failed: %s", self.name, e)
            return None

    @property
    def gripper_angle(self) -> Optional[int]:
        """Last commanded gripper servo angle (None if never set).

        Returns:
            The last angle sent via set_gripper, or None.
        """
        return self._gripper_angle

    async def set_gripper(self, angle: int) -> bool:
        """Set gripper servo angle (0-180 degrees).

        Args:
            angle: Target angle, clamped to 0-180.

        Returns:
            True if command was sent successfully.
        """
        angle = max(0, min(180, angle))
        success = await self.send_gcode(f"SET_SERVO SERVO=gripper ANGLE={angle}")
        if success:
            self._gripper_angle = angle
        return success

    async def goto_positions(
        self, positions: dict[int, float], speed: float = 15.0
    ) -> bool:
        """Move joints to absolute positions concurrently (e.g. waypoint return).

        Each joint is clamped to its soft limit and commanded to the absolute
        target via ``MANUAL_STEPPER MOVE`` with ``SYNC=0`` so all joints move
        together. This uses MANUAL_STEPPER (jog-compatible mode) rather than a
        coordinated G1, so it does not register/require G-code axes.

        NOTE: point-to-point with no path planning — the caller is responsible
        for ensuring the straight-line joint interpolation is collision-free.

        Args:
            positions: Dict of joint_index -> absolute target (mm rail, deg arm).
            speed: Move speed (mm/s or deg/s).

        Returns:
            True if all per-joint commands were accepted.
        """
        ok = True
        for joint, target in positions.items():
            if not (0 <= joint < NUM_JOINTS):
                continue
            clamped, was_clamped = self.clamp_target(joint, target)
            if was_clamped:
                limit = self._soft_limits[joint]
                logger.warning(
                    "%s: goto target %.3f%s for %s exceeds soft limit "
                    "[%.3f, %.3f]; clamped to %.3f",
                    self.name, target, limit.units, JOINT_NAMES[joint],
                    limit.minimum, limit.maximum, clamped,
                )
            stepper = STEPPER_NAMES[joint]
            cmd = (
                f"MANUAL_STEPPER STEPPER={stepper} "
                f"MOVE={clamped:.4f} SPEED={speed:.1f} ACCEL=300 SYNC=0"
            )
            if await self.send_gcode(cmd):
                self._position[joint] = clamped
            else:
                ok = False
        return ok

    def clamp_target(self, joint: int, target: float) -> tuple[float, bool]:
        """Clamp an absolute target position to the joint's soft limits.

        Klipper's ``manual_stepper`` does not enforce position limits, so this
        method is the sole guard preventing the arm/rail from being commanded
        past its mechanical range.

        Args:
            joint: Joint index (0=rail, 1..6=J0..J5).
            target: Requested absolute position (mm for the rail, degrees for
                rotary joints).

        Returns:
            A tuple ``(clamped, was_clamped)`` where ``clamped`` is the
            limit-constrained position and ``was_clamped`` is ``True`` when the
            requested target exceeded a soft limit.

        Raises:
            IndexError: If ``joint`` is outside ``0..NUM_JOINTS-1``.
        """
        limit = self._soft_limits[joint]
        clamped = min(limit.maximum, max(limit.minimum, target))
        return clamped, clamped != target

    async def jog_joint(self, joint: int, distance: float, speed: float = 10.0) -> bool:
        """Move a single joint by a relative distance, honoring soft limits.

        Computes the absolute target as ``current_position + distance`` (jog is
        relative), clamps it to the joint's soft limit, then dispatches an
        absolute ``MANUAL_STEPPER MOVE``. The locally tracked position is
        updated optimistically on success so rapid successive jogs accumulate
        (stack) correctly between status polls.

        Args:
            joint: Joint index (0=rail, 1=J0, 2=J1, ..., 6=J5).
            distance: Relative distance to move (mm for rail, degrees for arm
                joints). May be negative.
            speed: Movement speed (mm/s or degrees/s).

        Returns:
            True if the command was sent successfully, False on invalid joint
            index or transport error.
        """
        if joint < 0 or joint >= NUM_JOINTS:
            logger.warning("%s: Invalid joint index: %d", self.name, joint)
            return False

        target = self._position[joint] + distance
        clamped, was_clamped = self.clamp_target(joint, target)
        if was_clamped:
            limit = self._soft_limits[joint]
            logger.warning(
                "%s: jog target %.3f%s for %s exceeds soft limit "
                "[%.3f, %.3f]; clamped to %.3f",
                self.name,
                target,
                limit.units,
                JOINT_NAMES[joint],
                limit.minimum,
                limit.maximum,
                clamped,
            )

        stepper = STEPPER_NAMES[joint]
        cmd = (
            f"MANUAL_STEPPER STEPPER={stepper} "
            f"MOVE={clamped:.4f} SPEED={speed:.1f} ACCEL=300"
        )
        success = await self.send_gcode(cmd)
        if success:
            self._position[joint] = clamped
        return success

    async def move_coordinated(
        self,
        targets: dict[int, float],
        feed_rate: float = 1200.0,
    ) -> bool:
        """Move multiple joints simultaneously using coordinated G-code.

        Requires REGISTER_AXES macro to have been run first.

        Args:
            targets: Dict of joint_index -> target_position.
            feed_rate: Feed rate in units/min.

        Returns:
            True if command was sent successfully.
        """
        if not self._axes_registered:
            # Register axes on first coordinated move
            success = await self.register_axes()
            if not success:
                return False

        parts = ["G1"]
        for joint, target in targets.items():
            if 0 <= joint < NUM_JOINTS:
                clamped, was_clamped = self.clamp_target(joint, target)
                if was_clamped:
                    limit = self._soft_limits[joint]
                    logger.warning(
                        "%s: move target %.3f%s for %s exceeds soft limit "
                        "[%.3f, %.3f]; clamped to %.3f",
                        self.name,
                        target,
                        limit.units,
                        JOINT_NAMES[joint],
                        limit.minimum,
                        limit.maximum,
                        clamped,
                    )
                axis_letter = GCODE_AXIS_MAP[joint]
                parts.append(f"{axis_letter}{clamped:.4f}")
        parts.append(f"F{feed_rate:.0f}")

        cmd = " ".join(parts)
        return await self.send_gcode(cmd)

    async def register_axes(self) -> bool:
        """Register all manual steppers as G-code axes for coordinated motion.

        Runs the REGISTER_AXES macro defined in printer.cfg.

        Returns:
            True if registration was successful.
        """
        success = await self.send_gcode("REGISTER_AXES")
        if success:
            self._axes_registered = True
            logger.info("%s: G-code axes registered", self.name)
        return success

    async def set_home(self) -> bool:
        """Set current position as home (all zeros).

        Runs the SET_ARM_HOME macro defined in printer.cfg.

        Returns:
            True if command was successful.
        """
        success = await self.send_gcode("SET_ARM_HOME")
        if success:
            self._position = [0.0] * NUM_JOINTS
            logger.info("%s: Home position set", self.name)
        return success

    async def set_stepper_position(
        self, joint: int, position: float = 0.0
    ) -> bool:
        """Set the current position of a single stepper (manual home).

        Args:
            joint: Joint index (0-6).
            position: Position value to set.

        Returns:
            True if command was successful.
        """
        if joint < 0 or joint >= NUM_JOINTS:
            return False

        stepper = STEPPER_NAMES[joint]
        success = await self.send_gcode(
            f"MANUAL_STEPPER STEPPER={stepper} SET_POSITION={position:.4f}"
        )
        if success:
            self._position[joint] = position
        return success

    async def enable(self) -> bool:
        """Enable motors and energize all steppers so they hold position.

        In Klipper a ``manual_stepper`` only energizes when it receives a move,
        so it would otherwise be free to backdrive until commanded. This method
        actively energizes every stepper (``ENABLE=1``) so all joints hold their
        current position (at their configured hold current) immediately on
        enable, until a subsequent move. After E-STOP (klippy shutdown) a
        firmware restart is issued first.

        Returns:
            True if motors are enabled.
        """
        if not self._ready:
            # Try firmware restart first (recover from shutdown/E-STOP)
            await self.firmware_restart()
            await asyncio.sleep(2.0)

        # Energize every stepper so it actively holds position until a move.
        for stepper in STEPPER_NAMES:
            await self.send_gcode(f"MANUAL_STEPPER STEPPER={stepper} ENABLE=1")

        self._enabled = True
        logger.info("%s: Motors enabled (all steppers energized, holding)", self.name)
        return True

    async def disable(self) -> bool:
        """Disable all motors (let them free-spin).

        Sends M84 (disable steppers) to Klipper.

        Returns:
            True if command was successful.
        """
        success = await self.send_gcode("M84")
        if success:
            self._enabled = False
            logger.info("%s: Motors disabled", self.name)
        return success

    async def _poll_loop(self) -> None:
        """Background task: poll Moonraker for status at regular intervals.

        Updates position, connected state, and triggers callbacks.
        """
        while True:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug("%s: Poll error: %s", self.name, e)
                self._connected = False
                self._ready = False

            await asyncio.sleep(self.POLL_INTERVAL)

    async def _poll_once(self) -> None:
        """Single poll iteration: check server info and stepper positions."""
        if self._session is None:
            return

        # Check Moonraker/Klipper state
        try:
            async with self._session.get(
                f"{self.moonraker_url}/printer/info"
            ) as resp:
                if resp.status != 200:
                    self._connected = False
                    self._ready = False
                    return

                data = await resp.json()
                result = data.get("result", {})
                state = result.get("state", "")

                was_connected = self._connected
                self._connected = True
                self._ready = state == "ready"

                if not was_connected and self._connected:
                    logger.info(
                        "%s: Connected to Moonraker (Klipper state: %s)",
                        self.name,
                        state,
                    )
        except Exception:
            self._connected = False
            self._ready = False
            return

        # Query stepper positions if ready
        if self._ready:
            status = await self.query_status()
            if status is not None:
                self._update_positions(status)

    def _update_positions(self, status: dict[str, Any]) -> None:
        """Update internal position from Moonraker status response.

        Args:
            status: Dict from /printer/objects/query with manual_stepper data.
        """
        changed = False
        for i, stepper in enumerate(STEPPER_NAMES):
            key = f"manual_stepper {stepper}"
            if key in status:
                pos = status[key].get("commanded_pos")
                if pos is not None and pos != self._position[i]:
                    self._position[i] = float(pos)
                    changed = True

        if changed and self._state_callback is not None:
            self._state_callback()

    def get_state(self) -> dict[str, Any]:
        """Build the full state dict for broadcasting.

        Returns:
            State dictionary matching the WebSocket protocol.
        """
        return {
            "type": "state",
            "enabled": self._enabled,
            "position": self._position[:],
            "pending_target": self._position[:],
            "speed": 0,
            "connected": {self.name: self._connected},
            "position_certain": self._ready,
            "queue_depth": 0,
            "moving": self._moving,
            "klipper_ready": self._ready,
            "axes_registered": self._axes_registered,
        }
