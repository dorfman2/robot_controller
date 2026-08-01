# Mesa + LinuxCNC — Design

## LinuxCNC INI (Key Settings)

```ini
[KINS]
KINEMATICS = genserkins
JOINTS = 7

[JOINT_0]
TYPE = LINEAR
SCALE = 80.0
MAX_VELOCITY = 80

[JOINT_1-5]
TYPE = ANGULAR
SCALE = 230.6
MAX_VELOCITY = 30

[JOINT_6]
TYPE = ANGULAR
SCALE = 8.889
MAX_VELOCITY = 60
```

## DM542TE DIP Switches

Microstep 16: SW5=ON SW6=OFF SW7=ON SW8=OFF
Current 2.0A: SW1=OFF SW2=ON SW3=OFF
Current 3.0A (J3): SW1=ON SW2=OFF SW3=ON

## Migration Path
1. Acquire Mesa 7i96S + 7i74
2. Install LinuxCNC on PC
3. Wire DM542TE to Mesa
4. Configure HAL + INI + genserkins
5. Port armold_controller
6. Retire BTT + Pi from motion path
