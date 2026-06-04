#!/bin/bash
# Start Cartographer mapping mode (for building a new map)
# Usage: ./start_mapping.sh

set -e

cd /home/sunrise/Project/nav_ws
source /opt/tros/humble/setup.bash
source install/setup.bash

echo "========================================"
echo "Starting Cartographer 2D SLAM (mapping mode)"
echo "========================================"
echo ""
echo "Push the shopping cart slowly around the supermarket."
echo "When finished, run: ./scripts/save_map.sh"
echo ""

# Start only LiDAR + Cartographer (no Nav2, no bridge)
ros2 launch rdk_x5_nav_assistant nav_bringup.launch.py \
    use_nav2:=false \
    use_nav_bridge:=false
