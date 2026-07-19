#!/usr/bin/env python3
"""Quick test: enable motors and rotate joint 0 by 360 degrees on Einsy."""
import serial
import time
import sys

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbmodem1101"
BAUD = 115200
STEPS_PER_DEG = 20757 / 360  # ~57.7
STEPS_360 = 20757

ser = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(2)
ser.read(1024)  # flush startup

# Enable
ser.reset_input_buffer()
ser.write(b'E1\n')
time.sleep(0.2)
print(ser.readline().decode().strip())

# Move joint 0: 360 degrees forward
ser.reset_input_buffer()
cmd = f'M0 {STEPS_360} 0 200\n'
print(f'Sending: {cmd.strip()}')
ser.write(cmd.encode())
ser.timeout = 30
print(ser.readline().decode().strip())

ser.close()
