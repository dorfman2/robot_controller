#!/usr/bin/env python3
"""Enable motors, set 1000us step delay, rotate joint 0 (X) by 1080 degrees (3 revolutions)."""
import serial
import time

PORT = "/dev/cu.usbserial-AL03LVPB"
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(2)
ser.read(1024)

ser.write(b'e')
time.sleep(0.2)
ser.read(256)

# Set to 1000us: from 200, that's 16 'w' presses (200 + 16*50 = 1000)
for _ in range(16):
    ser.write(b'w')
    time.sleep(0.02)
time.sleep(0.2)
ser.read(2048)

# 1080 deg = 3 revs = 9600 steps * 1000us * 2 = ~19.2 seconds
ser.write(b'g0 360\n')
time.sleep(8)
print(ser.read(1024).decode('utf-8', errors='replace').strip())

ser.write(b'g0 360\n')
time.sleep(8)
print(ser.read(1024).decode('utf-8', errors='replace').strip())

ser.write(b'g0 360\n')
time.sleep(8)
print(ser.read(1024).decode('utf-8', errors='replace').strip())

ser.close()
