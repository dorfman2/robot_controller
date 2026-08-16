/**
 * Armold — UIM4247PM rail smoke test (factory defaults, no CFG344 config).
 *
 * Verifies the canonical Mega <-> UIM4247PM wiring from the ros2-can-motion
 * spec (design.md §4) before the real rail firmware is written:
 *
 *   COM (t3) -> Mega 5V        (opto common ANODE -> all signals ACTIVE-LOW)
 *   STP (t5) -> D2             (LOW pulse >= 5 us = one step)
 *   DIR (t4) -> D3             (LOW = CW)
 *   ENA (t6) -> D4             (LOW = enabled; floating/HIGH = DISABLED)
 *   t7  GND  -> Mega GND       (UART reference; harmless for smoke test)
 *   Endstop  -> D5 <-> GND     (NC switch, INPUT_PULLUP:
 *                               LOW = closed = OK; HIGH = pressed OR wire
 *                               break = TRIGGERED -> fail-safe)
 *
 * Factory defaults assumed: 32 microsteps -> 6400 pulses/motor rev.
 * Manual: min pulse width > 3 us both levels -> we use 5/5 us minimum.
 *
 * Serial console: 115200 8N1. Commands (single char, newline optional):
 *   e  enable driver           d  disable driver
 *   f  direction CW            r  direction CCW
 *   1  jog    100 steps        2  jog  1,000 steps
 *   3  jog  6,400 steps (1 motor rev at default MCS)
 *   4  jog 32,000 steps (5 revs)
 *   +  speed up (x2)           -  slow down (/2)
 *   ?  status                  !  abort current move
 *
 * Motion stops immediately if the endstop triggers (HIGH) while moving
 * toward it isn't distinguishable in a smoke test — it stops for EITHER
 * direction. Free the switch (or fix the wire) and jog the other way.
 */

#include <Arduino.h>

// ---- Pins (canonical map, design.md §4) ----
constexpr uint8_t PIN_STP = 2;      // active-LOW pulse
constexpr uint8_t PIN_DIR = 3;      // LOW = CW
constexpr uint8_t PIN_ENA = 4;      // LOW = enabled
constexpr uint8_t PIN_ENDSTOP = 5;  // NC to GND, INPUT_PULLUP: HIGH = triggered

// ---- Timing (manual p.6: >3 us high AND low; be conservative) ----
constexpr unsigned int PULSE_LOW_US = 5;   // active (LED on) phase
constexpr unsigned int PULSE_HIGH_MIN_US = 5;
constexpr unsigned long DIR_SETUP_US = 10;  // settle after direction change

// ---- State ----
long stepRateHz = 1000;     // gentle default (~9.4 rpm at 6400 p/rev)
constexpr long RATE_MIN_HZ = 125;
constexpr long RATE_MAX_HZ = 20000;  // 25+25 us period floor stays legal
bool enabled = false;
bool dirCw = true;
long positionSteps = 0;  // signed, CW = +

static bool endstopTriggered() { return digitalRead(PIN_ENDSTOP) == HIGH; }

static void printStatus() {
  Serial.print(F("ena="));
  Serial.print(enabled ? F("ON") : F("off"));
  Serial.print(F(" dir="));
  Serial.print(dirCw ? F("CW") : F("CCW"));
  Serial.print(F(" rate="));
  Serial.print(stepRateHz);
  Serial.print(F("Hz pos="));
  Serial.print(positionSteps);
  Serial.print(F(" endstop="));
  Serial.println(endstopTriggered() ? F("TRIGGERED/OPEN") : F("closed(ok)"));
}

static void setEnabled(bool on) {
  enabled = on;
  digitalWrite(PIN_ENA, on ? LOW : HIGH);  // active-LOW
  printStatus();
}

static void setDir(bool cw) {
  dirCw = cw;
  digitalWrite(PIN_DIR, cw ? LOW : HIGH);  // LOW = CW
  delayMicroseconds(DIR_SETUP_US);
  printStatus();
}

/**
 * Blocking jog with endstop + abort ('!') checks every step.
 * Returns steps actually taken.
 */
static long jog(long steps) {
  if (!enabled) {
    Serial.println(F("refused: driver disabled (send 'e')"));
    return 0;
  }
  if (endstopTriggered()) {
    Serial.println(F("refused: endstop TRIGGERED (or wire break)"));
    return 0;
  }
  const unsigned long periodUs = 1000000UL / (unsigned long)stepRateHz;
  const unsigned long highUs =
      (periodUs > PULSE_LOW_US + PULSE_HIGH_MIN_US) ? periodUs - PULSE_LOW_US
                                                    : PULSE_HIGH_MIN_US;
  Serial.print(F("jog "));
  Serial.print(steps);
  Serial.print(F(" steps @"));
  Serial.print(stepRateHz);
  Serial.println(F("Hz..."));

  long done = 0;
  for (; done < steps; ++done) {
    if (endstopTriggered()) {
      Serial.println(F("STOP: endstop triggered mid-move"));
      break;
    }
    if (Serial.available() && Serial.peek() == '!') {
      Serial.read();
      Serial.println(F("STOP: aborted"));
      break;
    }
    digitalWrite(PIN_STP, LOW);   // active phase
    delayMicroseconds(PULSE_LOW_US);
    digitalWrite(PIN_STP, HIGH);  // idle phase
    delayMicroseconds(highUs);
  }
  positionSteps += dirCw ? done : -done;
  Serial.print(F("moved "));
  Serial.print(done);
  Serial.println(F(" steps"));
  printStatus();
  return done;
}

void setup() {
  pinMode(PIN_STP, OUTPUT);
  digitalWrite(PIN_STP, HIGH);  // idle (LED off)
  pinMode(PIN_DIR, OUTPUT);
  digitalWrite(PIN_DIR, LOW);   // CW
  pinMode(PIN_ENA, OUTPUT);
  digitalWrite(PIN_ENA, HIGH);  // start DISABLED (spec R9)
  pinMode(PIN_ENDSTOP, INPUT_PULLUP);

  Serial.begin(115200);
  Serial.println(F("\nArmold rail smoke test — UIM4247PM @ factory defaults"));
  Serial.println(F("(32 microsteps assumed -> 6400 pulses/rev)"));
  Serial.println(F("e/d enable/disable  f/r dir  1/2/3/4 jog  +/- speed  ? status  ! abort"));
  printStatus();
}

void loop() {
  if (!Serial.available()) return;
  const int c = Serial.read();
  switch (c) {
    case 'e': setEnabled(true); break;
    case 'd': setEnabled(false); break;
    case 'f': setDir(true); break;
    case 'r': setDir(false); break;
    case '1': jog(100); break;
    case '2': jog(1000); break;
    case '3': jog(6400); break;
    case '4': jog(32000); break;
    case '+':
      stepRateHz = min(stepRateHz * 2, RATE_MAX_HZ);
      printStatus();
      break;
    case '-':
      stepRateHz = max(stepRateHz / 2, RATE_MIN_HZ);
      printStatus();
      break;
    case '?': printStatus(); break;
    case '!': Serial.println(F("(idle — nothing to abort)")); break;
    default: break;  // ignore whitespace/newlines
  }
}
