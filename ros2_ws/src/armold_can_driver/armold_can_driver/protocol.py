"""Vendor CAN protocol for thingsbyjosh CANBUS Stepper nodes.

Implements the frame format from the vendor's ``CAN Protocol.md`` (verified
against the V0.11 node firmware source):

- 11-bit standard CAN ID encodes both address and meaning:
  ``CAN_ID = (NodeID << 6) | MsgType`` with NodeID 0-31 (0 = broadcast) and
  MsgType 0-63 (0-31 commands, 32-63 telemetry).
- All multi-byte payload values are **little-endian**.
- Payloads are at most 8 bytes; the firmware zero-pads on receive.
- RTR=1 on a frame requests the current value of that MsgType from the node,
  which replies with the same CAN ID, RTR=0, and the value payload.

Safety (spec R14): broadcast (NodeID 0) frames are only permitted for
enable/disable and emergency stop. A broadcast ``Set Position`` would lunge
all six joints simultaneously, so :func:`encode` refuses to build one.

This module is transport-agnostic: it produces/consumes ``(can_id, rtr,
payload)`` triples that map 1:1 onto ``can_msgs/Frame`` (``.id``, ``.is_rtr``,
``.data``) or a python-can / SocketCAN message.

Example:
    >>> frame = encode_set_position_deg(node_id=3, degrees=90.0)
    >>> hex(frame.can_id)
    '0xc1'
    >>> frame.payload.hex()
    '000000000000 5640'.replace(" ", "")  # doctest: +SKIP
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum

BROADCAST_NODE_ID: int = 0
MIN_NODE_ID: int = 0
MAX_NODE_ID: int = 31
MAX_MSG_TYPE: int = 63
MAX_PAYLOAD_LEN: int = 8

#: 12-bit AUX PWM at 50 Hz (firmware: ``ledcAttach(pin, 50, 12)``): duty counts
#: for standard hobby-servo pulse widths over the 20 ms period.
AUX_PWM_PERIOD_MS: float = 20.0
AUX_PWM_MAX_COUNTS: int = 4095


class MsgType(IntEnum):
    """Command (0-31) and telemetry (32-63) message types.

    Values transcribed from the vendor protocol document and cross-checked
    against the V0.11 firmware's ``executeCommand`` switch.
    """

    NOP = 0
    SET_POSITION_DEG = 1
    SET_POSITION_STEPS = 2
    SET_VELOCITY = 3
    SET_CURRENT = 4
    ENABLE = 5
    ESTOP = 6
    STALLGUARD_BEHAVIOUR = 7
    ZERO_ON_BOOT = 8
    LED_STATE = 9
    STEPS_PER_REV = 10
    MICROSTEPS = 11
    STALLGUARD_THRESHOLD = 12
    CLOSED_LOOP_TYPE = 13
    STANDSTILL_MODE = 14
    MAP_DIRECTION = 15
    POSITION_SPEED = 16
    ACCELERATION = 17
    DECELERATION = 18
    REPORT_FREQUENCY = 19
    ENABLE_ON_BOOT = 20
    DISABLE_3V3_LED = 21
    RESET_TO_DEFAULT = 23
    SAVE_CONFIG = 24
    SET_NODE_ID = 25
    AUX_CONNECTOR = 26

    ENCODER_COUNTS = 32
    ENCODER_ANGLE_DEG = 33
    VOLTAGE = 34
    BUTTON_STATES = 35
    STALLGUARD_VALUE = 36
    STALLGUARD_TRIGGERED = 37
    BOARD_TEMPERATURE = 38
    FAULT_CODE = 39
    SOFTWARE_VERSION = 40
    ESP32_TEMPERATURE = 41
    CURRENT_VELOCITY = 42


class StandstillMode(IntEnum):
    """TMC2209 standstill behavior (``MsgType.STANDSTILL_MODE``)."""

    NORMAL = 0
    FREEWHEELING = 1
    BRAKING = 2
    STRONG_BRAKING = 3


class AuxFunction(IntEnum):
    """AUX connector pin function codes (``MsgType.AUX_CONNECTOR``)."""

    DISABLED = 0
    SERIAL_CONTROL = 1
    DIGITAL_OUTPUT = 3
    DIGITAL_INPUT = 4
    ANALOG_INPUT = 5
    PWM_OUTPUT = 6


#: Broadcast (NodeID 0) is only allowed for these message types (spec R14).
BROADCAST_ALLOWED: frozenset[MsgType] = frozenset(
    {MsgType.ENABLE, MsgType.ESTOP, MsgType.NOP}
)


class ProtocolError(ValueError):
    """Raised for invalid node IDs, message types, payloads, or a forbidden
    broadcast (a broadcast motion command would move all joints at once)."""


@dataclass(frozen=True)
class Frame:
    """A single protocol frame, transport-agnostic.

    Attributes:
        can_id: 11-bit standard CAN identifier, ``(node_id << 6) | msg_type``.
        rtr: Remote transmission request flag; ``True`` requests the current
            value of ``msg_type`` from the node instead of setting it.
        payload: 0-8 bytes, little-endian fields per the protocol table.
    """

    can_id: int
    rtr: bool = False
    payload: bytes = field(default=b"")

    @property
    def node_id(self) -> int:
        """Node address encoded in the CAN ID (0 = broadcast)."""
        return (self.can_id >> 6) & 0x1F

    @property
    def msg_type(self) -> MsgType:
        """Message type encoded in the CAN ID.

        Raises:
            ProtocolError: If the 6-bit field is not a known ``MsgType``.
        """
        raw = self.can_id & 0x3F
        try:
            return MsgType(raw)
        except ValueError as exc:
            raise ProtocolError(
                f"unknown MsgType {raw} in CAN ID 0x{self.can_id:X}"
            ) from exc


def build_can_id(node_id: int, msg_type: int) -> int:
    """Compose the 11-bit CAN ID from a node address and message type.

    Args:
        node_id: Node address, 0-31 (0 = broadcast).
        msg_type: Message type, 0-63.

    Returns:
        ``(node_id << 6) | msg_type``.

    Raises:
        ProtocolError: If either field is out of range.
    """
    if not MIN_NODE_ID <= node_id <= MAX_NODE_ID:
        raise ProtocolError(
            f"node_id must be {MIN_NODE_ID}-{MAX_NODE_ID}, got {node_id}"
        )
    if not 0 <= msg_type <= MAX_MSG_TYPE:
        raise ProtocolError(f"msg_type must be 0-{MAX_MSG_TYPE}, got {msg_type}")
    return (node_id << 6) | msg_type


def parse_can_id(can_id: int) -> tuple[int, int]:
    """Split an 11-bit CAN ID into ``(node_id, msg_type)``.

    Args:
        can_id: Standard CAN identifier, 0-0x7FF.

    Returns:
        Tuple of node address (0-31) and raw message type (0-63).

    Raises:
        ProtocolError: If ``can_id`` exceeds the 11-bit range.
    """
    if not 0 <= can_id <= 0x7FF:
        raise ProtocolError(f"can_id must fit 11 bits, got 0x{can_id:X}")
    return (can_id >> 6) & 0x1F, can_id & 0x3F


def encode(
    node_id: int, msg_type: MsgType, payload: bytes = b"", rtr: bool = False
) -> Frame:
    """Build a validated frame, enforcing the broadcast guard (R14).

    Args:
        node_id: Destination node (0 = broadcast).
        msg_type: Message type to send.
        payload: Little-endian payload bytes (0-8).
        rtr: Request the current value instead of setting it.

    Returns:
        The validated :class:`Frame`.

    Raises:
        ProtocolError: On out-of-range fields, oversized payload, or a
            broadcast of a message type not in :data:`BROADCAST_ALLOWED`.
    """
    if len(payload) > MAX_PAYLOAD_LEN:
        raise ProtocolError(
            f"payload must be <= {MAX_PAYLOAD_LEN} bytes, got {len(payload)}"
        )
    if node_id == BROADCAST_NODE_ID and not rtr and msg_type not in BROADCAST_ALLOWED:
        raise ProtocolError(
            f"broadcast of {msg_type.name} is forbidden (R14): only "
            f"{sorted(m.name for m in BROADCAST_ALLOWED)} may be broadcast"
        )
    return Frame(can_id=build_can_id(node_id, msg_type), rtr=rtr, payload=payload)


# ---------------------------------------------------------------------------
# Command encoders (host -> node)
# ---------------------------------------------------------------------------


def encode_set_position_deg(node_id: int, degrees: float) -> Frame:
    """Command an absolute move in **motor** degrees (64-bit double)."""
    return encode(node_id, MsgType.SET_POSITION_DEG, struct.pack("<d", float(degrees)))


def encode_set_position_steps(node_id: int, steps: int) -> Frame:
    """Command an absolute move in **motor** microsteps (64-bit signed)."""
    return encode(node_id, MsgType.SET_POSITION_STEPS, struct.pack("<q", int(steps)))


def encode_set_velocity(node_id: int, deg_per_sec: float) -> Frame:
    """Command continuous velocity in motor deg/s (32-bit float)."""
    return encode(node_id, MsgType.SET_VELOCITY, struct.pack("<f", float(deg_per_sec)))


def encode_position_speed(node_id: int, deg_per_sec: float) -> Frame:
    """Set the max speed used for position moves (motor deg/s)."""
    return encode(
        node_id, MsgType.POSITION_SPEED, struct.pack("<f", float(deg_per_sec))
    )


def encode_acceleration(node_id: int, deg_per_sec2: float) -> Frame:
    """Set move acceleration (motor deg/s^2)."""
    return encode(node_id, MsgType.ACCELERATION, struct.pack("<f", float(deg_per_sec2)))


def encode_deceleration(node_id: int, deg_per_sec2: float) -> Frame:
    """Set move deceleration (motor deg/s^2)."""
    return encode(node_id, MsgType.DECELERATION, struct.pack("<f", float(deg_per_sec2)))


def encode_set_current(node_id: int, percent: int) -> Frame:
    """Set motor current as a percentage of the board maximum (1.92 A).

    Raises:
        ProtocolError: If ``percent`` is outside 0-100.
    """
    if not 0 <= percent <= 100:
        raise ProtocolError(f"current percent must be 0-100, got {percent}")
    return encode(node_id, MsgType.SET_CURRENT, struct.pack("<H", percent))


def encode_enable(node_id: int, enabled: bool) -> Frame:
    """Enable or disable the motor driver (broadcast permitted)."""
    return encode(node_id, MsgType.ENABLE, struct.pack("<B", 1 if enabled else 0))


def encode_estop(node_id: int = BROADCAST_NODE_ID) -> Frame:
    """Emergency stop (default broadcast). Leaves drivers DISABLED — on a
    vertical arm with no brakes this risks gravity collapse (spec R13); use as
    the hard tier only."""
    return encode(node_id, MsgType.ESTOP)


def encode_zero_on_boot(node_id: int, enabled: bool) -> Frame:
    """Enable zero-encoder-at-boot (park-pose reference, spec R5)."""
    return encode(node_id, MsgType.ZERO_ON_BOOT, struct.pack("<B", 1 if enabled else 0))


def encode_closed_loop(node_id: int, enabled: bool) -> Frame:
    """Set closed-loop control. Firmware DEFAULT IS OPEN LOOP (contradicting
    the protocol doc) — always set and save during bring-up (spec R14)."""
    return encode(
        node_id, MsgType.CLOSED_LOOP_TYPE, struct.pack("<h", 1 if enabled else 0)
    )


def encode_standstill_mode(node_id: int, mode: StandstillMode) -> Frame:
    """Set the TMC2209 standstill mode (e-stop/hold policy, spec R13)."""
    return encode(node_id, MsgType.STANDSTILL_MODE, struct.pack("<H", int(mode)))


def encode_map_direction(node_id: int, inverted: bool) -> Frame:
    """Invert the node's motion direction (0 = normal, 1 = inverted)."""
    return encode(
        node_id, MsgType.MAP_DIRECTION, struct.pack("<B", 1 if inverted else 0)
    )


def encode_microsteps(node_id: int, microsteps: int) -> Frame:
    """Set microstepping (1-256, powers of two)."""
    return encode(node_id, MsgType.MICROSTEPS, struct.pack("<H", int(microsteps)))


def encode_steps_per_rev(node_id: int, steps: int) -> Frame:
    """Set full steps per motor revolution (200 for 1.8 deg motors)."""
    return encode(node_id, MsgType.STEPS_PER_REV, struct.pack("<H", int(steps)))


def encode_report_frequency(node_id: int, angle_hz: int, other_hz: int) -> Frame:
    """Set telemetry rates: angle stream and secondary stream (Hz, 0=off)."""
    return encode(
        node_id, MsgType.REPORT_FREQUENCY, struct.pack("<HH", angle_hz, other_hz)
    )


def encode_enable_on_boot(node_id: int, enabled: bool) -> Frame:
    """Set power-on driver state. Spec R9: motors MUST start disabled."""
    return encode(
        node_id, MsgType.ENABLE_ON_BOOT, struct.pack("<B", 1 if enabled else 0)
    )


def encode_save_config(node_id: int) -> Frame:
    """Persist the node's current configuration to non-volatile memory."""
    return encode(node_id, MsgType.SAVE_CONFIG)


def encode_aux(
    node_id: int,
    aux1_function: AuxFunction,
    aux1_value: int,
    aux2_function: AuxFunction = AuxFunction.DISABLED,
    aux2_value: int = 0,
) -> Frame:
    """Configure the AUX connector pins (gripper servo PWM lives on AUX1).

    Re-sending with the same function and a new value performs a live
    ``ledcWrite`` on the node (verified in firmware), so gripper motion is
    just repeated AUX frames with new duty counts.

    Raises:
        ProtocolError: If serial mode is requested (forbidden on the J5
            gripper node — mutually exclusive with PWM, spec R15) or a value
            exceeds 16 bits.
    """
    if AuxFunction.SERIAL_CONTROL in (aux1_function, aux2_function):
        raise ProtocolError(
            "AUX serial mode is forbidden here (R15): conflicts with PWM"
        )
    for value in (aux1_value, aux2_value):
        if not 0 <= value <= 0xFFFF:
            raise ProtocolError(f"AUX value must be uint16, got {value}")
    payload = struct.pack(
        "<HHHH", int(aux1_function), aux1_value, int(aux2_function), aux2_value
    )
    return encode(node_id, MsgType.AUX_CONNECTOR, payload)


def servo_duty_counts(pulse_ms: float) -> int:
    """Convert a hobby-servo pulse width to AUX PWM duty counts.

    The AUX PWM is 50 Hz / 12-bit (20 ms period, 4095 counts), so
    ``counts = pulse_ms / 20 ms * 4095``. Standard servo travel is
    1.0-2.0 ms (~205-410 counts), 1.5 ms center (~307).

    Args:
        pulse_ms: Pulse width in milliseconds (accepted range 0.5-2.5 ms to
            cover extended-travel servos).

    Returns:
        Duty counts, 0-4095.

    Raises:
        ProtocolError: If ``pulse_ms`` is outside 0.5-2.5 ms.
    """
    if not 0.5 <= pulse_ms <= 2.5:
        raise ProtocolError(f"servo pulse must be 0.5-2.5 ms, got {pulse_ms}")
    return round(pulse_ms / AUX_PWM_PERIOD_MS * AUX_PWM_MAX_COUNTS)


def encode_request(node_id: int, msg_type: MsgType) -> Frame:
    """Build an RTR request for the current value of ``msg_type``."""
    return encode(node_id, msg_type, rtr=True)


# ---------------------------------------------------------------------------
# Telemetry decoders (node -> host)
# ---------------------------------------------------------------------------

#: MsgType -> (struct format, human name) for scalar telemetry payloads.
_TELEMETRY_FORMATS: dict[MsgType, str] = {
    MsgType.ENCODER_COUNTS: "<q",
    MsgType.ENCODER_ANGLE_DEG: "<d",
    MsgType.VOLTAGE: "<f",
    MsgType.STALLGUARD_VALUE: "<I",
    MsgType.BOARD_TEMPERATURE: "<f",
    MsgType.SOFTWARE_VERSION: "<f",
    MsgType.ESP32_TEMPERATURE: "<f",
    MsgType.CURRENT_VELOCITY: "<f",
    MsgType.FAULT_CODE: "<H",
}


@dataclass(frozen=True)
class Telemetry:
    """A decoded telemetry reading from one node.

    Attributes:
        node_id: Source node address (1-31).
        msg_type: Which telemetry stream this is.
        value: Decoded scalar (float for angles/volts/temps/velocity, int for
            counts/stallguard/fault, bool for stall-triggered).
    """

    node_id: int
    msg_type: MsgType
    value: float | int | bool


def decode_telemetry(can_id: int, payload: bytes) -> Telemetry | None:
    """Decode a telemetry frame into a typed reading.

    Args:
        can_id: The frame's 11-bit CAN identifier.
        payload: The frame's data bytes.

    Returns:
        A :class:`Telemetry`, or ``None`` if the frame is a command type or a
        telemetry type without a scalar mapping (e.g. button states).

    Raises:
        ProtocolError: If the CAN ID is out of range or the payload is too
            short for the expected field.
    """
    node_id, raw_type = parse_can_id(can_id)
    try:
        msg_type = MsgType(raw_type)
    except ValueError:
        return None
    if msg_type == MsgType.STALLGUARD_TRIGGERED:
        if len(payload) < 1:
            raise ProtocolError("stall-triggered payload is empty")
        return Telemetry(node_id, msg_type, payload[0] != 0)
    fmt = _TELEMETRY_FORMATS.get(msg_type)
    if fmt is None:
        return None
    size = struct.calcsize(fmt)
    if len(payload) < size:
        raise ProtocolError(
            f"{msg_type.name} payload too short: need {size} bytes, got {len(payload)}"
        )
    value = struct.unpack(fmt, payload[:size])[0]
    return Telemetry(node_id, msg_type, value)
