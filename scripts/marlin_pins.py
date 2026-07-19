#!/usr/bin/env python3
"""Query Marlin for pin info to identify board pin mapping."""
import serial
import time
import sys

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbserial-A600QKZQ"

ser = serial.Serial(PORT, 115200, timeout=3)
time.sleep(2)
ser.read(4096)  # flush startup

# M43 reports pin states (if supported)
# M115 with extended capabilities
# M114 for position
commands = ['M43', 'M114', 'M119']
for cmd in commands:
    ser.reset_input_buffer()
    ser.write(f'{cmd}\n'.encode())
    time.sleep(2)
    response = ser.read(8192).decode('utf-8', errors='replace')
    print(f'--- {cmd} ---')
    print(response.strip() if response.strip() else '(no response)')
    print()

ser.close()
