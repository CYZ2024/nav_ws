#!/bin/bash
# Start full navigation stack with pre-built map
# Usage: ./start_navigation.sh /path/to/map.pbstream

set -e

MAP_FILE="${1:-/home/sunrise/Project/nav_ws/maps/supermarket.pbstream}"

cd /home/sunrise/Project/nav_ws
source /opt/tros/humble/setup.bash
source install/setup.bash

if [ ! -f "$MAP_FILE" ]; then
    echo "ERROR: Map file not found: $MAP_FILE"
    echo "Please build a map first using ./scripts/start_mapping.sh"
    exit 1
fi

echo "========================================"
echo "Starting navigation with map: $MAP_FILE"
echo "========================================"
echo ""

# Start full stack: LiDAR + Cartographer localization + Nav2 + bridge
ros2 launch rdk_x5_nav_assistant nav_bringup.launch.py \
    load_state_filename:="$MAP_FILE"
