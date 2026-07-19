#!/usr/bin/env python3
"""Send a single command to the Einsy and print the response."""
import serial
import time
import sys

PORT = "/dev/cu.usbmodem1101"
CMD = sys.argv[1] if len(sys.argv) > 1 else "?"

ser = serial.Serial(PORT, 115200, timeout=2)
time.sleep(2)
ser.read(1024)  # flush startup
ser.reset_input_buffer()
ser.write(f'{CMD}\n'.encode())
time.sleep(0.5)
while ser.in_waiting:
    print(ser.readline().decode().strip())
ser.close()
