#!/bin/bash
# Start full navigation mode (YDLIDAR X3 via vp100_ros2 + Cartographer localization + Nav2 + nav_bridge)
# Usage: ./start_navigation.sh [path_to.pbstream]

set -e

MAP_FILE="${1:-}"

echo "=== Starting YDLIDAR X3 + Cartographer + Nav2 navigation ==="

if [ -n "$MAP_FILE" ]; then
    echo "Loading map: $MAP_FILE"
else
    echo "WARNING: No map file specified. Cartographer will run in SLAM mode."
    echo "Usage: ./start_navigation.sh /path/to/map.pbstream"
fi

# Source ROS2 environment
source /opt/tros/humble/setup.bash
source /userdata/dev_ws/install/setup.bash 2>/dev/null || true
source /home/sunrise/Project/nav_ws/install/setup.bash

# Launch full navigation
if [ -n "$MAP_FILE" ]; then
    ros2 launch rdk_x5_nav_assistant nav_bringup.launch.py \
        load_state_filename:="$MAP_FILE"
else
    ros2 launch rdk_x5_nav_assistant nav_bringup.launch.py
fi
