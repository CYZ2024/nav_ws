#!/bin/bash
# Start Cartographer SLAM mapping mode (YDLIDAR X3 via vp100_ros2 + Cartographer)
# Usage: ./start_mapping.sh

set -e

echo "=== Starting YDLIDAR X3 + Cartographer SLAM mapping ==="

# Source ROS2 environment
source /opt/tros/humble/setup.bash
source /userdata/dev_ws/install/setup.bash 2>/dev/null || true
source /home/sunrise/Project/nav_ws/install/setup.bash

# Launch mapping (LiDAR + Cartographer, no Nav2, no nav_bridge)
ros2 launch rdk_x5_nav_assistant nav_bringup.launch.py \
    use_nav2:=false \
    use_nav_bridge:=false
