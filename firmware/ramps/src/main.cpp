/**
 * Armold - RAMPS 1.4 Stepper Controller (TMC2208, ROS 2 Bridge Compatible)
 *
 * Firmware for RAMPS 1.4 shield on Arduino Mega 2560 with TMC2208 drivers.
 * Supports both interactive serial commands and a structured protocol for
 * the ROS 2 bridge node running on the Raspberry Pi.
 *
 * TMC2208: 16 microsteps, StealthChop, active LOW enable
 * 3200 microsteps per revolution (200 full steps * 16)
 *
 * RAMPS 1.4 pin assignments:
 *   Joint 0 (X): STEP=54, DIR=55, ENABLE=38
 *   Joint 1 (Y): STEP=60, DIR=61, ENABLE=56
 *   Joint 2 (Z): STEP=46, DIR=48, ENABLE=62
 *
 * Protocol commands (newline terminated):
 *   E1          - Enable all motors
 *   E0          - Disable all motors
 *   M<j> <steps> <dir> <delay>  - Move joint j by steps (dir: 0=fwd, 1=rev, delay in us)
 *   G <pos0> <pos1> <pos2> <delay> - Coordinated move all joints to absolute positions
 *   S           - Query state (returns position counters)
 *   R           - Reset all position counters
 *   R<j>        - Reset single joint position (e.g. R1)
 *   ?           - Print help
 *
 * Interactive shortcuts (single char, for manual testing):
 *   e/d/s       - Enable/disable/stop
 *   0/1/2       - Move joint full revolution
 *   r/f/w       - Reverse/faster/slower
 *
 * Power: 24V DC, 10A
 */

#include <Arduino.h>

// --- Pin Definitions ---
#define J0_STEP_PIN  54
#define J0_DIR_PIN   55
#define J0_EN_PIN    38

#define J1_STEP_PIN  60
#define J1_DIR_PIN   61
#define J1_EN_PIN    56

#define J2_STEP_PIN  46
#define J2_DIR_PIN   48
#define J2_EN_PIN    62

// --- Configuration ---
#define MICROSTEPS          8
#define FULL_STEPS_PER_REV  200
#define STEPS_PER_REV       (FULL_STEPS_PER_REV * MICROSTEPS)

#define DEFAULT_STEP_DELAY  200
#define MIN_STEP_DELAY      50
#define MAX_STEP_DELAY      5000
#define DELAY_INCREMENT     50

// --- State ---
bool motorsEnabled = false;
bool reverseDirection = false;
uint16_t stepDelayUs = DEFAULT_STEP_DELAY;
int32_t position[3] = {0, 0, 0};  // Track position in microsteps

// --- Pin lookup tables ---
const uint8_t stepPins[3] = {J0_STEP_PIN, J1_STEP_PIN, J2_STEP_PIN};
const uint8_t dirPins[3]  = {J0_DIR_PIN,  J1_DIR_PIN,  J2_DIR_PIN};
const uint8_t enPins[3]   = {J0_EN_PIN,   J1_EN_PIN,   J2_EN_PIN};

/**
 * Enable or disable all stepper motor drivers.
 */
void setMotorsEnabled(bool enabled) {
    uint8_t state = enabled ? LOW : HIGH;
    for (uint8_t i = 0; i < 3; i++) {
        digitalWrite(enPins[i], state);
    }
    motorsEnabled = enabled;
}

/**
 * Move a single joint by a given number of microsteps.
 *
 * @param joint     Joint index (0-2)
 * @param steps     Number of microsteps
 * @param forward   Direction
 * @param delayUs   Microseconds between step pulses
 */
void moveJoint(uint8_t joint, uint32_t steps, bool forward, uint16_t delayUs) {
    if (joint > 2) return;

    digitalWrite(dirPins[joint], forward ? HIGH : LOW);
    delayMicroseconds(5);

    for (uint32_t i = 0; i < steps; i++) {
        digitalWrite(stepPins[joint], HIGH);
        delayMicroseconds(delayUs);
        digitalWrite(stepPins[joint], LOW);
        delayMicroseconds(delayUs);
    }

    // Track position
    if (forward) {
        position[joint] += steps;
    } else {
        position[joint] -= steps;
    }
}

/**
 * Coordinated move: move all 3 joints simultaneously to target positions.
 * Uses Bresenham-style interpolation so all joints start and stop together.
 *
 * @param target    Target positions for joints 0, 1, 2
 * @param delayUs   Base step delay in microseconds
 */
void moveCoordinated(int32_t target[3], uint16_t delayUs) {
    int32_t delta[3];
    uint32_t absDelta[3];
    bool dir[3];
    uint32_t maxSteps = 0;

    for (uint8_t i = 0; i < 3; i++) {
        delta[i] = target[i] - position[i];
        absDelta[i] = abs(delta[i]);
        dir[i] = (delta[i] >= 0);
        if (absDelta[i] > maxSteps) maxSteps = absDelta[i];
    }

    if (maxSteps == 0) return;

    // Set direction pins
    for (uint8_t i = 0; i < 3; i++) {
        digitalWrite(dirPins[i], dir[i] ? HIGH : LOW);
    }
    delayMicroseconds(5);

    // Bresenham interpolation: step each joint proportionally
    int32_t error[3] = {0, 0, 0};

    for (uint32_t step = 0; step < maxSteps; step++) {
        for (uint8_t i = 0; i < 3; i++) {
            error[i] += absDelta[i];
            if (error[i] >= (int32_t)maxSteps) {
                error[i] -= maxSteps;
                digitalWrite(stepPins[i], HIGH);
            }
        }
        delayMicroseconds(delayUs);

        for (uint8_t i = 0; i < 3; i++) {
            digitalWrite(stepPins[i], LOW);
        }
        delayMicroseconds(delayUs);
    }

    // Update positions
    for (uint8_t i = 0; i < 3; i++) {
        position[i] = target[i];
    }
}

/**
 * Parse and execute a structured command from serial.
 * Commands are newline-terminated strings.
 */
void handleCommand(String &cmd) {
    cmd.trim();
    if (cmd.length() == 0) return;

    char type = cmd.charAt(0);

    switch (type) {
        case 'E': {
            // E1 = enable, E0 = disable
            if (cmd.length() >= 2) {
                bool en = (cmd.charAt(1) == '1');
                setMotorsEnabled(en);
                Serial.print(F("OK E"));
                Serial.println(en ? '1' : '0');
            }
            break;
        }

        case 'M': {
            // M<joint> <steps> <dir> <delay>
            // Example: M0 3200 0 800
            int joint = -1;
            long steps = 0;
            int dir = 0;
            int delayVal = stepDelayUs;

            int idx = 1;
            joint = cmd.substring(idx, idx + 1).toInt();
            idx = cmd.indexOf(' ', idx);
            if (idx < 0) break;
            steps = cmd.substring(idx + 1).toInt();

            idx = cmd.indexOf(' ', idx + 1);
            if (idx > 0) {
                dir = cmd.substring(idx + 1).toInt();
                int idx2 = cmd.indexOf(' ', idx + 1);
                if (idx2 > 0) {
                    delayVal = cmd.substring(idx2 + 1).toInt();
                }
            }

            if (joint < 0 || joint > 2 || steps <= 0) {
                Serial.println(F("ERR PARAM"));
                break;
            }

            if (!motorsEnabled) {
                Serial.println(F("ERR DISABLED"));
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

        case 'S': {
            // Query state
            Serial.print(F("S "));
            Serial.print(motorsEnabled ? '1' : '0');
            Serial.print(' ');
            Serial.print(position[0]);
            Serial.print(' ');
            Serial.print(position[1]);
            Serial.print(' ');
            Serial.println(position[2]);
            break;
        }

        case 'G': {
            // G <pos0> <pos1> <pos2> <delay>
            // Coordinated move all joints to absolute positions simultaneously
            if (!motorsEnabled) {
                Serial.println(F("ERR DISABLED"));
                break;
            }

            int32_t targets[3];
            int delayVal = stepDelayUs;

            // Parse: "G pos0 pos1 pos2 [delay]"
            int idx = cmd.indexOf(' ');
            if (idx < 0) { Serial.println(F("ERR PARAM")); break; }
            targets[0] = cmd.substring(idx + 1).toInt();

            idx = cmd.indexOf(' ', idx + 1);
            if (idx < 0) { Serial.println(F("ERR PARAM")); break; }
            targets[1] = cmd.substring(idx + 1).toInt();

            idx = cmd.indexOf(' ', idx + 1);
            if (idx < 0) { Serial.println(F("ERR PARAM")); break; }
            targets[2] = cmd.substring(idx + 1).toInt();

            // Optional delay parameter
            idx = cmd.indexOf(' ', idx + 1);
            if (idx > 0) {
                delayVal = cmd.substring(idx + 1).toInt();
            }

            if (delayVal < MIN_STEP_DELAY) delayVal = MIN_STEP_DELAY;
            if (delayVal > MAX_STEP_DELAY) delayVal = MAX_STEP_DELAY;

            moveCoordinated(targets, delayVal);

            Serial.print(F("OK G "));
            Serial.print(position[0]);
            Serial.print(' ');
            Serial.print(position[1]);
            Serial.print(' ');
            Serial.println(position[2]);
            break;
        }

        case 'R': {
            // Reset position counters
            // R  = reset all, R0/R1/R2 = reset single joint
            if (cmd.length() >= 2) {
                int joint = cmd.charAt(1) - '0';
                if (joint >= 0 && joint <= 2) {
                    position[joint] = 0;
                    Serial.print(F("OK R"));
                    Serial.println(joint);
                } else {
                    Serial.println(F("ERR PARAM"));
                }
            } else {
                position[0] = 0;
                position[1] = 0;
                position[2] = 0;
                Serial.println(F("OK R"));
            }
            break;
        }

        // --- Interactive shortcuts (single char) ---
        case 'e':
            setMotorsEnabled(true);
            Serial.println(F("OK E1"));
            break;

        case 'd':
        case 's':
            setMotorsEnabled(false);
            Serial.println(F("OK E0"));
            break;

        case '0':
        case '1':
        case '2': {
            if (!motorsEnabled) {
                Serial.println(F("ERR DISABLED"));
                break;
            }
            uint8_t j = type - '0';
            moveJoint(j, STEPS_PER_REV, !reverseDirection, stepDelayUs);
            Serial.print(F("OK M"));
            Serial.print(j);
            Serial.print(' ');
            Serial.println(position[j]);
            break;
        }

        case 'r':
            reverseDirection = !reverseDirection;
            Serial.print(F("DIR "));
            Serial.println(reverseDirection ? '1' : '0');
            break;

        case 'f':
            if (stepDelayUs > MIN_STEP_DELAY) {
                stepDelayUs -= DELAY_INCREMENT;
                if (stepDelayUs < MIN_STEP_DELAY) stepDelayUs = MIN_STEP_DELAY;
            }
            Serial.print(F("DLY "));
            Serial.println(stepDelayUs);
            break;

        case 'w':
            if (stepDelayUs < MAX_STEP_DELAY) {
                stepDelayUs += DELAY_INCREMENT;
                if (stepDelayUs > MAX_STEP_DELAY) stepDelayUs = MAX_STEP_DELAY;
            }
            Serial.print(F("DLY "));
            Serial.println(stepDelayUs);
            break;

        case '?':
            Serial.println(F("=== Armold RAMPS Controller ==="));
            Serial.println(F("Protocol: E1/E0, M<j> <steps> <dir> <delay>, S, R"));
            Serial.println(F("Interactive: e/d/s/0/1/2/r/f/w/?"));
            Serial.print(F("State: "));
            Serial.print(motorsEnabled ? "EN" : "DIS");
            Serial.print(F(" DLY="));
            Serial.print(stepDelayUs);
            Serial.print(F(" POS="));
            Serial.print(position[0]);
            Serial.print(',');
            Serial.print(position[1]);
            Serial.print(',');
            Serial.println(position[2]);
            break;

        default:
            Serial.print(F("ERR CMD "));
            Serial.println(type);
            break;
    }
}

void setup() {
    Serial.begin(115200);

    for (uint8_t i = 0; i < 3; i++) {
        pinMode(stepPins[i], OUTPUT);
        pinMode(dirPins[i], OUTPUT);
        pinMode(enPins[i], OUTPUT);
    }

    setMotorsEnabled(false);

    Serial.println(F("ARMOLD RAMPS 1.0"));
    Serial.println(F("TMC2208/A4988 8ustep 1600/rev"));
    Serial.println(F("READY"));
}

void loop() {
    if (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        handleCommand(cmd);
    }
}
