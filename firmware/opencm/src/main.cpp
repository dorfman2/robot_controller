/**
 * Armold - OpenCM 9.04 Dynamixel Servo Test
 *
 * Basic hardware test firmware for OpenCM 9.04 board.
 * Controls Dynamixel XL430-W250 (joints 3, 4) and XL-320 (joint 5 + gripper)
 * individually to verify wiring and servo communication.
 *
 * Dynamixel protocol 2.0 is used for both XL430-W250 and XL-320 servos.
 *
 * Default servo IDs:
 *   Joint 3 (XL430-W250): ID 1
 *   Joint 4 (XL430-W250): ID 2
 *   Joint 5 (XL-320):     ID 3
 *   Gripper (XL-320):     ID 4
 *
 * Serial commands (115200 baud):
 *   'e' - Enable torque on all servos
 *   'd' - Disable torque on all servos
 *   '3' - Move joint 3 to center position (2048)
 *   '4' - Move joint 4 to center position (2048)
 *   '5' - Move joint 5 to center position (512)
 *   'g' - Toggle gripper (open/close)
 *   'p' - Print current positions of all servos
 *   '+' - Increment target position by 100
 *   '-' - Decrement target position by 100
 *   '?' - Print help
 *
 * Wiring:
 *   OpenCM 9.04 DXL port -> Dynamixel daisy chain
 *   Power: 24V DC (XL430) or 7.4V (XL-320, via OpenCM 485 expansion or separate supply)
 *
 * NOTE: If using the OpenCM 485 Expansion Board, the DXL port on the expansion
 *       handles both TTL and RS-485 servos with appropriate power routing.
 */

#include <Arduino.h>
#include <Dynamixel2Arduino.h>

// --- OpenCM 9.04 DXL Serial Port ---
// On OpenCM 9.04, the Dynamixel bus uses Serial1 (hardware UART)
// DXL direction pin is pin 28 on OpenCM 9.04
#define DXL_SERIAL   Serial1
#define DXL_DIR_PIN  28

// --- Servo IDs ---
#define JOINT3_ID    1   // XL430-W250
#define JOINT4_ID    2   // XL430-W250
#define JOINT5_ID    3   // XL-320
#define GRIPPER_ID   4   // XL-320

// --- Position Limits ---
// XL430-W250: 0-4095 (0-360 degrees)
#define XL430_CENTER    2048
#define XL430_MIN       0
#define XL430_MAX       4095

// XL-320: 0-1023 (0-300 degrees)
#define XL320_CENTER    512
#define XL320_MIN       0
#define XL320_MAX       1023

// Gripper positions
#define GRIPPER_OPEN    200
#define GRIPPER_CLOSED  512

// --- Configuration ---
#define DXL_BAUDRATE    1000000  // Dynamixel bus baud rate (1Mbps default)
#define SERIAL_BAUD     115200   // USB serial monitor baud rate

// --- State ---
Dynamixel2Arduino dxl(DXL_SERIAL, DXL_DIR_PIN);
bool gripperClosed = false;
int16_t positionOffset = 0;  // Adjustable offset for testing

using namespace ControlTableItem;

/**
 * Enable or disable torque on all servos.
 *
 * @param enabled  true to enable torque, false to disable
 */
void setTorqueAll(bool enabled) {
    dxl.torqueOn(JOINT3_ID);
    dxl.torqueOn(JOINT4_ID);
    dxl.torqueOn(JOINT5_ID);
    dxl.torqueOn(GRIPPER_ID);

    if (!enabled) {
        dxl.torqueOff(JOINT3_ID);
        dxl.torqueOff(JOINT4_ID);
        dxl.torqueOff(JOINT5_ID);
        dxl.torqueOff(GRIPPER_ID);
    }
}

/**
 * Read and print current position of all servos.
 */
void printPositions() {
    Serial.println(F("--- Current Positions ---"));

    int32_t pos3 = dxl.getPresentPosition(JOINT3_ID);
    int32_t pos4 = dxl.getPresentPosition(JOINT4_ID);
    int32_t pos5 = dxl.getPresentPosition(JOINT5_ID);
    int32_t posG = dxl.getPresentPosition(GRIPPER_ID);

    Serial.print(F("  Joint 3 (ID "));
    Serial.print(JOINT3_ID);
    Serial.print(F("): "));
    Serial.println(pos3);

    Serial.print(F("  Joint 4 (ID "));
    Serial.print(JOINT4_ID);
    Serial.print(F("): "));
    Serial.println(pos4);

    Serial.print(F("  Joint 5 (ID "));
    Serial.print(JOINT5_ID);
    Serial.print(F("): "));
    Serial.println(pos5);

    Serial.print(F("  Gripper (ID "));
    Serial.print(GRIPPER_ID);
    Serial.print(F("): "));
    Serial.println(posG);

    Serial.println(F("-------------------------"));
}

/**
 * Print available commands to serial monitor.
 */
void printHelp() {
    Serial.println(F("=== Armold OpenCM 9.04 Servo Test ==="));
    Serial.println(F("Commands:"));
    Serial.println(F("  e - Enable torque (all servos)"));
    Serial.println(F("  d - Disable torque (all servos)"));
    Serial.println(F("  3 - Move joint 3 to center + offset"));
    Serial.println(F("  4 - Move joint 4 to center + offset"));
    Serial.println(F("  5 - Move joint 5 to center + offset"));
    Serial.println(F("  g - Toggle gripper (open/close)"));
    Serial.println(F("  p - Print current positions"));
    Serial.println(F("  + - Increase offset by 100"));
    Serial.println(F("  - - Decrease offset by 100"));
    Serial.println(F("  ? - Print this help"));
    Serial.println();
    Serial.print(F("Position offset: "));
    Serial.println(positionOffset);
    Serial.print(F("Gripper: "));
    Serial.println(gripperClosed ? "CLOSED" : "OPEN");
}

/**
 * Move a servo to a target position, clamped to its valid range.
 *
 * @param id       Servo ID
 * @param target   Target position (raw encoder units)
 * @param minPos   Minimum valid position
 * @param maxPos   Maximum valid position
 */
void moveServo(uint8_t id, int32_t target, int32_t minPos, int32_t maxPos) {
    target = constrain(target, minPos, maxPos);
    dxl.setGoalPosition(id, target);
    Serial.print(F("  -> ID "));
    Serial.print(id);
    Serial.print(F(" goal: "));
    Serial.println(target);
}

void setup() {
    Serial.begin(SERIAL_BAUD);

    // Initialize Dynamixel bus
    dxl.begin(DXL_BAUDRATE);
    dxl.setPortProtocolVersion(2.0);

    // Ping each servo to verify communication
    Serial.println(F(""));
    Serial.println(F("Armold OpenCM 9.04 Servo Test"));
    Serial.println(F("Scanning for servos..."));

    bool found3 = dxl.ping(JOINT3_ID);
    bool found4 = dxl.ping(JOINT4_ID);
    bool found5 = dxl.ping(JOINT5_ID);
    bool foundG = dxl.ping(GRIPPER_ID);

    Serial.print(F("  Joint 3 (ID "));
    Serial.print(JOINT3_ID);
    Serial.println(found3 ? "): FOUND" : "): NOT FOUND");

    Serial.print(F("  Joint 4 (ID "));
    Serial.print(JOINT4_ID);
    Serial.println(found4 ? "): FOUND" : "): NOT FOUND");

    Serial.print(F("  Joint 5 (ID "));
    Serial.print(JOINT5_ID);
    Serial.println(found5 ? "): FOUND" : "): NOT FOUND");

    Serial.print(F("  Gripper (ID "));
    Serial.print(GRIPPER_ID);
    Serial.println(foundG ? "): FOUND" : "): NOT FOUND");

    Serial.println(F("---"));
    Serial.println(F("Send '?' for commands"));
}

void loop() {
    if (Serial.available()) {
        char cmd = Serial.read();

        switch (cmd) {
            case 'e':
                setTorqueAll(true);
                Serial.println(F("Torque ENABLED (all servos)"));
                break;

            case 'd':
                setTorqueAll(false);
                Serial.println(F("Torque DISABLED (all servos)"));
                break;

            case '3':
                Serial.println(F("Moving joint 3..."));
                moveServo(JOINT3_ID, XL430_CENTER + positionOffset, XL430_MIN, XL430_MAX);
                break;

            case '4':
                Serial.println(F("Moving joint 4..."));
                moveServo(JOINT4_ID, XL430_CENTER + positionOffset, XL430_MIN, XL430_MAX);
                break;

            case '5':
                Serial.println(F("Moving joint 5..."));
                moveServo(JOINT5_ID, XL320_CENTER + positionOffset, XL320_MIN, XL320_MAX);
                break;

            case 'g':
                gripperClosed = !gripperClosed;
                if (gripperClosed) {
                    moveServo(GRIPPER_ID, GRIPPER_CLOSED, XL320_MIN, XL320_MAX);
                    Serial.println(F("Gripper: CLOSING"));
                } else {
                    moveServo(GRIPPER_ID, GRIPPER_OPEN, XL320_MIN, XL320_MAX);
                    Serial.println(F("Gripper: OPENING"));
                }
                break;

            case 'p':
                printPositions();
                break;

            case '+':
                positionOffset += 100;
                Serial.print(F("Offset: "));
                Serial.println(positionOffset);
                break;

            case '-':
                positionOffset -= 100;
                Serial.print(F("Offset: "));
                Serial.println(positionOffset);
                break;

            case '?':
                printHelp();
                break;

            case '\n':
            case '\r':
                // Ignore newlines
                break;

            default:
                Serial.print(F("Unknown command: "));
                Serial.println(cmd);
                Serial.println(F("Send '?' for help"));
                break;
        }
    }
}
