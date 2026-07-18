#!/usr/bin/env python3
"""Enable motors and hold for 30 seconds so you can check for torque."""
import serial
import time

PORT = "/dev/cu.usbserial-AL03LVPB"
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(2)
ser.read(1024)  # flush startup

ser.write(b'e')
time.sleep(0.2)
print(ser.read(256).decode('utf-8', errors='replace').strip())
print()
print("Motors ENABLED - holding for 30 seconds.")
print("Try turning the X motor shaft by hand now.")

time.sleep(30)

ser.write(b'd')
time.sleep(0.1)
print()
print(ser.read(256).decode('utf-8', errors='replace').strip())
ser.close()
