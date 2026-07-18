#!/usr/bin/env python3
"""Enable motors, slow down, then rotate joint 0 (X) by 10 degrees."""
import serial
import time

PORT = "/dev/cu.usbserial-AL03LVPB"
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(2)
ser.read(1024)  # flush startup

# Enable motors
ser.write(b'e')
time.sleep(0.2)
print(ser.read(256).decode('utf-8', errors='replace').strip())

# Slow down: send 'w' 12 times (200 + 12*50 = 800 us step delay)
for _ in range(12):
    ser.write(b'w')
    time.sleep(0.05)
time.sleep(0.2)
# Read all the step delay confirmations
print(ser.read(1024).decode('utf-8', errors='replace').strip())

# Move joint 0 by 10 degrees
ser.write(b'g0 10\n')
time.sleep(3)
print(ser.read(1024).decode('utf-8', errors='replace').strip())

ser.close()
