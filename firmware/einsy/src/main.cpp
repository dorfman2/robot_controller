/**
 * Armold - Einsy RAMBo 1.1a Stepper Controller (TMC2130 SPI)
 *
 * Firmware for Einsy RAMBo board with 4 onboard TMC2130 drivers controlled
 * via SPI. Supports coordinated multi-joint motion, runtime configuration
 * of current/microstepping, and sensorless homing via StallGuard.
 *
 * Hardware: Einsy RAMBo 1.1a (ATmega2560 + 4x TMC2130)
 * Axes: X=Joint0(Base), Y=Joint1(Shoulder), Z=Joint2(Elbow), E=Joint3(Wrist)
 *
 * Pin Mapping (from Prusa/Klipper configs):
 *   Joint 0 (X): STEP=37(PC0), DIR=49(PL0), EN=29(PA7), CS=41(PG0), DIAG=PK2
 *   Joint 1 (Y): STEP=36(PC1), DIR=48(PL1), EN=28(PA6), CS=39(PG2), DIAG=PK7
 *   Joint 2 (Z): STEP=35(PC2), DIR=47(PL2), EN=27(PA5), CS=67(PK5), DIAG=PK6
 *   Joint 3 (E): STEP=34(PC3), DIR=43(PL6), EN=26(PA4), CS=66(PK4), DIAG=PK3
 *
 * Protocol commands (newline terminated):
 *   E1              - Enable all motors
 *   E0              - Disable all motors
 *   M<j> <steps> <dir> <delay> - Move single joint
 *   G <p0> <p1> <p2> <p3> [delay] - Coordinated move all joints
 *   S               - Query state
 *   R / R<j>        - Reset position counters
 *   C <current_mA>  - Set motor current (all axes)
 *   U <microsteps>  - Set microstepping (all axes, 1-256)
 *   H<j>            - Home joint using StallGuard sensorless homing
 *   T               - Toggle StealthChop/SpreadCycle
 *   I               - Print driver diagnostics
 *   ?               - Print help
 *
 * Power: 24V DC, 10A
 */

#include <Arduino.h>
#include <SPI.h>
#include <TMCStepper.h>

// --- Number of joints on this board ---
#define NUM_JOINTS 4

// --- Pin Definitions (Einsy RAMBo 1.1a) ---
// Joint 0 (X axis)
#define J0_STEP_PIN  37  // PC0
#define J0_DIR_PIN   49  // PL0
#define J0_EN_PIN    29  // PA7
#define J0_CS_PIN    41  // PG0
#define J0_DIAG_PIN  A10 // PK2

// Joint 1 (Y axis)
#define J1_STEP_PIN  36  // PC1
#define J1_DIR_PIN   48  // PL1
#define J1_EN_PIN    28  // PA6
#define J1_CS_PIN    39  // PG2
#define J1_DIAG_PIN  A15 // PK7

// Joint 2 (Z axis)
#define J2_STEP_PIN  35  // PC2
#define J2_DIR_PIN   47  // PL2
#define J2_EN_PIN    27  // PA5
#define J2_CS_PIN    67  // PK5 (A13)
#define J2_DIAG_PIN  A14 // PK6

// Joint 3 (E axis)
#define J3_STEP_PIN  34  // PC3
#define J3_DIR_PIN   43  // PL6
#define J3_EN_PIN    26  // PA4
#define J3_CS_PIN    66  // PK4 (A12)
#define J3_DIAG_PIN  A11 // PK3

// --- TMC2130 Configuration ---
#define R_SENSE       0.22f   // Einsy uses 0.22 ohm sense resistors
#define DEFAULT_CURRENT_MA  1200
#define DEFAULT_MICROSTEPS  16
#define DEFAULT_STEP_DELAY  80    // Cruise speed (microseconds between steps)
#define MIN_STEP_DELAY      20    // Absolute max speed
#define MAX_STEP_DELAY      5000
#define START_STEP_DELAY    600   // Initial speed for acceleration ramp
#define ACCEL_STEPS         300   // Steps to accelerate from start to cruise speed
#define DECEL_STEPS         300   // Steps to decelerate from cruise to stop

// --- Configuration ---
#define FULL_STEPS_PER_REV  200

// --- Driver instances (SPI) ---
TMC2130Stepper driver0(J0_CS_PIN, R_SENSE);
TMC2130Stepper driver1(J1_CS_PIN, R_SENSE);
TMC2130Stepper driver2(J2_CS_PIN, R_SENSE);
TMC2130Stepper driver3(J3_CS_PIN, R_SENSE);

TMC2130Stepper* drivers[NUM_JOINTS] = {&driver0, &driver1, &driver2, &driver3};

// --- Pin lookup tables ---
const uint8_t stepPins[NUM_JOINTS]  = {J0_STEP_PIN, J1_STEP_PIN, J2_STEP_PIN, J3_STEP_PIN};
const uint8_t dirPins[NUM_JOINTS]   = {J0_DIR_PIN,  J1_DIR_PIN,  J2_DIR_PIN,  J3_DIR_PIN};
const uint8_t enPins[NUM_JOINTS]    = {J0_EN_PIN,   J1_EN_PIN,   J2_EN_PIN,   J3_EN_PIN};
const uint8_t diagPins[NUM_JOINTS]  = {J0_DIAG_PIN, J1_DIAG_PIN, J2_DIAG_PIN, J3_DIAG_PIN};

// --- State ---
bool motorsEnabled = false;
bool stealthChop = false;  // SpreadCycle: better dynamic torque for robot arm
uint16_t stepDelayUs = DEFAULT_STEP_DELAY;
uint16_t currentMA = DEFAULT_CURRENT_MA;
uint16_t microsteps = DEFAULT_MICROSTEPS;
int32_t position[NUM_JOINTS] = {0, 0, 0, 0};

/**
 * Configure a single TMC2130 driver via SPI.
 */
void configureDriver(TMC2130Stepper &drv, uint8_t index) {
    drv.begin();
    drv.toff(4);                        // Enable driver
    drv.rms_current(currentMA);         // Set motor current
    drv.microsteps(microsteps);         // Set microstepping
    drv.en_pwm_mode(stealthChop);       // StealthChop
    drv.pwm_autoscale(true);            // Auto-scale PWM
    drv.intpol(true);                   // Interpolate to 256 microsteps
    drv.TCOOLTHRS(0xFFFFF);             // Enable StallGuard at all speeds
    drv.sgt(63);                        // StallGuard sensitivity (0=most sensitive, 63=least)
    drv.diag1_stall(true);              // DIAG1 pin = stallGuard output

    // Verify communication
    uint8_t version = drv.version();
    Serial.print(F("  Joint "));
    Serial.print(index);
    if (version == 0x11) {
        Serial.println(F(": OK (TMC2130)"));
    } else {
        Serial.print(F(": COMM ERROR (ver=0x"));
        Serial.print(version, HEX);
        Serial.println(F(")"));
    }
}

/**
 * Enable or disable all stepper motor drivers.
 */
void setMotorsEnabled(bool enabled) {
    uint8_t state = enabled ? LOW : HIGH;
    for (uint8_t i = 0; i < NUM_JOINTS; i++) {
        digitalWrite(enPins[i], state);
    }
    motorsEnabled = enabled;
}

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
 * Move a single joint with trapezoidal acceleration.
 */
void moveJoint(uint8_t joint, uint32_t steps, bool forward, uint16_t cruiseDelay) {
    if (joint >= NUM_JOINTS) return;

    digitalWrite(dirPins[joint], forward ? HIGH : LOW);
    delayMicroseconds(5);

    for (uint32_t i = 0; i < steps; i++) {
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

        // Check for E-STOP every 16 steps during segment execution
        if ((i & 0x0F) == 0 && Serial.available()) {
            char c = Serial.peek();
            if (c == 'E') {
                String ecmd = Serial.readStringUntil('\n');
                setMotorsEnabled(false);
                // Update position with steps completed so far
                if (forward) {
                    position[joint] += i;
                } else {
                    position[joint] -= i;
                }
                Serial.println(F("OK E0"));
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
 * Coordinated move with trapezoidal acceleration.
 * All joints start/stop together, speed ramps applied to the longest axis.
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

    // Bresenham interpolation with trapezoidal ramp on master axis
    int32_t error[NUM_JOINTS] = {0, 0, 0, 0};

    // Calculate accel/decel bounds for StallGuard check window
    uint16_t accelEnd = ACCEL_STEPS;
    uint16_t decelStart = maxSteps > DECEL_STEPS ? maxSteps - DECEL_STEPS : 0;
    if (maxSteps < (uint32_t)(ACCEL_STEPS + DECEL_STEPS)) {
        accelEnd = maxSteps / 2;
        decelStart = maxSteps - (maxSteps / 2);
    }

    for (uint32_t step = 0; step < maxSteps; step++) {
        uint16_t d = rampDelay(step, maxSteps, cruiseDelay);

        // --- Halt check: serial E-STOP only (StallGuard disabled for gearbox) ---
        if (step > accelEnd && step < decelStart && (step % 16 == 0)) {
            // Check for serial E-STOP (user-initiated)
            if (Serial.available()) {
                char c = Serial.peek();
                if (c == 'E') {
                    String ecmd = Serial.readStringUntil('\n');
                    setMotorsEnabled(false);
                    // Update position to where we actually stopped
                    for (uint8_t j = 0; j < NUM_JOINTS; j++) {
                        int32_t stepsCompleted = (int32_t)((uint64_t)absDelta[j] * step / maxSteps);
                        position[j] += dir[j] ? stepsCompleted : -stepsCompleted;
                    }
                    Serial.println(F("OK E0"));
                    return;
                }
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
 * Sensorless homing for a single joint using StallGuard.
 * Moves in reverse until stall is detected, then sets position to 0.
 */
void homeJoint(uint8_t joint) {
    if (joint >= NUM_JOINTS || !motorsEnabled) {
        Serial.println(F("ERR DISABLED"));
        return;
    }

    TMC2130Stepper &drv = *drivers[joint];

    // Switch to SpreadCycle for reliable StallGuard
    drv.en_pwm_mode(false);
    delay(100);

    // Move in reverse direction until stall
    digitalWrite(dirPins[joint], LOW);  // Reverse
    delayMicroseconds(5);

    Serial.print(F("Homing J"));
    Serial.print(joint);
    Serial.print(F("..."));

    uint32_t maxSteps = 100000;  // Safety limit
    bool stalled = false;

    for (uint32_t i = 0; i < maxSteps; i++) {
        digitalWrite(stepPins[joint], HIGH);
        delayMicroseconds(400);  // Slower for homing
        digitalWrite(stepPins[joint], LOW);
        delayMicroseconds(400);

        // Check StallGuard (DIAG pin goes HIGH on stall)
        if (digitalRead(diagPins[joint]) == HIGH) {
            stalled = true;
            break;
        }
    }

    // Restore StealthChop if it was enabled
    drv.en_pwm_mode(stealthChop);

    if (stalled) {
        position[joint] = 0;
        Serial.println(F(" OK (stall detected)"));
    } else {
        Serial.println(F(" WARN (no stall, limit reached)"));
    }
}

/**
 * Print driver diagnostics for all joints.
 */
void printDiagnostics() {
    Serial.println(F("--- TMC2130 Diagnostics ---"));
    for (uint8_t i = 0; i < NUM_JOINTS; i++) {
        TMC2130Stepper &drv = *drivers[i];
        Serial.print(F("  J"));
        Serial.print(i);
        Serial.print(F(": "));

        if (drv.ot()) Serial.print(F("OVERTEMP! "));
        if (drv.otpw()) Serial.print(F("OT_WARN "));
        if (drv.s2ga() || drv.s2gb()) Serial.print(F("SHORT_GND "));
        if (drv.ola() || drv.olb()) Serial.print(F("OPEN_LOAD "));
        if (drv.stallguard()) Serial.print(F("[STALL] "));
        if (drv.stst()) Serial.print(F("standstill "));

        Serial.print(F("SG="));
        Serial.print(drv.sg_result());
        Serial.print(F(" cs="));
        Serial.println(drv.cs_actual());
    }
    Serial.print(F("  Current: "));
    Serial.print(currentMA);
    Serial.print(F("mA, Microsteps: "));
    Serial.print(microsteps);
    Serial.print(F(", Mode: "));
    Serial.println(stealthChop ? "StealthChop" : "SpreadCycle");
    Serial.println(F("---------------------------"));
}

/**
 * Parse and execute commands.
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

        case 'C': {
            // Set current: C <mA>
            int idx = cmd.indexOf(' ');
            if (idx > 0) {
                currentMA = cmd.substring(idx + 1).toInt();
                if (currentMA < 100) currentMA = 100;
                if (currentMA > 1500) currentMA = 1500;
                for (uint8_t i = 0; i < NUM_JOINTS; i++) {
                    drivers[i]->rms_current(currentMA);
                }
                Serial.print(F("OK C "));
                Serial.println(currentMA);
            } else {
                Serial.println(F("ERR PARAM"));
            }
            break;
        }

        case 'U': {
            // Set microstepping: U <steps>
            int idx = cmd.indexOf(' ');
            if (idx > 0) {
                uint16_t ms = cmd.substring(idx + 1).toInt();
                // Validate: must be power of 2, 1-256
                if (ms == 1 || ms == 2 || ms == 4 || ms == 8 ||
                    ms == 16 || ms == 32 || ms == 64 || ms == 128 || ms == 256) {
                    microsteps = ms;
                    for (uint8_t i = 0; i < NUM_JOINTS; i++) {
                        drivers[i]->microsteps(microsteps);
                    }
                    Serial.print(F("OK U "));
                    Serial.println(microsteps);
                } else {
                    Serial.println(F("ERR PARAM (1,2,4,8,16,32,64,128,256)"));
                }
            } else {
                Serial.println(F("ERR PARAM"));
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
            // If not completed (E-STOP), the E0 response was already sent
            break;
        }

        case 'H': {
            // Home joint: H<j>
            if (cmd.length() >= 2) {
                int joint = cmd.charAt(1) - '0';
                if (joint >= 0 && joint < NUM_JOINTS) {
                    homeJoint(joint);
                } else {
                    Serial.println(F("ERR PARAM"));
                }
            } else {
                Serial.println(F("Usage: H0, H1, H2, H3"));
            }
            break;
        }

        case 'T': {
            // Toggle StealthChop / SpreadCycle
            stealthChop = !stealthChop;
            for (uint8_t i = 0; i < NUM_JOINTS; i++) {
                drivers[i]->en_pwm_mode(stealthChop);
            }
            Serial.print(F("OK T "));
            Serial.println(stealthChop ? "StealthChop" : "SpreadCycle");
            break;
        }

        case 'I': {
            printDiagnostics();
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
            Serial.println(F("=== Armold Einsy RAMBo Controller ==="));
            Serial.println(F("Protocol:"));
            Serial.println(F("  E1/E0         - Enable/disable motors"));
            Serial.println(F("  M<j> <s> <d> <dly> - Move single joint"));
            Serial.println(F("  G <p0> <p1> <p2> <p3> [dly] - Coordinated move"));
            Serial.println(F("  S             - Query state"));
            Serial.println(F("  R / R<j>      - Reset positions"));
            Serial.println(F("  C <mA>        - Set current (100-1500)"));
            Serial.println(F("  U <usteps>    - Set microstepping (1-256)"));
            Serial.println(F("  H<j>          - Sensorless home joint"));
            Serial.println(F("  T             - Toggle Stealth/Spread"));
            Serial.println(F("  I             - Driver diagnostics"));
            Serial.println();
            Serial.print(F("State: "));
            Serial.print(motorsEnabled ? "EN" : "DIS");
            Serial.print(F(" I="));
            Serial.print(currentMA);
            Serial.print(F("mA U="));
            Serial.print(microsteps);
            Serial.print(F(" DLY="));
            Serial.print(stepDelayUs);
            Serial.print(F(" POS="));
            for (uint8_t i = 0; i < NUM_JOINTS; i++) {
                Serial.print(position[i]);
                if (i < NUM_JOINTS - 1) Serial.print(',');
            }
            Serial.println();
            break;

        default:
            Serial.print(F("ERR CMD "));
            Serial.println(type);
            break;
    }
}

void setup() {
    Serial.begin(115200);

    // Initialize SPI for TMC2130 communication
    SPI.begin();

    // Configure pins
    for (uint8_t i = 0; i < NUM_JOINTS; i++) {
        pinMode(stepPins[i], OUTPUT);
        pinMode(dirPins[i], OUTPUT);
        pinMode(enPins[i], OUTPUT);
        pinMode(diagPins[i], INPUT);
    }

    // Disable motors during setup
    setMotorsEnabled(false);

    Serial.println(F(""));
    Serial.println(F("ARMOLD EINSY 1.0"));
    Serial.println(F("TMC2130 SPI, 4-axis"));
    Serial.println(F("Initializing drivers..."));

    // Configure TMC2130 drivers via SPI
    for (uint8_t i = 0; i < NUM_JOINTS; i++) {
        configureDriver(*drivers[i], i);
    }

    Serial.print(F("Current: "));
    Serial.print(currentMA);
    Serial.print(F("mA, Microsteps: "));
    Serial.print(microsteps);
    Serial.print(F(", Mode: "));
    Serial.println(stealthChop ? "StealthChop" : "SpreadCycle");
    Serial.println(F("READY"));
}

void loop() {
    if (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        handleCommand(cmd);
    }
}
