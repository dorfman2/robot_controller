/**
 * Armold - RAMPS 1.4 + BTT S42C Closed-Loop Stepper Controller
 *
 * Firmware for RAMPS 1.4 shield on Arduino Mega 2560 with BTT S42C
 * closed-loop driver boards. S42C handles position correction internally
 * via 14-bit TLE5012B encoder — this firmware only generates STEP/DIR pulses.
 *
 * No SPI driver communication needed (S42C configured via OLED/UART).
 * No StallGuard (S42C handles stall detection internally).
 * No current control (S42C manages motor current internally).
 *
 * Hardware: RAMPS 1.4 (Arduino Mega 2560) + 4x BTT S42C V1.1
 * Axes: X=Joint0(Base), Y=Joint1(Shoulder), Z=Joint2(Elbow), E0=Joint3(Wrist)
 *
 * RAMPS 1.4 pin assignments:
 *   Joint 0 (X):  STEP=54, DIR=55, ENABLE=38
 *   Joint 1 (Y):  STEP=60, DIR=61, ENABLE=56
 *   Joint 2 (Z):  STEP=46, DIR=48, ENABLE=62
 *   Joint 3 (E0): STEP=26, DIR=28, ENABLE=24
 *
 * Protocol commands (newline terminated):
 *   E1              - Enable all motors
 *   E0              - Disable all motors
 *   M<j> <steps> <dir> <delay> - Move single joint
 *   G <p0> <p1> <p2> <p3> [delay] - Coordinated move all joints
 *   X <joint> <steps> <dir> <start_int> <end_int> <curve> - Segment move
 *   S               - Query state
 *   R / R<j>        - Reset position counters
 *   ?               - Print help
 *
 * E-STOP: Send '!' byte mid-move to immediately halt all motion.
 *
 * S42C Configuration (set via OLED on each board):
 *   Mode: Step Mode | Microstep: 16 | Current: High/Very High
 *   Direction: Normal | Enable Pin: Normal | Stall: Enable
 *
 * Steps per degree (16 microsteps, 20:1 gearbox):
 *   (16 * 200 * 20) / 360 = 177.8 steps/degree
 *   64,000 steps per output revolution
 *
 * Power: 24V DC, 10A
 */

#include <Arduino.h>

// --- Number of joints on this board ---
#define NUM_JOINTS 4

// --- Pin Definitions (RAMPS 1.4) ---
// Joint 0 (X axis)
#define J0_STEP_PIN  54
#define J0_DIR_PIN   55
#define J0_EN_PIN    38

// Joint 1 (Y axis)
#define J1_STEP_PIN  60
#define J1_DIR_PIN   61
#define J1_EN_PIN    56

// Joint 2 (Z axis)
#define J2_STEP_PIN  46
#define J2_DIR_PIN   48
#define J2_EN_PIN    62

// Joint 3 (E0 axis)
#define J3_STEP_PIN  26
#define J3_DIR_PIN   28
#define J3_EN_PIN    24

// --- S42C Configuration Constants ---
// S42C configured via OLED: 16 microsteps, closed-loop correction internal
// Calibration: 83,028 steps = 360° output (measured empirically)
// Actual gearbox ratio: 83,028 / (16 × 200) = 25.946:1
#define MICROSTEPS          16
#define STEPS_PER_OUTPUT_REV 83028L
// 83,028 / 360 = 230.6 steps/degree (same as Einsy calibration)

// --- Soft Limits (per-joint, in steps) ---
// Prevents commanding past physical joint range.
// All joints at 16 microsteps: 83,028 steps/rev → 230.6 steps/degree
#define STEPS_PER_DEGREE    231  // 83028 / 360 ≈ 230.6, rounded

// Joint limits in degrees (from FK simulator):
//   J0 (Base):        ±360° (full rotation for testing)
//   J1 (Shoulder):    ±90°
//   J2 (Elbow):       ±150°
//   J3 (Wrist Pitch): ±120°
const int32_t softLimitMin[NUM_JOINTS] = {
    -360L * STEPS_PER_DEGREE,  // J0: -83,160
     -90L * STEPS_PER_DEGREE,  // J1: -20,790
    -150L * STEPS_PER_DEGREE,  // J2: -34,650
    -120L * STEPS_PER_DEGREE   // J3: -27,720
};
const int32_t softLimitMax[NUM_JOINTS] = {
     360L * STEPS_PER_DEGREE,  // J0: +83,160
      90L * STEPS_PER_DEGREE,  // J1: +20,790
     150L * STEPS_PER_DEGREE,  // J2: +34,650
     120L * STEPS_PER_DEGREE   // J3: +27,720
};
bool softLimitsEnabled = true;
#define DEFAULT_STEP_DELAY  80    // Cruise speed (microseconds between steps)
#define MIN_STEP_DELAY      20    // Absolute max speed
#define MAX_STEP_DELAY      5000
#define START_STEP_DELAY    600   // Initial speed for acceleration ramp
#define ACCEL_STEPS         300   // Steps to accelerate from start to cruise speed
#define DECEL_STEPS         300   // Steps to decelerate from cruise to stop

// --- Pin lookup tables ---
const uint8_t stepPins[NUM_JOINTS]  = {J0_STEP_PIN, J1_STEP_PIN, J2_STEP_PIN, J3_STEP_PIN};
const uint8_t dirPins[NUM_JOINTS]   = {J0_DIR_PIN,  J1_DIR_PIN,  J2_DIR_PIN,  J3_DIR_PIN};
const uint8_t enPins[NUM_JOINTS]    = {J0_EN_PIN,   J1_EN_PIN,   J2_EN_PIN,   J3_EN_PIN};

// --- State ---
bool motorsEnabled = false;
uint16_t stepDelayUs = DEFAULT_STEP_DELAY;
int32_t position[NUM_JOINTS] = {0, 0, 0, 0};


/**
 * 64-entry sinusoidal (half-cosine) lookup table for smooth acceleration.
 *
 * Values represent a normalized 0-255 scale of the half-cosine function:
 *   table[i] = round(255 * (1 - cos(i * PI / 63)) / 2)
 *
 * Index 0 = 0 (start of ramp, still at START_DELAY)
 * Index 63 = 255 (end of ramp, reached CRUISE_DELAY)
 *
 * This produces an S-shaped transition that eliminates the jerk
 * discontinuity of a linear ramp — acceleration eases in and eases out.
 */
static const uint8_t PROGMEM sinTable[64] = {
      0,   0,   1,   1,   3,   4,   6,   8,
     10,  13,  16,  19,  22,  26,  30,  34,
     38,  43,  48,  53,  58,  64,  69,  75,
     81,  87,  93,  99, 105, 112, 118, 124,
    131, 137, 143, 150, 156, 162, 168, 174,
    180, 186, 191, 197, 202, 207, 212, 217,
    221, 225, 229, 233, 236, 239, 242, 245,
    247, 249, 251, 252, 254, 254, 255, 255
};

/**
 * Calculate step delay using sinusoidal (half-cosine) acceleration profile.
 * Smoothly ramps from START_STEP_DELAY down to cruiseDelay using the
 * sinusoidal lookup table, then back up symmetrically for deceleration.
 *
 * @param step        Current step index (0-based)
 * @param totalSteps  Total steps in the move
 * @param cruiseDelay Target cruise speed delay (us)
 * @return            Delay for this step (us)
 */
uint16_t rampDelay(uint32_t step, uint32_t totalSteps, uint16_t cruiseDelay) {
    uint16_t accelSteps = ACCEL_STEPS;
    uint16_t decelSteps = DECEL_STEPS;

    // For short moves, split available steps between accel and decel
    if (totalSteps < (uint32_t)(accelSteps + decelSteps)) {
        accelSteps = totalSteps / 2;
        decelSteps = totalSteps - accelSteps;
    }

    uint32_t decelStart = totalSteps - decelSteps;

    if (step < accelSteps) {
        // Accelerating: sinusoidal ease-in from START_STEP_DELAY to cruiseDelay
        uint8_t idx = (uint8_t)((step * 63UL) / accelSteps);
        uint8_t t = pgm_read_byte(&sinTable[idx]);
        uint32_t range = START_STEP_DELAY - cruiseDelay;
        return START_STEP_DELAY - (uint16_t)((range * t) / 255);
    } else if (step >= decelStart) {
        // Decelerating: sinusoidal ease-out from cruiseDelay to START_STEP_DELAY
        uint32_t stepsIntoDecel = step - decelStart;
        uint8_t idx = (uint8_t)((stepsIntoDecel * 63UL) / decelSteps);
        uint8_t t = pgm_read_byte(&sinTable[idx]);
        uint32_t range = START_STEP_DELAY - cruiseDelay;
        return cruiseDelay + (uint16_t)((range * t) / 255);
    } else {
        // Cruising at target speed
        return cruiseDelay;
    }
}


/**
 * Check if a move would exceed soft limits.
 * Returns the clamped step count (may be less than requested).
 * Returns 0 if the move is entirely outside limits.
 */
uint32_t clampSteps(uint8_t joint, uint32_t steps, bool forward) {
    if (!softLimitsEnabled || joint >= NUM_JOINTS) return steps;

    int32_t targetPos;
    if (forward) {
        targetPos = position[joint] + (int32_t)steps;
        if (targetPos > softLimitMax[joint]) {
            int32_t allowed = softLimitMax[joint] - position[joint];
            if (allowed <= 0) return 0;
            return (uint32_t)allowed;
        }
    } else {
        targetPos = position[joint] - (int32_t)steps;
        if (targetPos < softLimitMin[joint]) {
            int32_t allowed = position[joint] - softLimitMin[joint];
            if (allowed <= 0) return 0;
            return (uint32_t)allowed;
        }
    }
    return steps;
}


/**
 * Enable or disable all stepper motor drivers.
 * RAMPS enable pins are active LOW (same as S42C default).
 */
void setMotorsEnabled(bool enabled) {
    uint8_t state = enabled ? LOW : HIGH;
    for (uint8_t i = 0; i < NUM_JOINTS; i++) {
        digitalWrite(enPins[i], state);
    }
    motorsEnabled = enabled;
}

/**
 * Move a single joint with sinusoidal acceleration profile.
 *
 * @param joint      Joint index (0-3)
 * @param steps      Number of microsteps to move
 * @param forward    Direction (true=forward, false=reverse)
 * @param cruiseDelay Target cruise speed delay in microseconds
 */
void moveJoint(uint8_t joint, uint32_t steps, bool forward, uint16_t cruiseDelay) {
    if (joint >= NUM_JOINTS) return;

    // Enforce soft limits
    steps = clampSteps(joint, steps, forward);
    if (steps == 0) return;

    digitalWrite(dirPins[joint], forward ? HIGH : LOW);
    delayMicroseconds(5);

    for (uint32_t i = 0; i < steps; i++) {
        // Check for E-STOP every step
        if (Serial.available()) {
            char c = Serial.peek();
            if (c == '!') {
                Serial.read();
                setMotorsEnabled(false);
                if (forward) { position[joint] += i; } else { position[joint] -= i; }
                Serial.println(F("!! ESTOP"));
                return;
            }
        }

        uint16_t d = rampDelay(i, steps, cruiseDelay);
        digitalWrite(stepPins[joint], HIGH);
        delayMicroseconds(d);
        digitalWrite(stepPins[joint], LOW);
        delayMicroseconds(d);
    }

    if (forward) {
        position[joint] += steps;
    } else {
        position[joint] -= steps;
    }
}


/**
 * Execute a single motion segment with interval interpolation.
 *
 * The Pi-side trajectory planner computes the S-curve and sends segments
 * with start/end intervals. The MCU smoothly interpolates between them.
 *
 * E-STOP: Checks for '!' byte every 16 steps. If received, immediately
 * halts motion and disables motors.
 *
 * @param joint          Joint index (0-3)
 * @param steps          Number of steps in this segment
 * @param forward        Direction (true=forward)
 * @param startInterval  Microseconds between steps at segment start
 * @param endInterval    Microseconds between steps at segment end
 * @param curveType      0=linear interpolation, 1=sinusoidal (lookup table)
 * @return               true if completed normally, false if interrupted by E-STOP
 */
bool moveSegment(uint8_t joint, uint32_t steps, bool forward,
                 uint16_t startInterval, uint16_t endInterval,
                 uint8_t curveType) {
    if (joint >= NUM_JOINTS || steps == 0) return true;

    // Clamp intervals
    if (startInterval < MIN_STEP_DELAY) startInterval = MIN_STEP_DELAY;
    if (endInterval < MIN_STEP_DELAY) endInterval = MIN_STEP_DELAY;
    if (startInterval > MAX_STEP_DELAY) startInterval = MAX_STEP_DELAY;
    if (endInterval > MAX_STEP_DELAY) endInterval = MAX_STEP_DELAY;

    digitalWrite(dirPins[joint], forward ? HIGH : LOW);
    delayMicroseconds(5);

    for (uint32_t i = 0; i < steps; i++) {
        uint16_t d;

        if (startInterval == endInterval) {
            // Constant speed segment
            d = startInterval;
        } else if (curveType == 1 && steps > 1) {
            // Sinusoidal interpolation via lookup table
            uint8_t idx = (uint8_t)((i * 63UL) / (steps - 1));
            uint8_t t = pgm_read_byte(&sinTable[idx]);
            if (endInterval > startInterval) {
                // Decelerating: start fast, end slow
                uint32_t range = endInterval - startInterval;
                d = startInterval + (uint16_t)((range * t) / 255);
            } else {
                // Accelerating: start slow, end fast
                uint32_t range = startInterval - endInterval;
                d = startInterval - (uint16_t)((range * t) / 255);
            }
        } else {
            // Linear interpolation (default)
            if (endInterval > startInterval) {
                uint32_t range = endInterval - startInterval;
                d = startInterval + (uint16_t)((range * i) / steps);
            } else {
                uint32_t range = startInterval - endInterval;
                d = startInterval - (uint16_t)((range * i) / steps);
            }
        }

        // Check for E-STOP every step during segment execution
        if (Serial.available()) {
            char c = Serial.peek();
            if (c == '!') {
                Serial.read();  // Consume the '!' byte
                setMotorsEnabled(false);
                // Update position with steps completed so far
                if (forward) {
                    position[joint] += i;
                } else {
                    position[joint] -= i;
                }
                Serial.println(F("!! ESTOP"));
                return false;
            }
        }

        digitalWrite(stepPins[joint], HIGH);
        delayMicroseconds(d);
        digitalWrite(stepPins[joint], LOW);
        delayMicroseconds(d);
    }

    // Update position
    if (forward) {
        position[joint] += steps;
    } else {
        position[joint] -= steps;
    }
    return true;
}


/**
 * Coordinated move with sinusoidal acceleration.
 * All joints start/stop together, speed ramps applied to the longest axis.
 * Uses Bresenham-style interpolation for proportional stepping.
 *
 * E-STOP: Checks for '!' byte every 16 master steps.
 *
 * @param target      Target absolute positions for all joints
 * @param cruiseDelay Target cruise speed delay in microseconds
 */
void moveCoordinated(int32_t target[NUM_JOINTS], uint16_t cruiseDelay) {
    int32_t delta[NUM_JOINTS];
    uint32_t absDelta[NUM_JOINTS];
    bool dir[NUM_JOINTS];
    uint32_t maxSteps = 0;

    for (uint8_t i = 0; i < NUM_JOINTS; i++) {
        delta[i] = target[i] - position[i];
        absDelta[i] = abs(delta[i]);
        dir[i] = (delta[i] >= 0);
        if (absDelta[i] > maxSteps) maxSteps = absDelta[i];
    }

    if (maxSteps == 0) return;

    // Set direction pins
    for (uint8_t i = 0; i < NUM_JOINTS; i++) {
        digitalWrite(dirPins[i], dir[i] ? HIGH : LOW);
    }
    delayMicroseconds(5);

    // Bresenham interpolation with sinusoidal ramp on master axis
    int32_t error[NUM_JOINTS] = {0, 0, 0, 0};

    for (uint32_t step = 0; step < maxSteps; step++) {
        uint16_t d = rampDelay(step, maxSteps, cruiseDelay);

        // Check for E-STOP every step
        if (Serial.available()) {
            char c = Serial.peek();
            if (c == '!') {
                Serial.read();
                setMotorsEnabled(false);
                for (uint8_t j = 0; j < NUM_JOINTS; j++) {
                    int32_t stepsCompleted = (int32_t)((absDelta[j] * step) / maxSteps);
                    if (dir[j]) { position[j] += stepsCompleted; }
                    else { position[j] -= stepsCompleted; }
                }
                Serial.println(F("!! ESTOP"));
                return;
            }
        }

        for (uint8_t i = 0; i < NUM_JOINTS; i++) {
            error[i] += absDelta[i];
            if (error[i] >= (int32_t)maxSteps) {
                error[i] -= maxSteps;
                digitalWrite(stepPins[i], HIGH);
            }
        }
        delayMicroseconds(d);

        for (uint8_t i = 0; i < NUM_JOINTS; i++) {
            digitalWrite(stepPins[i], LOW);
        }
        delayMicroseconds(d);
    }

    // Update positions
    for (uint8_t i = 0; i < NUM_JOINTS; i++) {
        position[i] = target[i];
    }
}


/**
 * Parse and execute commands from serial.
 * Protocol is identical to Einsy firmware minus TMC2130-specific commands
 * (C, U, H, T, I are removed — S42C handles those internally via OLED).
 */
void handleCommand(String &cmd) {
    cmd.trim();
    if (cmd.length() == 0) return;

    char type = cmd.charAt(0);

    switch (type) {
        case 'E': {
            if (cmd.length() >= 2) {
                bool en = (cmd.charAt(1) == '1');
                setMotorsEnabled(en);
                Serial.print(F("OK E"));
                Serial.println(en ? '1' : '0');
            }
            break;
        }

        case 'M': {
            int joint = cmd.substring(1, 2).toInt();
            int idx = cmd.indexOf(' ', 1);
            if (idx < 0 || joint < 0 || joint >= NUM_JOINTS) {
                Serial.println(F("ERR PARAM"));
                break;
            }
            long steps = cmd.substring(idx + 1).toInt();
            int dir = 0, delayVal = stepDelayUs;

            idx = cmd.indexOf(' ', idx + 1);
            if (idx > 0) {
                dir = cmd.substring(idx + 1).toInt();
                int idx2 = cmd.indexOf(' ', idx + 1);
                if (idx2 > 0) delayVal = cmd.substring(idx2 + 1).toInt();
            }

            if (steps <= 0 || !motorsEnabled) {
                Serial.println(motorsEnabled ? F("ERR PARAM") : F("ERR DISABLED"));
                break;
            }
            if (delayVal < MIN_STEP_DELAY) delayVal = MIN_STEP_DELAY;
            if (delayVal > MAX_STEP_DELAY) delayVal = MAX_STEP_DELAY;

            moveJoint(joint, steps, (dir == 0), delayVal);
            Serial.print(F("OK M"));
            Serial.print(joint);
            Serial.print(' ');
            Serial.println(position[joint]);
            break;
        }

        case 'G': {
            if (!motorsEnabled) { Serial.println(F("ERR DISABLED")); break; }

            int32_t targets[NUM_JOINTS];
            int delayVal = stepDelayUs;
            int idx = cmd.indexOf(' ');

            for (uint8_t i = 0; i < NUM_JOINTS; i++) {
                if (idx < 0) { Serial.println(F("ERR PARAM")); return; }
                targets[i] = cmd.substring(idx + 1).toInt();
                idx = cmd.indexOf(' ', idx + 1);
            }
            // Optional delay
            if (idx > 0) delayVal = cmd.substring(idx + 1).toInt();
            if (delayVal < MIN_STEP_DELAY) delayVal = MIN_STEP_DELAY;
            if (delayVal > MAX_STEP_DELAY) delayVal = MAX_STEP_DELAY;

            moveCoordinated(targets, delayVal);

            Serial.print(F("OK G "));
            for (uint8_t i = 0; i < NUM_JOINTS; i++) {
                Serial.print(position[i]);
                if (i < NUM_JOINTS - 1) Serial.print(' ');
            }
            Serial.println();
            break;
        }

        case 'S': {
            Serial.print(F("S "));
            Serial.print(motorsEnabled ? '1' : '0');
            for (uint8_t i = 0; i < NUM_JOINTS; i++) {
                Serial.print(' ');
                Serial.print(position[i]);
            }
            Serial.println();
            break;
        }

        case 'R': {
            if (cmd.length() >= 2) {
                int joint = cmd.charAt(1) - '0';
                if (joint >= 0 && joint < NUM_JOINTS) {
                    position[joint] = 0;
                    Serial.print(F("OK R"));
                    Serial.println(joint);
                } else {
                    Serial.println(F("ERR PARAM"));
                }
            } else {
                for (uint8_t i = 0; i < NUM_JOINTS; i++) position[i] = 0;
                Serial.println(F("OK R"));
            }
            break;
        }

        case 'X': {
            // Segment move: X <joint> <steps> <dir> <start_interval> <end_interval> <curve_type>
            // Executes a single motion segment with interval interpolation.
            // Pi-side planner computes the S-curve; MCU interpolates within segment.
            if (!motorsEnabled) { Serial.println(F("ERR DISABLED")); break; }

            int idx = cmd.indexOf(' ');
            if (idx < 0) { Serial.println(F("ERR PARAM")); break; }

            int joint = cmd.substring(idx + 1).toInt();
            idx = cmd.indexOf(' ', idx + 1);
            if (idx < 0 || joint < 0 || joint >= NUM_JOINTS) {
                Serial.println(F("ERR PARAM")); break;
            }

            long steps = cmd.substring(idx + 1).toInt();
            idx = cmd.indexOf(' ', idx + 1);
            if (idx < 0 || steps <= 0) { Serial.println(F("ERR PARAM")); break; }

            int dir = cmd.substring(idx + 1).toInt();
            idx = cmd.indexOf(' ', idx + 1);
            if (idx < 0) { Serial.println(F("ERR PARAM")); break; }

            int startInt = cmd.substring(idx + 1).toInt();
            idx = cmd.indexOf(' ', idx + 1);
            if (idx < 0) { Serial.println(F("ERR PARAM")); break; }

            int endInt = cmd.substring(idx + 1).toInt();
            idx = cmd.indexOf(' ', idx + 1);

            int curveType = 0;
            if (idx > 0) {
                curveType = cmd.substring(idx + 1).toInt();
            }

            bool completed = moveSegment(
                (uint8_t)joint, (uint32_t)steps, (dir == 0),
                (uint16_t)startInt, (uint16_t)endInt, (uint8_t)curveType
            );

            if (completed) {
                Serial.print(F("OK X"));
                Serial.print(joint);
                Serial.print(' ');
                Serial.println(position[joint]);
            }
            // If not completed (E-STOP), the ESTOP response was already sent
            break;
        }

        // --- Interactive shortcuts ---
        case 'e':
            setMotorsEnabled(true);
            Serial.println(F("OK E1"));
            break;
        case 'd':
        case 's':
            setMotorsEnabled(false);
            Serial.println(F("OK E0"));
            break;

        case '?':
            Serial.println(F("=== Armold RAMPS + S42C Controller ==="));
            Serial.println(F("Protocol:"));
            Serial.println(F("  E1/E0         - Enable/disable motors"));
            Serial.println(F("  M<j> <s> <d> <dly> - Move single joint"));
            Serial.println(F("  G <p0> <p1> <p2> <p3> [dly] - Coordinated move"));
            Serial.println(F("  X <j> <s> <d> <si> <ei> <c> - Segment move"));
            Serial.println(F("  S             - Query state"));
            Serial.println(F("  R / R<j>      - Reset positions"));
            Serial.println(F("  !             - E-STOP (mid-move halt)"));
            Serial.println();
            Serial.print(F("State: "));
            Serial.print(motorsEnabled ? "EN" : "DIS");
            Serial.print(F(" DLY="));
            Serial.print(stepDelayUs);
            Serial.print(F(" POS="));
            for (uint8_t i = 0; i < NUM_JOINTS; i++) {
                Serial.print(position[i]);
                if (i < NUM_JOINTS - 1) Serial.print(',');
            }
            Serial.println();
            Serial.print(F("Steps/rev="));
            Serial.print(STEPS_PER_OUTPUT_REV);
            Serial.print(F(" ("));
            Serial.print(MICROSTEPS);
            Serial.println(F(" ustep, 20:1 gearbox)"));
            break;

        default:
            Serial.print(F("ERR CMD "));
            Serial.println(type);
            break;
    }
}


void setup() {
    Serial.begin(250000);

    // Configure pins — no SPI needed (S42C handles driver control internally)
    for (uint8_t i = 0; i < NUM_JOINTS; i++) {
        pinMode(stepPins[i], OUTPUT);
        pinMode(dirPins[i], OUTPUT);
        pinMode(enPins[i], OUTPUT);
    }

    // Disable motors during setup (active LOW enable)
    setMotorsEnabled(false);

    Serial.println(F(""));
    Serial.println(F("ARMOLD RAMPS_S42C 1.0"));
    Serial.println(F("BTT S42C closed-loop, 4-axis"));
    Serial.print(F("Microsteps: "));
    Serial.print(MICROSTEPS);
    Serial.print(F(", Steps/output rev: "));
    Serial.println(STEPS_PER_OUTPUT_REV);
    Serial.println(F("READY"));
}

void loop() {
    if (Serial.available()) {
        // Check for single-byte E-STOP outside of move context
        char c = Serial.peek();
        if (c == '!') {
            Serial.read();  // Consume
            setMotorsEnabled(false);
            Serial.println(F("!! ESTOP"));
            return;
        }

        String cmd = Serial.readStringUntil('\n');
        handleCommand(cmd);
    }
}
