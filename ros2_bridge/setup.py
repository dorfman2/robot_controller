"""Setup file for the armold_bridge ROS 2 package."""
from setuptools import find_packages, setup

package_name = 'armold_bridge'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/bridge.launch.py']),
    ],
    install_requires=['setuptools', 'pyserial'],
    zip_safe=True,
    maintainer='Jeffrey Dorfman',
    maintainer_email='jdorfman@users.noreply.github.com',
    description='ROS 2 serial bridge for Armold robot arm stepper controller',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'serial_bridge = armold_bridge.serial_bridge:main',
        ],
    },
)
