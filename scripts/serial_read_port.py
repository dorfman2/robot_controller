#!/usr/bin/env python3
"""Read serial output from a specified port."""
import serial
import time
import sys

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbmodem1101"
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=3)
time.sleep(2)
data = ser.read(2048)
if data:
    print(data.decode('utf-8', errors='replace'))
else:
    print('No data received')
ser.close()
