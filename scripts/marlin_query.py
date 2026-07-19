#!/usr/bin/env python3
"""Send Marlin G-code commands to identify the board."""
import serial
import time
import sys

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbserial-A600QKZQ"

ser = serial.Serial(PORT, 115200, timeout=2)
time.sleep(2)
ser.read(4096)  # flush startup

commands = ['M115', 'M503']
for cmd in commands:
    ser.reset_input_buffer()
    ser.write(f'{cmd}\n'.encode())
    time.sleep(1)
    response = ser.read(4096).decode('utf-8', errors='replace')
    print(f'--- {cmd} ---')
    print(response)

ser.close()
