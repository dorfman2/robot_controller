#!/usr/bin/env python3
"""Send a move command to a specific joint for a given number of degrees."""
import serial
import time
import sys

PORT = "/dev/cu.usbserial-AL03LVPB"
BAUD = 115200
MICROSTEPS = 16
FULL_STEPS_PER_REV = 200
STEPS_PER_REV = FULL_STEPS_PER_REV * MICROSTEPS  # 3200
STEP_DELAY_US = 200  # Must match firmware default

# 20 degrees = 20/360 * 3200 = ~178 microsteps
DEGREES = 20
steps = int(STEPS_PER_REV * DEGREES / 360)

print(f"Moving Joint 0 (X) {DEGREES} degrees ({steps} microsteps)")

ser = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(2)  # Wait for Arduino reset

# Flush any startup output
ser.read(1024)

# Enable motors
ser.write(b'e')
time.sleep(0.1)
response = ser.read(256)
print(response.decode('utf-8', errors='replace').strip())

# Send step pulses directly isn't possible via single-char commands,
# so we send '0' which does a full revolution. Instead, let's just
# send the enable and then manually pulse via a custom approach.
# 
# The current firmware only supports full revolutions per command.
# Sending a partial move requires a firmware update.

ser.close()
print(f"\nNote: Current firmware only supports full-revolution moves.")
print(f"Need to update firmware to support degree-based moves.")
