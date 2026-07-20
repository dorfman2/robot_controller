"""
WebSocketServer — asyncio WebSocket server for the Armold controller.

Handles multiple simultaneous clients, JSON protocol messages,
periodic state broadcasts, and graceful connect/disconnect without
affecting motor state.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional, Set

from armold_controller.motion_manager import MotionManager

logger = logging.getLogger(__name__)


class WebSocketServer:
    """Asyncio WebSocket server for the Armold motion controller.

    Supports multiple clients, periodic state broadcasts at configurable
    frequency, and JSON message protocol defined in the spec.

    Attributes:
        host: Bind address.
        port: Bind port.
        motion_manager: Reference to the motion manager.
        broadcast_hz: State broadcast frequency in Hz.
    """

    def __init__(
        self,
        host: str,
        port: int,
        motion_manager: MotionManager,
        broadcast_hz: float = 2.0,
    ) -> None:
        """Initialize WebSocket server (does not start listening yet).

        Args:
            host: Bind address (e.g., '0.0.0.0').
            port: Bind port (e.g., 9090).
            motion_manager: MotionManager instance.
            broadcast_hz: State broadcast frequency.
        """
        self.host = host
        self.port = port
        self.motion_manager = motion_manager
        self.broadcast_hz = broadcast_hz

        self._clients: Set[Any] = set()
        self._server: Optional[Any] = None
        self._broadcast_task: Optional[asyncio.Task[None]] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Register broadcast function on motion manager
        self.motion_manager.set_broadcast(self._broadcast_threadsafe)

    async def start(self) -> None:
        """Start the WebSocket server and state broadcast task."""
        try:
            import websockets
        except ImportError:
            logger.error(
                "websockets package not installed. Install with: pip install websockets"
            )
            raise

        self._loop = asyncio.get_running_loop()
        self._server = await websockets.serve(
            self._handle_client, self.host, self.port
        )
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

        # Close all client connections
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
        state = self.motion_manager.get_state()
        await self._send(websocket, state)

        try:
            async for raw_message in websocket:
                await self._handle_message(websocket, raw_message)
        except Exception as e:
            logger.debug("Client %s disconnected: %s", remote, e)
        finally:
            self._clients.discard(websocket)
            logger.info("Client disconnected: %s", remote)

    async def _handle_message(self, websocket: Any, raw: str) -> None:
        """Parse and dispatch a single client message.

        Malformed messages are logged and an error response sent to the
        offending client only. Never affects other clients or motor state.

        Args:
            websocket: Source WebSocket connection.
            raw: Raw message string.
        """
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Malformed message from %s: %s", websocket.remote_address, e)
            await self._send(websocket, {
                "type": "error",
                "message": f"Invalid JSON: {e}",
            })
            return

        cmd = msg.get("cmd")
        if cmd is None:
            await self._send(websocket, {
                "type": "error",
                "message": "Missing 'cmd' field",
            })
            return

        try:
            await self._dispatch(websocket, cmd, msg)
        except Exception as e:
            logger.error("Error handling cmd '%s': %s", cmd, e)
            await self._send(websocket, {
                "type": "error",
                "message": f"Internal error: {e}",
            })

    async def _dispatch(
        self, websocket: Any, cmd: str, msg: dict[str, Any]
    ) -> None:
        """Dispatch a parsed command to the appropriate handler.

        Args:
            websocket: Source WebSocket connection.
            cmd: Command string.
            msg: Full parsed message dict.
        """
        if cmd == "enable":
            self.motion_manager.enable()
            await self._send(websocket, {"type": "ack", "cmd": "enable", "status": "ok"})

        elif cmd == "disable":
            self.motion_manager.disable()
            await self._send(websocket, {"type": "ack", "cmd": "disable", "status": "ok"})

        elif cmd == "estop":
            self.motion_manager.estop()

        elif cmd == "move":
            target = msg.get("target")
            if not isinstance(target, list):
                await self._send(websocket, {
                    "type": "error",
                    "message": "move requires 'target' array",
                })
                return
            cmd_id = self.motion_manager.move_absolute(target)
            await self._send(websocket, {
                "type": "ack",
                "id": cmd_id,
                "status": "queued",
            })

        elif cmd == "jog":
            joint = msg.get("joint")
            delta = msg.get("delta")
            if joint is None or delta is None:
                await self._send(websocket, {
                    "type": "error",
                    "message": "jog requires 'joint' and 'delta'",
                })
                return
            cmd_id = self.motion_manager.jog(int(joint), int(delta))
            await self._send(websocket, {
                "type": "ack",
                "id": cmd_id,
                "status": "queued",
            })

        elif cmd == "set_speed":
            delay_us = msg.get("delay_us")
            if delay_us is None:
                await self._send(websocket, {
                    "type": "error",
                    "message": "set_speed requires 'delay_us'",
                })
                return
            self.motion_manager.set_speed(int(delay_us))
            await self._send(websocket, {
                "type": "ack",
                "cmd": "set_speed",
                "status": "ok",
                "speed": self.motion_manager.step_delay,
            })

        elif cmd == "set_home":
            self.motion_manager.set_home()
            await self._send(websocket, {"type": "ack", "cmd": "set_home", "status": "ok"})

        elif cmd == "go_home":
            cmd_id = self.motion_manager.go_home()
            await self._send(websocket, {
                "type": "ack",
                "id": cmd_id,
                "status": "queued",
            })

        elif cmd == "get_state":
            state = self.motion_manager.get_state()
            await self._send(websocket, state)

        else:
            await self._send(websocket, {
                "type": "error",
                "message": f"Unknown command: {cmd}",
            })

    async def _broadcast_loop(self) -> None:
        """Periodically broadcast state to all connected clients."""
        interval = 1.0 / self.broadcast_hz
        while True:
            await asyncio.sleep(interval)
            if self._clients:
                state = self.motion_manager.get_state()
                await self._broadcast(state)

    async def _broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to all connected clients.

        Failures on individual clients are logged and the client is removed.

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
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self._clients.discard(ws)

    def _broadcast_threadsafe(self, message: dict[str, Any]) -> None:
        """Thread-safe broadcast (called from serial threads).

        Schedules the broadcast on the asyncio event loop.

        Args:
            message: Dict to broadcast as JSON.
        """
        if self._loop is not None and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._broadcast(message), self._loop
            )

    async def _send(self, websocket: Any, message: dict[str, Any]) -> None:
        """Send a message to a single client.

        Args:
            websocket: Target WebSocket connection.
            message: Dict to send as JSON.
        """
        try:
            await websocket.send(json.dumps(message))
        except Exception:
            self._clients.discard(websocket)
