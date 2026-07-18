/**
 * Stepper Motor Controller
 *
 * Lightweight stepper driver for use with RAMPS 1.4 stepper driver slots.
 * Handles acceleration-free positional moves with speed limiting.
 * Designed to be called from a timer ISR at high frequency (10 kHz).
 *
 * Source: Adapted from RoboLabHub/Niryo
 */

#ifndef STEPPER_H
#define STEPPER_H

#include <Arduino.h>

void ROSLog(char* str);

static int kSpeedDelta = 10;

class StepperController
{
public:
    StepperController(uint8_t stepPin, uint8_t dirPin, uint8_t enablePin)
    {
        m_stepPin   = stepPin;
        m_dirPin    = dirPin;
        m_enablePin = enablePin;

        m_prevRunTime = 0;
        m_prevPosTime = 0;

        m_maxSpeed  = 1;
        m_currSpeed = 0;
        m_goalSpeed = 0;

        m_motorEnabled = false;

        setCurrentPosition(0);
    }

    void CalculateStepInterval()
    {
        m_currSpeed = m_goalSpeed;
        m_stepInterval = 1000000.0 / m_currSpeed;
    }

    void setTargetPos(int16_t targetPos)
    {
        uint32_t now = millis();
        m_prevPosTime = now;

        if (targetPos != m_currentPos)
        {
            float steps = abs(targetPos - m_currentPos);
            float goalSpeed = (steps / 0.02);  // Steps per sec based on 20Hz publish rate
            if (goalSpeed > m_maxSpeed)
                goalSpeed = m_maxSpeed;

            m_goalSpeed = goalSpeed;
            m_targetPos = targetPos;

            CalculateStepInterval();
        }
    }

    void setMaxSpeed(int16_t speed) { m_maxSpeed = speed; }

    void setCurrentPosition(int16_t pos)
    {
        m_stepInterval = 0;
        m_targetPos = m_currentPos = pos;
    }

    int16_t getCurrentPosition() { return m_currentPos; }

    void enableMotor(boolean enable)
    {
        pinMode(m_stepPin,   OUTPUT);
        pinMode(m_dirPin,    OUTPUT);
        pinMode(m_enablePin, OUTPUT);

        digitalWrite(m_enablePin, enable ? LOW : HIGH);

        m_motorEnabled = enable;
    }

    void run()
    {
        if (m_motorEnabled && m_stepInterval != 0)
        {
            unsigned long now = micros();
            if ((now - m_prevRunTime) < m_stepInterval)
                return;
            m_prevRunTime = now;

            if (m_currentPos < m_targetPos) {
                doStep(true);
                m_currentPos++;
            }
            else if (m_currentPos > m_targetPos) {
                doStep(false);
                m_currentPos--;
            }

            if (abs(m_goalSpeed - m_currSpeed) > kSpeedDelta)
            {
                if (m_currSpeed < m_goalSpeed)
                    m_currSpeed += kSpeedDelta;
                else
                    m_currSpeed -= kSpeedDelta;

                CalculateStepInterval();
            }
        }
    }

protected:
    void doStep(boolean forwardMove)
    {
        digitalWrite(m_dirPin, forwardMove ? HIGH : LOW);

        digitalWrite(m_stepPin, HIGH);
        delayMicroseconds(1);
        digitalWrite(m_stepPin, LOW);
    }

    uint8_t m_stepPin;
    uint8_t m_dirPin;
    uint8_t m_enablePin;

    int16_t m_currentPos;
    int16_t m_targetPos;

    int16_t m_maxSpeed;
    int16_t m_currSpeed;
    int16_t m_goalSpeed;

    boolean m_motorEnabled;

    uint32_t        m_prevPosTime;
    unsigned long   m_prevRunTime;

    unsigned long   m_stepInterval;  // in microseconds
};

#endif // STEPPER_H
