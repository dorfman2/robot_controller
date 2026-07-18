#!/usr/bin/env python3
"""Enable motors, set 2000us step delay, rotate joint 0 (X) by 30 degrees."""
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

for _ in range(36):
    ser.write(b'w')
    time.sleep(0.02)
time.sleep(0.2)
ser.read(2048)

ser.write(b'g0 30\n')
# 30 deg = 266 steps * 2000us * 2 (high+low) = ~1.06s
time.sleep(3)
print(ser.read(1024).decode('utf-8', errors='replace').strip())

ser.close()
