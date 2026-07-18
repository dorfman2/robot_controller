"""Launch file for the Armold serial bridge node."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    """Generate launch description for the armold_bridge serial bridge.

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
                'serial_port': '/dev/armold_ramps',
                'baud_rate': 115200,
                'step_delay': 200,
                'poll_rate': 5.0,
            }],
        ),
    ])
