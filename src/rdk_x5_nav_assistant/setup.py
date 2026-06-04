from glob import glob
import os

from setuptools import find_packages, setup

package_name = "rdk_x5_nav_assistant"

setup(
    name=package_name,
    version="0.2.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/config", glob(os.path.join("config", "*.yaml"))),
        (f"share/{package_name}/config/cartographer", glob(os.path.join("config", "cartographer", "*.lua"))),
        (f"share/{package_name}/config/nav2", glob(os.path.join("config", "nav2", "*.yaml"))),
        (f"share/{package_name}/config/audio", glob(os.path.join("config", "audio", "*.json"))),
        (f"share/{package_name}/config/audio/hrsc", glob(os.path.join("config", "audio", "hrsc", "*.json"))),
        (f"share/{package_name}/launch", glob(os.path.join("launch", "*.launch.py"))),
        (f"share/{package_name}/maps", glob(os.path.join("maps", "*"))),
        (f"share/{package_name}/scripts", glob(os.path.join("scripts", "*.sh"))),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="sunrise",
    maintainer_email="sunrise@example.com",
    description="Navigation board for RDK X5 shopping assistant. LiDAR + Cartographer 2D SLAM + Nav2. No vision.",
    license="Apache License 2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "localization_bridge = rdk_x5_nav_assistant.localization_bridge:main",
            "nav_goal_bridge = rdk_x5_nav_assistant.nav_goal_bridge:main",
        ],
    },
)
