#!/usr/bin/env python3
"""Read serial output from the Mega after reset."""
import serial
import time

ser = serial.Serial('/dev/cu.usbserial-AL03LVPB', 115200, timeout=3)
time.sleep(2)
data = ser.read(2048)
if data:
    print(data.decode('utf-8', errors='replace'))
else:
    print('No data received - try pressing reset on the Mega')
ser.close()
