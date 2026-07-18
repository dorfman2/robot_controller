#!/usr/bin/env python3
"""Reset position counters on the Arduino to zero (set current position as home)."""
import serial
import time
import sys

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/armold_ramps"
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(0.5)
ser.write(b"R\n")
time.sleep(0.2)
print(ser.readline().decode().strip())
ser.write(b"S\n")
time.sleep(0.2)
print(ser.readline().decode().strip())
ser.close()
