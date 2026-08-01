# Mesa + LinuxCNC — Tasks

## Phase 1: Hardware Acquisition
- [ ] Order Mesa 7i96S (~$240)
- [ ] Order Mesa 7i74 SPI expansion (~$160)
- [ ] Order 1x additional DM542TE for linear rail (~$20)
- [ ] Order limit switches for rail homing (2x NC microswitch)
- [ ] Designate PC for LinuxCNC (any x86, 2+ GHz)

## Phase 2: PC + LinuxCNC Setup
- [ ] Install Debian 12 with PREEMPT_RT kernel
- [ ] Install LinuxCNC 2.9+
- [ ] Run latency test (must pass <25us jitter)
- [ ] Configure Ethernet for Mesa (static IP 10.10.10.x)
- [ ] Verify Mesa detected: mesaflash --device 7i96s --readhmid
- [ ] Flash Mesa firmware for 7-axis step/dir

## Phase 3: DM542TE Wiring
- [ ] Set microsteps: 16 on all DM542TE (DIP switches)
- [ ] Set current: 1.5A RMS most, 2.5A J3 (DIP switches)
- [ ] Wire Mesa 7i96S → DM542TE x5 (rail, J0, J1, J2, J3)
- [ ] Wire Mesa 7i74 → DM542TE x2 (J4, J5)
- [ ] Wire E-STOP button → Mesa digital input
- [ ] Wire limit switches → Mesa (rail only)
- [ ] Wire gripper servo (Mesa PWM or external controller)
- [ ] Connect 24V PSU to DM542TE power inputs
- [ ] Connect motors to DM542TE outputs

## Phase 4: LinuxCNC Configuration
- [ ] Create INI file (7 joints, axis limits, homing)
- [ ] Create HAL file (Mesa pins, step generators)
- [ ] Configure genserkins DH parameters
- [ ] Set steps/unit: rail=80, joints=230.6, J5=8.889
- [ ] Configure homing: rail via limit switch, arm manual
- [ ] Configure E-STOP chain in HAL
- [ ] Test each axis via Axis GUI

## Phase 5: IK + Arm Control
- [ ] Configure genserkins with Armold DH parameters
- [ ] Verify FK and IK
- [ ] Test coordinated multi-axis motion
- [ ] Verify smooth trajectory
- [ ] Test variable-speed jog

## Phase 6: armold_controller Integration
- [ ] Port KlipperBoard → LinuxCNCBoard class
- [ ] Interface via Python linuxcnc module
- [ ] Map WebSocket commands to MDI commands
- [ ] Position polling from stat channel
- [ ] E-STOP via command channel
- [ ] Test web UI end-to-end

## Phase 7: Validation
- [ ] 1-hour IK demo (smooth motion, no crashes)
- [ ] E-STOP latency <1ms
- [ ] Position accuracy ±0.1 deg
- [ ] Vision pipeline on LinuxCNC PC
- [ ] Document configuration
- [ ] Decommission BTT + Pi from motion path
