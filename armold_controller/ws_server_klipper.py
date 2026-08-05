"""
KlipperWebSocketServer — asyncio WebSocket server for the Klipper backend.

Routes WebSocket JSON commands through KlipperBoard (Moonraker API)
instead of the legacy MotionManager/SerialBoard path. Maintains the
same client-facing JSON protocol so the web UI works unchanged.

Protocol (unchanged from serial backend):
    Client → Server:
        {"cmd": "enable"}
        {"cmd": "disable"}
        {"cmd": "jog", "joint": 0, "delta": 5.0}
        {"cmd": "move", "target": [0, 90, -30, 70, 50, 0, 0]}
        {"cmd": "move_cartesian", "x": 150, "y": 0, "z": 300,
         "roll": 0, "pitch": 90, "yaw": 0, "speed": 15}
        {"cmd": "estop"}
        {"cmd": "set_home"}
        {"cmd": "gripper", "angle": 90}
        {"cmd": "get_state"}

    Server → Client:
        {"type": "state", ...}
        {"type": "halt", ...}
        {"type": "ack", ...}
        {"type": "error", ...}
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from armold_controller.ik_solver import NUM_ARM_JOINTS, ArmIK, CartesianTarget
from armold_controller.klipper_board import (
    JOINT_NAMES,
    NUM_JOINTS,
    KlipperBoard,
)
from armold_controller.waypoints import WaypointStore

logger = logging.getLogger(__name__)


class KlipperWebSocketServer:
    """Asyncio WebSocket server routing commands through KlipperBoard.

    Supports multiple clients, periodic state broadcasts, and the
    same JSON protocol as the serial backend WebSocket server.

    Attributes:
        host: Bind address.
        port: Bind port.
        klipper_board: KlipperBoard instance.
        broadcast_hz: State broadcast frequency in Hz.
    """

    def __init__(
        self,
        host: str,
        port: int,
        klipper_board: KlipperBoard,
        broadcast_hz: float = 2.0,
        waypoint_store: WaypointStore | None = None,
        arm_ik: ArmIK | None = None,
    ) -> None:
        """Initialize WebSocket server (does not start listening yet).

        Args:
            host: Bind address (e.g., '0.0.0.0').
            port: Bind port (e.g., 9090).
            klipper_board: KlipperBoard instance.
            broadcast_hz: State broadcast frequency.
            waypoint_store: Optional WaypointStore for save/goto/delete of
                named arm poses. If None, waypoint commands return an error.
            arm_ik: Optional ArmIK kinematics engine used for Cartesian moves
                and end-effector pose reporting. If None, a default
                :class:`ArmIK` (proportional-estimate geometry) is created.
        """
        self.host = host
        self.port = port
        self.klipper_board = klipper_board
        self.broadcast_hz = broadcast_hz
        self.waypoint_store = waypoint_store
        self.arm_ik: ArmIK = arm_ik if arm_ik is not None else ArmIK()

        self._clients: set[Any] = set()
        self._server: Any | None = None
        self._broadcast_task: asyncio.Task[None] | None = None

        # Register halt callback on klipper board
        self.klipper_board.set_halt_callback(self._on_halt)

    async def start(self) -> None:
        """Start the WebSocket server and state broadcast task."""
        try:
            import websockets
        except ImportError:
            logger.error(
                "websockets package not installed. Install with: pip install websockets"
            )
            raise

        self._server = await websockets.serve(self._handle_client, self.host, self.port)
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())

    async def stop(self) -> None:
        """Stop the WebSocket server and broadcast task."""
        if self._broadcast_task is not None:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass

        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

        for ws in list(self._clients):
            await ws.close()
        self._clients.clear()

    async def _handle_client(self, websocket: Any) -> None:
        """Handle a single WebSocket client connection.

        Args:
            websocket: WebSocket connection instance.
        """
        self._clients.add(websocket)
        remote = websocket.remote_address
        logger.info("Client connected: %s", remote)

        # Send initial state
        await self._send(websocket, self._state_message())

        # Send current waypoint list so the UI can populate on connect
        if self.waypoint_store is not None:
            await self._send(websocket, self._waypoints_message())

        try:
            async for raw_message in websocket:
                await self._handle_message(websocket, raw_message)
        except Exception as e:  # noqa: BLE001 - must not crash server
            logger.debug("Client %s disconnected: %s", remote, e)
        finally:
            self._clients.discard(websocket)
            logger.info("Client disconnected: %s", remote)

    async def _handle_message(self, websocket: Any, raw: str) -> None:
        """Parse and dispatch a single client message.

        Args:
            websocket: Source WebSocket connection.
            raw: Raw message string.
        """
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Malformed message from %s: %s", websocket.remote_address, e)
            await self._send(
                websocket,
                {
                    "type": "error",
                    "message": f"Invalid JSON: {e}",
                },
            )
            return

        cmd = msg.get("cmd")
        if cmd is None:
            await self._send(
                websocket,
                {
                    "type": "error",
                    "message": "Missing 'cmd' field",
                },
            )
            return

        try:
            await self._dispatch(websocket, cmd, msg)
        except Exception as e:  # noqa: BLE001 - a bad command must not crash the server
            logger.error("Error handling cmd '%s': %s", cmd, e)
            await self._send(
                websocket,
                {
                    "type": "error",
                    "message": f"Internal error: {e}",
                },
            )

    async def _dispatch(self, websocket: Any, cmd: str, msg: dict[str, Any]) -> None:
        """Dispatch a parsed command to the appropriate handler.

        Args:
            websocket: Source WebSocket connection.
            cmd: Command string.
            msg: Full parsed message dict.
        """
        if cmd == "enable":
            success = await self.klipper_board.enable()
            await self._send(
                websocket,
                {
                    "type": "ack",
                    "cmd": "enable",
                    "status": "ok" if success else "error",
                },
            )

        elif cmd == "disable":
            success = await self.klipper_board.disable()
            await self._send(
                websocket,
                {
                    "type": "ack",
                    "cmd": "disable",
                    "status": "ok" if success else "error",
                },
            )

        elif cmd == "estop":
            await self.klipper_board.estop()

        elif cmd == "move":
            target = msg.get("target")
            if not isinstance(target, list):
                await self._send(
                    websocket,
                    {
                        "type": "error",
                        "message": "move requires 'target' array",
                    },
                )
                return
            # Build targets dict from list
            targets: dict[int, float] = {}
            for i, val in enumerate(target):
                if i < NUM_JOINTS and val is not None:
                    targets[i] = float(val)
            feed_rate = msg.get("feed_rate", 1200.0)
            success = await self.klipper_board.move_coordinated(
                targets, feed_rate=float(feed_rate)
            )
            await self._send(
                websocket,
                {
                    "type": "ack",
                    "cmd": "move",
                    "status": "ok" if success else "error",
                },
            )

        elif cmd == "jog":
            joint = msg.get("joint")
            delta = msg.get("delta")
            if joint is None or delta is None:
                await self._send(
                    websocket,
                    {
                        "type": "error",
                        "message": "jog requires 'joint' and 'delta'",
                    },
                )
                return
            # delta is in degrees/mm depending on joint
            speed = msg.get("speed", 10.0)
            success = await self.klipper_board.jog_joint(
                int(joint), float(delta), speed=float(speed)
            )
            await self._send(
                websocket,
                {
                    "type": "ack",
                    "cmd": "jog",
                    "status": "ok" if success else "error",
                },
            )

        elif cmd == "set_home":
            success = await self.klipper_board.set_home()
            await self._send(
                websocket,
                {
                    "type": "ack",
                    "cmd": "set_home",
                    "status": "ok" if success else "error",
                },
            )

        elif cmd == "gripper":
            angle = msg.get("angle")
            if angle is None:
                await self._send(
                    websocket,
                    {
                        "type": "error",
                        "message": "gripper requires 'angle'",
                    },
                )
                return
            success = await self.klipper_board.set_gripper(int(angle))
            await self._send(
                websocket,
                {
                    "type": "ack",
                    "cmd": "gripper",
                    "status": "ok" if success else "error",
                },
            )

        elif cmd == "register_axes":
            success = await self.klipper_board.register_axes()
            await self._send(
                websocket,
                {
                    "type": "ack",
                    "cmd": "register_axes",
                    "status": "ok" if success else "error",
                },
            )

        elif cmd == "firmware_restart":
            success = await self.klipper_board.firmware_restart()
            await self._send(
                websocket,
                {
                    "type": "ack",
                    "cmd": "firmware_restart",
                    "status": "ok" if success else "error",
                },
            )

        elif cmd == "move_cartesian":
            await self._handle_move_cartesian(websocket, msg)

        elif cmd == "get_state":
            await self._send(websocket, self._state_message())

        elif cmd == "save_waypoint":
            await self._handle_save_waypoint(websocket, msg)

        elif cmd == "list_waypoints":
            await self._send(websocket, self._waypoints_message())

        elif cmd == "goto_waypoint":
            await self._handle_goto_waypoint(websocket, msg)

        elif cmd == "delete_waypoint":
            await self._handle_delete_waypoint(websocket, msg)

        elif cmd == "goto_joints":
            await self._handle_goto_joints(websocket, msg)

        else:
            await self._send(
                websocket,
                {
                    "type": "error",
                    "message": f"Unknown command: {cmd}",
                },
            )

    def _state_message(self) -> dict[str, Any]:
        """Build the state broadcast, augmented with the end-effector FK pose.

        The arm joint angles (board indices 1..6 = J0..J5) are run through
        forward kinematics to report the current tool-tip pose in the arm base
        frame. The linear rail (index 0) is deliberately excluded from the
        kinematic chain.

        Returns:
            The board state dict with an added ``end_effector`` key mapping to
            ``{x, y, z, roll, pitch, yaw}`` (mm/degrees), or ``None`` under that
            key when FK could not be computed.
        """
        state = self.klipper_board.get_state()
        end_effector: dict[str, float] | None = None
        try:
            arm_angles = self.klipper_board.position[1 : 1 + NUM_ARM_JOINTS]
            if len(arm_angles) == NUM_ARM_JOINTS:
                pose = self.arm_ik.fk(arm_angles)
                end_effector = {
                    "x": pose.x,
                    "y": pose.y,
                    "z": pose.z,
                    "roll": pose.roll,
                    "pitch": pose.pitch,
                    "yaw": pose.yaw,
                }
        except Exception as e:  # noqa: BLE001 - FK is best-effort for telemetry
            logger.debug("FK for state broadcast failed: %s", e)
        state["end_effector"] = end_effector
        return state

    async def _handle_goto_joints(self, websocket: Any, msg: dict[str, Any]) -> None:
        """Move joints to absolute positions (keeps daemon position in sync).

        This command is the preferred way for external tools (e.g. the pick
        orchestrator) to command absolute joint targets without bypassing the
        daemon's internal position tracking. Unlike the Moonraker-direct
        ``col_move`` workaround, this updates ``_position`` on the board.

        Message format:
            {"cmd": "goto_joints", "joints": {0: rail_mm, 1: j0_deg, ...},
             "speed": 15.0}
        OR:
            {"cmd": "goto_joints", "target": [rail, j0, j1, j2, j3, j4, j5],
             "speed": 15.0}

        Args:
            websocket: Source WebSocket connection.
            msg: Parsed message dict.
        """
        speed = msg.get("speed", 15.0)

        # Accept either dict or list format
        joints_raw = msg.get("joints")
        target_raw = msg.get("target")

        targets: dict[int, float] = {}
        if isinstance(joints_raw, dict):
            for k, v in joints_raw.items():
                targets[int(k)] = float(v)
        elif isinstance(target_raw, list):
            for i, val in enumerate(target_raw):
                if i < NUM_JOINTS and val is not None:
                    targets[i] = float(val)
        else:
            await self._send(
                websocket,
                {
                    "type": "error",
                    "message": "goto_joints requires 'joints' dict or 'target' list",
                },
            )
            return

        success = await self.klipper_board.goto_positions(targets, speed=float(speed))
        await self._send(
            websocket,
            {
                "type": "ack",
                "cmd": "goto_joints",
                "status": "ok" if success else "error",
                "position": self.klipper_board.position,
            },
        )

    async def _handle_move_cartesian(self, websocket: Any, msg: dict[str, Any]) -> None:
        """Solve IK for a Cartesian tool-tip target and move the arm joints.

        The target is expressed in the arm base frame anchored at the rail
        carriage. The linear rail (joint 0) is NOT moved — it is a separate
        gross-positioning axis. On an unreachable target (or one requiring
        joint-limit violation) no motion is commanded and an error is returned.

        On success the six arm joints (board indices 1..6) are commanded to the
        IK solution via ``goto_positions`` and an ack is sent containing the
        solved joint angles, the achieved end-effector pose, and the residual
        position/orientation errors.

        Args:
            websocket: Source WebSocket connection.
            msg: Message with numeric ``x``/``y``/``z`` (mm), optional
                ``roll``/``pitch``/``yaw`` (degrees), and optional ``speed``
                (degrees per second, default 15.0).
        """
        x_raw = msg.get("x")
        y_raw = msg.get("y")
        z_raw = msg.get("z")
        if x_raw is None or y_raw is None or z_raw is None:
            await self._send(
                websocket,
                {
                    "type": "error",
                    "message": "move_cartesian requires numeric 'x', 'y', 'z'",
                },
            )
            return

        def _opt(key: str) -> float | None:
            value = msg.get(key)
            return None if value is None else float(value)

        try:
            target = CartesianTarget(
                x=float(x_raw),
                y=float(y_raw),
                z=float(z_raw),
                roll=_opt("roll"),
                pitch=_opt("pitch"),
                yaw=_opt("yaw"),
            )
        except (TypeError, ValueError) as e:
            await self._send(
                websocket,
                {"type": "error", "message": f"Invalid move_cartesian value: {e}"},
            )
            return

        # Seed the solver with the current arm configuration for continuity.
        seed = self.klipper_board.position[1 : 1 + NUM_ARM_JOINTS]
        seed_deg = list(seed) if len(seed) == NUM_ARM_JOINTS else None
        result = self.arm_ik.solve_ik(target, seed_deg=seed_deg)

        if not result.success:
            logger.info(
                "move_cartesian target (%.1f, %.1f, %.1f) rejected: %s",
                target.x,
                target.y,
                target.z,
                result.message,
            )
            await self._send(
                websocket,
                {
                    "type": "error",
                    "cmd": "move_cartesian",
                    "message": result.message,
                    "reachable": result.reachable,
                    "position_error_mm": result.position_error_mm,
                },
            )
            return

        speed = float(msg.get("speed", 15.0))
        # Map arm joints 0..5 (J0..J5) to board indices 1..6 (0 is the rail).
        positions = {i + 1: angle for i, angle in enumerate(result.joint_angles_deg)}
        success = await self.klipper_board.goto_positions(positions, speed=speed)
        achieved = self.arm_ik.fk(result.joint_angles_deg)
        await self._send(
            websocket,
            {
                "type": "ack",
                "cmd": "move_cartesian",
                "status": "ok" if success else "error",
                "joint_angles": result.joint_angles_deg,
                "end_effector": {
                    "x": achieved.x,
                    "y": achieved.y,
                    "z": achieved.z,
                    "roll": achieved.roll,
                    "pitch": achieved.pitch,
                    "yaw": achieved.yaw,
                },
                "position_error_mm": result.position_error_mm,
                "orientation_error_deg": result.orientation_error_deg,
            },
        )

    def _waypoints_message(self) -> dict[str, Any]:
        """Build the waypoints-list broadcast message.

        Returns:
            Dict of type 'waypoints' with a list of waypoint dicts (empty if
            no store is configured).
        """
        if self.waypoint_store is None:
            return {"type": "waypoints", "waypoints": []}
        return {
            "type": "waypoints",
            "waypoints": [w.to_dict() for w in self.waypoint_store.list()],
        }

    async def _handle_save_waypoint(self, websocket: Any, msg: dict[str, Any]) -> None:
        """Save the current arm pose (+ last gripper angle) as a named waypoint.

        Args:
            websocket: Source connection.
            msg: Message with a 'name' field.
        """
        if self.waypoint_store is None:
            await self._send(
                websocket, {"type": "error", "message": "Waypoints not available"}
            )
            return
        name = str(msg.get("name", "")).strip()
        if not name:
            await self._send(
                websocket, {"type": "error", "message": "save_waypoint requires 'name'"}
            )
            return
        try:
            self.waypoint_store.save(
                name,
                self.klipper_board.position,
                gripper=self.klipper_board.gripper_angle,
            )
        except ValueError as e:
            await self._send(
                websocket, {"type": "error", "message": f"Invalid waypoint: {e}"}
            )
            return
        await self._send(
            websocket,
            {"type": "ack", "cmd": "save_waypoint", "status": "ok", "name": name},
        )
        await self._broadcast(self._waypoints_message())

    async def _handle_goto_waypoint(self, websocket: Any, msg: dict[str, Any]) -> None:
        """Move the arm to a saved waypoint (per-joint absolute moves + gripper).

        Args:
            websocket: Source connection.
            msg: Message with a 'name' field and optional 'speed'.
        """
        if self.waypoint_store is None:
            await self._send(
                websocket, {"type": "error", "message": "Waypoints not available"}
            )
            return
        name = str(msg.get("name", "")).strip()
        wp = self.waypoint_store.get(name)
        if wp is None:
            await self._send(
                websocket, {"type": "error", "message": f"Unknown waypoint: {name}"}
            )
            return
        speed = float(msg.get("speed", 15.0))
        positions = {i: p for i, p in enumerate(wp.positions) if i < NUM_JOINTS}
        success = await self.klipper_board.goto_positions(positions, speed=speed)
        if wp.gripper is not None:
            await self.klipper_board.set_gripper(int(wp.gripper))
        await self._send(
            websocket,
            {
                "type": "ack",
                "cmd": "goto_waypoint",
                "status": "ok" if success else "error",
                "name": name,
            },
        )

    async def _handle_delete_waypoint(
        self, websocket: Any, msg: dict[str, Any]
    ) -> None:
        """Delete a named waypoint.

        Args:
            websocket: Source connection.
            msg: Message with a 'name' field.
        """
        if self.waypoint_store is None:
            await self._send(
                websocket, {"type": "error", "message": "Waypoints not available"}
            )
            return
        name = str(msg.get("name", "")).strip()
        removed = self.waypoint_store.delete(name)
        await self._send(
            websocket,
            {
                "type": "ack",
                "cmd": "delete_waypoint",
                "status": "ok" if removed else "error",
                "name": name,
            },
        )
        await self._broadcast(self._waypoints_message())

    def _on_halt(self, source: str, joint: int | None) -> None:
        """Callback from KlipperBoard on halt (E-STOP).

        Broadcasts halt message to all connected clients.

        Args:
            source: 'user' or 'collision'.
            joint: Affected joint index, or None.
        """
        if source == "collision" and joint is not None:
            joint_name = (
                JOINT_NAMES[joint] if joint < len(JOINT_NAMES) else f"Joint {joint}"
            )
            message = f"Collision detected on Joint {joint} ({joint_name})"
        else:
            message = "E-STOP activated"

        halt_msg = {
            "type": "halt",
            "source": source,
            "joint": joint,
            "position": self.klipper_board.position,
            "message": message,
        }

        # Schedule broadcast on the event loop
        try:
            loop = asyncio.get_running_loop()
            asyncio.ensure_future(self._broadcast(halt_msg), loop=loop)
        except RuntimeError:
            pass

    async def _broadcast_loop(self) -> None:
        """Periodically broadcast state to all connected clients."""
        interval = 1.0 / self.broadcast_hz
        while True:
            await asyncio.sleep(interval)
            if self._clients:
                await self._broadcast(self._state_message())

    async def _broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to all connected clients.

        Args:
            message: Dict to send as JSON.
        """
        if not self._clients:
            return
        data = json.dumps(message)
        disconnected: list[Any] = []
        for ws in list(self._clients):
            try:
                await ws.send(data)
            except Exception:  # noqa: BLE001 - drop any client that fails to receive
                disconnected.append(ws)
        for ws in disconnected:
            self._clients.discard(ws)

    async def _send(self, websocket: Any, message: dict[str, Any]) -> None:
        """Send a message to a single client.

        Args:
            websocket: Target WebSocket connection.
            message: Dict to send as JSON.
        """
        try:
            await websocket.send(json.dumps(message))
        except Exception:  # noqa: BLE001 - drop a client that fails to receive
            self._clients.discard(websocket)
