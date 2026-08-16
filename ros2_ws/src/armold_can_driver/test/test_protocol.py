"""No-mock unit tests for the CANBUS Stepper protocol module.

Ground truth: the worked frame examples in the vendor's ``CAN Protocol.md``:

1. Set Position (deg) 90.0 for Node 3 -> CAN ID 0xC1,
   payload ``00 00 00 00 00 00 56 40``.
2. Request (RTR) Voltage from Node 5 -> CAN ID 0x162.
3. Angle telemetry 45.5 deg from Node 2 -> CAN ID 0x91,
   payload ``00 00 00 00 00 B8 46 40``.

Run:
    python -m unittest discover -s test -v
"""

from __future__ import annotations

import struct
import unittest

from armold_can_driver.protocol import (
    AUX_PWM_MAX_COUNTS,
    BROADCAST_NODE_ID,
    AuxFunction,
    Frame,
    MsgType,
    ProtocolError,
    StandstillMode,
    Telemetry,
    build_can_id,
    decode_telemetry,
    encode,
    encode_aux,
    encode_closed_loop,
    encode_enable,
    encode_estop,
    encode_request,
    encode_set_current,
    encode_set_position_deg,
    encode_set_position_steps,
    encode_standstill_mode,
    encode_zero_on_boot,
    parse_can_id,
    servo_duty_counts,
)


class TestSpecExamples(unittest.TestCase):
    """Round-trip the three worked examples from the vendor protocol doc."""

    def test_example_1_set_position_deg_node3(self) -> None:
        """Node 3, Set Position 90 deg -> ID 0xC1 + IEEE-754 double payload.

        NOTE: the vendor doc's example payload ``00 00 00 00 00 00 56 40``
        actually decodes to 88.0 — a doc typo. The firmware memcpy's raw
        doubles, so IEEE-754 is ground truth: 90.0 = ``...00 80 56 40`` LE.
        """
        frame = encode_set_position_deg(node_id=3, degrees=90.0)
        self.assertEqual(frame.can_id, 0xC1)
        self.assertFalse(frame.rtr)
        self.assertEqual(frame.payload, struct.pack("<d", 90.0))
        self.assertEqual(frame.payload, bytes.fromhex("0000000000805640"))

    def test_example_2_rtr_voltage_node5(self) -> None:
        """Node 5, RTR request for Voltage telemetry -> ID 0x162, RTR set."""
        frame = encode_request(node_id=5, msg_type=MsgType.VOLTAGE)
        self.assertEqual(frame.can_id, 0x162)
        self.assertTrue(frame.rtr)

    def test_example_3_angle_telemetry_node2(self) -> None:
        """Node 2 angle telemetry: ID (2<<6)|33 = 0xA1, decodes 45.5 deg.

        NOTE: the vendor doc's example states ID 0x91, but 0x91 parses to
        node 2 / MsgType 17 (a command). (2 << 6) | 33 = 0xA1 — a doc typo.
        The doc's payload bytes also decode to 45.4375, not 45.5; we encode
        the exact double instead.
        """
        can_id = build_can_id(2, MsgType.ENCODER_ANGLE_DEG)
        self.assertEqual(can_id, 0xA1)
        reading = decode_telemetry(can_id, struct.pack("<d", 45.5))
        self.assertIsNotNone(reading)
        assert reading is not None  # narrow for the type checker
        self.assertEqual(reading.node_id, 2)
        self.assertEqual(reading.msg_type, MsgType.ENCODER_ANGLE_DEG)
        self.assertAlmostEqual(float(reading.value), 45.5)


class TestCanId(unittest.TestCase):
    """CAN ID composition, parsing, and bounds."""

    def test_round_trip_all_valid_ids(self) -> None:
        """Every (node, type) pair survives build -> parse unchanged."""
        for node_id in range(32):
            for msg_type in range(64):
                can_id = build_can_id(node_id, msg_type)
                self.assertEqual(parse_can_id(can_id), (node_id, msg_type))

    def test_node_id_out_of_range_rejected(self) -> None:
        """NodeID 32 exceeds the 5-bit field and must be rejected."""
        with self.assertRaises(ProtocolError):
            build_can_id(32, 1)

    def test_msg_type_out_of_range_rejected(self) -> None:
        """MsgType 64 exceeds the 6-bit field and must be rejected."""
        with self.assertRaises(ProtocolError):
            build_can_id(1, 64)

    def test_can_id_over_11_bits_rejected(self) -> None:
        """parse_can_id refuses identifiers beyond 0x7FF."""
        with self.assertRaises(ProtocolError):
            parse_can_id(0x800)

    def test_frame_properties(self) -> None:
        """Frame.node_id / .msg_type decode the packed CAN ID."""
        frame = Frame(can_id=build_can_id(6, MsgType.AUX_CONNECTOR))
        self.assertEqual(frame.node_id, 6)
        self.assertEqual(frame.msg_type, MsgType.AUX_CONNECTOR)


class TestBroadcastGuard(unittest.TestCase):
    """R14: broadcast restricted to enable/disable/e-stop."""

    def test_broadcast_estop_allowed(self) -> None:
        """Broadcast e-stop is the designed emergency path."""
        frame = encode_estop()
        self.assertEqual(frame.node_id, BROADCAST_NODE_ID)
        self.assertEqual(frame.msg_type, MsgType.ESTOP)

    def test_broadcast_enable_allowed(self) -> None:
        """Broadcast enable/disable is permitted."""
        frame = encode_enable(BROADCAST_NODE_ID, False)
        self.assertEqual(frame.payload, b"\x00")

    def test_broadcast_motion_forbidden(self) -> None:
        """A broadcast Set Position would lunge all joints -> refused."""
        with self.assertRaises(ProtocolError):
            encode_set_position_deg(BROADCAST_NODE_ID, 10.0)

    def test_broadcast_config_forbidden(self) -> None:
        """Broadcast config writes are refused too."""
        with self.assertRaises(ProtocolError):
            encode_closed_loop(BROADCAST_NODE_ID, True)


class TestCommandEncoders(unittest.TestCase):
    """Payload layouts for the command set used by the driver."""

    def test_set_position_steps_int64_le(self) -> None:
        """Steps encode as little-endian int64 (negative included)."""
        frame = encode_set_position_steps(4, -20757)
        self.assertEqual(frame.payload, struct.pack("<q", -20757))
        self.assertEqual(frame.can_id, build_can_id(4, MsgType.SET_POSITION_STEPS))

    def test_set_current_bounds(self) -> None:
        """Current percent outside 0-100 is refused."""
        self.assertEqual(encode_set_current(1, 42).payload, struct.pack("<H", 42))
        with self.assertRaises(ProtocolError):
            encode_set_current(1, 101)

    def test_zero_on_boot_flag(self) -> None:
        """Park-pose reference flag encodes as a single byte."""
        self.assertEqual(encode_zero_on_boot(2, True).payload, b"\x01")

    def test_standstill_mode_uint16(self) -> None:
        """Standstill mode encodes as little-endian uint16."""
        frame = encode_standstill_mode(1, StandstillMode.STRONG_BRAKING)
        self.assertEqual(frame.payload, struct.pack("<H", 3))

    def test_oversized_payload_rejected(self) -> None:
        """CAN payloads are capped at 8 bytes."""
        with self.assertRaises(ProtocolError):
            encode(1, MsgType.NOP, b"\x00" * 9)


class TestAuxGripper(unittest.TestCase):
    """R15: gripper servo on AUX1 PWM; serial mode forbidden."""

    def test_aux_pwm_payload_layout(self) -> None:
        """Doc example: AUX1 PWM 1024, AUX2 PWM 3072 -> 060000040600000C."""
        frame = encode_aux(
            1, AuxFunction.PWM_OUTPUT, 1024, AuxFunction.PWM_OUTPUT, 3072
        )
        self.assertEqual(frame.payload, bytes.fromhex("060000040600000C"))

    def test_aux_serial_forbidden(self) -> None:
        """AUX serial conflicts with gripper PWM and is refused."""
        with self.assertRaises(ProtocolError):
            encode_aux(6, AuxFunction.SERIAL_CONTROL, 0)

    def test_servo_duty_counts(self) -> None:
        """1.0/1.5/2.0 ms map to ~205/307/410 counts on 50 Hz/12-bit PWM."""
        self.assertEqual(servo_duty_counts(1.0), 205)
        self.assertEqual(servo_duty_counts(1.5), 307)
        self.assertEqual(servo_duty_counts(2.0), 410)
        self.assertLessEqual(servo_duty_counts(2.5), AUX_PWM_MAX_COUNTS)

    def test_servo_pulse_bounds(self) -> None:
        """Pulse widths outside 0.5-2.5 ms are refused."""
        with self.assertRaises(ProtocolError):
            servo_duty_counts(0.4)
        with self.assertRaises(ProtocolError):
            servo_duty_counts(3.0)


class TestTelemetryDecoding(unittest.TestCase):
    """Telemetry demux across the scalar streams."""

    def test_encoder_counts_int64(self) -> None:
        """Counts decode as little-endian int64."""
        can_id = build_can_id(1, MsgType.ENCODER_COUNTS)
        reading = decode_telemetry(can_id, struct.pack("<q", -83_028))
        assert reading is not None
        self.assertEqual(reading.value, -83_028)

    def test_velocity_float(self) -> None:
        """Velocity decodes as little-endian float32."""
        can_id = build_can_id(3, MsgType.CURRENT_VELOCITY)
        reading = decode_telemetry(can_id, struct.pack("<f", 123.5))
        assert reading is not None
        self.assertAlmostEqual(float(reading.value), 123.5, places=3)

    def test_stall_triggered_bool(self) -> None:
        """Stall-triggered decodes byte 0 as a boolean."""
        can_id = build_can_id(2, MsgType.STALLGUARD_TRIGGERED)
        reading = decode_telemetry(can_id, b"\x01")
        assert reading is not None
        self.assertIs(reading.value, True)

    def test_command_frame_returns_none(self) -> None:
        """Command-type IDs are not telemetry."""
        can_id = build_can_id(1, MsgType.SET_POSITION_DEG)
        self.assertIsNone(decode_telemetry(can_id, b"\x00" * 8))

    def test_short_payload_rejected(self) -> None:
        """A truncated angle payload raises instead of mis-decoding."""
        can_id = build_can_id(1, MsgType.ENCODER_ANGLE_DEG)
        with self.assertRaises(ProtocolError):
            decode_telemetry(can_id, b"\x00\x01")

    def test_telemetry_is_typed(self) -> None:
        """decode_telemetry returns the Telemetry dataclass."""
        can_id = build_can_id(1, MsgType.VOLTAGE)
        reading = decode_telemetry(can_id, struct.pack("<f", 24.1))
        self.assertIsInstance(reading, Telemetry)


if __name__ == "__main__":
    unittest.main()
