#!/usr/bin/env python3
"""Enable motors and rotate joint 0 (X) by 10 degrees."""
import serial
import time

PORT = "/dev/cu.usbserial-AL03LVPB"
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(2)  # Wait for Arduino reset

# Flush startup
startup = ser.read(1024)
print(startup.decode('utf-8', errors='replace').strip())
print()

# Enable motors
ser.write(b'e')
time.sleep(0.2)
print(ser.read(256).decode('utf-8', errors='replace').strip())

# Move joint 0 by 10 degrees: "g0 10\n"
ser.write(b'g0 10\n')
time.sleep(2)  # Wait for move to complete
print(ser.read(1024).decode('utf-8', errors='replace').strip())

ser.close()
