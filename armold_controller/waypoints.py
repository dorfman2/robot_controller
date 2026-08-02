"""
Waypoint storage for saved robot-arm poses.

A waypoint is a named, absolute pose of the arm: one position value per joint
(mm for the linear rail, degrees for the rotary joints) plus an optional gripper
servo angle. Waypoints persist to a JSON file so they survive daemon restarts.

The store is intentionally decoupled from motion: it only holds pose data.
Executing a waypoint (moving the arm) is the caller's responsibility
(see KlipperBoard.goto_positions).
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Waypoint:
    """A saved arm pose.

    Attributes:
        name: Unique, human-readable waypoint name (non-empty).
        positions: Absolute position per joint, index-aligned with the joint
            order (0=rail mm, 1..6=J0..J5 degrees). Length must equal the
            store's ``num_joints``.
        gripper: Optional gripper servo angle (0-180), or None if not captured.
        created: Unix timestamp when the waypoint was created.
    """

    name: str
    positions: list[float]
    gripper: Optional[int] = None
    created: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the waypoint to a plain dict for JSON storage/transport.

        Returns:
            Dict with keys name, positions, gripper, created.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Waypoint":
        """Build a Waypoint from a stored/transported dict.

        Args:
            data: Dict with at least 'name' and 'positions'.

        Returns:
            A Waypoint instance.

        Raises:
            KeyError: If required keys are missing.
            ValueError: If positions are not numeric.
        """
        return cls(
            name=str(data["name"]),
            positions=[float(x) for x in data["positions"]],
            gripper=(None if data.get("gripper") is None else int(data["gripper"])),
            created=float(data.get("created", time.time())),
        )


class WaypointStore:
    """Persistent, name-keyed store of arm waypoints backed by a JSON file.

    Loads existing waypoints on construction and writes the full set to disk
    (atomically) on every mutation. Saving a waypoint with an existing name
    overwrites it.

    Attributes:
        path: Path to the backing JSON file.
        num_joints: Expected length of each waypoint's position list.
    """

    def __init__(self, path: str | Path, num_joints: int) -> None:
        """Initialize the store and load any existing waypoints from disk.

        Args:
            path: Backing JSON file path (created on first save if absent).
            num_joints: Required length of each waypoint's position list.
        """
        self.path = Path(path)
        self.num_joints = num_joints
        self._waypoints: dict[str, Waypoint] = {}
        self._load()

    def _load(self) -> None:
        """Load waypoints from the backing file, tolerating missing/corrupt data."""
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
            for entry in data.get("waypoints", []):
                wp = Waypoint.from_dict(entry)
                self._waypoints[wp.name] = wp
            logger.info(
                "Loaded %d waypoint(s) from %s", len(self._waypoints), self.path
            )
        except (json.JSONDecodeError, KeyError, ValueError, OSError) as e:
            logger.warning("Failed to load waypoints from %s: %s", self.path, e)

    def _write(self) -> None:
        """Atomically write all waypoints to the backing file."""
        payload = {
            "version": 1,
            "waypoints": [w.to_dict() for w in self.list()],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        os.replace(tmp, self.path)

    def save(
        self,
        name: str,
        positions: list[float],
        gripper: Optional[int] = None,
    ) -> Waypoint:
        """Create or overwrite a waypoint and persist to disk.

        Args:
            name: Waypoint name (non-empty after stripping whitespace).
            positions: Absolute position per joint; length must equal
                ``num_joints``.
            gripper: Optional gripper angle (0-180) to capture with the pose.

        Returns:
            The stored Waypoint.

        Raises:
            ValueError: If name is empty or positions length is wrong.
        """
        name = name.strip()
        if not name:
            raise ValueError("waypoint name must not be empty")
        if len(positions) != self.num_joints:
            raise ValueError(
                f"positions must have {self.num_joints} entries, "
                f"got {len(positions)}"
            )
        wp = Waypoint(
            name=name,
            positions=[float(p) for p in positions],
            gripper=(None if gripper is None else int(gripper)),
        )
        self._waypoints[name] = wp
        self._write()
        logger.info("Saved waypoint '%s'", name)
        return wp

    def list(self) -> list[Waypoint]:
        """Return all waypoints ordered by creation time (oldest first).

        Returns:
            List of Waypoint instances.
        """
        return sorted(self._waypoints.values(), key=lambda w: w.created)

    def get(self, name: str) -> Optional[Waypoint]:
        """Look up a waypoint by name.

        Args:
            name: Waypoint name.

        Returns:
            The Waypoint, or None if not found.
        """
        return self._waypoints.get(name.strip())

    def delete(self, name: str) -> bool:
        """Delete a waypoint by name and persist the change.

        Args:
            name: Waypoint name.

        Returns:
            True if a waypoint was removed, False if the name was not found.
        """
        name = name.strip()
        if name in self._waypoints:
            del self._waypoints[name]
            self._write()
            logger.info("Deleted waypoint '%s'", name)
            return True
        return False
