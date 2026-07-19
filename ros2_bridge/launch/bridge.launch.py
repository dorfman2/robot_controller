"""Launch file for the Armold dual-board serial bridge node."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    """Generate launch description for the armold_bridge serial bridge.

    Configures dual-board setup:
        Board 1 (Einsy): /dev/armold_einsy — Joints 0-3
        Board 2 (RAMPS): /dev/armold_ramps — Joints 4-5 (disabled until wired)

    Returns:
        LaunchDescription with the serial_bridge node configured.
    """
    return LaunchDescription([
        Node(
            package='armold_bridge',
            executable='serial_bridge',
            name='armold_serial_bridge',
            output='screen',
            parameters=[{
                'board1_port': '/dev/armold_einsy',
                'board2_port': '/dev/armold_ramps',
                'baud_rate': 115200,
                'step_delay': 30,
                'poll_rate': 2.0,
                'board2_enabled': False,
            }],
        ),
    ])
