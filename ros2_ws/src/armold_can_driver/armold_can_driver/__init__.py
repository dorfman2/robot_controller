"""armold_can_driver — Armold's driver for thingsbyjosh CANBUS Stepper nodes.

Modules:
    protocol: Vendor CAN protocol encode/decode (11-bit ID, little-endian
        payloads, RTR telemetry requests) with the R14 broadcast guard.
    gearing: Joint-space <-> motor-space <-> steps conversions with per-joint
        gear ratio, direction sign, park-pose offset, and soft limits.
"""

__version__ = "0.1.0"
