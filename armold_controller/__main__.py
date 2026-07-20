"""
Entry point for armold_controller daemon.

Usage:
    python -m armold_controller [--config CONFIG_PATH]

Starts the WebSocket server and serial board connections.
Handles SIGTERM/SIGINT for graceful shutdown.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sys
from pathlib import Path
from typing import Any

from armold_controller.motion_manager import MotionManager
from armold_controller.serial_board import SerialBoard
from armold_controller.ws_server import WebSocketServer

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG: dict[str, Any] = {
    "boards": {
        "einsy": {
            "port": "/dev/armold_einsy",
            "baud": 115200,
            "num_joints": 4,
            "enabled": True,
        },
        "ramps": {
            "port": "/dev/armold_ramps",
            "baud": 115200,
            "num_joints": 2,
            "enabled": False,
        },
    },
    "websocket": {
        "host": "0.0.0.0",
        "port": 9090,
    },
    "motion": {
        "step_delay": 20,
        "min_delay": 20,
        "max_delay": 5000,
        "state_broadcast_hz": 2.0,
    },
    "logging": {
        "level": "INFO",
        "format": "json",
    },
}


def setup_logging(config: dict[str, Any]) -> None:
    """Configure structured JSON logging to stdout.

    Args:
        config: Logging configuration dict with 'level' and 'format' keys.
    """
    level = getattr(logging, config.get("level", "INFO").upper(), logging.INFO)

    if config.get("format") == "json":
        formatter = logging.Formatter(
            '{"time":"%(asctime)s","level":"%(levelname)s",'
            '"module":"%(name)s","message":"%(message)s"}'
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger("armold_controller")
    root_logger.setLevel(level)
    root_logger.addHandler(handler)


def load_config(config_path: Path | None) -> dict[str, Any]:
    """Load configuration from JSON file, merging with defaults.

    Args:
        config_path: Path to JSON config file, or None for defaults.

    Returns:
        Merged configuration dictionary.
    """
    config = dict(DEFAULT_CONFIG)
    if config_path and config_path.exists():
        with open(config_path) as f:
            user_config = json.load(f)
        # Shallow merge per top-level key
        for key, value in user_config.items():
            if key in config and isinstance(config[key], dict) and isinstance(value, dict):
                config[key] = {**config[key], **value}
            else:
                config[key] = value
        logger.info("Loaded config from %s", config_path)
    return config


async def _health_check_loop(motion_manager: MotionManager, path: Path) -> None:
    """Write health check file every 10 seconds.

    External monitoring can check file mtime to verify the daemon is alive.

    Args:
        motion_manager: MotionManager instance for state info.
        path: Path to write health check file.
    """
    import time as _time

    while True:
        try:
            state = motion_manager.get_state()
            health = json.dumps({
                "alive": True,
                "timestamp": _time.time(),
                "connected": state["connected"],
                "enabled": state["enabled"],
                "queue_depth": state["queue_depth"],
            })
            path.write_text(health)
        except Exception:
            pass
        await asyncio.sleep(10.0)


async def run(config: dict[str, Any]) -> None:
    """Main async entry point. Starts boards, motion manager, and WebSocket server.

    Args:
        config: Full configuration dictionary.
    """
    shutdown_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown_event.set)

    # Create serial boards
    boards: dict[str, SerialBoard] = {}
    for name, board_cfg in config["boards"].items():
        if board_cfg.get("enabled", False):
            board = SerialBoard(
                name=name,
                port=board_cfg["port"],
                baud=board_cfg["baud"],
                num_joints=board_cfg["num_joints"],
            )
            boards[name] = board

    # Create motion manager
    motion_cfg = config["motion"]
    motion_manager = MotionManager(
        boards=boards,
        step_delay=motion_cfg["step_delay"],
        min_delay=motion_cfg["min_delay"],
        max_delay=motion_cfg["max_delay"],
    )

    # Create WebSocket server
    ws_cfg = config["websocket"]
    ws_server = WebSocketServer(
        host=ws_cfg["host"],
        port=ws_cfg["port"],
        motion_manager=motion_manager,
        broadcast_hz=motion_cfg["state_broadcast_hz"],
    )

    # Start boards (connect serial)
    for name, board in boards.items():
        board.start()
        logger.info("Started board: %s on %s", name, board.port)

    # Start WebSocket server
    await ws_server.start()
    logger.info(
        "WebSocket server listening on %s:%d", ws_cfg["host"], ws_cfg["port"]
    )

    # Start health check task
    health_task = asyncio.create_task(
        _health_check_loop(motion_manager, Path("/tmp/armold_health"))
    )

    # Wait for shutdown signal
    await shutdown_event.wait()
    logger.info("Shutdown signal received")

    # Graceful shutdown
    health_task.cancel()
    try:
        await health_task
    except asyncio.CancelledError:
        pass

    # Graceful shutdown
    await ws_server.stop()
    for name, board in boards.items():
        board.stop()
        logger.info("Stopped board: %s", name)

    logger.info("Armold controller stopped")


def main() -> None:
    """CLI entry point. Parses arguments and runs the async event loop."""
    parser = argparse.ArgumentParser(
        description="Armold motion controller daemon"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to JSON configuration file",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logging(config["logging"])

    logger.info("Starting Armold controller v0.1.0")
    asyncio.run(run(config))


if __name__ == "__main__":
    main()
