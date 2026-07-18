#!/usr/bin/env python3
"""Just enable motors - check for holding torque by trying to turn shaft."""
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
print("Motors enabled. Try turning the X motor shaft by hand.")
print("If you feel resistance, the driver is working (wiring/power OK).")
print("If it spins freely, the motor isn't getting current.")
print()
input("Press Enter to disable motors and exit...")

ser.write(b'd')
time.sleep(0.1)
print(ser.read(256).decode('utf-8', errors='replace').strip())
ser.close()
