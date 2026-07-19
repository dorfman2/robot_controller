#!/usr/bin/env python3
"""Rotate joint 0: +360 then -360 at max speed (60us cruise delay)."""
import serial
import time

PORT = "/dev/cu.usbmodem1101"
STEPS_360 = 20757
MAX_SPEED_DELAY = 30  # Minimum delay = max speed

ser = serial.Serial(PORT, 115200, timeout=30)
time.sleep(2)
ser.read(1024)

# Enable
ser.reset_input_buffer()
ser.write(b'E1\n')
time.sleep(0.2)
print(ser.readline().decode().strip())

# +360 at max speed
ser.reset_input_buffer()
cmd = f'M0 {STEPS_360} 0 {MAX_SPEED_DELAY}\n'
print(f'+360: {cmd.strip()}')
ser.write(cmd.encode())
print(ser.readline().decode().strip())

time.sleep(0.3)

# -360 at max speed
ser.reset_input_buffer()
cmd = f'M0 {STEPS_360} 1 {MAX_SPEED_DELAY}\n'
print(f'-360: {cmd.strip()}')
ser.write(cmd.encode())
print(ser.readline().decode().strip())

ser.close()
