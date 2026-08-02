"""
Unit tests for WaypointStore (real filesystem, no mocking).

Each test uses a real temporary JSON file so persistence is exercised
end-to-end (save -> reload from disk -> verify).

Run standalone: ``python -m armold_controller.tests.test_waypoints``
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

from armold_controller.waypoints import Waypoint, WaypointStore

NUM_JOINTS = 7


def _tmp_path() -> Path:
    """Return a unique temp file path (not created) for a store."""
    d = tempfile.mkdtemp(prefix="armold_wp_")
    return Path(d) / "waypoints.json"


def test_save_and_get() -> None:
    """A saved waypoint is retrievable with the same data."""
    store = WaypointStore(_tmp_path(), NUM_JOINTS)
    pos = [10.0, 0.0, 45.0, -30.0, 0.0, 0.0, 90.0]
    store.save("pick", pos, gripper=120)
    wp = store.get("pick")
    assert wp is not None
    assert wp.positions == pos
    assert wp.gripper == 120
    print("PASS: test_save_and_get")


def test_persist_reload() -> None:
    """Waypoints survive a reload from the same file (persistence)."""
    path = _tmp_path()
    s1 = WaypointStore(path, NUM_JOINTS)
    s1.save("home", [0.0] * NUM_JOINTS)
    s1.save("reach", [0, 30, 20, 10, 0, 0, 0], gripper=60)
    # New store instance reads the same file
    s2 = WaypointStore(path, NUM_JOINTS)
    names = [w.name for w in s2.list()]
    assert names == ["home", "reach"], names
    assert s2.get("reach").gripper == 60
    print("PASS: test_persist_reload")


def test_overwrite_same_name() -> None:
    """Saving with an existing name overwrites it (no duplicate)."""
    store = WaypointStore(_tmp_path(), NUM_JOINTS)
    store.save("wp", [0.0] * NUM_JOINTS)
    store.save("wp", [1.0] * NUM_JOINTS)
    lst = store.list()
    assert len(lst) == 1
    assert lst[0].positions == [1.0] * NUM_JOINTS
    print("PASS: test_overwrite_same_name")


def test_delete() -> None:
    """Delete removes a waypoint and returns True; missing returns False."""
    store = WaypointStore(_tmp_path(), NUM_JOINTS)
    store.save("a", [0.0] * NUM_JOINTS)
    assert store.delete("a") is True
    assert store.get("a") is None
    assert store.delete("a") is False
    print("PASS: test_delete")


def test_reject_empty_name() -> None:
    """Empty/whitespace name raises ValueError."""
    store = WaypointStore(_tmp_path(), NUM_JOINTS)
    try:
        store.save("   ", [0.0] * NUM_JOINTS)
    except ValueError:
        print("PASS: test_reject_empty_name")
        return
    raise AssertionError("expected ValueError for empty name")


def test_reject_wrong_length() -> None:
    """Positions of the wrong length raise ValueError."""
    store = WaypointStore(_tmp_path(), NUM_JOINTS)
    try:
        store.save("bad", [0.0, 1.0, 2.0])
    except ValueError:
        print("PASS: test_reject_wrong_length")
        return
    raise AssertionError("expected ValueError for wrong-length positions")


def test_list_ordered_by_created() -> None:
    """list() is ordered oldest-first by creation time."""
    store = WaypointStore(_tmp_path(), NUM_JOINTS)
    store.save("first", [0.0] * NUM_JOINTS)
    # Force distinct timestamps
    wp = store.get("first")
    wp2 = Waypoint("second", [0.0] * NUM_JOINTS, created=wp.created + 1)
    store._waypoints["second"] = wp2  # direct insert with later timestamp
    names = [w.name for w in store.list()]
    assert names == ["first", "second"], names
    print("PASS: test_list_ordered_by_created")


def test_corrupt_file_tolerated() -> None:
    """A corrupt backing file loads as empty rather than raising."""
    path = _tmp_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ this is not valid json ]")
    store = WaypointStore(path, NUM_JOINTS)
    assert store.list() == []
    # And it can still save over the corrupt file
    store.save("ok", [0.0] * NUM_JOINTS)
    assert store.get("ok") is not None
    print("PASS: test_corrupt_file_tolerated")


def main() -> None:
    """Run all waypoint tests and report a summary."""
    tests = [
        test_save_and_get,
        test_persist_reload,
        test_overwrite_same_name,
        test_delete,
        test_reject_empty_name,
        test_reject_wrong_length,
        test_list_ordered_by_created,
        test_corrupt_file_tolerated,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {t.__name__}: {e}")
            failed += 1
        except Exception as e:  # noqa: BLE001 - harness reports all errors
            print(f"ERROR: {t.__name__}: {e}")
            failed += 1
    print(f"\n{'=' * 40}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
