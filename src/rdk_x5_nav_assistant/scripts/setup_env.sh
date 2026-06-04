#!/bin/bash
# Setup ROS2 environment for robot-nav (RDK X5)
# Source this script: source ./setup_env.sh

# ROS2 Humble / TogetheROS
source /opt/tros/humble/setup.bash

# YDLIDAR X3 driver (vp100_ros2) workspace
source /userdata/dev_ws/install/setup.bash 2>/dev/null || true

# nav_ws
if [ -f /home/sunrise/Project/nav_ws/install/setup.bash ]; then
    source /home/sunrise/Project/nav_ws/install/setup.bash
fi

# Fast DDS Discovery Server (for cross-board ROS2 communication)
# Uncomment and adjust if using discovery server
# export ROS_DOMAIN_ID=43
# export ROS_LOCALHOST_ONLY=0
# export ROS_DISCOVERY_SERVER=10.0.0.5:11811

# Set ROS2 logging to show more detail during debugging
export RCUTILS_CONSOLE_OUTPUT_FORMAT="[{severity}] [{time}] [{name}]: {message}"

echo "=== ROS2 environment ready ==="
echo "ROS_DISTRO: $ROS_DISTRO"
echo "ROS_DOMAIN_ID: $ROS_DOMAIN_ID"
