"""Setup script for the armold_can_driver ament_python package."""

from setuptools import find_packages, setup

package_name = "armold_can_driver"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Jeffrey Dorfman",
    maintainer_email="jdorfman@users.noreply.github.com",
    description=(
        "Protocol driver for thingsbyjosh CANBUS Stepper nodes: vendor CAN "
        "frame encode/decode plus joint<->motor gear/unit mapping."
    ),
    license="MIT",
    tests_require=["pytest"],
    entry_points={"console_scripts": []},
)
