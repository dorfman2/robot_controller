"""Extract Preferences/NVS settings from a full ESP32-S3 flash backup.

Parses the partition table (0x8000) to find the NVS partition, then walks
NVS entries (32-byte records) looking for the CANBUS-Stepper settings keys.
Reports every write in flash order (later writes supersede earlier ones)
with the entry state so the operator can pick the live value.

Usage:
    python nvs_dig.py <flash_backup.bin>
"""

from __future__ import annotations

import struct
import sys

KEYS = {
    "NODE_ID": "u32",
    "controlType": "u32",
    "current": "u32",
    "microsteps": "u32",
    "stepsPerRev": "u32",
    "mapDirection": "bool",
    "posSpeed": "float",
    "accel": "float",
    "decel": "float",
    "stallThresh": "u32",
    "reportFreq1": "u32",
    "reportFreq2": "u32",
    "enableOnBoot": "bool",
    "zeroEncAtBoot": "bool",
    "standstillMode": "i32",
    "LED3V3Disable": "bool",
}

#: NVS entry datatype byte -> (struct fmt, nice name)
NVS_TYPES = {
    0x01: ("<B", "u8"),
    0x11: ("<b", "i8"),
    0x02: ("<H", "u16"),
    0x12: ("<h", "i16"),
    0x04: ("<I", "u32"),
    0x14: ("<i", "i32"),
    0x08: ("<Q", "u64"),
    0x18: ("<q", "i64"),
}


def find_nvs(image: bytes) -> tuple[int, int]:
    """Locate the NVS data partition via the partition table at 0x8000.

    Returns:
        (offset, size) of the first data/nvs partition.

    Raises:
        ValueError: If no NVS partition entry is found.
    """
    base = 0x8000
    for i in range(95):
        entry = image[base + i * 32 : base + (i + 1) * 32]
        if entry[:2] != b"\xaa\x50":
            continue
        ptype, subtype = entry[2], entry[3]
        offset, size = struct.unpack("<II", entry[4:12])
        label = entry[12:28].rstrip(b"\x00").decode(errors="replace")
        print(
            f"partition: {label:<12} type={ptype} sub=0x{subtype:02x} "
            f"off=0x{offset:x} size=0x{size:x}"
        )
        if ptype == 1 and subtype == 0x02:  # data / nvs
            return offset, size
    raise ValueError("no NVS partition found")


def main() -> None:
    """Scan the NVS partition for known settings keys and print values."""
    with open(sys.argv[1], "rb") as fh:
        image = fh.read()
    nvs_off, nvs_size = find_nvs(image)
    region = image[nvs_off : nvs_off + nvs_size]

    print(f"\nscanning NVS @0x{nvs_off:x} (+0x{nvs_size:x}) for settings keys:\n")
    hits = 0
    # NVS pages are 4096 B: 32 B header, 32 B state bitmap, then 126 entries.
    for page in range(0, len(region), 4096):
        for slot in range(2, 128):
            entry = region[page + slot * 32 : page + (slot + 1) * 32]
            if len(entry) < 32 or entry[0] in (0x00, 0xFF):
                continue
            dtype, span = entry[1], entry[2]
            key = entry[8:24].split(b"\x00")[0].decode(errors="replace")
            if key not in KEYS:
                continue
            data = entry[24:32]
            if dtype in NVS_TYPES:
                fmt, _name = NVS_TYPES[dtype]
                raw = struct.unpack(fmt, data[: struct.calcsize(fmt)])[0]
                shown = f"{raw}"
                if KEYS[key] == "float" and struct.calcsize(fmt) == 4:
                    shown += f"  (as float: {struct.unpack('<f', data[:4])[0]:.3f})"
                if KEYS[key] == "bool":
                    shown += f"  (bool: {bool(raw)})"
            else:
                shown = f"dtype=0x{dtype:02x} span={span} data={data.hex()}"
            print(f"  0x{nvs_off + page + slot * 32:06x}  {key:<15} = {shown}")
            hits += 1
    print(f"\n{hits} entries found (later offsets supersede earlier ones)")


if __name__ == "__main__":
    main()
