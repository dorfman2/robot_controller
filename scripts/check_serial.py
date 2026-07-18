#!/usr/bin/env python3
"""Quick serial port check - reads from connected device for 3 seconds."""
import serial
import time
import sys

PORT = "/dev/cu.usbserial-AL03LVPB"
BAUD = 115200

try:
    ser = serial.Serial(PORT, BAUD, timeout=3)
    time.sleep(2)  # Wait for device to reset/respond

    # Read whatever is in the buffer
    data = ser.read(1024)
    if data:
        print("Received data:")
        print(data.decode("utf-8", errors="replace"))
    else:
        print("No data received (device is silent)")

    print()
    print("Port info:")
    print(f"  Port: {ser.port}")
    print(f"  Baud: {ser.baudrate}")
    print(f"  DSR:  {ser.dsr}")
    print(f"  CTS:  {ser.cts}")
    ser.close()
    print("\nConnection OK - port opened and closed successfully.")
except serial.SerialException as e:
    print(f"Serial error: {e}")
    sys.exit(1)
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)
