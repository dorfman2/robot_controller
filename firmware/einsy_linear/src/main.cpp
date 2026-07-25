/**
 * Armold - Einsy RAMBo 1.1a Linear Rail Controller (TMC2130 SPI, X-axis)
 *
 * Firmware for Einsy RAMBo board using a single TMC2130 X-axis driver to
 * control a NEMA 17 stepper on a linear rail. Provides StallGuard
 * sensorless homing, soft limits, sinusoidal acceleration ramp, and
 * E-STOP interrupt.
 *
 * Hardware: Einsy RAMBo 1.1a (ATmega2560 + TMC2130 X-axis)
 * Axis: X = Linear rail translation
 *
 * Pin Mapping (Einsy RAMBo X-axis):
 *   X: STEP=37(PC0), DIR=49(PL0), EN=29(PA7), CS=41(PG0), DIAG=PK2
 *
 * Protocol commands (newline terminated):
 *   E1 / E0                        - Enable/disable motor
 *   M0 <steps> <dir> <delay>       - Move linear axis
 *   S                              - Query state: "S <enabled> <position>"
 *   R                              - Reset position to 0
 *   H                              - Home (StallGuard sensorless)
 *   !                              - E-STOP (halt immediately)
 *   ?                              - Print help
 *
 * Power: 24V DC, 10A
 */

#include <Arduino.h>
#include <SPI.h>
#include <TMCStepper.h>

// --- Linear Rail Configuration ---
// Steps per millimeter depends on drive mechanism:
//   GT2 belt, 20T pulley: 80 steps/mm (16 microsteps * 200 full steps / 40mm per rev)
//   Lead screw 8mm pitch: 400 steps/mm
//   Lead screw 2mm pitch: 1600 steps/mm
#define STEPS_PER_MM          80    // Default: GT2 belt + 20T pulley

// Maximum travel in millimeters (set to rail length)
#define MAX_TRAVEL_MM         350   // 18" rail, ~350mm usable (centers at 175mm)

// Derived soft limit in steps
#define MAX_TRAVEL_STEPS      ((int32_t)STEPS_PER_MM * MAX_TRAVEL_MM)

// --- Pin Definitions (Einsy RAMBo X-axis) ---
#define X_STEP_PIN    37  // PC0
#define X_DIR_PIN     49  // PL0
#define X_EN_PIN      29  // PA7
#define X_CS_PIN      41  // PG0
#define X_DIAG_PIN    A10 // PK2 (PCINT18)

// --- TMC2130 Configuration ---
#define R_SENSE             0.22f   // Einsy uses 0.22 ohm sense resistors
#define DEFAULT_CURRENT_MA  1000    // 1000mA RMS for linear rail (no gearbox)
#define DEFAULT_MICROSTEPS  16
#define DEFAULT_STEP_DELAY  80      // Cruise speed (microseconds between steps)
#define MIN_STEP_DELAY      20      // Absolute max speed
#define MAX_STEP_DELAY      5000
#define START_STEP_DELAY    600     // Initial speed for acceleration ramp
#define ACCEL_STEPS         300     // Steps to accelerate from start to cruise
#define DECEL_STEPS         300     // Steps to decelerate from cruise to stop

// --- Homing Configuration ---
#define HOMING_FAST_DELAY   80      // Fast approach speed (µs per half-step)
#define HOMING_SLOW_DELAY   200     // Slow recheck speed (µs per half-step)
#define HOMING_MAX_STEPS    100000  // Safety limit for homing travel
#define HOMING_BACKOFF      400     // Steps to back off after stall detection (5mm at 80 steps/mm)
#define STALLGUARD_SGT      7       // StallGuard sensitivity (0=most sensitive, 63=least)

// --- Driver instance (SPI) ---
TMC2130Stepper driver(X_CS_PIN, R_SENSE);

// --- State ---
bool motorsEnabled = false;
uint16_t stepDelayUs = DEFAULT_STEP_DELAY;
uint16_t currentMA = DEFAULT_CURRENT_MA;
uint16_t microsteps = DEFAULT_MICROSTEPS;
int32_t position = 0;        // Current position in steps (0 = home end)
bool isHomed = false;        // Whether homing has been performed

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
 * Configure TMC2130 driver via SPI for linear rail operation.
 *
 * Uses SpreadCycle mode for dynamic torque, 16 microsteps with
 * interpolation to 256, and StallGuard enabled for sensorless homing.
 */
void configureDriver() {
    driver.begin();
    driver.toff(4);                         // Enable driver (chopper on)
    driver.rms_current(currentMA);          // Set motor current
    driver.microsteps(microsteps);          // Set microstepping
    driver.en_pwm_mode(false);              // SpreadCycle mode (not StealthChop)
    driver.pwm_autoscale(true);             // Auto-scale PWM
    driver.intpol(true);                    // Interpolate to 256 microsteps
    driver.TCOOLTHRS(0xFFFFF);              // StallGuard active at all velocities
    driver.sgt(STALLGUARD_SGT);             // StallGuard sensitivity
    driver.diag1_stall(true);              // DIAG1 pin = StallGuard output

    // Verify communication
    uint8_t version = driver.version();
    Serial.print(F("  X-axis: "));
    if (version == 0x11) {
        Serial.println(F("OK (TMC2130)"));
    } else {
        Serial.print(F("COMM ERROR (ver=0x"));
        Serial.print(version, HEX);
        Serial.println(F(")"));
    }
}

/**
 * Enable or disable the stepper motor driver.
 *
 * Einsy enable pin is active LOW.
 *
 * @param enabled  true to enable motor, false to disable
 */
void setMotorEnabled(bool enabled) {
    digitalWrite(X_EN_PIN, enabled ? LOW : HIGH);
    motorsEnabled = enabled;
}

/**
 * Calculate step delay using sinusoidal (half-cosine) acceleration profile.
 *
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
 * Check for E-STOP byte ('!') in serial buffer.
 *
 * Called periodically during motion. If '!' is found, immediately
 * disables motor and returns true.
 *
 * @return true if E-STOP was triggered, false otherwise
 */
bool checkEstop() {
    if (Serial.available()) {
        char c = Serial.peek();
        if (c == '!') {
            Serial.read();  // Consume the '!'
            setMotorEnabled(false);
            Serial.println(F("OK ESTOP"));
            return true;
        }
    }
    return false;
}

/**
 * Move the linear axis with sinusoidal acceleration ramp and soft limits.
 *
 * Enforces soft limits (0 to MAX_TRAVEL_STEPS). Checks for E-STOP
 * every step. Updates position tracking on completion or interruption.
 *
 * @param steps      Number of steps to move
 * @param forward    Direction (true = toward max travel, false = toward home)
 * @param cruiseDelay Target cruise speed in microseconds
 * @return           true if move completed, false if interrupted by E-STOP
 */
bool moveLinear(uint32_t steps, bool forward, uint16_t cruiseDelay) {
    if (!motorsEnabled) {
        Serial.println(F("ERR DISABLED"));
        return false;
    }

    // Enforce soft limits: clamp steps if move would exceed bounds
    if (forward) {
        int32_t maxAllowed = MAX_TRAVEL_STEPS - position;
        if (maxAllowed <= 0) {
            Serial.println(F("ERR LIMIT_MAX"));
            return false;
        }
        if ((int32_t)steps > maxAllowed) {
            steps = (uint32_t)maxAllowed;
        }
    } else {
        int32_t maxAllowed = position;  // distance to 0
        if (maxAllowed <= 0) {
            Serial.println(F("ERR LIMIT_MIN"));
            return false;
        }
        if ((int32_t)steps > maxAllowed) {
            steps = (uint32_t)maxAllowed;
        }
    }

    if (steps == 0) return true;

    digitalWrite(X_DIR_PIN, forward ? HIGH : LOW);
    delayMicroseconds(5);

    for (uint32_t i = 0; i < steps; i++) {
        // E-STOP check every step
        if (checkEstop()) {
            // Update position with steps completed
            if (forward) {
                position += (int32_t)i;
            } else {
                position -= (int32_t)i;
            }
            return false;
        }

        uint16_t d = rampDelay(i, steps, cruiseDelay);
        digitalWrite(X_STEP_PIN, HIGH);
        delayMicroseconds(d);
        digitalWrite(X_STEP_PIN, LOW);
        delayMicroseconds(d);
    }

    // Update position
    if (forward) {
        position += (int32_t)steps;
    } else {
        position -= (int32_t)steps;
    }
    return true;
}

/**
 * Sensorless homing using StallGuard.
 *
 * Moves slowly toward the home end (direction = LOW) until StallGuard
 * detects a stall (end of rail). Then backs off slightly and sets
 * position to 0.
 *
 * No gearbox on linear rail means clean back-EMF signal — StallGuard
 * works reliably unlike the cycloidal gearbox joints.
 */
void homeLinear() {
    if (!motorsEnabled) {
        Serial.println(F("ERR DISABLED"));
        return;
    }
    Serial.print(F("Homing..."));
    driver.en_pwm_mode(false);
    delay(100);
    driver.sgt(STALLGUARD_SGT);

    // === Pass 1: Fast approach toward endstop ===
    digitalWrite(X_DIR_PIN, HIGH);
    delayMicroseconds(5);
    bool stalled = false;
    for (uint32_t i = 0; i < HOMING_MAX_STEPS; i++) {
        if (checkEstop()) return;
        digitalWrite(X_STEP_PIN, HIGH);
        delayMicroseconds(HOMING_FAST_DELAY);
        digitalWrite(X_STEP_PIN, LOW);
        delayMicroseconds(HOMING_FAST_DELAY);
        if ((i & 0x07) == 0 && i > 100) {
            uint32_t drv_status = driver.DRV_STATUS();
            if ((drv_status & 0x3FF) == 0) { stalled = true; break; }
        }
    }
    if (!stalled) { Serial.println(F(" FAIL pass1")); return; }

    // Back off 5mm
    digitalWrite(X_DIR_PIN, LOW);
    delayMicroseconds(5);
    for (uint16_t i = 0; i < HOMING_BACKOFF; i++) {
        digitalWrite(X_STEP_PIN, HIGH);
        delayMicroseconds(HOMING_FAST_DELAY);
        digitalWrite(X_STEP_PIN, LOW);
        delayMicroseconds(HOMING_FAST_DELAY);
    }
    delay(200);

    // === Pass 2: Slow verify ===
    Serial.print(F(" v1"));
    digitalWrite(X_DIR_PIN, HIGH);
    delayMicroseconds(5);
    stalled = false;
    for (uint32_t i = 0; i < HOMING_MAX_STEPS; i++) {
        if (checkEstop()) return;
        digitalWrite(X_STEP_PIN, HIGH);
        delayMicroseconds(HOMING_SLOW_DELAY);
        digitalWrite(X_STEP_PIN, LOW);
        delayMicroseconds(HOMING_SLOW_DELAY);
        if ((i & 0x07) == 0 && i > 50) {
            uint32_t drv_status = driver.DRV_STATUS();
            if ((drv_status & 0x3FF) == 0) { stalled = true; break; }
        }
    }
    if (!stalled) { Serial.println(F(" FAIL v1")); return; }

    // Back off 5mm
    digitalWrite(X_DIR_PIN, LOW);
    delayMicroseconds(5);
    for (uint16_t i = 0; i < HOMING_BACKOFF; i++) {
        digitalWrite(X_STEP_PIN, HIGH);
        delayMicroseconds(HOMING_SLOW_DELAY);
        digitalWrite(X_STEP_PIN, LOW);
        delayMicroseconds(HOMING_SLOW_DELAY);
    }
    delay(200);

    // === Pass 3: Final slow verify ===
    Serial.print(F(" v2"));
    digitalWrite(X_DIR_PIN, HIGH);
    delayMicroseconds(5);
    stalled = false;
    for (uint32_t i = 0; i < HOMING_MAX_STEPS; i++) {
        if (checkEstop()) return;
        digitalWrite(X_STEP_PIN, HIGH);
        delayMicroseconds(HOMING_SLOW_DELAY);
        digitalWrite(X_STEP_PIN, LOW);
        delayMicroseconds(HOMING_SLOW_DELAY);
        if ((i & 0x07) == 0 && i > 50) {
            uint32_t drv_status = driver.DRV_STATUS();
            if ((drv_status & 0x3FF) == 0) { stalled = true; break; }
        }
    }
    if (!stalled) { Serial.println(F(" FAIL v2")); return; }

    // Back off 5mm
    digitalWrite(X_DIR_PIN, LOW);
    delayMicroseconds(5);
    for (uint16_t i = 0; i < HOMING_BACKOFF; i++) {
        digitalWrite(X_STEP_PIN, HIGH);
        delayMicroseconds(HOMING_SLOW_DELAY);
        digitalWrite(X_STEP_PIN, LOW);
        delayMicroseconds(HOMING_SLOW_DELAY);
    }

    // === Move to center (max_travel / 2) ===
    Serial.print(F(" center"));
    int32_t centerSteps = MAX_TRAVEL_STEPS / 2;
    digitalWrite(X_DIR_PIN, LOW);
    delayMicroseconds(5);
    for (int32_t i = 0; i < centerSteps; i++) {
        if (checkEstop()) return;
        digitalWrite(X_STEP_PIN, HIGH);
        delayMicroseconds(HOMING_FAST_DELAY);
        digitalWrite(X_STEP_PIN, LOW);
        delayMicroseconds(HOMING_FAST_DELAY);
    }

    position = centerSteps;
    isHomed = true;
    Serial.print(F(" OK H "));
    Serial.println(position);
}

/**
 * Parse and execute serial commands.
 *
 * @param cmd  Newline-terminated command string
 */
void handleCommand(String &cmd) {
    cmd.trim();
    if (cmd.length() == 0) return;

    char type = cmd.charAt(0);

    switch (type) {
        case 'E': {
            // Enable/disable motor: E1 or E0
            if (cmd.length() >= 2) {
                bool en = (cmd.charAt(1) == '1');
                setMotorEnabled(en);
                Serial.print(F("OK E"));
                Serial.println(en ? '1' : '0');
            }
            break;
        }

        case 'M': {
            // Move: M0 <steps> <dir> <delay>
            // Only joint 0 exists on this board
            int joint = cmd.substring(1, 2).toInt();
            if (joint != 0) {
                Serial.println(F("ERR PARAM (only M0)"));
                break;
            }

            int idx = cmd.indexOf(' ', 1);
            if (idx < 0) {
                Serial.println(F("ERR PARAM"));
                break;
            }

            long steps = cmd.substring(idx + 1).toInt();
            int dir = 0;
            int delayVal = stepDelayUs;

            idx = cmd.indexOf(' ', idx + 1);
            if (idx > 0) {
                dir = cmd.substring(idx + 1).toInt();
                int idx2 = cmd.indexOf(' ', idx + 1);
                if (idx2 > 0) delayVal = cmd.substring(idx2 + 1).toInt();
            }

            if (steps <= 0) {
                Serial.println(F("ERR PARAM"));
                break;
            }
            if (delayVal < MIN_STEP_DELAY) delayVal = MIN_STEP_DELAY;
            if (delayVal > MAX_STEP_DELAY) delayVal = MAX_STEP_DELAY;

            bool completed = moveLinear((uint32_t)steps, (dir == 0), (uint16_t)delayVal);
            if (completed) {
                Serial.print(F("OK M0 "));
                Serial.println(position);
            }
            break;
        }

        case 'S': {
            // Query state: "S <enabled> <position>"
            Serial.print(F("S "));
            Serial.print(motorsEnabled ? '1' : '0');
            Serial.print(' ');
            Serial.println(position);
            break;
        }

        case 'R': {
            // Reset position to 0
            position = 0;
            isHomed = false;
            Serial.println(F("OK R"));
            break;
        }

        case 'H': {
            // Home: StallGuard sensorless homing
            homeLinear();
            break;
        }

        case '!': {
            // E-STOP: immediate halt
            setMotorEnabled(false);
            Serial.println(F("OK ESTOP"));
            break;
        }

        case 'D': {
            // Diagnostic: read StallGuard status
            uint32_t drv_status = driver.DRV_STATUS();
            uint16_t sg_result = drv_status & 0x3FF;
            bool sg_triggered = (drv_status >> 24) & 0x01;
            bool stall_flag = (drv_status >> 31) & 0x01;
            int diag_pin = digitalRead(X_DIAG_PIN);
            Serial.print(F("DIAG pin="));
            Serial.print(diag_pin);
            Serial.print(F(" SG_RESULT="));
            Serial.print(sg_result);
            Serial.print(F(" stallGuard="));
            Serial.print(sg_triggered);
            Serial.print(F(" stall="));
            Serial.print(stall_flag);
            Serial.print(F(" DRV_STATUS=0x"));
            Serial.println(drv_status, HEX);
            break;
        }

        case '?': {
            // Help
            Serial.println(F("=== Armold Einsy Linear Rail Controller ==="));
            Serial.println(F("Protocol:"));
            Serial.println(F("  E1/E0                  - Enable/disable motor"));
            Serial.println(F("  M0 <steps> <dir> <dly> - Move linear axis"));
            Serial.println(F("  S                      - Query state"));
            Serial.println(F("  R                      - Reset position to 0"));
            Serial.println(F("  H                      - Home (StallGuard)"));
            Serial.println(F("  !                      - E-STOP"));
            Serial.println();
            Serial.print(F("Config: "));
            Serial.print(STEPS_PER_MM);
            Serial.print(F(" steps/mm, "));
            Serial.print(MAX_TRAVEL_MM);
            Serial.print(F("mm max travel ("));
            Serial.print(MAX_TRAVEL_STEPS);
            Serial.println(F(" steps)"));
            Serial.print(F("State: "));
            Serial.print(motorsEnabled ? "EN" : "DIS");
            Serial.print(F(" I="));
            Serial.print(currentMA);
            Serial.print(F("mA U="));
            Serial.print(microsteps);
            Serial.print(F(" POS="));
            Serial.print(position);
            Serial.print(F(" HOMED="));
            Serial.println(isHomed ? "YES" : "NO");
            break;
        }

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
    pinMode(X_STEP_PIN, OUTPUT);
    pinMode(X_DIR_PIN, OUTPUT);
    pinMode(X_EN_PIN, OUTPUT);
    pinMode(X_DIAG_PIN, INPUT);

    // Disable motor during setup
    setMotorEnabled(false);

    Serial.println(F(""));
    Serial.println(F("ARMOLD EINSY_LINEAR 1.0"));
    Serial.println(F("TMC2130 SPI, 1-axis linear rail"));
    Serial.println(F("Initializing driver..."));

    // Configure TMC2130 driver via SPI
    configureDriver();

    Serial.print(F("Current: "));
    Serial.print(currentMA);
    Serial.print(F("mA, Microsteps: "));
    Serial.print(microsteps);
    Serial.println(F(", Mode: SpreadCycle"));
    Serial.print(F("Travel: "));
    Serial.print(MAX_TRAVEL_MM);
    Serial.print(F("mm ("));
    Serial.print(MAX_TRAVEL_STEPS);
    Serial.print(F(" steps @ "));
    Serial.print(STEPS_PER_MM);
    Serial.println(F(" steps/mm)"));
    Serial.println(F("READY"));
}

void loop() {
    if (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        handleCommand(cmd);
    }
}
