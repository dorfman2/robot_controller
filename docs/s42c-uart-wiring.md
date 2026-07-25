# S42C UART Monitor Board — Wiring Diagram

## Overview

A dedicated Arduino Mega 2560 ("Monitor Mega") connects bidirectionally to all
4 BTT S42C closed-loop driver boards via UART. A 4-channel bidirectional level
shifter handles the 5V↔3.3V translation.

```
                         ┌──────────────────────────────────┐
                         │       Raspberry Pi 4              │
                         │                                  │
                         │  USB-A ──── /dev/armold_ramps    │──── RAMPS Mega (motion)
                         │  USB-A ──── /dev/armold_monitor  │──┐
                         └──────────────────────────────────┘  │
                                                               │
                    USB Type-B                                  │
         ┌─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    MONITOR MEGA 2560                                  │
│                                                                      │
│  Serial (USB)  ← → Pi (250000 baud, commands + position reports)    │
│                                                                      │
│  Serial1 TX (pin 18) ─────────┐                                    │
│  Serial1 RX (pin 19) ────┐    │                                    │
│                           │    │                                    │
│  Serial2 TX (pin 16) ─────────┼────┐                               │
│  Serial2 RX (pin 17) ────┼────┼────┼────┐                          │
│                           │    │    │    │                          │
│  Serial3 TX (pin 14) ─────────┼────┼────┼────┐                     │
│  Serial3 RX (pin 15) ────┼────┼────┼────┼────┼────┐                │
│                           │    │    │    │    │    │                │
│  SoftSerial TX (pin 10) ──────┼────┼────┼────┼────┼────┐           │
│  SoftSerial RX (pin 11) ─┼────┼────┼────┼────┼────┼────┼────┐      │
│                           │    │    │    │    │    │    │    │      │
│  GND ─────────────────────┼────┼────┼────┼────┼────┼────┼────┼──┐   │
│  5V ──────────────────────┼────┼────┼────┼────┼────┼────┼────┼──┼─┐ │
└───────────────────────────┼────┼────┼────┼────┼────┼────┼────┼──┼─┼─┘
                            │    │    │    │    │    │    │    │  │ │
                            ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼  │ │
┌───────────────────────────────────────────────────────────────────────┐
│              4-CHANNEL BIDIRECTIONAL LEVEL SHIFTER                     │
│              (BSS138-based, e.g., Adafruit #757 or generic)           │
│                                                                       │
│  HIGH SIDE (5V)              LOW SIDE (3.3V)                          │
│  ─────────────              ──────────────                            │
│  HV  ← 5V from Mega         LV  ← 3.3V from S42C board              │
│  GND ← common GND           GND ← common GND                        │
│                                                                       │
│  CH1 HV ← Mega pin 18 (TX1) │ CH1 LV → S42C J0 RX                  │
│  CH2 HV ← Mega pin 19 (RX1) │ CH2 LV ← S42C J0 TX                  │
│  CH3 HV ← Mega pin 16 (TX2) │ CH3 LV → S42C J1 RX                  │
│  CH4 HV ← Mega pin 17 (RX2) │ CH4 LV ← S42C J1 TX                  │
└───────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────┐
│              4-CHANNEL BIDIRECTIONAL LEVEL SHIFTER #2                  │
│              (second module for J2 + J3)                              │
│                                                                       │
│  CH1 HV ← Mega pin 14 (TX3) │ CH1 LV → S42C J2 RX                  │
│  CH2 HV ← Mega pin 15 (RX3) │ CH2 LV ← S42C J2 TX                  │
│  CH3 HV ← Mega pin 10 (SoftTX) │ CH3 LV → S42C J3 RX               │
│  CH4 HV ← Mega pin 11 (SoftRX) │ CH4 LV ← S42C J3 TX               │
└───────────────────────────────────────────────────────────────────────┘

                            │    │    │    │    │    │    │    │
                            ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│  BTT S42C #1   │  │  BTT S42C #2   │  │  BTT S42C #3   │  │  BTT S42C #4   │
│  Joint 0 (Base)│  │  Joint 1 (Shldr)│  │  Joint 2 (Elbw)│  │  Joint 3 (Wrst)│
│                │  │                │  │                │  │                │
│  UART TX ──────│  │  UART TX ──────│  │  UART TX ──────│  │  UART TX ──────│
│  UART RX ──────│  │  UART RX ──────│  │  UART RX ──────│  │  UART RX ──────│
│  GND ──────────│  │  GND ──────────│  │  GND ──────────│  │  GND ──────────│
│                │  │                │  │                │  │                │
│  Baud: 115200  │  │  Baud: 115200  │  │  Baud: 115200  │  │  Baud: 19200   │
└────────────────┘  └────────────────┘  └────────────────┘  └────────────────┘
```

---

## Pin Reference Table

| Connection | Mega Pin | Level Shifter | S42C Board | Baud |
|-----------|----------|---------------|------------|------|
| J0 TX (Mega → S42C) | Pin 18 (TX1) | Shifter 1, CH1 | S42C #1 RX | 115200 |
| J0 RX (S42C → Mega) | Pin 19 (RX1) | Shifter 1, CH2 | S42C #1 TX | 115200 |
| J1 TX (Mega → S42C) | Pin 16 (TX2) | Shifter 1, CH3 | S42C #2 RX | 115200 |
| J1 RX (S42C → Mega) | Pin 17 (RX2) | Shifter 1, CH4 | S42C #2 TX | 115200 |
| J2 TX (Mega → S42C) | Pin 14 (TX3) | Shifter 2, CH1 | S42C #3 RX | 115200 |
| J2 RX (S42C → Mega) | Pin 15 (RX3) | Shifter 2, CH2 | S42C #3 TX | 115200 |
| J3 TX (Mega → S42C) | Pin 10 (SoftTX) | Shifter 2, CH3 | S42C #4 RX | 19200 |
| J3 RX (S42C → Mega) | Pin 11 (SoftRX) | Shifter 2, CH4 | S42C #4 TX | 19200 |

---

## Power Connections

```
Level Shifter #1:
  HV  ← Mega 5V pin
  LV  ← S42C board 3.3V (from any S42C 3.3V output, or separate 3.3V regulator)
  GND ← Common ground (shared across all boards)

Level Shifter #2:
  HV  ← Mega 5V pin
  LV  ← S42C board 3.3V
  GND ← Common ground
```

**CRITICAL**: All boards must share a common ground:
- RAMPS Mega GND
- Monitor Mega GND
- All S42C boards GND
- Level shifters GND
- 24V PSU GND

---

## S42C UART Header Location

The BTT S42C has a 4-pin UART header on the PCB edge:

```
S42C Board (top view)
┌──────────────────────┐
│                      │
│  [OLED]              │
│                      │
│  ┌──┐               │
│  │TX│  ← Pin 1 (UART output from S42C)
│  │RX│  ← Pin 2 (UART input to S42C)
│  │VCC│ ← Pin 3 (3.3V — can power level shifter LV side)
│  │GND│ ← Pin 4 (Ground)
│  └──┘               │
│                      │
│  [Motor connector]   │
│  [STEP/DIR/EN input] │
└──────────────────────┘
```

---

## Wire Color Suggestion

Use consistent colors across all 4 S42C connections:

| Wire | Color | Function |
|------|-------|----------|
| TX (S42C → Mega) | Yellow | S42C transmits position data |
| RX (Mega → S42C) | Green | Mega sends commands to S42C |
| GND | Black | Common ground |
| 3.3V (for LV ref) | Red | Level shifter LV reference |

---

## S42C OLED Baud Rate Settings

Before wiring, set each S42C's UART baud rate via OLED:

```
J0: OLED → BaudRate → 115200 → Save Setting
J1: OLED → BaudRate → 115200 → Save Setting
J2: OLED → BaudRate → 115200 → Save Setting
J3: OLED → BaudRate → 19200 → Save Setting  ← SoftwareSerial limitation
```

---

## Alternative: Skip Level Shifter (Read-Only)

If you only want TX (position monitoring, no write commands), you can skip the
level shifter for the RX direction. The S42C outputs 3.3V on TX, which the Mega
reads as HIGH (threshold ~2.5V for 5V logic). This works but is out of spec:

```
S42C TX (3.3V) → Mega RX pin directly (no shifter needed)
Mega TX (5V) → MUST go through level shifter to S42C RX (5V damages STM32)
```

**Recommended**: Use level shifters for both directions. They cost $3 and prevent
accidental damage.

---

## Parts List

| Item | Qty | Notes |
|------|-----|-------|
| Arduino Mega 2560 | 1 | Spare (already owned) |
| 4-ch bidirectional level shifter | 2 | BSS138-based, 3.3V↔5V ($1.50 each) |
| Dupont jumper wires (M-F) | 20 | For breadboard connections |
| USB Type-B cable | 1 | Mega to Pi (already owned) |
| Breadboard (small) | 1 | Optional — mount shifters cleanly |
| **Total** | | **~$5** |

---

## Physical Layout Suggestion

```
┌─────────────────────────────────────────────────────┐
│                    Raspberry Pi                       │
│  [USB] [USB] [USB] [USB]                            │
│    │      │                                         │
│    │      └──── Monitor Mega USB                    │
│    └─────────── RAMPS Mega USB                      │
└─────────────────────────────────────────────────────┘

    ┌────────────────────┐
    │    RAMPS Mega       │  ← Motion control (STEP/DIR to S42C)
    │    + RAMPS 1.4      │
    └────────────────────┘

    ┌────────────────────┐     ┌─────────────┐
    │   Monitor Mega      │ ──→ │ Level Shift │ ──→ S42C UART headers
    │   (UART monitor)    │     │ (×2 boards) │
    └────────────────────┘     └─────────────┘
```
