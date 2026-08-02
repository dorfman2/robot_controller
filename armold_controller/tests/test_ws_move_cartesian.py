"""
Integration tests for the ``move_cartesian`` WebSocket command.

These tests spin up a REAL :class:`KlipperWebSocketServer` (with a real
:class:`KlipperBoard` and a real :class:`ArmIK`) on a loopback port and drive it
with a REAL ``websockets`` client — no mocking. The KlipperBoard is not
connected to Moonraker, so motion G-code sends fail gracefully (the board has no
HTTP session); the tests therefore assert on the IK/protocol behaviour (pose
reporting, reachable/unreachable handling, joint mapping) rather than on actual
motion, which requires hardware.

Run standalone:
    ``.venv/bin/python -m armold_controller.tests.test_ws_move_cartesian``
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Callable
from typing import Any

sys.path.insert(0, ".")

import websockets

from armold_controller.ik_solver import ArmIK
from armold_controller.klipper_board import KlipperBoard
from armold_controller.ws_server_klipper import KlipperWebSocketServer

HOST: str = "127.0.0.1"
PORT: int = 8782
URI: str = f"ws://{HOST}:{PORT}"


async def _read_until(
    ws: Any, predicate: Callable[[dict[str, Any]], bool], timeout: float = 5.0
) -> dict[str, Any]:
    """Read messages until one satisfies ``predicate`` or ``timeout`` elapses.

    Args:
        ws: Connected client WebSocket.
        predicate: Returns True for the awaited message.
        timeout: Seconds to wait before giving up.

    Returns:
        The first matching message as a dict.

    Raises:
        asyncio.TimeoutError: If no matching message arrives in time.
    """

    async def _loop() -> dict[str, Any]:
        async for raw in ws:
            msg = json.loads(raw)
            if predicate(msg):
                return msg
        raise AssertionError("connection closed before matching message")

    return await asyncio.wait_for(_loop(), timeout)


async def _start_server() -> tuple[KlipperBoard, KlipperWebSocketServer]:
    """Start a server with a real (unconnected) board and IK engine.

    Returns:
        The board and server instances (caller must stop the server).
    """
    board = KlipperBoard()
    server = KlipperWebSocketServer(HOST, PORT, board, broadcast_hz=5.0)
    await server.start()
    return board, server


async def _test_initial_state_has_end_effector() -> None:
    """The initial state broadcast includes the FK end-effector pose."""
    _board, server = await _start_server()
    try:
        async with websockets.connect(URI) as ws:
            state = await _read_until(ws, lambda m: m.get("type") == "state")
            ee = state.get("end_effector")
            assert ee is not None, "state missing end_effector"
            # Board defaults to all-zero joints -> arm points straight up.
            assert abs(ee["x"]) < 1.0, f"x {ee['x']}"
            assert abs(ee["y"]) < 1.0, f"y {ee['y']}"
            assert abs(ee["z"] - 642.0) < 1.0, f"z {ee['z']}"
    finally:
        await server.stop()
    print("PASS: test_initial_state_has_end_effector")


async def _test_move_cartesian_unreachable() -> None:
    """An unreachable target returns an error flagged not reachable."""
    _board, server = await _start_server()
    try:
        async with websockets.connect(URI) as ws:
            await _read_until(ws, lambda m: m.get("type") == "state")
            await ws.send(
                json.dumps({"cmd": "move_cartesian", "x": 2000, "y": 0, "z": 0})
            )
            err = await _read_until(
                ws,
                lambda m: m.get("type") == "error" and m.get("cmd") == "move_cartesian",
            )
            assert err.get("reachable") is False, "expected reachable=False"
    finally:
        await server.stop()
    print("PASS: test_move_cartesian_unreachable")


async def _test_move_cartesian_reachable() -> None:
    """A reachable target yields an ack with six joint angles and a pose.

    The board is not connected to Moonraker, so the underlying motion command
    cannot succeed; this test asserts the IK/protocol contract (joint mapping,
    pose echo, low residual) which is independent of hardware.
    """
    _board, server = await _start_server()
    try:
        ik = ArmIK()
        pose = ik.fk([10.0, -20.0, 60.0, 40.0, 0.0, 0.0])
        async with websockets.connect(URI) as ws:
            await _read_until(ws, lambda m: m.get("type") == "state")
            await ws.send(
                json.dumps(
                    {
                        "cmd": "move_cartesian",
                        "x": pose.x,
                        "y": pose.y,
                        "z": pose.z,
                    }
                )
            )
            ack = await _read_until(
                ws,
                lambda m: m.get("type") == "ack" and m.get("cmd") == "move_cartesian",
            )
            assert len(ack["joint_angles"]) == 6, "expected 6 joint angles"
            assert ack.get("end_effector") is not None
            assert ack["position_error_mm"] <= 1.0, ack["position_error_mm"]
    finally:
        await server.stop()
    print("PASS: test_move_cartesian_reachable")


async def _test_move_cartesian_missing_coords() -> None:
    """A move_cartesian without x/y/z returns a validation error."""
    _board, server = await _start_server()
    try:
        async with websockets.connect(URI) as ws:
            await _read_until(ws, lambda m: m.get("type") == "state")
            await ws.send(json.dumps({"cmd": "move_cartesian", "x": 100}))
            err = await _read_until(ws, lambda m: m.get("type") == "error")
            assert "x" in err["message"] and "y" in err["message"]
    finally:
        await server.stop()
    print("PASS: test_move_cartesian_missing_coords")


def main() -> None:
    """Run all WebSocket move_cartesian integration tests sequentially."""
    tests = [
        _test_initial_state_has_end_effector,
        _test_move_cartesian_unreachable,
        _test_move_cartesian_reachable,
        _test_move_cartesian_missing_coords,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            asyncio.run(test_fn())
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
